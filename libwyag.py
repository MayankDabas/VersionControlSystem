#------------------------------------------------------------------------------------------------#
#                                     Import Statements                                          #
#------------------------------------------------------------------------------------------------#
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

#------------------------------------------------------------------------------------------------#
#                                     Argument Parser                                            #
#------------------------------------------------------------------------------------------------#

argparse = argparse.ArgumentParser(description="Parse the commands needed by the program")
argsubparsers = argparse.add_subparsers(title="Command", dest="command")
argsubparsers.required = True

# argparser for init command
argsp = argsubparsers.add_parser("init", help="Initialize a new, empty repositoyr")
argsp.add_argument("path", metavar="directory", nargs="?", default=".", help="Where to create the repository.")

# argparser for cat-file command
argsp = argsubparsers.add_parser("cat-file", help="Provide content of repository objects")
argsp.add_argument("type", metavar="type", choices=["blob", "commit", "tag", "tree"], help="Specify the type")
argsp.add_argument("object", metavar="object", help="The object to display")

# argparser for hash-object command
argsp = argsubparsers.add_parser("hash-object", help="Compute object ID and optionally creates a blob from a file")
argsp.add_argument("-t", metavar="type", dest="type", choices=["blob", "commit", "tag", "tree"], default="blob", help="Specify the type")
argsp.add_argument("-w", dest="write", action="store_true", help="Write the object into the database")
argsp.add_argument("path", help="Read object from <file>")

#------------------------------------------------------------------------------------------------#
#                                     Classes                                                    #
#------------------------------------------------------------------------------------------------#

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

class GitObject(object):
    """
    A generic base class for Git objects, providing a template for serialization and deserialization.

    This class is meant to be subclassed by specific types of Git objects such as commits, blobs, 
    trees, and tags. It ensures that all Git objects implement the necessary methods to handle 
    data conversion between raw bytes and meaningful object formats.

    Subclasses must override the `serialize()` and `deserialize()` methods to provide specific 
    implementations. The `init()` method offers a default way to initialize an empty object, which 
    can be customized by subclasses if needed.

    Attributes:
        data (bytes): The raw byte data of the Git object (if provided during initialization).
    """

    def __init__(self, data=None):
        """
        Initializes the GitObject instance.

        If `data` is provided, the object will load its content using the `deserialize()` method.
        Otherwise, it will initialize an empty object by calling the `init()` method.

        Args:
            data (bytes, optional): The raw byte data used to load the object. Defaults to None.
        """
        if data != None:
            self.deserialize(data)
        else:
            self.init()
    
    def serialize(self, repo):
        """
        Converts the object's data into a serialized format.

        This method must be implemented by subclasses to define how the object 
        should be converted from its internal representation to a byte string.

        Args:
            repo: A reference to the repository object, which might be needed for serialization.

        Raises:
            Exception: If the method is not implemented in a subclass.
        """
        raise Exception("Unimplemented!")
    
    def deserialize(self, data):
        """
        Loads the object's data from a serialized byte string.

        This method must be implemented by subclasses to define how the byte string 
        data should be converted into the object's internal representation.

        Args:
            data (bytes): The raw byte data used to populate the object's attributes.

        Raises:
            Exception: If the method is not implemented in a subclass.
        """
        raise Exception("Unimplemented!")
    
    def init(self):
        """
        Initializes a new, empty object.

        This method provides a default behavior of doing nothing (`pass`), but can be overridden 
        by subclasses to define specific initialization logic (e.g., setting default values).
        """
        pass

