#!/usr/bin/env python3
"Dockerfile entrypoint script."
import argparse
import os
import sys
from pathlib import Path

from configtest import NextflowConfigTest


def run_pipeline_test(pipeline: Path, test_case: Path) -> bool:
    "Run a pipeline test and save the results to a new file."
    testobj = NextflowConfigTest.from_file(pipeline, test_case)

    # Are we running in GitHub Actions?
    is_action = "GITHUB_OUTPUT" in os.environ

    updated_testobj = testobj.recompute_results(overwrite=is_action)

    # Print any differences
    testobj.print_diffs(updated_testobj)

    test_passed = testobj == updated_testobj

    if is_action:
        updated_testobj.mark_for_archive(test_passed, testobj)

    return test_passed


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("pipeline_path", type=Path)
    parser.add_argument("test_path", type=Path)

    args = parser.parse_args()
    if run_pipeline_test(args.pipeline_path.resolve(), args.test_path):
        sys.exit(0)

    # Exit with code 82 to indicate that the tests successfully ran but
    # differences were found
    sys.exit(82)
