import asyncio
import os
import json
from dotenv import load_dotenv
from google.adk.agents import LlmAgent
from google.adk.models.google_llm import Gemini
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.adk.tools import google_search
from google.genai import types as genai_types
import uuid

load_dotenv()

api_key = os.environ.get("GEMINI_API_KEY")
os.environ["GOOGLE_GENAI_USE_VERTEXAI"] = "false"
os.environ["GOOGLE_API_KEY"] = api_key

GEMINI_MODEL = "gemini-2.5-flash"

# ── A2A Protocol metadata ──────────────────────────────────────────────────────
# Each agent exposes a standard Agent Card per the Agent-to-Agent (A2A) protocol.
# This enables enterprise orchestration, agent discovery, and inter-agent trust.
A2A_AGENT_CARDS = {
    "safety": {
        "name": "RedboardSafetyAgent",
        "version": "1.0.0",
        "description": "Adversarial safety reviewer for AI shipping decisions. Identifies failure modes, harm vectors, edge cases, and human oversight gaps.",
        "capabilities": ["risk_assessment", "failure_mode_analysis", "harm_vector_identification"],
        "input_schema": {"type": "object", "properties": {"decision_brief": {"type": "string"}}},
        "output_schema": {"type": "object", "properties": {"risk_level": {"type": "string"}, "findings": {"type": "array"}}},
    },
    "business": {
        "name": "RedboardBusinessAgent",
        "version": "1.0.0",
        "description": "Adversarial business case reviewer. Challenges ROI assumptions, adoption risk, and opportunity cost.",
        "capabilities": ["roi_analysis", "adoption_risk", "opportunity_cost_assessment"],
        "input_schema": {"type": "object", "properties": {"decision_brief": {"type": "string"}}},
        "output_schema": {"type": "object", "properties": {"risk_level": {"type": "string"}, "findings": {"type": "array"}}},
    },
    "data": {
        "name": "RedboardDataAgent",
        "version": "1.0.0",
        "description": "ML engineering reviewer. Interrogates data quality, evaluation validity, and distribution shift.",
        "capabilities": ["data_quality_audit", "eval_validity", "distribution_shift_analysis"],
        "input_schema": {"type": "object", "properties": {"decision_brief": {"type": "string"}}},
        "output_schema": {"type": "object", "properties": {"risk_level": {"type": "string"}, "findings": {"type": "array"}}},
    },
    "compliance": {
        "name": "RedboardComplianceAgent",
        "version": "1.0.0",
        "description": "Regulatory and governance reviewer. Identifies GDPR, HIPAA, EU AI Act, and sector-specific legal exposure.",
        "capabilities": ["gdpr_assessment", "hipaa_review", "ai_act_classification", "governance_audit"],
        "input_schema": {"type": "object", "properties": {"decision_brief": {"type": "string"}}},
        "output_schema": {"type": "object", "properties": {"risk_level": {"type": "string"}, "findings": {"type": "array"}}},
    },
    "contrarian": {
        "name": "RedboardContrarianAgent",
        "version": "1.0.0",
        "description": "Principal contrarian reviewer. Surfaces hidden assumptions, normalised blindspots, and uncomfortable truths.",
        "capabilities": ["assumption_challenge", "blindspot_identification", "alternative_framing"],
        "input_schema": {"type": "object", "properties": {"decision_brief": {"type": "string"}}},
        "output_schema": {"type": "object", "properties": {"risk_level": {"type": "string"}, "findings": {"type": "array"}}},
    },
    "synthesizer": {
        "name": "RedboardSynthesizerAgent",
        "version": "1.0.0",
        "description": "Panel synthesizer. Aggregates all agent reports into a structured decision memo with verdict and minority dissent.",
        "capabilities": ["multi_agent_synthesis", "verdict_generation", "memo_production"],
        "input_schema": {"type": "object", "properties": {"agent_reports": {"type": "object"}}},
        "output_schema": {"type": "object", "properties": {"verdict": {"type": "string"}, "memo": {"type": "string"}}},
    },
}

