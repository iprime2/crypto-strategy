#!/usr/bin/env python3
"""Tests for scripts/shadow_housekeep.py (stdlib unittest; CI runs it on ubuntu via pr.yml, Python script tests).

    cd cex-mm/scripts && python3 -m unittest -v test_shadow_housekeep
"""
from __future__ import annotations

import contextlib
import io
import os
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import shadow_housekeep as hk  # noqa: E402

DAY = 86400.0


def set_age(path: Path, days: float) -> None:
    t = time.time() - days * DAY
    os.utime(path, (t, t), follow_symlinks=False)


class HousekeepTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name).resolve()
        self.shadow = self.root / "artifacts" / "shadow"
        self.shadow.mkdir(parents=True)

    def tearDown(self):
        self._tmp.cleanup()

    # ------------------------------------------------------------ helpers

    def make_run(self, name: str, age_days: float, files=("delta_mainnet_public_ADAUSDT.jsonl", "dry-run.log"),
                 parent: Path | None = None) -> Path:
        run = (parent or self.shadow) / name
        run.mkdir()
        for f in files:
            (run / f).write_text("x" * 1000)
            set_age(run / f, age_days)
        set_age(run, age_days)
        return run

    def point_current(self, target) -> None:
        cur = self.shadow / "current"
        if os.path.lexists(cur):
            cur.unlink()
        os.symlink(target, cur)

    def run_main(self, *args: str, shadow: Path | None = None):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = hk.main(["--shadow-dir", str(shadow or self.shadow), *args])
        return code, out.getvalue(), err.getvalue()

    def standard_layout(self):
        """Two old runs, one recent run, and a fresh current run."""
        old1 = self.make_run("20260801T000000Z", 60)
        old2 = self.make_run("20260901T120000Z", 30)
        recent = self.make_run("20261001T000000Z", 5)
        cur = self.make_run("20261008T000000Z", 0)
        self.point_current(cur)
        return old1, old2, recent, cur

    # ------------------------------------------------------------ behaviour

    def test_dry_run_reports_and_deletes_nothing(self):
        old1, old2, recent, cur = self.standard_layout()
        code, out, _ = self.run_main()
        self.assertEqual(code, 0)
        for d in (old1, old2, recent, cur):
            self.assertTrue(d.is_dir(), d)
        self.assertRegex(out, r"would-delete\s+20260801T000000Z")
        self.assertRegex(out, r"would-delete\s+20260901T120000Z")
        self.assertRegex(out, r"keep\s+20261001T000000Z")
        self.assertRegex(out, r"keep\s+20261008T000000Z.*current")
        self.assertNotRegex(out, r"(?m)^deleted")
        self.assertIn("disk free before", out)
        self.assertIn("disk free after", out)
        self.assertRegex(out, r"total: 4 run dirs, kept 2, would delete 2")

    def test_apply_deletes_only_old_non_current_runs(self):
        old1, old2, recent, cur = self.standard_layout()
        code, out, _ = self.run_main("--apply")
        self.assertEqual(code, 0, out)
        self.assertFalse(os.path.lexists(old1))
        self.assertFalse(os.path.lexists(old2))
        self.assertTrue(recent.is_dir())
        self.assertTrue(cur.is_dir())
        self.assertTrue((self.shadow / "current").is_symlink())
        self.assertRegex(out, r"deleted\s+20260801T000000Z")
        self.assertRegex(out, r"total: 4 run dirs, kept 2, deleted 2")
        self.assertIn("disk free after", out)

    def test_days_threshold(self):
        run = self.make_run("20261003T000000Z", 5)
        self.point_current(self.make_run("20261008T000000Z", 0))
        self.assertEqual(self.run_main("--days", "7", "--apply")[0], 0)
        self.assertTrue(run.is_dir())
        self.assertEqual(self.run_main("--days", "3", "--apply")[0], 0)
        self.assertFalse(run.exists())

    def test_current_kept_even_when_old(self):
        cur = self.make_run("20260101T000000Z", 200)
        self.point_current(cur)
        code, out, _ = self.run_main("--apply")
        self.assertEqual(code, 0)
        self.assertTrue(cur.is_dir())
        self.assertRegex(out, r"keep\s+20260101T000000Z.*current")

    def test_current_given_as_relative_symlink_is_kept(self):
        cur = self.make_run("20260101T000000Z", 200)
        self.point_current("20260101T000000Z")
        self.assertEqual(self.run_main("--apply")[0], 0)
        self.assertTrue(cur.is_dir())

    def test_old_run_with_recent_file_is_kept(self):
        run = self.make_run("20260801T000000Z", 60)
        (run / "late.jsonl").write_text("still being written")
        set_age(run, 60)  # the new file is recent; the directory itself is old
        self.point_current(self.make_run("20261008T000000Z", 0))
        code, out, _ = self.run_main("--apply")
        self.assertEqual(code, 0)
        self.assertTrue(run.is_dir())
        self.assertRegex(out, r"keep\s+20260801T000000Z.*0\.\d days old")

    def test_recent_file_in_subdirectory_keeps_run(self):
        run = self.make_run("20260801T000000Z", 60)
        sub = run / "sub"
        sub.mkdir()
        (sub / "fresh.jsonl").write_text("x")
        set_age(sub, 60)
        set_age(run, 60)
        self.point_current(self.make_run("20261008T000000Z", 0))
        self.assertEqual(self.run_main("--apply")[0], 0)
        self.assertTrue((sub / "fresh.jsonl").is_file())

    def test_non_matching_names_and_files_are_ignored(self):
        self.point_current(self.make_run("20261008T000000Z", 0))
        others = [
            self.make_run("notes", 90),
            self.make_run("20260101T000000", 90),      # no Z
            self.make_run("20260101T000000Z.bak", 90),
            self.make_run("x20260101T000000Z", 90),
        ]
        for name in ("dashboard.log", "dashboard.pid", "20260102T000000Z"):  # last one: a file named like a run
            p = self.shadow / name
            p.write_text("keep me")
            set_age(p, 90)
            others.append(p)
        code, out, _ = self.run_main("--apply")
        self.assertEqual(code, 0)
        for p in others:
            self.assertTrue(p.exists(), p)
        self.assertRegex(out, r"skip\s+20260102T000000Z.*not a directory")
        self.assertNotIn("notes", out)

    def test_symlinked_run_entry_is_not_followed_or_deleted(self):
        outside = self.root / "elsewhere"
        outside.mkdir()
        target = self.make_run("20260101T000000Z", 90, parent=outside)
        link = self.shadow / "20260101T000000Z"
        os.symlink(target, link)
        self.point_current(self.make_run("20261008T000000Z", 0))
        code, out, _ = self.run_main("--apply")
        self.assertEqual(code, 0)
        self.assertTrue(link.is_symlink())
        self.assertTrue((target / "dry-run.log").is_file())
        self.assertRegex(out, r"skip\s+20260101T000000Z.*symlink")

    def test_symlink_inside_old_run_is_not_followed(self):
        outside = self.root / "precious"
        outside.mkdir()
        (outside / "data.jsonl").write_text("do not delete")
        run = self.make_run("20260801T000000Z", 60)
        os.symlink(outside, run / "link-to-precious")
        set_age(run / "link-to-precious", 60)
        set_age(run, 60)
        self.point_current(self.make_run("20261008T000000Z", 0))
        self.assertEqual(self.run_main("--apply")[0], 0)
        self.assertFalse(os.path.lexists(run))
        self.assertTrue((outside / "data.jsonl").is_file())

    def test_run_with_live_pid_is_kept(self):
        run = self.make_run("20260801T000000Z", 60)
        (run / "recorder.pid").write_text(f"{os.getpid()}\n")
        set_age(run / "recorder.pid", 60)
        set_age(run, 60)
        self.point_current(self.make_run("20261008T000000Z", 0))
        code, out, _ = self.run_main("--apply")
        self.assertEqual(code, 0)
        self.assertTrue(run.is_dir())
        self.assertRegex(out, rf"keep\s+20260801T000000Z.*live pid {os.getpid()} \S+ \(recorder\.pid\)")

    def test_dead_or_garbage_pid_does_not_block_deletion(self):
        proc = subprocess.Popen([sys.executable, "-c", "pass"])
        proc.wait()
        runs = []
        for i, text in enumerate([str(proc.pid), "", "0", "-1", "abc", "99999999999999999999"]):
            run = self.make_run(f"2026080{i}T000000Z", 60)
            (run / "dry-run.pid").write_text(text)
            set_age(run / "dry-run.pid", 60)
            set_age(run, 60)
            runs.append(run)
        self.point_current(self.make_run("20261008T000000Z", 0))
        code, out, _ = self.run_main("--apply")
        self.assertEqual(code, 0, out)
        for run in runs:
            self.assertFalse(run.exists(), (run, out))

    def test_unreadable_subdirectory_keeps_run(self):
        """os.walk reporting an error (e.g. EACCES on a subdir) must keep the run, not age it on partial mtimes."""
        bad = self.make_run("20260801T000000Z", 60)
        self.point_current(self.make_run("20261008T000000Z", 0))
        real_walk = os.walk

        def walk(top, *args, onerror=None, **kwargs):
            yield from real_walk(top, *args, onerror=onerror, **kwargs)
            if Path(top).name == bad.name and onerror is not None:
                onerror(PermissionError(13, "Permission denied", str(bad / "sub")))

        with mock.patch.object(hk.os, "walk", walk):
            code, out, _ = self.run_main("--apply")
        self.assertEqual(code, 0, out)
        self.assertTrue((bad / "dry-run.log").is_file())
        self.assertRegex(out, r"keep\s+20260801T000000Z\s+could not scan .*Permission denied")
        self.assertRegex(out, r"total: 2 run dirs, kept 2, deleted 0")

    def test_file_vanishing_mid_scan_keeps_run(self):
        bad = self.make_run("20260801T000000Z", 60)
        victim = str(bad / "dry-run.log")
        self.point_current(self.make_run("20261008T000000Z", 0))
        real_lstat = os.lstat

        def lstat(path, *args, **kwargs):
            if os.fspath(path) == victim:
                raise FileNotFoundError(2, "No such file or directory", victim)
            return real_lstat(path, *args, **kwargs)

        with mock.patch.object(hk.os, "lstat", lstat):
            code, out, _ = self.run_main("--apply")
        self.assertEqual(code, 0, out)
        self.assertTrue(bad.is_dir())
        self.assertRegex(out, r"keep\s+20260801T000000Z\s+could not scan .*No such file")

    def test_future_mtime_is_kept_and_logged_as_clock_skew(self):
        run = self.make_run("20260801T000000Z", -3)  # mtimes three days in the future
        self.point_current(self.make_run("20261008T000000Z", 0))
        code, out, _ = self.run_main("--apply")
        self.assertEqual(code, 0)
        self.assertTrue(run.is_dir())
        self.assertRegex(out, r"keep\s+20260801T000000Z.*newest file in the future \(clock skew\)")
        self.assertNotRegex(out, r"newest file -")

    def test_stdout_is_line_buffered(self):
        out = io.TextIOWrapper(io.BytesIO(), encoding="utf-8")  # block-buffered, like a pipe to journald
        self.assertFalse(out.line_buffering)
        self.point_current(self.make_run("20261008T000000Z", 0))
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(hk.main(["--shadow-dir", str(self.shadow)]), 0)
        self.assertTrue(out.line_buffering)

    def test_mid_run_stop_logs_deletions_before_the_stop_message(self):
        """Through a real pipe (as under systemd), stdout lines must not be held back behind stderr."""
        first = self.make_run("20260801T000000Z", 60)
        second = self.make_run("20260802T000000Z", 60)
        self.point_current(self.make_run("20261008T000000Z", 0))
        code = (
            "import sys\n"
            "sys.path.insert(0, sys.argv[1])\n"
            "import shadow_housekeep as hk\n"
            "real, calls = hk.check_deletable, []\n"
            "def guard(*a):\n"
            "    calls.append(a)\n"
            "    if len(calls) > 1:\n"
            "        raise hk.Refuse('test: current changed')\n"
            "    return real(*a)\n"
            "hk.check_deletable = guard\n"
            "sys.exit(hk.main(sys.argv[2:]))\n"
        )
        env = {k: v for k, v in os.environ.items() if k != "PYTHONUNBUFFERED"}
        p = subprocess.run([sys.executable, "-c", code, str(HERE), "--shadow-dir", str(self.shadow), "--apply"],
                           stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, env=env)
        self.assertEqual(p.returncode, 2, p.stdout)
        self.assertFalse(first.exists())
        self.assertTrue(second.is_dir())
        deleted = p.stdout.find("deleted       20260801T000000Z")
        stopped = p.stdout.find("stopped before deleting more: test: current changed")
        self.assertGreaterEqual(deleted, 0, p.stdout)
        self.assertGreater(stopped, deleted, p.stdout)
        self.assertGreater(stopped, p.stdout.find("disk free after"), p.stdout)

    # ------------------------------------------------------------ refusals

    def test_missing_current_deletes_nothing_and_fails(self):
        old = self.make_run("20260801T000000Z", 60)
        code, out, err = self.run_main("--apply")
        self.assertNotEqual(code, 0)
        self.assertTrue(old.is_dir())
        self.assertIn("current", err)
        self.assertIn("nothing deleted", err)

    def test_dangling_current_deletes_nothing_and_fails(self):
        old = self.make_run("20260801T000000Z", 60)
        self.point_current(self.shadow / "20261008T000000Z")  # never created
        code, _, err = self.run_main("--apply")
        self.assertNotEqual(code, 0)
        self.assertTrue(old.is_dir())
        self.assertIn("dangling", err)

    def test_current_outside_shadow_dir_deletes_nothing_and_fails(self):
        old = self.make_run("20260801T000000Z", 60)
        outside = self.root / "elsewhere"
        outside.mkdir()
        self.point_current(outside)
        code, _, err = self.run_main("--apply")
        self.assertNotEqual(code, 0)
        self.assertTrue(old.is_dir())
        self.assertIn("current", err)

    def test_current_as_plain_directory_deletes_nothing_and_fails(self):
        old = self.make_run("20260801T000000Z", 60)
        self.make_run("current", 0)  # a real directory, not shadow.sh's symlink
        code, _, err = self.run_main("--apply")
        self.assertEqual(code, 2)
        self.assertTrue(old.is_dir())
        self.assertIn("not a symlink", err)
        self.assertIn("nothing deleted", err)

    def test_current_pointing_at_non_run_directory_deletes_nothing_and_fails(self):
        old = self.make_run("20260801T000000Z", 60)
        self.point_current(self.make_run("notarun", 0))
        code, _, err = self.run_main("--apply")
        self.assertEqual(code, 2)
        self.assertTrue(old.is_dir())
        self.assertIn("not a run directory", err)

    def test_missing_shadow_dir_fails(self):
        code, _, err = self.run_main("--apply", shadow=self.root / "nope")
        self.assertNotEqual(code, 0)
        self.assertIn("nothing deleted", err)

    def test_days_below_one_refused(self):
        old = self.make_run("20260801T000000Z", 60)
        self.point_current(self.make_run("20261008T000000Z", 0))
        for days in ("0", "-3"):
            with self.assertRaises(SystemExit) as cm:
                self.run_main("--days", days, "--apply")
            self.assertNotEqual(cm.exception.code, 0)
        self.assertTrue(old.is_dir())

    def test_delete_guard_refuses_paths_outside_shadow_dir(self):
        cur = self.make_run("20261008T000000Z", 0)
        self.point_current(cur)
        outside = self.root / "elsewhere"
        outside.mkdir()
        foreign = self.make_run("20260101T000000Z", 90, parent=outside)
        with self.assertRaises(hk.Refuse):
            hk.check_deletable(self.shadow, foreign, cur)
        with self.assertRaises(hk.Refuse):  # .. escapes the shadow dir
            hk.check_deletable(self.shadow, self.shadow / ".." / ".." / "elsewhere" / "20260101T000000Z", cur)
        link = self.shadow / "20260102T000000Z"
        os.symlink(foreign, link)
        with self.assertRaises(hk.Refuse):
            hk.check_deletable(self.shadow, link, cur)
        with self.assertRaises(hk.Refuse):
            hk.check_deletable(self.shadow, cur, cur)
        with self.assertRaises(hk.Refuse):
            hk.check_deletable(self.shadow, self.shadow / "current", cur)
        ok = self.make_run("20260801T000000Z", 60)
        hk.check_deletable(self.shadow, ok, cur)  # does not raise
        self.assertTrue(foreign.is_dir())

    # ------------------------------------------------------------ CLI wiring

    def test_cli_exit_codes(self):
        script = HERE / "shadow_housekeep.py"
        old = self.make_run("20260801T000000Z", 60)
        p = subprocess.run([sys.executable, str(script), "--shadow-dir", str(self.shadow)],
                           capture_output=True, text=True)
        self.assertNotEqual(p.returncode, 0)  # no current yet
        self.point_current(self.make_run("20261008T000000Z", 0))
        p = subprocess.run([sys.executable, str(script), "--shadow-dir", str(self.shadow)],
                           capture_output=True, text=True)
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertIn("would-delete", p.stdout)
        self.assertTrue(old.is_dir())


if __name__ == "__main__":
    unittest.main()
