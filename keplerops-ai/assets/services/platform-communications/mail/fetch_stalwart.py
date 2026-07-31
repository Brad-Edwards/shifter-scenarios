"""Fetch and verify the Stalwart server binary during the image build."""

from __future__ import annotations

import gzip
import hashlib
from pathlib import Path
import shutil
import tarfile
import tempfile
import urllib.request


VERSION = "0.16.13"
ARCHIVE_SHA256 = "64a464e9aa7c40bd2af1d1be92bdf3343dd1e561c90bc7e04e43d429333f0472"
URL = (
    "https://github.com/stalwartlabs/stalwart/releases/download/"
    f"v{VERSION}/stalwart-x86_64-unknown-linux-gnu.tar.gz"
)


def main() -> None:
    output = Path("/opt/build/out")
    output.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as temporary_directory:
        archive = Path(temporary_directory) / "stalwart.tar.gz"
        digest = hashlib.sha256()
        with urllib.request.urlopen(URL, timeout=120) as response, archive.open(
            "wb"
        ) as destination:
            while chunk := response.read(1024 * 1024):
                digest.update(chunk)
                destination.write(chunk)
        if digest.hexdigest() != ARCHIVE_SHA256:
            raise RuntimeError("Stalwart server archive checksum mismatch")
        with gzip.open(archive) as compressed, tarfile.open(fileobj=compressed) as bundle:
            extracted = bundle.extractfile("stalwart")
            if extracted is None:
                raise RuntimeError("Stalwart server binary is absent from the archive")
            with (output / "stalwart").open("wb") as executable:
                shutil.copyfileobj(extracted, executable)
    (output / "stalwart").chmod(0o755)


if __name__ == "__main__":
    main()
