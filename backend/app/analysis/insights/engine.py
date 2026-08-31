from ..models import Insight

from .normalize import (
    DEFAULT_RECOMMENDED_ACTIONS,
    normalize_priority,
)


class InsightEngine:

    def __init__(self, rules):
        self.rules = rules

    def evaluate(self, facts):

        insights = []

        for rule in self.rules:

            if rule.condition(facts):

                priority = normalize_priority(
                    rule.severity
                )

                why_it_matters = (
                    rule.message(facts)
                )

                insights.append(
                    Insight(
                        severity=priority,

                        priority=priority,

                        title=rule.title,

                        message=why_it_matters,

                        category=rule.category,

                        what_happened=rule.title,

                        why_it_matters=why_it_matters,

                        recommended_action=(
                            rule.recommended_action
                            or DEFAULT_RECOMMENDED_ACTIONS[
                                priority
                            ]
                        ),
                    )
                )

        return insights