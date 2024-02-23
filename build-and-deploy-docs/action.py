#!/usr/bin/env python3
"""
GitHub Action to build and deploy docs from the README.
"""
import argparse
import json
import os
import re
import subprocess
import functools
import sys

from pathlib import Path

import create_mkdocs_config


TAG_REGEX = re.compile(r"""
    ^v                      # Leading `v` character
    (?P<major>\d+)          # Major version
    \.                      # Dot
    (?P<minor>\d+)          # Minor version
    \.                      # Dot
    (?P<patch>\d+)          # Patch version
    (?:-rc\.(?P<rc>\d+))?  # Optional release candidate version
    """, re.VERBOSE)


def sort_key(version_str: str, strings_high: bool):
    """
    Return a key suitable for sorting version strings.

    Release candidates are weird. Here is a correctly ordered list:

    v1.2.3
    v1.2.4-rc.1
    v1.2.4-rc.2
    v1.2.4

    In order to handle the rule that an absent RC outranks all RCs, an
    absent RC is treated as sys.maxsize.

    If `strings_high` is True, non-version strings (like "development") are
    ranked higher than all version strings.
    """
    try:
        numbers = TAG_REGEX.match(version_str).groups()

        return (
            int(numbers[0]),
            int(numbers[1]),
            int(numbers[2]),
            int(numbers[4]) if numbers[4] else sys.maxsize
        )
    except AttributeError:
        return (
            sys.maxsize if strings_high else -1,
            version_str
        )


strings_low_key = functools.partial(sort_key, strings_high=False)
strings_high_key = functools.partial(sort_key, strings_high=True)


def setup_git():
    """
    Do various required git actions to prepare for generating documentation.
    """
    # Only do these things if we're running in GitHub actions
    if os.environ.get("CI", None) and os.environ.get("GITHUB_ACTIONS", None):
        # see https://github.com/actions/checkout/issues/766
        subprocess.check_call([
            "git",
            "config",
            "--global",
            "--add", "safe.directory", os.environ["GITHUB_WORKSPACE"]
        ])

        subprocess.check_call([
            "git",
            "config",
            "--global",
            "user.name",
            os.environ["GITHUB_ACTOR"],
        ])

        subprocess.check_call([
            "git",
            "config",
            "--global",
            "user.email",
            f"{os.environ['GITHUB_ACTOR']}@users.noreply.github.com"
        ])

    # https://github.com/jimporter/mike/tree/af47b9699aeeeea7f9ecea2631e1c9cfd92e06af#deploying-via-ci
    subprocess.check_call(["git", "fetch", "origin", "gh-pages", "--depth=1"])

    # Fetch all of the tags as well
    subprocess.check_call(["git", "fetch", "--tags"])


def get_version_and_alias():
    "Return a tuple of (version, alias) for the current commit."
    # Get all tags pointing to the current commit
    head_tags = [
        tag.strip() for tag in
        subprocess.check_output(
            ["git", "tag", "--points-at", "HEAD"]
        ).decode("utf-8").strip().splitlines()
        if TAG_REGEX.match(tag.strip())
    ]

    if not head_tags:
        # This is an untagged commit - use "development" as the version
        return ("development", None)

    highest_head_tag = max(head_tags, key=strings_low_key)

    # Get all doc versions
    doc_versions = [
        item["version"] for item in
        json.loads(subprocess.check_output(["mike", "list", "--json"]))
    ]
    highest_doc_tag = max(doc_versions, default="v0.0.0", key=strings_low_key)

    if strings_low_key(highest_head_tag) > strings_low_key(highest_doc_tag):
        return (highest_head_tag, "latest")

    return (highest_head_tag, None)


def run_action(mkdocs_config, readme):
    "Build and deploy the documentation."
    setup_git()

    # Build the mkdocs configuration
    config_file = create_mkdocs_config.build_mkdocs_config(
        pipeline_dir=Path(os.environ["GITHUB_WORKSPACE"]),
        pipeline_repo=os.environ["GITHUB_REPOSITORY"],
        readme=Path(readme),
        mkdocs_config=Path(mkdocs_config)
    )

    mike_args = ["mike", "deploy", "--config-file", config_file]

    version, alias = get_version_and_alias()

    if alias is not None:
        mike_args.extend(["--update-aliases", version, alias])
    else:
        mike_args.append(version)

    # Build the docs as a commit on the gh-pages branch
    subprocess.check_call(mike_args)

    # Redirect from the base site to the latest version. This will be a no-op
    # after the very first deployment, but it will not cause problems
    subprocess.check_call(
        ["mike", "set-default", "--config-file", config_file, "latest"]
    )

    # Push up the changes to the docs
    subprocess.check_call(["git", "push", "origin", "gh-pages"])


if __name__ == "__main__":
    PARSER = argparse.ArgumentParser()
    PARSER.add_argument("mkdocs_config")
    PARSER.add_argument("readme")

    ARGS = PARSER.parse_args()

    run_action(ARGS.mkdocs_config, ARGS.readme)
