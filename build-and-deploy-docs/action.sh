#!/bin/bash
set -euo pipefail

MKDOCS_CONFIG=$1
README=$2
TOKEN=$3

set_git() {
    # see https://github.com/actions/checkout/issues/766
    git config --global --add safe.directory "${GITHUB_WORKSPACE}"

    remote_repo="https://x-access-token:${TOKEN}@github.com/${GITHUB_REPOSITORY}.git"
    git remote rm origin
    git remote add origin "${remote_repo}"

    git config --global user.name "${GITHUB_ACTOR}"
    git config --global user.email "${GITHUB_ACTOR}@users.noreply.github.com"
}

build_and_deploy() {
    config_file=${GITHUB_WORKSPACE}/mkdocs.yml
    mike deploy \
        --config-file "$config_file" \
        "$(git describe --tags --always)"
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
