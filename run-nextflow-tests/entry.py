#!/usr/bin/env python3
"Quick entrypoint for this tool."
import argparse
import sys
from pathlib import Path

from configtest import NextflowConfigTest


def run_recalibrate_bam_test(pipeline: Path):
    "Run the bundled pipeline-recalibrate-BAM test."
    testobj = NextflowConfigTest.from_file(
        Path(__file__).resolve().parent / "recalibrate-bam.json"
    )

    if testobj.check_results(pipeline):
        print("No changes!")
    else:
        sys.exit(1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("recalibrate_bam_path")

    args = parser.parse_args()
    run_recalibrate_bam_test(Path(args.recalibrate_bam_path))
