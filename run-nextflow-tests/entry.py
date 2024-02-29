#!/usr/bin/env python3
"Quick entrypoint for this tool."
import argparse
import os
import re
import sys
from pathlib import Path

from configtest import NextflowConfigTest


def run_pipeline_test(pipeline: Path, test_case: Path) -> bool:
    "Run the bundled pipeline-recalibrate-BAM test."
    testobj = NextflowConfigTest.from_file(pipeline, test_case)
    updated_testobj = testobj.recompute_results()

    if testobj == updated_testobj:
        print("No changes!")
        return True

    # Print the differences
    testobj.print_diffs(updated_testobj)
    updated_testobj.mark_for_archive()

    return False

"""

    if testobj.check_results(pipeline, gh_annotations=gh_annotations):
        print("No changes!")
        return True

    # Emit details required to archive changed file
    bad_characters = re.compile(r'[":<>|*?\r\n\\/]')

    try:
        with Path(os.environ["GITHUB_OUTPUT"]).open(
                mode="w", encoding="utf-8") as outfile:
            # Each archive file needs a unique key
            key = bad_characters.sub(
                "_",
                str(testobj.outpath.relative_to(pipeline))
            )
            outfile.write(f"archive_path={testobj.outpath}\n")
            outfile.write(f"archive_key={key}\n")
    except (TypeError, KeyError):
        print("Could not echo file")
        pass

    return False
    """


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("pipeline_path", type=Path)
    parser.add_argument("test_path", type=Path)

    args = parser.parse_args()
    if run_pipeline_test(args.pipeline_path.resolve(), args.test_path):
        sys.exit(0)

    sys.exit(1)


"""

        if self.expected_result == result:
            return True

        if not self.outpath:
            return False

        print("Saving updated file to", self.outpath)
        dataclasses.replace(self, expected_result=result).to_file(self.outpath)

        self.print_diffs(gh_annotations)

        return False
        """
