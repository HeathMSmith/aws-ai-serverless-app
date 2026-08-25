import io
import stat
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

from scripts import package_lambda


class LambdaPackagingTests(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary_directory.cleanup)
        self.root = Path(self.temporary_directory.name)
        self.source = self.root / "handler.py"
        self.archive = self.root / "lambda.zip"
        self.source_bytes = b"def lambda_handler(event, context):\n    return event\n"
        self.source.write_bytes(self.source_bytes)

    def write_zip(self, members, *, timestamp=(2026, 1, 1, 0, 0, 0)):
        with zipfile.ZipFile(self.archive, mode="w") as archive:
            for name, contents in members:
                member = zipfile.ZipInfo(name, date_time=timestamp)
                archive.writestr(member, contents)

    def assert_check_rejects(self, expected_message):
        with self.assertRaisesRegex(package_lambda.PackagingError, expected_message):
            package_lambda.check_archive(self.source, self.archive)

    def test_identical_source_produces_identical_archive_bytes(self):
        first = package_lambda.canonical_archive_bytes(self.source_bytes)
        second = package_lambda.canonical_archive_bytes(self.source_bytes)

        self.assertEqual(first, second)

    def test_canonical_archive_has_normalized_layout_and_metadata(self):
        archive_bytes = package_lambda.canonical_archive_bytes(self.source_bytes)

        with zipfile.ZipFile(io.BytesIO(archive_bytes), mode="r") as archive:
            self.assertEqual(archive.comment, b"")
            self.assertEqual(len(archive.infolist()), 1)
            member = archive.infolist()[0]
            self.assertEqual(member.filename, "handler.py")
            self.assertFalse(member.is_dir())
            self.assertEqual(member.date_time, (1980, 1, 1, 0, 0, 0))
            self.assertEqual(member.compress_type, zipfile.ZIP_STORED)
            self.assertEqual(member.create_system, 3)
            self.assertEqual(member.external_attr >> 16, stat.S_IFREG | 0o644)
            self.assertEqual(member.extra, b"")
            self.assertEqual(member.comment, b"")
            self.assertEqual(archive.read(member), self.source_bytes)

    def test_check_accepts_synchronized_canonical_archive(self):
        self.archive.write_bytes(
            package_lambda.canonical_archive_bytes(self.source_bytes)
        )

        package_lambda.check_archive(self.source, self.archive)

    def test_check_rejects_missing_member(self):
        self.write_zip([])

        self.assert_check_rejects("exactly one member; found 0")

    def test_check_rejects_extra_member(self):
        self.write_zip(
            [("handler.py", self.source_bytes), ("extra.txt", b"unexpected")]
        )

        self.assert_check_rejects("exactly one member; found 2")

    def test_check_rejects_nested_member(self):
        self.write_zip([("app/lambda/handler.py", self.source_bytes)])

        self.assert_check_rejects("must be root-level handler.py")

    def test_check_rejects_stale_source(self):
        self.archive.write_bytes(
            package_lambda.canonical_archive_bytes(b"old source\n")
        )

        self.assert_check_rejects("does not match app/lambda/handler.py")

    def test_check_rejects_noncanonical_member_metadata(self):
        self.write_zip([("handler.py", self.source_bytes)])

        self.assert_check_rejects("timestamp is not canonical")

    def test_failed_build_preserves_destination_and_removes_temporary_file(self):
        original_archive = b"existing archive"
        self.archive.write_bytes(original_archive)

        with patch.object(
            package_lambda.os,
            "replace",
            side_effect=OSError("simulated replacement failure"),
        ):
            with self.assertRaisesRegex(
                package_lambda.PackagingError, "simulated replacement failure"
            ):
                package_lambda.build_archive(self.source, self.archive)

        self.assertEqual(self.archive.read_bytes(), original_archive)
        self.assertEqual(
            {path.name for path in self.root.iterdir()},
            {"handler.py", "lambda.zip"},
        )

    def test_successful_build_replaces_stale_destination(self):
        self.archive.write_bytes(b"stale archive")

        package_lambda.build_archive(self.source, self.archive)

        self.assertEqual(
            self.archive.read_bytes(),
            package_lambda.canonical_archive_bytes(self.source_bytes),
        )
        package_lambda.check_archive(self.source, self.archive)


if __name__ == "__main__":
    unittest.main()
