"""
Test manifest functionality
"""
from datetime import datetime
import os

import pytest

from filefetcher import exceptions, manifest


SAMPLE_FILE = os.path.join(os.path.dirname(__file__), 'data', 'sample_file.txt')


# Instance creation and data loading
def test_loader_can_use_specified_data(tmpdir):
    local = manifest.LocalManifest(tmpdir / 'manifest.json')
    assert local._loaded is False

    local.load(data={'items': [], 'collections': [1, 2, 3]})
    assert len(local._collections) == 3


def test_loader_can_create_empty_manifest(tmpdir):
    local = manifest.LocalManifest(tmpdir / 'manifest.json')
    local.load()
    assert os.path.exists(local._manifest_path)


# Locate: finds specified records
def test_locates_newest_fixture_with_specified_tags(local_manifest):
    data = local_manifest.locate('snp_to_rsid', genome_build='GRCh37')
    assert data['_sha256'] == 'iamthenewest'


def test_locates_fixture_with_most_specific_match_for_tags(local_manifest):
    data = local_manifest.locate('snp_to_rsid', genome_build='GRCh37', db_snp_build='b152')
    assert data['_sha256'] == 'notthenewest'


def test_errors_when_no_fixtures_match_tags(local_manifest):
    with pytest.raises(exceptions.NoMatchingAsset):
        local_manifest.locate('snp_to_rsid', genome_build='nonexistent')


# add_record
def test_adds_record_metadata_from_arguments(local_manifest):
    label = 'Added during test'
    date = datetime.fromisoformat('2020-01-01').isoformat()
    local_manifest.add_record('flubber', label=label, my_tag='avalue', date=date)
    found = local_manifest.locate('flubber')
    assert found['_label'] == label
    assert found['my_tag'] == 'avalue'
    assert found['_date'] == date


def test_add_record_fails_when_exists(local_manifest):
    with pytest.raises(exceptions.ImmutableManifestError):
        local_manifest.add_record('snp_to_rsid')


def test_adds_file_to_directory_with_sha_and_versioned_path(local_manifest):
    local_manifest.add_record('my_file', my_tag='avalue', source_path=SAMPLE_FILE, copy_file=True)
    found = local_manifest.locate('my_file')
    assert found['my_tag'] == 'avalue'
    assert found['_sha256'] == 'c87e2ca771bab6024c269b933389d2a92d4941c848c52f155b9b84e1f109fe35'
    assert found['_path'] == 'c87e2ca771bab6024c269b933389d2a92d4941c848c52f155b9b84e1f109fe35_sample_file.txt'


def test_mutually_exclusive_options_are_validated(local_manifest):
    with pytest.raises(exceptions.BaseAssetException):
        local_manifest.add_record('my_file', my_tag='avalue', source_path=SAMPLE_FILE, move_file=True, copy_file=True)


# Special manifest behaviors
def test_some_manifests_are_immutable(tmpdir):
    remote = manifest.RemoteManifest('https://site.example/assets/manifest.json')
    recipe = manifest.RecipeManifest(tmpdir)

    with pytest.raises(exceptions.ImmutableManifestError):
        remote.save()

    with pytest.raises(exceptions.ImmutableManifestError):
        recipe.save()
