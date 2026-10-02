# Azure (later phases only — not used in Phase 1)

Phase 1 uses **Apple RoomPlan JSON only**. No Azure calls.

When we reach **Phase 4 (photos)** you may enable:

| Azure product | Purpose | Env vars |
|---------------|---------|----------|
| **Azure OpenAI** (GPT-4o / GPT-4o-mini with vision) | Guess room layout from photos when geometry is weak | `AZURE_OPENAI_API_KEY`, `AZURE_OPENAI_ENDPOINT`, `AZURE_OPENAI_DEPLOYMENT` |
| **Azure AI Vision** (optional, Phase 5) | Extra tags for damage cues | `AZURE_VISION_KEY`, `AZURE_VISION_ENDPOINT` |

In Azure Portal search: **Azure OpenAI** → create resource → deploy a **gpt-4o** (or gpt-4o-mini) model → copy endpoint + key.

We will add code in Phase 4 behind `housefloor run --tier photos` only. LiDAR accuracy does not depend on Azure.
