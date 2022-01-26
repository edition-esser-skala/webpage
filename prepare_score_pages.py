#!/usr/bin/python

from collections import namedtuple
import dateutil.parser
import git
from github import Github
from operator import attrgetter, itemgetter
import os
from pygments import highlight
from pygments.lexers import LilyPondLexer
from pygments.formatters import HtmlFormatter
import re
from read_metadata import parse_metadata
import tempfile
import yaml

try:
    from pat import TOKEN
except ModuleNotFoundError:
    TOKEN = os.environ["GH_API_TOKEN"]


Composer = namedtuple("Composer", "first last suffix")



# Constants ---------------------------------------------------------------

GITHUB = Github(TOKEN, user_agent = "edition-esser-skala")
GITHUB_ORG_NAME = "edition-esser-skala"
GITHUB_ORG = GITHUB.get_organization(GITHUB_ORG_NAME)

IGNORED_REPOS = ["ees-template", "ees-tools", "haydn-m-proprium-missae",
                 "sacral-lyrics", "webpage"]

IGNORED_WORKS = ["template"]

SLUG_REPLACE = {
    " ": "-", ":": "-", "/": "-", ".": "-",
    ",": "", "(": "", ")": "",
    "á": "a", "ä": "ae", "æ": "ae",
    "í": "i",
    "ö": "oe", "œ": "oe",
    "ß": "ss", "š": "s",
    "ü": "ue", "ů": "u",
    "ý": "y"
}

LICENSES = {
    "cc-by-sa-4.0": "![CC BY-SA 4.0](/assets/images/license_cc-by-sa.svg){:width='120px'}",
    "cc-by-nc-sa-4.0": "![CC BY-NC-SA 4.0](/assets/images/license_cc-by-nc-sa.svg){:width='120px'}"
}

