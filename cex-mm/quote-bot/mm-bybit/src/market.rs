use anyhow::{Context, Result};
use reqwest::Client;
use serde::Deserialize;

use crate::BybitEnvironment;

#[derive(Clone)]
pub struct BybitPublic {
    client: Client,
    env: BybitEnvironment,
}

#[derive(Debug, Deserialize)]
struct ApiResponse<T> {
    #[serde(rename = "retCode")]
    ret_code: i32,
    #[serde(rename = "retMsg")]
    ret_msg: String,
    result: Option<T>,
}

#[derive(Debug, Deserialize)]
struct TickersResult {
    list: Vec<TickerRow>,
}

#[derive(Debug, Deserialize)]
struct TickerRow {
    symbol: String,
    #[serde(rename = "turnover24h")]
    turnover_24h: String,
}

#[derive(Debug, Deserialize)]
struct InstrumentsResult {
    list: Vec<InstrumentStatusRow>,
    #[serde(rename = "nextPageCursor")]
    next_page_cursor: Option<String>,
}

#[derive(Debug, Deserialize)]
struct InstrumentStatusRow {
    symbol: String,
    status: String,
    #[serde(rename = "quoteCoin")]
    quote_coin: String,
}

impl BybitPublic {
    pub fn new(env: BybitEnvironment) -> Self {
        Self {
            client: Client::new(),
            env,
        }
    }

    /// USDT-margined linear perps that are `Trading`, ranked by 24h turnover (quote USDT).
    pub async fn top_liquid_usdt_linear(&self, limit: usize) -> Result<Vec<String>> {
        let trading = self.trading_usdt_linear_symbols().await?;
        let mut ranked = self.rank_by_turnover(trading).await?;
        ranked.truncate(limit);
        Ok(ranked)
    }

    async fn trading_usdt_linear_symbols(&self) -> Result<Vec<String>> {
        let mut out = Vec::new();
        let mut cursor: Option<String> = None;
        loop {
            let mut url = format!(
                "{}/v5/market/instruments-info?category=linear&limit=1000",
                self.env.rest_base()
            );
            if let Some(c) = &cursor {
                url.push_str(&format!("&cursor={c}"));
            }
            let resp: ApiResponse<InstrumentsResult> = self
                .client
                .get(&url)
                .send()
                .await
                .context("instruments-info")?
                .json()
                .await?;
            if resp.ret_code != 0 {
                anyhow::bail!("instruments-info {}: {}", resp.ret_code, resp.ret_msg);
            }
            let Some(page) = resp.result else { break };
            for row in page.list {
                if row.status.eq_ignore_ascii_case("Trading")
                    && row.quote_coin.eq_ignore_ascii_case("USDT")
                    && row.symbol.ends_with("USDT")
                {
                    out.push(row.symbol);
                }
            }
            cursor = page.next_page_cursor.filter(|c| !c.is_empty());
            if cursor.is_none() {
                break;
            }
        }
        Ok(out)
    }

    async fn rank_by_turnover(&self, symbols: Vec<String>) -> Result<Vec<String>> {
        let url = format!(
            "{}/v5/market/tickers?category=linear",
            self.env.rest_base()
        );
        let resp: ApiResponse<TickersResult> = self
            .client
            .get(&url)
            .send()
            .await
            .context("tickers")?
            .json()
            .await?;
        if resp.ret_code != 0 {
            anyhow::bail!("tickers {}: {}", resp.ret_code, resp.ret_msg);
        }
        let list = resp.result.map(|r| r.list).unwrap_or_default();
        let allowed: std::collections::HashSet<_> = symbols.into_iter().collect();
        let mut rows: Vec<(String, f64)> = list
            .into_iter()
            .filter(|t| allowed.contains(&t.symbol))
            .filter_map(|t| {
                let turnover: f64 = t.turnover_24h.parse().ok()?;
                if turnover.is_finite() && turnover > 0.0 {
                    Some((t.symbol, turnover))
                } else {
                    None
                }
            })
            .collect();
        rows.sort_by(|a, b| b.1.partial_cmp(&a.1).unwrap_or(std::cmp::Ordering::Equal));
        Ok(rows.into_iter().map(|(s, _)| s).collect())
    }
}

