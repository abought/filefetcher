"""
Manager class: responsible for finding, downloading, or building assets as appropriate
"""
import abc
import functools
import logging
import os
import re
import tempfile
import typing as ty
import urllib.request

from . import exceptions, manifest, util


logger = logging.getLogger(__name__)


class BuildTask(abc.ABC):
    """A build task (recipe) can be any callable, but this provides machinery for some common operations"""
    def check_existing(self, manager, item_type, **kwargs):
        """
        Cancel build of this asset if it already exists

        This means that the build step can be run on a cron job regularly, incrementally building new files when source
            data is updated
        """
        try:
            # Cancel the build step if the asset already exists. This is not very ergonomic, but hey.
            manager.locate(item_type, auto_build=False, auto_fetch=False, **kwargs)
            logger.debug('Skipping build step for asset {} because asset already exists'.format(item_type))
            raise exceptions.AssetAlreadyExists
        except exceptions.NoMatchingAsset:
            return True

    @abc.abstractmethod
    def build(self, manager: 'AssetManager', item_type: str, build_folder: str, **kwargs) -> ty.Tuple[str, dict]:
        """Perform the actual build step, resulting in an output file and metadata"""
        pass

    def __call__(self, manager: 'AssetManager', item_type: str, build_folder: str, **kwargs) -> ty.Tuple[str, dict]:
        """
        Perform all operations required to build an asset (this class may be expanded in the future)

        :param manager: The manager instance that is performing the build. Can be used to check if assets already exist
        :param item_type: The type of asset (eg `snp_to_rsid`)
        :param build_folder: A temp folder that is automatically created during the build process for use by this
            build task. This folder and its contents will automatically be removed when the build completes; this may
            or may not be the desired behavior for you.
        :param kwargs: Custom tags that can be used to further define the asset (eg `genome_build`)
        :return:
        """
        self.check_existing(manager, item_type, **kwargs)
        return self.build(manager, item_type, build_folder, **kwargs)


