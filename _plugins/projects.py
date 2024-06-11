"""Create pages for projects."""

from operator import itemgetter
import os
import tempfile

import dateutil.parser
from git import Repo
from github.Organization import Organization
import strictyaml  # type: ignore

from common_functions import (Composer,
                              format_metadata,
                              make_part_name,
                              parse_composer_details,
                              RELEASE_TEMPLATE,
                              TABLEROW_TEMPLATE,
                              WORK_TEMPLATE)


PAGE_TEMPLATE = """\
---
title: {title}
permalink: {permalink}
sidebar:
  nav: scores
---

<div class="composer-details" markdown="1">
{composer_details}
</div>

{table_caption}

|ID|Title|Genre|
|--|-----|-----|
{table_rows}
{{: id="toctable" class="overview-table"}}

## Works

{work_details}
"""

WORK_COLL_TEMPLATE = """\
### {title}<br/><span class="work-subtitle">{subtitle}</span>
{{: #work-{id_slug}}}

|<span class="label-col">genre</span>|{genre}|
|<span class="label-col">festival</span>|{festival}|
|<span class="label-col">scoring</span>|{scoring}|
|<span class="label-col">latest release</span>|{latest_release}|
|<span class="label-col">scores</span>|{asset_links}|
|<span class="label-col">IMSLP</span>|[scores and parts](https://imslp.org/wiki/{imslp})|{entry_print}
|<span class="label-col">source</span>|[GitHub](https://github.com/edition-esser-skala/{repo})|
|<span class="label-col">license</span>|{license}|
{{: class="work-table"}}
"""

PDF_LINK_TEMPLATE = ("[{part_name}](https://edition.esser-skala.at/assets/"
                     "pdf/{repo}/{work}/{file})"
                     "{{: .asset-link{cls}}}")


def add_project(gh_org: Organization,
                works: dict,
                composer: dict,
                title: str,
                slug: str,
                repo: str,
                table_caption: str) -> None:
    """Generates a markdown page for a project.

    Args:
        gh_org (Organization): GitHub organization that contains the repo
        works (dict): works metadata
        composer (dict): composer
        title (str): page title
        slug (str): page slug
        repo (str): git repository of the project
        table_caption (str): introductory text at the top of the table
    """
    print(f"Preparing page for '{slug}'")

    last_tag = gh_org.get_repo(repo).get_tags()[0]

    # get data from the collection repo
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

        work_dirs = [w for w in os.listdir(f"{repo_dir}/works")
                     if w not in ignored_works]

        works_collection = []
        for counter, work_dir in enumerate(work_dirs):
            counter += 1
            print(f"({counter}/{len(work_dirs)}) Analyzing {work_dir}")
            with open(f"{repo_dir}/works/{work_dir}/metadata.yaml",
                      encoding="utf-8") as f:
                metadata = strictyaml.load(f.read()).data

            metadata = format_metadata(metadata, gh_org.login)

            metadata["festival"] = metadata.get("festival", "–")
            metadata["imslp"] = metadata.get("imslp", "")

            assets = []
            for score in os.listdir(f"{repo_dir}/works/{work_dir}/scores"):
                assets.append(
                    PDF_LINK_TEMPLATE.format(
                        part_name=make_part_name(score, ".ly"),
                        repo=repo,
                        work=work_dir,
                        file=score.replace(".ly", ".pdf"),
                        cls=".full-score" if score == "full_score.ly" else ""
                    )
                )
            assets.append(
                '[<i class="fas fa-music"></i>]'
                "(https://edition.esser-skala.at/assets/"
                f"pdf/{repo}/midi_collection.zip){{: .asset-link}}"
            )

            metadata["asset_links"] = " ".join(assets)
            metadata["latest_release"] = RELEASE_TEMPLATE.format(
                version=last_tag.name,
                org=gh_org.login,
                repo=repo,
                date=dateutil.parser.parse(
                    last_tag
                    .commit
                    .commit
                    .last_modified
                ).strftime("%Y-%m-%d")
            )
            metadata["entry_print"] = ""
            metadata["repo"] = repo

            works_collection.append(metadata)
        works_collection.sort(key=itemgetter("title"))

    # create table rows and work details
    ## … for the collection repo
    table_rows_coll = [TABLEROW_TEMPLATE.format(**w)
                       for w in works_collection]
    work_details_coll = [WORK_COLL_TEMPLATE.format(**w)
                         for w in works_collection]

    ## … for the individual repos
    try:
        works_repos = sorted(works[Composer(**composer)],
                             key=itemgetter("title"))
    except KeyError:
        works_repos = []
    table_rows_repos = [TABLEROW_TEMPLATE.format(**w)
                       for w in works_repos]
    work_details_repos = [WORK_TEMPLATE.format(**w)
                         for w in works_repos]

    ## … and combine them
    table_rows = "\n".join(table_rows_coll + table_rows_repos)
    work_details = "\n".join(sorted(work_details_coll + work_details_repos))

    # load composer details
    composer_details = parse_composer_details(f"_data/composers/{slug}.yml")

    # save the page
    with open(f"_pages/scores/{slug}.md", "w", encoding="utf-8") as f:
        f.write(
            PAGE_TEMPLATE.format(
                title=title,
                permalink=f"/scores/{slug}/",
                composer_details=composer_details,
                table_caption=table_caption,
                table_rows=table_rows,
                work_details=work_details
            )
        )


def add_projects(gh_org: Organization, works: dict, metadata_file: str) -> None:
    """Generates all project pages.

    Args:
        gh_org (Organization): GitHub organization that contains the repo
        works (dict): works metadata
        metadata_file (str): pathon to YAML file with project metadata
    """

    with open(metadata_file, encoding="utf-8") as f:
        projects = strictyaml.load(f.read()).data["projects"]

    for project in projects:
        add_project(gh_org, works, **project)
