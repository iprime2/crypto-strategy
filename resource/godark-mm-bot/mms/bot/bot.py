"""Vanilla GoDark market-making bot (post-only mass quote)."""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field

from godark import Environment, GodarkClient, MarketDataClient, Side
from godark.enums import OrderUpdateType
from godark.types import OrderUpdate, PositionUpdate, PositionsSnapshot

from config import BotConfig
from pricing import fair_jump_bps, half_spread_bps, quote_prices

log = logging.getLogger("vanilla_mm")


@dataclass
class QuoteState:
    fair: float | None = None
    fair_updated_at: float = 0.0
    inventory: float = 0.0
    bid_order_id: int | None = None
    ask_order_id: int | None = None
    paused: bool = False
    fills: list[dict] = field(default_factory=list)


class VanillaMMBot:
    """Two-sided post-only quotes via mass_quote; lean inventory; conservative width."""

    def __init__(self, config: BotConfig) -> None:
        self.config = config
        self.state = QuoteState()
        self._client: GodarkClient | None = None
        self._md: MarketDataClient | None = None
        self._stop = asyncio.Event()

    async def run(self) -> None:
        cfg = self.config
        log.info(
            "starting vanilla MM symbol=%s edge=%s dry_run=%s",
            cfg.symbol,
            cfg.edge_url,
            cfg.dry_run,
        )

        if cfg.dry_run:
            await self._run_dry()
            return

        async with GodarkClient(
            environment=Environment.DEVNET if cfg.environment == "devnet" else Environment.TESTNET,
            base_url=cfg.edge_url,
            api_key_id=cfg.api_key_id,
            api_secret=cfg.api_secret,
            passphrase=cfg.passphrase,
            auto_reconnect=True,
        ) as client:
            self._client = client
            await client.subscribe(["orders", "positions"])
            client.on_order_update(self._on_order_update)
            client.on_positions_snapshot(self._on_positions_snapshot)

            listener = asyncio.create_task(self._listen_private_streams(client))
            md_task = asyncio.create_task(self._run_market_data())
            quote_task = asyncio.create_task(self._quote_loop())

            try:
                await self._stop.wait()
            finally:
                for task in (listener, md_task, quote_task):
                    task.cancel()
                    with asyncio.suppress(asyncio.CancelledError):
                        await task

    def stop(self) -> None:
        self._stop.set()

    async def _run_dry(self) -> None:
        """Log quote math locally without connecting to GoDark."""
        cfg = self.config
        if cfg.fair_override is not None:
            self._set_fair(cfg.fair_override, source="override")
        else:
            self._set_fair(68000.0, source="dry_default")

        spread_bps = half_spread_bps(cfg.half_spread_bps, cfg.maker_fee_bps)
        while not self._stop.is_set():
            reservation, bid, ask = quote_prices(
                self.state.fair or 0.0,
                self.state.inventory,
                max_inventory=cfg.max_inventory,
                half_spread_bps=spread_bps,
                inventory_skew_bps=cfg.inventory_skew_bps,
                tick_size=cfg.tick_size,
            )
            log.info(
                "dry quote fair=%.4f res=%.4f bid=%.4f ask=%.4f q=%.6f",
                self.state.fair,
                reservation,
                bid,
                ask,
                self.state.inventory,
            )
            await asyncio.sleep(cfg.loop_interval_sec)

    async def _listen_private_streams(self, client: GodarkClient) -> None:
        async for _ in client.position_updates():
            pass

    async def _run_market_data(self) -> None:
        cfg = self.config
        if cfg.fair_override is not None:
            self._set_fair(cfg.fair_override, source="override")
            while not self._stop.is_set():
                await asyncio.sleep(1)
            return

        md = MarketDataClient(cfg.edge_url)
        self._md = md
        try:
            await md.connect()
        except Exception as exc:
            log.warning("market data unavailable (%s); waiting for position mark", exc)
            while not self._stop.is_set():
                await asyncio.sleep(1)
            return

        async def on_book(msg: dict) -> None:
            bids = msg.get("bids") or []
            asks = msg.get("asks") or []
            if not bids or not asks:
                return
            best_bid = float(bids[0][0] if isinstance(bids[0], (list, tuple)) else bids[0].get("price"))
            best_ask = float(asks[0][0] if isinstance(asks[0], (list, tuple)) else asks[0].get("price"))
            mid = (best_bid + best_ask) / 2.0
            self._set_fair(mid, source="book_mid")

        try:
            await md.subscribe_orderbook(cfg.symbol, on_book)
            while not self._stop.is_set():
                await asyncio.sleep(1)
        finally:
            await md.disconnect()

    async def _quote_loop(self) -> None:
        cfg = self.config
        spread_bps = half_spread_bps(cfg.half_spread_bps, cfg.maker_fee_bps)

        while not self._stop.is_set():
            await asyncio.sleep(cfg.loop_interval_sec)
            if self._client is None:
                continue
            if self.state.paused:
                log.warning("quotes paused (stale fair or jump)")
                continue
            if self.state.fair is None:
                log.debug("waiting for fair price")
                continue
            if self._fair_is_stale():
                self.state.paused = True
                log.warning("fair stale >%ss — pausing quotes", cfg.stale_fair_sec)
                continue

            try:
                reservation, bid, ask = quote_prices(
                    self.state.fair,
                    self.state.inventory,
                    max_inventory=cfg.max_inventory,
                    half_spread_bps=spread_bps,
                    inventory_skew_bps=cfg.inventory_skew_bps,
                    tick_size=cfg.tick_size,
                )
            except ValueError as exc:
                log.error("quote math failed: %s", exc)
                continue

            if abs(self.state.inventory) >= cfg.max_inventory:
                log.warning("inventory cap hit q=%.6f — skip adding", self.state.inventory)
                continue

            legs = [
                {
                    "side": Side.BUY,
                    "price": bid,
                    "quantity": cfg.order_qty,
                    "cancel_order_id": self.state.bid_order_id or 0,
                },
                {
                    "side": Side.SELL,
                    "price": ask,
                    "quantity": cfg.order_qty,
                    "cancel_order_id": self.state.ask_order_id or 0,
                },
            ]

            log.info(
                "quote fair=%.4f res=%.4f bid=%.4f ask=%.4f q=%.6f spread_bps=%.1f",
                self.state.fair,
                reservation,
                bid,
                ask,
                self.state.inventory,
                spread_bps,
            )

            if cfg.dry_run:
                continue

            try:
                ack = await self._client.mass_quote(cfg.symbol, legs, post_only=None)
            except Exception as exc:
                log.error("mass_quote failed: %s", exc)
                continue

            for result in ack.results:
                if result.status == "open" and result.new_order_id:
                    leg = legs[result.leg_index]
                    oid = int(result.new_order_id)
                    if leg["side"] == Side.BUY:
                        self.state.bid_order_id = oid
                    else:
                        self.state.ask_order_id = oid
                elif result.status == "failed":
                    log.warning(
                        "leg %s failed code=%s cancelled=%s",
                        result.leg_index,
                        result.error_code,
                        result.cancelled_order_id,
                    )

    def _set_fair(self, value: float, *, source: str) -> None:
        now = time.time()
        if self.state.fair is not None:
            jump = fair_jump_bps(self.state.fair, value)
            if jump >= self.config.jump_bps:
                self.state.paused = True
                log.warning(
                    "fair jump %.1f bps (%s -> %.4f) — pausing quotes",
                    jump,
                    source,
                    value,
                )
                self.state.fair = value
                self.state.fair_updated_at = now
                return
        self.state.fair = value
        self.state.fair_updated_at = now
        if source == "override":
            self.state.paused = False

    def _fair_is_stale(self) -> bool:
        if self.state.fair_updated_at <= 0:
            return True
        return (time.time() - self.state.fair_updated_at) > self.config.stale_fair_sec

    def _on_positions_snapshot(self, snap: PositionsSnapshot) -> None:
        cfg = self.config
        net = 0.0
        mark: float | None = None
        for row in snap.rows:
            size = float(row.size)
            if row.side.value == "SELL":
                size = -size
            net += size
            if row.mark_price:
                mark = float(row.mark_price)
        self.state.inventory = net
        if mark is not None and self.state.fair is None:
            self._set_fair(mark, source="position_mark")

    def _on_order_update(self, update: OrderUpdate) -> None:
        if update.update_type not in (OrderUpdateType.FILLED, OrderUpdateType.PARTIALLY_FILLED):
            return
        fair = self.state.fair
        record = {
            "ts": time.time(),
            "order_id": update.order_id,
            "side": str(update.side),
            "fill_price": update.price,
            "fill_qty": update.filled_qty,
            "fair_at_fill": fair,
        }
        self.state.fills.append(record)
        log.info(
            "fill side=%s px=%s filled_qty=%s fair=%s",
            update.side,
            update.price,
            update.filled_qty,
            fair,
        )
        asyncio.create_task(self._schedule_markouts(record))

    async def _schedule_markouts(self, record: dict) -> None:
        for delay in (1, 10, 60):
            await asyncio.sleep(delay)
            log.info(
                "markout +%ss fair=%s fill_px=%s side=%s",
                delay,
                self.state.fair,
                record.get("fill_price"),
                record.get("side"),
            )
