"""Cross-platform tests; only temporary instruction files are modified."""

import contextlib
import importlib.util
import io
import json
import os
from pathlib import Path, PureWindowsPath
import shutil
import stat
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "skills" / "ai-apf" / "SKILL.md"
SCRIPT = SKILL.parent / "scripts" / "configure_plan_entry.py"
SPEC = importlib.util.spec_from_file_location("configure_plan_entry", SCRIPT)
ENTRY = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(ENTRY)
BOM = b"\xef\xbb\xbf"


class PlanEntryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="apf-entry-")
        self.directory = Path(self.temp.name).resolve() / "Test 研究 空间"
        self.directory.mkdir()
        self.target = self.directory / "AGENTS.md"

    def tearDown(self):
        self.temp.cleanup()

    def call(self, command, *extra, target=None, skill=SKILL, expected=0, env=None):
        target = self.target if target is None else target
        args = [sys.executable, str(SCRIPT), command, "--agents-file", str(target)]
        if command == "enable":
            args += ["--skill-file", str(skill)]
        result = subprocess.run(args + list(extra), capture_output=True, encoding="utf-8", env=env)
        self.assertEqual(result.returncode, expected, result.stderr)
        return json.loads(result.stdout if expected == 0 else result.stderr)

    def test_status_and_dry_run_do_not_create_files_or_parent(self):
        target = self.directory / "missing" / "AGENTS.md"
        self.assertEqual(self.call("status", target=target)["entry"], "absent")
        self.assertTrue(self.call("enable", "--dry-run", target=target)["would_change"])
        self.assertFalse(target.parent.exists())
        self.assertEqual(list(self.directory.iterdir()), [])

    def test_enable_backup_idempotence_and_disable_preserve_later_edits(self):
        before = "用户原有指令\n保留。\n".encode("utf-8")
        self.target.write_bytes(before)
        first = self.call("enable")
        self.assertTrue(first["changed"])
        self.assertEqual(Path(first["backup_file"]).read_bytes(), before)
        once = self.target.read_bytes()
        self.assertTrue(once.endswith(before))
        self.assertEqual(once.count(ENTRY.BEGIN.encode()), 1)
        self.assertFalse(self.call("enable")["changed"])
        self.assertEqual(self.target.read_bytes(), once)
        self.assertEqual(len(list(self.directory.glob("*.ai-apf.bak.*"))), 1)
        later = "后来新增的用户指令\n".encode("utf-8")
        with self.target.open("ab") as stream:
            stream.write(later)
        removed = self.call("disable")
        self.assertEqual(Path(removed["backup_file"]).read_bytes(), once + later)
        self.assertEqual(self.target.read_bytes(), before + later)
        self.assertFalse(self.call("disable")["changed"])

    def test_line_endings_and_bom_round_trip(self):
        for prefix in (b"", BOM):
            for newline in (b"\n", b"\r\n"):
                with self.subTest(bom=bool(prefix), newline=newline):
                    before = prefix + b"Original" + newline + "保留".encode("utf-8") + newline
                    self.target.write_bytes(before)
                    self.call("enable")
                    enabled = self.target.read_bytes()
                    self.assertTrue(enabled.startswith(prefix + ENTRY.BEGIN.encode()))
                    self.assertEqual(enabled.count(BOM), int(bool(prefix)))
                    if newline == b"\r\n":
                        self.assertNotIn(b"\n", enabled.replace(b"\r\n", b""))
                    self.call("disable")
                    self.assertEqual(self.target.read_bytes(), before)

    def test_unicode_space_skill_path_is_directly_usable(self):
        copied = self.directory / "技能 with spaces" / "SKILL.md"
        copied.parent.mkdir()
        shutil.copy2(SKILL, copied)
        preview = self.call("enable", "--dry-run", skill=copied)
        line = preview["managed_block"].splitlines()[4]
        rendered = json.loads(line)
        self.assertEqual(rendered, copied.resolve().as_posix())
        self.assertTrue(Path(rendered).is_file())
        if os.name == "nt":
            self.assertNotIn("\\", rendered)
        self.call("enable", skill=copied)
        self.assertIn(line, self.target.read_text(encoding="utf-8"))

    def test_windows_drive_and_unc_are_unescaped_and_human_readable(self):
        for skill in (PureWindowsPath("C:/Users/名 字/ai-apf/SKILL.md"),
                      PureWindowsPath("//server/share/名 字/ai-apf/SKILL.md")):
            line = ENTRY.make_block(skill, "\n").splitlines()[4]
            self.assertEqual(json.loads(line), skill.as_posix())
            self.assertNotIn("\\\\", line)

    def test_ascii_output_encoding_does_not_fail_on_unicode_paths(self):
        env = os.environ.copy()
        env["PYTHONIOENCODING"] = "ascii"
        result = self.call("enable", "--dry-run", env=env)
        self.assertIn("研究", result["agents_file"])
        self.assertFalse(self.target.exists())

    def test_existing_override_is_detected_and_can_be_selected(self):
        self.target.write_bytes(b"ordinary\n")
        override = self.directory / "AGENTS.override.md"
        override.write_bytes(b"effective\n")
        self.assertIn("shadowed", self.call("enable", expected=2)["error"])
        self.assertEqual(self.target.read_bytes(), b"ordinary\n")
        self.assertTrue(self.call("enable", target=override)["changed"])
        self.call("disable", target=override)
        self.assertEqual(override.read_bytes(), b"effective\n")

    def test_new_override_cannot_hide_existing_rules(self):
        self.target.write_bytes(b"important\n")
        override = self.directory / "AGENTS.override.md"
        self.assertIn("hide", self.call("enable", target=override, expected=2)["error"])
        self.assertFalse(override.exists())
        self.assertEqual(self.target.read_bytes(), b"important\n")

    def test_malformed_markers_and_invalid_utf8_are_rejected(self):
        for before in (b"<!-- ai-apf:begin -->\nmissing end\n",
                       b"<!-- ai-apf:begin -->\n<!-- ai-apf:end -->\n"
                       b"<!-- ai-apf:begin -->\n<!-- ai-apf:end -->\n",
                       b"invalid\xffutf8"):
            with self.subTest(before=before):
                self.target.write_bytes(before)
                self.assertEqual(self.call("enable", expected=2)["state"], "blocked")
                self.assertEqual(self.target.read_bytes(), before)
                self.assertEqual(list(self.directory.glob("*.ai-apf.bak.*")), [])

    def test_non_skill_and_missing_skill_rejected(self):
        wrong = self.directory / "SKILL.md"
        wrong.write_bytes(b"---\nname: other\n---\nbody\n")
        self.assertIn("name: ai-apf", self.call("enable", skill=wrong, expected=2)["error"])
        self.assertEqual(self.call("enable", skill=self.directory / "missing", expected=2)["state"], "blocked")
        self.assertFalse(self.target.exists())

    def test_symlink_is_rejected_when_creation_permitted(self):
        actual = self.directory / "original.txt"
        actual.write_bytes(b"preserve\n")
        try:
            self.target.symlink_to(actual)
        except (OSError, NotImplementedError) as exc:
            self.skipTest("Creating a symlink requires platform permission: " + str(exc))
        self.assertIn("symlink", self.call("enable", expected=2)["error"])
        self.assertEqual(actual.read_bytes(), b"preserve\n")

    @unittest.skipUnless(os.name == "nt", "Native Windows junction test")
    def test_windows_junction_parent_is_rejected(self):
        actual = self.directory / "actual"
        actual.mkdir()
        (actual / "AGENTS.md").write_bytes(b"preserve\n")
        junction = self.directory / "junction"
        run = subprocess.run(["cmd", "/c", "mklink", "/J", str(junction), str(actual)],
                             capture_output=True)
        if run.returncode:
            self.skipTest("Unable to create a test junction on this host")
        result = self.call("enable", target=junction / "AGENTS.md", expected=2)
        self.assertIn("reparse", result["error"])
        self.assertEqual((actual / "AGENTS.md").read_bytes(), b"preserve\n")

    def test_windows_reparse_attribute_is_recognized_without_pathlib_support(self):
        details = SimpleNamespace(st_mode=stat.S_IFDIR, st_file_attributes=0x400)
        with mock.patch.object(ENTRY.os, "name", "nt"), mock.patch.object(Path, "lstat", return_value=details):
            self.assertTrue(ENTRY.is_link_or_reparse(self.target))

    def test_windows_write_branch_never_requires_fchmod(self):
        before = b"existing\n"
        self.target.write_bytes(before)
        with mock.patch.object(ENTRY.os, "name", "nt"), \
                mock.patch.object(ENTRY.os, "fchmod", create=True) as fchmod:
            backup = ENTRY.write_change(self.target, before, b"new\n" + before)
        fchmod.assert_not_called()
        self.assertEqual(self.target.read_bytes(), b"new\n" + before)
        self.assertEqual(backup.read_bytes(), before)

    def test_failed_replace_reports_blocked_and_keeps_original(self):
        before = b"original\n"
        self.target.write_bytes(before)
        err = io.StringIO()
        with mock.patch.object(ENTRY.os, "replace", side_effect=PermissionError("locked")), \
                contextlib.redirect_stderr(err):
            result = ENTRY.main(["enable", "--agents-file", str(self.target), "--skill-file", str(SKILL)])
        self.assertEqual(result, 2)
        self.assertEqual(json.loads(err.getvalue())["state"], "blocked")
        self.assertEqual(self.target.read_bytes(), before)
        self.assertEqual(len(list(self.directory.glob("*.ai-apf.bak.*"))), 1)
        self.assertEqual(list(self.directory.glob(".ai-apf-*")), [])

    def test_concurrent_edit_before_replace_is_not_overwritten(self):
        before = b"original\n"
        later = b"new user edit\n"
        self.target.write_bytes(before)
        real_inspect = ENTRY.inspect_target
        calls = 0

        def inspect_with_edit(path):
            nonlocal calls
            calls += 1
            if calls == 2:
                path.write_bytes(later)
            return real_inspect(path)

        with mock.patch.object(ENTRY, "inspect_target", side_effect=inspect_with_edit):
            with self.assertRaises(ENTRY.EntryError):
                ENTRY.write_change(self.target, before, b"replacement\n")
        self.assertEqual(self.target.read_bytes(), later)
        self.assertEqual(list(self.directory.glob(".ai-apf-*")), [])


if __name__ == "__main__":
    unittest.main()