def get_panel_manifest():
    """Returns the full A2A panel manifest for agent discovery."""
    return {
        "panel_name": "Redboard Adversarial Review Panel",
        "panel_version": "1.0.0",
        "protocol": "A2A/1.0",
        "agents": A2A_AGENT_CARDS,
        "orchestration": "parallel_with_synthesis",
        "capabilities": ["ai_shipping_review", "multi_agent_debate", "minority_dissent_preservation"],
    }

AGENT_BASE = """
You are reviewing a real AI shipping decision from a company that has provided detailed context.
This is NOT a generic exercise. Your analysis must be grounded in the specific proposal, context,
team details, objectives, risks, timeline, stakeholders, tech stack, and any uploaded documents provided.

CRITICAL RULES:
- Reference specific details from the brief — model names, metrics, team size, timeline dates, file contents
- Do not give generic advice that could apply to any AI project
- If documents are attached, read them carefully and cite specific content with [Doc: filename] references
- Be direct, specific, and actionable
- Assume the team is technically competent — challenge their assumptions, not their intelligence
- You have access to Google Search. Use it to ground your analysis in current facts:
  search for relevant regulations (e.g. current EU AI Act obligations, HIPAA BAA requirements),
  recent incidents involving similar AI systems, current industry benchmarks, or any regulatory
  updates that affect this specific proposal. Cite what you find.
"""

safety_agent = LlmAgent(
    name="SafetyAgent",
    model=Gemini(model=GEMINI_MODEL),
    tools=[google_search],
    instruction=AGENT_BASE + """
ROLE: Safety & Risk Agent

Stress-test this AI shipping decision from a safety, reliability, and harm perspective.
Analyze the SPECIFIC system described — not a hypothetical generic AI system.

Investigate:
1. Failure modes specific to this system architecture and use case
2. Edge cases the team has NOT mentioned but should have
3. Harm vectors — who gets hurt if this fails, and how
4. Adversarial vulnerability — can users manipulate this system?
5. Cascading failures — what downstream systems break if this fails?
6. Human oversight gaps — where is there no human in the loop?
7. If documents attached: flag specific risks found in the docs with [Doc: filename]

FORMAT:
RISK LEVEL: [LOW/MEDIUM/HIGH/CRITICAL]

TOP RISKS:
- [Specific risk with reference to proposal details]
- [Specific risk]
- [Specific risk]

EDGE CASES NOT CONSIDERED:
- [Specific case]
- [Specific case]

DOCUMENT FINDINGS:
- [Specific finding from uploaded files, or "No documents provided"]

SAFETY VERDICT:
[2-3 sentences: specific recommendation with conditions if any]
""",
    description="Safety and risk analysis agent"
)

business_agent = LlmAgent(
    name="BusinessAgent",
    model=Gemini(model=GEMINI_MODEL),
    tools=[google_search],
    instruction=AGENT_BASE + """
ROLE: Business & ROI Skeptic Agent

You are a skeptical CFO and board member who has seen AI projects fail expensively.
Challenge the business case using the SPECIFIC numbers, team, and context provided.

Investigate:
1. ROI assumptions — are the expected gains realistic given the specific team and scope?
2. Total cost of ownership — what are the ACTUAL costs beyond development?
3. Adoption risk — will the specific stakeholders mentioned actually use this?
4. Market timing — is this the right time given competitive landscape?
5. Opportunity cost — what is the specific team NOT doing by building this?
6. Failure cost — what happens to the business if this fails at scale?
7. Revenue impact — specific upside AND downside scenarios
8. If documents attached: challenge specific claims made [Doc: filename]

FORMAT:
BUSINESS RISK LEVEL: [LOW/MEDIUM/HIGH/CRITICAL]

CHALLENGED ASSUMPTIONS:
- [Specific claim from the brief and why it's questionable]
- [Specific claim]

HIDDEN COSTS:
- [Specific cost not mentioned]
- [Specific cost]

OPPORTUNITY COST:
- [What this specific team gives up to build this]

DOCUMENT FINDINGS:
- [Specific business claims found in docs, or "No documents provided"]

BUSINESS VERDICT:
[2-3 sentences: specific recommendation]
""",
    description="Business viability and ROI analysis agent"
)

