#!/usr/bin/python

# import datetime
import os
# import pandas as pd
import yaml

from django.utils.text import slugify


ROOT_DIR = "/home/wolfgang/Dokumente/Noten"
IGNORED_COMPOSER_DIRS = ["Misc", "TODO"]

HEADER_TEMPLATE = """
---
title: {composer}
permalink: /scores/{permalink}
sidebar:
  nav: scores
---
"""

slug_replace = {
    " ": "-",
    "ä": "ae",
    "ö": "oe",
    "ü": "ue",
    "ů": "u",
    "ý": "y"
}


# read metadata
metadata = []
for composer_dir in os.listdir(ROOT_DIR):
    full_composer_dir = os.path.join(ROOT_DIR, composer_dir)
    if (not os.path.isdir(full_composer_dir) or
        composer_dir in IGNORED_COMPOSER_DIRS):
        continue
    for work_dir in os.listdir(full_composer_dir):
        full_work_dir = os.path.join(full_composer_dir, work_dir)
        if not os.path.isdir(full_work_dir):
            continue
        try:
            with open (os.path.join(full_work_dir, "metadata.yaml")) as f:
                work_data = yaml.load(f, Loader=yaml.SafeLoader)
                work_data["folder"] = full_work_dir
                metadata.append(work_data)
        except FileNotFoundError:
            print("Warning: No metadata found in", full_work_dir)
            pass


# normalize and save as CSV
# for i in range(len(metadata)):
#     try:
#         metadata[i]["sources"] = {str(k): v for k, v in metadata[i]["sources"].items()}
#     except (AttributeError, KeyError):
#         pass

works = {}

for work in metadata:
    if work.get("github") is None:
        continue
    try:
        works[work["composer"]].append(work)
    except KeyError:
        works[work["composer"]] = [work]

for composer in sorted(works.keys()):
    permalink = composer.split(", ")[0].lower()
    for k, v in slug_replace.items():
        if k in permalink:
            permalink = permalink.replace(k, v)
    contents = [HEADER_TEMPLATE.format(permalink=permalink,
                                       composer=composer)]
    for w in sorted(works[composer],
                    key=lambda s: s["github"]):
        print(w["github"])
    # print("".join(contents))
    # print(permalink)



# from ghapi.all import GhApi
#
# api = GhApi()
# x = api.repos.get_release(
#     owner="skafdasschaf",
#     repo="albrechtsberger-litaniae-SchAl-J.9",
#     release_id="latest"
# )
# print(type(x))
