from pydantic import BaseModel, Field


class NflversePreviewRequest(BaseModel):
    dataset_id: str
    seasons: list[int] = Field(default_factory=list)


class NflverseAnalyzeRequest(BaseModel):
    dataset_id: str
    seasons: list[int] = Field(default_factory=list)
    mappings: list = Field(default_factory=list)
    product_ids: list[str] = Field(default_factory=list)


class NflverseRefreshRequest(BaseModel):
    """
    Ingest / refresh standardized fantasy tables.

    mode (preferred):
      - historical: one-time multi-season bootstrap
      - incremental: current-season weekly update
      - reprocess: rebuild derived analytics/intelligence only

    scope (legacy alias):
      - historical → historical
      - current → incremental
      - seasons → explicit seasons list
    """

    mode: str | None = None
    scope: str = "current"
    seasons: list[int] = Field(default_factory=list)
    layers: list[str] = Field(default_factory=list)
    dataset_ids: list[str] = Field(default_factory=list)
    persist: bool = True
    # Default true: Render/proxy HTTP timeouts kill long sync refreshes.
    background: bool = True


class SportsdataversePreviewRequest(BaseModel):
    dataset_id: str
    seasons: list[int] = Field(default_factory=list)


class SportsdataverseRefreshRequest(BaseModel):
    """
    Ingest / refresh college_football tables from sportsdataverse.

    mode:
      - historical: multi-season bootstrap (dims + facts)
      - incremental: current-season update
      - reprocess: rebuild facts
    """

    mode: str | None = None
    scope: str = "current"
    seasons: list[int] = Field(default_factory=list)
    layers: list[str] = Field(default_factory=list)
    dataset_ids: list[str] = Field(default_factory=list)
    persist: bool = True
    background: bool = True


class ScoresandoddsRefreshRequest(BaseModel):
    """
    Refresh odds from ScoresAndOdds / Action Network.

    ``league``:
      - ``ncaaf`` → college_football.fact_game_market
      - ``nfl`` → fantasy_football.fact_game_market
      - ``nba`` / ``nhl`` / ``mlb`` / ``ncaab`` → sports_odds.fact_game_market

    Week-based leagues (ncaaf/nfl): empty ``weeks`` pulls the current
    week. Slate leagues ignore ``weeks`` and use the current board
    (optional ``dates`` as YYYYMMDD / YYYY-MM-DD).
    """

    league: str = "ncaaf"
    season: int | None = None
    weeks: list[int] = Field(default_factory=list)
    dates: list[str] = Field(default_factory=list)
    persist: bool = True
    background: bool = True


class DfsSalaryUploadResponse(BaseModel):
    site: str
    contest_type: str
    season: int
    week: int
    filename: str | None = None
    rows_parsed: int
    matched: int
    unmatched: int
    persisted: int
    unmatched_samples: list[dict] = Field(default_factory=list)
    matched_samples: list[dict] = Field(default_factory=list)