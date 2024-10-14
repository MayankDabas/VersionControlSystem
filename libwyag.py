import argparse
import collections
import configparser
import grp
import hashlib
import os
import pwd
import re
import sys
import zlib

from datetime import datetime
from fnmatch import fnmatch
from math import ceil

argparse = argparse.ArgumentParser(description="Parse the commmands needed by program")
argsubparsers = argparse.add_subparsers(title="Command", dest="command")
argsubparsers.required = True

class GitRepository(object):
    worktree = None
    gitdir = None
    config = None

    def __init__(self, path, force=False):
        self.worktree = path
        self.gitdir = os.path.join(path, ".git")

        if not (force or os.path.isdir(self.gitdir)):
            raise Exception(f"Not a Git repository {path}")
        
        self.config = configparser.ConfigParser()
        conf = repo_file(self, "config")

        if conf and os.path.exists(conf):
            self.config.read([conf])
        elif not force:
            raise Exception("Configuration file missing")
        
        if not force:
            vers = int(self.config.get("core", "repositoryformatversion"))
            if vers != 0:
                raise Exception(f"Unsupported repositoryformatversion {vers}")

def repo_path(repo, *path):
    return os.path.join(repo.gitdir, *path)

def repo_dir(repo, *path, mkdir=False):
    path = repo_path(repo, *path)

    if os.path.exists(path):
        if os.path.isdir(path):
            return path
        else:
            raise Exception(f"Not a directory {path}")
    
    if mkdir:
        os.mkdir(path)
        return path
    else:
        return None

def repo_file(repo, *path, mkdir=False):
    if repo_dir(repo, *path[:-1], mkdir=mkdir):
        return repo_path(repo, *path)

def repo_default_config():
    ret = configparser.ConfigParser()

    ret.add_section("core")
    ret.set("core", "repositoryformatversion", "0")
    ret.set("core", "filemode", "false")
    ret.set("core", "bare", "false")

    return ret

def repo_create(path):
    repo = GitRepository(path, True)

    if os.path.exists(repo.worktree):
        if not os.path.isdir(repo.worktree):
            raise Exception(f"{path} is not a directory!")
        if os.path.exists(repo.gitdir) and os.listdir(repo.gitdir):
            raise Exception(f"{path} is not empty!")
    else:
        os.mkdir(repo.worktree)
    
    assert repo_dir(repo, "branches", mkdir=True)
    assert repo_dir(repo, "objects", mkdir=True)
    assert repo_dir(repo, "refs", "tags", mkdir=True)
    assert repo_dir(repo, "refs", "heads", mkdir=True)

    with open(repo_file(repo, "description"), "w") as f:
        f.write("Unnamed repository; edit this file 'description' to name the repository.\n")
    with open(repo_file(repo, "HEAD"), "w") as f:
        config = repo_default_config()
        config.write(f)
    
    return repo

def main(argv=sys.argv[1:]):
    args = argparse.parse_args(argv)
    match args.command:
        case "add"              : cmd_add(args)
        case "cat-file"         : cmd_cat_file(args)
        case "check-ignore"     : cmd_check_ignore(args)
        case "checkout"         : cmd_checkout(args)
        case "commit"           : cmd_commit(args)
        case "hash-object"      : cmd_hash_object(args)
        case "init"             : cmd_init(args)
        case "log"              : cmd_log(args)
        case "ls-files"         : cmd_ls_files(args)
        case "ls-tree"          : cmd_ls_tree(args)
        case "rev-parse"        : cmd_rev_parse(args)
        case "rm"               : cmd_rm(args)
        case "show-ref"         : cmd_show_ref(args)
        case "status"           : cmd_status(args)
        case "tag"              : cmd_tag(args)
        case _                  : print("Invalid Command!")
