# Build and Deploy Pipeline Documentation

This Github Action builds a documentation website and deploys it to [GitHub Pages](https://pages.github.com/) for the UCLAHS-CDS pipelines using [MKDocs](https://www.mkdocs.org/).

The pipeline's README.md is split into individual pages based on [level 2 headings](https://www.markdownguide.org/basic-syntax/#headings). A MkDocs config yaml file can also be used to specify specific parameters including additional documentation. Documentation must be written in Markdown syntax.

## Example

```yaml
---
name: Build and Deploy Docs

on:
  workflow_dispatch:
  push:
    branches:
      - main
    tags:
      - 'v[0-9]*'

jobs:
  build:
    name: Deploy docs
    runs-on: ubuntu-latest
    steps:
      - name: Checkout main
        uses: actions/checkout@v4

      - name: Deploy docs
        uses: uclahs-cds/tool-Nextflow-action/build-and-deploy-docs@main
```

## Parameters

Parameters can be specified using the [`with`](https://docs.github.com/en/actions/creating-actions/metadata-syntax-for-github-actions#runsstepswith) option.

| Parameter | Type | Required | Description |
| ---- | ---- | ---- | ---- |
| `readme` | string | no | Relative path to the README file. Defaults to 'README.md' |
| `mkdocs_config` | string | no | Relative path to the MKDocs config yaml. |
