//! Process supervisor for quote-bot mm-bot — only signals PIDs it spawned or adopted.
//!
//! - Every spawned child is waited on from a thread, so an exited bot is reaped
//!   instead of lingering as a zombie that `kill(pid, 0)` would report as alive.
//! - Bot stdout/stderr go to `artifacts/logs/mm-bot-<strategy>-<utc>.log`; the
//!   telemetry tailer reads `MM_METRICS` and events from there.
//! - After an OEMS restart the bot keeps running; `adopt` re-attaches to it when
//!   `/proc/<pid>/cmdline` shows it is our `mm-bot run`.

use std::collections::{BTreeMap, HashMap};
use std::path::{Path, PathBuf};
use std::process::Stdio;
use std::sync::{Arc, Mutex};
use std::time::{Duration, Instant};

use chrono::{DateTime, Utc};
use serde_json::Value;

use crate::delta::VenueEnv;

#[derive(Debug, Clone)]
pub struct StartRequest {
    pub strategy_id: String,
    pub cex_mm_root: PathBuf,
    pub quote_bot_env: PathBuf,
    pub config_body: Option<Value>,
    pub env: VenueEnv,
    /// Settings file relative to `cex_mm_root` (e.g. `config/dism.env`); see `bot_env_pairs`.
    pub profile: Option<PathBuf>,
}

#[derive(Debug, thiserror::Error)]
pub enum SupervisorError {
    #[error("quote-bot/.env is missing at {0}; refuse to start")]
    MissingEnv(String),
    #[error("strategy {0} already has a live process (pid {1})")]
    AlreadyAlive(String, u32),
    #[error("{0} missing from quote-bot/.env; refuse to start")]
    MissingKeys(String),
    #[error("strategy profile {0} is missing; refuse to start")]
    MissingProfile(String),
    #[error("mm-bot binary not found at {0}")]
    MissingBinary(String),
    #[error("spawn failed: {0}")]
    Spawn(String),
}

#[derive(Debug, Clone)]
pub struct ProcInfo {
    pub pid: u32,
    pub started_at: Option<DateTime<Utc>>,
    pub log_path: Option<PathBuf>,
    pub adopted: bool,
}

#[derive(Debug, Clone)]
pub struct ExitInfo {
    pub pid: u32,
    pub code: Option<i32>,
    pub at: DateTime<Utc>,
}

/// In-memory record of PIDs this OEMS process spawned or adopted. Never signal others.
#[derive(Default)]
pub struct Supervisor {
    spawned: Mutex<HashMap<String, ProcInfo>>,
    exits: Arc<Mutex<HashMap<String, ExitInfo>>>,
}

/// Default log filter for a supervised bot when the env file does not set one.
const BOT_RUST_LOG: &str = "info,mm_bot=info,MM_METRICS=info,MM_ORDER=info";

impl Supervisor {
    pub fn new() -> Self {
        Self::default()
    }

    pub fn recorded_pid(&self, strategy_id: &str) -> Option<u32> {
        self.info(strategy_id).map(|p| p.pid)
    }

    pub fn info(&self, strategy_id: &str) -> Option<ProcInfo> {
        self.spawned.lock().ok().and_then(|g| g.get(strategy_id).cloned())
    }

    pub fn last_exit(&self, strategy_id: &str) -> Option<ExitInfo> {
        self.exits.lock().ok().and_then(|g| g.get(strategy_id).cloned())
    }

    pub fn record_spawned(&self, strategy_id: &str, pid: u32) {
        self.record(strategy_id, ProcInfo { pid, started_at: Some(Utc::now()), log_path: None, adopted: false });
    }

    fn record(&self, strategy_id: &str, info: ProcInfo) {
        if let Ok(mut g) = self.spawned.lock() {
            g.insert(strategy_id.to_string(), info);
        }
    }

    pub fn clear_spawned(&self, strategy_id: &str) {
        if let Ok(mut g) = self.spawned.lock() {
            g.remove(strategy_id);
        }
    }

