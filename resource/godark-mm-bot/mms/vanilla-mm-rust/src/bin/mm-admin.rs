//! GoDark MM admin — account snapshot and cancel stale working orders.

use std::time::Duration;

use godark::{
    GodarkError, GodarkRestClient, OpenOrderRow, OrderType, PositionRow, PositionsSnapshot, Side,
    TimeInForce,
};
use tracing::{info, warn};
use vanilla_mm_rust::{build_rest_client, is_transient_error, load_instruments};

#[tokio::main]
async fn main() -> Result<(), Box<dyn std::error::Error>> {
    tracing_subscriber::fmt()
        .with_env_filter(
            std::env::var("RUST_LOG").unwrap_or_else(|_| "mm_admin=info,godark=warn".into()),
        )
        .init();

    let cmd = std::env::args().nth(1).unwrap_or_else(|| "snapshot".into());
    match cmd.as_str() {
        "snapshot" => snapshot().await?,
        "cancel-all" => cancel_all().await?,
        "flatten" => flatten().await?,
        other => {
            eprintln!("unknown command: {other}");
            eprintln!("usage: mm-admin [snapshot|cancel-all|flatten]");
            std::process::exit(1);
        }
    }
    Ok(())
}

async fn connect_client() -> Result<GodarkRestClient, GodarkError> {
    let mut client = build_rest_client()?;
    let mut backoff = Duration::from_millis(300);
    for attempt in 1..=4 {
        if attempt > 1 {
            tokio::time::sleep(backoff).await;
            backoff = (backoff * 2).min(Duration::from_secs(3));
        }
        match client.connect().await {
            Ok(()) => return Ok(client),
            Err(e) if is_transient_error(&e) && attempt < 4 => {
                warn!("connect retry {attempt}/4: {e}");
            }
            Err(e) => return Err(e),
        }
    }
    Err(GodarkError::Connection("connect failed".into()))
}

async fn snapshot() -> Result<(), GodarkError> {
    let mut client = connect_client().await?;
    info!("connected user_uuid={:?}", client.user_uuid());

    let mut account = None;
    for attempt in 1..=4 {
        match client.get_account().await {
            Ok(v) => {
                account = Some(v);
                break;
            }
            Err(e) if is_transient_error(&e) && attempt < 4 => {
                warn!("get_account retry {attempt}/4: {e}");
                client.connect().await.ok();
                tokio::time::sleep(Duration::from_millis(300 * attempt as u64)).await;
            }
            Err(e) => return Err(e),
        }
    }
    let account = account.expect("get_account");
    info!("account server_ts={}", account.server_timestamp);
    if let Some(acct) = &account.account {
        info!(
            "collateral={} position_margin={} reserved_order_margin={} free_collateral={}",
            acct.total_collateral,
            acct.position_margin,
            acct.reserved_order_margin,
            acct.free_collateral,
        );
    }

    let mut positions = None;
    for attempt in 1..=4 {
        match client.get_positions().await {
            Ok(v) => {
                positions = Some(v);
                break;
            }
            Err(e) if is_transient_error(&e) && attempt < 4 => {
                warn!("get_positions retry {attempt}/4: {e}");
                tokio::time::sleep(Duration::from_millis(300 * attempt as u64)).await;
            }
            Err(e) => return Err(e),
        }
    }
    let positions = positions.expect("get_positions");
    info!("positions rows={}", positions.rows.len());
    for row in &positions.rows {
        info!(
            "  symbol_id={} side={:?} size={} entry={} mark={:?} upl={:?}",
            row.symbol_id,
            row.side,
            row.size,
            row.entry_price,
            row.mark_price,
            row.unrealized_pnl,
        );
    }

    let mut orders = None;
    for attempt in 1..=5 {
        match client.get_open_orders().await {
            Ok(v) => {
                orders = Some(v);
                break;
            }
            Err(e) if is_transient_error(&e) && attempt < 5 => {
                warn!("get_open_orders retry {attempt}/5: {e}");
                tokio::time::sleep(Duration::from_millis(300 * attempt as u64)).await;
            }
            Err(e) => return Err(e),
        }
    }
    let orders = orders.expect("get_open_orders");
    info!("open_orders rows={}", orders.rows.len());
    summarize_orders(&orders.rows);

    client.disconnect().await.ok();
    Ok(())
}

