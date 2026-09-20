"""
Resolve analysis columns and human-readable entity labels.

Grouping should use stable keys (customer_id / product_id).
UI surfaces (charts, metrics, opportunity labels, insight text)
should prefer names when available.
"""

from __future__ import annotations

from typing import Any


class ColumnResolver:

    def __init__(self, column_profiles):
        self.columns = column_profiles or []
        self._by_lower = {
            str(column.get("name", "")).lower(): column.get("name")
            for column in self.columns
            if column.get("name")
        }

    def find(
        self,
        role=None,
        keywords=None,
    ):

        keywords = keywords or []

        # Keyword match first
        if keywords:

            for column in self.columns:

                name = str(column.get("name", "")).lower()

                if any(
                    keyword in name
                    for keyword in keywords
                ):
                    return column["name"]

        # Fallback to role
        if role:

            for column in self.columns:

                if column.get("role") == role:
                    return column["name"]

        return None

    def exact(self, *names: str) -> str | None:
        """Return the first column whose name matches exactly (case-insensitive)."""

        for name in names:
            resolved = self._by_lower.get(str(name).lower())
            if resolved:
                return resolved
        return None

    def customer_key(self) -> str | None:
        """Stable customer identity column for grouping / joins."""

        return (
            self.exact(
                "customer_id",
                "client_id",
                "account_id",
            )
            or self.find(
                keywords=[
                    "customer_id",
                    "client_id",
                    "account_id",
                ]
            )
            or self.find(
                keywords=[
                    "customer",
                    "client",
                    "account",
                ]
            )
        )

    def customer_label(self) -> str | None:
        """Human-readable customer label for UI display."""

        return (
            self.exact(
                "customer_name",
                "client_name",
                "account_name",
            )
            or self.find(
                keywords=[
                    "customer_name",
                    "client_name",
                    "account_name",
                    "customer name",
                    "client name",
                    "account name",
                ]
            )
            or self.customer_key()
        )

    def customer(self):
        """Backward-compatible alias — prefer the stable key."""

        return self.customer_key()

    def product_key(self) -> str | None:
        """Stable product identity column for grouping / joins."""

        return (
            self.exact(
                "product_id",
                "item_id",
                "sku",
            )
            or self.find(
                keywords=[
                    "product_id",
                    "item_id",
                    "sku",
                ]
            )
            or self.find(
                keywords=[
                    "product",
                    "item",
                ]
            )
        )

    def product_label(self) -> str | None:
        """Human-readable product label for UI display."""

        return (
            self.exact(
                "product_name",
                "item_name",
                "sku_name",
            )
            or self.find(
                keywords=[
                    "product_name",
                    "item_name",
                    "sku_name",
                    "product name",
                    "item name",
                ]
            )
            or self.product_key()
        )

    def product(self):
        """Backward-compatible alias — prefer the stable key."""

        return self.product_key()

    def sales(self):
        return self.find(
            keywords=["sales", "revenue"]
        )

    def profit(self):
        return self.find(
            keywords=["profit"]
        )

    def date(self):
        return self.find(
            role="date"
        )

    def category(self):
        return self.find(
            keywords=["category"]
        )

    def region(self):
        return self.find(
            keywords=["region", "state"]
        )

    def player_key(self) -> str | None:
        return (
            self.exact(
                "player_id",
                "gsis_id",
            )
            or self.find(
                keywords=[
                    "player_id",
                    "gsis_id",
                ]
            )
            or self.find(
                keywords=["player"]
            )
        )

    def player_label(self) -> str | None:
        return (
            self.exact(
                "player_name",
                "name",
                "display_name",
            )
            or self.find(
                keywords=[
                    "player_name",
                    "display_name",
                ]
            )
            or self.player_key()
        )

    def team_key(self) -> str | None:
        return (
            self.exact(
                "team_id",
                "team",
                "recent_team",
            )
            or self.find(
                keywords=[
                    "team_id",
                    "recent_team",
                ]
            )
            or self.find(
                keywords=["team"]
            )
        )

    def season(self) -> str | None:
        return (
            self.exact("season")
            or self.find(keywords=["season"])
        )

    def week(self) -> str | None:
        return (
            self.exact("week")
            or self.find(keywords=["week"])
        )

    def fantasy_points(self) -> str | None:
        return (
            self.exact(
                "fantasy_points",
                "fantasy_points_ppr",
                "fpts",
            )
            or self.find(
                keywords=[
                    "fantasy_points",
                    "fpts",
                    "ppr",
                ]
            )
        )

    def signal_type(self) -> str | None:
        return (
            self.exact("signal_type")
            or self.find(
                keywords=["signal_type"]
            )
        )

    def signal_strength(self) -> str | None:
        return (
            self.exact("signal_strength")
            or self.find(
                keywords=["signal_strength"]
            )
        )

    def signal_confidence(self) -> str | None:
        return (
            self.exact("confidence")
            or self.find(
                keywords=["confidence"]
            )
        )


def build_entity_label_map(
    source_df: Any,
    key_column: str | None,
    label_column: str | None,
) -> dict[Any, str]:
    """
    Build key → display-name map from a source dataframe.

    Empty when the label column is missing or identical to the key.
    """

    if source_df is None or not key_column:
        return {}

    if key_column not in getattr(source_df, "columns", []):
        return {}

    if (
        not label_column
        or label_column == key_column
        or label_column not in source_df.columns
    ):
        return {}

    mapping: dict[Any, str] = {}
    pairs = source_df[[key_column, label_column]].dropna(subset=[key_column])

    for key, label in pairs.itertuples(index=False):
        if key in mapping:
            continue

        if label is None:
            continue

        text = str(label).strip()
        if not text or text.lower() == "nan":
            continue

        mapping[key] = text
        mapping[str(key)] = text

    return mapping


def format_entity_label(value: Any, label_map: dict[Any, str] | None) -> str:
    """Resolve a single entity value to its display label."""

    if value is None:
        return ""

    if not label_map:
        return str(value)

    if value in label_map:
        return label_map[value]

    text = str(value)
    return label_map.get(text, text)


def apply_entity_labels(
    frame: Any,
    *,
    key_column: str | None,
    label_map: dict[Any, str] | None,
    columns: list[str] | None = None,
) -> Any:
    """
    Return a copy of ``frame`` with key values replaced by display labels.

    Used for chart axes, metric cards, opportunity labels, and insight text.
    """

    if frame is None or not key_column or not label_map:
        return frame

    if key_column not in getattr(frame, "columns", []):
        # Still allow remapping alternate columns (e.g. product_a).
        target_columns = [
            column
            for column in (columns or [])
            if column in getattr(frame, "columns", [])
        ]
        if not target_columns:
            return frame
    else:
        target_columns = columns or [key_column]
        target_columns = [
            column
            for column in target_columns
            if column in frame.columns
        ]

    if not target_columns:
        return frame

    out = frame.copy()
    for column in target_columns:
        out[column] = out[column].map(
            lambda value: format_entity_label(value, label_map)
        )
    return out


def labeled_entity_pair(
    left: Any,
    right: Any,
    *,
    left_map: dict[Any, str] | None = None,
    right_map: dict[Any, str] | None = None,
    sep: str = " → ",
) -> str:
    """Format a pair of entities for charts / opportunity labels."""

    return (
        f"{format_entity_label(left, left_map)}"
        f"{sep}"
        f"{format_entity_label(right, right_map)}"
    )
