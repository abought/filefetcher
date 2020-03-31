"""
Manifest file class (local or remote)
"""
import abc
from datetime import datetime
import functools
import json
import logging
import operator
import os
import shutil
import typing as ty
import urllib.error
import urllib.parse
import urllib.request

from . import exceptions, util


logger = logging.getLogger(__name__)


SCHEMA_VERSION = 1


class ManifestBase(abc.ABC):
    """
    Track package manifests detailing what files are available
    """
    def __init__(self, base_path, *args, **kwargs):
        self._base_path = base_path
        self._path = ''  # type: str

        self._items = []  # type: ty.List[dict]
        self._collections = []  # type: ty.List[dict]

        self._loaded = False

    # Helper methods for working with manifest
    @functools.lru_cache()
    def locate(self, item_id, err_on_missing=True, **kwargs) -> ty.Optional[dict]:
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
        n_matches = len(matches)
        if not n_matches:
            if err_on_missing:
                raise exceptions.NoMatchingAsset
            else:
                return None

        logging.debug('Query for {} found {} matches', item_id, n_matches)

        match = sorted(matches, key=operator.itemgetter('date'), reverse=True)[0]
        return match

    @abc.abstractmethod
    def get_path(self, basename: ty.Union[str, dict]) -> str:
        """Get the path for a specific asset"""
        pass

    def add_record(self, item_id, *, source_path: str = None, label: str = None, date: ty.Optional[datetime] = None,
                   copy_file=False, move_file=False,
                   **kwargs):
        """
        Add an item record to the internal manifest (and optionally ensure that the file is in the manifest path
         in a systematic format of `sha_basename`)
        """
        if self.locate(item_id, err_on_missing=False, **kwargs):
            raise exceptions.ImmutableManifestError('Attempted to add a record that already exists. The specified tags may be ambiguous.')

        record = {
            'id': item_id,
            'label': label,
            **kwargs
        }

        if copy_file is True and move_file is True:
            raise exceptions.BaseAssetException('Move and copy are exclusive operations.')

        if copy_file or move_file:
            sha256 = util._get_file_sha256(source_path)
            date = datetime.utcfromtimestamp(os.path.getmtime(source_path))
            dest_fn = '{}_{}'.format(sha256, os.path.basename(source_path))
            copy_func = shutil.copy2 if copy_file else shutil.move
            copy_func(source_path, self.get_path(dest_fn))

            record['sha256'] = sha256
            record['path'] = dest_fn

        record['date'] = date or datetime.utcnow()
        self._items.append(record)
        return record

    # Reading contents to and from the datastore. Some methods may not be defined for all data types.
    def _parse(self, contents: dict):
        """Parse a JSON object and ensure that datestamps are serialized as dates"""
        self._items = contents['items']
        for item in self._items:
            item['date'] = datetime.fromisoformat(item['date'])
        self._collections = contents['collections']

    def _serialize(self) -> dict:
        return {
            'schema_version': SCHEMA_VERSION,
            'items': self._items,
            'collections': self._collections,
        }

    def save(self):
        """Some manifests (such as remote data) cannot and should not be written to"""
        raise exceptions.ImmutableManifestError

    def load(self, data: dict = None):
        """Load the contents of the manifest into memory"""
        if data is None:
            raise exceptions.ManifestNotFound

        self._parse(data)
        self._loaded = True


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

    def load(self, data=None):
        if self._loaded:
            return

        if data is None:
            try:
                with open(self._path, 'r') as f:
                    data = json.load(f)
            except FileNotFoundError:
                # Save an empty manifest as a starter, then load it
                self.save()
                return self.load()
            except IOError:
                raise exceptions.ManifestNotFound

        super(LocalManifest, self).load(data)

    def save(self):
        with open(self._path, 'w') as f:
            json.dump(self._serialize(), f)


class RemoteManifest(ManifestBase):
    """
    Track a list of all packages currently available for download, according to a remote server
    """
    def __init__(self, base_path, *args, filename='manifest.json', **kwargs):
        super(RemoteManifest, self).__init__(base_path, *args, filename=filename, **kwargs)
        self._path = self.get_path(filename)

    def get_path(self, basename):
        return urllib.parse.urljoin(self._base_path, basename)

    def load(self, data=None):
        """
        Download a manifest file from a remote URL
        """
        if self._loaded:
            return

        if data is None:
            try:
                with urllib.request.urlopen(self._path) as response:
                    body = response.read()
            except urllib.error.URLError:
                raise exceptions.ManifestNotFound

            text = body.decode(response.info().get_param('charset', 'utf-8'))
            data = json.loads(text)

        super(RemoteManifest, self).load(data)


class RecipeManifest(ManifestBase):
    """
    Track a list of recipes that can be used to build an asset class

    This is a helper that allows us to use the item and collections machinery on things that are not files
    All `items` in a recipe have an extra field (source)
    """
    # TODO: What should we do with BasePath? Perhaps a consistent build folder tmpdir?
    def load(self, data=None):
        # This manifest exists only in memory
        self._loaded = True

    def get_path(self, basename):
        raise NotImplementedError
