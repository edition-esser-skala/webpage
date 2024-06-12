"""Common functions."""

from operator import itemgetter
import os
from collections import namedtuple
import re
import tempfile

import dateutil.parser
from git import Repo, Tag
from github.Organization import Organization
import strictyaml  # type: ignore

LICENSES = {
    "cc-by-sa-4.0": "![CC BY-SA 4.0](/assets/images/license_cc-by-sa.svg){:width='120px'}",
    "cc-by-nc-sa-4.0": "![CC BY-NC-SA 4.0](/assets/images/license_cc-by-nc-sa.svg){:width='120px'}"
}

PART_REPLACE = {
    # instrument names
    "bc_realized": "bc (realizzato)",
    "cord": "cor (D)",
    "corf": "cor (F)",
    "cemb_realized": "cemb (realizzato)",
    "full_score": "full score",
    "oba": "ob d'amore",
    "obdc": "ob da caccia",
    "org_realized": "org (realizzato)",
    "pf_red": "pf (riduzione)",

    # instrument numbers
    r"([\w\)])123$": r"\1 1, 2, 3",
    r"([\w\)])12$": r"\1 1, 2",
    r"([\w\)])(\d)$": r"\1 \2",

    # spaces
    r"[_ ]": r"&nbsp;"
}

SLUG_REPLACE = {
    " ": "-",
    ":": "-",
    "/": "-",
    ".": "-",
    ",": "",
    "(": "",
    ")": "",
    "·": "",
    "*": "star",
    "á": "a",
    "ä": "ae",
    "æ": "ae",
    "í": "i",
    "ö": "oe",
    "œ": "oe",
    "ß": "ss",
    "š": "s",
    "ü": "ue",
    "ů": "u",
    "ý": "y"
}

RELEASE_TEMPLATE = ("[{version}](https://github.com/{org}/"
                    "{repo}/releases/tag/{version})&nbsp;({date})")

ASSET_LINK_GH = ("(https://github.com/{org}/"
                 "{repo}/releases/download/{version}/{file})"
                 "{{: .asset-link{cls}}}")

ASSET_LINK_SERVER = ("(https://edition.esser-skala.at/assets/"
                     "pdf/{repo}/{work}/{file})"
                     "{{: .asset-link{cls}}}")

TABLEROW_TEMPLATE = "|[{id}](#work-{id_slug})|{title}|{genre}|"

INTRO_TEMPLATE = """\
|<span class="label-col">born</span>|{born}|
|<span class="label-col">died</span>|{died}|
|<span class="label-col">links</span>|{links}|
|<span class="label-col">authorities</span>|{authorities}|
|<span class="label-col">archives</span>|{archives}|
{{: class="composer-table"}}

{cv}

{literature}
"""

# pylint: disable=line-too-long
ENCYCLOPEDIAS = {
    "mgg": "[MGG](https://www.mgg-online.com/mgg/stable/{}){{: .asset-link}}",
    "grove": "[Grove](https://doi.org/{}){{: .asset-link}}",
    "wikipedia_de": '[<i class="fab fa-wikipedia-w"></i> (de)](https://de.wikipedia.org/wiki/{}){{: .asset-link}}',
    "wikipedia_cs": '[<i class="fab fa-wikipedia-w"></i> (cs)](https://cs.wikipedia.org/wiki/{}){{: .asset-link}}',
    "wikipedia_en": '[<i class="fab fa-wikipedia-w"></i> (en)](https://en.wikipedia.org/wiki/{}){{: .asset-link}}',
    "oeml": "[ÖML](https://doi.org/{}){{: .asset-link}}",
    "oebl": "[ÖBL](https://doi.org/{}){{: .asset-link}}",
    "db": "[DB](https://www.deutsche-biographie.de/{}.html){{: .asset-link}}",
}

AUTHORITIES = {
    "gnd": "[GND](https://d-nb.info/gnd/{}){{: .asset-link}}",
    "viaf": "[VIAF](https://viaf.org/viaf/{}){{: .asset-link}}"
}