    /// True only if this supervisor recorded the pid for the strategy.
    pub fn owns_pid(&self, strategy_id: &str, pid: u32) -> bool {
        self.recorded_pid(strategy_id) == Some(pid)
    }

    /// Re-attach to a bot left running by a previous OEMS process. Only adopts a
    /// live process whose command line is `mm-bot … run`.
    pub fn adopt(&self, strategy_id: &str, pid: u32) -> bool {
        if self.recorded_pid(strategy_id).is_some() || !pid_alive(pid) || !is_mm_bot_run(pid) {
            return false;
        }
        self.record(
            strategy_id,
            ProcInfo {
                pid,
                started_at: process_start_time(pid),
                log_path: log_path_for_pid(pid),
                adopted: true,
            },
        );
        true
    }

    /// Stop: SIGTERM only a pid this supervisor recorded, wait up to `grace` for it
    /// to exit, then SIGKILL. Returns Ok(true) if signaled, Ok(false) if not ours / none.
    pub fn stop_owned(&self, strategy_id: &str) -> std::io::Result<bool> {
        self.stop_owned_with_grace(strategy_id, Duration::from_secs(5))
    }

    pub fn stop_owned_with_grace(&self, strategy_id: &str, grace: Duration) -> std::io::Result<bool> {
        let Some(pid) = self.recorded_pid(strategy_id) else {
            return Ok(false);
        };
        if !pid_alive(pid) {
            self.clear_spawned(strategy_id);
            return Ok(false);
        }
        signal(pid, SIGTERM)?;
        if !wait_for_exit(pid, grace) {
            let _ = signal(pid, SIGKILL);
            wait_for_exit(pid, Duration::from_secs(2));
        }
        self.clear_spawned(strategy_id);
        Ok(true)
    }

    /// Start mm-bot with env from quote-bot/.env (+ config overrides). Does not touch other pids.
    pub fn start(&self, req: StartRequest) -> Result<u32, SupervisorError> {
        if !req.quote_bot_env.is_file() {
            return Err(SupervisorError::MissingEnv(req.quote_bot_env.display().to_string()));
        }
        if let Some(pid) = self.recorded_pid(&req.strategy_id) {
            if pid_alive(pid) {
                return Err(SupervisorError::AlreadyAlive(req.strategy_id, pid));
            }
            self.clear_spawned(&req.strategy_id);
        }
        let profile_pairs = match &req.profile {
            Some(rel) => {
                let path = req.cex_mm_root.join(rel);
                if !path.is_file() {
                    return Err(SupervisorError::MissingProfile(path.display().to_string()));
                }
                Some(load_env_file(&path))
            }
            None => None,
        };
        let env_pairs = load_env_file(&req.quote_bot_env);
        let names = req.env.key_names();
        if req.env == VenueEnv::Mainnet
            && !names.iter().any(|(k, s)| env_map_has_key(&env_pairs, k) && env_map_has_key(&env_pairs, s))
        {
            let names: Vec<String> = names.iter().map(|(k, s)| format!("{k}/{s}")).collect();
            return Err(SupervisorError::MissingKeys(names.join(" or ")));
        }

        let bin = req.cex_mm_root.join("target/debug/mm-bot");
        if !bin.is_file() {
            return Err(SupervisorError::MissingBinary(bin.display().to_string()));
        }

        let log_dir = req.cex_mm_root.join("artifacts/logs");
        std::fs::create_dir_all(&log_dir).map_err(|e| SupervisorError::Spawn(e.to_string()))?;
        let log_path = log_dir.join(format!(
            "mm-bot-{}-{}.log",
            req.strategy_id,
            Utc::now().format("%Y%m%dT%H%M%SZ")
        ));
        let log = std::fs::OpenOptions::new()
            .create(true)
            .append(true)
            .open(&log_path)
            .map_err(|e| SupervisorError::Spawn(e.to_string()))?;
        let log_err = log.try_clone().map_err(|e| SupervisorError::Spawn(e.to_string()))?;

        let pairs = bot_env_pairs(req.env, &env_pairs, profile_pairs.as_deref(), req.config_body.as_ref());
        let mut cmd = std::process::Command::new(&bin);
        cmd.args(["run", "--venue", "delta", "--env", req.env.bot_flag(), "--loop-ms", "400"])
            .current_dir(&req.cex_mm_root)
            .stdin(Stdio::null())
            .stdout(Stdio::from(log))
            .stderr(Stdio::from(log_err))
            .env_clear();
        if let Ok(path) = std::env::var("PATH") {
            cmd.env("PATH", path);
        }
        for (k, v) in &pairs {
            cmd.env(k, v);
        }
        if !env_map_has_key(&pairs, "RUST_LOG") {
            cmd.env("RUST_LOG", BOT_RUST_LOG);
        }
        cmd.env("NO_COLOR", "1");

        let mut child = cmd.spawn().map_err(|e| SupervisorError::Spawn(e.to_string()))?;
        let pid = child.id();
        self.record(
            &req.strategy_id,
            ProcInfo { pid, started_at: Some(Utc::now()), log_path: Some(log_path), adopted: false },
        );
        // Reap the child when it exits so it never lingers as a zombie.
        let exits = self.exits.clone();
        let strategy_id = req.strategy_id.clone();
        std::thread::spawn(move || {
            let code = child.wait().ok().and_then(|s| s.code());
            if let Ok(mut g) = exits.lock() {
                g.insert(strategy_id, ExitInfo { pid, code, at: Utc::now() });
            }
        });
        Ok(pid)
    }
}