class GitBlob(GitObject):
    """
    Represents a Git blob object, which stores the contents of a file.

    A Git blob is a binary large object that contains the raw data of a file in the repository.
    It does not store metadata such as filenames or directories, only the file content itself.
    This class provides methods to serialize and deserialize the blob data, inheriting common 
    behavior from the `GitObject` base class.

    Attributes:
        object_type (bytes): A byte string indicating the type of this object ('blob').
        blobdata (bytes): The raw binary content of the file stored in the blob.

    Methods:
        serialize(): Converts the blob object into a byte string for storage.
        deserialize(data): Loads the raw binary content into the blob object.
    """

    object_type = b'blob'

    def serialize(self):
        """
        Converts the blob object into a byte string.

        This method serializes the blob's data (stored in `self.blobdata`) into a byte string.
        The serialized form is used when storing the object in the Git repository.

        Returns:
            bytes: The raw binary content of the blob.
        """
        return self.blobdata
    
    def deserialize(self, data):
        """
        Loads the raw binary data into the blob object.

        This method populates the `blobdata` attribute with the given binary content.
        It is used when reading the object from the Git repository.

        Args:
            data (bytes): The raw binary content to be loaded into the blob.
        """
        self.blobdata = data

class GitCommit(GitObject):
    pass

class GitTag(GitObject):
    pass

class GitTree(GitObject):
    pass

#------------------------------------------------------------------------------------------------#
#                                     Methods                                                    #
#------------------------------------------------------------------------------------------------#

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

def object_read(repo, sha):
    """
    Reads a Git object from the repository and returns an instance of the appropriate object type.

    This function locates the compressed object file in the `.git/objects/` directory based on the 
    given SHA-1 hash. It decompresses the content, extracts the object type and size from the header, 
    and validates the object size. Depending on the type of the object (commit, tree, tag, or blob), 
    it creates and returns an instance of the corresponding class.

    Args:
        repo (GitRepository): The repository object from which the object is being read.
        sha (str): The 40-character SHA-1 hash of the object to be retrieved.

    Returns:
        GitObject: An instance of the corresponding Git object (e.g., GitCommit, GitTree, GitBlob).
        None: If the object file is not found.

    Raises:
        Exception: If the object type is unknown or the object size is malformed.

    Example:
        >> repo = GitRepository("/path/to/repo")
        >> sha = "e83c5163316f89bfbde7d9ab23ca2e25604af290"
        >> obj = object_read(repo, sha)
        >> print(type(obj))
        <class '__main__.GitCommit'>

    Explanation:
        1. The function constructs the file path for the given SHA-1 hash inside the `.git/objects/` directory.
        2. It decompresses the object file using `zlib`.
        3. It extracts the object type and size from the header.
        4. It validates the size of the object's content.
        5. Based on the object type, it instantiates and returns the corresponding Git object.
        6. If the object file is missing, it returns `None`.
        7. If the type is unrecognized or the size is malformed, it raises an exception.
    """
    path = repo_file(repo, "objects", sha[0:2], sha[2:])

    if not os.path.isfile(path):
        return None
    
    with open(path, "rb") as f:
        raw = zlib.decompress(f.read())

        x = raw.find(b' ')
        object_type = raw[0:x]

        y = raw.find(b'\x00', x)
        size = int(raw[x+1:y].decode("ascii"))
        if size != len(raw) - y - 1:
            raise Exception(f"Malformed object {sha}: bad length")
        
        match object_type:
            case b'commit'      : c=GitCommit
            case b'tree'        : c=GitTree
            case b'tag'         : c=GitTag
            case b'blob'        : c=GitBlob
            case _:
                raise Exception(f"Unknown type {object_type.decode("ascii")} for object {sha}")
        
        return c(raw[y + 1])

