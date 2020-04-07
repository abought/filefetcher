"""
Shared unit test fixtures
"""
import pytest

from filefetcher import manifest


@pytest.fixture
def local_manifest(tmpdir):
    fixture = manifest.LocalManifest(tmpdir / 'manifest.json')
    fixture.load(data={
        'items': [
            {
                '_type': 'snp_to_rsid',
                '_label': 'RSID annotations',
                '_date': '2019-08-08',
                '_sha256': 'iamthenewest',
                '_path': 'iamthenewest_snp_to_rsid.lmdb',
                '_size': 1000,
                'genome_build': 'GRCh37',
                'db_snp_build': 'b153',
            },
            {
                '_type': 'snp_to_rsid',
                '_label': 'RSID annotations',
                '_date': '2018-01-01',
                '_sha256': 'notthenewest',
                '_path': 'notthenewest_snp_to_rsid.lmdb',
                '_size': 750,
                'genome_build': 'GRCh37',
                'db_snp_build': 'b152',
            }
        ],
        'collections': []  # Reserved for future features
    })
    return fixture
