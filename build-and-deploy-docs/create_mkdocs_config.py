#!/usr/bin/env python3
""" Create MKDocs config yaml. If a README file is given, the content is split
into individual markdown file for MKDocs to render. """
import argparse
import collections
import re
import shutil
import itertools

from urllib.parse import urlparse, urlunparse
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List

import magic
import yaml
import mdformat
from markdown_it import MarkdownIt
from markdown_it.token import Token
from mdformat.renderer import RenderContext, RenderTreeNode



VALID_IMAGE_MIME_TYPES = {
    'image/png',
    'image/jpeg',
    'image/pjpeg'
    'image/gif',
    'image/tiff',
    'image/x-tiff',
    'image/svg+xml'
}

# pylint: disable=R0914

def parse_args():
    """ parse args """
    parser = argparse.ArgumentParser()
    parser.add_argument(
        '--pipeline-dir',
        type=Path,
        required=True,
        help='Path to the pipeline directory. Should be set to GITHUB_WORKSPACE'
        ' when called from github action.'
    )
    parser.add_argument(
        '--pipeline-repo',
        type=str,
        required=True,
        help='Pipeline repo name. Should be set to GITHUB_REPOSITORY when called'
        ' from github action.'
    )
    parser.add_argument(
        '--mkdocs-config',
        type=Path,
        help='Additional MKDocs config file.',
        default=None
    )
    parser.add_argument(
        '--readme',
        type=Path,
        help='Relative path to the README.md file.',
        default=Path('README.md')
    )
    return parser.parse_args()


def is_url(path: str) -> bool:
    """ Checks if the given path is an url. """
    return path.startswith('http')


def validate_image(path: str, work_dir: Path) -> Path:
    """ Check whether the given path is a valid image file and return the
    cleaned and resolved path. """
    path = path.split('?')[0]
    validated_path = Path(path)

    if not validated_path.is_absolute():
        validated_path = work_dir / validated_path

    if not str(validated_path.resolve()).startswith(str(work_dir.resolve())) \
            or not validated_path.exists() \
            or magic.from_file(str(validated_path), mime=True) not in VALID_IMAGE_MIME_TYPES:
        raise ValueError(f'The given path {validated_path} is invalid.')

    return validated_path


def get_heading_anchor(text):
    """
    Return the anchor name GitHub would assign to this heading text.
    """
    # Based on https://gist.github.com/asabaylus/3071099, it seems like GitHub
    # replaces spaces with dashes and strips all special characters other than
    # - and _. I can't find an authoritative source confirming these rules.
    no_spaces = re.sub(r"\s", "-", text.strip())
    no_specials = re.sub(r"[^\w_-]", "", no_spaces)
    return no_specials.casefold()


@dataclass
class Page:
    "A page to be rendered."
    title: str
    filename: str = ""
    tokens: list[Token] = field(default_factory=list)

    def get_filename(self):
        "Get the associated filename."
        if not self.filename:
            return get_heading_anchor(self.title) + ".md"
        return self.filename


