# File Fetcher

## Purpose

Many bioinformatics pipeline tasks rely on large data files, often pre-processed in such a way as to support fast 
lookups. To make libraries re-usable, it should be easy to create the files programmatically, and to download 
pre-made versions from a remote server. (rather than spending hours generating data structures on first install).

Additionally, it should be possible to get the newest versions based on some automated server process.  

This library abstracts the tasks of locating, downloading, or creating the necessary pieces, as appropriate. 


## Usage
```python
from filefetcher import AssetCLI, AssetManager
from filefetcher.exceptions import AssetAlreadyExists

# For routine use, instantiate a manager. It will locate cached copies of asset files. 
manager = AssetManager('mylib', 'https://downloader-server.example/mylib/')  # site hosts a manifest.json file
manager.locate('snp_to_rsid', genome_build='GRCh38')

# If the file has not yet been downloaded, it can be automatically fetched or built (from a known recipe)
manager.locate('snp_to_rsid', genome_build='GRCh38', auto_fetch=True, auto_build=True)

# Alternately, the asset can be manually fetched or built as a one-time operation during installation.
manager.download('snp_to_rsid', genome_build='GRCh38')
manager.build('snp_to_rsid', genome_build='GRCh38')

# The manager can build assets according to pre-defined recipes (a callable that accepts arguments).
def a_build_func(manager, item_type, temp_build_folder, **kwargs):
    # A build function has access to the manager (so it can check for existing files), and returns metadata calculated 
    #   during the build that will be stored as additional asset tags
    if manager.locate(item_type, auto_build=False, auto_fetch=False, **kwargs):
        # Raise a special exception class to interrupt the build without performing extra steps
        raise AssetAlreadyExists
    # ...do stuff that results in creating a file called filename.txt, and return extra metadata about the file version built
    return 'filename.txt', {'db_snp_build': 'b153'}

manager.add_recipe('snp_to_rsid', a_build_func, label='fast rsID lookups', genome_build='GRCh37')

# With an additional helper, your package can expose a CLI to handle these asset operations. 
#   (this is especially useful as a package entrypoint script, so that filefetcher provides a convenient install 
#   experience for your large data assets)
cli = AssetCLI(manager)
if __name__ == '__main__':
   cli.run()



```



## Development
Install dependencies + unit tests

`pip install -e .[test]`
