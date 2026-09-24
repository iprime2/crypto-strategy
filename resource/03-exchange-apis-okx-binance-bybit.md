# Exchange APIs for a Market-Making Bot: OKX, Binance, Bybit (Spot + USDT Perps)

Research date: 2026-09-20. Sources are the official API docs (URLs cited inline). Where a
page could not be read directly (Binance derivatives docs are JS-rendered and Cloudflare-gated),
facts were confirmed from Binance's official connector repositories and marked accordingly.
Anything that could not be verified against an official source is marked **unverified**.

Key URL shorthand used below:

- Binance spot docs (markdown source): `https://github.com/binance/binance-spot-api-docs` (files: `rest-api.md`, `web-socket-streams.md`, `web-socket-api.md`, `user-data-stream.md`, `filters.md`, `enums.md`, `errors.md`, `faqs/*.md`, `demo-mode/general-info.md`, `CHANGELOG.md`)
- Binance USDⓈ-M futures docs: `https://developers.binance.com/docs/derivatives/usds-margined-futures/...` (JS-rendered; cross-checked against `https://github.com/binance/binance-futures-connector-python`)
- OKX docs: `https://www.okx.com/docs-v5/en/`
- Bybit docs: `https://bybit-exchange.github.io/docs/v5/...`
- CCXT: `https://docs.ccxt.com` and `https://github.com/ccxt/ccxt/tree/master/python/ccxt/pro`

---

## OKX

### 1. Market data

