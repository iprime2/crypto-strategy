//! Per-strategy venue plumbing. Each strategy runs against one Delta environment (demo or
//! mainnet) and gets its own market proxy, venue sync state and bot telemetry, so demo and
//! real-money strategies can run side by side without sharing prices, orders or keys.

use std::collections::BTreeMap;
use std::path::{Path, PathBuf};
use std::sync::Arc;

use serde_json::Value;

use crate::delta::VenueEnv;
use crate::market::Market;
use crate::supervisor::load_env_file;
use crate::sync::{new_venue_state, SharedVenue};
use crate::telemetry::{new_telemetry, Telemetry};

#[derive(Clone)]
pub struct StrategyRuntime {
    pub id: String,
    pub env: VenueEnv,
    /// Absolute path of the strategy's settings profile, if it has one.
    pub profile: Option<PathBuf>,
    pub market: Market,
    pub venue: SharedVenue,
    pub telemetry: Telemetry,
}

impl StrategyRuntime {
    /// Profile lines (`KEY=value`), or None when the strategy has no profile.
    pub fn profile_pairs(&self) -> Option<Vec<(String, String)>> {
        self.profile.as_deref().map(load_env_file)
    }
}

pub type Runtimes = Arc<BTreeMap<String, StrategyRuntime>>;

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct StrategySpec {
    pub id: String,
    pub env: VenueEnv,
    /// Relative to cex-mm/, as stored in `strategies.profile`.
    pub profile: Option<String>,
}

/// Strategy rows (`id`, `env`, `profile`) to specs. A row with an unknown env is skipped rather
/// than guessed. Without a database (no rows) the demo `mm` strategy still gets a runtime.
pub fn specs_from_rows(rows: &[Value]) -> Vec<StrategySpec> {
    let mut specs: Vec<StrategySpec> = rows
        .iter()
        .filter_map(|r| {
            let id = r.get("id")?.as_str()?.to_string();
            let env_name = r.get("env").and_then(|v| v.as_str()).unwrap_or("demo");
            let Some(env) = VenueEnv::parse(env_name) else {
                tracing::warn!(strategy = %id, env = env_name, "unknown strategy env; skipped");
                return None;
            };
            let profile = r
                .get("profile")
                .and_then(|v| v.as_str())
                .filter(|s| !s.is_empty())
                .map(str::to_string);
            Some(StrategySpec { id, env, profile })
        })
        .collect();
    if specs.is_empty() {
        specs.push(StrategySpec { id: "mm".into(), env: VenueEnv::Demo, profile: None });
    }
    specs
}

/// One market proxy per environment (public data and caches are shared), fresh venue state and
/// telemetry per strategy.
pub fn build_runtimes(specs: &[StrategySpec], cex_mm_root: &Path) -> Runtimes {
    let demo = Market::new(VenueEnv::Demo.base());
    let mainnet = Market::new(VenueEnv::Mainnet.base());
    let map = specs
        .iter()
        .map(|s| {
            let market = match s.env {
                VenueEnv::Demo => demo.clone(),
                VenueEnv::Mainnet => mainnet.clone(),
            };
            let rt = StrategyRuntime {
                id: s.id.clone(),
                env: s.env,
                profile: s.profile.as_ref().map(|p| cex_mm_root.join(p)),
                market,
                venue: new_venue_state(),
                telemetry: new_telemetry(),
            };
            (s.id.clone(), rt)
        })
        .collect();
    Arc::new(map)
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::json;

    #[test]
    fn rows_map_to_specs_with_env_and_profile() {
        let rows = [
            json!({"id": "mm", "env": "demo", "profile": null}),
            json!({"id": "dism", "env": "mainnet", "profile": "config/dism.env"}),
            json!({"id": "odd", "env": "staging"}),
        ];
        let specs = specs_from_rows(&rows);
        assert_eq!(
            specs,
            vec![
                StrategySpec { id: "mm".into(), env: VenueEnv::Demo, profile: None },
                StrategySpec { id: "dism".into(), env: VenueEnv::Mainnet, profile: Some("config/dism.env".into()) },
            ]
        );
    }

    #[test]
    fn no_database_still_runs_the_demo_strategy() {
        assert_eq!(
            specs_from_rows(&[]),
            vec![StrategySpec { id: "mm".into(), env: VenueEnv::Demo, profile: None }]
        );
    }

    #[test]
    fn runtimes_resolve_profiles_under_the_cex_mm_root() {
        let specs = specs_from_rows(&[json!({"id": "dism", "env": "mainnet", "profile": "config/dism.env"})]);
        let rts = build_runtimes(&specs, Path::new("/srv/cex-mm"));
        let rt = &rts["dism"];
        assert_eq!(rt.env, VenueEnv::Mainnet);
        assert_eq!(rt.profile.as_deref(), Some(Path::new("/srv/cex-mm/config/dism.env")));
    }
}
