use hmac::{Hmac, Mac};
use sha2::Sha256;

use crate::DeltaEnvironment;

type HmacSha256 = Hmac<Sha256>;

#[derive(Clone)]
pub struct DeltaCredentials {
    pub api_key: String,
    pub api_secret: String,
}

/// Env var names of each environment's key and secret, in order of preference. Demo reads
/// `DELTA_DEMO_API_*`, then the older `DELTA_API_*`; mainnet reads only `DELTA_MAINNET_API_*`.
pub fn key_vars(env: DeltaEnvironment) -> &'static [(&'static str, &'static str)] {
    match env {
        DeltaEnvironment::DemoIndia => &[
            ("DELTA_DEMO_API_KEY", "DELTA_DEMO_API_SECRET"),
            ("DELTA_API_KEY", "DELTA_API_SECRET"),
        ],
        DeltaEnvironment::IndiaMainnet => &[("DELTA_MAINNET_API_KEY", "DELTA_MAINNET_API_SECRET")],
    }
}

impl DeltaCredentials {
    /// Demo keys (`DELTA_DEMO_API_KEY` / `DELTA_DEMO_API_SECRET`, or `DELTA_API_*`), for the demo
    /// smoke examples.
    pub fn from_env() -> Option<Self> {
        Self::from_env_for(DeltaEnvironment::DemoIndia)
    }

    /// Keys for `env`. Mainnet reads only `DELTA_MAINNET_API_KEY` / `DELTA_MAINNET_API_SECRET`,
    /// so demo keys can never place a real-money order.
    pub fn from_env_for(env: DeltaEnvironment) -> Option<Self> {
        Self::from_lookup(env, |k| std::env::var(k).ok())
    }

    /// The first pair in `key_vars(env)` with both values set; key and secret never mix pairs.
    pub fn from_lookup(env: DeltaEnvironment, get: impl Fn(&str) -> Option<String>) -> Option<Self> {
        let set = |name: &str| get(name).filter(|v| !v.is_empty());
        key_vars(env).iter().find_map(|(key_var, secret_var)| {
            Some(Self { api_key: set(key_var)?, api_secret: set(secret_var)? })
        })
    }

    pub fn sign(&self, message: &str) -> String {
        let mut mac =
            HmacSha256::new_from_slice(self.api_secret.as_bytes()).expect("hmac key");
        mac.update(message.as_bytes());
        hex::encode(mac.finalize().into_bytes())
    }

    /// REST: `method + timestamp + path + query_string + body` (query includes leading `?` if any).
    pub fn sign_rest(
        &self,
        method: &str,
        timestamp: &str,
        path: &str,
        query_string: &str,
        body: &str,
    ) -> String {
        let pre = format!("{method}{timestamp}{path}{query_string}{body}");
        self.sign(&pre)
    }

    /// Private WS key-auth: `GET` + timestamp + `/live`
    pub fn sign_ws_auth(&self, timestamp: &str) -> String {
        self.sign(&format!("GET{timestamp}/live"))
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn lookup(pairs: &'static [(&'static str, &'static str)]) -> impl Fn(&str) -> Option<String> {
        move |k| pairs.iter().find(|(name, _)| *name == k).map(|(_, v)| v.to_string())
    }

    #[test]
    fn demo_uses_the_demo_keys() {
        let get = lookup(&[("DELTA_API_KEY", "demo-k"), ("DELTA_API_SECRET", "demo-s")]);
        let c = DeltaCredentials::from_lookup(DeltaEnvironment::DemoIndia, get).unwrap();
        assert_eq!(c.api_key, "demo-k");
    }

    #[test]
    fn demo_prefers_the_delta_demo_names() {
        let get = lookup(&[
            ("DELTA_DEMO_API_KEY", "new-k"),
            ("DELTA_DEMO_API_SECRET", "new-s"),
            ("DELTA_API_KEY", "old-k"),
            ("DELTA_API_SECRET", "old-s"),
        ]);
        let c = DeltaCredentials::from_lookup(DeltaEnvironment::DemoIndia, get).unwrap();
        assert_eq!((c.api_key.as_str(), c.api_secret.as_str()), ("new-k", "new-s"));
    }

    #[test]
    fn demo_takes_key_and_secret_from_one_pair() {
        // A half-set new pair falls back to the whole old pair, never a mix of the two.
        let get = lookup(&[
            ("DELTA_DEMO_API_KEY", "new-k"),
            ("DELTA_API_KEY", "old-k"),
            ("DELTA_API_SECRET", "old-s"),
        ]);
        let c = DeltaCredentials::from_lookup(DeltaEnvironment::DemoIndia, get).unwrap();
        assert_eq!((c.api_key.as_str(), c.api_secret.as_str()), ("old-k", "old-s"));
        let half = lookup(&[("DELTA_DEMO_API_KEY", "new-k"), ("DELTA_API_SECRET", "old-s")]);
        assert!(DeltaCredentials::from_lookup(DeltaEnvironment::DemoIndia, half).is_none());
    }

    #[test]
    fn mainnet_never_falls_back_to_the_demo_keys() {
        let demo_only = lookup(&[
            ("DELTA_DEMO_API_KEY", "demo-k"),
            ("DELTA_DEMO_API_SECRET", "demo-s"),
            ("DELTA_API_KEY", "demo-k"),
            ("DELTA_API_SECRET", "demo-s"),
        ]);
        assert!(DeltaCredentials::from_lookup(DeltaEnvironment::IndiaMainnet, demo_only).is_none());
        let both = lookup(&[
            ("DELTA_API_KEY", "demo-k"),
            ("DELTA_API_SECRET", "demo-s"),
            ("DELTA_MAINNET_API_KEY", "real-k"),
            ("DELTA_MAINNET_API_SECRET", "real-s"),
        ]);
        let c = DeltaCredentials::from_lookup(DeltaEnvironment::IndiaMainnet, both).unwrap();
        assert_eq!((c.api_key.as_str(), c.api_secret.as_str()), ("real-k", "real-s"));
    }

    #[test]
    fn empty_keys_count_as_missing() {
        let get = lookup(&[("DELTA_MAINNET_API_KEY", ""), ("DELTA_MAINNET_API_SECRET", "x")]);
        assert!(DeltaCredentials::from_lookup(DeltaEnvironment::IndiaMainnet, get).is_none());
    }
}