Endpoints (https://www.okx.com/docs-v5/en/#overview-production-trading-services):
- REST `https://www.okx.com` (also `https://openapi.okx.com`), public WS `wss://ws.okx.com:8443/ws/v5/public`, private WS `wss://ws.okx.com:8443/ws/v5/private`, business WS `wss://ws.okx.com:8443/ws/v5/business`.
- Same channels/instruments for spot and SWAP (USDT perps); instrument IDs differ (`BTC-USDT` vs `BTC-USDT-SWAP`).

Order book channels (https://www.okx.com/docs-v5/en/#order-book-trading-market-data-ws-order-book-channel):

| Channel | Depth | Push cadence | Type | Access |
|---|---|---|---|---|
| `books` | 400 | snapshot once, then diffs every ~100 ms when changed | snapshot + delta | public |
| `books5` | 5 | full snapshot every ~100 ms when changed | full snapshot | public |
| `bbo-tbt` | 1 | ~10 ms tick-by-tick when changed | full snapshot (L1) | public |
| `books50-l2-tbt` | 50 | ~10 ms tick-by-tick | snapshot + delta | VIP4+ with identity verification |
| `books-l2-tbt` | 400 | ~10 ms tick-by-tick | snapshot + delta | VIP5+ with identity verification |
| `books-rpi` | 400 (incl. RPI liquidity) | ~100 ms | snapshot + delta | public |
| `books-elp` | – | – | deprecated | – |

- Book messages carry `seqId` and `prevSeqId`. Sync rule (same doc): first message is `action: "snapshot"`; subsequent `action: "update"` messages must satisfy `prevSeqId == last seqId`. If not, re-subscribe. Level entries are `[price, size, deprecated_liq_orders, num_orders]`; `size == 0` deletes the level.
- **Checksum is deprecated**: the `checksum` field is now fixed to `0` in book pushes; OKX instructs clients to rely on `seqId`/`prevSeqId` only (https://www.okx.com/docs-v5/en/#order-book-trading-market-data-ws-order-book-channel, checksum note). Do not implement the CRC32 check on new code.
- Trades: `trades` channel (aggregated per taker order per price) and `trades-all` (every trade, business WS) (https://www.okx.com/docs-v5/en/#order-book-trading-market-data-ws-trades-channel, https://www.okx.com/docs-v5/en/#order-book-trading-market-data-ws-all-trades-channel).
- BBO: `bbo-tbt` (10 ms). `tickers` channel gives last/bid/ask at ~100 ms (https://www.okx.com/docs-v5/en/#order-book-trading-market-data-ws-tickers-channel).
- Mark price: `mark-price` channel, pushed every 200 ms when changed, every 10 s when static (https://www.okx.com/docs-v5/en/#public-data-websocket-mark-price-channel).
- Funding: `funding-rate` channel, pushed every 30–90 s (https://www.okx.com/docs-v5/en/#public-data-websocket-funding-rate-channel). REST `GET /api/v5/public/funding-rate`.
- Index price: `index-tickers` (https://www.okx.com/docs-v5/en/#public-data-websocket-index-tickers-channel).
- WS connection hygiene: server closes connections idle >30 s; send `ping` string if no data for 30 s and expect `pong` (https://www.okx.com/docs-v5/en/#overview-websocket-connect).

### 2. Order entry

- REST: `POST /api/v5/trade/order` (single), `POST /api/v5/trade/batch-orders` (up to 20 orders), `POST /api/v5/trade/cancel-order`, `POST /api/v5/trade/cancel-batch-orders` (up to 20), `POST /api/v5/trade/amend-order`, `POST /api/v5/trade/amend-batch-orders` (up to 20) (https://www.okx.com/docs-v5/en/#order-book-trading-trade).
- WS trade channel: `order`, `batch-orders`, `cancel-order`, `batch-cancel-orders`, `amend-order`, `batch-amend-orders` operations on the private WS (`op` field). Uses `instIdCode` (numeric) for WS operations; the docs mark `instId` deprecated for WS trade ops, so map `instId → instIdCode` via `GET /api/v5/public/instruments` (https://www.okx.com/docs-v5/en/#order-book-trading-trade-ws-place-order).
- Post-only: `ordType = post_only`. Other `ordType`: `limit`, `market`, `fok`, `ioc`, `optimal_limit_ioc` (perps only), `mmp`, `mmp_and_post_only` (options only) (https://www.okx.com/docs-v5/en/#order-book-trading-trade-post-place-order). Post-only orders that would cross are **rejected** (not price-adjusted); the response is an error `sCode` for that order.
- Amend: `POST /api/v5/trade/amend-order` changes `newSz` and/or `newPx`; `cxlOnFail` flag controls whether the order is cancelled if the amend fails. Amend can be done by `ordId` or `clOrdId`. Amends do not preserve queue priority when price changes (queue priority is preserved only for size decreases — **unverified**, standard matching-engine behavior; OKX docs do not state it explicitly).
- Cancel-all: OKX has no simple "cancel all open orders" REST endpoint; use `POST /api/v5/trade/mass-cancel` (options/MMP only) or `POST /api/v5/trade/cancel-all-after` (dead-man switch, `timeOut` 10–120 s, 0 to disable; 1 req/s) (https://www.okx.com/docs-v5/en/#order-book-trading-trade-post-cancel-all-after). Otherwise cancel via `cancel-batch-orders` (20/request) after `GET /api/v5/trade/orders-pending`.
- Client order id `clOrdId`: alphanumeric, ≤32 chars, case-sensitive, must be unique among open orders (https://www.okx.com/docs-v5/en/#order-book-trading-trade-post-place-order). `tag` field ≤16 chars for broker tagging.
- Self-trade prevention: `stpMode` = `cancel_maker` (default), `cancel_taker`, `cancel_both`; STP is keyed at the master-account level (sub-accounts of the same master are included) (https://www.okx.com/docs-v5/en/#order-book-trading-trade-post-place-order, `stpMode` param).
- Attached TP/SL (`attachAlgoOrds`) allowed on the same order.

### 3. Rate limits

Source: https://www.okx.com/docs-v5/en/#overview-rate-limits and https://www.okx.com/docs-v5/en/#overview-trading-rate-limit

- Limits are **shared between REST and WS**, independent per action (place / cancel / amend), and keyed **per instrument ID** for trade endpoints (options: per underlying); other endpoints are keyed per UID or per IP as stated on each endpoint.
- Place order: 60 requests / 2 s per instrument; batch place: 300 orders / 2 s (batch counts each order). Cancel: 60 / 2 s; batch cancel: 300 / 2 s. Amend: 60 / 2 s; batch amend: 300 / 2 s. Cancel-all-after: 1 / s. Mass cancel: 5 / 2 s.
- Sub-account level trading limit: **1000 order requests / 2 s per sub-account** covering new + amend (cancels excluded). Fill-ratio based tiering applies to VIP5+ accounts (lower fill ratio → lower limit) (https://www.okx.com/docs-v5/en/#overview-trading-rate-limit).
- WS: 3 connection requests / s per IP; 480 `subscribe`/`unsubscribe`/`login` messages per connection per hour; 30 connections per channel per sub-account; login attempts limited (https://www.okx.com/docs-v5/en/#overview-websocket-connect).
- Exceeding: HTTP 429 with `code 50011` "Rate limit reached"; repeated abuse can result in temporary IP-level throttling (**unverified** duration). Response headers carry no per-second budget, so track locally.

### 4. Fees

- Regular (Lv1) users: Spot 0.08% maker / 0.10% taker; Perps/Futures 0.02% maker / 0.05% taker (https://www.okx.com/fees). VIP1–VIP8 tiers lower these (perps maker to ~0.00% at VIP5+; check live page). Fee schedule is regional (OKX EU/US differ).
- OKB holdings give Regular-tier discount tiers (Lv1–Lv5 by OKB balance) (https://www.okx.com/fees) — the API `GET /api/v5/account/trade-fee` returns the actual `maker`/`taker` rates for the account and instrument (https://www.okx.com/docs-v5/en/#trading-account-rest-api-get-fee-rates).
- Market Maker Program (GLP – "Global Liquidity Program"): prerequisites are VIP2+ on OKX or documented market-maker status on another major venue; apply via `Institutional@okx.com`; rebates and quoting obligations are disclosed after acceptance (not public) (https://www.okx.com/docs-v5/en/#market-maker-program). GLP performance can be queried via `GET /api/v5/account/glp-performance` (today) and historical variant — see the docs section "Market Maker Program". MM accounts get `books50-l2-tbt` / `books-l2-tbt` tick-by-tick book access.

### 5. User data / private streams

- Private WS `wss://ws.okx.com:8443/ws/v5/private`; login with `op: login` and HMAC-SHA256 signature over `timestamp + 'GET' + '/users/self/verify'` (https://www.okx.com/docs-v5/en/#overview-websocket-login).
- Channels: `orders` (order state + fills), `fills` (VIP5+ dedicated fill stream, faster), `account` (balances), `positions`, `balance_and_position` (combined), `liquidation-warning` (https://www.okx.com/docs-v5/en/#order-book-trading-trade-ws-order-channel, https://www.okx.com/docs-v5/en/#trading-account-websocket-account-channel).
- Fill reporting in `orders`: `fillPx`, `fillSz`, `fillFee`, `fillFeeCcy`, `execType` (`T` = taker, `M` = maker), `tradeId`, `fillTime`. Cumulative `fee`/`feeCcy` on the order.
- No listenKey concept; connection auth lives for the socket lifetime. Keep-alive: ping/pong every <30 s.

### 6. Instrument metadata

- `GET /api/v5/public/instruments?instType=SPOT|SWAP` returns `tickSz`, `lotSz`, `minSz`, `maxLmtSz`, `maxMktSz`, `ctVal` (contract value, e.g. 0.01 BTC per BTC-USDT-SWAP), `ctMult`, `state`, `instIdCode` (https://www.okx.com/docs-v5/en/#public-data-rest-api-get-instruments).
- Perps size is in contracts (`sz`), not coins — multiply by `ctVal`. Spot has no per-order min notional field; `minSz` is in base currency.
- `instruments` WS channel pushes metadata changes (https://www.okx.com/docs-v5/en/#public-data-websocket-instruments-channel). Tick/lot changes are announced but rare; refresh on startup and on `instruments` push.

### 7. Testnet / demo

- Demo trading: same API surface with REST `https://www.okx.com` + header `x-simulated-trading: 1`; WS `wss://wspap.okx.com:8443/ws/v5/public|private|business` (https://www.okx.com/docs-v5/en/#overview-demo-trading-services). Demo API keys are separate (created on the Demo Trading page).
- Limitations: demo market data mirrors production but the demo matching engine has its own book/fills, so fill behavior of resting quotes is not realistic; rate limits still apply; `books-l2-tbt` access requires VIP tiers even in demo (**unverified**).

### 8. Infrastructure

- Hosting: OKX matching/API in **Alibaba Cloud Hong Kong (cn-hongkong)**; Alibaba Cloud HK colocation gives ~1–2 ms; AWS ap-east-1 (Hong Kong) ~3–5 ms. Confidence: medium — from third-party latency guides and community measurements, not stated in official docs (**unverified** against official OKX statement).
- Timestamps: `OK-ACCESS-TIMESTAMP` is ISO-8601 UTC with milliseconds (e.g. `2020-12-08T09:08:57.715Z`); requests with a timestamp more than **30 s** from server time are rejected (https://www.okx.com/docs-v5/en/#overview-rest-authentication). `GET /api/v5/public/time` for server time.
- WS login `timestamp` is Unix seconds and must be within 30 s of server time (https://www.okx.com/docs-v5/en/#overview-websocket-login).
- Colocation: OKX offers a low-latency "OKX Institutional Colocation" in Alibaba HK for VIP/MM clients (**unverified** details).

### 9. Gotchas for MM

- `checksum` is deprecated (fixed `0`); validate via `seqId`/`prevSeqId` only; on gap, unsubscribe + resubscribe.
- The public `books` channel is 100 ms; tick-by-tick (`books50-l2-tbt`) needs VIP4 + KYC. For a retail MM, `bbo-tbt` (10 ms L1) + `books` (100 ms L2) is the best public combination.
- Perps sizes are in contracts (`ctVal`); mixing coin and contract sizes is a classic bug.
- WS trade operations require `instIdCode` (not `instId`).
- Post-only that would cross is rejected with a per-order `sCode` (batch responses are per order — check each).
- Price limits: perps have a mark-price-based price band (`GET /api/v5/public/price-limit` returns `buyLmt`/`sellLmt`); orders outside are rejected (https://www.okx.com/docs-v5/en/#public-data-rest-api-get-limit-price).
- ADL exists for perps under extreme conditions; MM accounts are not exempt (https://www.okx.com/help/... — **unverified** URL; see OKX help centre "auto-deleveraging").
- Account modes: use **Single-currency margin** or **Multi-currency margin** (unified account) and set `tdMode` = `cash` for spot, `cross`/`isolated` for perps. Position mode `net_mode` vs `long_short_mode` affects perps `posSide` param.
- Sub-accounts: up to 20 IP addresses bound per API key; keys with Trade/Withdraw permission that are not IP-bound expire after **14 days** of inactivity; API key permissions are `Read`, `Trade`, `Withdraw` (https://www.okx.com/docs-v5/en/#overview-api-key-security). Sub-account transfers via `POST /api/v5/asset/transfer`.
- Trading rate limit is per instrument — quoting several symbols scales the budget linearly, but the 1000/2 s sub-account cap is global.

### 10. Libraries

- CCXT / CCXT Pro `okx`: `watch_order_book` (`books`, `books5`, `bbo-tbt`, `books50-l2-tbt`, `books-l2-tbt`), `watch_trades`, `watch_bids_asks` (`bbo-tbt`), `watch_mark_price`, `watch_funding_rate`, `watch_orders`, `watch_my_trades`, `watch_positions`, `watch_balance`, plus WS trading `create_order_ws`, `edit_order_ws`, `cancel_order_ws`, `cancel_all_orders_ws` (https://github.com/ccxt/ccxt/blob/master/python/ccxt/pro/okx.py).
- Official Python SDK: `python-okx` (`pip install python-okx`, https://github.com/okxapi/python-okx) — REST + WS wrappers, thin, maintained by OKX.
- Rust: NautilusTrader has a native OKX adapter (https://nautilustrader.io/docs/latest/integrations/okx/); `dcex` and Barter-rs have OKX data connectors.

---

## Binance

### 1. Market data

**Spot** (https://github.com/binance/binance-spot-api-docs/blob/master/web-socket-streams.md):
- Base: `wss://stream.binance.com:9443/ws` or `/stream` (combined); `wss://data-stream.binance.vision` for market data only. Connections valid **24 h**; server sends `serverShutdown` event before planned disconnect; max **1024 streams per connection**, **5 incoming messages/s per connection**, **300 connections per 5 min per IP**.
- Diff depth: `<symbol>@depth` (1000 ms) and `<symbol>@depth@100ms`. Partial book: `<symbol>@depth5|10|20` at 1000 ms and `@100ms`.
- Book sync procedure (spot, "How to manage a local order book correctly" in the same doc): open `@depth` stream and buffer events; fetch `GET /api/v3/depth?symbol=X&limit=5000`; drop events with `u <= lastUpdateId`; the first event to apply must have `U <= lastUpdateId+1 <= u`; then each subsequent event must have `U == previous u + 1`, otherwise restart. Quantities are absolute; `0` removes the level.
- Trades: `<symbol>@trade` (real-time), `<symbol>@aggTrade`.
- BBO: `<symbol>@bookTicker` (real-time, individual symbol only; the all-symbols `!bookTicker` was removed).
- SBE market streams `wss://stream-sbe.binance.com` for binary encoding (lower bandwidth).

**USDⓈ-M futures** (docs: https://developers.binance.com/docs/derivatives/usds-margined-futures/websocket-market-streams ; confirmed via https://github.com/binance/binance-futures-connector-python/blob/main/binance/websocket/um_futures/websocket_client.py):
- Base `wss://fstream.binance.com`; **200 streams per connection**, **10 incoming msgs/s**, 24 h connection lifetime.
- Diff depth `<symbol>@depth` at 250 ms (default), `@500ms`, `@100ms`. Partial `@depth5|10|20` same speeds.
- Book sync (https://developers.binance.com/docs/derivatives/usds-margined-futures/websocket-market-streams/How-to-manage-a-local-order-book-correctly): snapshot from `GET /fapi/v1/depth?limit=1000`; drop events with `u < lastUpdateId`; first event `U <= lastUpdateId AND u >= lastUpdateId`; afterwards each event's `pu` must equal the previous event's `u` (futures adds `pu` = previous final update ID). Restart on mismatch.
- Trades `@aggTrade` (futures has no raw `@trade` stream). BBO `@bookTicker` (real-time). Mark price + funding: `<symbol>@markPrice` (3 s) or `@markPrice@1s` — carries `p` mark, `i` index, `r` funding rate, `T` next funding time. `@forceOrder` liquidations.

### 2. Order entry

**Spot** (https://github.com/binance/binance-spot-api-docs/blob/master/rest-api.md, https://github.com/binance/binance-spot-api-docs/blob/master/web-socket-api.md):
- REST `POST /api/v3/order`; WS API `wss://ws-api.binance.com:443/ws-api/v3` with methods `order.place`, `order.cancel`, `order.cancelReplace`, `order.amend.keepPriority`, `openOrders.cancelAll`. FIX order-entry (`fix-oe.binance.com:9000`) also available for Ed25519 keys.
- Post-only: order `type = LIMIT_MAKER` (no `timeInForce`). Rejected (`-2010`, "Order would immediately match and take.") if it would cross (https://github.com/binance/binance-spot-api-docs/blob/master/errors.md).
- Amend: `PUT /api/v3/order/amend/keepPriority` — **reduce quantity only**, keeps queue priority; weight 4 (0 when it results in expiry). Price change requires `POST /api/v3/order/cancelReplace` with `cancelReplaceMode` = `STOP_ON_FAILURE` | `ALLOW_FAILURE` and optional `orderRateLimitExceededMode` (`DO_NOTHING` | `CANCEL_ONLY`) — this is a cancel + new, so it loses priority and consumes an unfilled-order-count slot.
- Batch: **no batch place** on spot; `DELETE /api/v3/openOrders` cancels all on a symbol. OCO/OTO/OPO order lists exist but are not batch quoting tools.
- Client order id `newClientOrderId`: must match `^[\.A-Z\:/a-z0-9_-]{1,36}$`, unique among open orders.
- STP: `selfTradePreventionMode` = `NONE`, `EXPIRE_TAKER`, `EXPIRE_MAKER`, `EXPIRE_BOTH`, `DECREMENT` (https://github.com/binance/binance-spot-api-docs/blob/master/faqs/stp_faq.md). Symbol default from `exchangeInfo.defaultSelfTradePreventionMode`.

**USDⓈ-M futures** (https://developers.binance.com/docs/derivatives/usds-margined-futures/trade/rest-api ; confirmed via https://github.com/binance/binance-futures-connector-python/blob/main/binance/um_futures/account.py and the Java connector `NewOrderExample.java`):
- REST `POST /fapi/v1/order`; WS API `wss://ws-fapi.binance.com/ws-fapi/v1` with `order.place`, `order.modify`, `order.cancel`, `order.status`.
- Post-only: `timeInForce = GTX` (Good-Till-Crossing). Rejected with `-5022` ("Due to the order could not be executed as maker, the Post Only order will be rejected") if it would cross. `GTD` also exists (goodTillDate).
- Modify: `PUT /fapi/v1/order` (`order.modify`) — LIMIT orders only, can change price and/or quantity; the order **re-enters the queue** (loses priority) even for quantity decreases (**unverified** for pure decrease; docs state modify "re-enters matching queue"). `PUT /fapi/v1/batchOrders` for up to 5 modifies.
- Batch: `POST /fapi/v1/batchOrders` up to **5 orders**; `DELETE /fapi/v1/batchOrders` up to 10 cancels; `DELETE /fapi/v1/allOpenOrders` cancel-all per symbol; `POST /fapi/v1/countdownCancelAll` dead-man switch (`countdownTime` ms, 0 disables).
- Client order id `newClientOrderId`: `^[\.A-Z\:/a-z0-9_-]{1,36}$`. Futures also has `priceMatch` (OPPONENT/QUEUE pegs) and `selfTradePreventionMode` (`EXPIRE_TAKER`, `EXPIRE_MAKER`, `EXPIRE_BOTH`, `NONE`).

### 3. Rate limits

**Spot** (https://github.com/binance/binance-spot-api-docs/blob/master/rest-api.md#limits, `web-socket-api.md#rate-limits`, https://github.com/binance/binance-spot-api-docs/blob/master/faqs/order_count_decrement.md):
- Types `REQUEST_WEIGHT` (per IP, per minute), `ORDERS` (unfilled order count, per account, 10 s and 1 day windows), `RAW_REQUESTS` (per IP, 5 min). Live values come from `GET /api/v3/exchangeInfo` — currently 6000 weight/min, 100 orders/10 s, 200,000 orders/day (**unverified live numbers; read from exchangeInfo at startup**).
- **Unfilled order count**: every new order counts; a fill (partial or full) *decrements* the count; cancels do **not**. Tracked per (sub)account across all IPs and keys. Exceeding → HTTP 429 and `-1015 TOO_MANY_ORDERS`. Headers `X-MBX-ORDER-COUNT-10S`, `X-MBX-ORDER-COUNT-1D`, `X-MBX-USED-WEIGHT-1M`.
- Weight abuse → HTTP 429; continuing after 429 → HTTP 418 and an IP ban scaling from **2 minutes to 3 days** with `Retry-After` header.
- WS API: 300 connections per 5 min per IP; connection costs 2 weight; `rateLimits` echoed in every response; 429 when limits are hit. Ed25519 `session.logon` lets you omit apiKey/signature per request.
- Market streams: 5 incoming msgs/s per connection, 1024 streams/connection.

**USDⓈ-M futures** (https://developers.binance.com/docs/derivatives/usds-margined-futures/general-info ; values confirmed via exchangeInfo mirrors e.g. https://hexdocs.pm/binance_futures/BinanceFutures.USDM.MarketData-function-exchange_info.html):
- `REQUEST_WEIGHT` 2,400 / min per IP; `ORDERS` 1,200 / min and **300 / 10 s per account** (order placement/modify/cancel each cost order-count units; cancels count here, unlike spot's unfilled-order-count). HTTP 429 then 418 IP bans as in spot. `X-MBX-USED-WEIGHT-1M`, `X-MBX-ORDER-COUNT-10S`, `X-MBX-ORDER-COUNT-1M` headers.
- WS market streams: 200 streams/conn, 10 msgs/s/conn. WS API (`ws-fapi`): connection limits and `rateLimits` echo follow the spot model (**unverified** exact numbers).

### 4. Fees

- Spot regular user: **0.10% / 0.10%** maker/taker; with BNB fee payment −25% → 0.075%/0.075% (https://www.binance.com/en/fee/trading). Stablecoin pairs (e.g., FDUSD/USDC pairs) have promotional zero maker fees at times — check the live page.
- USDⓈ-M futures regular user: **0.02% maker / 0.05% taker**; −10% with BNB fee payment → 0.018%/0.045% (https://www.binance.com/en/fee/futureFee). VIP tiers: maker falls to 0.00% at VIP9 (perps).
- Spot Liquidity Provider (Market Maker) Program: requires ≥1,000 BTC-equivalent 30-day spot maker volume or existing MM status elsewhere; rebates up to −0.005%/−0.01% maker on eligible pairs; quoting obligations (spread/size/uptime) set per pair (https://www.binance.com/en/support/announcement/binance-spot-liquidity-provider-program — thresholds **unverified**, page requires login/region).
- Futures Market Maker Program: application via `futures.mm@binance.com`; tiered maker rebates (e.g., −0.005% to −0.010% on USDⓈ-M) tied to maker volume share; requires VIP tier and volume (https://www.binance.com/en/support/faq/binance-futures-market-maker-program — **unverified** current numbers).
- Both programs also unlock higher order-rate limits and dedicated market-data infrastructure (**unverified**).

### 5. User data / private streams

**Spot** (https://github.com/binance/binance-spot-api-docs/blob/master/user-data-stream.md, https://github.com/binance/binance-spot-api-docs/blob/master/CHANGELOG.md):
- **listenKey is deprecated** (`POST /api/v3/userDataStream` on `stream.binance.com`, removed after 2025-10-24). Use the WS API: `session.logon` with an **Ed25519** key, then `userDataStream.subscribe` (or `userDataStream.subscribe.signature` without logon). No keep-alive pings required beyond the connection's 24 h lifetime.
- Events: `executionReport` (order + fill; `x` execution type, `X` status, `l` last fill qty, `L` last fill price, `n` commission, `N` commission asset, `m` = true if the account was the **maker**, `t` trade id), `outboundAccountPosition` (balances), `balanceUpdate`, `listStatus`, `eventStreamTerminated`, `externalLockUpdate`.

**USDⓈ-M futures** (https://developers.binance.com/docs/derivatives/usds-margined-futures/user-data-streams ; confirmed via https://github.com/binance/binance-futures-connector-python/blob/main/binance/um_futures/data_stream.py):
- Still uses **listenKey**: `POST /fapi/v1/listenKey` (valid **60 min**), `PUT /fapi/v1/listenKey` to extend, `DELETE` to close; connect to `wss://fstream.binance.com/ws/<listenKey>`. Renew every ~30 min. (A WS-API `userDataStream.start` path exists on `ws-fapi` too — **unverified**.)
- Events: `ORDER_TRADE_UPDATE` (`o.x` exec type, `o.X` status, `o.l`/`o.L` last fill, `o.n` commission, `o.N` commission asset, `o.m` maker flag, `o.rp` realized PnL; `c` starting with `autoclose-` = liquidation, `adl_autoclose` = ADL), `ACCOUNT_UPDATE` (balances `B` + positions `P`), `MARGIN_CALL`, `ACCOUNT_CONFIG_UPDATE`, `TRADE_LITE` (lightweight fill event), `listenKeyExpired`.

### 6. Instrument metadata

- Spot `GET /api/v3/exchangeInfo` (weight 20; filter by `symbol`/`symbols`/`permissions`). Per-symbol `filters`: `PRICE_FILTER` (`tickSize`, `minPrice`, `maxPrice`), `LOT_SIZE` (`stepSize`, `minQty`, `maxQty`), `MARKET_LOT_SIZE`, `NOTIONAL`/`MIN_NOTIONAL` (`minNotional`, `applyMinToMarket`, `avgPriceMins`), `PERCENT_PRICE_BY_SIDE` (price band vs weighted avg price), `MAX_NUM_ORDERS` (open orders per symbol, typically 200), `MAX_NUM_ALGO_ORDERS`, `MAX_NUM_ORDER_AMENDS`, `MAX_POSITION`; exchange-wide `EXCHANGE_MAX_NUM_ORDERS` (https://github.com/binance/binance-spot-api-docs/blob/master/filters.md). `baseAssetPrecision` / `quoteAssetPrecision` give decimals; `tickSize`/`stepSize` are the binding constraints.
- Futures `GET /fapi/v1/exchangeInfo`: `pricePrecision`, `quantityPrecision`, filters `PRICE_FILTER`, `LOT_SIZE`, `MARKET_LOT_SIZE`, `MAX_NUM_ORDERS`, `MAX_NUM_ALGO_ORDERS`, `MIN_NOTIONAL` (typically 5 USDT on majors), `PERCENT_PRICE` (`multiplierUp/Down` vs **mark price**) (https://developers.binance.com/docs/derivatives/usds-margined-futures/common-definition).
- Frequency: tick/step sizes change occasionally (announced ~1 day ahead; more common for small caps). Refresh exchangeInfo at startup and at least daily; treat `-1013`/`-1111` filter errors as a trigger to refresh.

### 7. Testnet / demo

- Spot Testnet: `https://testnet.binance.vision/api` + `wss://stream.testnet.binance.vision` / `wss://ws-api.testnet.binance.vision/ws-api/v3` (https://testnet.binance.vision). Supports `/api` endpoints only (no `/sapi`); separate keys; periodic data resets.
- Spot **Demo Mode** (newer): REST `https://demo-api.binance.com/api`, WS API `wss://demo-ws-api.binance.com/ws-api/v3`, streams `wss://demo-stream.binance.com`, plus SBE and FIX demo endpoints; keys created under "Binance Demo Trading" (https://github.com/binance/binance-spot-api-docs/blob/master/demo-mode/general-info.md).
- Futures: the old `testnet.binancefuture.com` is being retired in favor of **Demo Trading** at `https://demo-fapi.binance.com` / `wss://demo-fstream.binance.com` (CCXT exposes `enable_demo_trading(True)`) (https://developers.binance.com/docs/derivatives/usds-margined-futures/general-info — **unverified** exact date of testnet shutdown).
- Limitations for MM: demo/testnet books are thin and price feeds are copies of production, so queue position, fill rates, and adverse selection are not representative. Use them for protocol/plumbing tests only; use tiny size on production for fill-behaviour tests.

### 8. Infrastructure

- Hosting: **AWS ap-northeast-1 (Tokyo)** for spot and futures matching/API gateways; co-locating in ap-northeast-1 gives ~1–3 ms RTT (community/third-party measurements; Binance does not publish this — confidence medium-high, **unverified** against official statement).
- Timestamps: `timestamp` in ms (optionally µs with `X-MBX-TIME-UNIT: MICROSECOND` / `timeUnit` param); `recvWindow` default 5000 ms, max 60000 ms; request rejected (`-1021`) if `timestamp` is more than 1000 ms ahead of server time or older than `serverTime - recvWindow` (https://github.com/binance/binance-spot-api-docs/blob/master/rest-api.md#timing-security). Same rule on futures (`recvWindow` ≤ 60000).
- Signatures: HMAC-SHA256, RSA, or **Ed25519** (required for WS API session auth and FIX). Prefer Ed25519.
- Server time: `GET /api/v3/time`, `GET /fapi/v1/time`.

### 9. Gotchas for MM

- Spot unfilled-order-count: cancels do not free slots; a quote loop that places+cancels without fills burns 10 s/day budget fast. Use `cancelReplace` sparingly; prefer `amend.keepPriority` for size-down; consider quoting fewer levels.
- Futures `PERCENT_PRICE`: BUY price ≤ mark × `multiplierUp`, SELL ≥ mark × `multiplierDown`; quotes far from mark are rejected. Spot `PERCENT_PRICE_BY_SIDE` uses weighted average price over `avgPriceMins`.
- `LIMIT_MAKER` / `GTX` are **rejected**, never price-adjusted. Handle `-2010` (spot) and `-5022` (futures) as normal flow.
- `MAX_NUM_ORDERS` (spot per symbol, commonly 200) and futures `MAX_NUM_ORDERS` (commonly 200) cap ladder depth.
- Order book vs trade stream: `@bookTicker` and `@trade` are real-time while `@depth` is batched (100 ms spot, 250 ms futures default) — trades can print before the depth diff reflecting them arrives. Use `bookTicker` for top-of-book decisions.
- Futures `pu` field is mandatory in sync; spot uses `U == prev_u + 1`. They differ — do not share code blindly.
- 24 h connection lifetime + `serverShutdown` event: implement seamless reconnect with overlap.
- `listenKey` deprecation on spot: new spot user-data code must use the WS API with Ed25519 keys.
- Sub-accounts: rate limits and unfilled-order counts are per (sub)account, so isolating each strategy into a sub-account multiplies the order budget. API key restrictions: enable only "Enable Reading" + "Enable Spot & Margin Trading" / "Enable Futures"; restrict to trusted IPs — unrestricted keys with trading permission auto-expire after 90 days of inactivity (**unverified**).
- ADL on futures: positions can be auto-deleveraged during liquidation cascades; `ORDER_TRADE_UPDATE` `c = adl_autoclose`. Keep leverage low, use `positionSide` correctly in hedge mode.
- Minimum notional: spot commonly 5 USDT (`NOTIONAL` filter); futures 5 USDT (`MIN_NOTIONAL`) — plus `MIN_NOTIONAL` may be raised for some pairs; read from exchangeInfo.

### 10. Libraries

- CCXT / CCXT Pro `binance` (`binanceusdm` alias for futures): `watch_order_book`, `watch_trades`, `watch_bids_asks`, `watch_mark_price(s)`, `watch_balance`, `watch_orders`, `watch_my_trades`, `watch_positions`, and WS trading `create_order_ws`, `edit_order_ws`, `cancel_order_ws`, `cancel_all_orders_ws` (https://github.com/ccxt/ccxt/blob/master/python/ccxt/pro/binance.py). Supports Ed25519 keys.
- Official: `binance-connector-python` (spot, https://github.com/binance/binance-connector-python), `binance-futures-connector-python` (https://github.com/binance/binance-futures-connector-python), `binance-connector-java` (has ws-fapi trading examples), plus new generated connectors (`binance-sdk-*`).
- Rust: NautilusTrader Binance adapter (spot + futures, https://nautilustrader.io/docs/latest/integrations/binance/); HftBacktest Rust live connector for Binance Futures (https://github.com/nkaz001/hftbacktest); Barter-rs (`barter-data`) for market data; `binance-rs` community client (REST + WS, no WS trading).

---

## Bybit

### 1. Market data

Endpoints (https://bybit-exchange.github.io/docs/v5/ws/connect): public `wss://stream.bybit.com/v5/public/spot|linear|inverse|option`, private `wss://stream.bybit.com/v5/private`, trade `wss://stream.bybit.com/v5/trade`. USDT perps are `category=linear`.

Order book (https://bybit-exchange.github.io/docs/v5/websocket/public/orderbook):

| Category | Depth | Push frequency |
|---|---|---|
| Linear/Inverse | 1 | 10 ms |
| Linear/Inverse | 50 | 20 ms |
| Linear/Inverse | 200 | 100 ms |
| Linear/Inverse | 1000 | 300 ms |
| Spot | 1 | 10 ms |
| Spot | 50 | 20 ms |
| Spot | 200 | 200 ms |
| Spot | 1000 | 300 ms |
| Option | 25 / 100 | 20 ms / 100 ms |

- Topic `orderbook.{depth}.{symbol}`. First message `type: "snapshot"`, then `type: "delta"`. Level-1 is always pushed as snapshot. Delta rules: `size == 0` → delete; price not present → insert; present → update. Fields: `u` (update id; `u == 1` means a service restart → treat as a fresh snapshot), `seq` (cross-sequence; a smaller `seq` means earlier data; the same `seq` across topics/trades indicates the same matching event), `cts` (matching-engine timestamp).
- Sync: apply the snapshot, then apply deltas in order; if `u` is not contiguous or a snapshot arrives, reset. Bybit recommends re-subscribing on any gap. No checksum.
- Trades: `publicTrade.{symbol}` real-time; fields `T`, `s`, `S`, `v`, `p`, `L` (tick direction), `i`, `BT` (block trade), `RPI`, `seq` — up to 1024 trades per message (https://bybit-exchange.github.io/docs/v5/websocket/public/trade).
- BBO: `orderbook.1.{symbol}` (10 ms) is the fastest L1; `tickers.{symbol}` gives `bid1Price/ask1Price` plus `markPrice`, `indexPrice`, `fundingRate`, `nextFundingTime` at 100 ms for derivatives (snapshot/delta) and 50 ms (snapshot) for spot (https://bybit-exchange.github.io/docs/v5/websocket/public/ticker).
- Mark/index/funding: via `tickers` (derivatives); `kline`, `liquidation`/`allLiquidation`, `orderbook.rpi` (RPI-inclusive book), `insurance` also exist.
- Public subscription limits: Spot max 10 `args` per subscribe request; futures no limit; Option 2000 (https://bybit-exchange.github.io/docs/v5/ws/connect). Heartbeat `{"op":"ping"}` every 20 s.

### 2. Order entry

Source: https://bybit-exchange.github.io/docs/v5/order/create-order , https://bybit-exchange.github.io/docs/v5/order/amend-order , https://bybit-exchange.github.io/docs/v5/order/batch-place , https://bybit-exchange.github.io/docs/v5/websocket/trade/guideline

- REST `POST /v5/order/create`, `/amend`, `/cancel`, `/cancel-all`, and batch `/v5/order/create-batch`, `/amend-batch`, `/cancel-batch`. Same endpoints for spot and linear (`category` param).
- WS order entry: `wss://stream.bybit.com/v5/trade` with `op: order.create | order.amend | order.cancel | order.create-batch | order.amend-batch | order.cancel-batch`; requires auth and `X-BAPI-TIMESTAMP` / `X-BAPI-RECV-WINDOW` in a `header` object of each message.
- Post-only: `timeInForce = "PostOnly"` (also `GTC`, `IOC`, `FOK`, `RPI` — retail price improvement, maker-only vs. retail flow). Post-only orders that would cross are **cancelled/rejected**, not adjusted. Legacy `orderFilter`/`orderType` only `Limit`/`Market`.
- Amend: `POST /v5/order/amend` on unfilled or partially filled orders; can change `qty`, `price`, `triggerPrice`, TP/SL, `orderIv`. Amending price re-queues; qty-decrease keeps priority (**unverified**, standard behaviour).
- Batch: `create-batch`, `amend-batch`, `cancel-batch` accept up to **20 orders per request for linear/inverse/option** and **10 for spot** (https://bybit-exchange.github.io/docs/v5/order/batch-place). Rate limit is consumed per actual order count, not per request.
- Cancel-all: `POST /v5/order/cancel-all` (by category, symbol, or `baseCoin`/`settleCoin`). Dead-man switch `POST /v5/order/disconnected-cancel-all` (DCP, 3–300 s window) — **institutional accounts only** (https://bybit-exchange.github.io/docs/v5/order/dcp).
- Client order id `orderLinkId`: ≤36 chars; must be unique among open orders; letters, digits, `-` and `_`. Spot allows reuse after fill; derivatives require uniqueness per active order.
- Open-order caps: perps/futures **500 open orders per symbol**; spot 500 total per account; conditional orders limited separately (https://bybit-exchange.github.io/docs/v5/order/create-order).
- STP: `smpType` = `None` | `CancelMaker` | `CancelTaker` | `CancelBoth`; SMP groups for institutional accounts (https://bybit-exchange.github.io/docs/v5/smp).
- `reduceOnly`, `closeOnTrigger`, `positionIdx` (0 one-way, 1/2 hedge) for linear.

### 3. Rate limits

Source: https://bybit-exchange.github.io/docs/v5/rate-limit

- IP limit: **600 requests / 5 s per IP** (HTTP 403 "access too frequent" → 10 min block on abuse).
- API (UID) limits, per second, per category: `order/create` Spot **20/s**, Linear **10/s**; `order/amend` 10/s both; `order/cancel` Spot 20/s, Linear 10/s; `cancel-all` Spot 20/s, Linear 10/s; batch endpoints share the corresponding single-order buckets and are counted by order count. Headers `X-Bapi-Limit`, `X-Bapi-Limit-Status`, `X-Bapi-Limit-Reset-Timestamp`. Exceeding → `retCode 10006` (HTTP 200 body) with `X-Bapi-Limit-Reset-Timestamp` telling when to resume.
- Institutional/Pro tiers: VIP/Pro levels can raise per-second limits (up to 300/s at Pro 6 via application) — see the "Upgrade" table in the same page.
- WS: **500 connections per 5 min per IP**; max **1000 public connections per IP** (separate counts for spot/linear/inverse/option); private connections limited by `max_active_time` (30 s–600 s) and heartbeat.
- WS trade: same UID limits as REST (counted together).

### 4. Fees

- VIP0 (non-VIP): Spot **0.10% / 0.10%**; USDT perps **0.02% maker / 0.055% taker** (https://www.bybit.com/en/help-center/article/Trading-Fee-Structure). VIP1–Supreme VIP lower maker to 0.00%–0.01% on perps.
- No native discount token (there is no equivalent of BNB/OKB); MNT holding affects VIP tier in some regions (**unverified**). Regional entities (Bybit EU, Bybit NL) have different schedules.
- Market Maker Incentive Program (https://www.bybit.com/en/help-center/article/Market-Maker-Incentive-Program): apply via `institutional_services@bybit.com`. Spot MM tiers (MM1–MM3) by 30-day volume / maker-volume share with maker rebates up to **−0.0075%**; Derivatives MM tiers by maker-volume share with quoting obligations (e.g. resting orders ≥10× min size within spread bands for X% of time). Numbers change quarterly — **treat current thresholds as unverified**.
- Fee rate API: `GET /v5/account/fee-rate` returns the account's `makerFeeRate` / `takerFeeRate` per symbol.

### 5. User data / private streams

Source: https://bybit-exchange.github.io/docs/v5/websocket/private/order , https://bybit-exchange.github.io/docs/v5/websocket/private/execution , https://bybit-exchange.github.io/docs/v5/websocket/private/position , https://bybit-exchange.github.io/docs/v5/websocket/private/wallet

- Private WS `wss://stream.bybit.com/v5/private`: auth message `{"op":"auth","args":[api_key, expires, signature]}` where `signature = HMAC_SHA256(secret, "GET/realtime" + expires)`; `expires` is a future Unix ms timestamp. Optional `?max_active_time=600s` (30 s–10 min) to force periodic reconnection.
- Topics: `order` (all order state changes, `rejectReason`), `execution` (fills: `execPrice`, `execQty`, `execFee`, `feeRate`, `isMaker`, `execType` = `Trade|AdlTrade|Funding|BustTrade|Settle|BlockTrade`, `seq`), `execution.fast` (lightweight fill stream, lower latency, fewer fields), `position`, `wallet`, `greeks`, `dcp`.
- No listenKey; connection auth persists; send `ping` every 20 s.
- Fee sign: positive `execFee` = paid, negative = rebate. `feeCurrency` provided for spot.

### 6. Instrument metadata

- `GET /v5/market/instruments-info?category=spot|linear` (https://bybit-exchange.github.io/docs/v5/market/instrument): `priceFilter.tickSize` (+ `minPrice`/`maxPrice` for linear), `lotSizeFilter.qtyStep` (linear) / `basePrecision`, `quotePrecision` (spot), `minOrderQty`, `maxOrderQty`, `maxMktOrderQty`, `minNotionalValue`, `priceScale`, `riskParameters.priceLimitRatioX/Y` (price band vs. mark/ref price), `status`, `fundingInterval`.
- Bybit adjusts `maxOrderQty` / `maxMktOrderQty` roughly bi-monthly; `tickSize`/`qtyStep` changes are announced. Refresh daily and on `retCode 10001` parameter errors.

### 7. Testnet / demo

- Testnet: REST `https://api-testnet.bybit.com`, WS `wss://stream-testnet.bybit.com/v5/...` — full API incl. WS trade; separate account/keys; faucet-funded (https://bybit-exchange.github.io/docs/v5/guide).
- Demo Trading (mainnet UI toggle): REST `https://api-demo.bybit.com`, private WS `wss://stream-demo.bybit.com`; uses **production market data** with simulated fills; **WS trade not supported**; limited endpoint list; `POST /v5/account/demo-apply-money` to top up (https://bybit-exchange.github.io/docs/v5/demo).
- Limitations: testnet books are thin and manipulated; demo uses real prices but simulated matching (fills when price crosses your level, no queue). Good for plumbing, not for fill-rate or queue research.

### 8. Infrastructure

- Hosting: **AWS ap-southeast-1 (Singapore)** for matching engine and API gateways; co-locating in ap-southeast-1 gives ~1–2 ms RTT. Bybit publicly recommends Singapore AWS for low latency in institutional materials (**confidence medium-high; unverified** against a doc URL — third-party latency guides).
- Alternate REST host `https://api.bytick.com`; regional hosts `api.bybit.nl`, `api.byhkbit.com`, `api.bybit-tr.com` for regulated entities (https://bybit-exchange.github.io/docs/v5/guide).
- Timestamps: headers `X-BAPI-TIMESTAMP` (ms), `X-BAPI-RECV-WINDOW` (default 5000 ms), `X-BAPI-SIGN` (HMAC-SHA256 or RSA). Validity: `server_time - recv_window <= timestamp < server_time + 1000` (https://bybit-exchange.github.io/docs/v5/guide). Server time `GET /v5/market/time`.

### 9. Gotchas for MM

- `u` / `seq`: `u` is per-topic contiguity; `seq` is the cross-topic matching sequence. Use `seq` to align `publicTrade` and `orderbook` (trades often arrive before the corresponding book delta). `u == 1` means a service restart — treat as snapshot.
- Spot vs linear WS are different hosts; run two public connections.
- `PostOnly` is rejected (order status `Rejected`/`Cancelled` with `rejectReason` `EC_PostOnlyWillTakeLiquidity`) — not repriced.
- Price bands: `riskParameters.priceLimitRatioX/Y` from instruments-info; orders beyond the band are rejected (`retCode 110xxx`). For linear, price deviation from mark also limits "Limit" orders.
- Per-second UID limits (10/s linear) are **low** relative to OKX/Binance — batch endpoints are essential (20 orders per request) and each order still counts 1 toward the bucket (so batches don't increase the per-second order budget, just reduce round-trips).
- 500 open orders per symbol cap; conditional order caps are lower.
- Unified Trading Account (UTA 2.0) is required for most V5 features (spot margin, cross-collateral); classic accounts have a different API surface.
- ADL: Bybit uses ADL after insurance-fund exhaustion; `execType = AdlTrade` on the execution stream (https://bybit-exchange.github.io/docs/v5/websocket/private/execution).
- Sub-accounts: created via `POST /v5/user/create-sub-member`; each sub-UID has its own rate limit buckets. API keys can be IP-whitelisted; non-whitelisted keys expire after **3 months** (docs: "keys without IP restriction expire in 3 months" — https://bybit-exchange.github.io/docs/v5/guide, **unverified** exact wording).
- Institutional-only features: DCP dead-man switch, SMP groups, higher rate limits. Retail must implement its own kill-switch (cancel-all on heartbeat loss).

### 10. Libraries

- CCXT / CCXT Pro `bybit`: `watch_order_book`, `watch_trades`, `watch_bids_asks`, `watch_ticker`, `watch_orders`, `watch_my_trades`, `watch_positions`, `watch_balance`; WS trading `create_order_ws`, `edit_order_ws`, `cancel_order_ws` (https://github.com/ccxt/ccxt/blob/master/python/ccxt/pro/bybit.py). Demo mode via `enable_demo_trading(True)`.
- Official Python SDK: `pybit` (https://github.com/bybit-exchange/pybit) — REST + WS incl. WS trade.
- Rust: NautilusTrader Bybit adapter (spot + linear, https://nautilustrader.io/docs/latest/integrations/bybit/); HftBacktest experimental Bybit live connector; Barter-rs Bybit data.

---

## Comparison table

| Topic | OKX | Binance | Bybit |
|---|---|---|---|
| Fastest public L1 | `bbo-tbt` 10 ms | `@bookTicker` real-time (spot & futures) | `orderbook.1` 10 ms |
| Fastest public L2 | `books` 400 lvls @100 ms (tick-by-tick needs VIP4/5) | spot `@depth@100ms`; futures `@depth@100ms` | linear `orderbook.50` @20 ms; spot `orderbook.50` @20 ms |
| Book integrity | `seqId`/`prevSeqId` (checksum deprecated) | `U`/`u` (spot), `pu` chain (futures) + REST snapshot | `u` contiguity + `seq`; snapshot/delta, no checksum |
| Mark/funding stream | `mark-price` 200 ms, `funding-rate` 30–90 s | `@markPrice@1s` (perps) | `tickers` 100 ms (perps) |
| WS order entry | Yes (private WS `order`/`amend-order`/…) | Yes (spot `ws-api`, futures `ws-fapi`) | Yes (`/v5/trade`, not in demo) |
| Post-only flag | `ordType=post_only` | spot `type=LIMIT_MAKER`; futures `timeInForce=GTX` | `timeInForce=PostOnly` |
| Post-only cross | reject | reject (`-2010` / `-5022`) | reject |
| Amend | `amend-order` (px & sz), batch 20 | spot `amend.keepPriority` (qty down only) / `cancelReplace`; futures `PUT /fapi/v1/order` (LIMIT, px/qty, re-queues), batch 5 | `order/amend` (px, qty, TP/SL), batch 20 (spot 10) |
| Batch place / cancel | 20 / 20 | spot none / cancel-all per symbol; futures 5 / 10 | 20 (spot 10) / 20 |
| Dead-man switch | `cancel-all-after` 10–120 s (all users) | futures `countdownCancelAll` (all users); spot none | DCP 3–300 s (institutional only) |
| Order rate limit | 60 req/2 s per instrument; 300 orders/2 s batch; 1000/2 s per sub-account | spot: unfilled-order count (≈100/10 s, 200k/day) per account + 6000 weight/min per IP; futures 300 orders/10 s, 1200/min, 2400 weight/min | 10/s linear, 20/s spot per UID per endpoint; 600 req/5 s per IP |
| Limit keying | per instrument + per sub-account | IP (weight) + account (orders) | UID (+ IP for raw) |
| Over-limit behaviour | 429 / code 50011 | 429 → 418 IP ban 2 min–3 days | `retCode 10006`, IP 403 block on abuse |
| VIP0 spot fees | 0.08% / 0.10% | 0.10% / 0.10% (0.075% with BNB) | 0.10% / 0.10% |
| VIP0 perps fees | 0.02% / 0.05% | 0.02% / 0.05% (0.018%/0.045% with BNB) | 0.02% / 0.055% |
| MM program entry | VIP2+ or MM elsewhere; email | 1000 BTC/30 d spot volume or MM elsewhere (**unverified**); futures via email | Email; tiered by maker share; rebates to −0.0075% |
| Private stream auth | WS login (HMAC), no listenKey | spot: Ed25519 `session.logon` + `userDataStream.subscribe` (listenKey deprecated); futures: listenKey 60 min + PUT keepalive | WS `auth` (HMAC), no listenKey |
| Fill fee / liquidity fields | `fillFee`, `fillFeeCcy`, `execType` T/M | `n`, `N`, `m` (maker bool) | `execFee`, `feeRate`, `isMaker` |
| Instrument metadata | `/public/instruments` (`tickSz`, `lotSz`, `minSz`, `ctVal`) | `exchangeInfo` filters | `/market/instruments-info` filters |
| Min notional | none on spot (minSz); perps via `minSz`×`ctVal` | 5 USDT typical | `minNotionalValue` (≈1–5 USDT) |
| Demo/testnet | Demo via `x-simulated-trading: 1` + `wspap` WS (full API) | Spot Testnet + Spot Demo Mode; Futures Demo Trading (testnet retiring) | Testnet (full incl. WS trade) + Demo (real prices, no WS trade) |
| Hosting (unverified, med-high conf.) | Alibaba Cloud Hong Kong | AWS Tokyo ap-northeast-1 | AWS Singapore ap-southeast-1 |
| Timestamp tolerance | ±30 s (ISO-8601) | `recvWindow` ≤ 60 s, ≤1 s ahead | `recvWindow` default 5 s, ≤1 s ahead |
| CCXT Pro WS trading | yes | yes | yes |
| Official SDK | `python-okx` | `binance-connector`, `binance-futures-connector` | `pybit` |
| Rust adapters | NautilusTrader, Barter, dcex | NautilusTrader, HftBacktest, Barter | NautilusTrader, HftBacktest (exp.), Barter |

---

## Recommendations for our MM bot

### Starting venue & market

Start on **Bybit USDT perpetuals (`category=linear`)**, second choice **OKX USDT-SWAP**, and treat Binance as the venue to graduate to once the bot is proven. Rationale:

1. **Market data quality for retail**: Bybit gives a public 50-level book at **20 ms** and L1 at 10 ms with a simple snapshot/delta + `seq` model. OKX's public L2 is 100 ms (tick-by-tick needs VIP4+ KYC), Binance futures depth is 100 ms at best. Bybit's `seq` lets us align trades and book updates, which matters for adverse-selection filters.
2. **Order entry ergonomics**: Bybit offers WS order entry, batch place/amend/cancel of 20 orders, full amend (price + qty), and a full-featured testnet including WS trade. Binance spot has no batch place and its `cancelReplace` burns the unfilled-order budget.
3. **Rate limit model is predictable**: Bybit's 10 orders/s per endpoint per UID is small but deterministic and exposed via headers; Binance's unfilled-order count punishes exactly the place→cancel churn a naive MM produces. OKX's per-instrument 60/2 s is generous and is the reason it is our second choice.
4. **Fees**: all three are 0.02% maker for perps at VIP0; Bybit taker is slightly worse (0.055%) which is irrelevant for a maker strategy. Binance's BNB discount is a minor edge later.
5. **Risk plumbing**: perps let us hedge with a single instrument and avoid spot inventory conversion; funding is a manageable term. Spot MM on Binance later benefits from the largest retail flow.

Suggested first market: **a mid-cap linear perp with tick/spread ratio favorable to MM** (e.g., a top-30 alt where the spread is ≥2–3 ticks most of the day) rather than BTCUSDT/ETHUSDT, where professional MMs sit at 1 tick. Validate tick, `qtyStep`, `minNotionalValue`, and `priceLimitRatio` from `instruments-info` at startup.

### Streams to use (Bybit linear)

- `orderbook.50.{symbol}` (20 ms) as the primary book; `orderbook.1.{symbol}` for fastest mid; `publicTrade.{symbol}` for flow/toxicity; `tickers.{symbol}` for mark, index, funding.
- Private: `order`, `execution` (or `execution.fast`), `position`, `wallet` on one private connection with `max_active_time=600s` and 20 s pings.
- Order entry over the WS trade endpoint; REST as fallback and for `cancel-all` on startup/shutdown.

### Order types

- `Limit` + `timeInForce=PostOnly` for all quotes; treat `EC_PostOnlyWillTakeLiquidity` rejections as a normal signal to re-price.
- Use `amend` for price/size changes (one call vs. cancel+create = 2 rate-limit units); fall back to cancel+create only when the amend fails.
- `reduceOnly` `IOC` orders for inventory flattening; set `smpType=CancelMaker` to avoid self-trades across sub-accounts.

### Rate-limit budget per quote loop (Bybit linear, 10/s per endpoint)

- Quote refresh loop at **200–250 ms** (4–5 cycles/s) with 2 levels per side = 4 live orders. Each cycle amends at most 4 orders → ≤20 amends/s in the worst case, which exceeds the 10/s amend bucket. Therefore: (a) batch all amends into **one `order.amend-batch` call per cycle** (still counts 4), and (b) only re-quote levels whose target price/size moved ≥1 tick / ≥10%, which in practice brings the average to ~2–4 amends/s.
- Reserve ~30% headroom: target ≤7 order operations/s steady state, keep `X-Bapi-Limit-Status` ≥ 3 before sending non-urgent amends, and always leave budget for one emergency `cancel-all`.
- Per-symbol scaling: each symbol adds ~2–4 ops/s; beyond 2–3 symbols per UID, use **sub-accounts** (separate UID buckets) or apply for a higher tier.
- For OKX the same loop fits comfortably in 60 req/2 s per instrument (or 300 orders/2 s via batch); for Binance futures, 300 orders/10 s per account is fine, but on Binance spot the unfilled-order count (~100/10 s) will be the binding constraint — budget ≤5 new orders/s and prefer `amend.keepPriority` for size-downs.

### Book maintenance

- Bybit: apply snapshot, then deltas; on non-contiguous `u` or `u == 1`, resubscribe. Cross-check top-of-book vs `orderbook.1` and drop quotes if they diverge for >100 ms.
- OKX: verify `prevSeqId == last seqId`; ignore `checksum`.
- Binance: implement both the spot (`U == prev_u+1`) and futures (`pu == prev_u`) chains; buffer events while fetching the REST snapshot.

### Operational

- Time sync: NTP/chrony on the host; query exchange server time on startup and compute offset; keep `recvWindow` at 5000 ms (Bybit/Binance) and never send timestamps >1 s ahead.
- Keys: trade-only permission, IP whitelist, one key per sub-account; store in a secrets manager; rotate before inactivity expiry (OKX 14 d, Bybit ~3 months, Binance ~90 d — verify).
- Kill switch: since Bybit's DCP is institutional-only, implement our own: cancel-all on private-stream heartbeat loss (>2 missed pongs) and on any book-integrity failure; on Binance futures use `countdownCancelAll` as a backstop; on OKX use `cancel-all-after` (60 s, refreshed every 20 s).
- Hosting: deploy in **AWS ap-southeast-1 (Singapore)** for Bybit (also decent to OKX HK ~30 ms and Binance Tokyo ~70 ms); if/when Binance becomes primary, move to ap-northeast-1.
- Language: start in **Python** with `pybit`/CCXT Pro for iteration speed (Bybit's 20 ms feed is well within asyncio's reach); move hot paths (book maintenance, quote calc) to **Rust** (NautilusTrader or a custom tokio client) once latency to first quote update matters; at retail rate limits, network RTT (1–2 ms colocated vs 30–70 ms remote) dominates over language overhead.