ARCHIVES = {
    "imslp": "[IMSLP](https://imslp.org/wiki/Category:{}){{: .asset-link}}",
    "cpdl": "[CPDL](https://www.cpdl.org/wiki/index.php/{}){{: .asset-link}}"
}

REFERENCE_TEMPLATE = {
    "article": "- {author} ({year}). {title}. {journal} {volume}:{pages}.",
    "book": "- {author} ({year}). {title}. {publisher}, {location}.",
    "website": "- {author} ({year}). {title}."
}

Composer = namedtuple("Composer", "first last suffix", defaults=[""])


def format_metadata(metadata: dict, gh_org_name: str) -> dict:
    """Formats metadata.

    Args:
        metadata (dict): Metadata extracted from metadata.yaml
        gh_org_name (str): name of GitHub organization

    Returns:
        dict: Reformatted metadata.
    """
    # ensure that the composer is complete
    metadata["composer"] = metadata.get("composer", {"last": "(unknown)"})
    metadata["composer"]["first"] = metadata["composer"].get("first", "")
    metadata["composer"]["suffix"] = metadata["composer"].get("suffix", "")

    # add an id
    if "id" not in metadata or metadata["id"] is None:
        for source in metadata["sources"].values():
            if source.get("principal", False):
                metadata["id"] = f"({source['siglum']} {source['shelfmark']})"
                break

    # add a subtitle
    if "subtitle" not in metadata:
        metadata["subtitle"] = metadata["id"]
    else:
        metadata["subtitle"] = f"{metadata['subtitle']}<br/>{metadata['id']}"
    metadata["subtitle"] = metadata["subtitle"].replace(r"\\", " ")

    # convert LaTeX commands to plain text
    metadata["title"] = latex_to_text(metadata["title"])
    metadata["scoring"] = latex_to_text(metadata["scoring"])

    # misc fields
    metadata["license"] = LICENSES[metadata["license"]]
    metadata["id_slug"] = slugify(metadata["id"])

    # releases
    if "releases" in metadata:
        current_release = metadata["releases"][0]

        metadata["latest_release"] = RELEASE_TEMPLATE.format(
            **current_release, org=gh_org_name, repo=metadata["repo"]
        )

        old_releases = [
            RELEASE_TEMPLATE.format(**r, org=gh_org_name, repo=metadata["repo"])
            for r in metadata["releases"][1:]
        ]
        if old_releases:
            metadata["old_releases"] = ", ".join(old_releases)
        else:
            metadata["old_releases"] = "(none)"

    # asset links
    if "assets" in metadata:
        assets = {
            make_part_name(asset_file, ".pdf"):
            ASSET_LINK_GH.format(
                org=gh_org_name,
                repo=metadata["repo"],
                version=current_release["version"],
                file=asset_file,
                cls=".full-score" if asset_file == "full_score.pdf" else ""
            )
            for asset_file in metadata["assets"]
        }

        midi_file = "midi_collection.zip"
        if midi_file in assets:
            metadata["midi"] = assets[midi_file]
            del assets[midi_file]

        metadata["asset_links"] = " ".join([f"[{k}]{v}"
                                            for k, v in assets.items()])

    return metadata


def latex_to_text(s: str) -> str:
    """Converts LaTeX commands to plain text.

    Args:
        s (str): string to format

    Returns:
        str: reformatted string.
    """
    res = re.sub(r"\\newline", " ", s)
    res = re.sub(r"\\\\", " ", res)
    res = re.sub(r"\\flat\s(.)", r"\1♭", res)
    res = re.sub(r"\\sharp\s(.)", r"\1♯", res)
    res = re.sub(r"\\\s", r" ", res)
    return res


