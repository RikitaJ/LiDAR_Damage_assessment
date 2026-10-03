"""Pull Azure OpenAI from rg-consolidated-plan-2026 into .env (never commit)."""
import json
import subprocess
from pathlib import Path

RG = "rg-consolidated-plan-2026"
OPENAI_ACCOUNT = "conplan-openai-2026"
HUB_ACCOUNT = "MyAIHub"
# Only deployment in this RG (vision-capable mini model for photo/video assist)
DEPLOYMENT = "gpt-4o"
API_VERSION = "2024-10-21"

ROOT = Path(__file__).resolve().parents[1]


def _az_json(cmd: str) -> dict:
    out = subprocess.check_output(cmd, shell=True, text=True)
    return json.loads(out)


def main() -> None:
    keys = _az_json(
        f"az cognitiveservices account keys list -g {RG} -n {OPENAI_ACCOUNT} -o json"
    )
    endpoint = _az_json(
        f"az cognitiveservices account show -g {RG} -n {OPENAI_ACCOUNT} "
        f"--query properties.endpoint -o json"
    )
    if isinstance(endpoint, str):
        endpoint_url = endpoint
    else:
        endpoint_url = str(endpoint)

    hub_keys = _az_json(
        f"az cognitiveservices account keys list -g {RG} -n {HUB_ACCOUNT} -o json"
    )
    hub_endpoint = _az_json(
        f"az cognitiveservices account show -g {RG} -n {HUB_ACCOUNT} "
        f"--query properties.endpoint -o json"
    )
    if not isinstance(hub_endpoint, str):
        hub_endpoint = str(hub_endpoint)

    api_key = keys.get("key1") or keys.get("key2") or ""
    vision_key = hub_keys.get("key1") or hub_keys.get("key2") or ""

    lines = [
        "# Local only — rg-consolidated-plan-2026 (never commit)",
        "# Regenerate: az login && python scripts/_write_env_from_consolidated.py",
        "",
        f"AZURE_OPENAI_API_KEY={api_key}",
        f"AZURE_OPENAI_ENDPOINT={endpoint_url.rstrip('/')}/",
        f"AZURE_OPENAI_DEPLOYMENT={DEPLOYMENT}",
        f"AZURE_OPENAI_API_VERSION={API_VERSION}",
        "",
        f"AZURE_VISION_KEY={vision_key}",
        f"AZURE_VISION_ENDPOINT={hub_endpoint.rstrip('/')}/",
    ]
    (ROOT / ".env").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(
        f"Wrote .env: endpoint={OPENAI_ACCOUNT}, deployment={DEPLOYMENT}, hub={HUB_ACCOUNT}"
    )


if __name__ == "__main__":
    main()
