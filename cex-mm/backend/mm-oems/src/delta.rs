//! Read-only Delta REST helpers for OEMS snapshots / cancel-all on stop.

use hmac::{Hmac, Mac};
use sha2::Sha256;

type HmacSha256 = Hmac<Sha256>;

const TESTNET_BASE: &str = "https://cdn-ind.testnet.deltaex.org";
const MAINNET_BASE: &str = "https://api.india.delta.exchange";

pub fn delta_base(mm_env: Option<&str>) -> &'static str {
    match mm_env.map(|s| s.to_lowercase()).as_deref() {
        Some("mainnet" | "prod" | "production") => MAINNET_BASE,
        _ => TESTNET_BASE,
    }
}

pub fn map_delta_symbol(delta_sym: &str) -> String {
    match delta_sym.to_uppercase().as_str() {
        "BTCUSD" => "BTCUSDT".into(),
        "ETHUSD" => "ETHUSDT".into(),
        "SOLUSD" => "SOLUSDT".into(),
        other if other.ends_with("USD") && !other.ends_with("USDT") => format!("{other}T"),
        other => other.to_string(),
    }
}

pub fn sign_rest(secret: &str, method: &str, timestamp: &str, path: &str, query: &str, body: &str) -> String {
    let q = if query.is_empty() {
        String::new()
    } else if query.starts_with('?') {
        query.to_string()
    } else {
        format!("?{query}")
    };
    let pre = format!("{method}{timestamp}{path}{q}{body}");
    let mut mac = HmacSha256::new_from_slice(secret.as_bytes()).expect("hmac");
    mac.update(pre.as_bytes());
    hex::encode(mac.finalize().into_bytes())
}

#[derive(Clone)]
pub struct DeltaClient {
    http: reqwest::Client,
    base: String,
    api_key: String,
    api_secret: String,
}

impl DeltaClient {
    pub fn new(base: &str, api_key: String, api_secret: String) -> Self {
        Self {
            http: reqwest::Client::new(),
            base: base.trim_end_matches('/').to_string(),
            api_key,
            api_secret,
        }
    }

    /// Build from quote-bot/.env pairs. Returns None if key missing. Never logs secrets.
    pub fn from_env_pairs(pairs: &[(String, String)]) -> Option<Self> {
        let key = pairs
            .iter()
            .find(|(k, _)| k == "DELTA_API_KEY")
            .map(|(_, v)| v.clone())
            .filter(|v| !v.is_empty())?;
        let secret = pairs
            .iter()
            .find(|(k, _)| k == "DELTA_API_SECRET")
            .map(|(_, v)| v.clone())
            .filter(|v| !v.is_empty())?;
        let mm_env = pairs
            .iter()
            .find(|(k, _)| k == "MM_ENV")
            .map(|(_, v)| v.as_str());
        Some(Self::new(delta_base(mm_env), key, secret))
    }

    async fn signed(
        &self,
        method: reqwest::Method,
        path: &str,
        query: &str,
        body: &str,
    ) -> anyhow::Result<serde_json::Value> {
        let ts = chrono::Utc::now().timestamp().to_string();
        let sig = sign_rest(
            &self.api_secret,
            method.as_str(),
            &ts,
            path,
            query,
            body,
        );
        let q = if query.is_empty() {
            String::new()
        } else if query.starts_with('?') {
            query.to_string()
        } else {
            format!("?{query}")
        };
        let url = format!("{}{path}{q}", self.base);
        let mut req = self
            .http
            .request(method, &url)
            .header("api-key", &self.api_key)
            .header("timestamp", &ts)
            .header("signature", sig)
            .header("Accept", "application/json")
            .header("User-Agent", "mm-oems/0.1");
        if !body.is_empty() {
            req = req
                .header("Content-Type", "application/json")
                .body(body.to_string());
        }
        let resp = req.send().await?;
        let text = resp.text().await?;
        let v: serde_json::Value = serde_json::from_str(&text).unwrap_or_else(|_| {
            serde_json::json!({ "error": "non-json", "detail": text.chars().take(200).collect::<String>() })
        });
        Ok(v)
    }

    pub async fn wallet_balances(&self) -> anyhow::Result<serde_json::Value> {
        self.signed(reqwest::Method::GET, "/v2/wallet/balances", "", "")
            .await
    }

