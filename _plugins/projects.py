"""Create pages for projects."""

from operator import itemgetter
import os
import tempfile

from git import Repo
from github.Organization import Organization
import strictyaml  # type: ignore

from common_functions import (format_metadata, make_part_name,
                              PAGE_TEMPLATE, TABLEROW_TEMPLATE)


IGNORED_WORKS = ["template"]

WORK_TEMPLATE = """\
### {title}<br/><span class="work-subtitle">{subtitle}</span>
{{: #work-{id_slug}}}

|<span class="label-col">genre</span>|{genre}|
|<span class="label-col">festival</span>|{festival}|
|<span class="label-col">scoring</span>|{scoring}|
|<span class="label-col">scores</span>|{asset_links}|
|<span class="label-col">license</span>|{license}|
{{: class="work-table"}}
"""


def add_project(gh_org: Organization,
                repo: str,
                title: str,
                page_intro: str) -> None:
    """Generates a markdown page for a project.

    Args:
        gh_org (Organization): GitHub organization that contains the repo
        repo (str): git repository of the project
        title (str): page title
        page_intro (str): introductory text at the top of the page
    """
    print(f"Preparing project '{title}'")

    PDF_LINK_TEMPLATE = ("[{part_name}](https://edition.esser-skala.at/assets/"
                         "pdf/{repo}/{work}/{file})"
                         "{{: .asset-link{cls}}}")

    PAGE_INTRO = """
    {page_intro}

    MIDI files of all works are available [in this archive](https://edition.esser-skala.at/assets/pdf/{repo}/midi_collection.zip).

    *Current release: {last_tag} containing {n_works} works*
    """

    last_tag = gh_org.get_repo(repo).get_tags()[0].name

    with tempfile.TemporaryDirectory() as repo_dir:
        Repo.clone_from(
            f"https://github.com/edition-esser-skala/{repo}",
            repo_dir,
            multi_options=["--depth 1", f"--branch {last_tag}"]
        )

        work_dirs = [w for w in os.listdir(f"{repo_dir}/works")
                     if w not in IGNORED_WORKS]

        works = []
        for counter, work_dir in enumerate(work_dirs):
            counter += 1
            print(f"({counter}/{len(work_dirs)}) Analyzing {work_dir}")
            with open(f"{repo_dir}/works/{work_dir}/metadata.yaml",
                      encoding="utf-8") as f:
                metadata = strictyaml.load(f.read()).data

            metadata = format_metadata(metadata, gh_org.login)

            metadata["festival"] = metadata.get("festival", "–")

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
            metadata["asset_links"] = " ".join(assets)

            works.append(metadata)
        works.sort(key=itemgetter("title"))

    table_rows = "\n".join([TABLEROW_TEMPLATE.format(**w) for w in works])
    work_details = "\n".join([WORK_TEMPLATE.format(**w) for w in works])

    with open(f"_pages/projects/{repo}.md", "w", encoding="utf-8") as f:
        f.write(
            PAGE_TEMPLATE.format(
                title=title,
                permalink=f"/projects/{repo}/",
                intro=PAGE_INTRO.format(
                    page_intro=page_intro,
                    repo=repo,
                    last_tag=last_tag,
                    n_works=len(works)
                ),
                table_rows=table_rows,
                work_details=work_details
            )
        )


def add_projects(gh_org: Organization, metadata_file: str) -> None:
    """Generates all project pages..

    Args:
        gh_org (Organization): GitHub organization that contains the repo
        metadata_file (str): pathon to YAML file with project metadata
    """

    with open(metadata_file, encoding="utf-8") as f:
        projects = strictyaml.load(f.read()).data["projects"]

    for project in projects:
        add_project(gh_org, **project)
