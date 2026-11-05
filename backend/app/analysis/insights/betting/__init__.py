"""Sports Betting analysis — NFL market vs model workspace."""

from __future__ import annotations

from app.analysis.insights.betting.slate import (
    build_betting_results,
    build_betting_slate,
    find_betting_event_by_matchup,
    get_betting_event,
    list_betting_weeks,
)
from app.analysis.insights.betting.portfolio import (
    analyze_betting_portfolio,
    create_position_from_market,
    generate_betting_portfolio,
)
from app.analysis.insights.betting.daily_slate import (
    generate_daily_betting_slate,
    generate_single_parlay,
    list_daily_sport_availability,
)
from app.analysis.insights.betting.guided_slate import (
    back_guided_step,
    confirm_guided_slate,
    replace_guided_pick,
    review_guided_slate,
    select_guided_pick,
    start_guided_slate,
)
from app.analysis.insights.betting.power_rankings import (
    backtest_power_rankings_week,
    build_cfb_power_rankings,
    build_nfl_power_rankings,
    build_power_rankings,
    project_margin_from_power_rankings,
)

__all__ = [
    "analyze_betting_portfolio",
    "back_guided_step",
    "backtest_power_rankings_week",
    "build_betting_results",
    "build_betting_slate",
    "build_cfb_power_rankings",
    "build_nfl_power_rankings",
    "build_power_rankings",
    "confirm_guided_slate",
    "create_position_from_market",
    "find_betting_event_by_matchup",
    "generate_betting_portfolio",
    "generate_daily_betting_slate",
    "generate_single_parlay",
    "get_betting_event",
    "list_betting_weeks",
    "list_daily_sport_availability",
    "project_margin_from_power_rankings",
    "replace_guided_pick",
    "review_guided_slate",
    "select_guided_pick",
    "start_guided_slate",
]
