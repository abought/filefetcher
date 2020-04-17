"""
Helper function: given a manager instance, automatically build a CLI that can be exposed as a package script
"""
import argparse
from pprint import pprint as pp
import sys
import typing as ty

from . import exceptions, manager


class AssetCLI:
    def __init__(self, manager: manager.AssetManager):
        self._manager = manager

    def run(self):
        args = self._parse_args()
        args.func(args)

    def _parse_args(self):
        def add_common(subparser):
            group = subparser.add_mutually_exclusive_group()

            group.add_argument('--all', help='Apply this action for all assets in manifest', action='store_true')
            group.add_argument('--type', help='Apply this action for a specific record type', nargs=1)

            subparser.add_argument('--tag', nargs=2, action='append',
                                   help="Tag attributes with metadata for the desired item")

        parser = argparse.ArgumentParser(description="Manage and download assets for {}".format(self._manager.name))

        parser.add_argument('--local', nargs='?', default=None, help='Base path for the local cache directory')
        parser.add_argument('--remote', nargs='?', default=None, help='Base URL for downloading pre-built assets')
        # parser.add_argument('-y', '--yes', help='Automatic yes to prompts; run non-interactively')

        subparsers = parser.add_subparsers(dest='cmd', help='Several sub-commands are available')
        subparsers.required = True

        show_parser = subparsers.add_parser('show', help='Show information about assets in local cache')
        show_parser.add_argument('--available', default=False, action='store_true',
                                 help='Show assets available for download, rather than what is currently installed')
        add_common(show_parser)
        show_parser.set_defaults(func=self.show_command)

        # TODO (future) add an update feature?
        download_parser = subparsers.add_parser('download', help='Download the specified assets (pre-built)')
        add_common(download_parser)
        download_parser.set_defaults(func=self.download_command)
        download_parser.add_argument('--no-update', dest='no_update', default=False, action='store_true',
                                     help='Skip downloading of assets that already exist locally')

        build_parser = subparsers.add_parser('build', help='Build the specified assets from a recipe')
        add_common(build_parser)
        build_parser.set_defaults(func=self.build_command)
        return parser.parse_args()

    def _validate_common(self, args):
        single_item = args.type is not None
        if args.all and single_item:
            sys.exit('Options "--all" and "--type" are mutually exclusive')

        if not args.all and not single_item:
            sys.exit('Must specify asset using `--all` or `--type name --tag key1 value1 --tag key2 value2...`')

    def _set_manifests(self, args):
        if args.local:
            self._manager.set_local_manifest(args.local)

        if args.remote:
            self._manager.set_remote_manifest(args.remote)

    def _get_matching_records(self, args, manifest) -> ty.List[dict]:
        """Get one or more matching records"""
        if args.all:
            records = manifest._items  # type: ty.List[dict]
        else:
            tags = dict(args.tag or [])
            try:
                records = [manifest.locate(args.type[0], **tags)]
            except exceptions.NoMatchingAsset:
                records = []
        return records

    # Implement specific CLI subcommands
    def show_command(self, args):
        """
        Show full manifest information about currently available assets
        """
        self._validate_common(args)
        self._set_manifests(args)

        use_local = not args.available

        manifest = self._manager._local if use_local else self._manager._remote
        if not use_local:
            manifest.load()

        records = self._get_matching_records(args, manifest)
        print('- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -')

        print('Local manifest path: ', self._manager._local._manifest_path)
        print('Remote manifest path: ', self._manager._remote._manifest_path)

        if not len(records):
            sys.exit("No matching items found.")

        for record in records:
            print('- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -')
            pp(record)

    def download_command(self, args):
        """
        Download one or more assets from the specified remote location
        :param args:
        :return:
        """
        self._validate_common(args)
        self._set_manifests(args)

        manifest = self._manager._remote
        manifest.load()

        records = self._get_matching_records(args, manifest)

        if not len(records):
            sys.exit("No matching items found.")

        for record in records:
            try:
                self._manager.download(record['_type'], **record)
                print('Successfully downloaded file: {}'.format(record['_path']))
            except exceptions.ImmutableManifestError as e:
                if args.no_update:
                    print('Asset already exists; will not download: {}'.format(record['_path']))
                else:
                    raise e

        if len(records) > 1:
            print('All files successfully downloaded. Thank you.')

    def build_command(self, args):
        """
        Build one or more assets from the specified recipe
        """
        self._validate_common(args)
        self._set_manifests(args)

        manifest = self._manager._recipes

        records = self._get_matching_records(args, manifest)

        if not len(records):
            sys.exit("No matching items found.")

        for record in records:
            result = self._manager.build(record['_type'], **record)
            print('The requested asset has been built: {}'.format(result['_path']))

        if len(records) > 1:
            print('All files have been successfully built. Thank you.')
