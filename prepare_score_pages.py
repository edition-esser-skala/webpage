#!/usr/bin/python

from collections import namedtuple
from github import Github
from operator import attrgetter, itemgetter
from pat import TOKEN
from pygments import highlight
from pygments.lexers import LilyPondLexer
from pygments.formatters import HtmlFormatter
import re
from read_metadata import parse_metadata
import yaml


Composer = namedtuple("Composer", "first last suffix")



# Constants ---------------------------------------------------------------

GITHUB_ORG = "edition-esser-skala"

IGNORED_REPOS = ["ees-tools", "ees-template", "sacral-lyrics", "webpage"]

SLUG_REPLACE = {
    " ": "-", "á": "a", "ä": "ae", "í": "i", "ö": "oe", "ß": "ss", "š": "s",
    "ü": "ue", "ů": "u", "ý": "y", ",": ""
}



# Templates ---------------------------------------------------------------

HEADER_TEMPLATE = """\
---
title: {title}
permalink: /scores/{permalink}
sidebar:
  nav: scores
---
"""

RELEASE_LINK_TEMPLATE = ("[{version}](https://github.com/" f"{GITHUB_ORG}"
                         "/{repo}/releases/tag/{version})&nbsp;({date})")

ASSET_LINK_TEMPLATE = f"[{{part_name}}](https://github.com/{GITHUB_ORG}/{{repo}}/releases/download/{{version}}/{{file}}){{{{: .asset-link}}}}"

WORK_TEMPLATE = """\
### {title} <span class="work-id">{id}</span>

|<span class="label-col">genre</span>|{genre}|
|<span class="label-col">scoring</span>|{scoring}|
|<span class="label-col">latest release</span>|{latest_release}|
|<span class="label-col">GitHub</span>|{assets}|
|<span class="label-col">IMSLP</span>|[scores and parts](https://imslp.org/wiki/{imslp})|
|<span class="label-col">previous releases</span>|{old_releases}|
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

scores:
{}
"""


# Get current version of documentation ------------------------------------

def get_markdown_file(file, outfile, title):
    header = (
        "---\n"
        f"title: {title}\n"
        f"permalink: /about/{outfile[:-3]}\n"
        "toc: true\n"
        "toc_label: Contents\n"
        "toc_sticky: true\n"
        "---\n"
    )

    print(f"Obtaining {file}")
    doc = (Github(TOKEN)
           .get_organization(GITHUB_ORG)
           .get_repo("ees-tools")
           .get_contents(path=file)
           .decoded_content
           .decode("utf-8")
           .split("\n", 1)[1])

    doc = header + re.sub("# Contents.+?##", "#", doc, flags=re.DOTALL)

    with open(f"_pages/about/{outfile}", "w") as f:
        f.write(doc)


get_markdown_file("editorial_guidelines.md",
                  "editorial-guidelines.md",
                  "Editorial guidelines")
get_markdown_file("README.md",
                  "technical-documentation.md",
                  "Technical documentation",)



# Highlight LilyPond code blocks ------------------------------------------

def highlight_lilypond(file):
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

print("Highlighting LilyPond code")
highlight_lilypond("_pages/about/technical-documentation.md")



# Collect metadata --------------------------------------------------------

works = {}
repos = Github(TOKEN).get_organization(GITHUB_ORG).get_repos()

for rid, repo in enumerate(repos):
    rid += 1
    if repo.name in IGNORED_REPOS:
        print(f"({rid}/{repos.totalCount}) Ignoring {repo.name} (blacklisted)")
        continue

    releases = repo.get_releases()
    if releases.totalCount == 0:
        print(f"({rid}/{repos.totalCount}) Ignoring {repo.name} (no releases)")
        continue

    print(f"({rid}/{repos.totalCount}) Analyzing {repo.name}")
    metadata = parse_metadata(
        string=repo
               .get_contents(path="metadata.yaml", ref=releases[0].tag_name)
               .decoded_content,
        checksum_from=None
    )

    metadata["scoring"] = re.sub(r"\\newline", " ", metadata["scoring"])
    metadata["scoring"] = re.sub(r"\\flat\s(.)", r"\1♭", metadata["scoring"])
    metadata["scoring"] = re.sub(r"\\sharp\s(.)", r"\1♯", metadata["scoring"])

    metadata["repo"] = repo.name
    metadata["releases"] = [dict(version=r.tag_name,
                                 date=r.published_at.strftime("%Y-%m-%d"))
                            for r in releases]
    metadata["assets"] = [i.name for i in releases[0].get_assets()]

    c = Composer(**metadata["composer"])
    try:
        works[c] += [metadata]
    except KeyError:
        works[c] = [metadata]



# Generate pages ----------------------------------------------------------

def make_part_name(filename):
    name = filename.removesuffix(".pdf")
    if name == "full_score":
        name = "full score"
    if name == "org_realized":
        name = "org (realizzato)"
    return name


navigation = {}

for composer in sorted(works.keys(), key=attrgetter("last", "suffix", "first")):
    # page header
    if composer.suffix == "":
        title = f"{composer.last}, {composer.first}"
        permalink = f"{composer.first}-{composer.last}"
    else:
        title = f"{composer.last} {composer.suffix}, {composer.first}"
        permalink = f"{composer.first}-{composer.last}-{composer.suffix}"

    permalink = permalink.lower()
    for k, v in SLUG_REPLACE.items():
        permalink = permalink.replace(k, v)

    page_contents = [HEADER_TEMPLATE.format(permalink=permalink, title=title)]

    # works
    for work in sorted(works[composer], key=itemgetter("title")):
        current_release = work["releases"][0]

        work["latest_release"] = RELEASE_LINK_TEMPLATE.format(
            **current_release, repo=work["repo"]
        )

        if len(work["releases"]) > 1:
            old_releases = []
            for old_release in work["releases"][1:]:
                old_releases.append(
                    RELEASE_LINK_TEMPLATE.format(**old_release, repo=work["repo"])
                )
            work["old_releases"] = ", ".join(old_releases)
        else:
            work["old_releases"] = "(none)"

        assets = []
        for asset_file in work["assets"]:
            assets.append(
                ASSET_LINK_TEMPLATE.format(
                    part_name=make_part_name(asset_file),
                    repo=work["repo"],
                    version=current_release["version"],
                    file=asset_file
                )
            )
        work["assets"] = "".join(assets)

        page_contents.append(WORK_TEMPLATE.format(**work))

    # save composer page
    with open(f"_pages/scores/{permalink}.md", "w") as f:
        f.write("\n".join(page_contents))

    # add navigation entry
    last_initial = composer.last[0]
    composer_nav = dict(title=title, url=f"/scores/{permalink}")
    try:
        navigation[last_initial] += [composer_nav]
    except KeyError:
        navigation[last_initial] = [composer_nav]


# save navigation
navigation = [dict(title=initial, children=children)
              for initial, children in navigation.items()]

with open("_data/navigation.yml", "w") as f:
    f.write(NAVIGATION_TEMPLATE.format(yaml.dump(navigation)))
