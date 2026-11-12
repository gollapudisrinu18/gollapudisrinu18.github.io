"""Burn-rate math shared by the simulator and the tests.

Thresholds match prometheus/rules/slo-rules.yaml.
"""
SLO_TARGET = 0.99            # 99% of checkouts within 300 ms
ERROR_BUDGET = 1 - SLO_TARGET
WINDOW_DAYS = 30

ALERTS = {
    # name: (long window min, short window min, burn factor, for minutes, severity)
    "CheckoutLatencyBudgetFastBurn": (60, 5, 14.4, 2, "page"),
    "CheckoutLatencyBudgetSlowBurn": (360, 30, 6.0, 15, "ticket"),
}


def bad_ratio(series, end, window):
    """series: list of (total, bad) per minute. Ratio over the last `window` minutes ending at `end` (inclusive)."""
    start = max(0, end - window + 1)
    total = sum(t for t, _ in series[start:end + 1])
    bad = sum(b for _, b in series[start:end + 1])
    return bad / total if total else 0.0


def burn_rate(ratio):
    return ratio / ERROR_BUDGET


def condition(series, minute, long_w, short_w, factor):
    threshold = factor * ERROR_BUDGET
    return (bad_ratio(series, minute, long_w) > threshold
            and bad_ratio(series, minute, short_w) > threshold)


def budget_consumed(bad_requests, requests_per_minute):
    """Share of the 30-day error budget used by `bad_requests`."""
    total_30d = requests_per_minute * 60 * 24 * WINDOW_DAYS
    return bad_requests / (total_30d * ERROR_BUDGET)
