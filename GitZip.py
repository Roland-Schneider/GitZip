#!/usr/bin/env python3

# Invoke as
# python GitZip.py ~/Documents/Programming/Backup/
# python GitZip.py smb://user@server/Backup/
# --or--
# Copy this file to ~/.local/bin/GitZip.py
# Ensure ~/.local/bin is part of $PATH (Test by invoking 'echo $PATH' in bash terminal)
# chmod +x ~/.local/bin/GitZip.py
# Make entry in file ~/.bash_aliases:
# alias gitzip='~/.local/bin/GitZip.py'

import argparse
from sys import exit as app_exit, platform
import subprocess
from enum import IntFlag, auto   # Python 3.6
import tempfile
import os
import zipfile
import re as regex
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

class ArgumentParserEx(argparse.ArgumentParser):
    def error(self, message):
        raise argparse.ArgumentError(None, message)

def print_error(message):
    parser.print_usage()
    print(f'{parser.prog}: error: {message}')

def subprocess_run(args):
    # print(subprocess.list2cmdline(args))
    process = subprocess.run(args, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    # print(process.stdout)
    process.check_returncode()
    # print(f'type(process)={type(process)}  type(process.stdout)={type(process.stdout)}')
    return process.stdout

def resolve_path(path_or_uri):
    if platform == 'win32':
        return Path(path_or_uri)
    elif platform == 'linux':
        p = urlparse(path_or_uri)
        if p.scheme:
            match p.scheme:
                case 'smb':
                    gvfs = Path(f'/run/user/{os.getuid()}/gvfs')
                    share, *rest = p.path.lstrip('/').split('/', 1)
                    relpath = rest[0] if rest else ''
                    for mount in gvfs.iterdir():
                        name = mount.name
                        if (name.find(f'server={p.hostname}') >= 0 and name.find(f'share={share}') >= 0
                            and (p.username is None or name.find(f'user={p.username}') >= 0)):
                            return mount.joinpath(relpath)
                    raise FileNotFoundError(f'GVfs mount not found for {path_or_uri}')
                case _:
                    raise ValueError(f'Unsupported URI scheme: {p.scheme}')
        else:
            return Path(path_or_uri)
    else:
        raise Exception(f'Unsupported operating system \'{platform}\'')

class Scope(IntFlag):
    UNSTAGED_FILES = auto()          # 1
    STAGED_AND_COMMITTED_FILES = auto()  # 2

parser = ArgumentParserEx(description='Pack together all current changes in a git repository with previous versions for reference')
parser.set_defaults(file_scope=Scope.UNSTAGED_FILES | Scope.STAGED_AND_COMMITTED_FILES)
group = parser.add_mutually_exclusive_group()
group.add_argument('--unstaged_only', dest='file_scope', action='store_const', const=Scope.UNSTAGED_FILES)
group.add_argument('--staged_and_committed', dest='file_scope', action='store_const', const=Scope.STAGED_AND_COMMITTED_FILES)
parser.add_argument('--no_previous_versions', action='store_true')
parser.add_argument('out_location')

try:
    args = parser.parse_args()
except argparse.ArgumentError as e:
    # parser.print_help()
    print_error(e.message)
    app_exit(2)

# print(f'no_previous_versions={args.no_previous_versions}')
# print(f'file_scope={args.file_scope}')
# print(f'out_location={args.out_location}')

if not args.out_location.endswith(os.sep):
    print_error(f'out_location needs to end with \'{os.sep}\' to indicate a folder')
    app_exit(2)

repository_url = subprocess_run(['git', 'config', '--local', 'remote.origin.url']).strip()
#print(f'repository_url={repository_url}')
workspace_name = repository_url.split('/')[-1]
#print(f'workspace_name={workspace_name}')
branch_name = subprocess_run(['git', 'rev-parse', '--abbrev-ref', 'HEAD']).replace('/', '.').strip()
# print(f'branch_name={branch_name}')
workspace_root = subprocess_run(['git', 'rev-parse', '--show-toplevel']).strip()
# print(f'workspace_root={workspace_root}')
out_path = resolve_path(args.out_location)
zip_filepath = os.path.join(out_path, datetime.now().strftime('%Y%m%dT%H%M%S') + '_' + workspace_name+ '_' + branch_name + '.zip')
# print(f'out_file={zip_filepath}')
main_branch_name = subprocess_run(['git', 'symbolic-ref', 'refs/remotes/origin/HEAD', '--short']).strip()
# print(f'main_branch_name={main_branch_name}')
branch_info = subprocess_run(['git', 'log', '--all', '--graph', '--decorate', '--oneline', '--simplify-by-decoration'])

files = set()  # The Python set object ensures items are unique, e.g. if file is committed and modified again
if args.file_scope & Scope.UNSTAGED_FILES:
    # print('unstaged files included')
    # Modified but not staged:  git diff --name-only
    files.update(subprocess_run(['git', 'diff', '--name-only']).splitlines())
    # Untracked files:  git ls-files --others --exclude-standard
    files.update(subprocess_run(['git', 'ls-files', f'{workspace_root}', '--others', '--exclude-standard', '--full-name']).splitlines())
if args.file_scope & Scope.STAGED_AND_COMMITTED_FILES:
    # print('staged and committed files included')
    # Staged (git add):  git diff --name-only --cached
    files.update(subprocess_run(['git', 'diff', '--name-only', '--cached']).splitlines())
    # Committed compared to main branch:  git diff --name-only origin/Main...
    files.update(subprocess_run(['git', 'diff', '--name-only', f'{main_branch_name}...']).splitlines())

files = sorted(files)

if len(files) > 0:
    print(f'Writing to {zip_filepath}')
    # print(*files, sep='\n')

    info_filename = 'GitZip.log'
    info_filepath = os.path.join(tempfile.gettempdir(), info_filename)

    with zipfile.ZipFile(zip_filepath, 'w', compression=zipfile.ZIP_DEFLATED) as zip_file:
        with open(info_filepath, 'w') as info_file:
            for filepath_relative in files:
                filepath_absolute = os.path.join(workspace_root, filepath_relative)

                status = subprocess_run(['git', 'status', '--porcelain=v1', '--', f'{filepath_relative}']).strip()
                # print(f'{status}')
                status = status[0:2]  # Take 2 characters at position 0
                info_file.write(f'{status} {filepath_relative}\n')
                deleted = status.find('D') >= 0
                if not deleted:
                    zip_file.write(filepath_absolute, filepath_relative)
                    print(f'Include {filepath_relative}')
                else:
                    print(f'Detected deleted file {filepath_relative}')

                if not args.no_previous_versions:
                    previous_version_hash = subprocess_run(['git', 'log', f'--pretty=format:%H', '--max-count=1', f'{main_branch_name}', '--', f'{filepath_relative}']).strip()
                    # print(previous_version_hash)
                    if len(previous_version_hash) > 0 and regex.search('^[0-9a-fA-F]{40}$', previous_version_hash):
                        # print('Has hash')
                        root, ext = os.path.splitext(filepath_relative)
                        # print(f'root={root} ext={ext}')
                        filepath_previous_relative = root + '.' + previous_version_hash + ext
                        # print(f'{filepath_previous_relative}')

                        blob_filepath = os.path.join(tempfile.gettempdir(), 'GitZip.tmp')
                        with open(blob_filepath, 'wb') as blob_file:
                            subprocess.run(
                                ['git', 'cat-file', '-p', f'{previous_version_hash}:{filepath_relative}'],
                                stdout=blob_file,
                                check=True,
                            )
                        previous_time_iso8601 = subprocess_run(['git', 'show', '--no-patch', '--pretty=%cI', f'{previous_version_hash}']).strip()
                        # print(previous_time_iso8601)
                        previous_timestamp = datetime.fromisoformat(previous_time_iso8601).timestamp()
                        os.utime(blob_filepath, (previous_timestamp, previous_timestamp))
                        zip_file.write(blob_filepath, filepath_previous_relative)
                        os.remove(blob_filepath)

            info_file.write(f'\n{repository_url}\n')
            info_file.write(f'\n{branch_info}')
        zip_file.write(info_filepath, info_filename)

    if os.path.exists(info_filepath):
        os.remove(info_filepath)
else:
    print('No modified files detected')

