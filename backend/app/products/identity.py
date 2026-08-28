"""
Deterministic dataset identity for product versioning.

MVP identity is derived only from information already
available during analysis:

  - analytical product definition id
  - dataset classification type
  - product grain
  - required semantic fields present after mapping
"""

from __future__ import annotations

import hashlib


def build_dataset_identity(
    *,
    definition_id: str,
    classification_type: str,
    grain: str,
    required_fields: list[str],
    columns: list[str],
) -> str:
    """
    Build a stable identity for a product lineage.

    Two uploads are treated as versions of the same
    product when they share this identity.
    """

    column_set = {
        str(column).strip()
        for column in columns
        if str(column).strip()
    }

    present_required = sorted(
        field
        for field in (required_fields or [])
        if field in column_set
    )

    payload = "|".join(
        [
            str(definition_id).strip(),
            str(classification_type or "").strip().lower(),
            str(grain or "").strip().lower(),
            ",".join(present_required),
        ]
    )

    return hashlib.sha256(
        payload.encode("utf-8")
    ).hexdigest()[:32]


def build_product_instance_id(
    definition_id: str,
    dataset_identity: str,
    version: int,
) -> str:
    """
    Unique id for one version of a product lineage.
    """

    return (
        f"{definition_id}__"
        f"{dataset_identity}__"
        f"v{version}"
    )
