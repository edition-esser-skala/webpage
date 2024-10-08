"""Prepare score and project pages from metadata in GitHub score repos."""

from operator import attrgetter, itemgetter
import os
import re
from typing import Optional, Iterable

from github import Github
from github.Organization import Organization
from github.GithubException import UnknownObjectException
from pygments import highlight
from pygments.lexers.lilypond import LilyPondLexer
from pygments.formatters.html import HtmlFormatter
import strictyaml  # type: ignore

from common_functions import (Composer,
                              format_metadata,
                              get_work_list,
                              get_collection_works,
                              get_tag_date,
                              parse_composer_details,
                              slugify)
from cantorey import add_cantorey

try:
    from pat import TOKEN
except ModuleNotFoundError:
    TOKEN = os.environ["GH_API_TOKEN"]


NAVIGATION_TEMPLATE = """\
main:
  - title: Welcome
    url: /
  - title: About
    url: /about
  - title: News
    url: /news
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
{}
- title: ❦ Bonus
  children:
    - title: Cantorey Performance Materials
      url: /scores/cantorey-performance-materials
"""

PAGE_TEMPLATE = """\
---
title: {title}
permalink: {permalink}
{header_image}
sidebar:
  nav: scores
---

<div class="composer-details" markdown="1">
{composer_details}
</div>

{page_intro}

|ID|Title|Genre|
|--|-----|-----|
{table_rows}
{{: id="toctable" class="overview-table"}}


## Works

{work_details}
"""


def get_markdown_file(gh_org: Organization,
                      repo_file: str,
                      out_file: str,
                      title: str) -> None:
    """Downloads a markdown file that should be used as page.

    Args:
        gh_org (Organization): GitHub organization
        repo_file (str): file name in repository
        out_file (str): file name for Jekyll
        title (str): page title
    """
    header = (
        "---\n"
        f"title: {title}\n"
        f"permalink: /about/{out_file[:-3]}/\n"
        "toc: true\n"
        "toc_label: Contents\n"
        "toc_sticky: true\n"
        "sidebar:\n"
        "  nav: about\n"
        "---\n"
    )

    print(f"Obtaining {repo_file}")
    doc = (gh_org  # type: ignore
           .get_repo("ees-tools")
           .get_contents(repo_file)
           .decoded_content
           .decode("utf-8")
           .split("\n", 1)[1])

    doc = header + re.sub("# Contents.+?##", "#", doc, flags=re.DOTALL)

    with open(f"_pages/about/{out_file}", "w", encoding="utf-8") as f:
        f.write(doc)


def highlight_lilypond_snippets(file: str) -> None:
    """Add syntax highlighting to LiyPond code snippets in markdown file.

    Args:
        file (str): file with LilyPond code
    """
    print("Highlighting LilyPond code")
    pattern = re.compile(r"```lilypond(.+?)```", re.DOTALL)

    with open(file, encoding="utf-8") as f:
        doc = f.read()

    match = pattern.search(doc)
    while match:
        code = (highlight(match.group(1), LilyPondLexer(), HtmlFormatter())
                .replace("<pre>", '<pre class="highlight">', 1)
                .replace("\\", "\\\\"))
        code = f'<div class="language-lilypond highlighter-rouge">{code}</div>'
        doc = pattern.sub(code, doc, 1)
        match = pattern.search(doc)

    with open(file, "w", encoding="utf-8") as f:
        f.write(doc)


def collect_metadata(gh_org: Organization,
                     ignored_repos: Optional[Iterable[str]]=None) -> dict:
    """Collects work metadata from YAML files in GitHub repos.

    Args:
        gh_org (Organization): GitHub organization
        ignored_repos (Optional[Iterable[str]]): list of ignored repositories

    Returns:
        dict: work metadata
    """

    repos = gh_org.get_repos()
    if ignored_repos is None:
        ignored_repos = []

    works: dict[Composer, list] = {}

    for counter, repo in enumerate(repos):
        counter_str = f"({counter + 1}/{repos.totalCount})"

        if repo.name in ignored_repos:
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
        try:
            metadata = strictyaml.load(
                repo  # type: ignore
                .get_contents("metadata.yaml", ref=releases[0].tag_name)
                .decoded_content
                .decode("utf-8")
            ).data
        except UnknownObjectException:
            print(f"UnknownObjectException for {repo.name}")
            continue

        metadata["repo"] = repo.name
        tags = {t.name: t for t in repo.get_tags()}

        metadata["releases"] = [
            {"version": r.tag_name,
             "date": get_tag_date(tags[r.tag_name])}  # type: ignore
            for r in releases
        ]

        metadata["assets"] = [i.name for i in releases[0].get_assets()]

        try:
            print_data = strictyaml.load(
                repo  # type: ignore
                .get_contents("print/printer.yaml")
                .decoded_content
                .decode("utf-8")
            ).data
            metadata["asin"] = print_data["asin"]
        except UnknownObjectException:
            pass

        metadata = format_metadata(metadata, gh_org.login)

        c = Composer(**metadata["composer"])
        try:
            works[c] += [metadata]
        except KeyError:
            works[c] = [metadata]

    return works


