"""Fetch and verify the Stalwart management CLI during the image build."""

from __future__ import annotations

import hashlib
import lzma
from pathlib import Path
import shutil
import tarfile
import tempfile
import urllib.request


VERSION = "1.0.10"
ARCHIVE_SHA256 = "31fc35b95a4ed82d5618cea60298ddcdfbb308c252c4ce7e9dde8a7e89fc655d"
URL = (
    "https://github.com/stalwartlabs/cli/releases/download/"
    f"v{VERSION}/stalwart-cli-x86_64-unknown-linux-gnu.tar.xz"
)


def main() -> None:
    output = Path("/opt/build/out")
    output.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as temporary_directory:
        archive = Path(temporary_directory) / "stalwart-cli.tar.xz"
        digest = hashlib.sha256()
        with urllib.request.urlopen(URL, timeout=120) as response, archive.open("wb") as destination:
            while chunk := response.read(1024 * 1024):
                digest.update(chunk)
                destination.write(chunk)
        if digest.hexdigest() != ARCHIVE_SHA256:
            raise RuntimeError("Stalwart CLI archive checksum mismatch")
        with lzma.open(archive) as compressed, tarfile.open(fileobj=compressed) as bundle:
            member = bundle.getmember(
                "stalwart-cli-x86_64-unknown-linux-gnu/stalwart-cli"
            )
            extracted = bundle.extractfile(member)
            if extracted is None:
                raise RuntimeError("Stalwart CLI binary is absent from the archive")
            with (output / "stalwart-cli").open("wb") as executable:
                shutil.copyfileobj(extracted, executable)
    (output / "stalwart-cli").chmod(0o755)


if __name__ == "__main__":
    main()