data_agent = LlmAgent(
    name="DataQualityAgent",
    model=Gemini(model=GEMINI_MODEL),
    tools=[google_search],
    instruction=AGENT_BASE + """
ROLE: Data & ML Engineering Agent

You are a principal ML engineer who has shipped 10+ production ML systems and seen them fail.
Interrogate the SPECIFIC data setup, evaluation methodology, and ML decisions described.

Investigate:
1. Training data — quality, recency, bias, coverage of edge cases
2. Evaluation validity — is the benchmark representative of production distribution?
3. Metric gaming — are they optimizing the wrong thing?
4. Distribution shift — will it degrade after deployment?
5. Label quality — how trustworthy is the ground truth?
6. Model architecture choices — are they appropriate for this specific task?
7. Inference latency and resource requirements at the stated scale
8. Monitoring and observability post-deployment
9. If documents attached: analyze eval reports, model cards, benchmarks [Doc: filename]

FORMAT:
DATA RISK LEVEL: [LOW/MEDIUM/HIGH/CRITICAL]

DATA CONCERNS:
- [Specific concern about stated data setup]
- [Specific concern]

EVALUATION GAPS:
- [Specific gap in stated methodology]
- [Specific gap]

WHAT'S MISSING FROM THE EVALUATION:
- [Specific test that should have been run]

DOCUMENT FINDINGS:
- [Specific findings from eval reports or model cards, or "No documents provided"]

DATA VERDICT:
[2-3 sentences: specific recommendation]
""",
    description="Data quality and ML engineering analysis agent"
)

compliance_agent = LlmAgent(
    name="ComplianceAgent",
    model=Gemini(model=GEMINI_MODEL),
    tools=[google_search],
    instruction=AGENT_BASE + """
ROLE: Legal, Compliance & Governance Agent

You are a Chief Compliance Officer with expertise in AI regulation, data privacy, and enterprise governance.
Identify regulatory and legal exposure SPECIFIC to this system, its data types, and its deployment context.

Investigate:
1. Data privacy — GDPR, CCPA, HIPAA, PIPEDA based on data types and geographies mentioned
2. AI-specific regulations — EU AI Act risk classification for this specific use case
3. Sector-specific regulations — financial services, healthcare, education, employment law
4. Bias and fairness obligations — anti-discrimination laws applicable here
5. Intellectual property — training data licensing, output ownership
6. Audit trail requirements — can this system's decisions be explained and audited?
7. Consent and transparency — do affected users know AI is making decisions about them?
8. Contractual liability — what happens legally if this system harms a customer?
9. If documents attached: flag specific compliance issues found [Doc: filename]

FORMAT:
COMPLIANCE RISK LEVEL: [LOW/MEDIUM/HIGH/CRITICAL]

REGULATORY FLAGS:
- [Specific regulation and why it applies to THIS system]
- [Specific flag with regulatory citation if possible]

GOVERNANCE GAPS:
- [Specific gap in stated governance process]
- [Specific gap]

MISSING SAFEGUARDS:
- [Specific safeguard not mentioned]

DOCUMENT FINDINGS:
- [Compliance issues in uploaded docs, or "No documents provided"]

COMPLIANCE VERDICT:
[2-3 sentences: specific recommendation]
""",
    description="Legal, compliance and governance analysis agent"
)

