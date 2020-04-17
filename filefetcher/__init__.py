from distutils.version import LooseVersion

__version__ = '0.1.1'
__version_info__ = tuple(LooseVersion(__version__).version)

from .cli import AssetCLI  # noqa
from .manager import AssetManager  # noqa
