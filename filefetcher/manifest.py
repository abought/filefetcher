"""
Manifest file class (local or remote)
"""
import abc
from datetime import datetime
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
# A list of manifest entries that have meaning for the system, but should not be used when searching for a matching item
# By convention, most of these have the prefix `_`
SYSTEM_TAGS = frozenset(['_type', '_label', '_date', '_sha256', '_path', '_size', '_source'])


class ManifestBase(abc.ABC):
    """
    Track package manifests detailing what files are available
    """
    def __init__(self, manifest_path, *args, **kwargs):
        # A manifest file defines the root folder in which to find assets. All assets described in the manifest will
        #   live at a path relative to this manifest
        self._base_path = os.path.dirname(manifest_path)  # type: str
        self._manifest_path = manifest_path  # type: str

        self._items = []  # type: ty.List[dict]
        self._collections = []  # type: ty.List[dict]

        self._loaded = False  # type: bool

    # Helper methods for working with manifest
    def locate(self, item_type, err_on_missing=True, **kwargs) -> ty.Optional[dict]:
        """
        Find the (newest) manifest item that corresponds to the specified asset type + all additional
            tags (specified as kwargs)

        Eg, locate('snp_to_rsid', genome_build='GRCh38')
        """
        if not self._loaded:
            raise exceptions.ManifestNotFound('Manifest must be loaded before using')

        # Find every record for which the item ID and all user-provided tags describing the record are an exact match
        #  (but do not consider "system tags" like "filesize", which do not part of how we label items)
        matches = [
            item for item in self._items
            if item['_type'] == item_type and all(
                key in item and item[key] == value
                for key, value in kwargs.items()
                if key not in SYSTEM_TAGS
            )
        ]
        n_matches = len(matches)
        if not n_matches:
            if err_on_missing:
                raise exceptions.NoMatchingAsset
            else:
                return None

        logging.debug('Query for {} found {} matches', item_type, n_matches)

        match = sorted(matches, key=operator.itemgetter('_date'), reverse=True)[0]
        return match

    @abc.abstractmethod
    def get_path(self, basename: ty.Union[str, dict]) -> str:
        """Get the path of an asset (relative to the manifest location)"""
        pass

    def add_record(self, item_type, *, source_path: str = None, label: str = None, date: ty.Optional[str] = None,
                   copy_file=False, move_file=False,
                   **kwargs):
        """
        Add an item record to the internal manifest (and optionally ensure that the file is in the manifest path
         in a systematic format of `sha_basename`)
        """
        if self.locate(item_type, err_on_missing=False, **kwargs):
            raise exceptions.ImmutableManifestError('Attempted to add a record that already exists. '
                                                    'The specified tags may be ambiguous.')

        record = {
            '_type': item_type,
            '_label': label,
            **kwargs
        }

        if copy_file is True and move_file is True:
            raise exceptions.BaseAssetException('Move and copy are exclusive operations.')

        if copy_file or move_file:
            # Move the file to the cached asset folder, and track some extra metadata in the manifest
            sha256 = util.get_file_sha256(source_path)
            date = datetime.utcfromtimestamp(os.path.getmtime(source_path)).isoformat()
            size = os.path.getsize(source_path)
            dest_fn = '{}_{}'.format(sha256, os.path.basename(source_path))
            copy_func = shutil.copy2 if copy_file else shutil.move
            copy_func(source_path, self.get_path(dest_fn))  # type: ignore

            record['_path'] = dest_fn
            record['_sha256'] = sha256
            record['_size'] = size

        record['_date'] = date or datetime.utcnow().isoformat()
        self._items.append(record)
        return record

    # Reading contents to and from the datastore. Some methods may not be defined for all data types.
    def _parse(self, contents: dict):
        """Parse a JSON object"""
        self._items = contents['items']
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

    def get_path(self, basename):
        """Get the path for a file record"""
        if isinstance(basename, dict):
            basename = basename['_path']
        return os.path.join(self._base_path, basename)

    def load(self, data=None):
        if self._loaded:
            return

        if data is None:
            try:
                with open(self._manifest_path, 'r') as f:
                    data = json.load(f)
            except FileNotFoundError:
                # Save an empty manifest as a starter, then load it
                self.save()
                return self.load()
            except IOError:
                raise exceptions.ManifestNotFound

        super(LocalManifest, self).load(data)

    def save(self):
        with open(self._manifest_path, 'w') as f:
            json.dump(
                self._serialize(),
                f,
                indent=2,
                sort_keys=True
            )


class RemoteManifest(ManifestBase):
    """
    Track a list of all packages currently available for download, according to a remote server
    """

    def __init__(self, base_path, *args, filename='manifest.json', **kwargs):
        super(RemoteManifest, self).__init__(base_path, *args, filename=filename, **kwargs)

    def get_path(self, basename):
        if isinstance(basename, dict):
            basename = basename['_path']
        return urllib.parse.urljoin(self._base_path, basename)

    def load(self, data=None):
        """
        Download a manifest file from a remote URL
        """
        if self._loaded:
            return

        if data is None:
            try:
                with urllib.request.urlopen(self._manifest_path) as response:
                    body = response.read()  # type: bytes
            except urllib.error.URLError:
                raise exceptions.ManifestNotFound

            text = body.decode(response.info().get_param('charset', 'utf-8'))  # type: ignore
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