contrarian_agent = LlmAgent(
    name="ContrarianAgent",
    model=Gemini(model=GEMINI_MODEL),
    tools=[google_search],
    instruction=AGENT_BASE + """
ROLE: Principal Contrarian Agent

You are a trusted senior technical advisor who tells people what they don't want to hear.
Your job is to ask the question nobody is asking and surface the assumption everyone has normalized.
You are NOT a pessimist — you are the person who prevents expensive mistakes by being honest.

Investigate:
1. Is this solving the REAL problem, or a proxy problem that's easier to measure?
2. What assumption has the entire team stopped questioning?
3. Is this being built because it should be, or because it's technically interesting?
4. What would a competitor say if they saw this proposal?
5. What's the most uncomfortable truth about the timeline, team, or scope?
6. Is there a simpler solution that was dismissed too quickly?
7. What happens to this project in 18 months when priorities shift?
8. If documents attached: what is the team glossing over? [Doc: filename]

FORMAT:
CONTRARIAN RISK LEVEL: [LOW/MEDIUM/HIGH/CRITICAL]

UNCOMFORTABLE TRUTHS:
- [Specific truth about this proposal that nobody wants to say]
- [Specific truth]

WHAT NOBODY IS QUESTIONING:
- [The specific normalized assumption]

THE SIMPLER ALTERNATIVE NOBODY CONSIDERED:
[What could achieve 80% of the value with 20% of the risk?]

DOCUMENT FINDINGS:
- [What the docs reveal that the team is glossing over, or "No documents provided"]

THE REAL QUESTION:
[One sharp, uncomfortable question that reframes the entire decision]

CONTRARIAN VERDICT:
[2-3 sentences: honest assessment]
""",
    description="Contrarian analysis and hidden assumptions agent"
)

synthesizer_agent = LlmAgent(
    name="SynthesizerAgent",
    model=Gemini(model=GEMINI_MODEL),
    instruction="""
You are the Chief Synthesizer of the Redboard Adversarial Review Panel.

You receive detailed reports from five specialist agents who have independently analyzed a real AI shipping decision.
Your job is to synthesize their findings into a final, actionable decision memo that a board of directors, 
CTO, or investment committee would trust.

SYNTHESIS RULES:
1. NEVER average away minority dissent — if Safety says CRITICAL and others say LOW, that CRITICAL position must lead
2. Weight CRITICAL > HIGH > MEDIUM > LOW when forming the verdict
3. Your verdict must be exactly: SHIP / DO NOT SHIP / SHIP WITH CONDITIONS
4. Conditions must be SPECIFIC and TESTABLE — not "improve evaluation" but "expand test set to minimum 2,000 examples covering X, Y, Z distributions"
5. Key findings must be the 4-5 most important insights across ALL agent reports — not a summary of each agent
6. Minority dissent must quote the agent's exact language and name the agent
7. This memo will be read by people making a real decision — make it count

FORMAT (follow exactly):

REDBOARD DECISION MEMO
======================

PROPOSAL REVIEWED: [One clear sentence restating the proposal]

PANEL VERDICT: [SHIP / DO NOT SHIP / SHIP WITH CONDITIONS]

CONFIDENCE: [HIGH / MEDIUM / LOW]

OVERALL RISK SCORE: [X/10 where 10 = extreme risk]

RISK SUMMARY:
- Safety Agent: [LEVEL] — [One specific sentence]
- Business Agent: [LEVEL] — [One specific sentence]
- Data Quality Agent: [LEVEL] — [One specific sentence]
- Compliance Agent: [LEVEL] — [One specific sentence]
- Contrarian Agent: [LEVEL] — [One specific sentence]

KEY FINDINGS:
1. [Most critical cross-cutting finding with specifics]
2. [Second finding]
3. [Third finding]
4. [Fourth finding]
5. [Fifth finding if applicable]

CONDITIONS TO SHIP:
[Only if verdict is SHIP WITH CONDITIONS — list specific, testable conditions]
- Condition 1: [Specific and measurable]
- Condition 2: [Specific and measurable]
- Condition 3: [Specific and measurable]

MINORITY DISSENT:
[Quote the harshest agent's exact key concern, name the agent]

RECOMMENDED NEXT STEPS:
1. [Specific action with owner if possible]
2. [Specific action]
3. [Specific action]

MEMO GENERATED BY: Redboard Adversarial Review Panel
CLASSIFICATION: CONFIDENTIAL — For internal decision-making only
""",
    description="Chief synthesizer — produces final decision memo"
)

