"""Tests for live.sh against a fake cex-mm tree: a stub mm-bot, stub key check and dummy keys, so nothing reaches
Delta and the real quote-bot/.env is never read. Linux only (/proc, setsid). CI does not run Python; run:

    cd cex-mm/scripts && python3 -m unittest -v test_live_sh
"""
from __future__ import annotations

import os
import shutil
import signal
import subprocess
import tempfile
import time
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
KEY, SECRET = "dummy-key-123", "dummy-secret-456"

# Records argv, cwd and env to stub.log, then behaves like the mode it was started in.
STUB_BOT = r"""#!/bin/bash
root="$(cd "$(dirname "$0")/../.." && pwd)"
{
  echo "ARGV $*"
  echo "CWD $PWD"
  env | sed 's/^/ENV /'
  echo "END"
} >>"$root/stub.log"
case "$1" in
  run)
    if [[ -f "$root/run_fails" ]]; then echo "ERROR leverage guard: mainnet start refused"; exit 1; fi
    echo "INFO mm_bot::runner: account guards on"; while :; do sleep 0.2; done ;;
  dry-run) while :; do sleep 0.2; done ;;
  cancel-all) [[ -f "$root/cancel_fails" ]] && exit 1; echo "cancelled"; exit 0 ;;
esac
"""
STUB_KEYCHECK = """import sys
from pathlib import Path
root = Path(__file__).resolve().parent.parent
print("ok   stub key check", sys.argv[1:])
sys.exit(1 if (root / "keycheck_fails").exists() else 0)
"""
STUB_VENUE = """import sys
from pathlib import Path
root = Path(__file__).resolve().parent.parent
args = sys.argv[1:]
with (root / "lvs_calls.log").open("a") as f:
    f.write(" ".join(args) + "\\n")
if args and args[0] == "venue":
    print("venue: stub", " ".join(args[1:]))
    if "--require-no-orders" in args and (root / "orders_open").exists():
        sys.exit(3)
"""


