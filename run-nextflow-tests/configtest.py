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


BAD_CHARACTERS = re.compile(r'[":<>|*?\r\n\\/]')


@dataclasses.dataclass
class NextflowConfigTest:
    "A class representing a single Nextflow configuration test."
    # pylint: disable=too-many-instance-attributes
    SENTINEL: ClassVar = "=========SENTINEL_OUTPUT=========="

    # python3.7 doesn't support `kw_only` and other useful dataclass features.
    # These two fields are workarounds for that.
    OPTIONAL_DICTS: ClassVar = {
        "nf_params",
        "envvars",
        "mocks",
        "dated_fields",
        "version_fields",
    }
    OPTIONAL_LISTS: ClassVar = {
        "dated_fields",
        "version_fields",
    }

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
    version_fields: List[str]

    expected_result: Dict

    @classmethod
    def from_file(cls: Type[T], pipeline: Path, filepath: Path) -> T:
        "Load a ConfigTest from a file."
        with filepath.open(mode="rb") as infile:
            data = json.load(infile)

        # Remove these deprecated fields
        data.pop("empty_files", None)
        data.pop("mapped_files", None)

        for fieldname in cls.OPTIONAL_DICTS:
            data.setdefault(fieldname, {})

        for fieldname in cls.OPTIONAL_LISTS:
            data.setdefault(fieldname, [])

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

        # Strip any empty optional fields from the output
        for field in self.OPTIONAL_DICTS | self.OPTIONAL_LISTS:
            if not data[field]:
                data.pop(field)

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
            return parse_config(
                config_text, self.dated_fields, self.version_fields
            )
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

    def generate_outputs(self, prior: T, print_only: bool):
        """
        Emit any outputs for this test.

        The `print_only` argument controls the kinds of outputs generated.

        If `print_only` is True, this tool is assumed to be running locally
        (not in GitHub Actions). The diff between the original expected_results
        and the updated expected_results is printed to console.

        If `print_only` is False, this tool is assumed to be running in GitHub
        Actions. Lines are written to $GITHUB_OUTPUT (to be used by a later
        workflow step) to create an artifact with the following files:
            * The test file
            * An empty file used to preserve the directory hierarchy
            * (If diff found) A Markdown file with human-readable commentary
              about the test differences. These notes (one per failed test) are
              collected into a pull request review by a later workflow step.
        """
        # Generate the diff between the prior object and this object
        with tempfile.TemporaryDirectory() as tempdir:
            original_file = Path(tempdir, "before.json")
            updated_file = Path(tempdir, "after.json")

            original_file.write_text(
                json.dumps(prior.expected_result),
                encoding="utf-8"
            )

            updated_file.write_text(
                json.dumps(self.expected_result),
                encoding="utf-8"
            )

            jd_output = subprocess.run(
                ["jd", "-set", original_file, updated_file],
                capture_output=True,
                check=False
            ).stdout.decode("utf-8").strip()

        # Sanity check: jd should produce no output if the objects match
        if jd_output and self == prior:
            print(jd_output)
            raise RuntimeError("jd produced diffs for identical tests!")

        # Sanity check: jd should produce output if the objects differ
        if not jd_output and self != prior:
            raise RuntimeError("jd produced no diffs for differing tests!")

        if print_only:
            # Running locally - just print the diff (if any)
            if jd_output:
                print(jd_output)
            return

        # Running in GitHub Actions
        relpath = str(self.filepath.relative_to(self.pipeline))
        # Each archive file needs a unique key
        key = BAD_CHARACTERS.sub("_", relpath)

        # https://github.com/actions/upload-artifact#upload-using-multiple-paths-and-exclusions
        # https://github.com/actions/upload-artifact/issues/174#issuecomment-1909478119
        # Sigh. We also need to include a dummy file at the root to ensure
        # that the directory structure is preserved
        dummy_filename = f".{key}-dummy"
        Path(dummy_filename).touch()

        filenames = [relpath, dummy_filename]

        if jd_output:
            # Write out a chunk of Markdown text describing the test
            # differences. The eventual PR review will combine all such notes.
            notepath = Path(self.pipeline, f".{key}.prnote")
            with notepath.open(mode="w", encoding="utf-8") as note_fileobj:
                note_fileobj.write(f"### {relpath}\n```diff\n")
                note_fileobj.write(jd_output)
                note_fileobj.write("\n```\n")

            # Include the note in the list of files to be archived
            filenames.append(str(notepath.relative_to(self.pipeline)))

            # Also update the key name to highlight tests with differences
            key += " (changed)"

        # Guard against malicious filenames
        eof_index = 0
        while f"EOF{eof_index}" in "".join(filenames):
            eof_index += 1

        with Path(os.environ["GITHUB_OUTPUT"])\
                .open(mode="w", encoding="utf-8") as outfile:
            # Write out a string with the artifact's name
            outfile.write(f"archive_key={key}\n")

            # Write out a multiline string encoding the files to be archived.
            # Make sure to include the final trailing newline.
            # https://docs.github.com/en/actions/using-workflows/workflow-commands-for-github-actions#multiline-strings
            outfile.write("\n".join([
                f"archive_path<<EOF{eof_index}",
                *filenames,
                f"EOF{eof_index}",
                ""
            ]))

    def recompute_results(self: T, overwrite: bool) -> T:
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
        if not overwrite:
            # Update the filepath so as not to overwrite the original
            regenerated_test.filepath = self.filepath.with_name(
                self.filepath.stem + "-out.json"
            )

        regenerated_test.to_file()

        return regenerated_test
