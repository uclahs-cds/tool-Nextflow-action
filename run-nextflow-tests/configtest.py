"""
The class representation of a Nextflow configuration test.
"""
import dataclasses
import json
import os
import re
import subprocess
import tempfile
import textwrap

from pathlib import Path
from typing import List, Dict, ClassVar, TypeVar, Type

from utils import parse_config


T = TypeVar('T', bound='NextflowConfigTest')


@dataclasses.dataclass
class NextflowConfigTest:
    "A class representing a single Nextflow configuration test."
    # pylint: disable=too-many-instance-attributes
    SENTINEL: ClassVar = "=========SENTINEL_OUTPUT=========="

    pipeline: Path = dataclasses.field(init=False, compare=False)
    filepath: Path = dataclasses.field(init=False, compare=False)

    nextflow_version: str

    config: List[str]
    params_file: str
    cpus: int
    memory_gb: float

    nf_params: Dict[str, str]
    envvars: Dict[str, str]
    mocks: Dict

    dated_fields: List[str]

    expected_result: Dict

    @classmethod
    def from_file(cls: Type[T], pipeline: Path, filepath: Path) -> T:
        "Load a ConfigTest from a file."
        with filepath.open(mode="rb") as infile:
            data = json.load(infile)

        # Remove these deprecated fields
        data.pop("empty_files", None)
        data.pop("mapped_files", None)

        result = cls(**data)
        result.pipeline = pipeline
        result.filepath = filepath.resolve()
        return result

    def replace_results(self: T, updated_results) -> T:
        "Return another test object with updated results and filepath."
        nf_version = updated_results.pop("betterconfig_nextflow_version")

        regenerated_test = dataclasses.replace(
            self,
            nextflow_version=nf_version,
            expected_result=updated_results
        )

        # These fields are not automatically copied, as they were set with
        # init=False
        regenerated_test.pipeline = self.pipeline
        regenerated_test.filepath = self.filepath

        return regenerated_test

    def to_file(self):
        "Serialize a ConfigTest to a file."
        data = dataclasses.asdict(self)
        data.pop("pipeline")

        with data.pop("filepath").open(mode="w") as outfile:
            json.dump(
                data,
                outfile,
                indent=2,
                sort_keys=False
            )
            # Add a trailing newline to the file
            outfile.write("\n")

    def _run_test(self):
        "Get the resolved config of this pipepline."
        # pylint: disable=too-many-locals
        # Make a temporary directory on the host to hold all of the
        # scaffolding files for this test
        with tempfile.TemporaryDirectory() as tempdir:
            # Make a wrapper config file that will mock out the system calls
            # before including the real config file(s)
            config_file = Path(tempdir, "docker_test.config")
            with config_file.open(mode="w", encoding="utf-8") as outfile:
                outfile.write(textwrap.dedent("""\
                    import nextflow.util.SysHelper
                    import nextflow.util.MemoryUnit
                    import static org.mockito.Mockito.*
                    import org.mockito.MockedStatic

                    """))

                outfile.write(textwrap.dedent(f"""\
                    try (MockedStatic dummyhelper = mockStatic(
                            SysHelper.class,
                            CALLS_REAL_METHODS)) {{
                        dummyhelper
                            .when(SysHelper::getAvailCpus)
                            .thenReturn({self.cpus});
                        dummyhelper
                            .when(SysHelper::getAvailMemory)
                            .thenReturn(MemoryUnit.of("{self.memory_gb}GB"));
                    """))

                for configfile in self.config:
                    outfile.write(
                        f'    includeConfig "{self.pipeline / configfile}"\n'
                    )

                # The config files can print arbitrary text to stdout; include
                # this sentinel value so that we only parse the result of
                # printing the configuration
                outfile.write(f'}}\n\nSystem.out.println("{self.SENTINEL}")\n')

            # Write the Nextflow command-line parameters to a JSON file
            cli_params_file = Path(tempdir, "cli_params.json")
            cli_params_file.write_text(
                json.dumps(self.nf_params),
                encoding="utf-8"
            )

            # Write the mocked methods and results to a JSON file
            mocks_file = Path(tempdir, "test_mocks.json")
            mocks_file.write_text(
                json.dumps(self.mocks),
                encoding="utf-8"
            )

            # Generate a list of environment variable arguments
            envvars = {
                **os.environ,
                **self.envvars,
                "BL_PIPELINE_DIR": str(self.pipeline),
                "BL_CONFIG_FILE": str(config_file),
                "BL_MOCKS_FILE": str(mocks_file),
                "BL_CLI_PARAMS_FILE": str(cli_params_file),
            }

            if self.params_file:
                envvars["BL_PARAMS_FILE"] = \
                    str(self.pipeline / self.params_file)

            try:
                # Run the test and capture the output
                config_output = subprocess.run(
                    [
                        "/usr/local/bin/nextflow-config-test",
                        "/usr/local/bltests/betterconfig.groovy",
                    ],
                    env=envvars,
                    capture_output=True,
                    check=True,
                ).stdout.decode("utf-8").strip()

            except subprocess.CalledProcessError as err:
                print(err.cmd)
                print(err.stdout.decode("utf-8"))
                print(err.stderr.decode("utf-8"))
                raise

        config_text = config_output.rsplit(self.SENTINEL, maxsplit=1)[-1]

        try:
            return parse_config(config_text, self.dated_fields)
        except Exception:
            print(config_output)
            raise

    def print_diffs(self, other: T):
        "Print the diff results to the console."
        diff_process = subprocess.run(
            ["diff", self.filepath, other.filepath],
            capture_output=True,
            check=False
        )
        if diff_process.returncode == 0:
            # No diff!
            print("No changes!")
            return

        raw_diff = diff_process.stdout.decode("utf-8")

        if "CI" not in os.environ:
            # We're running from the console - print the raw diff
            print(raw_diff)
            return

        # Diff lines look like:
        # 176c176
        # < "operand": "4",
        # ---
        # > "operand": "2",

        # For multiline diffs the first line looks like:
        # 572,574c572,574
        context_re = re.compile(
            r"""
            ^(?P<from_start>\d+)        # First line of the left file
            (?:,(?P<from_end>\d+))?     # Last line of the left file
            [acd]                       # Add, change, or delete
            (?P<to_start>\d+)           # First line of the right file
            (?:,(?P<to_end>\d+))        # Last line of the right file
            ?$\n
            (?P<diff>(?:^[-<>].*$\n?)+) # Multiline diff text
            """,
            re.VERBOSE | re.MULTILINE
        )

        # Produce annotations in the GitHub UI
        # https://docs.github.com/en/actions/using-workflows/workflow-commands-for-github-actions#setting-an-error-message

        # The __equals__ method ignores some keys and is blind to any JSON
        # formatting differences. If the two objects are __equal__ (meaning the
        # test will pass) but have text differences, mark those differences as
        # warnings. Otherwise mark them as errors.
        if self == other:
            level = "warning"
        else:
            level = "error"

        for match in context_re.finditer(raw_diff):
            data = match.groupdict()

            error_data = {
                "file": str(self.filepath),
                "line": data["from_start"],
            }
            if data["from_end"] is not None:
                error_data["endLine"] = data["from_end"]

            annotation = ",".join(
                f"{key}={value}" for (key, value) in error_data.items()
            )

            # %0A is a url-encoded linefeed - doing this enables multi-line
            # annotations
            diff = data['diff'].rstrip().replace('\n', '%0A')

            print(f"::{level} {annotation}::{diff}")

    def mark_for_archive(self, test_passed):
        "Emit GitHub workflow commands to archive this file."
        if "GITHUB_OUTPUT" not in os.environ:
            # Nothing to be done here
            print("Unable to mark for archive")
            return

        # Emit details required to archive changed file
        bad_characters = re.compile(r'[":<>|*?\r\n\\/]')

        output_file = Path(os.environ["GITHUB_OUTPUT"])
        with output_file.open(mode="w", encoding="utf-8") as outfile:
            # Each archive file needs a unique key
            key = bad_characters.sub(
                "_",
                str(self.filepath.relative_to(self.pipeline))
            )
            if not test_passed:
                key += " (changed)"

            outfile.write(f"archive_key={key}\n")
            outfile.write(f"archive_path={self.filepath}\n")

    def recompute_results(self: T) -> T:
        "Compare the results."
        result = self._run_test()

        # These are namespaces defined in the common submodules
        boring_keys = {
            'csv_parser',
            'custom_schema_types',
            'methods',
            'retry',
            'schema',
            'bam_parser',
            'json_extractor',
        }

        for key in boring_keys:
            result.pop(key, None)

        regenerated_test = self.replace_results(result)
        # Update the filepath so as not to overwrite
        regenerated_test.filepath = self.filepath.with_name(
            self.filepath.stem + "-out.json"
        )
        regenerated_test.to_file()

        return regenerated_test
