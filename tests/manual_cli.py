#! /usr/bin/env python3

"""
A sample CLI app that can be used for manual testing

This is not run as part of pytest, but it allows manual verification of the basic commands, and demonstrates
    a realistic sample implementation of the filefetcher in a custom package.
"""
import os
import typing as ty

from filefetcher import AssetCLI, AssetManager, manager

SAMPLE_FILE = os.path.join(os.path.dirname(__file__), 'data', 'sample_manifest.json')

# This example is optimized for testing in a local environment, so we'll use a simple local server url
asset_manager = AssetManager('mypackage', 'http://127.0.0.1:8080/sample_manifest.json', local_manifest=SAMPLE_FILE)


class SampleRecipe(manager.BuildTask):
    def build(self, manager, item_type, build_folder, mytag=None, **kwargs) -> ty.Tuple[str, dict]:
        out_fn = os.path.join(build_folder, 'sample_file_{}.txt'.format(mytag))
        with open(out_fn, 'w') as f:
            f.write('I was built by the CLI')

        return out_fn, {'meta': 'built by CLI'}


if __name__ == '__main__':
    # Add some recipes that could be used to test the the "build --all" command.
    asset_manager.add_recipe('sample_file', SampleRecipe(), mytag="GRCh37",
                             label="Already tracked in the manifest, so build will be skipped")

    asset_manager.add_recipe(
        'sample_file', SampleRecipe(), mytag="GRCh38",
        label="Not tracked in the manifest, so it will be built. (be sure not to commit the change to the manifest!)"
    )

    cli = AssetCLI(asset_manager)
    cli.run()
