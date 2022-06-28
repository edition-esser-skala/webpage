"""Pages for the Caldara@Dresden project."""

from common_functions import Composer, get_work_list, PAGE_TEMPLATE

REPOS = ["caldara-missa-providentiae",
         "caldara-missa-reformata",
         "caldara-missa-quia-mihi-et-tibi",
         "caldara-missa-D-Dl-Mus-2170-D-11",
         "caldara-missa-divi-xaverii-D-Dl-Mus-2170-D-9",
         "caldara-missa-mundata-est-D-Dl-Mus-2170-D-12",
         "caldara-missa-intende-D-Dl-Mus-2170-D-10",
         "caldara-missa-vix-orimur-morimur-D-Dl-Mus-2170-D-13",
         "caldara-missa-matris-dolorosae-D-Dl-Mus-2170-D-4"]

PAGE_INTRO="""
Nine of Caldara's masses and several short liturgical works are extant in the SLUB Dresden. These works are highly interesting, since they contain annotations and even whole movements by Jan Dismas Zelenka. The *Caldara@Dresden* project will provide practical editions of these works.
"""

def add_project_caldara(works: dict) -> None:
    """Generates a markdown page for the project.

    Args:
        works (dict): works metadata
    """
    print("Preparing the Caldara@Dresden project")

    selected_works = [
        w for w in works[Composer(last="Caldara", first="Antonio", suffix="")]
        if w["repo"] in REPOS
    ]

    table_rows, work_details = get_work_list(selected_works)

    with open("_pages/projects/caldara-at-dresden.md", "w",
              encoding="utf-8") as f:
        f.write(
            PAGE_TEMPLATE.format(
                title="Caldara@Dresden",
                permalink="/projects/caldara-at-dresden/",
                intro=PAGE_INTRO,
                table_rows=table_rows,
                work_details=work_details
            )
        )
