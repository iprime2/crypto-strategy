mod auth;
mod book;
mod depth_feed;
mod products;
mod rest;
mod ticker;
mod ws;

pub use auth::{key_vars, DeltaCredentials};
pub use book::{BookFeed, DeltaBook, OrderbookMaintainer};
pub use depth_feed::{parse_ob_l2, spawn_depth_feed, DepthRx, DepthSnapshot};
pub use products::{delta_product_symbol, mm_symbol_from_delta, ProductCatalog};
pub use rest::{funding_carry_bps, outcome_unknown, DeltaRest, FillRole, DEFAULT_REQUEST_TIMEOUT};
pub use ticker::{parse_ticker, spawn_ticker_poller, TickerPoller, TickerSnapshot};
pub use ws::{parse_user_trade, DeltaPrivateWs, PrivateFeedState, PrivateWsTimings, UserTrade};

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum DeltaEnvironment {
    /// India demo / testnet (`cdn-ind.testnet.deltaex.org`).
    DemoIndia,
    /// India production (`api.india.delta.exchange`).
    IndiaMainnet,
}

impl DeltaEnvironment {
    pub fn from_env_flag(env: &str) -> Self {
        match env {
            "mainnet" | "prod" | "production" => Self::IndiaMainnet,
            _ => Self::DemoIndia,
        }
    }

    pub fn rest_base(&self) -> &'static str {
        match self {
            Self::DemoIndia => "https://cdn-ind.testnet.deltaex.org",
            Self::IndiaMainnet => "https://api.india.delta.exchange",
        }
    }

    pub fn ws_public(&self) -> &'static str {
        match self {
            Self::DemoIndia => "wss://socket-ind-pub.testnet.deltaex.org",
            Self::IndiaMainnet => "wss://public-socket.india.delta.exchange",
        }
    }

    pub fn ws_private(&self) -> &'static str {
        match self {
            Self::DemoIndia => "wss://socket-ind.testnet.deltaex.org",
            Self::IndiaMainnet => "wss://socket.india.delta.exchange",
        }
    }
}
