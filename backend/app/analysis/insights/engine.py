from ..models import Insight


class InsightEngine:

    def __init__(self, rules):
        self.rules = rules

    def evaluate(self, facts):

        insights = []

        for rule in self.rules:

            if rule.condition(facts):

                insights.append(
                    Insight(
                        severity=rule.severity,
                        title=rule.title,
                        message=rule.message(facts),
                    )
                )

        return insights