"""Kelly Criterion for optimal position sizing in prediction markets."""


def kelly_criterion(win_prob, odds):
    """Calculate optimal fraction of bankroll to bet.

    Formula: f* = (b*p - q) / b
    Where:
      b = decimal odds (net payout per $1 wagered)
      p = probability of winning
      q = 1 - p

    For binary markets: odds = (1/price) - 1
    Example: price=0.40 -> odds=1.5 (win $1.50 net per $1 risked)

    Returns:
      f* (Kelly fraction). Negative means don't bet.
    """
    if odds <= 0 or win_prob <= 0 or win_prob >= 1:
        return 0.0

    q = 1.0 - win_prob
    return (odds * win_prob - q) / odds


def position_size(
    bankroll,
    win_prob,
    odds,
    kelly_fraction=0.25,
    max_kelly=0.50,
    max_position_usd=50.0,
):
    """Calculate actual dollar position size with safety caps.

    Three layers of protection:
    1. Fractional Kelly (default 25%) reduces variance
    2. Max Kelly cap prevents over-betting
    3. Absolute dollar cap provides hard limit
    """
    raw = kelly_criterion(win_prob, odds)

    if raw <= 0:
        return 0.0

    adjusted = raw * kelly_fraction
    capped = min(adjusted, max_kelly)
    dollar_size = bankroll * capped

    return min(dollar_size, max_position_usd)
