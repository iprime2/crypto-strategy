//! Reject strategy config bodies that embed API secrets, and config overrides of the keys that must come from
//! the profile file only.

const FORBIDDEN_KEYS: &[&str] = &[
    "delta_api_key",
    "api_key",
    "secret",
    "DELTA_API_SECRET",
    "delta_api_secret",
    "delta_demo_api_key",
    "delta_demo_api_secret",
];

/// Env-name prefixes the UI and API may not override: the anchored fair's weight, live flag and basis source
/// are live-safety settings that `scripts/live.sh` checks in the profile file (plans/live-basis.plan.md).
const PROFILE_ONLY_PREFIXES: &[&str] = &["MM_FAIR_ANCHOR", "MM_BASIS_"];

/// Returns the first top-level key of `body` whose bot env name starts with a profile-only prefix.
pub fn find_profile_only_key(body: &serde_json::Value) -> Option<String> {
    let map = body.as_object()?;
    map.keys()
        .find(|k| {
            let name = crate::supervisor::env_key_for(k).unwrap_or_else(|| k.to_ascii_uppercase());
            PROFILE_ONLY_PREFIXES.iter().any(|p| name.starts_with(p))
        })
        .cloned()
}

/// Returns the forbidden key name if `body` (object or nested) contains a secret field.
pub fn find_forbidden_secret_key(body: &serde_json::Value) -> Option<String> {
    match body {
        serde_json::Value::Object(map) => {
            for (k, v) in map {
                if is_forbidden_key(k) {
                    return Some(k.clone());
                }
                if let Some(found) = find_forbidden_secret_key(v) {
                    return Some(found);
                }
            }
            None
        }
        serde_json::Value::Array(arr) => {
            for v in arr {
                if let Some(found) = find_forbidden_secret_key(v) {
                    return Some(found);
                }
            }
            None
        }
        _ => None,
    }
}

fn is_forbidden_key(key: &str) -> bool {
    FORBIDDEN_KEYS
        .iter()
        .any(|f| f.eq_ignore_ascii_case(key) || *f == key)
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::json;

    #[test]
    fn rejects_delta_api_key() {
        let body = json!({"delta_api_key": "x", "spread_bps": 5});
        assert_eq!(
            find_forbidden_secret_key(&body).as_deref(),
            Some("delta_api_key")
        );
    }

    #[test]
    fn rejects_api_key_and_secret() {
        assert!(find_forbidden_secret_key(&json!({"api_key": "k"})).is_some());
        assert!(find_forbidden_secret_key(&json!({"secret": "s"})).is_some());
        assert!(find_forbidden_secret_key(&json!({"DELTA_DEMO_API_SECRET": "s"})).is_some());
        assert!(find_forbidden_secret_key(&json!({"delta_demo_api_key": "k"})).is_some());
        assert!(find_forbidden_secret_key(&json!({"DELTA_API_SECRET": "s"})).is_some());
    }

    #[test]
    fn rejects_nested_secret() {
        let body = json!({"venue": {"delta_api_secret": "nope"}});
        assert!(find_forbidden_secret_key(&body).is_some());
    }

    #[test]
    fn anchor_and_basis_keys_are_profile_only() {
        for k in ["MM_FAIR_ANCHOR_WEIGHT", "MM_FAIR_ANCHOR_WEIGHT_ADAUSDT", "MM_FAIR_ANCHOR_LIVE", "MM_BASIS_SOURCE", "mm_basis_depth_qty_adausdt"] {
            let body = json!({"spread_bps": 5, k: "depth"});
            assert_eq!(find_profile_only_key(&body).as_deref(), Some(k), "{k}");
        }
        assert_eq!(find_profile_only_key(&json!({"spread_bps": 5, "MM_BINANCE_STALE_MS": 5000})), None);
        assert_eq!(find_profile_only_key(&json!([1, 2])), None);
    }

    #[test]
    fn allows_clean_config() {
        let body = json!({
            "spread_bps": 5,
            "symbols": ["BTCUSDT"],
            "loop_ms": 400
        });
        assert!(find_forbidden_secret_key(&body).is_none());
    }
}
