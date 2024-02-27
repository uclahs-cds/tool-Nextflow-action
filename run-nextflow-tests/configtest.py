"""
The class representation of a Nextflow configuration test.
"""
import dataclasses
import itertools
import json
import os
import re
import subprocess
import tempfile
import textwrap

from contextlib import ExitStack
from pathlib import Path
from typing import List, Dict

from utils import parse_config, diff_json


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

    def check_results(self, pipeline_dir: Path, overwrite: bool) -> bool:
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
                envvars["BL_PARAMS_FILE"] = str(pipeline_dir / self.params_file)

            try:
                # Launch the docker container in the background and immediately
                # capture the container ID (so that we can clean up afterwards)
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
            return parse_config(config_text)
        except Exception:
            print(config_output)
            raise

    def check_results(self, pipeline_dir: Path, overwrite: bool) -> bool:
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

        differences = diff_json(self.expected_result, result)

        # Filter out any differences resulting from dates
        date_re = re.compile(r"\d{8}T\d{6}Z")
        for index, (jsonpath, original, updated) in \
                reversed(list(enumerate(differences))):
            if re.sub(r"^\.+", "", jsonpath) in self.dated_fields:
                if date_re.sub("", original) == date_re.sub("", updated):
                    differences.pop(index)

        if differences:
            for key, original, updated in differences:
                print(key)
                print(original)
                print(updated)
                print("------")

            if self.filepath:
                if not overwrite:
                    outpath = self.filepath.with_name(
                        self.filepath.stem + "-out.json")
                else:
                    outpath = self.filepath

                print("Saving updated file to", outpath)
                dataclasses.replace(
                    self,
                    expected_result=result
                ).to_file(outpath)

            return False

        return True
