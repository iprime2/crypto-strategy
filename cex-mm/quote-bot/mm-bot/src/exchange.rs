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
    ) -> Result<()> {
        match self {
            Self::Bybit(r) => {
                r.place_limit_post_only(symbol, side, qty, price, link_id)
                    .await
            }
            Self::Delta(r) => {
                r.place_limit_post_only(symbol, side, qty, price, link_id)
                    .await
            }
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

    pub fn cancel_before_requote(&self) -> bool {
        matches!(self, Self::Delta(_))
    }
}
