"""Pages for the Proprium Missae project."""

import os
import tempfile

import git
from github.Organization import Organization

from common_functions import (format_metadata, make_part_name,
                              PAGE_TEMPLATE, TABLEROW_TEMPLATE)
from read_metadata import parse_metadata


IGNORED_WORKS = ["template"]

PAGE_INTRO = """
The *Proprium Missæ* is an emerging collection of all known short liturgical
works by Johann Michael Haydn, in particular those that are freely available
in contemporary manuscripts.

*Current release: {last_tag} containing {n_works} works*
"""

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

PDF_LINK_TEMPLATE = ("[{part_name}](https://edition.esser-skala.at/assets/"
                     "pdf/haydn-m-proprium-missae/{work}/{file})"
                     "{{: .asset-link{cls}}}")


def add_project_haydn(gh_org: Organization) -> None:
    """Generates a markdown page for the project.

    Args:
        gh_org (Organization): GitHub organization that contains the repo
    """
    print("Preparing the Proprium Missae project")

    last_tag = gh_org.get_repo("haydn-m-proprium-missae").get_tags()[0].name

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

            metadata = format_metadata(metadata, gh_org.login)

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
            metadata["asset_links"] = " ".join(assets)

            works.append(metadata)

    table_rows = "\n".join([TABLEROW_TEMPLATE.format(**w) for w in works])
    work_details = "\n".join([WORK_TEMPLATE.format(**w) for w in works])

    with open("_pages/projects/proprium-missae.md", "w", encoding="utf-8") as f:
        f.write(
            PAGE_TEMPLATE.format(
                title="Michael Haydn's Proprium Missæ",
                permalink="/projects/proprium-missae/",
                intro=PAGE_INTRO.format(last_tag=last_tag, n_works=len(works)),
                table_rows=table_rows,
                work_details=work_details
            )
        )
