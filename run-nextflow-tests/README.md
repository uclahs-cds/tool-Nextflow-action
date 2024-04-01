# Run Nextflow Configuration Tests

This Github Action discovers and runs all bundled configuration tests for Nextflow pipelines.

## Regression Test Format

Configuration tests are self-contained JSON files named `configtest*.json` with the following keys:

| Key | Description |
| --- | --- |
| nextflow_version | The version of Nextflow to be used for the tests (e.g. `23.10.0`) |
| config | A list of configuration files to be included (`nextflow -c <file1> -c <file2>`) |
| params_file | A single parameter file or an empty string (`nextflow -params-file <file>`) |
| cpus | The integer CPU count to be returned by `SysHelper::getAvailCpus()` |
| memory_gb | The memory value to be returned by `SysHelper::getAvailMemory` (float, GB) |
| nf_params | A map of command-line parameters to pass to Nextflow (`nextflow --<key>=<value>`) |
| envvars | A map of environment variables to set (`KEY=VALUE nextflow ...`) |
| mocks | Method names to be mocked, mapped to the objects they should return |
| dated_fields | A list of JSONPath-like keys indicating values in the rendered configuration that contain datestamps |
| version_fields | A list of JSONPath-like keys indicating values in the rendered configuration that contain the pipeline version number |
| expected_results | The expected output of the test |

For each test, this Action parses the configuration and runs a modified version of [`nextflow config`](https://www.nextflow.io/docs/latest/cli.html#config), comparing the results against `expected_results` and warning about any differences.

The partition type (e.g. `F2`, `F16`, `F72`) can be mocked using the `cpus` and `memory_gb` keys.

Any methods that access files outside of the repository must be listed in `mocks`. For Boutros Lab pipelines a common method is [`schema.check_path`](https://github.com/uclahs-cds/pipeline-Nextflow-config/blob/3ec718630ff1862377815e6c986a8b56cea1115b/config/schema/schema.config#L51-L56), which can be mocked like so:

```json
  "mocks": {
    "check_path": ""
  }
```

### Dynamic Mocks

In very specific circumstances a mock function that returns a static value is insufficient - for example, a pipeline that requires paired input BAMs might check that they have separate sample IDs. That means that this mock...

```json
  "mocks": {
    "parse_bam_header": {
      "read_group": [
        {
          "SM": "495723"
        }
      ]
    }
  }
```

... would return the same sample ID for each input BAM and thus fail.

To solve this, a dynamic mock like the following may be used:

```json
  "mocks": {
    "DYNAMIC|parse_bam_header": {
      "[\"/hot/software/pipeline/pipeline-SQC-DNA/Nextflow/development/test-input/HG002.N-n2.bam\"]": {
        "read_group": [
          {
            "SM": "098765"
          }
        ]
      },
      "[\"/hot/software/pipeline/pipeline-SQC-DNA/Nextflow/development/test-input/S2.T-n2.bam\"]": {
        "read_group": [
          {
            "SM": "52345245"
          }
        ]
      }
    }
  }
```

Dynamic mocks have their method name prefixed with `DYNAMIC|`. Their values are maps with JSONified function arguments for keys and static return values as values. Note that the function arguments are always presented as a list, even for a single argument.

## Usage

### Workflow Files

These two workflows must be added to each repository. They will only behave correctly once merged to the `main` branch.

```yaml
---
name: Trigger tests
on:
  issue_comment:
    types: [created]
  pull_request_target:
    branches:
      - main
  push:
    branches:
      - main

permissions:
  pull-requests: write
  statuses: write

jobs:
  check-user:
    uses: uclahs-cds/tool-Nextflow-action/.github/workflows/test-setup.yml@main
```

```yaml
---
name: Nextflow

on:
  workflow_run:
    workflows: [Trigger Tests]
    types:
      - completed

permissions:
  contents: write
  pull-requests: write
  statuses: write
  actions: read
  packages: read

jobs:
  tests:
    if: ${{ github.event.workflow_run.conclusion == 'success' }}
    uses: uclahs-cds/tool-Nextflow-action/.github/workflows/nextflow-tests.yml@main
    secrets: inherit
```

### Example Test
```json
{
  "nextflow_version": "23.10.0",
  "config": [
    "test/global.config",
    "test/config/gsv_discovery-all-tools.config"
  ],
  "params_file": "test/yaml/gsv_test-std-input.yaml",
  "cpus": 16,
  "memory_gb": 31,
  "nf_params": {
    "output_dir": "/tmp/outputs"
  },
  "envvars": {
    "SLURM_JOB_ID": "8543"
  },
  "mocks": {
    "check_path": ""
  },
  "dated_fields": [
    "params.log_output_dir",
    "report.file",
    "timeline.file",
    "trace.file",
    "params.date"
  ],
  "expected_result": {}
}
```

### Output Modifications

The true Nextflow configuration output is slightly modified for usability:

* Every field listed in `dated_fields` has timestamps matching the format `YYYYMMDDTHHMMSSZ` replaced with the static value `19970704T165655Z` ([Pathfinder's landing](https://science.nasa.gov/mission/mars-pathfinder/)).
* Every field listed in `version_fields` has sub-strings matching the `manifest.version` value replaced with the static value `VER.SI.ON`.
* Every value that looks like a Java object (e.g. `[Ljava.lang.String;@49c7b90e`) has the hash code replaced with the static value `dec0ded`.
    * These should not appear in test files. When they do, it is a sign that the corresponding variable is missing a `def` in the configuration file.
* Closures are expressed as the first valid item in this list:
    * The result of evaluating the closure
    * A map with the closure's code and the results of evaluating it with the additional variables `task.attempt` and `task.cpus` set
    * The static string `closure()`

## Local Usage

Regression tests can be run locally with the [`nfconfigtest`](./nfconfigtest) script included with this repository.

```console
usage: nfconfigtest [-h] [--dev] [--path repo]

Run the Nextflow configuration regression tests for a specified pipeline.

options:
  -h, --help   show this help message and exit
  --dev        Rebuild and use image from the checked-out repository
  --path repo  Root of the repository to be tested (default: .)
```
