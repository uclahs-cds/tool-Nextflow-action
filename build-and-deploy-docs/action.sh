#!/bin/bash
set -euo pipefail

MKDOCS_CONFIG=$1
README=$2
TOKEN=$3

set_git() {
    remote_repo="https://x-access-token:${TOKEN}@github.com/${GITHUB_REPOSITORY}.git"
    git remote rm origin
    git remote add origin "${remote_repo}"

    if ! git config --get user.name; then
        git config --global user.name "${GITHUB_ACTOR}"
    fi

    if ! git config --get user.email; then
        git config --global user.email "${GITHUB_ACTOR}@users.noreply.github.com"
    fi
}

set_ownership() {
    chown -R $(id -u):$(id -u) ${GITHUB_WORKSPACE}
    # see https://github.com/actions/checkout/issues/766
    git config --global --add safe.directory "${GITHUB_WORKSPACE}"
}

build_and_deploy() {
    config_file=${GITHUB_WORKSPACE}/mkdocs.yml
    mkdocs gh-deploy --config-file $config_file --force
}

main() {
    set_git
    python /src/create_mkdocs_config.py \
        --pipeline-dir ${GITHUB_WORKSPACE} \
        --pipeline-repo ${GITHUB_REPOSITORY} \
        --mkdocs-config ${MKDOCS_CONFIG} \
        --readme ${README}
    set_ownership
    build_and_deploy
}

main
