import os
from setuptools import setup, find_packages

here = os.path.abspath(os.path.dirname(__file__))

# Get the long description from the README file
with open(os.path.join(here, 'README.md'), encoding='utf-8') as f:
    long_description = f.read()


setup(
    name='filefetcher',
    version='0.1.0',
    packages=find_packages(exclude=['docs', 'tests']),
    url='',
    license='',
    author='abought',
    author_email='abought@umich.edu',
    description='Find, download, and build versioned assets',
    long_description=long_description,
    long_description_content_type='text/markdown',  # Optional (see note above)
    python_requires='>=3.5',
    # install_requires=[],
    extras_require={  # Optional
        'test': ['coverage', 'pytest', 'pytest-flake8'],
    },
)
