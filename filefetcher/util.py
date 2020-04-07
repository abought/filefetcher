import hashlib
import os
import stat
import sys

from .exceptions import BaseAssetException


def get_file_sha256(src_path: str, block_size: int = 2 ** 20) -> str:
    """Calculate the (hex string) hash for a large file"""
    with open(src_path, 'rb') as f:
        shasum_256 = hashlib.sha256()

        while True:
            data = f.read(block_size)
            if not data:
                break
            shasum_256.update(data)
        return shasum_256.hexdigest()


def is_writable(path):
    """
    Determine whether a specific directory is writable
    From NLTK: https://github.com/nltk/nltk/blob/d13078e0441cd46f46b41a9db70dbde0ffacd4fe/nltk/internals.py"""
    # Ensure that it exists.
    if not os.path.exists(path):
        return False

    # If we're on a posix system, check its permissions.
    if hasattr(os, "getuid"):
        statdata = os.stat(path)
        perm = stat.S_IMODE(statdata.st_mode)
        # is it world-writable?
        if perm & 0o002:
            return True
        # do we own it?
        elif statdata.st_uid == os.getuid() and (perm & 0o200):
            return True
        # are we in a group that can write to it?
        elif (statdata.st_gid in [os.getgid()] + os.getgroups()) and (perm & 0o020):
            return True
        # otherwise, we can't write to it.
        else:
            return False

    # Otherwise, we'll assume it's writable.
    # [xx] should we do other checks on other platforms?
    return True


def get_default_asset_dir() -> str:
    """
    Find the parent directory in which all assets managed by "filefetcher" instances are stored. It must be writable
        and as broadly scoped as feasible. (eg prefer system directories over one user's home path)

    This function is only used if no explicit path is provided.

    Note that this is not the same thing as the folder for a particular package: each package is a subdirectory of
        the centrally managed asset collection
    ( `/<filefetcher_cache>/mypackage/` )

    The order of search options is as follows, in descending order of priority:
    - Library or application data paths
    - Python install location (or the virtualenv root)
    - User-specific directories

    Adapted from NLTK:
    https://github.com/nltk/nltk/blob/develop/nltk/data.py#L74
    """
    possible_locations = [
        os.path.join(sys.prefix, "share"),
        os.path.join(sys.prefix, "lib"),
    ]
    # User-specified locations:

    if sys.platform.startswith("win"):
        # Common locations on Windows:
        possible_locations += [
            os.path.join(os.environ.get("APPDATA", "C:\\")),
            r"C:\\",
            r"D:\\",
            r"E:\\",
        ]
    else:
        # Common locations on UNIX & OS X:
        possible_locations += [
            "/usr/share/",
            "/usr/local/share/",
            "/usr/lib/",
            "/usr/local/lib/",
        ]

    # Python install location (or virtualenv root folder)
    possible_locations.append(sys.prefix)

    if os.path.expanduser("~/") != "~/":
        # The user must have a home directory ("if expansion fails, expanduser returns the string unchanged")
        # This package is intended to support really large files shared among multiple services (or even a web app)-
        #   as such, installing in the user folder is a last resort (it would lead to a lot of duplication)
        possible_locations.append(os.path.expanduser("~/"))

    for location in possible_locations:
        if os.path.exists(location) and is_writable(location):
            return os.path.join(location, '.assets')

    raise BaseAssetException('Could not choose a default asset cache root directory; exiting')
