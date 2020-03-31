"""
Manifest file class (local or remote)
"""
from datetime import datetime
import enum
import functools
import json
import operator
import os
import typing as ty
import urllib.error
import urllib.parse
import urllib.request

from . import exceptions


class ItemType(enum.Enum):
    item = 1
    collection = 2


class ManifestBase:
    """
    Track package manifests detailing what files are available
    """
    def __init__(self, base_path, *args, **kwargs):
        self._base_path = base_path
        self._path = ''  # type: str

        self._items = []  # type: ty.List[dict]
        self._collections = []  # type: ty.List[dict]

    # Helper methods for working with manifest
    @functools.lru_cache()
    def locate(self, item_id, **kwargs) -> dict:
        """
        Find the (newest) manifest item that corresponds to the specified ID + all additional tags (specified as kwargs)

        Eg, locate('rsid_lookup', genome_build='GRCh38')
        """
        matches = [
            item for item in self._items
            if item['id'] == item_id
               and all(key in item and item[key] == value
                       for key, value in kwargs.items())
        ]
        if not len(matches):
            raise exceptions.NoMatchingAsset

        match = sorted(matches, key=operator.itemgetter('date'), reverse=True)[0]
        return match

    def get_path(self, basename: ty.Union[str, dict]) -> str:
        """Get the path for a specific asset"""
        raise NotImplementedError

    def add_record(self, item_id, sha256, label=None, date=None, check_file=True, **kwargs):
        """Add an item record to the internal manifest (and optionally verify that the item exists)"""
        filename = os.path.join(self._base_path, sha256)
        if check_file and not os.path.isfile(filename):
            raise exceptions.AssetNotFound

        # FIXME: Check if the existing item/metadata set already exists? (eg all other tags except data and SHA are a match)
        date = date or datetime.utcnow()
        self._items.append({
            'id': item_id,
            'sha256': sha256,
            'label': label,
            'date': date,
            **kwargs
        })

    def add_file(self, source_path, sha256):
        """Add a file to the asset directory, under the specified name. Validate the SHA256"""
        raise NotImplementedError

    def gather_items(self, collection_id, label, **kwargs):
        """Make a collection of items: group anything with matching tags, only newest version of each"""
        # TODO: Check if collection exists
        raise NotImplementedError

    def prune_items(self, item_id=None, max_count=10, delete=False):
        """Prune a manifest: as new dataset builds are released, prune/cleanup older ones"""
        raise NotImplementedError

    # Reading contents to and from the datastore. Some methods may not be defined for all data types.
    def _parse(self, contents: dict):
        """Parse a JSON object and ensure that datestamps are serialized as dates"""
        self._items = contents['items']
        for item in self._items:
            item['date'] = datetime.fromisoformat(item['date'])
        self._collections = contents['collections']

    def _serialize(self) -> dict:
        return {
            'items': self._items,
            'collections': self._collections,
        }

    def save(self):
        contents = self._serialize()
        with open(self._path, 'w') as f:
            json.dump(contents, f)

    def load(self):
        """Load the contents of the manifest into memory"""
        raise NotImplementedError



class RemoteManifest(ManifestBase):
    """
    Track a list of all packages currently available for download, according to a remote server
    """
    def __init__(self, base_path, *args, filename='manifest.json', **kwargs):
        super(RemoteManifest, self).__init__(base_path, *args, filename=filename, **kwargs)
        self._path = self.get_path(filename)

    def get_path(self, basename):
        return urllib.parse.urljoin(self._base_path, basename)

    def save(self):
        """We cannot and should not attempt to overwrite the remote manifest file"""
        raise NotImplementedError

    def load(self):
        """
        Download a manifest file from a remote URL
        """
        try:
            with urllib.request.urlopen(self._path) as response:
                data = response.read()
        except urllib.error.URLError:
            raise exceptions.ManifestNotFound

        text = data.decode(response.info().get_param('charset', 'utf-8'))
        self._parse(json.loads(text))


class LocalManifest(ManifestBase):
    """
    Track a list of all packages that exist locally (eg have been created or downloaded at any time)
    """
    def __init__(self, base_path, *args, filename='manifest.json', **kwargs):
        super(LocalManifest, self).__init__(base_path, *args, filename=filename, **kwargs)
        self._path = self.get_path(filename)

    def get_path(self, basename):
        """Get the path for a file record"""
        if isinstance(basename, dict):
            basename = basename['path']
        return os.path.join(self._base_path, basename)

    def load(self):
        try:
            with open(self._path, 'r') as f:
                contents = json.load(f)
        except FileNotFoundError:
            # Save an empty manifest as a starter
            self.save()
        except IOError:
            raise exceptions.ManifestNotFound
        self._parse(contents)

    def save(self):
        with open(self._path, 'w') as f:
            json.dump(self._serialize(), f)
