# Changelog
All notable changes to the tool_name Docker file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

This project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [Unreleased]
### Added
- Action to build and deploy documentation on GitHub Pages
- `backfill.py` script to generate documentation for existing tags
- Add reusable workflow to run Nextflow regression tests
- Add new `nextflow-config-tests` Docker image linked to this repository
- Add `nfconfigtest` script to run regression tests locally
- Add `summary` check for Nextflow tests
- Ability for Nextflow tests to self-resolve in response to "/fix-tests" comments
- Add support for testing configuration in Nextflow 24.10.4

### Changed
- Update output file name to explicitly specify `submodules`
- Update documentation action to use tags and 'development' versions
- Improved GitHub links in documentation links for tagged versions
- Add dynamic mocks to Nextflow regression tests
- Resolve permissions issues with Nextflow tests via multiple workflows
- Rename workflow and status check name to 'Nextflow config tests'

### Fixed
- No longer fail on missing `gh-pages` branch
- No longer fail on relative links to directories
- No longer fail on broken links
- Properly format headings with embedded markdown
- Handle constructing anchor links for repeated headings
- No longer fail when no Nextflow tests are discovered
- Do not store GITHUB_TOKEN in release bundle
- Add new breaking `include-hidden-files` argument to `update-artifact`

---

## [1.0.0-rc.1] - 2022-08-22
### Added
- Action to tar repository with submodules
- Action to add source code with submodules as release asset
