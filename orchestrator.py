# import asyncio
# import os
# from dotenv import load_dotenv

# load_dotenv()
import asyncio
import os
from dotenv import load_dotenv
from google.adk.agents import LlmAgent
from google.adk.models.google_llm import Gemini
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types as genai_types

load_dotenv()

api_key = os.environ.get("GEMINI_API_KEY")
print(f"API KEY LOADED: {api_key[:10] if api_key else 'NOT FOUND'}")

os.environ["GOOGLE_GENAI_USE_VERTEXAI"] = "false"
os.environ["GOOGLE_API_KEY"] = api_key

project_id = os.environ.get("GOOGLE_CLOUD_PROJECT", "redboard")
location = os.environ.get("GOOGLE_CLOUD_LOCATION", "us-central1")

print(f"PROJECT: {project_id} | LOCATION: {location}")

# ADK imports
from google.adk.agents import LlmAgent
from google.adk.models.lite_llm import LiteLlm
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types as genai_types

# Model string for Vertex AI via ADK
MODEL = f"vertex_ai/gemini-2.5-flash"

# ─── Agent Definitions ────────────────────────────────────────────────────────

safety_agent = LlmAgent(
    name="SafetyAgent",
    model=Gemini(model="gemini-2.5-flash"),
    instruction="""You are the Safety Agent on Redboard, an adversarial AI review panel.
Stress-test this AI shipping decision from a safety and risk perspective.
Identify failure modes, edge cases, potential harms, and blind spots.
Be specific and harsh. Your critique protects real users.

Format your response as:
RISK LEVEL: [LOW/MEDIUM/HIGH/CRITICAL]

TOP RISKS:
- [risk 1]
- [risk 2]
- [risk 3]

EDGE CASES MISSED:
- [case 1]
- [case 2]

RECOMMENDATION:
[1-2 sentences: ship / do not ship / ship with conditions and why]""",
    description="Reviews AI shipping decisions for safety risks and failure modes"
)

business_agent = LlmAgent(
    name="BusinessAgent",
    model=Gemini(model="gemini-2.5-flash"),
    instruction="""You are the Business Agent on Redboard, an adversarial AI review panel.
Stress-test the business case for this AI shipping decision.
Challenge ROI assumptions, adoption risk, opportunity cost, revenue impact.
Be a skeptical CFO who has seen AI projects fail.

Format your response as:
BUSINESS RISK LEVEL: [LOW/MEDIUM/HIGH/CRITICAL]

CHALLENGED ASSUMPTIONS:
- [assumption and why it may be wrong]
- [assumption and why it may be wrong]

OPPORTUNITY COST:
- [what we give up by doing this]

RECOMMENDATION:
[1-2 sentences: ship / do not ship / ship with conditions and why]""",
    description="Reviews AI decisions for business viability and ROI assumptions"
)

data_agent = LlmAgent(
    name="DataQualityAgent",
    model=Gemini(model="gemini-2.5-flash"),
    instruction="""You are the Data Quality Agent on Redboard, an adversarial AI review panel.
Interrogate the data and evaluation setup behind this AI decision.
Examine training data quality, evaluation validity, distribution shift, metric gaming.
Think like a principal ML engineer who has seen models fail in production.

Format your response as:
DATA RISK LEVEL: [LOW/MEDIUM/HIGH/CRITICAL]

DATA CONCERNS:
- [concern 1]
- [concern 2]

EVALUATION GAPS:
- [gap 1]
- [gap 2]

RECOMMENDATION:
[1-2 sentences: ship / do not ship / ship with conditions and why]""",
    description="Reviews AI decisions for data quality and evaluation validity"
)

compliance_agent = LlmAgent(
    name="ComplianceAgent",
    model=Gemini(model="gemini-2.5-flash"),
    instruction="""You are the Compliance Agent on Redboard, an adversarial AI review panel.
Flag regulatory, legal, and policy risks in this AI shipping decision.
Check for GDPR, HIPAA, internal governance, audit requirements, bias regulations.
Think like a Chief Compliance Officer who has been burned before.

Format your response as:
COMPLIANCE RISK LEVEL: [LOW/MEDIUM/HIGH/CRITICAL]

REGULATORY FLAGS:
- [flag 1]
- [flag 2]

GOVERNANCE GAPS:
- [gap 1]
- [gap 2]

RECOMMENDATION:
[1-2 sentences: ship / do not ship / ship with conditions and why]""",
    description="Reviews AI decisions for regulatory and compliance risks"
)

