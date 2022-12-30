# Build and Deploy Pipeline Documentation

This github action builds a documentation website and deploy it to [GitHub Pages](https://pages.github.com/) for the UCLA-CDS pipelines using [MKDocs](https://www.mkdocs.org/). It takes the README.md and split sections into individual pages base on the headings. A mkdocs config yaml file can also be used to specify specific parameters including additional documentations. Documentations must be written in Markdown syntax.

## Example

```yaml
---
name: Build and Deploy Docs

on:
  workflow_dispatch:
  push:
    branches:
      - main

jobs:
  build:
    name: Deploy docs
    runs-on: ubuntu-latest
    steps:
      - name: Checkout main
        uses: actions/checkout@v2

      - name: Deploy docs
        uses: uclahs-cds/tool-Nextflow-action/build-and-deploy-docs@czhu-render-and-deploy-doc
        with:
          token: ${{ secrets.UCLAHS_CDS_REPO_READ_TOKEN }}
```

## Parameters

Parameters can be specified using the [`with`](https://docs.github.com/en/actions/creating-actions/metadata-syntax-for-github-actions#runsstepswith) option.

| Parameter | Type | Required | Description |
| ---- | ---- | ---- | ---- |
| `readme` | string | no | Relative path to the README file. Defaults to 'README.md' |
| `mkdocs_config` | string | no | Relative path to the MKDocs config yaml. |