PART_REPLACE = {
    # instrument names
    "bc_realized": "bc (realizzato)",
    "cord": "cor (D)",
    "corf": "cor (F)",
    "coro_DE": "coro (DE)",
    "coro_DK": "coro (DK)",
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



# Templates ---------------------------------------------------------------

PAGE_TEMPLATE = """\
---
title: {title}
permalink: /scores/{slug}/
sidebar:
  nav: scores
---


## Overview

|ID|Title|Genre|
|--|-----|-----|
{rows}
{{: id="toctable" class="overview-table"}}


## Works

{details}
"""

TABLEROW_TEMPLATE = "|[{id}](#work-{id_slug})|{title}|{genre}|"

RELEASE_LINK_TEMPLATE = ("[{version}](https://github.com/" f"{GITHUB_ORG_NAME}"
                         "/{repo}/releases/tag/{version})&nbsp;({date})")

ASSET_LINK_TEMPLATE = ("[{part_name}](https://github.com/" f"{GITHUB_ORG_NAME}"
                       "/{repo}/releases/download/{version}/{file})"
                       "{{: .asset-link{cls}}}")

PDF_LINK_TEMPLATE = ("[{part_name}](https://edition.esser-skala.at/assets/"
                     "pdf/haydn-m-proprium-missae/{work}/{file})"
                     "{{: .asset-link{cls}}}")

WORK_TEMPLATE = """\
### {title}<br/><span class="work-subtitle">{subtitle}</span>
{{: #work-{id_slug}}}

|<span class="label-col">genre</span>|{genre}|
|<span class="label-col">scoring</span>|{scoring}|
|<span class="label-col">latest release</span>|{latest_release}|
|<span class="label-col">GitHub</span>|{assets}|
|<span class="label-col">IMSLP</span>|[scores and parts](https://imslp.org/wiki/{imslp})|
|<span class="label-col">previous releases</span>|{old_releases}|
|<span class="label-col">license</span>|{license}|
{{: class="work-table"}}
"""

PROJECT_PAGE_TEMPLATE = """\
---
title: Michael Haydn's Proprium Missæ
permalink: /projects/proprium-missae/
sidebar:
  nav: scores
---

The *Proprium Missæ* is an emerging collection of all known short liturgical
works by Johann Michael Haydn, in particular those that are freely available
in contemporary manuscripts.

*Current release: {last_tag} containing {n_works} works*


## Overview

|MH|Title|Genre|
|--|-----|-----|
{rows}
{{: id="toctable-mh" class="overview-table"}}


## Works

{details}
"""

PROJECT_TABLEROW_TEMPLATE = "|[{id_int}](#mh-{id_int})|{title}|{genre}|"

PROJECT_WORK_TEMPLATE = """\
### {title}<br/><span class="work-subtitle">{subtitle}</span>
{{: #mh-{id_int}}}

|<span class="label-col">genre</span>|{genre}|
|<span class="label-col">festival</span>|{festival}|
|<span class="label-col">scoring</span>|{scoring}|
|<span class="label-col">scores</span>|{assets}|
|<span class="label-col">license</span>|{license}|
{{: class="work-table"}}
"""

NAVIGATION_TEMPLATE = """\
main:
  - title: Welcome
    url: /
  - title: About
    url: /about
  - title: Scores
    url: /scores
  - title: Contact
    url: /contact

about:
  - title: About
    children:
      - title: Overview
        url: /about
      - title: Sources for digital versions
        url: /about/sources-for-digital-versions
      - title: Editorial guidelines
        url: /about/editorial-guidelines
      - title: Technical documentation
        url: /about/technical-documentation

scores:
- title: ❦ Projects
  children:
    - title: Michael Haydn's Proprium Missæ
      url: /projects/proprium-missae
{}
"""



# General functions -------------------------------------------------------

def slugify(s):
    slug = s.lower()
    for k, v in SLUG_REPLACE.items():
        slug = slug.replace(k, v)
    return slug

def print_rates():
    print(GITHUB.get_rate_limit().core)



# Prepare projects --------------------------------------------------------

def format_metadata(metadata):
    scoring = re.sub(r"\\newline", " ", metadata["scoring"])
    scoring = re.sub(r"\\\\", " ", scoring)
    scoring = re.sub(r"\\flat\s(.)", r"\1♭", scoring)
    scoring = re.sub(r"\\sharp\s(.)", r"\1♯", scoring)
    metadata["scoring"] = scoring

    metadata["subtitle"] = re.sub(r"\\newline\s*",
                                  "<br/>",
                                  metadata["subtitle"]
                           ).replace(r"\\", " ")

    metadata["license"] = LICENSES[metadata["license"]]

    return metadata


def make_part_name(filename, extension):
    name = filename.removesuffix(extension)
    for old, new in PART_REPLACE.items():
        name = re.sub(old, new, name)
    return name


def prepare_projects():
    print("Preparing the Proprium Missae project")

    last_tag = GITHUB_ORG.get_repo("haydn-m-proprium-missae").get_tags()[0].name

    with tempfile.TemporaryDirectory() as repo_dir:
        git.Repo.clone_from(
            "https://github.com/edition-esser-skala/haydn-m-proprium-missae",
            repo_dir,
            multi_options=["--depth 1", f"--branch {last_tag}"]
        )

        work_dirs = [w for w in os.listdir(f"{repo_dir}/works")
                     if w not in IGNORED_WORKS]
        # work_dirs = ["453", "46", "145", "142"]  # for testing

        works = []
        for counter, work_dir in enumerate(work_dirs):
            counter += 1
            print(f"({counter}/{len(work_dirs)}) Analyzing {work_dir}")
            metadata = parse_metadata(
                f"{repo_dir}/works/{work_dir}/metadata.yaml",
                checksum_from=None,
                check_license=False
            )

            metadata = format_metadata(metadata)

            metadata["id_int"] = int(metadata["id"].removeprefix("MH "))

            if "festival" not in metadata:
                metadata["festival"] = "–"

            assets = []
            for score in os.listdir(f"{repo_dir}/works/{work_dir}/scores"):
                assets.append(
                    PDF_LINK_TEMPLATE.format(
                        part_name=make_part_name(score, ".ly"),
                        work=work_dir,
                        file=score.replace(".ly", ".pdf"),
                        cls=".full-score" if score == "full_score.ly" else ""
                    )
                )
            metadata["assets"] = " ".join(assets)

            works.append(metadata)

    works = sorted(works, key=itemgetter("id_int"))
    rows = "\n".join([PROJECT_TABLEROW_TEMPLATE.format(**w) for w in works])
    details = "\n".join([PROJECT_WORK_TEMPLATE.format(**w) for w in works])

    with open("_pages/projects/proprium-missae.md", "w") as f:
        f.write(
            PROJECT_PAGE_TEMPLATE.format(
                last_tag=last_tag,
                n_works=len(works),
                rows=rows,
                details=details
            )
        )



# Get current version of documentation ------------------------------------

def get_markdown_file(file, outfile, title):
    header = (
        "---\n"
        f"title: {title}\n"
        f"permalink: /about/{outfile[:-3]}/\n"
        "toc: true\n"
        "toc_label: Contents\n"
        "toc_sticky: true\n"
        "sidebar:\n"
        "  nav: about\n"
        "---\n"
    )

    print(f"Obtaining {file}")
    doc = (GITHUB_ORG
           .get_repo("ees-tools")
           .get_contents(file)
           .decoded_content
           .decode("utf-8")
           .split("\n", 1)[1])

    doc = header + re.sub("# Contents.+?##", "#", doc, flags=re.DOTALL)

    with open(f"_pages/about/{outfile}", "w") as f:
        f.write(doc)



# Highlight LilyPond code blocks ------------------------------------------

def highlight_lilypond(file):
    print("Highlighting LilyPond code")
    pattern = re.compile(r"```lilypond(.+?)```", re.DOTALL)

    with open(file) as f:
        doc = f.read()

    match = pattern.search(doc)
    while match:
        code = (highlight(match.group(1), LilyPondLexer(), HtmlFormatter())
                .replace("<pre>", '<pre class="highlight">', 1)
                .replace("\\", "\\\\"))
        code = f'<div class="language-lilypond highlighter-rouge">{code}</div>'
        doc = pattern.sub(code, doc, 1)
        match = pattern.search(doc)

    with open(file, "w") as f:
        f.write(doc)



# Collect metadata --------------------------------------------------------

def collect_metadata():
    works = {}
    repos = GITHUB_ORG.get_repos()

    for counter, repo in enumerate(repos):
        # if counter > 3: break  # for testing
        counter_str = f"({counter + 1}/{repos.totalCount})"
        if repo.name in IGNORED_REPOS:
            print(f"{counter_str} Ignoring {repo.name} (blacklisted)")
            continue

        if repo.private:
            print(f"{counter_str} Ignoring {repo.name} (private)")
            continue

        releases = repo.get_releases()
        if releases.totalCount == 0:
            print(f"{counter_str} Ignoring {repo.name} (no releases)")
            continue

        print(f"{counter_str} Analyzing {repo.name}")
        metadata = parse_metadata(
            string=repo
                   .get_contents("metadata.yaml", ref=releases[0].tag_name)
                   .decoded_content,
            checksum_from=None,
            check_license=False
        )

        metadata = format_metadata(metadata)

        if "imslp" not in metadata:
            metadata["imslp"] = ""

        metadata["repo"] = repo.name
        tags = {t.name: t for t in repo.get_tags()}

        metadata["releases"] = [
            dict(
                version=r.tag_name,
                date=dateutil.parser.parse(
                    tags[r.tag_name]
                    .commit
                    .commit
                    .last_modified
                ).strftime("%Y-%m-%d")
            )
            for r in releases
        ]
        metadata["assets"] = [i.name for i in releases[0].get_assets()]

        c = Composer(**metadata["composer"])
        try:
            works[c] += [metadata]
        except KeyError:
            works[c] = [metadata]

    return works



# Generate pages ----------------------------------------------------------

def generate_pages(works):
    navigation = {}

    for composer in sorted(works.keys(),
                           key=attrgetter("last", "suffix", "first")):
        # page header
        if composer.last == "Anonymus":
            title = composer.last
            slug = composer.last
        elif composer.suffix == "":
            title = f"{composer.last}, {composer.first}"
            slug = f"{composer.first}-{composer.last}"
        else:
            title = f"{composer.last} {composer.suffix}, {composer.first}"
            slug = f"{composer.first}-{composer.last}-{composer.suffix}"

        slug = slugify(slug)

        # works
        details = []
        rows = []
        for work in sorted(works[composer], key=itemgetter("title")):
            current_release = work["releases"][0]

            work["latest_release"] = RELEASE_LINK_TEMPLATE.format(
                **current_release, repo=work["repo"]
            )

            if len(work["releases"]) > 1:
                old_releases = []
                for r in work["releases"][1:]:
                    old_releases.append(
                        RELEASE_LINK_TEMPLATE.format(**r, repo=work["repo"])
                    )
                work["old_releases"] = ", ".join(old_releases)
            else:
                work["old_releases"] = "(none)"

            assets = []
            for asset_file in work["assets"]:
                assets.append(
                    ASSET_LINK_TEMPLATE.format(
                        part_name=make_part_name(asset_file, ".pdf"),
                        repo=work["repo"],
                        version=current_release["version"],
                        file=asset_file,
                        cls=".full-score" if asset_file == "full_score.pdf"
                                          else ""
                    )
                )
            work["assets"] = " ".join(assets)

            work["id_slug"] = slugify(work["id"])
            details.append(WORK_TEMPLATE.format(**work))
            rows.append(TABLEROW_TEMPLATE.format(**work))

        # save composer page
        with open(f"_pages/scores/{slug}.md", "w") as f:
            f.write(
                PAGE_TEMPLATE.format(
                    slug=slug,
                    title=title,
                    rows="\n".join(rows),
                    details="\n".join(details)
                )
            )

        # add navigation entry
        last_initial = composer.last[0]
        composer_nav = dict(title=title, url=f"/scores/{slug}")
        try:
            navigation[last_initial] += [composer_nav]
        except KeyError:
            navigation[last_initial] = [composer_nav]


    # save navigation
    navigation = [dict(title=initial, children=children)
                  for initial, children in navigation.items()]

    with open("_data/navigation.yml", "w") as f:
        f.write(NAVIGATION_TEMPLATE.format(yaml.dump(navigation)))



# Execute workflow --------------------------------------------------------

if __name__ == "__main__":
    print_rates()
    prepare_projects()
    get_markdown_file("editorial_guidelines.md",
                      "editorial-guidelines.md",
                      "Editorial guidelines")
    get_markdown_file("README.md",
                      "technical-documentation.md",
                      "Technical documentation",)
    highlight_lilypond("_pages/about/technical-documentation.md")
    works = collect_metadata()
    generate_pages(works)
    print_rates()