/// Badge state: a saved "running" row is stopped once its process is gone.
pub fn status_for_display(desired_state: &str, process_alive: bool) -> &'static str {
    if desired_state == "running" && process_alive {
        "running"
    } else {
        "stopped"
    }
}

/// Alive = exists and is not a zombie (`kill(pid, 0)` alone reports zombies as alive).
pub fn pid_alive(pid: u32) -> bool {
    if pid == 0 {
        return false;
    }
    // kill(pid, 0) — existence check; does not send a real signal.
    if unsafe { libc_kill(pid as i32, 0) } != 0 {
        return false;
    }
    !matches!(proc_state(pid), Some('Z') | Some('X'))
}

/// Single-letter process state from `/proc/<pid>/stat` (R, S, Z, …).
fn proc_state(pid: u32) -> Option<char> {
    let stat = std::fs::read_to_string(format!("/proc/{pid}/stat")).ok()?;
    parse_stat_state(&stat)
}

fn parse_stat_state(stat: &str) -> Option<char> {
    // Format: pid (comm) S ...; comm may contain spaces, so split after the last ')'.
    let rest = &stat[stat.rfind(')')? + 1..];
    rest.split_whitespace().next()?.chars().next()
}

fn is_mm_bot_run(pid: u32) -> bool {
    let Ok(raw) = std::fs::read(format!("/proc/{pid}/cmdline")) else {
        return false;
    };
    cmdline_is_mm_bot_run(&raw)
}

fn cmdline_is_mm_bot_run(raw: &[u8]) -> bool {
    let args: Vec<String> = raw
        .split(|b| *b == 0)
        .filter(|a| !a.is_empty())
        .map(|a| String::from_utf8_lossy(a).into_owned())
        .collect();
    args.first().is_some_and(|a| a.ends_with("mm-bot")) && args.iter().any(|a| a == "run")
}

/// Where the process writes stdout, if it is a regular file (not /dev/null or a pipe).
pub fn log_path_for_pid(pid: u32) -> Option<PathBuf> {
    let target = std::fs::read_link(format!("/proc/{pid}/fd/1")).ok()?;
    if target.is_file() {
        Some(target)
    } else {
        None
    }
}

/// Process start time from `/proc/<pid>/stat` (field 22, clock ticks since boot).
pub fn process_start_time(pid: u32) -> Option<DateTime<Utc>> {
    let stat = std::fs::read_to_string(format!("/proc/{pid}/stat")).ok()?;
    let rest = &stat[stat.rfind(')')? + 1..];
    // After ')' the fields start at #3 (state); starttime is #22 → index 19.
    let ticks: u64 = rest.split_whitespace().nth(19)?.parse().ok()?;
    let btime: i64 = std::fs::read_to_string("/proc/stat")
        .ok()?
        .lines()
        .find_map(|l| l.strip_prefix("btime ").and_then(|v| v.trim().parse().ok()))?;
    const CLK_TCK: u64 = 100;
    DateTime::from_timestamp(btime + (ticks / CLK_TCK) as i64, 0)
}