def split_readme_new(readme_file: Path,
                     docs_dir: Path,
                     pipeline_repo: str) -> Dict[str, Path]:
    """
    Split the README file into individual markdown files.
    """
    img_dir = docs_dir / 'img'

    docs_dir.mkdir(exist_ok=True)
    img_dir.mkdir(exist_ok=True)

    # Parse the original markdown file into tokens
    with readme_file.open(encoding="utf-8") as infile:
        tokens = MarkdownIt("gfm-like").parse(infile.read())

    # Break the monolithic page into multiple pages on H2s. Name the pages by
    # the content of their headings. Simultaneously, build up a corrected set
    # of anchor links
    anchor_pages = {}

    current_page = Page("Home", filename="index.md")
    pages = [current_page, ]

    for token, next_token in itertools.pairwise(
            itertools.chain(tokens, [None, ])):
        if token.type == "heading_open":
            heading_content = next_token.content

            if token.tag == "h2":
                # We've moved on to a new page
                current_page = Page(heading_content)
                pages.append(current_page)

            # Associate this heading with the the current page
            anchor = get_heading_anchor(heading_content)
            assert anchor not in anchor_pages
            anchor_pages[anchor] = current_page.get_filename()

        current_page.tokens.append(token)

    def sanitize_link(url):
        link = urlparse(url)

        if link.scheme or link.netloc:
            # This is a "real" link (https://, ftp://, etc.) - don't touch it
            return url

        if link.path:
            # This is a link to a file on disk
            resolved_path = Path(readme_file.parent, link.path).resolve()

            # If the path reaches outside of the repo, bail out
            if not resolved_path.is_relative_to(readme_file.parent):
                return url

            # If the path is already under the docs directory, correct it
            if resolved_path.is_relative_to(docs_dir):
                return urlunparse((
                    "",     # scheme
                    "",     # netloc
                    str(resolved_path.relative_to(docs_dir)),
                    link.params,
                    link.query,
                    link.fragment
                ))

            # If the link is to an image, copy that image to the docs
            filetype = magic.from_file(resolved_path, mime=True)
            if filetype in VALID_IMAGE_MIME_TYPES:
                output_path = Path(img_dir, resolved_path.name)
                shutil.copy2(resolved_path, output_path)

                return urlunparse((
                    "",     # scheme
                    "",     # netloc
                    str(output_path.relative_to(docs_dir)),
                    link.params,
                    link.query,
                    link.fragment
                ))

            # For everything else, link to the file on GitHub
            return urlunparse((
                "https",
                "github.com",
                str(Path(
                    pipeline_repo,
                    "blob",
                    "main",
                    resolved_path.relative_to(readme_file.parent)
                )),
                link.params,
                link.query,
                link.fragment
            ))

        if link.fragment:
            # This is an anchor link. As we've split the monolithic README into
            # multiple files, we need to prepend those filepaths.
            return urlunparse((
                "",     # scheme
                "",     # netloc
                anchor_pages[get_heading_anchor(link.fragment)],
                "",     # params
                "",     # query
                link.fragment
            ))

        return url

    # Examine and correct all links (if necessary)
    tokens_to_examine = collections.deque(tokens)
    while tokens_to_examine:
        token = tokens_to_examine.popleft()
        if token.children:
            tokens_to_examine.extend(token.children)

        if token.type == "link_open" and "href" in token.attrs:
            token.attrs["href"] = sanitize_link(token.attrs["href"])

        elif token.type == "image" and "src" in token.attrs:
            token.attrs["src"] = sanitize_link(token.attrs["src"])

    # Write out each page to a separate file
    renderer = mdformat.renderer.MDRenderer()
    options = {
        'parser_extension': [
            mdformat.plugins.PARSER_EXTENSIONS['gfm'],
            mdformat.plugins.PARSER_EXTENSIONS['tables'],
        ]
    }

    table_of_contents = []

    for page in pages:
        fullpath = Path(docs_dir, page.get_filename())
        fullpath.write_text(
            renderer.render(page.tokens, options, {}),
            encoding="utf-8"
        )

        table_of_contents.append({page.title: page.get_filename()})

    return table_of_contents


def get_pipeline_name(repo: str):
    """ Get the pipeline name. """
    pipeline_name = repo.rsplit('/', maxsplit=1)[-1]
    return pipeline_name

def get_mkdocs_config_data(path:Path, repo:str):
    """ Read the given MKDocs config file or create it from default.

    Args:
        - `path`: Path to the MKDocs config file. When set to None, default
          config is used.
        - `repo`: The github repo name.
    """
    if path is not None:
        with open(path, 'rt') as handle:
            data = yaml.safe_load(handle)
            if 'nav' not in data:
                data['nav'] = []
            return data
    else:
        return {
            'site_name': get_pipeline_name(repo),
            'docs_dir': 'docs/',
            'repo_url': 'https://github.com/' + repo,
            'nav': [],
            'theme': 'readthedocs',
            'markdown_extensions': ['tables', 'admonition'],
            'edit_uri_template': 'blob/main/README.md',
            'plugins': ['mike'],
        }


def build_mkdocs_config():
    """ Build the mkdocs config file. """
    args = parse_args()
    repo = args.pipeline_repo
    work_dir = args.pipeline_dir
    mkdocs_config = args.mkdocs_config

    if mkdocs_config is not None \
            and (mkdocs_config.name == 'None' or mkdocs_config == 'None'):
        mkdocs_config = None

    if mkdocs_config is not None:
        mkdocs_config = work_dir/mkdocs_config

    config_data = get_mkdocs_config_data(mkdocs_config, repo)

    if args.readme:
        readme_nav = split_readme_new(
            readme_file=work_dir/args.readme,
            docs_dir=work_dir/config_data['docs_dir'],
            pipeline_repo=args.pipeline_repo
        )

        config_data['nav'] = readme_nav + config_data['nav']

    with open(work_dir/'mkdocs.yml', 'w', encoding="utf-8") as handle:
        yaml.dump(config_data, handle, explicit_start=True)


if __name__ == '__main__':
    build_mkdocs_config()