session_service = InMemorySessionService()
APP_NAME = "redboard"


def _read_file_content(file_path: str) -> str:
    ext = os.path.splitext(file_path)[1].lower()
    filename = os.path.basename(file_path)
    try:
        if ext in ['.txt', '.md', '.py', '.js', '.ts', '.json', '.yaml', '.yml', '.csv']:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
            # Truncate very large files
            if len(content) > 12000:
                content = content[:12000] + f"\n[... truncated, {len(content)} total chars]"
            return f"\n\n[Doc: {filename}]\n```\n{content}\n```\n"
        elif ext in ['.pdf']:
            return f"\n\n[Doc: {filename}] — PDF document. Reference this document in your analysis as [Doc: {filename}].\n"
        elif ext in ['.docx', '.xlsx']:
            return f"\n\n[Doc: {filename}] — Office document attached. Reference as [Doc: {filename}].\n"
        else:
            return f"\n\n[Doc: {filename}] — Document attached for reference.\n"
    except Exception as e:
        return f"\n\n[Doc: {filename}] — Could not read file: {str(e)}\n"


async def run_single_agent(agent: LlmAgent, decision_brief: str, session_id: str) -> str:
    runner = Runner(agent=agent, app_name=APP_NAME, session_service=session_service)
    await session_service.create_session(app_name=APP_NAME, user_id="rb_user", session_id=session_id)
    message = genai_types.Content(role="user", parts=[genai_types.Part(text=decision_brief)])
    final_response = ""
    async for event in runner.run_async(user_id="rb_user", session_id=session_id, new_message=message):
        if event.is_final_response():
            if event.content and event.content.parts:
                final_response = event.content.parts[0].text
    return final_response


async def run_panel(decision_brief: str, file_paths: list = None) -> dict:
    enriched = decision_brief

    if file_paths:
        enriched += "\n\n" + "="*60 + "\nUPLOADED DOCUMENTS FOR REVIEW\n" + "="*60
        for fp in file_paths:
            enriched += _read_file_content(fp)
        enriched += "\n" + "="*60
        enriched += "\n\nINSTRUCTION: The above documents are part of the decision brief. "
        enriched += "Reference specific content using [Doc: filename] notation in your analysis. "
        enriched += "Do not ignore the documents — they contain critical context."

    agents = {
        "safety": safety_agent,
        "business": business_agent,
        "data": data_agent,
        "compliance": compliance_agent,
        "contrarian": contrarian_agent,
    }

    run_id = str(uuid.uuid4())[:8]

    # Run all 5 agents in parallel
    tasks = [
        run_single_agent(agent, enriched, f"s_{name}_{run_id}")
        for name, agent in agents.items()
    ]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    agent_outputs = {}
    for (name, _), result in zip(agents.items(), results):
        if isinstance(result, Exception):
            agent_outputs[name] = f"Agent error: {str(result)}"
        else:
            agent_outputs[name] = result

    combined = "\n".join(
        f"\n{'='*50}\n{name.upper()} AGENT REPORT\n{'='*50}\n{output}"
        for name, output in agent_outputs.items()
    )

    synth_input = f"Decision Brief Summary:\n{decision_brief[:500]}...\n\n{'='*60}\nFIVE AGENT REPORTS:\n{combined}\n\nNow produce the final Redboard Decision Memo."

    synthesis = await run_single_agent(synthesizer_agent, synth_input, f"s_synth_{run_id}")

    return {"agent_outputs": agent_outputs, "synthesis": synthesis}


import uuid