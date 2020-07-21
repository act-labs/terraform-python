import os
import re
import requests
import shutil

import sys
import yaml
from pydantic import BaseModel
from typing import List, Optional, Dict

from .utils import exec

REGISTRY_BASE_URL = 'https://registry.terraform.io/v1/modules'
GITHUB_DOWNLOAD_URL_RE = re.compile(
    'https://[^/]+/repos/([^/]+)/([^/]+)/tarball/([^/]+)/.*')


def get_registry_info(source, version):
    namespace, name, provider = source.split('/')
    registry_download_url = '{base_url}/{namespace}/{name}/{provider}/{version}'.format(
        base_url=REGISTRY_BASE_URL,
        namespace=namespace,
        name=name,
        provider=provider,
        version=version,
    )
    response = requests.get(registry_download_url)
    if response.status_code == 200:
        return response.json()

    # sys.stderr.write('Error looking up module in Terraform Registry: {}\n'.format(response.content))
    # sys.exit(1)


def add_github_token(github_download_url, token):
    github_repo_url_pattern = re.compile(r'.*github.com/(.*)/(.*)\.git')
    match = github_repo_url_pattern.match(github_download_url)
    url = github_download_url
    if match:
        user, repo = match.groups()
        url = 'https://{}@github.com/{}/{}.git'.format(token, user, repo)
    return url


def get_terrafile_path(path):
    if path is None:
        return 'terrafile.yaml'
    if os.path.isdir(path):
        return os.path.join(path, 'terrafile.yaml')
    else:
        return path


def read_terrafile(path):
    try:
        with open(path) as open_file:
            terrafile = yaml.safe_load(open_file)
        if not terrafile:
            raise ValueError('{} is empty'.format(path))
    except IOError as error:
        sys.stderr.write(
            'Error loading Terrafile: {}\n'.format(error.strerror))
        sys.exit(1)
    except ValueError as error:
        sys.stderr.write('Error loading Terrafile: {}\n'.format(error))
        sys.exit(1)
    else:
        return terrafile


def has_git_tag(path, tag) -> bool:
    if os.path.isdir(path):
        output, returncode = exec('git', 'tag', '--points-at=HEAD', cwd=path)
        if returncode == 0:
            return tag in output.split("\n")
    return False


def is_valid_registry_source(source):
    name_sub_regex = '[0-9A-Za-z](?:[0-9A-Za-z-_]{0,62}[0-9A-Za-z])?'
    provider_sub_regex = '[0-9a-z]{1,64}'
    registry_regex = re.compile('^({})\\/({})\\/({})(?:\\/\\/(.*))?$'.format(
        name_sub_regex, name_sub_regex, provider_sub_regex))
    if registry_regex.match(source):
        return True
    else:
        return False

class TerrafileEntry(BaseModel):
    name: Optional[str] = None
    version: str
    source: str

class Terrafile:
    entries: Dict[str, TerrafileEntry]
    token: str
    root_path: str
    project_name: str

    def __init__(self, path=None, token=None):
        terrafile_path = get_terrafile_path(path)
        if token is None and 'GITHUB_TOKEN' in os.environ:
            token = os.getenv('GITHUB_TOKEN')

        self.root_path = os.path.dirname(terrafile_path)
        self.project_name = os.path.basename(os.path.abspath(self.root_path))

        self.token = token

        terrafile = read_terrafile(terrafile_path)

        entries = {}
        for name, repository_details in terrafile.items():
            entry = TerrafileEntry(**repository_details)
            entries[name] = entry

        self.entries = entries

    def update(self):
        for name in sorted(self.entries.keys()):
            self.import_module(name=name)

    def import_module(self, name: str):
        repository_details = self.entries[name]
        if repository_details.name:
            name = repository_details.name

        target = os.path.join(self.root_path, "modules", name)
        source = repository_details.source

        # Support modules on the local filesystem.
        if source.startswith('./') or source.startswith('../') or source.startswith('/'):
            print('Copying {}/{}'.format(self.project_name, name))
            # Paths must be relative to the Terrafile directory.
            source = os.path.join(self.root_path, source)
            shutil.rmtree(target, ignore_errors=True)
            shutil.copytree(source, target)
            return

        version = repository_details.version

        # Support Terraform Registry sources.
        if is_valid_registry_source(source):
            print('Checking {}/{}'.format(self.project_name, name))
            info = get_registry_info(source, version)
            source = info["source"]
            if "tag" in info:
                version = info["tag"]
            else:
                version = info["version"]

        # Skip this module if it has already been checked out.
        # This won't skip branches, because they may have changes
        # that need to be pulled.
        if has_git_tag(path=target, tag=version):
            print('already exists, skipping: {}/{}'.format(self.project_name, name))
            return

        # add token to tthe source url if exists
        if self.token is not None:
            source = add_github_token(source, self.token)
        # Delete the old directory and clone it from scratch.
        print('Fetching {}/modules/{}'.format(self.project_name, name))
        shutil.rmtree(target, ignore_errors=True)
        output, returncode = exec(
            'git', 'clone', '--branch={}'.format(version), source, target)
        if returncode != 0:
            raise Exception("git error code: {}".format(returncode))
        return output
