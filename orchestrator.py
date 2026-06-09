import asyncio
import os
import json
from dotenv import load_dotenv
from google.adk.agents import LlmAgent
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types as genai_types
import uuid

load_dotenv()

api_key = os.environ.get("GEMINI_API_KEY")
os.environ["GOOGLE_GENAI_USE_VERTEXAI"] = "false"
os.environ["GOOGLE_API_KEY"] = api_key

# ── Import agents from their individual modules ────────────────────────────────
from agents.safety_agent import safety_agent
from agents.business_agent import business_agent
from agents.data_agent import data_agent
from agents.compliance_agent import compliance_agent
from agents.contrarian_agent import contrarian_agent
from agents.synthesizer_agent import synthesizer_agent

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