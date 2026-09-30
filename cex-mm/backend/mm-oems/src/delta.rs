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
            http: http_client(),
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

    pub fn base(&self) -> &str {
        &self.base
    }

    /// Open and pending orders across all products (newest first).
    pub async fn open_orders(&self) -> anyhow::Result<serde_json::Value> {
        self.signed(reqwest::Method::GET, "/v2/orders", "states=open,pending&page_size=100", "")
            .await
    }

    /// One page of account fills, newest first. `after` is the cursor from `meta.after`.
    pub async fn fills_page(&self, page_size: u32, after: Option<&str>) -> anyhow::Result<serde_json::Value> {
        let mut query = format!("page_size={page_size}");
        if let Some(cursor) = after {
            query.push_str("&after=");
            query.push_str(&urlencode(cursor));
        }
        self.signed(reqwest::Method::GET, "/v2/fills", &query, "").await
    }

    /// Reduce-only market order (used only by the operator's close-position action).
    pub async fn place_reduce_only_market(
        &self,
        product_id: u64,
        side: &str,
        size_contracts: i64,
    ) -> anyhow::Result<serde_json::Value> {
        let body = serde_json::json!({
            "product_id": product_id,
            "size": size_contracts,
            "side": side,
            "order_type": "market_order",
            "reduce_only": true,
        })
        .to_string();
        self.signed(reqwest::Method::POST, "/v2/orders", "", &body).await
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
        let body = serde_json::json!({
            "product_id": product_id,
            "cancel_limit_orders": true,
            "cancel_stop_orders": true
        })
        .to_string();
        let _ = self
            .signed(reqwest::Method::DELETE, "/v2/orders/all", "", &body)
            .await?;
        Ok(())
    }

    /// Resolve product_id for an MM symbol via the public (paginated) product catalog.
    pub async fn product_id_for_mm_symbol(&self, mm_symbol: &str) -> anyhow::Result<Option<u64>> {
        let catalog = fetch_catalog(&self.http, &self.base).await?;
        Ok(catalog.get(&delta_symbol_for(mm_symbol)).map(|p| p.product_id))
    }
}

/// Shared HTTP client: the Delta demo API can take several seconds, but a signed
/// request older than ~10 s is rejected, so do not wait longer than that.
pub fn http_client() -> reqwest::Client {
    reqwest::Client::builder()
        .timeout(std::time::Duration::from_secs(9))
        .user_agent("mm-oems/0.2")
        .build()
        .unwrap_or_else(|_| reqwest::Client::new())
}

fn urlencode(s: &str) -> String {
    s.bytes()
        .map(|b| match b {
            b'A'..=b'Z' | b'a'..=b'z' | b'0'..=b'9' | b'-' | b'_' | b'.' | b'~' => (b as char).to_string(),
            _ => format!("%{b:02X}"),
        })
        .collect()
}

/// MM symbol (`ETHUSDT`) → Delta product symbol (`ETHUSD`).
pub fn delta_symbol_for(mm_symbol: &str) -> String {
    let upper = mm_symbol.trim().to_uppercase().replace(['/', '-'], "");
    match upper.strip_suffix("USDT") {
        Some(base) => format!("{base}USD"),
        None => upper,
    }
}

#[derive(Debug, Clone)]
pub struct ProductInfo {
    pub product_id: u64,
    pub symbol: String,
    pub tick_size: f64,
    pub contract_value: f64,
}

/// All live perpetuals keyed by Delta symbol. Mainnet lists 220+, so follow `meta.after`.
pub async fn fetch_catalog(
    http: &reqwest::Client,
    base: &str,
) -> anyhow::Result<std::collections::HashMap<String, ProductInfo>> {
    let mut out = std::collections::HashMap::new();
    let mut after: Option<String> = None;
    for _ in 0..20 {
        let mut url = format!("{base}/v2/products?contract_types=perpetual_futures&page_size=200");
        if let Some(c) = &after {
            url.push_str("&after=");
            url.push_str(&urlencode(c));
        }
        let resp: serde_json::Value = http.get(&url).send().await?.json().await?;
        let rows = resp.get("result").and_then(|r| r.as_array()).cloned().unwrap_or_default();
        for row in &rows {
            if let Some(p) = parse_product(row) {
                out.insert(p.symbol.clone(), p);
            }
        }
        after = resp
            .get("meta")
            .and_then(|m| m.get("after"))
            .and_then(|a| a.as_str())
            .map(|s| s.to_string());
        if after.is_none() || rows.is_empty() {
            break;
        }
    }
    Ok(out)
}