fn wait_for_exit(pid: u32, timeout: Duration) -> bool {
    let start = Instant::now();
    while start.elapsed() < timeout {
        if !pid_alive(pid) {
            return true;
        }
        std::thread::sleep(Duration::from_millis(100));
    }
    !pid_alive(pid)
}

const SIGTERM: i32 = 15;
const SIGKILL: i32 = 9;

fn signal(pid: u32, sig: i32) -> std::io::Result<()> {
    if unsafe { libc_kill(pid as i32, sig) } == 0 {
        Ok(())
    } else {
        Err(std::io::Error::last_os_error())
    }
}

unsafe fn libc_kill(pid: i32, sig: i32) -> i32 {
    // Avoid depending on the `libc` crate; use libc via extern.
    extern "C" {
        fn kill(pid: i32, sig: i32) -> i32;
    }
    kill(pid, sig)
}

/// Load KEY=VALUE pairs from an env file. Never logs values.
pub fn load_env_file(path: &Path) -> Vec<(String, String)> {
    let Ok(text) = std::fs::read_to_string(path) else {
        return Vec::new();
    };
    let mut out = Vec::new();
    for raw in text.lines() {
        let line = raw.trim();
        if line.is_empty() || line.starts_with('#') || !line.contains('=') {
            continue;
        }
        let (k, v) = line.split_once('=').unwrap();
        let k = k.trim();
        let v = v.trim().trim_matches('"');
        if !k.is_empty() {
            out.push((k.to_string(), v.to_string()));
        }
    }
    out
}

/// Whether `key`'s last assignment in the env file is non-empty (a name set twice: the last one wins).
pub fn env_map_has_key(pairs: &[(String, String)], key: &str) -> bool {
    pairs.iter().rev().find(|(k, _)| k == key).is_some_and(|(_, v)| !v.is_empty())
}

/// Legacy UI config keys → the env names mm-bot actually reads.
const LEGACY_KEYS: &[(&str, &str)] = &[
    ("symbols", "MM_SYMBOLS"),
    ("order_qty", "MM_ORDER_QTY"),
    ("max_inventory", "MM_MAX_INVENTORY"),
    ("half_spread_bps", "MM_HALF_SPREAD_BPS"),
    ("min_half_spread_bps", "MM_MIN_HALF_SPREAD_BPS"),
    ("max_half_spread_bps", "MM_MAX_HALF_SPREAD_BPS"),
    ("inv_spread_widen", "MM_INV_SPREAD_WIDEN"),
    ("reject_kill_count", "MM_REJECT_KILL_COUNT"),
    ("l3_jump_bps", "MM_REGIME_L3_JUMP_BPS"),
];

/// Env var name for a config key: `MM_*` names pass through, legacy keys are mapped,
/// anything else is ignored (it would not affect the bot).
pub fn env_key_for(key: &str) -> Option<String> {
    let is_env_name = key.starts_with("MM_")
        && key.chars().all(|c| c.is_ascii_uppercase() || c.is_ascii_digit() || c == '_');
    if is_env_name {
        return Some(key.to_string());
    }
    LEGACY_KEYS.iter().find(|(k, _)| *k == key).map(|(_, v)| v.to_string())
}

fn env_value(v: &Value) -> Option<String> {
    match v {
        Value::String(s) => Some(s.trim().to_string()),
        Value::Number(n) => Some(n.to_string()),
        Value::Bool(b) => Some(if *b { "1" } else { "0" }.to_string()),
        Value::Array(items) => Some(
            items
                .iter()
                .filter_map(|i| env_value(i))
                .filter(|s| !s.is_empty())
                .collect::<Vec<_>>()
                .join(","),
        ),
        Value::Null | Value::Object(_) => None,
    }
}

