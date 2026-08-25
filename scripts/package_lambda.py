#!/usr/bin/env python3
"""Build and verify the reproducible Lambda deployment archive."""

import argparse
import io
import os
import stat
import sys
import tempfile
import zipfile
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SOURCE = REPOSITORY_ROOT / "app" / "lambda" / "handler.py"
DEFAULT_ARCHIVE = REPOSITORY_ROOT / "app" / "lambda" / "package" / "lambda.zip"

MEMBER_NAME = "handler.py"
MEMBER_TIMESTAMP = (1980, 1, 1, 0, 0, 0)
MEMBER_MODE = stat.S_IFREG | 0o644
ZIP_VERSION = 20


class PackagingError(Exception):
    """Raised when the Lambda archive cannot be built or verified."""


def canonical_archive_bytes(source_bytes: bytes) -> bytes:
    """Return canonical ZIP bytes containing the supplied Lambda source."""
    member = zipfile.ZipInfo(MEMBER_NAME, date_time=MEMBER_TIMESTAMP)
    member.compress_type = zipfile.ZIP_STORED
    member.create_system = 3
    member.create_version = ZIP_VERSION
    member.extract_version = ZIP_VERSION
    member.flag_bits = 0
    member.internal_attr = 0
    member.external_attr = MEMBER_MODE << 16
    member.extra = b""
    member.comment = b""

    output = io.BytesIO()
    with zipfile.ZipFile(
        output,
        mode="w",
        compression=zipfile.ZIP_STORED,
        allowZip64=False,
    ) as archive:
        archive.comment = b""
        archive.writestr(member, source_bytes)

    return output.getvalue()


def _read_bytes(path: Path, description: str) -> bytes:
    try:
        return path.read_bytes()
    except OSError as exc:
        raise PackagingError(f"Unable to read {description} at {path}: {exc}") from exc


def validate_archive_bytes(archive_bytes: bytes, source_bytes: bytes) -> None:
    """Validate archive structure, contents, metadata, and canonical bytes."""
    try:
        with zipfile.ZipFile(io.BytesIO(archive_bytes), mode="r") as archive:
            members = archive.infolist()
            if len(members) != 1:
                raise PackagingError(
                    f"Archive must contain exactly one member; found {len(members)}"
                )

            member = members[0]
            if member.is_dir():
                raise PackagingError("Archive member must be a file, not a directory")
            if member.filename != MEMBER_NAME:
                raise PackagingError(
                    f"Archive member must be root-level {MEMBER_NAME}; "
                    f"found {member.filename}"
                )
            if member.date_time != MEMBER_TIMESTAMP:
                raise PackagingError("Archive member timestamp is not canonical")
            if member.compress_type != zipfile.ZIP_STORED:
                raise PackagingError("Archive member compression is not ZIP_STORED")
            if member.create_system != 3:
                raise PackagingError("Archive member creator system is not Unix")
            if member.create_version != ZIP_VERSION:
                raise PackagingError("Archive member creator version is not canonical")
            if member.extract_version != ZIP_VERSION:
                raise PackagingError("Archive member extraction version is not canonical")
            if member.flag_bits != 0:
                raise PackagingError("Archive member flags are not canonical")
            if member.internal_attr != 0:
                raise PackagingError("Archive member internal attributes are not canonical")
            if member.external_attr >> 16 != MEMBER_MODE:
                raise PackagingError("Archive member permissions are not 0644")
            if member.extra:
                raise PackagingError("Archive member extra data must be empty")
            if member.comment:
                raise PackagingError("Archive member comment must be empty")
            if archive.comment:
                raise PackagingError("Archive comment must be empty")

            archived_source = archive.read(member)
    except zipfile.BadZipFile as exc:
        raise PackagingError("Archive is not a valid ZIP file") from exc

    if archived_source != source_bytes:
        raise PackagingError("Archived handler.py does not match app/lambda/handler.py")

    expected_bytes = canonical_archive_bytes(source_bytes)
    if archive_bytes != expected_bytes:
        raise PackagingError("Archive bytes are not canonical and reproducible")


def check_archive(source_path: Path, archive_path: Path) -> None:
    """Verify an existing archive without writing to the filesystem."""
    source_bytes = _read_bytes(source_path, "Lambda source")
    archive_bytes = _read_bytes(archive_path, "Lambda archive")
    validate_archive_bytes(archive_bytes, source_bytes)


def build_archive(source_path: Path, archive_path: Path) -> None:
    """Create, validate, and atomically replace the Lambda archive."""
    source_bytes = _read_bytes(source_path, "Lambda source")
    archive_bytes = canonical_archive_bytes(source_bytes)
    validate_archive_bytes(archive_bytes, source_bytes)

    temporary_path = None
    try:
        file_descriptor, temporary_name = tempfile.mkstemp(
            dir=archive_path.parent,
            prefix=f".{archive_path.name}.",
            suffix=".tmp",
        )
        temporary_path = Path(temporary_name)
        with os.fdopen(file_descriptor, mode="wb") as temporary_file:
            temporary_file.write(archive_bytes)
            temporary_file.flush()
            os.fsync(temporary_file.fileno())

        validate_archive_bytes(temporary_path.read_bytes(), source_bytes)
        os.chmod(temporary_path, 0o644)
        os.replace(temporary_path, archive_path)
        temporary_path = None
    except (OSError, PackagingError) as exc:
        if temporary_path is not None:
            try:
                temporary_path.unlink(missing_ok=True)
            except OSError:
                pass
        if isinstance(exc, PackagingError):
            raise
        raise PackagingError(f"Unable to build Lambda archive: {exc}") from exc


def parse_args(argv=None):
    parser = argparse.ArgumentParser(
        description="Build or verify the reproducible Lambda deployment archive."
    )
    parser.add_argument("command", choices=("build", "check"))
    return parser.parse_args(argv)


def main(argv=None) -> int:
    args = parse_args(argv)
    try:
        if args.command == "build":
            build_archive(DEFAULT_SOURCE, DEFAULT_ARCHIVE)
            print(f"Built canonical Lambda archive: {DEFAULT_ARCHIVE}")
        else:
            check_archive(DEFAULT_SOURCE, DEFAULT_ARCHIVE)
            print(f"Lambda archive is canonical and synchronized: {DEFAULT_ARCHIVE}")
    except PackagingError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
