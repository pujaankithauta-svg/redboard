# Redboard

Adversarial AI review panel for shipping decisions. 
Five specialist agents debate your proposal in parallel. 
One synthesizer produces a go/no-go memo with minority dissent preserved.

## Setup

1. Clone the repo
2. Copy `.env.example` to `.env` and fill in your keys
3. Install dependencies: `pip install -r requirements.txt`
4. Authenticate gcloud: `gcloud auth application-default login`
5. Run: `uvicorn main:app --reload`
6. Go to `http://localhost:8000/docs`

## Agents

- Safety Agent
- Business Agent  
- Data Quality Agent
- Compliance Agent
- Contrarian Agent
- Synthesizer Agent