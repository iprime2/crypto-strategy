//! Reject strategy config bodies that embed API secrets.

const FORBIDDEN_KEYS: &[&str] = &[
    "delta_api_key",
    "api_key",
    "secret",
    "DELTA_API_SECRET",
    "delta_api_secret",
];

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
        assert!(find_forbidden_secret_key(&json!({"DELTA_API_SECRET": "s"})).is_some());
    }

    #[test]
    fn rejects_nested_secret() {
        let body = json!({"venue": {"delta_api_secret": "nope"}});
        assert!(find_forbidden_secret_key(&body).is_some());
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
