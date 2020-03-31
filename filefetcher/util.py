import hashlib


def _get_file_sha256(src_path: str, block_size: int = 2 ** 20) -> str:
    with open(src_path, 'rb') as f:
        shasum_256 = hashlib.sha256()

        while True:
            data = f.read(block_size)
            if not data:
                break
            shasum_256.update(data)
        return shasum_256.hexdigest()