class AssetManager:
    """Locate, download, or build assets as appropriate"""
    def __init__(self, library_name: str, remote_url: str, local_manifest: str = None, *,
                 auto_fetch: bool = False, auto_build: bool = False,
                 # Whether to autoload the local manifest (useful for testing to avoid blank files)
                 auto_load: bool = True):
        self.name = library_name

        if not local_manifest:
            # By default, package assets will be stored in `/<filefetcher_cache/mypackage`. The <filefetcher_cache>
            #   folder may be specified as an environment variable, OR a suggested default location.
            library_as_folder_name = re.sub(r'[^\w\d]', '_', library_name)
            env_var_override = '{}_ASSETS_DIR'.format(library_as_folder_name.upper())

            base_cache_dir = os.environ.get(env_var_override) or util.get_default_asset_dir()
            local_manifest = os.path.join(base_cache_dir, library_as_folder_name, 'manifest.json')

        package_cache_dir = os.path.dirname(local_manifest)

        # Identify places to fetch pre-build assets
        self._local = manifest.LocalManifest(local_manifest)
        self._remote = manifest.RemoteManifest(remote_url)

        # Store information about any relevant build scripts that can be used to make manifest items
        self._recipes = manifest.RecipeManifest(local_manifest)

        self._auto_fetch = auto_fetch
        self._auto_build = auto_build

        # Load the manifest files into memory (creating if needed)
        if auto_load:
            # Ensure that the local asset directory exists for all future checks
            if not os.path.isdir(package_cache_dir):
                os.makedirs(package_cache_dir)
            self._local.load()
        self._recipes.load()

    def set_local_manifest(self, manifest_path: str):
        """
        Change the manifest path used to track local assets. This is useful for, eg, CLI functionality
        """
        self._local = manifest.LocalManifest(manifest_path)
        self._local.load()
        self.locate.cache_clear()

    def set_remote_manifest(self, manifest_path: str):
        """
        Change the manifest path used to track remote assets. This is useful for, eg, CLI functionality
        We don't download the remote manifest until it is actually needed, but we do clear the cache.
        """
        self._remote = manifest.RemoteManifest(manifest_path)
        self.locate.cache_clear()

    # Methods to modify the collection of items in the manager
    def add_recipe(self,
                   item_type,
                   source: ty.Callable[['AssetManager', str,  str], ty.Tuple[str, dict]],
                   label: str = None,
                   **kwargs):
        """
        Add a recipe for a single item. The source can be a filename (direct copy) or a callable
            that receives the provided args and kwargs, and returns a dict with any tags that should be written to
            the manifest. (eg: "generic build command that can run on a schedule to get newest data releases")
        """
        self._recipes.add_record(item_type, label=label, _source=source, **kwargs)

    # Methods for retrieving an asset (precedence is local copy -> remote download -> build from scratch)
    @functools.lru_cache()
    def locate(self, item_type, auto_build=None, auto_fetch=None, **kwargs) -> str:
        """
        Find an asset in the local store, and optionally, try to auto-download it

        Return the (local) path to the asset at the end of this process
        """
        # Auto build can be overridden for specific method calls. This is useful to avoid infinite loops when checking
        # "asset already exists" during build.
        auto_build = auto_build if auto_build is not None else self._auto_build
        auto_fetch = auto_fetch if auto_fetch is not None else self._auto_fetch

        try:
            data = self._local.locate(item_type, **kwargs)
            return self._local.get_path(data)
        except (exceptions.NoMatchingAsset, exceptions.ManifestNotFound) as e:
            if not auto_fetch and not auto_build:
                raise e

        if auto_fetch:
            # If auto-fetch is active, try to auto-download the newest and best possible match
            try:
                data = self.download(item_type, **kwargs)
                logger.debug('Automatically downloaded asset from remote: {}'.format(item_type))
                return self._local.get_path(data)
            except exceptions.BaseAssetException as e:
                if not auto_build:
                    raise e

        if auto_build:
            # If auto-build is active, and all other options have failed, try to build the asset
            logger.debug('Automatically built asset from recipe: {}'.format(item_type))
            data = self.build(item_type, **kwargs)
            return self._local.get_path(data)

        raise exceptions.NoMatchingAsset

    def download(self, item_type, save=True, **kwargs) -> dict:
        """Fetch a file from the remote repository to the local cache directory, and update the local manifest"""
        self._remote.load()  # Load manifest (if not already loaded)
        remote_record = self._remote.locate(item_type, **kwargs)
        url = self._remote.get_path(remote_record)
        dest = self._local.get_path(remote_record)

        urllib.request.urlretrieve(url, dest)

        # Validate that sha256 of the downloaded file matches the record
        sha = remote_record['_sha256']
        if not os.path.isfile(dest) or util.get_file_sha256(dest) != sha:
            raise exceptions.IntegrityError

        # Since we are downloading directly to the cache dir, we don't need to move or copy the file, and the remote
        #   manifest has already provided us with the appropriate metadata info
        local_record = self._local.add_record(item_type, source_path=dest, **remote_record)
        if save:
            # Can turn off auto-save if downloading a batch of records at once
            self._local.save()
        return local_record

    def build(self, item_type, save=True, **kwargs) -> dict:
        """
        Build a specified asset. This is a very crude build system and is not intended to handle nested
            dependencies, multi-file builds, etc. It is assumed the function can operate completely from within
            a temp folder and that that folder can be cleaned up when done.
        """
        recipe = self._recipes.locate(item_type, **kwargs)
        recipe_func = recipe['_source']

        # When building "all recipes", the source (a function) might get passed as a kwarg. Remove it from the
        #   list of "custom tags"- it's a "system-defined key" and not part of the metadata that goes in the manifest
        kwargs.pop('_source', None)

        with tempfile.TemporaryDirectory() as tmpdirname:
            # All build steps are automatically given a temporary working folder that will be cleaned up when done
            try:
                # TODO: Currently we do not provide a mechanism to force rebuild, except to manually edit the local
                #   registry to remove the record
                out_fn, build_meta = recipe_func(self, item_type, tmpdirname, **kwargs)
            except exceptions.AssetAlreadyExists:
                # The recipe function can raise "asset already exists" to interrupt the build step.
                # This will fail if the manifest does not find such a matching asset present locally
                return self._local.locate(item_type, **kwargs)

            if not os.path.isfile(out_fn):
                raise exceptions.IntegrityError

            # The build is described by the options we pass in (like "genome_build"), and also by any other metadata
            #   calculated during the process (eg "db_snp_newest_version")
            build_description = {**kwargs, **build_meta}
            local_record = self._local.add_record(item_type, source_path=out_fn, move_file=True, **build_description)

        if save:
            # Can turn off auto-save if downloading a batch of records at once
            self._local.save()
        return local_record
