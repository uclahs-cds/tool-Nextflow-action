#!/bin/bash
set -euo pipefail

set_git() {
    remote_repo="https://x-access-token:${GITHUB_TOKEN}@github.com/${GITHUB_REPOSITORY}.git"
    git remote rm origin
    git remote add origin "${remote_repo}"

    if ! git config --get user.name; then
        git config --global user.name "${GITHUB_ACTOR}"
    fi

    if ! git config --get user.email; then
        git config --global user.email "${GITHUB_ACTOR}@users.noreply.github.com"
    fi
}

build_and_deploy() {
    config_file=${GITHUB_WORKSPACE}/mkdocs.yml
    mkdocs gh-deploy --config-file $CONFIG_FILE --force
}

main() {
    set_git
    python /src/build_config_yaml_from_readme.py
    build_and_deploy
}

main
