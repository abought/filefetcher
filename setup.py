import os
from setuptools import setup, find_packages

here = os.path.abspath(os.path.dirname(__file__))

# Get the long description from the README file
with open(os.path.join(here, 'README.md'), encoding='utf-8') as f:
    long_description = f.read()


setup(
    name='filefetcher',
    version='0.1.1',
    packages=find_packages(exclude=['docs', 'tests', 'venv']),
    url='https://github.com/abought/filefetcher',
    license='',
    author='abought',
    author_email='abought@umich.edu',
    classifiers=[  # Optional
        # How mature is this project? Common values are
        #   3 - Alpha
        #   4 - Beta
        #   5 - Production/Stable
        'Development Status :: 3 - Alpha',

        'Intended Audience :: Developers',
        'License :: OSI Approved :: MIT License',

        'Programming Language :: Python :: 3.5',
        'Programming Language :: Python :: 3.6',
        'Programming Language :: Python :: 3.8',
    ],

    description='Find, download, and build versioned assets',
    long_description=long_description,
    long_description_content_type='text/markdown',  # Optional (see note above)
    python_requires='>=3.5',
    # install_requires=[],
    extras_require={  # Optional
        'test': ['coverage', 'pytest', 'pytest-flake8'],
    },

    project_urls={  # Optional
        'Bug Reports': 'https://github.com/abought/filefetcher/issues',
        'Source': 'https://github.com/abought/filefetcher/',
    },
)
