#!/usr/bin/env python3
"Quick entrypoint for this tool."
import argparse
import os
import sys
from pathlib import Path

from configtest import NextflowConfigTest


def run_pipeline_test(pipeline: Path, test_case: Path):
    "Run the bundled pipeline-recalibrate-BAM test."
    testobj = NextflowConfigTest.from_file(test_case)

    if testobj.check_results(pipeline, gh_annotations="CI" in os.environ):
        print("No changes!")
    else:
        sys.exit(1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("pipeline_path")
    parser.add_argument("test_path")

    args = parser.parse_args()
    run_pipeline_test(
        Path(args.pipeline_path).resolve(),
        Path(args.test_path)
    )
