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


def build_insight_explanation_prompt(insight_facts: dict) -> str:
    """
    Build a per-Insight AI contract prompt from precomputed facts.

    ``insight_facts`` must come from ``build_ai_insight_fact_pack`` —
    structured insight, evidence, dataset context, and data-quality
    limitations only. Never raw dataset rows.
    """

    return f"""
You are a senior analytics consultant interpreting one deterministic Insight.

ALLOWED INPUTS (and only these):
- structured_insight
- evidence
- dataset_context
- data_quality_limitations
- evidence_supported_drivers
- constraints

You must NOT receive or use the raw dataset, dataframe rows, CSV contents,
or any records outside the compact evidence entities above.

ANTI-HALLUCINATION RULES (mandatory):
- Do NOT invent numbers, counts, aggregations, distributions, comparisons,
  trends, anomalies, statistical results, or confidence scores.
- Do NOT invent trends that are not in the provided facts.
- Do NOT claim causation without evidence.
- Do NOT introduce unsupported customer/product facts.
- Do NOT alter calculated values from structured_insight or evidence.
- Do NOT manufacture business context that is not implied by the facts.

If evidence does not establish a cause, use potential language:
  "Potential drivers include..."
Never write:
  "This happened because..."

When drivers are unsupported, say evidence is insufficient — do not speculate
beyond evidence_supported_drivers / evidence.

Fact pack:
{insight_facts}

Return JSON only using the AI Insight Contract:

{{
  "summary": "AI interpretation of what the finding means (not a restatement of raw numbers)",
  "why_it_matters": "potential business significance",
  "potential_drivers": [
    "evidence-supported potential factor 1"
  ],
  "recommended_action": "reasonable next action or investigation",
  "caveats": [
    "data-quality or confidence limitation from the fact pack only"
  ],
  "layer": "interpretation",
  "source": "ai"
}}

Rules:
- summary is interpretation, separate from the deterministic finding.
- Refer only to provided metric values; never invent or change them.
- potential_drivers must be empty or drawn only from evidence-supported signals.
- Phrase drivers as potential factors, never established causes.
- recommended_action should be a practical investigation or business follow-up.
- caveats should reflect provided data-quality / confidence limitations only.
"""


def build_insight_executive_brief_prompt(fact_pack: dict) -> str:
    """
    Build a concise leadership brief prompt from ranked Insights.

    ``fact_pack`` must come from ``build_executive_brief_fact_pack``.
    Target: something a leader can read in 30–60 seconds.
    """

    return f"""
You are preparing a concise executive brief for business leadership.

Objective: a 30–60 second read — not a lengthy report.
Answer only:
1) What matters most?
2) Why does it matter?
3) What should leadership investigate?

ALLOWED INPUTS only:
- product_context
- what_matters_most (top ranked Insights with facts + interpretations)
- cross_insight_signals
- data_quality_limitations
- constraints

Do NOT invent numbers, trends, causes, or unsupported entity facts.
Do NOT alter calculated values from the fact pack.
Do NOT write a long narrative memo.

Fact pack:
{fact_pack}

Return JSON only:

{{
  "what_matters_most": [
    {{
      "rank": 1,
      "insight_id": "id from input",
      "title": "title from input",
      "fact": "exact fact text from input"
    }}
  ],
  "why_it_matters": "2-4 short sentences synthesizing why these insights deserve attention together",
  "leadership_investigate": [
    "cross-insight investigation item 1"
  ],
  "layer": "executive_brief",
  "source": "ai"
}}

Rules:
- what_matters_most must copy facts/titles from the input — do not rewrite numbers.
- Keep why_it_matters under ~80 words.
- leadership_investigate: 2-5 items that cut across insights when possible.
- Prefer potential language over causation.
- Omit rather than invent.
"""
