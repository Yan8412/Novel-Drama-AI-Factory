"""Synthetic staging fixtures only; no project files, credentials or network."""
import importlib.util
import os
from pathlib import Path
import stat
import subprocess
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch


SPEC = importlib.util.spec_from_file_location(
    "candidate_guard_staging", Path(__file__).resolve().parents[1] / "tools" / "guard_staging.py")
guard = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(guard)


class StagingGuardTest(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="candidate-guard-")
        self.addCleanup(self.temporary.cleanup)
        # macOS may expose its temporary directory through /var -> /private/var.
        # Build fixtures under the canonical root; the guard still rejects links.
        self.base = Path(self.temporary.name).resolve()
        self.root = self.base / "staging"
        self.root.mkdir()
        self.allowed = patch.object(guard, "ALLOWED", {Path("safe.txt")})
        self.allowed.start()
        self.addCleanup(self.allowed.stop)
        self.safe = self.root / "safe.txt"
        self.safe.write_text("synthetic safe text\n", encoding="utf-8")

    def assertBlocked(self, marker):
        errors = guard.verify(self.root)
        self.assertTrue(any(marker in item for item in errors), errors)
        return errors

    def test_normal_text_passes(self):
        self.assertEqual(guard.verify(self.root), [])

    def test_path_and_handle_ctime_semantics_may_differ(self):
        original = os.fstat

        def differing_ctime(fd):
            info = original(fd)
            fields = {name: getattr(info, name) for name in
                      ('st_dev', 'st_ino', 'st_mode', 'st_size', 'st_mtime_ns', 'st_ctime_ns')}
            fields['st_ctime_ns'] += 12345
            return SimpleNamespace(**fields)

        with patch.object(guard.os, "fstat", differing_ctime):
            self.assertEqual(guard.verify(self.root), [])

    def test_unicode_staging_root_passes(self):
        renamed = self.base / "合成-é"
        self.root.rename(renamed)
        self.assertEqual(guard.verify(renamed), [])

    def test_missing_file_blocked(self):
        self.safe.unlink()
        self.assertBlocked("MISSING_EXPECTED_FILE")

    def test_extra_file_blocked(self):
        (self.root / "extra.txt").write_text("synthetic", encoding="utf-8")
        self.assertBlocked("UNREVIEWED_PATH")

    def test_wrong_case_is_not_the_exact_allowlist_path(self):
        self.safe.rename(self.root / "SAFE.TXT")
        self.assertBlocked("UNREVIEWED_PATH")

    def test_case_collision_blocked(self):
        # A mocked directory listing covers case-sensitive and Windows hosts.
        with patch.object(guard.os, "walk", return_value=[
                (str(self.root), [], ["safe.txt", "SAFE.TXT"])]):
            self.assertBlocked("PATH_CASE_OR_NFC_COLLISION")

    def test_nfc_collision_blocked(self):
        first, second = "é.txt", "e\u0301.txt"
        (self.root / first).write_text("synthetic", encoding="utf-8")
        with patch.object(guard.os, "walk", return_value=[
                (str(self.root), [], ["safe.txt", first, second])]):
            self.assertBlocked("PATH_CASE_OR_NFC_COLLISION")

    def test_non_nfc_path_blocked(self):
        name = "e\u0301.txt"
        (self.root / name).write_text("synthetic", encoding="utf-8")
        with patch.object(guard, "ALLOWED", {Path("safe.txt"), Path(name)}):
            self.assertBlocked("NON_NFC_PATH")

    def test_non_utf8_blocked(self):
        self.safe.write_bytes(b"\xff")
        self.assertBlocked("NOT_UTF8_TEXT")

    def test_oversize_blocked_before_read(self):
        self.safe.write_bytes(b"x" * 512_001)
        with patch.object(guard, "_read_checked") as read:
            self.assertBlocked("OVERSIZE_TEXT")
            read.assert_not_called()

    def test_synthetic_secret_marker_blocked(self):
        # Deliberately constructed fixture, never a credential.
        self.safe.write_text("ghp_" + "x" * 35, encoding="utf-8")
        self.assertBlocked("POSSIBLE_SECRET")

    def test_file_symlink_blocked_before_read(self):
        target = self.base / "outside.txt"
        target.write_text("synthetic outside marker", encoding="utf-8")
        self.safe.unlink()
        try:
            self.safe.symlink_to(target)
        except OSError as exc:
            self.skipTest(f"Host cannot create file symlink: {type(exc).__name__}")
        with patch.object(guard, "_read_checked") as read:
            self.assertBlocked("LINK_OR_REPARSE_POINT")
            read.assert_not_called()

    def test_directory_symlink_blocked_without_traversal(self):
        target = self.base / "outside"
        target.mkdir()
        (target / "never-read.txt").write_text("synthetic", encoding="utf-8")
        link = self.root / "linked"
        try:
            link.symlink_to(target, target_is_directory=True)
        except OSError as exc:
            self.skipTest(f"Host cannot create directory symlink: {type(exc).__name__}")
        errors = self.assertBlocked("LINK_OR_REPARSE_POINT")
        self.assertFalse(any("never-read" in error for error in errors))

    @unittest.skipUnless(os.name == "nt", "Real Windows junction test")
    def test_windows_junction_blocked_without_traversal(self):
        target = self.base / "junction-target"
        target.mkdir()
        (target / "never-read.txt").write_text("synthetic", encoding="utf-8")
        link = self.root / "junction"
        self.assertTrue(target.resolve().is_relative_to(self.base.resolve()))
        self.assertEqual(link.parent, self.root)
        result = subprocess.run(["cmd.exe", "/d", "/c", "mklink", "/J", str(link), str(target)],
                                capture_output=True, timeout=10, check=False)
        if result.returncode:
            self.skipTest(f"Host cannot create junction: exit {result.returncode}")
        try:
            self.assertEqual(link.resolve(), target.resolve())
            errors = self.assertBlocked("LINK_OR_REPARSE_POINT")
            self.assertFalse(any("never-read" in error for error in errors))
        finally:
            # Remove only this verified junction entry, never recursively its target.
            self.assertEqual(link.resolve(), target.resolve())
            link.rmdir()
        self.assertTrue((target / "never-read.txt").is_file())

    def test_reparse_attribute_blocked_before_read(self):
        original = Path.lstat

        def attributes(path, *args, **kwargs):
            info = original(path, *args, **kwargs)
            if path == self.safe:
                class Reparse:
                    st_mode = info.st_mode
                    st_file_attributes = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
                return Reparse()
            return info

        with patch.object(Path, "lstat", attributes), patch.object(guard, "_read_checked") as read:
            self.assertBlocked("LINK_OR_REPARSE_POINT")
            read.assert_not_called()

    def test_resolved_escape_blocked_before_read(self):
        target = self.base / "outside.txt"
        target.write_text("synthetic", encoding="utf-8")
        original = Path.resolve

        def resolve(path, *args, **kwargs):
            return target if path == self.safe else original(path, *args, **kwargs)

        with patch.object(Path, "resolve", resolve), patch.object(guard, "_read_checked") as read:
            self.assertBlocked("UNSAFE_PATH")
            read.assert_not_called()

    def test_swap_between_inspection_and_open_blocked_before_data_read(self):
        alternate = self.base / "alternate.txt"
        alternate.write_text("synthetic alternate", encoding="utf-8")
        original = Path.open

        def open_swapped(path, *args, **kwargs):
            return original(alternate if path == self.safe else path, *args, **kwargs)

        with patch.object(Path, "open", open_swapped):
            self.assertBlocked("FILE_IDENTITY_CHANGED_BEFORE_READ")

    def test_write_during_read_blocked(self):
        original = os.fstat
        calls = 0

        def modify_after_read(fd):
            nonlocal calls
            calls += 1
            if calls == 2:
                with self.safe.open("ab") as stream:
                    stream.write(b"changed")
            return original(fd)

        with patch.object(guard.os, "fstat", modify_after_read):
            self.assertBlocked("FILE_IDENTITY_CHANGED_DURING_READ")

    def test_post_read_path_replacement_blocked(self):
        alternate = self.base / "alternate.txt"
        alternate.write_text("synthetic replacement", encoding="utf-8")
        original = guard._checked_path
        calls = 0

        def replace_before_postcheck(path, root):
            nonlocal calls
            if path == self.safe:
                calls += 1
                if calls == 2:
                    os.replace(alternate, self.safe)
            return original(path, root)

        with patch.object(guard, "_checked_path", replace_before_postcheck):
            self.assertBlocked("FILE_IDENTITY_CHANGED_AFTER_READ")

    def test_earlier_file_changed_after_its_read_is_blocked(self):
        later = self.root / "z-later.txt"
        later.write_text("synthetic later", encoding="utf-8")
        original = guard._read_checked

        def read_then_change_earlier(path, root, before):
            data = original(path, root, before)
            if path == later:
                self.safe.write_text("synthetic changed after its read", encoding="utf-8")
            return data

        with patch.object(guard, "ALLOWED", {Path("safe.txt"), Path("z-later.txt")}), \
                patch.object(guard, "_read_checked", read_then_change_earlier):
            self.assertBlocked("STAGING_CHANGED_DURING_SCAN")

    def test_new_file_added_after_listing_is_blocked(self):
        original = guard._read_checked

        def read_then_add(path, root, before):
            data = original(path, root, before)
            (root / "late.txt").write_text("synthetic addition", encoding="utf-8")
            return data

        with patch.object(guard, "_read_checked", read_then_add):
            self.assertBlocked("STAGING_CHANGED_DURING_SCAN")

    def test_late_entry_detected_with_unchanged_directory_metadata(self):
        original_read, original_stat = guard._read_checked, Path.lstat
        directory_before = self.root.lstat()

        def unchanged_directory_stat(path, *args, **kwargs):
            return directory_before if path == self.root else original_stat(path, *args, **kwargs)

        def read_then_add(path, root, before):
            data = original_read(path, root, before)
            (root / "late.txt").write_text("synthetic addition", encoding="utf-8")
            return data

        with patch.object(Path, "lstat", unchanged_directory_stat), \
                patch.object(guard, "_read_checked", read_then_add):
            self.assertBlocked("STAGING_CHANGED_DURING_SCAN")

    def test_unreadable_file_fails_closed(self):
        with patch.object(guard, "_read_checked", side_effect=PermissionError("synthetic")):
            self.assertBlocked("PermissionError")

    def test_walk_failure_fails_closed(self):
        def failed_walk(root, *, topdown, followlinks, onerror):
            onerror(PermissionError("synthetic"))
            return []

        with patch.object(guard.os, "walk", failed_walk):
            self.assertBlocked("STAGING_WALK_ERROR")


if __name__ == "__main__":
    unittest.main()