def make_part_name(filename: str, extension: str) -> str:
    """Formats a part filename.

    Args:
        filename (str): part file name
        extension (str): part file extension

    Returns:
        str: Reformatted part name.
    """
    if filename == "midi_collection.zip":
        return filename

    name = filename.removesuffix(extension)
    if name.startswith("coro_"):
        name = re.sub("_(.+)$", " (\\1)", name)

    for old, new in PART_REPLACE.items():
        name = re.sub(old, new, name)

    return name


def slugify(s: str) -> str:
    """Formats a string as valid slug.

    Args:
        s (str): string to format

    Returns:
        str: a slug
    """
    slug = s.lower()
    for k, v in SLUG_REPLACE.items():
        slug = slug.replace(k, v)
    return slug


def format_work_entry(work: dict) -> str:
    """Formats the work entry."""

    # title
    title = (
        '### {title}<br/><span class="work-subtitle">{subtitle}</span>\n'
        '{{: #work-{id_slug}}}\n'
    )
    res = [title.format(**work)]

    # table rows
    row = '|<span class="label-col">{}</span>|{}|'

    ## genre
    res.append(row.format("genre", work["genre"]))

    ## festival (optional)
    if "festival" in work:
        res.append(row.format("festival", work["festival"]))

    ## scoring
    res.append(row.format("scoring", work["scoring"]))

    ## full score and parts
    res.append(row.format("scores", work["asset_links"]))

    ## MIDI collection (optional)
    if "midi" in work:
        res.append(
            row.format(
                "MIDI",
                f'[<i class="fas fa-music"></i>]{work["midi"]}'
            )
        )

    ## IMSLP link (optional)
    if "imslp" in work:
        res.append(
            row.format(
                "IMSLP",
                f"[scores and parts](https://imslp.org/wiki/{work['imslp']})"
            )
        )

    ## link to printed edition (optional)
    if "asin" in work:
        res.append(
            row.format(
                "print",
                f"[full score](https://amazon.de/dp/{work['asin']})"
            )
        )

    ## source code
    res.append(
        row.format(
            "source",
            f"[GitHub](https://github.com/edition-esser-skala/{work['repo']})"
        )
    )

    ## license
    res.append(row.format("license", work["license"]))

    # CSS class
    res.append('{: class="work-table"}')

    return "\n".join(res)


def get_work_list(works: list) -> tuple[list[str], list[str]]:
    """Get work table rows and work details.

    Args:
        works (list): works

    Returns:
        tuple[str, str]: table rows and work details
    """
    table_rows = [TABLEROW_TEMPLATE.format(**w) for w in works]
    work_details = [format_work_entry(w) for w in works]
    return table_rows, work_details


def format_reference(ref: dict) -> str:
    """Format a reference.

    Args:
        ref (list): reference details (author, title, ...)

    Returns:
        str: formatted reference
    """

    # format the author(s): "A" or "A, B" or "A, B, and C"
    if isinstance(ref["author"], str):
        authors = ref["author"]
    else:  # list of authors
        if len(ref["author"]) == 2:
            authors = f'{ref["author"][0]} and {ref["author"][1]}'
        if len(ref["author"]) > 2:
            authors = ref["author"][:-1]
            authors = ", ".join(authors) + ", and" + ref["author"][-1]
    ref["author"] = authors

    if "url" in ref:
        ref["title"] = f'[{ref["title"]}]({ref["url"]})'

    return REFERENCE_TEMPLATE[ref["type"]].format(**ref)


