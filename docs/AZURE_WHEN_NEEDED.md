# Azure (this project uses Azure only — no OpenAI.com or Hugging Face keys)

Phases 1–3 (LiDAR, Stray, video v0) run **offline**. Azure is wired for **Phase 4+** only.

## Env vars (see `.env.example`)

| Azure product | When | Variables |
|---------------|------|-----------|
| **Azure OpenAI** (`conplan-openai-2026`, deploy `gpt-4o`) | Photo tier VLM | `AZURE_OPENAI_API_KEY`, `AZURE_OPENAI_ENDPOINT`, `AZURE_OPENAI_DEPLOYMENT`, `AZURE_OPENAI_API_VERSION` |
| **Azure AI hub** (`MyAIHub`, optional) | Phase 5 damage / tagging | `AZURE_VISION_KEY`, `AZURE_VISION_ENDPOINT` |

## Populate `.env` locally

```powershell
az login
python scripts/_write_env_from_consolidated.py
```

Resource group: **rg-consolidated-plan-2026**. Never commit `.env`.
