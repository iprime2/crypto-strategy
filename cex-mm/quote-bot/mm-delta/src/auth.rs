use hmac::{Hmac, Mac};
use sha2::Sha256;

type HmacSha256 = Hmac<Sha256>;

#[derive(Clone)]
pub struct DeltaCredentials {
    pub api_key: String,
    pub api_secret: String,
}

impl DeltaCredentials {
    pub fn from_env() -> Option<Self> {
        let api_key = std::env::var("DELTA_API_KEY").ok()?;
        let api_secret = std::env::var("DELTA_API_SECRET").ok()?;
        if api_key.is_empty() || api_secret.is_empty() {
            return None;
        }
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
