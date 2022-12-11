"""Common functions."""

from collections import namedtuple
import re

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

SLUG_REPLACE = {
    " ": "-",
    ":": "-",
    "/": "-",
    ".": "-",
    ",": "",
    "(": "",
    ")": "",
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

ASSET_TEMPLATE = ("[{part_name}](https://github.com/{org}/"
                  "{repo}/releases/download/{version}/{file})"
                  "{{: .asset-link{cls}}}")

WORK_TEMPLATE = """\
### {title}<br/><span class="work-subtitle">{subtitle}</span>
{{: #work-{id_slug}}}

|<span class="label-col">genre</span>|{genre}|
|<span class="label-col">scoring</span>|{scoring}|
|<span class="label-col">latest release</span>|{latest_release}|
|<span class="label-col">GitHub</span>|{asset_links}|
|<span class="label-col">IMSLP</span>|[scores and parts](https://imslp.org/wiki/{imslp})|
|<span class="label-col">previous releases</span>|{old_releases}|
|<span class="label-col">license</span>|{license}|
{{: class="work-table"}}
"""

TABLEROW_TEMPLATE = "|[{id}](#work-{id_slug})|{title}|{genre}|"

PAGE_TEMPLATE = """\
---
title: {title}
permalink: {permalink}
sidebar:
  nav: scores
---

{intro}

## Overview

|ID|Title|Genre|
|--|-----|-----|
{table_rows}
{{: id="toctable" class="overview-table"}}


## Works

{work_details}
"""

Composer = namedtuple("Composer", "first last suffix")


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
    metadata["imslp"] = metadata.get("imslp", "")

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
        assets = [
            ASSET_TEMPLATE.format(
                part_name=make_part_name(asset_file, ".pdf"),
                org=gh_org_name,
                repo=metadata["repo"],
                version=current_release["version"],
                file=asset_file,
                cls=".full-score" if asset_file == "full_score.pdf" else ""
            )
            for asset_file in metadata["assets"]
        ]
        metadata["asset_links"] = " ".join(assets)

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
    name = filename.removesuffix(extension)
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


def get_work_list(works: list) -> tuple[str, str]:
    """Get work table rows and work details.

    Args:
        works (list): works

    Returns:
        tuple[str, str]: table rows and work details
    """
    table_rows = "\n".join([TABLEROW_TEMPLATE.format(**w) for w in works])
    work_details = "\n".join([WORK_TEMPLATE.format(**w) for w in works])
    return table_rows, work_details
