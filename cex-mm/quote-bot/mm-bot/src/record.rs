use anyhow::Result;
use chrono::Utc;
use clap::Args;
use std::fs::{create_dir_all, OpenOptions};
use std::io::Write;
use std::path::PathBuf;
use std::sync::Arc;
use tokio::sync::watch;

use mm_binance::BinanceBbo;
use mm_bybit::{BybitBook, BybitEnvironment, OrderbookMaintainer};

use crate::symbols::normalize_symbol;
use crate::universe::{UniverseOptions, resolve_universe};

#[derive(Args)]
pub struct RecordArgs {
    #[arg(long, env = "MM_SYMBOL", default_value = "BTCUSDT")]
    pub symbol: String,
    #[arg(long, env = "MM_SYMBOLS", value_delimiter = ',')]
    pub symbols: Vec<String>,
    #[arg(long, env = "MM_TOP_N", default_value = "0")]
    pub top_n: usize,
    #[arg(long, env = "MM_TOP_N_EXCLUDE", value_delimiter = ',')]
    pub exclude_symbols: Vec<String>,
    #[arg(long, default_value = "3600")]
    pub duration_sec: u64,
    #[arg(long, default_value = "artifacts/recordings")]
    pub out_dir: PathBuf,
    #[arg(long, default_value = "testnet")]
    pub bybit_env: String,
}

pub async fn run(args: RecordArgs) -> Result<()> {
    create_dir_all(&args.out_dir)?;
    let bybit_env = if args.bybit_env == "mainnet" {
        BybitEnvironment::Mainnet
    } else {
        BybitEnvironment::Testnet
    };
    let symbols = resolve_universe(
        UniverseOptions {
            single: args.symbol.clone(),
            multi: args.symbols.clone(),
            top_n: args.top_n,
            exclude: args.exclude_symbols.clone(),
        },
        bybit_env,
    )
    .await?;
    let stamp = Utc::now().format("%Y%m%dT%H%M%SZ");
    let path = if symbols.len() == 1 {
        args.out_dir.join(format!("{}_{stamp}.jsonl", symbols[0]))
    } else {
        args.out_dir.join(format!("multi_{stamp}.jsonl"))
    };
    let file = Arc::new(std::sync::Mutex::new(
        OpenOptions::new()
            .create(true)
            .append(true)
            .open(&path)?,
    ));
    let meta = serde_json::json!({
        "ts_local": Utc::now().to_rfc3339_opts(chrono::SecondsFormat::Millis, true),
        "source": "meta",
        "symbols": symbols,
        "bybit_env": args.bybit_env,
        "duration_sec": args.duration_sec,
    });
    writeln!(file.lock().unwrap(), "{meta}")?;

    let mut book_rxs = Vec::new();
    for sym in &symbols {
        let (book_tx, book_rx) = watch::channel(BybitBook::default());
        book_rxs.push((sym.clone(), book_rx));
        let maint = OrderbookMaintainer {
            env: bybit_env,
            symbol: sym.clone(),
        };
        tokio::spawn(async move {
            let _ = maint.run(book_tx).await;
        });

        let (bbo_tx, mut bbo_rx) = watch::channel(BinanceBbo::default());
        let binance_sym = sym.clone();
        let sym_label = normalize_symbol(sym);
        let file = file.clone();
        tokio::spawn(async move {
            tokio::spawn(async move {
                let _ = mm_binance::run_book_ticker(&binance_sym, bbo_tx).await;
            });
            loop {
                if bbo_rx.changed().await.is_err() {
                    break;
                }
                let b = *bbo_rx.borrow();
                let line = serde_json::json!({
                    "ts_local": Utc::now().to_rfc3339_opts(chrono::SecondsFormat::Millis, true),
                    "source": "binance",
                    "symbol": sym_label,
                    "bid": b.bid,
                    "ask": b.ask,
                    "mid": b.mid,
                });
                let _ = writeln!(file.lock().unwrap(), "{line}");
            }
        });
    }

    let deadline =
        tokio::time::Instant::now() + std::time::Duration::from_secs(args.duration_sec);
    while tokio::time::Instant::now() < deadline {
        for (sym, book_rx) in &mut book_rxs {
            if book_rx.has_changed().unwrap_or(false) {
                let b = book_rx.borrow_and_update().clone();
                let line = serde_json::json!({
                    "ts_local": Utc::now().to_rfc3339_opts(chrono::SecondsFormat::Millis, true),
                    "source": "bybit",
                    "symbol": sym,
                    "bid": b.top.best_bid,
                    "ask": b.top.best_ask,
                    "bid_qty": b.top.bid_qty,
                    "ask_qty": b.top.ask_qty,
                    "u": b.last_u,
                });
                writeln!(file.lock().unwrap(), "{line}")?;
            }
        }
        tokio::time::sleep(std::time::Duration::from_millis(50)).await;
    }
    tracing::info!(?path, ?symbols, "recording finished");
    Ok(())
}
