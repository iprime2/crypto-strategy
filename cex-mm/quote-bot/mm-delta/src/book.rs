use anyhow::Result;
use mm_core::BookTop;
use reqwest::Client;
use serde::Deserialize;
use tokio::sync::watch;
use tracing::warn;

use crate::products::delta_product_symbol;
use crate::DeltaEnvironment;

#[derive(Debug, Clone, Default)]
pub struct DeltaBook {
    pub top: BookTop,
}

pub struct OrderbookMaintainer {
    pub env: DeltaEnvironment,
    /// MM symbol or Delta symbol (e.g. BTCUSDT or BTCUSD).
    pub symbol: String,
}

#[derive(Debug, Deserialize)]
struct L2Response {
    success: Option<bool>,
    result: Option<L2Book>,
}

#[derive(Debug, Deserialize)]
struct L2Book {
    buy: Option<Vec<L2Level>>,
    sell: Option<Vec<L2Level>>,
}

#[derive(Debug, Deserialize)]
struct L2Level {
    price: String,
    size: i64,
}

impl OrderbookMaintainer {
    pub async fn run(&self, tx: watch::Sender<BookTop>) -> Result<()> {
        let delta_sym = delta_product_symbol(&self.symbol);
        let client = Client::new();
        let url = format!(
            "{}/v2/l2orderbook/{delta_sym}",
            self.env.rest_base()
        );
        loop {
            match client
                .get(&url)
                .header("User-Agent", "mm-delta/0.1")
                .send()
                .await
            {
                Ok(resp) => match resp.json::<L2Response>().await {
                    Ok(parsed) => {
                        if let Some(book) = parsed.result {
                            let mut top = BookTop::default();
                            if let Some(bids) = book.buy {
                                if let Some(lvl) = bids.first() {
                                    top.best_bid = lvl.price.parse().unwrap_or(0.0);
                                    top.bid_qty = lvl.size as f64;
                                }
                            }
                            if let Some(asks) = book.sell {
                                if let Some(lvl) = asks.first() {
                                    top.best_ask = lvl.price.parse().unwrap_or(0.0);
                                    top.ask_qty = lvl.size as f64;
                                }
                            }
                            if top.best_bid > 0.0 && top.best_ask > top.best_bid {
                                let _ = tx.send(top);
                            }
                        }
                    }
                    Err(e) => warn!(?e, "delta l2 json"),
                },
                Err(e) => warn!(?e, "delta l2 poll"),
            }
            tokio::time::sleep(std::time::Duration::from_millis(250)).await;
        }
    }
}