pub fn parse_product(row: &serde_json::Value) -> Option<ProductInfo> {
    Some(ProductInfo {
        product_id: row.get("id")?.as_u64()?,
        symbol: row.get("symbol")?.as_str()?.to_string(),
        tick_size: f64_of(row.get("tick_size")),
        contract_value: f64_of(row.get("contract_value")),
    })
}

/// A resting order as the venue reports it; sizes in base units.
#[derive(Debug, Clone, serde::Serialize)]
pub struct VenueOrder {
    pub id: String,
    pub client_order_id: Option<String>,
    pub symbol: String,
    pub side: String,
    pub price: f64,
    pub size: f64,
    pub unfilled: f64,
    pub state: String,
    pub order_type: String,
    pub reduce_only: bool,
    pub post_only: Option<bool>,
    pub created_at: Option<String>,
    pub updated_at: Option<String>,
}

pub fn parse_open_orders(v: &serde_json::Value) -> Vec<VenueOrder> {
    let Some(rows) = v.get("result").and_then(|r| r.as_array()) else {
        return Vec::new();
    };
    rows.iter()
        .map(|o| {
            let cv = f64_of(o.get("product").and_then(|p| p.get("contract_value"))).max(0.0);
            let cv = if cv > 0.0 { cv } else { 1.0 };
            let delta_sym = o
                .get("product_symbol")
                .and_then(|s| s.as_str())
                .unwrap_or("?");
            VenueOrder {
                id: o.get("id").map(|i| i.to_string()).unwrap_or_default(),
                client_order_id: o
                    .get("client_order_id")
                    .and_then(|s| s.as_str())
                    .map(|s| s.to_string()),
                symbol: map_delta_symbol(delta_sym),
                side: o.get("side").and_then(|s| s.as_str()).unwrap_or("").to_string(),
                price: f64_of(o.get("limit_price")),
                size: f64_of(o.get("size")) * cv,
                unfilled: f64_of(o.get("unfilled_size")) * cv,
                state: o.get("state").and_then(|s| s.as_str()).unwrap_or("").to_string(),
                order_type: o
                    .get("order_type")
                    .and_then(|s| s.as_str())
                    .unwrap_or("")
                    .to_string(),
                reduce_only: o.get("reduce_only").and_then(|b| b.as_bool()).unwrap_or(false),
                post_only: o.get("post_only").and_then(|b| b.as_bool()),
                created_at: o.get("created_at").and_then(|s| s.as_str()).map(|s| s.to_string()),
                updated_at: o.get("updated_at").and_then(|s| s.as_str()).map(|s| s.to_string()),
            }
        })
        .collect()
}

/// One account fill from `/v2/fills`; qty in base units.
#[derive(Debug, Clone, PartialEq)]
pub struct VenueFill {
    pub id: String,
    pub order_id: Option<String>,
    pub symbol: String,
    pub side: String,
    pub role: String,
    pub price: f64,
    pub qty: f64,
    pub fee: f64,
    pub order_price: f64,
    pub mark: f64,
    pub created_at: chrono::DateTime<chrono::Utc>,
}

pub fn parse_fill(row: &serde_json::Value) -> Option<VenueFill> {
    let id = match row.get("id")? {
        serde_json::Value::String(s) => s.clone(),
        other => other.to_string(),
    };
    let cv = f64_of(row.get("product").and_then(|p| p.get("contract_value")));
    let price = f64_of(row.get("price"));
    let meta = row.get("meta_data");
    let created_at = chrono::DateTime::parse_from_rfc3339(row.get("created_at")?.as_str()?)
        .ok()?
        .with_timezone(&chrono::Utc);
    let order_price = f64_of(meta.and_then(|m| m.get("order_price")));
    Some(VenueFill {
        id,
        order_id: row.get("order_id").and_then(|v| match v {
            serde_json::Value::String(s) => Some(s.clone()),
            serde_json::Value::Number(n) => Some(n.to_string()),
            _ => None,
        }),
        symbol: map_delta_symbol(row.get("product_symbol").and_then(|s| s.as_str()).unwrap_or("?")),
        side: row.get("side").and_then(|s| s.as_str()).unwrap_or("").to_string(),
        role: row.get("role").and_then(|s| s.as_str()).unwrap_or("").to_string(),
        price,
        qty: f64_of(row.get("size")) * if cv > 0.0 { cv } else { 1.0 },
        fee: f64_of(row.get("commission")),
        order_price: if order_price > 0.0 { order_price } else { price },
        mark: f64_of(meta.and_then(|m| m.get("mark"))),
        created_at,
    })
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
    pub liq_price: Option<f64>,
    pub margin: Option<f64>,
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
            liq_price: opt_f64(row.get("liquidation_price")),
            margin: opt_f64(row.get("margin")),
        });
    }
    out
}

