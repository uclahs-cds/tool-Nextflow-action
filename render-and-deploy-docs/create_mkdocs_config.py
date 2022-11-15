""" Create MKDocs config yaml. If a README file is given, the content is split
into individual markdown file for MKDocs to render. """
import argparse
from typing import Dict, List
from pathlib import Path
import re
import shutil
import yaml


def parse_args():
    """ parse args """
    parser = argparse.ArgumentParser()
    parser.add_argument(
        '--pipeline-dir',
        type=Path,
        help='Path to the pipeline directory. Should be set to GITHUB_WORKSPACE'
        ' when called from github action.'
    )
    parser.add_argument(
        '--pipeline-repo',
        type=str,
        help='Pipeline repo name. Should be set to GITHUB_REPOSITORY when called'
        ' from github action.'
    )
    parser.add_argument(
        '--mkdocs-config',
        type=Path,
        help='Additional '
    )
    parser.add_argument(
        '--readme',
        type=Path,
        help='Relative path to the README.md file.',
        default=Path('README.md')
    )
    return parser.parse_args()

def split_readme(path:Path, work_dir:Path) -> Dict[str, Path]:
    """ Split the README file into individual markdown.

    Args:
        - `path`: Path to the README file.
        - `work_dir`: Path to the pipeline directory.
    """
    contents:Dict[str, List[str]] = {}
    paths:Dict[str, Path] = {}
    readme_file = work_dir/path
    docs_dir = work_dir/'docs'
    img_dir = docs_dir/'img'

    docs_dir.mkdir(exist_ok=True)

    cur = None
    with open(readme_file, 'rt') as handle:
        line:str
        for line in handle:
            if line.startswith('## '):
                header = re.sub('^#+ ', '', line.rstrip())

                if header.lower() == 'overview':
                    header = 'Home'
                cur = contents.setdefault(header, [])
                if len(cur) == 0:
                    if header == 'Home':
                        doc_file_name = 'index.md'
                    else:
                        doc_file_name = header.lower().replace(' ','-') + '.md'
                    doc_file_path = docs_dir/doc_file_name
                    paths[header] = doc_file_path

            if cur is None:
                continue

            p = re.compile(r'!\[.+\]\((\S+)\)$')
            m = p.match(line)
            if m:
                image = m.group(1)
                if not image.startswith('http'):
                    image = image.split('?')[0]
                    image_path = work_dir/image
                    if image_path.exists():
                        img_dir.mkdir(exist_ok=True)
                        shutil.copy2(image, img_dir)
                        image_name = Path(image).name
                        line = re.sub(image, f"img/{image_name}", line)

            cur.append(line)

    for key, content in contents.items():
        path = paths[key]
        with open(path, 'w') as handle:
            for line in content:
                handle.write(line)

    return paths

def get_pipeline_name(repo:str):
    """ Get the pipeline name. """
    pipeline_name = repo.split('/')[1]
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
    else:
        return {
            'site_name': get_pipeline_name(repo),
            'docs_dir': 'docs/',
            'repo_url': 'https://github.com/' + repo,
            'nav': [],
            'theme': 'readthedocs',
            'markdown_extensions': ['tables', 'admonition']
        }

def build_mkdocs_config():
    """ Build the mkdocs config file. """
    args = parse_args()
    repo = args.pipeline_repo
    work_dir = args.pipeline_dir
    mkdocs_config = args.mkdocs_config

    if mkdocs_config.name == 'None' or mkdocs_config == 'None':
        mkdocs_config = None

    config_data = get_mkdocs_config_data(mkdocs_config, repo)

    if args.readme:
        paths = split_readme(args.readme, work_dir)
        for key, val in paths.items():
            config_data['nav'].append({key:val.name})

    with open(work_dir/'mkdocs.yml', 'w') as handle:
        yaml.dump(config_data, handle)


if __name__ == '__main__':
    build_mkdocs_config()
