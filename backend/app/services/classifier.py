from collections import Counter


DATASET_PATTERNS = {
    "Sales & Revenue": [
        "sales",
        "revenue",
        "profit",
        "invoice",
        "customer",
        "product",
        "price",
        "amount",
        "discount",
        "order",
    ],
    "Healthcare Claims": [
        "claim",
        "member",
        "patient",
        "diagnosis",
        "provider",
        "procedure",
        "icd",
        "cpt",
    ],
    "Human Resources": [
        "employee",
        "salary",
        "department",
        "manager",
        "hire",
        "termination",
        "title",
    ],
    "Marketing": [
        "campaign",
        "click",
        "impression",
        "lead",
        "conversion",
        "channel",
    ],
    "Inventory": [
        "sku",
        "inventory",
        "stock",
        "warehouse",
        "supplier",
        "quantity",
    ],
}


def classify_dataset(columns: list[str]) -> dict:
    scores = Counter()

    lower_columns = [c.lower() for c in columns]

    for dataset_type, keywords in DATASET_PATTERNS.items():
        for keyword in keywords:
            for column in lower_columns:
                if keyword in column:
                    scores[dataset_type] += 1

    if not scores:
        return {
            "type": "General",
            "confidence": 0,
            "matched_fields": [],
        }

    dataset_type = scores.most_common(1)[0][0]

    matched = []

    for column in columns:
        for keyword in DATASET_PATTERNS[dataset_type]:
            if keyword in column.lower():
                matched.append(column)
                break

    confidence = min(
        100,
        int((scores[dataset_type] / len(DATASET_PATTERNS[dataset_type])) * 100),
    )

    return {
        "type": dataset_type,
        "confidence": confidence,
        "matched_fields": matched,
    }