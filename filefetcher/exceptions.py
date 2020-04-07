"""
Exceptions for asset manager
"""


class BaseAssetException(Exception):
    DEFAULT_MESSAGE = ''  # type: str

    def __init__(self, message=None, *args):
        super(BaseAssetException, self).__init__(*args)
        self.message = message or self.DEFAULT_MESSAGE

    def __str__(self):
        return str(self.message)


class ManifestNotFound(BaseAssetException):
    DEFAULT_MESSAGE = "Manifest could not be located in the specified location"


class ImmutableManifestError(BaseAssetException):
    DEFAULT_MESSAGE = 'Cannot mutate an immutable manifest'


class NoMatchingAsset(BaseAssetException):
    DEFAULT_MESSAGE = 'No asset could be found that matched the tags provided'


class AssetNotFound(BaseAssetException):
    DEFAULT_MESSAGE = 'Could not locate the specified asset file. Please download or generate it before continuing.'


class IntegrityError(BaseAssetException):
    DEFAULT_MESSAGE = 'Could not validate file integrity hash. ' \
                      'Check whether the file is corrupt or the manifest file is out of date.'


class AssetAlreadyExists(BaseAssetException):
    DEFAULT_MESSAGE = 'You already have the newest version of the requested asset'