class LiveSh(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.root = self.tmp / "cex-mm"
        (self.root / "scripts").mkdir(parents=True)
        (self.root / "config").mkdir()
        (self.root / "quote-bot").mkdir()
        (self.root / "target" / "release").mkdir(parents=True)
        shutil.copy(HERE / "live.sh", self.root / "scripts" / "live.sh")
        shutil.copy(HERE.parent / "config" / "dism.env", self.root / "config" / "dism.env")
        (self.root / "scripts" / "delta_key_check.py").write_text(STUB_KEYCHECK)
        (self.root / "scripts" / "live_vs_shadow.py").write_text(STUB_VENUE)
        bot = self.root / "target" / "release" / "mm-bot"
        bot.write_text(STUB_BOT)
        bot.chmod(0o755)
        (self.root / "quote-bot" / ".env").write_text(
            f'DELTA_API_KEY=demo-must-not-leak\nMM_FIXED_HALF_SPREAD_BPS=99\n'
            f'DELTA_MAINNET_API_KEY="{KEY}"\n  DELTA_MAINNET_API_SECRET = {SECRET}\n')
        self.procs: list[int] = []
        self.env = {"PATH": os.environ["PATH"], "HOME": str(self.tmp), "LIVE_ALLOW_BINARY_MISMATCH": "1",
                    "LIVE_START_WAIT_S": "5"}

    def tearDown(self):
        for pid in self.procs + self.pids_of_stub():
            try:
                os.kill(pid, signal.SIGKILL)
            except OSError:
                pass
        shutil.rmtree(self.tmp, ignore_errors=True)

    def pids_of_stub(self) -> list[int]:
        out = []
        for d in Path("/proc").iterdir():
            if d.name.isdigit():
                try:
                    if str(self.root) in (d / "cmdline").read_bytes().decode(errors="replace"):
                        out.append(int(d.name))
                except OSError:
                    pass
        return out

    def live(self, *args, env=None, check=False) -> subprocess.CompletedProcess:
        e = dict(self.env, **(env or {}))
        return subprocess.run(["bash", str(self.root / "scripts" / "live.sh"), *args], env=e, capture_output=True,
                              text=True, timeout=60, check=check)

    def start_shadow(self):
        run = self.root / "artifacts" / "shadow" / "20261012T075609Z"
        run.mkdir(parents=True)
        (self.root / "artifacts" / "shadow" / "current").symlink_to(run)
        p = subprocess.Popen([str(self.root / "target" / "release" / "mm-bot"), "dry-run", "--venue", "delta"],
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
        self.procs.append(p.pid)
        (run / "dry-run.pid").write_text(f"{p.pid}\n")
        return p

    def stub_calls(self, argv0: str) -> list[dict]:
        log = self.root / "stub.log"
        calls, cur = [], None
        for line in (log.read_text().splitlines() if log.exists() else []):
            if line.startswith("ARGV "):
                cur = {"argv": line[5:], "env": {}}
            elif line.startswith("CWD ") and cur is not None:
                cur["cwd"] = line[4:]
            elif line.startswith("ENV ") and cur is not None:
                k, _, v = line[4:].partition("=")
                cur["env"][k] = v
            elif line == "END" and cur is not None:
                calls.append(cur)
                cur = None
        return [c for c in calls if c["argv"].split(" ")[0] == argv0]

    @staticmethod
    def alive(pid: int) -> bool:
        """Running and not a zombie (this container's PID 1 does not reap orphans)."""
        try:
            return Path(f"/proc/{pid}/stat").read_text().split(") ")[1][0] != "Z"
        except (OSError, IndexError):
            return False

    def bot_pid(self) -> int:
        return int((self.root / "artifacts" / "live" / "current" / "bot.pid").read_text())

    # ------------------------------------------------------------ refusals

    def test_start_needs_the_typed_confirmation(self):
        self.start_shadow()
        for args in ([], ["--confirm"], ["--confirm", "start real"], ["--confirm", "START", "REAL"]):
            r = self.live("start", *args)
            self.assertNotEqual(r.returncode, 0, args)
            self.assertIn('--confirm "START REAL"', r.stderr)
        self.assertEqual(self.stub_calls("run"), [])

    def test_start_refuses_without_the_shadow_test(self):
        r = self.live("start", "--confirm", "START REAL")
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("shadow test is not running", r.stderr)
        self.assertEqual(self.stub_calls("run"), [])

    def test_start_refuses_when_the_key_check_fails(self):
        self.start_shadow()
        (self.root / "keycheck_fails").write_text("")
        r = self.live("start", "--confirm", "START REAL")
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("key check failed", r.stderr)
        self.assertEqual(self.stub_calls("run"), [])

    def test_start_refuses_with_missing_keys_and_names_only_the_variables(self):
        self.start_shadow()
        (self.root / "quote-bot" / ".env").write_text(f"DELTA_MAINNET_API_KEY={KEY}\n")
        r = self.live("start", "--confirm", "START REAL")
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("DELTA_MAINNET_API_SECRET", r.stderr)
        self.assertNotIn(KEY, r.stdout + r.stderr)

    def test_start_refuses_a_different_binary_from_the_shadow_unless_allowed(self):
        self.start_shadow()
        r = self.live("start", "--confirm", "START REAL", env={"LIVE_ALLOW_BINARY_MISMATCH": ""})
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("different mm-bot build", r.stderr)

    def test_start_refuses_when_another_bot_is_running(self):
        self.start_shadow()
        p = subprocess.Popen([str(self.root / "target" / "release" / "mm-bot"), "run", "--venue", "delta"],
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
        self.procs.append(p.pid)
        time.sleep(0.3)
        r = self.live("start", "--confirm", "START REAL")
        self.assertNotEqual(r.returncode, 0)
        self.assertIn(f"another mm-bot run process is alive (pid {p.pid}", r.stderr)

    def test_start_refuses_while_another_start_or_stop_holds_the_lock(self):
        self.start_shadow()
        (self.root / "artifacts" / "live").mkdir(parents=True, exist_ok=True)
        holder = subprocess.Popen(["flock", str(self.root / "artifacts" / "live" / ".lock"), "sleep", "20"],
                                  start_new_session=True)
        self.procs.append(holder.pid)
        time.sleep(0.3)
        r = self.live("start", "--confirm", "START REAL")
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("another live.sh start or stop is running", r.stderr)
        self.assertEqual(self.stub_calls("run"), [])

    def test_exec_is_internal(self):
        self.start_shadow()
        r = self.live("_exec", "run", "ADAUSDT")
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("_exec is internal", r.stderr)
        self.assertEqual(self.stub_calls("run"), [])

    def test_start_refuses_a_quoted_or_spaced_key_naming_only_the_variable(self):
        self.start_shadow()
        (self.root / "quote-bot" / ".env").write_text(f"DELTA_MAINNET_API_KEY='{KEY}'\nDELTA_MAINNET_API_SECRET={SECRET}\n")
        r = self.live("start", "--confirm", "START REAL")
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("DELTA_MAINNET_API_KEY", r.stderr)
        self.assertIn("quotes or spaces", r.stderr)
        self.assertNotIn(KEY, r.stdout + r.stderr)
        self.assertNotIn(SECRET, r.stdout + r.stderr)

    def test_tracing_never_prints_the_secret(self):
        self.start_shadow()
        e = dict(self.env)
        r = subprocess.run(["bash", "-x", str(self.root / "scripts" / "live.sh"), "start", "--confirm", "START REAL"],
                           env=e, capture_output=True, text=True, timeout=60)
        self.assertEqual(r.returncode, 0, r.stderr[-2000:])
        self.assertNotIn(SECRET, r.stdout + r.stderr)
        self.assertNotIn(KEY, r.stdout + r.stderr)

    # ------------------------------------------------------------ start / status / stop

    def test_start_runs_the_bot_on_mainnet_with_only_the_keys_and_the_profile(self):
        self.start_shadow()
        r = self.live("start", "--confirm", "START REAL")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        pid = self.bot_pid()
        self.assertTrue(self.alive(pid))
        self.assertNotIn("no 'account guards on' line", r.stdout)
        runs = self.stub_calls("run")
        self.assertEqual(len(runs), 1)
        call = runs[0]
        self.assertEqual(call["argv"], "run --venue delta --env mainnet --symbols ADAUSDT --loop-ms 400")
        env = call["env"]
        self.assertEqual(env["DELTA_MAINNET_API_KEY"], KEY)  # quotes and spaces stripped like the OEMS
        self.assertEqual(env["DELTA_MAINNET_API_SECRET"], SECRET)
        self.assertNotIn("DELTA_API_KEY", env)  # nothing else from quote-bot/.env
        self.assertEqual(env["MM_FIXED_HALF_SPREAD_BPS"], "5")  # the profile, not the demo line
        self.assertEqual(env["MM_DMS_TTL_MS"], "15000")
        self.assertIn("MM_ORDER=info", env["RUST_LOG"])
        self.assertIn("MM_METRICS=info", env["RUST_LOG"])
        self.assertEqual(Path(call["cwd"]).resolve(), (self.root / "artifacts" / "live").resolve())
        # The secret is in no argv, no config, no output.
        cmdline = Path(f"/proc/{pid}/cmdline").read_bytes().decode()
        self.assertNotIn(SECRET, cmdline)
        run_dir = (self.root / "artifacts" / "live" / "current").resolve()
        config = (run_dir / "config.txt").read_text()
        for secret in (KEY, SECRET):
            self.assertNotIn(secret, config)
            self.assertNotIn(secret, r.stdout + r.stderr)
        self.assertIn("MM_SYMBOLS=ADAUSDT", config)
        self.assertIn("shadow_run=20261012T075609Z", config)
        # The daily loss state is shared with every mainnet runner from cex-mm/; economics stay apart.
        risk = self.root / "artifacts" / "live" / "artifacts" / "risk"
        self.assertTrue(risk.is_symlink())
        self.assertEqual(risk.resolve(), (self.root / "artifacts" / "risk").resolve())
        self.assertIn("bot: running", r.stdout)
        # A second start is refused while it runs.
        r2 = self.live("start", "--confirm", "START REAL")
        self.assertNotEqual(r2.returncode, 0)
        self.assertIn("already running", r2.stderr)

    def test_a_failed_start_cancels_on_mainnet_and_says_why(self):
        self.start_shadow()
        (self.root / "run_fails").write_text("")
        r = self.live("start", "--confirm", "START REAL")
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("exited during startup", r.stderr)
        self.assertIn("leverage guard", r.stderr)
        cancels = self.stub_calls("cancel-all")
        self.assertEqual(len(cancels), 1)
        self.assertEqual(cancels[0]["argv"], "cancel-all --venue delta --env mainnet --symbol ADAUSDT")

    def test_stop_kills_the_bot_then_cancels_on_mainnet_without_the_profile(self):
        self.start_shadow()
        self.live("start", "--confirm", "START REAL", check=True)
        pid = self.bot_pid()
        r = self.live("stop")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        time.sleep(0.2)
        self.assertFalse(self.alive(pid))
        cancels = self.stub_calls("cancel-all")
        self.assertEqual(len(cancels), 1)
        self.assertEqual(cancels[0]["argv"], "cancel-all --venue delta --env mainnet --symbol ADAUSDT")
        self.assertEqual(cancels[0]["env"]["DELTA_MAINNET_API_KEY"], KEY)
        self.assertNotIn("MM_SYMBOLS", cancels[0]["env"])  # would send cancel-all down the universe path
        self.assertTrue((self.root / "artifacts" / "live" / "current" / "stopped").exists())
        self.assertIn("left open", r.stdout)
        self.assertIn("bot: stopped", self.live("status").stdout)

    def test_stop_cancels_the_running_run_symbols_even_if_the_profile_changed(self):
        self.start_shadow()
        self.live("start", "--confirm", "START REAL", check=True)
        prof = self.root / "config" / "dism.env"
        prof.write_text(prof.read_text().replace("MM_SYMBOLS=ADAUSDT", "MM_SYMBOLS=KITEUSDT"))
        r = self.live("stop")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(self.stub_calls("cancel-all")[0]["argv"], "cancel-all --venue delta --env mainnet --symbol ADAUSDT")
        prof.write_text("\n".join(l for l in prof.read_text().splitlines() if not l.startswith("MM_SYMBOLS")))
        r = self.live("stop")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(self.stub_calls("cancel-all")[1]["argv"], "cancel-all --venue delta --env mainnet --symbol ADAUSDT")

    def test_stop_fails_when_orders_are_still_open_after_the_cancel(self):
        self.start_shadow()
        self.live("start", "--confirm", "START REAL", check=True)
        (self.root / "orders_open").write_text("")
        r = self.live("stop")
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("orders are still open", r.stderr)

    def test_report_defaults_to_the_last_day(self):
        self.start_shadow()
        self.live("start", "--confirm", "START REAL", check=True)
        self.live("report")
        self.live("report", "--all", "--json")
        self.live("report", "--hours", "6")
        calls = [l for l in (self.root / "lvs_calls.log").read_text().splitlines() if l.startswith("--live-dir")]
        self.assertIn("--hours 24", calls[0])
        self.assertNotIn("--hours", calls[1])
        self.assertIn("--json", calls[1])
        self.assertIn("--hours 6", calls[2])
        self.assertNotIn("--hours 24", calls[2])

    def test_stop_reports_a_failed_cancel(self):
        self.start_shadow()
        self.live("start", "--confirm", "START REAL", check=True)
        (self.root / "cancel_fails").write_text("")
        r = self.live("stop")
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("CANCEL FAILED", r.stderr)
        self.assertEqual(len(self.stub_calls("cancel-all")), 3)

    def test_status_says_down_when_the_bot_died_on_its_own(self):
        self.start_shadow()
        self.live("start", "--confirm", "START REAL", check=True)
        os.kill(self.bot_pid(), signal.SIGKILL)
        time.sleep(0.2)
        out = self.live("status").stdout
        self.assertIn("bot: DOWN", out)
        self.assertIn("dead man's switch", out)
        # The shadow test is untouched by all of this.
        self.assertTrue(self.alive(int((self.root / "artifacts" / "shadow" / "current" / "dry-run.pid").read_text())))

    def test_stop_never_signals_a_reused_pid(self):
        self.start_shadow()
        self.live("start", "--confirm", "START REAL", check=True)
        bot = self.bot_pid()
        os.kill(bot, signal.SIGKILL)
        time.sleep(0.2)
        other = subprocess.Popen(["sleep", "30"], start_new_session=True)
        self.procs.append(other.pid)
        (self.root / "artifacts" / "live" / "current" / "bot.pid").write_text(f"{other.pid}\n")
        self.live("stop")
        self.assertTrue(self.alive(other.pid))  # not an mm-bot run process, so never signalled


if __name__ == "__main__":
    unittest.main()
