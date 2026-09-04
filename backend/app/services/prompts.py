"""
LLM prompt builders for narrative generation only.

Prompts must receive precomputed facts from AnalysisContext and
must instruct the model not to invent analytical results.
"""


def build_executive_brief_prompt(context):
    """
    Build an executive-brief prompt from structured facts only.

    ``context`` should expose ``to_prompt_context()`` (preferred)
    or the same fact keys. Raw dataframes must never be included.
    """

    if hasattr(context, "to_prompt_context"):
        facts = context.to_prompt_context()
    else:
        facts = context

    classification = facts.get("classification", {})
    metrics = facts.get("metrics", {})
    insights = facts.get("insights", [])
    recommendations = facts.get("recommendations", [])
    semantic_model = facts.get("semantic_model", {})
    capabilities = facts.get("capabilities", [])
    dataset_archetype = facts.get("dataset_archetype", {})
    constraints = facts.get("narrative_constraints", {})

    return f"""
You are a senior analytics consultant preparing an executive briefing.

You may ONLY narrate the precomputed facts below.
You must NOT invent numbers, counts, aggregations, distributions,
comparisons, trends, anomalies, statistical results, or confidence
scores. If a fact is missing, omit it — do not calculate it.

Narrative constraints:
{constraints}

Dataset classification:
{classification}

Dataset archetype (semantic):
{dataset_archetype}

Semantic model (structured facts):
{semantic_model}

Analytical capabilities (structured facts):
{capabilities}

Dataset metrics (precomputed):
{metrics}

Detected insights (precomputed):
{insights}

Recommended analyses:
{recommendations}

Create a concise executive brief.

Return JSON only using this structure:

{{
  "overview": "short executive summary",
  "key_findings": [
    "finding 1",
    "finding 2"
  ],
  "risks": [
    "risk 1"
  ],
  "opportunities": [
    {{
      "id": "identifier",
      "title": "opportunity title",
      "category": "category"
    }}
  ],
  "next_steps": [
    "next action"
  ]
}}

Write for business leaders.
Avoid technical jargon.
Use only the facts provided above.
"""
