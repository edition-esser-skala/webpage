"""Pages for the Cantorey Performance Materials project."""

from operator import itemgetter
import os
import tempfile

import git
from github.Organization import Organization
import strictyaml

from common_functions import (format_metadata, make_part_name)


PAGE_TEMPLATE = """\
---
title: Cantorey Performance Materials
permalink: /projects/cantorey-performance-materials/
sidebar:
  nav: scores
---

This project collects various performance materials used by the
Cantorey der Kirche der Barmherzigen Brüder Schärding.
It mainly comprises organ parts with realized bass figures.

*Current release: {last_tag}*

{composers}
"""

COMPOSER_TEMPLATE = """\
## {composer_long}

{works}
"""

WORK_TEMPLATE = """\
- <span class="work-title">{title}</span>{subtitle}<br/>
  {asset_links}
"""

PDF_LINK_TEMPLATE = ("[{part_name}](https://edition.esser-skala.at/assets/"
                     "pdf/cantorey-performance-materials/{work}/{file})"
                     "{{: .asset-link}}")


def format_composer(c: dict) -> str:
    """Formats a composer name."""
    return c["last"] + ", " + c["first"] + " " + c["suffix"]


def add_project_cantorey(gh_org: Organization) -> None:
    """Generates a markdown page for the project.

    Args:
        gh_org (Organization): GitHub organization that contains the repo
    """
    print("Preparing the Cantorey Performace Materials project")

    last_tag = (gh_org
                .get_repo("cantorey-performance-materials")
                .get_tags()[0]
                .name)

    with tempfile.TemporaryDirectory() as repo_dir:
        git.Repo.clone_from(
            "https://github.com/edition-esser-skala/" +
            "cantorey-performance-materials",
            repo_dir,
            multi_options=["--depth 1", f"--branch {last_tag}"]
        )

        composers = []
        for composer_dir in sorted(os.listdir(f"{repo_dir}/works")):
            works = []
            for work_dir in os.listdir(f"{repo_dir}/works/{composer_dir}"):
                work_dir_root = f"{repo_dir}/works/{composer_dir}/{work_dir}/"
                with open(work_dir_root + "metadata.yaml",
                          encoding="utf-8") as f:
                    metadata = strictyaml.load(f.read()).data

                metadata = format_metadata(metadata, gh_org.login)
                if len(metadata["subtitle"]) > 1:
                    metadata["subtitle"] = "<br/>" + metadata["subtitle"]

                assets = []
                for score in os.listdir(work_dir_root + "scores"):
                    assets.append(
                        PDF_LINK_TEMPLATE.format(
                            part_name=make_part_name(score, ".ly"),
                            work=work_dir,
                            file=score.replace(".ly", ".pdf")
                        )
                    )
                metadata["asset_links"] = " ".join(assets)

                works.append(metadata)

            works.sort(key=itemgetter("title"))
            composers.append(
                COMPOSER_TEMPLATE.format(
                    composer_long=format_composer(works[0]["composer"]),
                    works="\n".join([WORK_TEMPLATE.format(**w) for w in works])
                )
            )

    with open("_pages/projects/cantorey-performance-materials.md",
              "w",
              encoding="utf-8") as f:
        f.write(
            PAGE_TEMPLATE.format(
                last_tag=last_tag,
                composers="\n\n".join(composers)
            )
        )