    pub async fn positions_margined(&self) -> anyhow::Result<serde_json::Value> {
        self.signed(reqwest::Method::GET, "/v2/positions/margined", "", "")
            .await
    }

    /// Best-effort cancel all open orders for a product_id.
    pub async fn cancel_all_product(&self, product_id: u64) -> anyhow::Result<()> {
        let body = serde_json::json!({ "product_id": product_id }).to_string();
        let _ = self
            .signed(reqwest::Method::DELETE, "/v2/orders/all", "", &body)
            .await?;
        Ok(())
    }

    /// Resolve product_id for an MM symbol via public products endpoint.
    pub async fn product_id_for_mm_symbol(&self, mm_symbol: &str) -> anyhow::Result<Option<u64>> {
        let upper = mm_symbol.to_uppercase();
        let delta_sym = match upper.as_str() {
            "BTCUSDT" | "BTCUSD" => "BTCUSD",
            "ETHUSDT" | "ETHUSD" => "ETHUSD",
            "SOLUSDT" | "SOLUSD" => "SOLUSD",
            other => other,
        };
        let url = format!(
            "{}/v2/products?contract_types=perpetual_futures&page_size=200",
            self.base
        );
        let resp: serde_json::Value = self
            .http
            .get(&url)
            .header("User-Agent", "mm-oems/0.1")
            .send()
            .await?
            .json()
            .await?;
        let rows = resp
            .get("result")
            .and_then(|r| r.as_array())
            .cloned()
            .unwrap_or_default();
        for row in rows {
            let sym = row.get("symbol").and_then(|s| s.as_str()).unwrap_or("");
            if sym.eq_ignore_ascii_case(delta_sym) {
                if let Some(id) = row.get("id").and_then(|i| i.as_u64()) {
                    return Ok(Some(id));
                }
            }
        }
        Ok(None)
    }
}

#[derive(Debug, Clone)]
pub struct ParsedBalance {
    pub equity: f64,
    pub available: f64,
    pub blocked_margin: f64,
}

#[derive(Debug, Clone)]
pub struct ParsedPosition {
    pub symbol: String,
    pub venue_qty: f64,
    pub entry: f64,
    pub mark: f64,
    pub unrealized: f64,
    pub realized: f64,
}

pub fn parse_usd_balance(bal: &serde_json::Value) -> ParsedBalance {
    let meta = bal.get("meta").cloned().unwrap_or(serde_json::Value::Null);
    let equity = f64_of(meta.get("net_equity"));
    let mut available = 0.0;
    let mut blocked = 0.0;
    if let Some(rows) = bal.get("result").and_then(|r| r.as_array()) {
        for row in rows {
            if row.get("asset_symbol").and_then(|s| s.as_str()) == Some("USD") {
                available = f64_of(row.get("available_balance"));
                blocked = f64_of(row.get("blocked_margin"));
                break;
            }
        }
    }
    ParsedBalance {
        equity,
        available,
        blocked_margin: blocked,
    }
}

pub fn parse_positions(pos: &serde_json::Value) -> Vec<ParsedPosition> {
    let mut out = Vec::new();
    let Some(rows) = pos.get("result").and_then(|r| r.as_array()) else {
        return out;
    };
    for row in rows {
        let prod = row.get("product").cloned().unwrap_or(serde_json::Value::Null);
        let delta_sym = prod
            .get("symbol")
            .and_then(|s| s.as_str())
            .or_else(|| row.get("product_symbol").and_then(|s| s.as_str()))
            .unwrap_or("?");
        let mm_sym = map_delta_symbol(delta_sym);
        let cv = f64_of(prod.get("contract_value")).max(0.0);
        let size = row.get("size").and_then(|v| v.as_i64()).unwrap_or(0) as f64;
        let venue_qty = size * cv;
        out.push(ParsedPosition {
            symbol: mm_sym,
            venue_qty,
            entry: f64_of(row.get("entry_price")),
            mark: f64_of(row.get("mark_price")),
            unrealized: f64_of(row.get("unrealized_pnl")),
            realized: f64_of(row.get("realized_pnl")),
        });
    }
    out
}

fn f64_of(v: Option<&serde_json::Value>) -> f64 {
    match v {
        Some(serde_json::Value::Number(n)) => n.as_f64().unwrap_or(0.0),
        Some(serde_json::Value::String(s)) => s.parse().unwrap_or(0.0),
        _ => 0.0,
    }
}