fn summarize_orders(rows: &[OpenOrderRow]) {
    let mut by_symbol: std::collections::HashMap<u64, usize> = std::collections::HashMap::new();
    for row in rows {
        *by_symbol.entry(row.symbol_id).or_default() += 1;
    }
    for (symbol_id, count) in by_symbol {
        info!("  symbol_id={symbol_id} working_orders={count}");
    }
}

async fn fetch_open_orders(client: &mut GodarkRestClient) -> Result<Vec<OpenOrderRow>, GodarkError> {
    for attempt in 1..=6 {
        match client.get_open_orders().await {
            Ok(v) => return Ok(v.rows),
            Err(e) if is_transient_error(&e) && attempt < 6 => {
                warn!("get_open_orders retry {attempt}/6: {e}");
                tokio::time::sleep(Duration::from_millis(800 * attempt as u64)).await;
            }
            Err(e) => return Err(e),
        }
    }
    Err(GodarkError::Connection("get_open_orders failed".into()))
}

async fn cancel_all() -> Result<(), GodarkError> {
    let mut client = connect_client().await?;
    let instruments = load_instruments().await;
    let id_to_symbol: std::collections::HashMap<u64, String> = instruments
        .values()
        .map(|row| (row.symbol_id, row.symbol.clone()))
        .collect();

    let batch_pause_ms = vanilla_mm_rust::env_usize("MM_ADMIN_BATCH_PAUSE_MS", 2000);
    let mut ok = 0u32;
    let mut fail = 0u32;

    loop {
        let rows = fetch_open_orders(&mut client).await?;
        if rows.is_empty() {
            break;
        }
        info!("cancel-all: {} open orders remaining", rows.len());

        let mut by_symbol: std::collections::HashMap<String, Vec<u64>> =
            std::collections::HashMap::new();
        for row in rows {
            let symbol = id_to_symbol
                .get(&row.symbol_id)
                .cloned()
                .unwrap_or_else(|| format!("symbol_id:{}", row.symbol_id));
            let oid: u64 = row.order_id.parse().unwrap_or(0);
            if oid == 0 {
                fail += 1;
                continue;
            }
            by_symbol.entry(symbol).or_default().push(oid);
        }

        for (symbol, ids) in by_symbol {
            for chunk in ids.chunks(20) {
                tokio::time::sleep(Duration::from_millis(batch_pause_ms as u64)).await;
                let mut done = false;
                for attempt in 1..=4 {
                    match client.batch_cancel(&symbol, chunk).await {
                        Ok(ack) => {
                            ok += ack.results.iter().filter(|r| r.cancelled).count() as u32;
                            fail += ack.results.iter().filter(|r| !r.cancelled).count() as u32;
                            info!(
                                "batch_cancel {symbol} n={} ok={}",
                                chunk.len(),
                                ack.results.iter().filter(|r| r.cancelled).count()
                            );
                            done = true;
                            break;
                        }
                        Err(e) if is_transient_error(&e) && attempt < 4 => {
                            warn!("batch_cancel retry {attempt}/4 {symbol}: {e}");
                            tokio::time::sleep(Duration::from_millis(1000 * attempt as u64))
                                .await;
                        }
                        Err(e) => {
                            warn!("batch_cancel failed {symbol}: {e} — falling back to singles");
                            for oid in chunk {
                                tokio::time::sleep(Duration::from_millis(800)).await;
                                match client.cancel_order(&oid.to_string(), &symbol).await {
                                    Ok(a) if a.success => ok += 1,
                                    _ => fail += 1,
                                }
                            }
                            done = true;
                            break;
                        }
                    }
                }
                if !done {
                    fail += chunk.len() as u32;
                }
            }
        }
    }

    info!("cancel-all done ok={ok} fail={fail}");
    client.disconnect().await.ok();
    Ok(())
}

