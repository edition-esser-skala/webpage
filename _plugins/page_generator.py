"""Prepare score and project pages from metadata in GitHub score repos."""

from operator import attrgetter, itemgetter
import os
import re
from typing import Optional, Iterable

import dateutil.parser
from github import Github
from github.Organization import Organization
from pygments import highlight
from pygments.lexers.lilypond import LilyPondLexer
from pygments.formatters.html import HtmlFormatter
import strictyaml

from common_functions import (Composer, format_metadata, get_work_list,
                              parse_composer_details, slugify, PAGE_TEMPLATE)
from project_haydn import add_project_haydn
from project_caldara import add_project_caldara
from project_cantorey import add_project_cantorey
from project_werner import add_project_werner

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
- title: ❦ Projects
  children:
    - title: Michael Haydn's Proprium Missæ
      url: /projects/haydn-m-proprium-missae
    - title: Caldara@Dresden
      url: /projects/caldara-at-dresden
    - title: Cantorey Performance Materials
      url: /projects/cantorey-performance-materials
    - title: Werner's Proprium Missæ
      url: /projects/werner-proprium-missae
{}
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
        # if counter > 1: break  # for testing
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
        metadata = strictyaml.load(
            repo  # type: ignore
            .get_contents("metadata.yaml", ref=releases[0].tag_name)
            .decoded_content
            .decode("utf-8")
        ).data

        metadata["repo"] = repo.name
        tags = {t.name: t for t in repo.get_tags()}

        metadata["releases"] = [
            dict(
                version=r.tag_name,
                date=dateutil.parser.parse(
                    tags[r.tag_name]  # type: ignore
                    .commit
                    .commit
                    .last_modified
                ).strftime("%Y-%m-%d")
            )
            for r in releases
        ]

        metadata["assets"] = [i.name for i in releases[0].get_assets()]

        metadata = format_metadata(metadata, gh_org.login)

        c = Composer(**metadata["composer"])
        try:
            works[c] += [metadata]
        except KeyError:
            works[c] = [metadata]

    return works


def generate_score_pages(works: dict) -> None:
    """Generates one markdown file for each composer.

    Args:
        works (dict): works metadata
    """
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

        # composer details
        intro = ""
        details_file = f"_data/composers/{slug}.yml"
        if os.path.exists(details_file):
            print("Adding composer details for", slug)
            intro = parse_composer_details(details_file)

        # works
        table_rows, work_details = get_work_list(
            sorted(works[composer], key=itemgetter("title")),
        )

        # save composer page
        with open(f"_pages/scores/{slug}.md", "w", encoding="utf-8") as f:
            f.write(
                PAGE_TEMPLATE.format(
                    title=title,
                    permalink=permalink,
                    intro=intro,
                    table_rows=table_rows,
                    work_details=work_details
                )
            )

        # add navigation entry
        last_initial = composer.last[0]
        composer_nav = dict(title=title, url=permalink)
        try:
            navigation[last_initial] += [composer_nav]
        except KeyError:
            navigation[last_initial] = [composer_nav]


    # save navigation
    nav_dict = [dict(title=initial, children=children)
                for initial, children in navigation.items()]

    with open("_data/navigation.yml", "w", encoding="utf-8") as f:
        f.write(NAVIGATION_TEMPLATE.format(strictyaml.as_document(nav_dict)
                                                     .as_yaml()))


def main() -> None:
    """Main workflow.
    """
    ignored_repos = ["ees-template", "ees-tools", "haydn-m-proprium-missae",
                     "sacral-lyrics", "webpage", "misc-analyses"]

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
    generate_score_pages(all_works)
    add_project_haydn(gh_org)
    add_project_caldara(all_works)
    add_project_cantorey(gh_org)
    add_project_werner(gh_org)
    print(gh.get_rate_limit().core)


if __name__ == "__main__":
    main()
