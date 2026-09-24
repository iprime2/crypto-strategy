//! Pure analytics helpers (bucket choice, nullable bps averages).
//!
//! Aggregation over fills / pnl snapshots lives in `db`; this module stays
//! free of Postgres so unit tests do not need a database.

use chrono::{DateTime, Duration, Utc};
use serde::{Deserialize, Serialize};

/// Series bucket granularity for analytics responses.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum AnalyticsBucket {
    Hour,
    Day,
}

impl AnalyticsBucket {
    pub fn as_str(self) -> &'static str {
        match self {
            Self::Hour => "hour",
            Self::Day => "day",
        }
    }

    /// Postgres `date_trunc` unit matching this bucket.
    pub fn date_trunc_unit(self) -> &'static str {
        self.as_str()
    }
}

/// Hourly buckets when the inclusive range is 2 days or less; otherwise daily.
pub fn choose_bucket(from: DateTime<Utc>, to: DateTime<Utc>) -> AnalyticsBucket {
    if to - from <= Duration::days(2) {
        AnalyticsBucket::Hour
    } else {
        AnalyticsBucket::Day
    }
}

/// Average of present bps values; `None` when every input is `None` (or empty).
pub fn avg_nullable_bps(values: &[Option<f64>]) -> Option<f64> {
    let mut sum = 0.0;
    let mut n = 0usize;
    for v in values {
        if let Some(x) = *v {
            if x.is_finite() {
                sum += x;
                n += 1;
            }
        }
    }
    if n == 0 {
        None
    } else {
        Some(sum / n as f64)
    }
}

/// Reject analytics query ranges that are invalid or longer than 366 days.
pub fn validate_analytics_range(
    from: DateTime<Utc>,
    to: DateTime<Utc>,
) -> Result<(), &'static str> {
    if from > to {
        return Err("from must not be after to");
    }
    if to - from > Duration::days(366) {
        return Err("range must not exceed 366 days");
    }
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;
    use chrono::TimeZone;

    fn utc(y: i32, m: u32, d: u32, h: u32) -> DateTime<Utc> {
        Utc.with_ymd_and_hms(y, m, d, h, 0, 0).unwrap()
    }

    #[test]
    fn bucket_hour_when_range_exactly_two_days() {
        let from = utc(2026, 1, 1, 0);
        let to = utc(2026, 1, 3, 0);
        assert_eq!(choose_bucket(from, to), AnalyticsBucket::Hour);
    }

    #[test]
    fn bucket_hour_when_range_under_two_days() {
        let from = utc(2026, 1, 1, 0);
        let to = utc(2026, 1, 2, 12);
        assert_eq!(choose_bucket(from, to), AnalyticsBucket::Hour);
    }

    #[test]
    fn bucket_day_when_range_over_two_days() {
        let from = utc(2026, 1, 1, 0);
        let to = utc(2026, 1, 3, 0) + Duration::seconds(1);
        assert_eq!(choose_bucket(from, to), AnalyticsBucket::Day);
    }

    #[test]
    fn bucket_day_for_week_range() {
        let from = utc(2026, 1, 1, 0);
        let to = utc(2026, 1, 8, 0);
        assert_eq!(choose_bucket(from, to), AnalyticsBucket::Day);
    }

    #[test]
    fn avg_nullable_bps_skips_none_and_returns_none_when_empty() {
        assert_eq!(avg_nullable_bps(&[]), None);
        assert_eq!(avg_nullable_bps(&[None, None]), None);
        let avg = avg_nullable_bps(&[Some(10.0), None, Some(20.0)]).unwrap();
        assert!((avg - 15.0).abs() < 1e-12);
    }

    #[test]
    fn avg_nullable_bps_single_value() {
        assert!((avg_nullable_bps(&[Some(-4.5)]).unwrap() - (-4.5)).abs() < 1e-12);
    }

    #[test]
    fn validate_range_rejects_inverted_and_too_long() {
        let a = utc(2026, 1, 10, 0);
        let b = utc(2026, 1, 1, 0);
        assert!(validate_analytics_range(a, b).is_err());
        let from = utc(2025, 1, 1, 0);
        let to = utc(2026, 1, 3, 0); // > 366 days
        assert!(validate_analytics_range(from, to).is_err());
        assert!(validate_analytics_range(utc(2026, 1, 1, 0), utc(2026, 6, 1, 0)).is_ok());
    }
}
