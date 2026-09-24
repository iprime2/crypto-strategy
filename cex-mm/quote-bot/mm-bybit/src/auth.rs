use hmac::{Hmac, Mac};
use sha2::Sha256;

type HmacSha256 = Hmac<Sha256>;

#[derive(Clone)]
pub struct BybitCredentials {
    pub api_key: String,
    pub api_secret: String,
}

impl BybitCredentials {
    pub fn from_env() -> Option<Self> {
        let api_key = std::env::var("BYBIT_API_KEY").ok()?;
        let api_secret = std::env::var("BYBIT_API_SECRET").ok()?;
        Some(Self { api_key, api_secret })
    }

    pub fn sign(&self, payload: &str) -> String {
        let mut mac =
            HmacSha256::new_from_slice(self.api_secret.as_bytes()).expect("hmac key");
        mac.update(payload.as_bytes());
        hex::encode(mac.finalize().into_bytes())
    }

    pub fn sign_get(&self, query: &str, timestamp: &str, recv_window: &str) -> String {
        let pre = format!("{timestamp}{}{recv_window}{query}", self.api_key);
        self.sign(&pre)
    }

    pub fn sign_post(&self, body: &str, timestamp: &str, recv_window: &str) -> String {
        let pre = format!("{timestamp}{}{recv_window}{body}", self.api_key);
        self.sign(&pre)
    }
}