def parse_composer_details(file: str) -> str:
    """Parse composer details (dates, links, cv ...) from a YAML file.

    Args:
        file (str): YAML file with composer details

    Returns:
        str: Markdown string to be included in the webpage
    """

    with open(file, encoding="utf8") as f:
        data = strictyaml.load(f.read()).data

    # born date and possibly location
    born = "(unknown)"
    if "born" in data:
        born = data["born"]["date"]
        if "location" in data["born"]:
            born = f'{data["born"]["date"]} ({data["born"]["location"]})'

    # died date and possibly location
    died = "(unknown)"
    if "died" in data:
        died = data["died"]["date"]
        if "location" in data["died"]:
            died = f'{data["died"]["date"]} ({data["died"]["location"]})'

    # encyclopedia links (if available)
    links = "-"
    if "encyclopedia" in data:
        links = " ".join([ENCYCLOPEDIAS[k].format(v)
                          for k, v in data["encyclopedia"].items()])

    # authority files (if available)
    authorities = "-"
    if "authority" in data:
        authorities = " ".join([AUTHORITIES[k].format(v)
                                for k, v in data["authority"].items()])

    # sheet music archives (if available)
    archives = "-"
    if "archive" in data:
        archives = " ".join([ARCHIVES[k].format(v)
                             for k, v in data["archive"].items()])

    # cv (if available)
    cv = data.get("cv", "")

    # literature (if available)
    literature = ""
    if "literature" in data:
        literature = "\n".join(
            ["#### Literature"] +
            [format_reference(r) for r in data["literature"]]
        )

    return INTRO_TEMPLATE.format(
        born=born,
        died=died,
        links=links,
        authorities=authorities,
        archives=archives,
        cv=cv,
        literature=literature
    )


def get_tag_date(tag: Tag) -> str:
    """Return the date of a git tag in ISO 8601 format."""
    return (dateutil.parser.parse(tag.commit.commit.last_modified)
                          .strftime("%Y-%m-%d"))


def get_collection_works(repo: str,
                         gh_org: Organization) -> tuple[list[str], list[str]]:
    """Generates a markdown page for a project."""

    print("  -> Adding collection repository", repo)
    last_tag = gh_org.get_repo(repo).get_tags()[0]

    with tempfile.TemporaryDirectory() as repo_dir:
        Repo.clone_from(
            f"https://github.com/edition-esser-skala/{repo}",
            repo_dir,
            multi_options=["--depth 1", f"--branch {last_tag.name}"]
        )

        try:
            with open(f"{repo_dir}/ignored_works", encoding="utf8") as f:
                ignored_works = [w.strip() for w in f.read().splitlines()
                                 if not w.startswith("#")]
        except FileNotFoundError:
            ignored_works = ["template"]

        work_dirs = os.listdir(f"{repo_dir}/works")

        works = []
        for counter, work_dir in enumerate(work_dirs):
            counter_str = f"({counter + 1}/{len(work_dirs)})"

            if work_dir in ignored_works:
                print(f"     {counter_str} Ignoring {work_dir}")
                continue

            print(f"     {counter_str} Adding {work_dir}")
            with open(f"{repo_dir}/works/{work_dir}/metadata.yaml",
                      encoding="utf-8") as f:
                metadata = strictyaml.load(f.read()).data

            metadata = format_metadata(metadata, gh_org.login)

            assets = {
                make_part_name(score, ".ly"):
                ASSET_LINK_SERVER.format(
                    repo=repo,
                    work=work_dir,
                    file=score.replace(".ly", ".pdf"),
                    cls=".full-score" if score == "full_score.ly" else ""
                )
                for score in os.listdir(f"{repo_dir}/works/{work_dir}/scores")
            }
            metadata["asset_links"] = " ".join([f"[{k}]{v}"
                                                for k, v in assets.items()])

            metadata["midi"] = (
                f"(https://edition.esser-skala.at/assets/pdf/{repo}/"
                "midi_collection.zip){: .asset-link}"
            )

            metadata["latest_release"] = RELEASE_TEMPLATE.format(
                version=last_tag.name,
                org=gh_org.login,
                repo=repo,
                date=get_tag_date(last_tag)
            )
            metadata["repo"] = repo

            works.append(metadata)
        works.sort(key=itemgetter("title"))

    # create table rows and work details
    table_rows = [TABLEROW_TEMPLATE.format(**w) for w in works]
    work_details = [format_work_entry(w) for w in works]

    return table_rows, work_details
