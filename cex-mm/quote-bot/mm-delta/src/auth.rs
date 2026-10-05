use hmac::{Hmac, Mac};
use sha2::Sha256;

use crate::DeltaEnvironment;

type HmacSha256 = Hmac<Sha256>;

#[derive(Clone)]
pub struct DeltaCredentials {
    pub api_key: String,
    pub api_secret: String,
}

impl DeltaCredentials {
    /// Demo keys (`DELTA_API_KEY` / `DELTA_API_SECRET`), for the demo smoke examples.
    pub fn from_env() -> Option<Self> {
        Self::from_env_for(DeltaEnvironment::DemoIndia)
    }

    /// Keys for `env`. Mainnet reads only `DELTA_MAINNET_API_KEY` / `DELTA_MAINNET_API_SECRET`,
    /// so demo keys can never place a real-money order.
    pub fn from_env_for(env: DeltaEnvironment) -> Option<Self> {
        Self::from_lookup(env, |k| std::env::var(k).ok())
    }

    pub fn from_lookup(env: DeltaEnvironment, get: impl Fn(&str) -> Option<String>) -> Option<Self> {
        let (key_var, secret_var) = match env {
            DeltaEnvironment::DemoIndia => ("DELTA_API_KEY", "DELTA_API_SECRET"),
            DeltaEnvironment::IndiaMainnet => ("DELTA_MAINNET_API_KEY", "DELTA_MAINNET_API_SECRET"),
        };
        let api_key = get(key_var).filter(|v| !v.is_empty())?;
        let api_secret = get(secret_var).filter(|v| !v.is_empty())?;
        Some(Self { api_key, api_secret })
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
    fn mainnet_never_falls_back_to_the_demo_keys() {
        let demo_only = lookup(&[("DELTA_API_KEY", "demo-k"), ("DELTA_API_SECRET", "demo-s")]);
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
