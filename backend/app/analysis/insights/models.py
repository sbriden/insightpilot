from dataclasses import dataclass


@dataclass
class InsightRule:
    id: str
    severity: str
    title: str
    condition: callable
    message: callable