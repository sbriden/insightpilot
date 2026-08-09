from dataclasses import dataclass


@dataclass
class RecommendationRule:

    id: str

    condition: callable

    message: callable