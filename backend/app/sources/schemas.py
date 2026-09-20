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