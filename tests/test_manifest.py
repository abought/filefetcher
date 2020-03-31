"""
Test manifest functionality
"""
import os

import pytest

from filefetcher import exceptions, manifest

@pytest.fixture
def local_manifest(tmpdir):
    fixture = manifest.LocalManifest(tmpdir)
    fixture._parse({
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
        'collections': []
    })
    return fixture


def test_locates_newest_fixture_with_specified_tags(local_manifest):
    data = local_manifest.locate('rsid_lookup', genome_build='GRCh37')
    assert data['sha256'] == 'iamthenewest'


def test_locates_fixture_with_most_specific_match_for_tags(local_manifest):
    data = local_manifest.locate('rsid_lookup', genome_build='GRCh37', db_snp_build='b152')
    assert data['sha256'] == 'notthenewest'


def test_errors_when_no_fixtures_match_tags(local_manifest):
    with pytest.raises(exceptions.NoMatchingAsset):
        local_manifest.locate('rsid_lookup', genome_build='nonexistent')