/// Config body → env pairs for the bot. Secret-looking keys and profile-only keys are dropped.
pub fn config_env_pairs(body: &Value) -> Vec<(String, String)> {
    let Some(obj) = body.as_object() else {
        return Vec::new();
    };
    let mut out = Vec::new();
    for (k, v) in obj {
        let single = Value::Object([(k.clone(), v.clone())].into_iter().collect());
        if crate::config_guard::find_forbidden_secret_key(&single).is_some()
            || crate::config_guard::find_profile_only_key(&single).is_some()
        {
            continue;
        }
        if let (Some(name), Some(val)) = (env_key_for(k), env_value(v)) {
            out.push((name, val));
        }
    }
    out
}

fn is_secret_name(name: &str) -> bool {
    let upper = name.to_uppercase();
    ["KEY", "SECRET", "TOKEN", "PASS"].iter().any(|s| upper.contains(s))
}

/// Env for the bot process, later pairs winning:
/// - no profile (the demo `mm` strategy): quote-bot/.env minus the other environment's keys,
///   then config overrides;
/// - with a profile (e.g. DISM): only this environment's keys and `RUST_LOG` from quote-bot/.env,
///   then the profile, then config overrides. The demo bot's `MM_*` lines never leak in, so a
///   live run uses exactly the settings the shadow test scored.
pub fn bot_env_pairs(
    env: VenueEnv,
    file_pairs: &[(String, String)],
    profile_pairs: Option<&[(String, String)]>,
    body: Option<&Value>,
) -> Vec<(String, String)> {
    let own: Vec<&str> = env.secret_names().collect();
    let other: Vec<&str> = env.other().secret_names().collect();
    let mut out: Vec<(String, String)> = match profile_pairs {
        None => file_pairs
            .iter()
            .filter(|(k, _)| !other.contains(&k.as_str()))
            .cloned()
            .collect(),
        Some(profile) => file_pairs
            .iter()
            .filter(|(k, _)| own.contains(&k.as_str()) || k == "RUST_LOG")
            .chain(profile.iter())
            .cloned()
            .collect(),
    };
    if let Some(b) = body {
        out.extend(config_env_pairs(b));
    }
    out
}

/// Typed confirmation a real-money start must carry.
pub const MAINNET_CONFIRM: &str = "START REAL";

/// A mainnet start needs the OEMS started with `OEMS_ALLOW_MAINNET=1` and the typed confirmation.
/// Err is `(code, message)` for the API error body.
pub fn mainnet_start_check(env: VenueEnv, allow_mainnet: bool, confirm: Option<&str>) -> Result<(), (&'static str, String)> {
    if env != VenueEnv::Mainnet {
        return Ok(());
    }
    if !allow_mainnet {
        return Err((
            "mainnet_disabled",
            "real-money strategies are disabled; restart the OEMS with OEMS_ALLOW_MAINNET=1".into(),
        ));
    }
    if confirm != Some(MAINNET_CONFIRM) {
        return Err(("confirm_required", format!("type \"{MAINNET_CONFIRM}\" to start a real-money strategy")));
    }
    Ok(())
}

/// What the bot will run with (see `bot_env_pairs`), tagged `env_file`, `profile` or `override`.
/// Secrets never appear.
pub fn effective_env_for(
    file_pairs: &[(String, String)],
    profile_pairs: Option<&[(String, String)]>,
    body: Option<&Value>,
) -> BTreeMap<String, (String, &'static str)> {
    let mut out = BTreeMap::new();
    for (k, v) in file_pairs {
        let inherited = match profile_pairs {
            None => k.starts_with("MM_") || k == "RUST_LOG",
            Some(_) => k == "RUST_LOG",
        };
        if inherited && !is_secret_name(k) {
            out.insert(k.clone(), (v.clone(), "env_file"));
        }
    }
    for (k, v) in profile_pairs.unwrap_or_default() {
        if !is_secret_name(k) {
            out.insert(k.clone(), (v.clone(), "profile"));
        }
    }
    if let Some(b) = body {
        for (k, v) in config_env_pairs(b) {
            if !is_secret_name(&k) {
                out.insert(k, (v, "override"));
            }
        }
    }
    out
}

