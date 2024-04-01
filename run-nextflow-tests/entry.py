#!/usr/bin/env python3
"Dockerfile entrypoint script."
import argparse
import os
import sys
from pathlib import Path

from configtest import NextflowConfigTest


def run_pipeline_test(pipeline: Path, test_case: Path) -> bool:
    "Run a pipeline test and save the results to a new file."
    # Parse a test case object from the input file
    testobj = NextflowConfigTest.from_file(pipeline, test_case)

    # Are we running in GitHub Actions? If so, overwrite the original file and
    # write out additional files to be included as workflow artifacts.
    is_action = "GITHUB_OUTPUT" in os.environ

    # Run Nextflow, capturing the results in a new test case object
    updated_testobj = testobj.recompute_results(overwrite=is_action)

    # Generate test outputs (console text or modified files)
    updated_testobj.generate_outputs(prior=testobj, print_only=not is_action)

    # Return True if the test outputs were unchanged
    return testobj == updated_testobj


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