def generate_score_pages(works: dict,
                         gh_org: Organization,
                         page_settings_file: str) -> None:
    """Generates one markdown file for each composer.

    Args:
        works (dict): works metadata
        gh_org (github.Organization): GitHub organization
        page_settings_file (str): YAML file with optional page settings
    """
    with open(page_settings_file, encoding="utf-8") as f:
        page_settings = strictyaml.load(f.read()).data["page_settings"]

    navigation: dict[str, list] = {}

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
        permalink = f"/scores/{slug}/"
        print("Generating page for", slug)

        # header image
        try:
            header_image = ("header:\n  image: /assets/images/"
                            + page_settings[slug]["header_image"])
        except KeyError:
            header_image = ""

        # composer details
        composer_details = ""
        details_file = f"_data/composers/{slug}.yml"
        if os.path.exists(details_file):
            print("  -> Adding composer details")
            composer_details = parse_composer_details(details_file)

        # page intro
        try:
            page_intro = page_settings[slug]["page_intro"]
        except KeyError:
            page_intro = ""

        # works from individual repos
        table_rows_repos, work_details_repos = get_work_list(
            sorted(works[composer], key=itemgetter("title")),
        )

        # works from collection repo
        try:
            coll_repo = page_settings[slug]["collection_repo"]
            table_rows_coll, work_details_coll = get_collection_works(
                coll_repo, gh_org
            )
        except KeyError:
            table_rows_coll = []
            work_details_coll = []

        # combine table rows and work details
        table_rows = "\n".join(sorted(table_rows_repos + table_rows_coll))
        work_details = "\n".join(sorted(work_details_repos + work_details_coll))

        # save composer page
        with open(f"_pages/scores/{slug}.md", "w", encoding="utf-8") as f:
            f.write(
                PAGE_TEMPLATE.format(
                    title=title,
                    permalink=permalink,
                    header_image=header_image,
                    composer_details=composer_details,
                    page_intro=page_intro,
                    table_rows=table_rows,
                    work_details=work_details
                )
            )

        # add navigation entry
        last_initial = composer.last[0]
        composer_nav = {"title": title, "url": permalink}
        try:
            navigation[last_initial] += [composer_nav]
        except KeyError:
            navigation[last_initial] = [composer_nav]


    # save navigation
    nav_dict = [{"title": initial, "children": children}
                for initial, children in navigation.items()]

    with open("_data/navigation.yml", "w", encoding="utf-8") as f:
        f.write(NAVIGATION_TEMPLATE.format(strictyaml.as_document(nav_dict)
                                                     .as_yaml()))


def main() -> None:
    """Main workflow."""
    ignored_repos = [
        ".github",
        "ees-template",
        "ees-tools",
        "eybler-sacred-music",
        "haydn-m-proprium-missae",
        "imslp-lists",
        "misc-analyses",
        "sacral-lyrics",
        "tuma-catalogue-of-works",
        "tuma-collected-works",
        "webpage",
        "werner-catalogue-of-works",
        "werner-collected-works"
    ]

    gh = Github(TOKEN)
    gh_org = gh.get_organization("edition-esser-skala")

    print(gh.get_rate_limit().core)
    get_markdown_file(gh_org,
                      "documents/editorial_guidelines.md",
                      "editorial-guidelines.md",
                      "Editorial guidelines")
    get_markdown_file(gh_org,
                      "README.md",
                      "technical-documentation.md",
                      "Technical documentation",)
    highlight_lilypond_snippets("_pages/about/technical-documentation.md")
    all_works = collect_metadata(gh_org, ignored_repos)
    all_works[Composer("Gregor Joseph", "Werner")] = []
    all_works[Composer("František Ignác Antonín", "Tůma")] = []
    generate_score_pages(all_works, gh_org, "_data/page_settings.yml")
    add_cantorey(gh_org)
    print(gh.get_rate_limit().core)


if __name__ == "__main__":
    main()