/// `effective_env_for` without a profile (the demo `mm` strategy).
pub fn effective_env(file_pairs: &[(String, String)], body: Option<&Value>) -> BTreeMap<String, (String, &'static str)> {
    effective_env_for(file_pairs, None, body)
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::json;
    use std::sync::Arc;

    fn kv(list: &[(&str, &str)]) -> Vec<(String, String)> {
        list.iter().map(|(k, v)| (k.to_string(), v.to_string())).collect()
    }

    fn file() -> Vec<(String, String)> {
        kv(&[
            ("DELTA_DEMO_API_KEY", "ndk"),
            ("DELTA_DEMO_API_SECRET", "nds"),
            ("DELTA_API_KEY", "dk"),
            ("DELTA_API_SECRET", "ds"),
            ("DELTA_MAINNET_API_KEY", "mk"),
            ("DELTA_MAINNET_API_SECRET", "ms"),
            ("MM_SYMBOLS", "ETHUSDT"),
            ("MM_ORDER_QTY", "0.01"),
            ("RUST_LOG", "debug"),
        ])
    }

    fn get<'a>(pairs: &'a [(String, String)], key: &str) -> Option<&'a str> {
        pairs.iter().rev().find(|(k, _)| k == key).map(|(_, v)| v.as_str())
    }

    #[test]
    fn profile_strategy_takes_only_its_keys_from_the_env_file() {
        let profile = kv(&[("MM_SYMBOLS", "ADAUSDT"), ("MM_FIXED_HALF_SPREAD_BPS", "5")]);
        let env = bot_env_pairs(VenueEnv::Mainnet, &file(), Some(&profile), Some(&json!({"MM_ACCOUNT_POLL_SEC": 20})));
        assert_eq!(get(&env, "DELTA_MAINNET_API_KEY"), Some("mk"));
        assert_eq!(get(&env, "DELTA_API_KEY"), None, "demo keys never reach a real-money bot");
        assert_eq!(get(&env, "DELTA_DEMO_API_KEY"), None);
        assert_eq!(get(&env, "DELTA_DEMO_API_SECRET"), None);
        assert_eq!(get(&env, "MM_SYMBOLS"), Some("ADAUSDT"));
        assert_eq!(get(&env, "MM_ORDER_QTY"), None, "the demo bot's MM_* lines do not leak in");
        assert_eq!(get(&env, "MM_FIXED_HALF_SPREAD_BPS"), Some("5"));
        assert_eq!(get(&env, "MM_ACCOUNT_POLL_SEC"), Some("20"), "UI overrides beat the profile");
        assert_eq!(get(&env, "RUST_LOG"), Some("debug"));
    }

    #[test]
    fn legacy_demo_strategy_keeps_the_env_file_but_not_mainnet_keys() {
        let env = bot_env_pairs(VenueEnv::Demo, &file(), None, Some(&json!({"symbols": "BTCUSDT"})));
        assert_eq!(get(&env, "DELTA_API_KEY"), Some("dk"));
        assert_eq!(get(&env, "DELTA_DEMO_API_KEY"), Some("ndk"));
        assert_eq!(get(&env, "DELTA_MAINNET_API_KEY"), None);
        assert_eq!(get(&env, "MM_ORDER_QTY"), Some("0.01"));
        assert_eq!(get(&env, "MM_SYMBOLS"), Some("BTCUSDT"));
    }

    #[test]
    fn no_demo_name_reaches_a_mainnet_bot_without_a_profile_either() {
        let env = bot_env_pairs(VenueEnv::Mainnet, &file(), None, None);
        assert_eq!(get(&env, "DELTA_MAINNET_API_KEY"), Some("mk"));
        for name in ["DELTA_DEMO_API_KEY", "DELTA_DEMO_API_SECRET", "DELTA_API_KEY", "DELTA_API_SECRET"] {
            assert_eq!(get(&env, name), None, "{name}");
        }
    }

    #[test]
    fn demo_profile_strategy_gets_both_demo_pairs_and_no_mainnet_keys() {
        let profile = kv(&[("MM_SYMBOLS", "ADAUSDT")]);
        let env = bot_env_pairs(VenueEnv::Demo, &file(), Some(&profile), None);
        assert_eq!(get(&env, "DELTA_DEMO_API_SECRET"), Some("nds"));
        assert_eq!(get(&env, "DELTA_API_SECRET"), Some("ds"));
        assert_eq!(get(&env, "DELTA_MAINNET_API_KEY"), None);
        assert_eq!(get(&env, "MM_ORDER_QTY"), None);
    }

    #[test]
    fn effective_env_tags_file_profile_and_override_and_hides_keys() {
        let profile = kv(&[("MM_SYMBOLS", "ADAUSDT")]);
        let eff = effective_env_for(&file(), Some(&profile), Some(&json!({"MM_DMS_TTL_MS": 15000})));
        assert_eq!(eff.get("MM_SYMBOLS"), Some(&("ADAUSDT".to_string(), "profile")));
        assert_eq!(eff.get("MM_DMS_TTL_MS"), Some(&("15000".to_string(), "override")));
        assert_eq!(eff.get("RUST_LOG"), Some(&("debug".to_string(), "env_file")));
        assert!(eff.keys().all(|k| !k.contains("KEY") && !k.contains("SECRET")));
        assert!(!eff.contains_key("MM_ORDER_QTY"));
    }

    #[test]
    fn mainnet_start_needs_the_server_switch_and_typed_confirmation() {
        assert!(mainnet_start_check(VenueEnv::Demo, false, None).is_ok(), "demo needs neither");
        assert_eq!(mainnet_start_check(VenueEnv::Mainnet, false, Some(MAINNET_CONFIRM)).unwrap_err().0, "mainnet_disabled");
        assert_eq!(mainnet_start_check(VenueEnv::Mainnet, true, None).unwrap_err().0, "confirm_required");
        assert_eq!(mainnet_start_check(VenueEnv::Mainnet, true, Some("start real")).unwrap_err().0, "confirm_required");
        assert!(mainnet_start_check(VenueEnv::Mainnet, true, Some(MAINNET_CONFIRM)).is_ok());
    }

    #[test]
    fn mainnet_start_refuses_without_mainnet_keys() {
        let dir = std::env::temp_dir().join(format!("oems-sup-{}", std::process::id()));
        std::fs::create_dir_all(dir.join("config")).unwrap();
        let env_file = dir.join("quote-bot.env");
        std::fs::write(&env_file, "DELTA_API_KEY=dk\nDELTA_API_SECRET=ds\n").unwrap();
        std::fs::write(dir.join("config/dism.env"), "MM_SYMBOLS=ADAUSDT\n").unwrap();
        let err = Supervisor::new()
            .start(StartRequest {
                strategy_id: "dism".into(),
                cex_mm_root: dir.clone(),
                quote_bot_env: env_file,
                config_body: None,
                env: VenueEnv::Mainnet,
                profile: Some("config/dism.env".into()),
            })
            .unwrap_err();
        assert!(matches!(err, SupervisorError::MissingKeys(_)), "{err}");
        std::fs::remove_dir_all(dir).ok();
    }

    #[test]
    fn dead_process_displays_stopped() {
        assert_eq!(status_for_display("running", false), "stopped");
        assert_eq!(status_for_display("running", true), "running");
        assert_eq!(status_for_display("stopped", true), "stopped");
    }

    #[test]
    fn stop_ignores_pid_not_recorded_by_supervisor() {
        let s = Arc::new(Supervisor::new());
        // Foreign pid must never be signaled — stop returns false.
        assert!(!s.owns_pid("mm", 1));
        let signaled = s.stop_owned("mm").expect("stop");
        assert!(!signaled);
    }

    #[test]
    fn stop_ignores_when_only_foreign_pid_claimed() {
        let s = Supervisor::new();
        assert!(!s.owns_pid("mm", 99999));
        assert_eq!(s.recorded_pid("mm"), None);
        assert!(!s.stop_owned("mm").unwrap());
    }

    #[test]
    fn start_refuses_without_quote_bot_env() {
        let s = Supervisor::new();
        let tmp = std::env::temp_dir().join("mm-oems-missing-env-test");
        let err = s
            .start(StartRequest {
                strategy_id: "mm".into(),
                cex_mm_root: PathBuf::from("/tmp"),
                quote_bot_env: tmp.join("no-such.env"),
                config_body: None,
                env: VenueEnv::Demo,
                profile: None,
            })
            .unwrap_err();
        match err {
            SupervisorError::MissingEnv(_) => {}
            other => panic!("expected MissingEnv, got {other}"),
        }
    }

    #[test]
    fn owns_only_recorded() {
        let s = Supervisor::new();
        s.record_spawned("mm", 4242);
        assert!(s.owns_pid("mm", 4242));
        assert!(!s.owns_pid("mm", 1111));
        assert!(!s.owns_pid("other", 4242));
    }

    #[test]
    fn zombie_state_is_parsed_after_comm() {
        assert_eq!(parse_stat_state("7388 (mm-bot) Z 5403 7388 0 0"), Some('Z'));
        assert_eq!(parse_stat_state("55781 (mm bot (x)) S 5403 55781"), Some('S'));
    }

    #[test]
    fn exited_child_is_reaped_not_zombie() {
        let mut child = std::process::Command::new("true").spawn().expect("spawn true");
        let pid = child.id();
        let _ = child.wait();
        assert!(!pid_alive(pid));
    }

    #[test]
    fn adopt_only_matches_mm_bot_run() {
        assert!(cmdline_is_mm_bot_run(b"/x/target/debug/mm-bot\0run\0--venue\0delta\0"));
        assert!(!cmdline_is_mm_bot_run(b"/x/target/release/mm-bot\0dry-run\0--venue\0delta\0"));
        assert!(!cmdline_is_mm_bot_run(b"/usr/bin/python3\0run\0"));
        // Our own test process is not mm-bot, so adoption is refused.
        let s = Supervisor::new();
        assert!(!s.adopt("mm", std::process::id()));
    }

    #[test]
    fn legacy_config_keys_map_to_bot_env_names() {
        let body = json!({
            "symbols": "ETHUSDT",
            "min_half_spread_bps": 8,
            "MM_LEAD_BETA": 0.8,
            "MM_SYMBOLS_EXTRA": ["ADAUSDT", "NEARUSDT"],
            "loop_ms": 400,
            "delta_api_key": "nope",
            "MM_FAIR_ANCHOR_WEIGHT": 1
        });
        let mut pairs = config_env_pairs(&body);
        pairs.sort();
        assert_eq!(
            pairs,
            vec![
                ("MM_LEAD_BETA".to_string(), "0.8".to_string()),
                ("MM_MIN_HALF_SPREAD_BPS".to_string(), "8".to_string()),
                ("MM_SYMBOLS".to_string(), "ETHUSDT".to_string()),
                ("MM_SYMBOLS_EXTRA".to_string(), "ADAUSDT,NEARUSDT".to_string()),
            ]
        );
    }

    #[test]
    fn effective_env_hides_secrets_and_marks_overrides() {
        let file = vec![
            ("DELTA_API_KEY".to_string(), "k".to_string()),
            ("MM_SYMBOLS".to_string(), "ETHUSDT".to_string()),
            ("MM_HALF_SPREAD_BPS".to_string(), "8".to_string()),
            ("RUST_LOG".to_string(), "info".to_string()),
        ];
        let eff = effective_env(&file, Some(&json!({"MM_HALF_SPREAD_BPS": 6})));
        assert!(!eff.contains_key("DELTA_API_KEY"));
        assert_eq!(eff["MM_SYMBOLS"], ("ETHUSDT".to_string(), "env_file"));
        assert_eq!(eff["MM_HALF_SPREAD_BPS"], ("6".to_string(), "override"));
        assert!(eff.contains_key("RUST_LOG"));
    }
}
