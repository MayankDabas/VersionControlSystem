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

argparse = argparse.ArgumentParser(description="Parse the commands needed by the program")
argsubparsers = argparse.add_subparsers(title="Command", dest="command")
argsubparsers.required = True
argsp = argsubparsers.add_parser("init", help="Initialize a new, empty repositoyr")
argsp.add_argument("path", metavar="directory", nargs="?", default=".", help="Where to create the repository.")

class GitRepository:
    """
    Represents a Git repository with its working directory and configuration.

    Attributes:
        worktree (str): The path to the working tree of the repository.
        gitdir (str): The path to the `.git` directory.
        config (ConfigParser): Configuration object for the repository.
    """

    def __init__(self, path, force=False):
        """
        Initializes a Git repository at the given path.

        Args:
            path (str): The file system path of the repository.
            force (bool): If True, force the initialization even if the repository is not properly configured.

        Raises:
            Exception: If the path is not a valid Git repository or the config file is missing/invalid.
        """
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
    """
    Constructs a path inside the `.git` directory.

    Args:
        repo (GitRepository): The repository object.
        path (str): Subpaths inside the repository.

    Returns:
        str: The constructed path.
    """
    return os.path.join(repo.gitdir, *path)

def repo_dir(repo, *path, mkdir=False):
    """
    Ensures that a directory exists inside the `.git` structure.

    Args:
        repo (GitRepository): The repository object.
        path (str): Subpaths inside the repository.
        mkdir (bool): If True, create the directory if it doesn't exist.

    Returns:
        str or None: The path to the directory, or None if it doesn't exist and mkdir is False.

    Raises:
        Exception: If the path exists but is not a directory.
    """
    path = repo_path(repo, *path)

    if os.path.exists(path):
        if os.path.isdir(path):
            return path
        else:
            raise Exception(f"Not a directory {path}")

    if mkdir:
        os.makedirs(path)
        return path
    else:
        return None

def repo_file(repo, *path, mkdir=False):
    """
    Constructs a file path inside the `.git` structure.

    Args:
        repo (GitRepository): The repository object.
        path (str): Subpaths inside the repository.
        mkdir (bool): If True, create necessary directories.

    Returns:
        str: The constructed file path.
    """
    if repo_dir(repo, *path[:-1], mkdir=mkdir):
        return repo_path(repo, *path)

def repo_default_config():
    """
    Creates a default configuration for a new repository.

    Returns:
        ConfigParser: A configuration object with default values for core settings.
    """
    ret = configparser.ConfigParser()

    ret.add_section("core")
    ret.set("core", "repositoryformatversion", "0")
    ret.set("core", "filemode", "false")
    ret.set("core", "bare", "false")

    return ret

def repo_create(path):
    """
    Creates a new Git repository at the given path.

    Args:
        path (str): The path where the repository will be created.

    Returns:
        GitRepository: The created repository object.

    Raises:
        Exception: If the path is not empty or not a directory.
    """
    repo = GitRepository(path, True)

    if os.path.exists(repo.worktree):
        if not os.path.isdir(repo.worktree):
            raise Exception(f"{path} is not a directory!")
        if os.path.exists(repo.gitdir) and os.listdir(repo.gitdir):
            raise Exception(f"{path} is not empty!")
    else:
        os.mkdirs(repo.worktree)

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

def repo_find(path=".", required=True):
    """
    Recursively searches for the root of a Git repository starting from the given path.

    This function looks for a `.git` directory to identify the root of the repository.
    It starts from the provided path (or the current directory by default) and moves up
    through parent directories until it finds a `.git` directory or reaches the root of 
    the filesystem. If no repository is found, it raises an exception or returns `None` 
    based on the `required` flag.

    Args:
        path (str): The starting directory for the search. Defaults to the current directory (".").
        required (bool): If True, raises an exception if no repository is found. 
                            If False, returns `None` when no repository is found. Defaults to True.

    Returns:
        GitRepository: A `GitRepository` object representing the found repository.
        None: If no repository is found and `required` is set to False.

    Raises:
        Exception: If no `.git` directory is found and `required` is True.

    Example:
        >>> repo = repo_find("/home/user/Documents/MyProject/src")
        >>> print(repo.worktree)
        /home/user/Documents/MyProject

    Explanation:
        Given a path within a project, this function ensures that Git commands will operate
        on the correct repository root, even if invoked from nested subdirectories.

    """
    path = os.path.realpath(path)

    if os.path.isdir(os.path.join(path, ".git")):
        return GitRepository(path)
    
    parent = os.path.realpath(os.path.join(path, ".."))

    if parent == path:
        if required:
            raise Exception("No git directory")
        else:
            return None
    
    return repo_find(parent, required)

def cmd_init(args):
    repo_create(args.path)

def main(argv=sys.argv[1:]):
    """
    Entry point of the program. Parses command-line arguments and calls the appropriate function.

    Args:
        argv (list): Command-line arguments passed to the program.
    """
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