fn opt_f64(v: Option<&serde_json::Value>) -> Option<f64> {
    match v {
        Some(serde_json::Value::Null) | None => None,
        other => Some(f64_of(other)).filter(|x| *x != 0.0),
    }
}

pub fn f64_of(v: Option<&serde_json::Value>) -> f64 {
    match v {
        Some(serde_json::Value::Number(n)) => n.as_f64().unwrap_or(0.0),
        Some(serde_json::Value::String(s)) => s.parse().unwrap_or(0.0),
        _ => 0.0,
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::json;

    #[test]
    fn delta_symbol_maps_usdt_to_usd() {
        assert_eq!(delta_symbol_for("ETHUSDT"), "ETHUSD");
        assert_eq!(delta_symbol_for("adausdt"), "ADAUSD");
        assert_eq!(delta_symbol_for("BTCUSD"), "BTCUSD");
    }

    #[test]
    fn open_orders_convert_contracts_to_base() {
        let v = json!({"result": [{
            "id": 2173974807u64, "client_order_id": "mm-ETHUSDT-ask-1", "product_symbol": "ETHUSD",
            "side": "sell", "size": 2, "unfilled_size": 1, "limit_price": "2738.2", "state": "open",
            "order_type": "limit_order", "post_only": null, "reduce_only": false,
            "product": {"contract_value": "0.01"}
        }]});
        let orders = parse_open_orders(&v);
        assert_eq!(orders.len(), 1);
        let o = &orders[0];
        assert_eq!(o.id, "2173974807");
        assert_eq!(o.symbol, "ETHUSDT");
        assert!((o.size - 0.02).abs() < 1e-12);
        assert!((o.unfilled - 0.01).abs() < 1e-12);
        assert!((o.price - 2738.2).abs() < 1e-9);
        assert_eq!(o.post_only, None);
    }

    #[test]
    fn fill_parses_role_fee_and_base_qty() {
        let row = json!({
            "id": "f9af", "order_id": "2173959397", "product_symbol": "ETHUSD", "side": "buy",
            "role": "maker", "price": "2718.95", "size": "1", "commission": "0.00577505",
            "created_at": "2026-09-29T09:56:19.664975Z",
            "product": {"contract_value": "0.01"},
            "meta_data": {"order_price": "2718.95", "mark": "2718.91"}
        });
        let f = parse_fill(&row).expect("fill");
        assert_eq!(f.symbol, "ETHUSDT");
        assert_eq!(f.role, "maker");
        assert!((f.qty - 0.01).abs() < 1e-12);
        assert!((f.fee - 0.00577505).abs() < 1e-12);
        assert!((f.mark - 2718.91).abs() < 1e-9);
        assert_eq!(f.order_id.as_deref(), Some("2173959397"));
    }

    #[test]
    fn positions_carry_liquidation_price_when_present() {
        let v = json!({"result": [{
            "product": {"symbol": "ETHUSD", "contract_value": "0.01"}, "size": -1,
            "entry_price": "2740.4", "mark_price": "2734.1", "unrealized_pnl": "0.06",
            "realized_pnl": "0", "liquidation_price": "3100.5", "margin": "5.48"
        }]});
        let p = &parse_positions(&v)[0];
        assert!((p.venue_qty + 0.01).abs() < 1e-12);
        assert_eq!(p.liq_price, Some(3100.5));
        assert_eq!(p.margin, Some(5.48));
    }
}
