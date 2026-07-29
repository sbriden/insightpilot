def build_executive_brief_prompt(context):

    return f"""
You are a senior analytics consultant preparing an executive briefing.

Review the following dataset assessment.

Dataset classification:
{context.classification}

Dataset metrics:
{context.metrics}

Detected insights:
{context.insights}

Recommended analyses:
{context.recommendations}

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
"""