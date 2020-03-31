"""
Test manifest functionality
"""
from datetime import datetime
import os

import pytest

from filefetcher import exceptions, manifest


SAMPLE_FILE = os.path.join(os.path.dirname(__file__), 'data', 'sample_file.txt')


@pytest.fixture
def local_manifest(tmpdir):
    fixture = manifest.LocalManifest(tmpdir)
    fixture.load(data={
        'items': [
            {
                'id': 'rsid_lookup',
                'label': 'RSID annotations',
                'date': '2019-08-08',
                'sha256': 'iamthenewest',
                'path': 'rsid_lookup_iamthenewest.lmdb',
                'genome_build': 'GRCh37',
                'db_snp_build': 'b153',
            },
            {
                'id': 'rsid_lookup',
                'label': 'RSID annotations',
                'date': '2018-01-01',
                'sha256': 'notthenewest',
                'path': 'rsid_lookup_notthenewest.lmdb',
                'genome_build': 'GRCh37',
                'db_snp_build': 'b152',
            }
        ],
        'collections': []  # Reserved for future features
    })
    return fixture


# Instance creation and data loading
def test_loader_can_use_specified_data(tmpdir):
    local = manifest.LocalManifest(tmpdir)
    assert local._loaded is False

    local.load(data={'items': [], 'collections': [1, 2, 3]})
    assert len(local._collections) == 3


def test_loader_can_create_empty_manifest(tmpdir):
    local = manifest.LocalManifest(tmpdir)
    local.load()
    assert os.path.exists(local._path)


# Locate: finds specified records
def test_locates_newest_fixture_with_specified_tags(local_manifest):
    data = local_manifest.locate('rsid_lookup', genome_build='GRCh37')
    assert data['sha256'] == 'iamthenewest'


def test_locates_fixture_with_most_specific_match_for_tags(local_manifest):
    data = local_manifest.locate('rsid_lookup', genome_build='GRCh37', db_snp_build='b152')
    assert data['sha256'] == 'notthenewest'


def test_errors_when_no_fixtures_match_tags(local_manifest):
    with pytest.raises(exceptions.NoMatchingAsset):
        local_manifest.locate('rsid_lookup', genome_build='nonexistent')


# add_record
def test_adds_record_metadata_from_arguments(tmpdir, local_manifest):
    label = 'Added during test'
    date = datetime.fromisoformat('2020-01-01')
    local_manifest.add_record('flubber', label=label, my_tag='avalue', date=date)
    found = local_manifest.locate('flubber')
    assert found['label'] == label
    assert found['my_tag'] == 'avalue'
    assert found['date'] == date


def test_add_record_fails_when_exists(local_manifest):
    with pytest.raises(exceptions.ImmutableManifestError):
        local_manifest.add_record('rsid_lookup')


def test_adds_file_to_directory_with_sha_and_versioned_path(local_manifest):
    local_manifest.add_record('my_file', my_tag='avalue', source_path=SAMPLE_FILE, copy_file=True)
    found = local_manifest.locate('my_file')
    assert found['my_tag'] == 'avalue'
    assert found['sha256'] == 'c87e2ca771bab6024c269b933389d2a92d4941c848c52f155b9b84e1f109fe35'
    assert found['path'] == 'c87e2ca771bab6024c269b933389d2a92d4941c848c52f155b9b84e1f109fe35_sample_file.txt'


def test_mutually_exclusive_options_are_validated(local_manifest):
    with pytest.raises(exceptions.BaseAssetException):
        local_manifest.add_record('my_file', my_tag='avalue', source_path=SAMPLE_FILE, move_file=True, copy_file=True)


# Special manifest behaviors
def test_some_manifests_are_immutable(tmpdir):
    remote = manifest.RemoteManifest('https://site.example/assets')
    recipe = manifest.RecipeManifest(tmpdir)

    with pytest.raises(exceptions.ImmutableManifestError):
        remote.save()

    with pytest.raises(exceptions.ImmutableManifestError):
        recipe.save()
