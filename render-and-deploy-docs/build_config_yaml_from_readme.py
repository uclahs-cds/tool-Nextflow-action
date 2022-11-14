""" """
from typing import Dict, List
import os
from pathlib import Path
import re
import shutil
import yaml


def get_workspace() -> Path:
    """ """
    return Path(os.getenv('GITHUB_WORKSPACE'))

def split_readme() -> Dict[str, Path]:
    """ """
    contents:Dict[str, List[str]] = {}
    paths:Dict[str, Path] = {}
    work_dir = get_workspace()
    readme_file = work_dir/'README.md'
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

def get_pipeline_name():
    """ """
    repo_name = os.getenv('GITHUB_REPOSITORY').split('/')[1]
    pipeline_name = repo_name
    for key in ['pipeline', 'metapipeline']:
        if pipeline_name.startswith(key):
            pipeline_name.replace(key, '')
            break
    return pipeline_name

def load_metadata():
    """ """
    work_dir = get_workspace()
    with open(work_dir, 'r') as handle:
        return yaml.safe_load(handle)

def build_mkdocs_config():
    """ """
    paths = split_readme()
    config_data = {
        'site_name': get_pipeline_name(),
        'docs_dir': 'docs/',
        'repo_url': 'https://github.com/' + os.getenv('GITHUB_REPOSITORY'),
        'nav': [{key:val.name} for key,val in paths.items()],
        'theme': 'readthedocs',
        'markdown_extensions': ['tables', 'admonition']
    }
    workspace = get_workspace()
    with open(workspace/'mkdocs.yml', 'w') as handle:
        yaml.dump(config_data, handle)


if __name__ == '__main__':
    build_mkdocs_config()