fn signed_position_size(row: &PositionRow) -> f64 {
    let size: f64 = row.size.parse().unwrap_or(0.0);
    match row.side {
        Side::Buy => size,
        Side::Sell => -size,
    }
}

async fn fetch_positions(client: &mut GodarkRestClient) -> Result<PositionsSnapshot, GodarkError> {
    for attempt in 1..=6 {
        match client.get_positions().await {
            Ok(v) => return Ok(v),
            Err(e) if is_transient_error(&e) && attempt < 6 => {
                warn!("get_positions retry {attempt}/6: {e}");
                tokio::time::sleep(Duration::from_millis(500 * attempt as u64)).await;
            }
            Err(e) => return Err(e),
        }
    }
    Err(GodarkError::Connection("get_positions failed".into()))
}

/// Cancel all working orders, then market-close any open positions (IOC).
async fn flatten() -> Result<(), GodarkError> {
    cancel_all().await?;
    tokio::time::sleep(Duration::from_secs(2)).await;

    let mut client = connect_client().await?;
    let instruments = load_instruments().await;
    let id_to_symbol: std::collections::HashMap<u64, String> = instruments
        .values()
        .map(|row| (row.symbol_id, row.symbol.clone()))
        .collect();

    let positions = fetch_positions(&mut client).await?;
    if positions.rows.is_empty() {
        info!("flatten: no open positions");
        client.disconnect().await.ok();
        return Ok(());
    }

    let pause_ms = vanilla_mm_rust::env_usize("MM_ADMIN_FLATTEN_PAUSE_MS", 400);
    let mut closed = 0u32;
    let mut fail = 0u32;

    for row in positions.rows {
        let inv = signed_position_size(&row);
        if inv.abs() < 1e-8 {
            continue;
        }
        let symbol = id_to_symbol
            .get(&row.symbol_id)
            .cloned()
            .unwrap_or_else(|| format!("symbol_id:{}", row.symbol_id));
        let (close_side, qty) = if inv > 0.0 {
            (Side::Sell, inv)
        } else {
            (Side::Buy, -inv)
        };
        info!(
            "flatten: {symbol} inv={inv:.6} -> market {close_side:?} qty={qty:.6}"
        );
        tokio::time::sleep(Duration::from_millis(pause_ms as u64)).await;
        let coid = format!("mm-flatten-{}-{}", symbol_slug(&symbol), uuid::Uuid::new_v4());
        let mut done = false;
        for attempt in 1..=4 {
            match client
                .place_order(
                    &symbol,
                    close_side,
                    OrderType::Market,
                    qty,
                    None,
                    TimeInForce::Ioc,
                    false,
                    None,
                    None,
                    Some(coid.clone()),
                )
                .await
            {
                Ok(ack) if ack.success => {
                    closed += 1;
                    done = true;
                    info!(
                        "flatten closed {symbol} order_id={} inv_was={inv:.6}",
                        ack.order_id
                    );
                    break;
                }
                Ok(ack) => {
                    fail += 1;
                    done = true;
                    warn!("flatten rejected {symbol}: {:?}", ack.error);
                    break;
                }
                Err(e) if is_transient_error(&e) && attempt < 4 => {
                    warn!("flatten retry {attempt}/4 {symbol}: {e}");
                    tokio::time::sleep(Duration::from_millis(600 * attempt as u64)).await;
                }
                Err(e) => {
                    fail += 1;
                    done = true;
                    warn!("flatten failed {symbol}: {e}");
                    break;
                }
            }
        }
        if !done {
            fail += 1;
        }
    }

    tokio::time::sleep(Duration::from_secs(2)).await;
    let after = fetch_positions(&mut client).await?;
    info!(
        "flatten done closed={closed} fail={fail} remaining_positions={}",
        after.rows.len()
    );
    for row in &after.rows {
        info!(
            "  remaining symbol_id={} side={:?} size={}",
            row.symbol_id, row.side, row.size
        );
    }
    client.disconnect().await.ok();
    Ok(())
}

fn symbol_slug(symbol: &str) -> &str {
    symbol.split('-').next().unwrap_or(symbol)
}