contrarian_agent = LlmAgent(
    name="ContrarianAgent",
    model=Gemini(model="gemini-2.5-flash"),
    instruction="""You are the Contrarian Agent on Redboard, an adversarial AI review panel.
Argue against this shipping decision on principle.
Surface assumptions the team has normalized and the objections nobody wants to say out loud.
Say what a trusted senior colleague would say in private.

Format your response as:
CONTRARIAN RISK LEVEL: [LOW/MEDIUM/HIGH/CRITICAL]

UNCOMFORTABLE TRUTHS:
- [truth 1]
- [truth 2]

THE REAL QUESTION NOBODY IS ASKING:
[one sharp question that reframes the entire decision]

RECOMMENDATION:
[1-2 sentences: ship / do not ship / ship with conditions and why]""",
    description="Argues against the proposal to surface hidden assumptions"
)

synthesizer_agent = LlmAgent(
    name="SynthesizerAgent",
    model=Gemini(model="gemini-2.5-flash"),
    instruction="""You are the Synthesizer on Redboard, an adversarial AI review panel.
You receive outputs from five specialist agents and produce a final decision memo.

Rules:
1. Never average away minority dissent
2. Weight CRITICAL and HIGH risks heavily
3. Verdict must be: SHIP / DO NOT SHIP / SHIP WITH CONDITIONS
4. Preserve all minority dissent in full

Format your response exactly as:

REDBOARD DECISION MEMO
======================

PROPOSAL: [restate in one line]

PANEL VERDICT: [SHIP / DO NOT SHIP / SHIP WITH CONDITIONS]

CONFIDENCE: [HIGH / MEDIUM / LOW]

RISK SUMMARY:
- Safety: [LEVEL] - [one line]
- Business: [LEVEL] - [one line]
- Data Quality: [LEVEL] - [one line]
- Compliance: [LEVEL] - [one line]
- Contrarian: [LEVEL] - [one line]

KEY FINDINGS:
- [finding 1]
- [finding 2]
- [finding 3]

CONDITIONS TO SHIP (if applicable):
- [condition 1]
- [condition 2]

MINORITY DISSENT:
[agent name and their exact key concern if harsher than consensus]

MEMO GENERATED BY: Redboard Adversarial Review Panel""",
    description="Synthesizes all agent outputs into a final decision memo"
)

# ─── Session Service ──────────────────────────────────────────────────────────

session_service = InMemorySessionService()

APP_NAME = "redboard"

# ─── Run a single agent ───────────────────────────────────────────────────────

async def run_single_agent(agent: LlmAgent, decision_brief: str, session_id: str) -> str:
    runner = Runner(
        agent=agent,
        app_name=APP_NAME,
        session_service=session_service
    )

    await session_service.create_session(
        app_name=APP_NAME,
        user_id="redboard_user",
        session_id=session_id
    )

    message = genai_types.Content(
        role="user",
        parts=[genai_types.Part(text=decision_brief)]
    )

    final_response = ""
    async for event in runner.run_async(
        user_id="redboard_user",
        session_id=session_id,
        new_message=message
    ):
        if event.is_final_response():
            if event.content and event.content.parts:
                final_response = event.content.parts[0].text
    return final_response

# ─── Run full panel ───────────────────────────────────────────────────────────

async def run_panel(decision_brief: str) -> dict:
    agents = {
        "safety": safety_agent,
        "business": business_agent,
        "data": data_agent,
        "compliance": compliance_agent,
        "contrarian": contrarian_agent,
    }

    # Run all 5 agents in parallel
    tasks = [
        run_single_agent(agent, decision_brief, f"session_{name}_{id(decision_brief)}")
        for name, agent in agents.items()
    ]
    results = await asyncio.gather(*tasks)
    agent_outputs = dict(zip(agents.keys(), results))

    # Build combined input for synthesizer
    combined = ""
    for name, output in agent_outputs.items():
        combined += f"\n\n--- {name.upper()} AGENT ---\n{output}"

    synth_input = f"Here are the five agent reviews:\n{combined}\n\nNow produce the final Redboard decision memo."

    synthesis = await run_single_agent(
        synthesizer_agent,
        synth_input,
        f"session_synth_{id(decision_brief)}"
    )

    return {
        "agent_outputs": agent_outputs,
        "synthesis": synthesis
    }