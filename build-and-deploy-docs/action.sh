#!/bin/bash
set -euo pipefail

MKDOCS_CONFIG=$1
README=$2

set_git() {
    # see https://github.com/actions/checkout/issues/766
    git config --global --add safe.directory "${GITHUB_WORKSPACE}"

    git config --global user.name "${GITHUB_ACTOR}"
    git config --global user.email "${GITHUB_ACTOR}@users.noreply.github.com"

    # See https://github.com/jimporter/mike/tree/af47b9699aeeeea7f9ecea2631e1c9cfd92e06af#deploying-via-ci
    git fetch origin gh-pages --depth=1
}

build_and_deploy() {
    config_file=${GITHUB_WORKSPACE}/mkdocs.yml

    # Create a new commit on the gh-pages branch with documentation from this
    # version and alias that as "latest"
    mike deploy \
        --config-file "$config_file" \
        --update-aliases \
        "$(git describe --tags --always)" \
        latest

    # Redirect from the base site to the latest version. This will be a no-op
    # after the very first deployment, but it will not cause problems
    mike set-default \
        --config-file "$config_file" \
        latest

    # Push up the changes to the docs
    git push origin gh-pages
}

main() {
    set_git
    python /src/create_mkdocs_config.py \
        --pipeline-dir "${GITHUB_WORKSPACE}" \
        --pipeline-repo "${GITHUB_REPOSITORY}" \
        --mkdocs-config "${MKDOCS_CONFIG}" \
        --readme "${README}"
    build_and_deploy
}

main