def object_write(obj, repo=None):
    """
    Serializes and writes a Git object to the repository, returning the object's SHA-1 hash.

    This function takes a Git object, serializes its data, and constructs the object in the format:
    `<object_type> <size>\x00<data>`. It then computes the SHA-1 hash of the object to uniquely 
    identify it. If a repository is provided, the object is saved to the appropriate location in 
    the `.git/objects/` directory, creating the necessary directories if needed. If the object 
    already exists, it will not be written again.

    Args:
        obj (GitObject): The Git object to be serialized and stored (e.g., GitCommit, GitBlob).
        repo (GitRepository, optional): The repository where the object should be saved. 
                                        Defaults to None (for cases where we only need the SHA).

    Returns:
        str: The SHA-1 hash of the serialized object, which acts as a unique identifier.

    Raises:
        Exception: If there are issues creating directories or writing the file.

    Example:
        >> blob = GitBlob(b"Hello, World!")
        >> repo = GitRepository("/path/to/repo")
        >> sha = object_write(blob, repo)
        >> print(sha)
        e69de29bb2d1d6434b8b29ae775ad8c2e48c5391

    Explanation:
        1. The object is serialized using the `serialize()` method of the Git object.
        2. The serialized data is formatted as: `<object_type> <size>\x00<data>`.
        3. A SHA-1 hash of the object is computed to act as its unique identifier.
        4. If a repository is provided:
            - The object is written to the `.git/objects/` directory in the appropriate subdirectory.
            - If necessary, directories are created.
            - If the object already exists, it is not overwritten.
        5. The function returns the computed SHA-1 hash.
    """
    data = obj.serialize()

    object_format = object_format.object_type + b' ' + str(len(data)).encode() + b'\x00' + data
    sha = hashlib.sha1(object_format).hexdigest()

    if repo:
        path = repo_file(repo, "objects", sha[0:2], sha[2:], mkdir=True)

        if not os.path.exists(path):
            with open(path, 'wb') as f:
                f.write(zlib.compress(object_format))
    
    return sha

def object_find(repo, name, object_type=None, follow=True):
    """
    Finds and returns the SHA-1 hash corresponding to the given object name.

    This function is intended to locate a Git object by its name, such as a branch name,
    tag, or partial SHA. It performs name resolution to map the input to the full SHA-1 hash
    of the corresponding Git object. Optional parameters allow filtering by object type and 
    whether to follow symbolic references (e.g., tags).

    Args:
        repo (GitRepository): The repository in which the object is searched.
        name (str): The name of the object (branch, tag, or SHA prefix) to resolve.
        object_type (str, optional): The expected type of the object (e.g., 'commit', 'tree').
                                     If provided, the function ensures the resolved object matches
                                     this type. Defaults to None.
        follow (bool, optional): If True, the function will follow symbolic references (e.g., tags). 
                                 Defaults to True.

    Returns:
        str: The resolved SHA-1 hash of the object.

    Example:
        >> repo = GitRepository("/path/to/repo")
        >> sha = object_find(repo, "HEAD")
        >> print(sha)  # Prints the SHA-1 hash for the current commit
    """
    return name

def cat_file(repo, obj, object_type=None):
    """
    Reads and prints the serialized content of a Git object to standard output.

    This function locates a Git object using the provided name or SHA, reads it from the
    repository, and writes its serialized content directly to `sys.stdout` in binary mode. 
    This mimics the behavior of the `git cat-file` command, which allows viewing the raw 
    contents of objects such as commits, trees, blobs, or tags.

    Args:
        repo (GitRepository): The repository from which to read the object.
        obj (str): The name or SHA-1 hash of the object to display.
        object_type (str, optional): The expected type of the object (e.g., 'blob', 'commit'). 
                                     Defaults to None.

    Raises:
        Exception: If the object cannot be found or the type is incorrect.

    Example:
        >> repo = GitRepository("/path/to/repo")
        >> cat_file(repo, "HEAD")
        # Prints the content of the current commit to stdout.
    """
    obj = object_read(repo, object_find(repo, obj, object_type=object_type))
    sys.stdout.buffer.write(obj.serialize())

def object_hash(file, object_type, repo=None):
    data = file.read()

    match object_type:
        case b'blob'    : obj = GitBlob(data)
        case b'commit'  : obj = GitCommit(data)
        case b'tag'     : obj = GitTag(data)
        case b'tree'    : obj = GitTree(data)
        case _          : raise Exception(f"Unknown type {object_type}")
    
    return object_write(obj, repo)

#------------------------------------------------------------------------------------------------#
#                                     Bridging Functions                                         #
#------------------------------------------------------------------------------------------------#

def cmd_init(args):
    repo_create(args.path)

def cmd_cat_file(args):
    repo = repo_find()
    cat_file(repo, args.object, object_type=args.type.encode())

def cmd_hash_object(args):
    if args.write:
        repo = repo_file()
    else:
        repo = None
    
    with open(args.path, "rb") as f:
        sha = object_hash(f, args.type.encode(), repo)
        print(sha)

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
