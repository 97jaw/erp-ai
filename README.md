# Odoo Omni-Agent (OOA)

A multimodal (Voice/Text) AI layer for Odoo ERP supporting v14 and v18.

## Architecture
- **Unified Core** (`/core`): Version-agnostic brain, state contracts, orchestration
- **Versioned Adapters** (`/adapters`): XML-RPC (v14) and JSON-RPC (v18) plugins
- **Integrations** (`/integrations`): Whisper STT, ElevenLabs TTS, Chart Generator
- **Gateway** (`/gateway`): FastAPI service — HTTP and Voice endpoints

## Quick Start
```bash
cp .env.example .env
# Fill in your Odoo and API credentials

pip install -r requirements.txt

# Run tests
pytest tests/

# Start all services
docker-compose up --build
```

## Phase Status
| Phase | Description | Status |
|-------|-------------|--------|
| 1 | Functional & Intent Specification | ✅ Locked |
| 2 | Architecture & Data Strategy | ✅ Locked |
| 3 | Semantic Bridge & KPI Contract | ✅ Locked |
| 4 | Agentic Logic & Deployment | 🔄 In Progress |
