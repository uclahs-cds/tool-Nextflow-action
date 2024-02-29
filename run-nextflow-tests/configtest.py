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
from typing import List, Dict

from utils import parse_config


@dataclasses.dataclass
class ConfigTest:
    "A class representing a single Nextflow configuration test."
    # pylint: disable=too-many-instance-attributes
    config: List[str]
    params_file: str
    cpus: int
    memory_gb: float

    empty_files: List[str]
    mapped_files: Dict[str, str]
    nf_params: Dict[str, str]
    envvars: Dict[str, str]
    mocks: Dict

    dated_fields: List[str]

    expected_result: Dict

    @classmethod
    def from_file(cls, filepath: Path):
        "Load a ConfigTest from a file."
        with filepath.open(mode="rb") as infile:
            data = json.load(infile)

        return cls(**data)

    def check_results(self, pipeline_dir: Path, gh_annotations: bool) -> bool:
        "Run the test against the given pipeline directory."
        raise NotImplementedError()

    def to_file(self, filepath):
        "Serialize a ConfigTest to a file."
        with filepath.open(mode="w") as outfile:
            json.dump(
                dataclasses.asdict(self),
                outfile,
                indent=2,
                sort_keys=False
            )
            # Add a trailing newline to the file
            outfile.write("\n")


class NextflowConfigTest(ConfigTest):
    "A subclass."
    SENTINEL = "=========SENTINEL_OUTPUT=========="

    @classmethod
    def from_file(cls, filepath: Path):
        "Load a ConfigTest from a file."
        result = super().from_file(filepath)
        result.filepath = filepath
        return result

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.filepath = None

    def _run_test(self, pipeline_dir: Path):
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
                        f'    includeConfig "{pipeline_dir / configfile}"\n'
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
                "BL_PIPELINE_DIR": str(pipeline_dir),
                "BL_CONFIG_FILE": str(config_file),
                "BL_MOCKS_FILE": str(mocks_file),
                "BL_CLI_PARAMS_FILE": str(cli_params_file),
            }

            if self.params_file:
                envvars["BL_PARAMS_FILE"] = \
                    str(pipeline_dir / self.params_file)

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

    def print_diffs(self, otherfile: Path, gh_annotations: bool):
        "Print the diff results to the console."
        diff_process = subprocess.run(
            ["diff", self.filepath, otherfile],
            capture_output=True,
            check=False
        )
        assert diff_process.returncode == 1
        raw_diff = diff_process.stdout.decode("utf-8")

        if not gh_annotations:
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
            c
            (?P<to_start>\d+)           # First line of the right file
            (?:,(?P<to_end>\d+))        # Last line of the right file
            ?$\n
            (?P<diff>(?:^[-<>].*$\n?)+) # Multiline diff text
            """,
            re.VERBOSE | re.MULTILINE
        )

        # Produce annotations in the GitHub UI
        # https://docs.github.com/en/actions/using-workflows/workflow-commands-for-github-actions#setting-an-error-message
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

            print(f"::error {annotation}::{diff}")

    def check_results(self, pipeline_dir: Path, gh_annotations: bool) -> bool:
        "Compare the results."
        result = self._run_test(pipeline_dir)

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

        if self.expected_result == result:
            return True

        if not self.filepath:
            return False

        outpath = self.filepath.with_name(self.filepath.stem + "-out.json")
        print("Saving updated file to", outpath)
        dataclasses.replace(self, expected_result=result).to_file(outpath)

        self.print_diffs(outpath, gh_annotations)

        return False
