from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import asyncio
from orchestrator import run_panel

app = FastAPI(title="Redboard API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

class DecisionBrief(BaseModel):
    proposal: str
    context: str
    team: str

@app.get("/")
def root():
    return {"status": "Redboard is running"}

@app.post("/review")
async def review(brief: DecisionBrief):
    full_brief = f"""
PROPOSAL: {brief.proposal}
CONTEXT: {brief.context}
TEAM: {brief.team}
"""
    result = await run_panel(full_brief)
    return {
        "synthesis": result["synthesis"],
        "agent_outputs": result["agent_outputs"]
    }