use anyhow::Result;
use mm_bybit::BybitRest;
use mm_delta::DeltaRest;

/// Quoting venue REST surface used by the MM loop (Bybit or Delta).
#[derive(Clone)]
pub enum QuotingRest {
    Bybit(BybitRest),
    Delta(DeltaRest),
}

impl QuotingRest {
    pub async fn get_instrument(&self, symbol: &str) -> Result<(f64, f64, f64)> {
        match self {
            Self::Bybit(r) => r.get_instrument(symbol).await,
            Self::Delta(r) => r.get_instrument(symbol).await,
        }
    }

    pub async fn get_position(&self, symbol: &str) -> Result<f64> {
        match self {
            Self::Bybit(r) => r.get_position(symbol).await,
            Self::Delta(r) => r.get_position(symbol).await,
        }
    }

    pub async fn cancel_all(&self, symbol: &str) -> Result<()> {
        match self {
            Self::Bybit(r) => r.cancel_all(symbol).await,
            Self::Delta(r) => r.cancel_all(symbol).await,
        }
    }

    pub async fn get_funding_carry_bps(&self, symbol: &str, position: f64) -> Result<f64> {
        match self {
            Self::Bybit(r) => r.get_funding_carry_bps(symbol, position).await,
            Self::Delta(r) => r.get_funding_carry_bps(symbol, position).await,
        }
    }

    pub async fn place_limit_post_only(
        &self,
        symbol: &str,
        side: &str,
        qty: f64,
        price: f64,
        link_id: &str,
    ) -> Result<Option<u64>> {
        match self {
            Self::Bybit(r) => r
                .place_limit_post_only(symbol, side, qty, price, link_id)
                .await
                .map(|_| None),
            Self::Delta(r) => {
                r.place_limit_post_only(symbol, side, qty, price, link_id)
                    .await
            }
        }
    }

    pub async fn edit_post_only(
        &self,
        symbol: &str,
        order_id: u64,
        qty: f64,
        price: f64,
    ) -> Result<()> {
        match self {
            Self::Bybit(_) => anyhow::bail!("edit by order id is Delta-only"),
            Self::Delta(r) => r.edit_post_only(symbol, order_id, qty, price).await,
        }
    }

    /// Whether a failed order call may still have reached the venue (`mm_delta::outcome_unknown`). Bybit keeps
    /// treating every failed place as not placed, as before.
    pub fn outcome_unknown(&self, err: &anyhow::Error) -> bool {
        match self {
            Self::Bybit(_) => false,
            Self::Delta(_) => mm_delta::outcome_unknown(err),
        }
    }

    pub async fn cancel_order(&self, symbol: &str, order_id: u64) -> Result<()> {
        match self {
            Self::Bybit(_) => anyhow::bail!("cancel by order id is Delta-only"),
            Self::Delta(r) => r.cancel_order(symbol, order_id).await,
        }
    }

    pub async fn place_reduce_only(
        &self,
        symbol: &str,
        side: &str,
        qty: f64,
        price: f64,
        link_id: &str,
    ) -> Result<()> {
        match self {
            Self::Bybit(r) => r.place_reduce_only(symbol, side, qty, price, link_id).await,
            Self::Delta(r) => r.place_reduce_only(symbol, side, qty, price, link_id).await,
        }
    }

    /// The venue's state of one order (`open`, `pending`, `closed`, `cancelled`) and its unfilled contracts.
    pub async fn order_state(&self, order_id: u64) -> Result<(String, i64)> {
        match self {
            Self::Bybit(_) => anyhow::bail!("order state by id is Delta-only"),
            Self::Delta(r) => r.order_state(order_id).await,
        }
    }

    pub fn cancel_before_requote(&self) -> bool {
        matches!(self, Self::Delta(_))
    }
}
