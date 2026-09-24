mod auth;
mod book;
mod market;
mod rest;
mod trade_ws;
mod ws;

pub use auth::BybitCredentials;
pub use book::{BybitBook, OrderbookMaintainer};
pub use market::BybitPublic;
pub use rest::BybitRest;
pub use trade_ws::BybitTradeWs;
pub use ws::BybitPrivateWs;

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum BybitEnvironment {
    Mainnet,
    Testnet,
}

impl BybitEnvironment {
    pub fn rest_base(&self) -> &'static str {
        match self {
            Self::Mainnet => "https://api.bybit.com",
            Self::Testnet => "https://api-testnet.bybit.com",
        }
    }

    pub fn ws_public(&self) -> &'static str {
        match self {
            Self::Mainnet => "wss://stream.bybit.com/v5/public/linear",
            Self::Testnet => "wss://stream-testnet.bybit.com/v5/public/linear",
        }
    }

    pub fn ws_private(&self) -> &'static str {
        match self {
            Self::Mainnet => "wss://stream.bybit.com/v5/private",
            Self::Testnet => "wss://stream-testnet.bybit.com/v5/private",
        }
    }

    pub fn ws_trade(&self) -> &'static str {
        match self {
            Self::Mainnet => "wss://stream.bybit.com/v5/trade",
            Self::Testnet => "wss://stream-testnet.bybit.com/v5/trade",
        }
    }
}
