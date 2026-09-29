//! Process supervisor for quote-bot mm-bot — only signals PIDs it spawned.

use std::collections::HashMap;
use std::path::{Path, PathBuf};
use std::process::Stdio;
use std::sync::Mutex;

use serde_json::Value;

#[derive(Debug, Clone)]
pub struct StartRequest {
    pub strategy_id: String,
    pub cex_mm_root: PathBuf,
    pub quote_bot_env: PathBuf,
    pub config_body: Option<Value>,
}

#[derive(Debug, thiserror::Error)]
pub enum SupervisorError {
    #[error("quote-bot/.env is missing at {0}; refuse to start")]
    MissingEnv(String),
    #[error("strategy {0} already has a live process (pid {1})")]
    AlreadyAlive(String, u32),
    #[error("mm-bot binary not found at {0}")]
    MissingBinary(String),
    #[error("spawn failed: {0}")]
    Spawn(String),
}

/// In-memory record of PIDs this OEMS process spawned. Never signal others.
#[derive(Default)]
pub struct Supervisor {
    spawned: Mutex<HashMap<String, u32>>,
}

impl Supervisor {
    pub fn new() -> Self {
        Self::default()
    }

    pub fn recorded_pid(&self, strategy_id: &str) -> Option<u32> {
        self.spawned
            .lock()
            .ok()
            .and_then(|g| g.get(strategy_id).copied())
    }

    pub fn record_spawned(&self, strategy_id: &str, pid: u32) {
        if let Ok(mut g) = self.spawned.lock() {
            g.insert(strategy_id.to_string(), pid);
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

    /// Stop: SIGTERM only a pid this supervisor recorded for the strategy.
    /// Returns Ok(true) if signaled, Ok(false) if ignored (not ours / none).
    pub fn stop_owned(&self, strategy_id: &str) -> std::io::Result<bool> {
        let pid = match self.recorded_pid(strategy_id) {
            Some(p) => p,
            None => return Ok(false),
        };
        // Refuse to signal if map was cleared / mismatched.
        if !self.owns_pid(strategy_id, pid) {
            return Ok(false);
        }
        signal_sigterm(pid)?;
        self.clear_spawned(strategy_id);
        Ok(true)
    }

    /// Start mm-bot with env from quote-bot/.env (+ config vars). Does not touch other pids.
    pub fn start(&self, req: StartRequest) -> Result<u32, SupervisorError> {
        if !req.quote_bot_env.is_file() {
            return Err(SupervisorError::MissingEnv(
                req.quote_bot_env.display().to_string(),
            ));
        }
        if let Some(pid) = self.recorded_pid(&req.strategy_id) {
            if pid_alive(pid) {
                return Err(SupervisorError::AlreadyAlive(req.strategy_id, pid));
            }
            self.clear_spawned(&req.strategy_id);
        }

        let bin = req.cex_mm_root.join("target/debug/mm-bot");
        if !bin.is_file() {
            return Err(SupervisorError::MissingBinary(bin.display().to_string()));
        }

        let env_pairs = load_env_file(&req.quote_bot_env);
        let mut cmd = std::process::Command::new(&bin);
        cmd.args([
            "run",
            "--venue",
            "delta",
            "--env",
            "testnet",
            "--loop-ms",
            "400",
        ])
        .current_dir(&req.cex_mm_root)
        .stdin(Stdio::null())
        .stdout(Stdio::null())
        .stderr(Stdio::null())
        .env_clear();

        // Preserve minimal PATH for the child.
        if let Ok(path) = std::env::var("PATH") {
            cmd.env("PATH", path);
        }
        for (k, v) in &env_pairs {
            cmd.env(k, v);
        }
        if let Some(body) = &req.config_body {
            apply_config_env(&mut cmd, body);
        }

        let child = cmd
            .spawn()
            .map_err(|e| SupervisorError::Spawn(e.to_string()))?;
        let pid = child.id();
        self.record_spawned(&req.strategy_id, pid);
        // Detach: drop Child without waiting (process keeps running).
        std::mem::forget(child);
        Ok(pid)
    }
}

/// Badge state: a saved "running" row is stopped once its process is gone.
pub fn status_for_display(desired_state: &str, process_alive: bool) -> &'static str {
    if desired_state == "running" && !process_alive {
        "stopped"
    } else if desired_state == "running" {
        "running"
    } else {
        "stopped"
    }
}

pub fn pid_alive(pid: u32) -> bool {
    if pid == 0 {
        return false;
    }
    // kill(pid, 0) — existence check; do not send a real signal.
    let rc = unsafe { libc_kill(pid as i32, 0) };
    rc == 0
}

fn signal_sigterm(pid: u32) -> std::io::Result<()> {
    let rc = unsafe { libc_kill(pid as i32, 15) }; // SIGTERM
    if rc == 0 {
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

pub fn env_map_has_key(pairs: &[(String, String)], key: &str) -> bool {
    pairs.iter().any(|(k, v)| k == key && !v.is_empty())
}

fn apply_config_env(cmd: &mut std::process::Command, body: &Value) {
    let Some(obj) = body.as_object() else {
        return;
    };
    for (k, v) in obj {
        if crate::config_guard::find_forbidden_secret_key(&Value::Object(
            [(k.clone(), v.clone())].into_iter().collect(),
        ))
        .is_some()
        {
            continue;
        }
        let val = match v {
            Value::String(s) => s.clone(),
            Value::Number(n) => n.to_string(),
            Value::Bool(b) => b.to_string(),
            Value::Null => continue,
            other => other.to_string(),
        };
        cmd.env(k, val);
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::sync::Arc;

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
        // Simulate: we never recorded; caller might know some OS pid.
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
}
