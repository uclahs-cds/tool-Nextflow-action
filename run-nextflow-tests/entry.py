#!/usr/bin/env python3
"Quick entrypoint for this tool."
import argparse
import sys
from pathlib import Path

from configtest import NextflowConfigTest


def run_pipeline_test(pipeline: Path, test_case: Path) -> bool:
    "Run the bundled pipeline-recalibrate-BAM test."
    testobj = NextflowConfigTest.from_file(pipeline, test_case)
    updated_testobj = testobj.recompute_results()

    # Print any differences
    testobj.print_diffs(updated_testobj)
    updated_testobj.mark_for_archive()

    return testobj == updated_testobj


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("pipeline_path", type=Path)
    parser.add_argument("test_path", type=Path)

    args = parser.parse_args()
    if run_pipeline_test(args.pipeline_path.resolve(), args.test_path):
        sys.exit(0)

    sys.exit(1)
