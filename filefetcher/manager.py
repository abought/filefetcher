"""
Manager class: responsible for finding, downloading, or building assets as appropriate
"""
import os
import re
import typing as ty
import urllib.request

from . import exceptions, manifest, util


# class AssetCLI:
#     def __init__(self, manager):
#         self._manager = manager  # type: AssetManager
#
#     def parse_args(self):
#         def add_common(subparser):
#             group = subparser.add_mutually_exclusive_group()
#
#             group.add_argument('--all', help='Apply this action for all assets in manifest', action='store_true')
#             group.add_argument('--id', help='Apply this action for a specific record ID', action='store_true')
#
#             subparser.add_argument('--tag', nargs=2, action='append',
#                                    help="Tag attributes with metadata for the desired item")
#
#         parser = argparse.ArgumentParser(description="Manage and download assets for {}".format(self._manager.name))
#         # FIXME: currently CLI injects a manager class instance; how can we make local/remote configurable in this pattern?
#         parser.add_argument('--local', help='Base path for the local cache directory')
#         parser.add_argument('--remote', help='Base URL for downloading pre-built assets')
#         parser.add_argument('-y', help='Automatic yes to prompts; run non-interactively')
#
#         subparsers = parser.add_subparsers(dest='cmd', help='Several sub-commands are available')
#
#         show_parser = subparsers.add_parser('show', help='Show information about assets in local cache')
#         add_common(show_parser)
#         show_parser.set_defaults(func=self.show_command)
#
#         download_parser = subparsers.add_parser('download', help='Download the specified assets (pre-built)')
#         add_common(download_parser)
#         download_parser.set_defaults(func=self.download_command)
#
#         build_parser = subparsers.add_parser('build', help='Build the specified assets from a recipe')
#         add_common(build_parser)
#         build_parser.set_defaults(func=self.build_command)
#
#
#     def _validate_common(self, args):
#         n_tags = len(args.tags)
#         if args.all and n_tags:
#             sys.exit('Options "--all" and "--tags" are mutually exclusive')
#
#         if not args.all and not n_tags:
#             sys.exit('Must specify at least one asset')
#
#
#     # TODO: Can we use show/download/build as 'func'? Does it receive a reference to self already?
#     def show_command(self, args):
#         # TODO: Implement
#         self._validate_common(args)
#
#         if args.all:
#             records = self._manager._local._items
#         else:
#             tags = dict(args.tags)
#             records = [self._manager.locate(args.id, **item) for item in tags]
#
#         # TODO: Most of these CLI features will be nicer to use once "collections" have been implemented
#
#     def download_command(self, args):
#         # TODO: Implement
#         self._validate_common(args)
#
#     def build_command(self, args):
#         # TODO: implement
#         self._validate_common(args)


class AssetManager:
    """Locate, download, or build assets as appropriate"""
    def __init__(self, name, remote_url, cache_dir=None, auto_fetch=False, auto_build=False):
        user_path = '~/.assets/{}'.format(re.sub(r'[^\w\d-]','_', name))
        cache_dir = cache_dir or os.environ.get(name + '_ASSETS_DIR') or user_path
        self._cache_dir = cache_dir

        # Identify places to fetch pre-build assets
        self._local = manifest.LocalManifest(cache_dir)
        self._remote = manifest.RemoteManifest(remote_url)

        # Store information about any relevant build scripts that can be used to make manifest items
        self._recipes = manifest.RecipeManifest(cache_dir)

        self._auto_fetch = auto_fetch
        self._auto_build = auto_build

        # Ensure that the local asset directory exists for all future checks
        if not os.path.isdir(cache_dir):
            os.makedirs(cache_dir)

        # Load the manifest files into memory (creating if needed)
        self._local.load()

    def locate(self, item_id, **kwargs) -> str:
        """
        Find an asset in the local store, and optionally, try to auto-download it

        Return the (local) path to the asset at the end of this process
        """
        try:
            data = self._local.locate(item_id, **kwargs)
            return self._local.get_path(data)
        except (exceptions.NoMatchingAsset, exceptions.ManifestNotFound) as e:
            if not self._auto_fetch or self._auto_build:
                raise e

        if self._auto_fetch:
            # If auto-fetch is active, try to auto-download the newest and best possible match
            try:
                data = self.download(item_id, **kwargs)
                return self._local.get_path(data)
            except exceptions.BaseAssetException as e:
                if not self._auto_build:
                    raise e

        if self._auto_build:
            # If auto-build is active, and all other options have failed, try to build the asset
            data = self.build(item_id, **kwargs)
            return self._local.get_path(data)

    def download(self, item_id, save=True, **kwargs) -> dict:
        """Fetch a file from the remote repository to the local cache directory, and update the local manifest"""
        self._remote.load()  # Load manifest (if not already loaded)
        remote_record = self._remote.locate(item_id, **kwargs)
        url = self._remote.get_path(remote_record)
        dest = self._local.get_path(remote_record)

        urllib.request.urlretrieve(url, dest)

        # Validate that sha256 of the downloaded file matches the record
        sha = remote_record['sha256']
        if not (os.path.isfile(dest) and util._get_file_sha256(dest) != sha):
            raise exceptions.IntegrityError

        local_record = self._local.add_record(item_id, source_path=dest, **remote_record)
        if save:
            # Can turn off auto-save if downloading a batch of records at once
            self._local.save()
        return local_record

    # Methods that build assets from scratch
    def add_recipe(self,
                   item_id,
                   source: ty.Callable[['AssetManager', str], ty.Tuple[str, dict]],
                   label: str = None,
                   **kwargs):
        """
        Add a recipe for a single item. The source can be a filename (direct copy) or a callable
            that receives the provided args and kwargs, and returns a dict with any tags that should be written to
            the manifest. (eg: "generic build command that can run on a schedule to get newest data releases")
        """
        self._recipes.add_record(item_id, label=label, check_file=False, source=source, **kwargs)

    def build(self, item_id, save=True, **kwargs):
        """
        Build a specified asset. This is a very crude build system and is not intended to handle nested
            dependencies, multi-file builds, etc. It is assumed the function can operate completely from within
            a temp folder and that that folder can be cleaned up when done.
        """
        recipe = self._recipes.locate(item_id, **kwargs)
        recipe_func = recipe['source']
        try:
            out_fn, build_meta = recipe_func(self, item_id, **kwargs)
        except exceptions.AssetAlreadyExists:
            # The recipe function can raise "asset already exists" to interrupt the build step. It has access to the
            #   manager object to see what files already exist. A very abusable feature.
            # This will fail if the manifest does not find such a matching asset present locally
            return self._local.locate(item_id, **kwargs)

        if not os.path.isfile(out_fn):
            raise exceptions.IntegrityError

        # The build is described by the options we pass in (like "genome_build"), and also by any other metadata
        #   calculated during the process (eg "db_snp_newest_version")
        build_description = {**kwargs, **build_meta}
        local_record = self._local.add_record(item_id, source_path=out_fn, move_file=True, **build_description)
        if save:
            # Can turn off auto-save if downloading a batch of records at once
            self._local.save()
        return local_record
