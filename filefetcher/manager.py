"""
Manager class: responsible for finding, downloading, or building assets as appropriate
"""
import hashlib
import os
import re
import typing as ty
import urllib.request

from . import exceptions, manifest


class AssetManager:
    """Locate, download, or build assets as appropriate"""
    def __init__(self, name, remote_url, cache_dir=None, auto_fetch=False):
        user_path = '~/.assets/{}'.format(re.sub(r'[^\w\d-]','_', name))
        cache_dir = cache_dir or os.environ.get(name + '_ASSETS_DIR') or user_path
        self._cache_dir = cache_dir
        self._local = manifest.LocalManifest(cache_dir)

        # For most work, we will use a pre-cached copy of the remote manifest
        self._remote = manifest.LocalManifest(cache_dir, filename='manifest-remote.json')
        self._remote_url = remote_url
        # self._remote = manifest.RemoteManifest(remote_url)

        self._auto_fetch = auto_fetch

        # Ensure that the local asset directory exists for all future checks
        if not os.path.isdir(cache_dir):
            os.makedirs(cache_dir)

        # Load the manifest files into memory (creating if needed)
        self._local.load()
        self._remote.load()

        # Store information about any relevant build scripts that can are used to make manifest items
        self._recipes = []

    def locate(self, item_id, check_file=True, **kwargs):
        """Find an asset in the local store, and optionally, try to auto-download it"""
        try:
            data = self._local.locate(item_id, **kwargs)
            return self._local.get_path(data)
        except (exceptions.NoMatchingAsset, exceptions.ManifestNotFound) as e:
            if not self._auto_fetch:
                raise e


        # Try to auto-download
        self._remote.load()


        # At end of process,

    def _get_file_sha256(self, src_path: str, block_size: int = 2 ** 20) -> str:
        with open(src_path, 'rb') as f:
            shasum_256 = hashlib.sha256()

            while True:
                data = f.read(block_size)
                if not data:
                    break
                shasum_256.update(data)
            return shasum_256.hexdigest

    def add_file(self, source_path, sha256):
        dest = os.path.join(self._cache_dir, sha256)

    def download(self, item_id, check_file=False, **kwargs):
        """Fetch a file from the remote repository to the local cache directory, and update the local manifest"""
        remote_url = self._remote.locate(item_id, check_file=check_file, **kwargs)

        urllib.request.urlretrieve(remote_url, local_dest)

    def downloader(self, item_id: str, item_type=manifest.ItemType.item):
        # Will this be a CLI utility?
        pass

    def add_recipe(self, item_id, source: ty.Union[str, ty.Callable[..., dict]], *args, **kwargs):
        """
        Add a recipe for a single item. The source can be a filename (direct copy) or a callable
            that receives the provided args and kwargs, and returns a dict with any tags that should be written to
            the manifest
        """

