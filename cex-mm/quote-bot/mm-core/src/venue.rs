/// Stub for future OKX / Binance quoting adapters.
pub trait VenueAdapter: Send + Sync {
    fn name(&self) -> &'static str;
    fn place_post_only(
        &self,
        symbol: &str,
        side_buy: bool,
        qty: f64,
        price: f64,
        link_id: &str,
    ) -> Result<(), String>;
    fn cancel_all(&self, symbol: &str) -> Result<(), String>;
}
