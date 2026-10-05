mod account;
mod exchange;
mod markout;
mod oems;
mod oms;
mod record;
mod record_delta;
mod runner;
mod risk;
mod symbols;
mod universe;

use anyhow::Result;
use clap::{Parser, Subcommand};
use tracing_subscriber::EnvFilter;

#[derive(Parser)]
#[command(name = "mm-bot", about = "CEX perp market maker (Bybit or Delta India)")]
struct Cli {
    #[command(subcommand)]
    command: Commands,
}

#[derive(Subcommand)]
enum Commands {
    /// Record public WS feeds with local timestamps (Slice 1).
    Record(record::RecordArgs),
    /// Record Delta public trades and L1 (raw websocket, local timestamps) for the shadow test.
    RecordDelta(record_delta::RecordDeltaArgs),
    /// Compute quotes on live book without placing orders.
    DryRun(runner::RunArgs),
    /// Run MM on Bybit testnet/mainnet (requires API keys).
    Run(runner::RunArgs),
    /// Print resolved symbol universe (top-N / pins / excludes) without trading.
    Universe(runner::RunArgs),
    /// Cancel all open orders (kill switch helper).
    CancelAll {
        #[arg(long, env = "MM_SYMBOL", default_value = "BTCUSDT")]
        symbol: String,
        #[arg(long, env = "MM_SYMBOLS", value_delimiter = ',')]
        symbols: Vec<String>,
        #[arg(long, env = "MM_TOP_N", default_value = "0")]
        top_n: usize,
        #[arg(long, env = "MM_TOP_N_EXCLUDE", value_delimiter = ',')]
        exclude_symbols: Vec<String>,
        /// Cancel every symbol in the resolved universe (`MM_SYMBOLS`, or `MM_TOP_N`, or `--all`).
        #[arg(long)]
        all: bool,
        #[arg(long, default_value = "testnet")]
        env: String,
        #[arg(long, env = "MM_VENUE", default_value = "bybit")]
        venue: String,
    },
}

#[tokio::main]
async fn main() -> Result<()> {
    tracing_subscriber::fmt()
        .with_env_filter(EnvFilter::from_default_env().add_directive("mm_bot=info".parse()?))
        .init();
    let cli = Cli::parse();
    match cli.command {
        Commands::Record(args) => record::run(args).await,
        Commands::RecordDelta(args) => record_delta::run(args).await,
        Commands::DryRun(args) => runner::run(args, true).await,
        Commands::Run(args) => runner::run(args, false).await,
        Commands::Universe(args) => {
            let bybit_env = if args.env == "mainnet" {
                mm_bybit::BybitEnvironment::Mainnet
            } else {
                mm_bybit::BybitEnvironment::Testnet
            };
            universe::print_universe(args.universe_options(), bybit_env).await
        }
        Commands::CancelAll {
            symbol,
            symbols,
            top_n,
            exclude_symbols,
            all,
            env,
            venue,
        } => {
            let bybit_env = if env == "mainnet" {
                mm_bybit::BybitEnvironment::Mainnet
            } else {
                mm_bybit::BybitEnvironment::Testnet
            };
            let mut top_n = top_n;
            if top_n == 0 {
                top_n = std::env::var("MM_TOP_N")
                    .ok()
                    .and_then(|s| s.parse().ok())
                    .unwrap_or(0);
            }
            let mut multi = symbols;
            if multi.is_empty() {
                if let Ok(list) = std::env::var("MM_SYMBOLS") {
                    multi = list
                        .split(',')
                        .map(crate::symbols::normalize_symbol)
                        .filter(|s| !s.is_empty())
                        .collect();
                }
            }
            if all || top_n > 0 || !multi.is_empty() {
                let list = universe::resolve_universe(
                    crate::universe::UniverseOptions {
                        single: symbol.clone(),
                        multi,
                        top_n,
                        exclude: exclude_symbols,
                    },
                    bybit_env,
                )
                .await?;
                for sym in list {
                    runner::cancel_all(&sym, &env, &venue).await?;
                }
                Ok(())
            } else {
                runner::cancel_all(&symbol, &env, &venue).await
            }
        }
    }
}
