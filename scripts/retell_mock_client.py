"""retell_mock_client.py

Mock Retell API client.
When you obtain a real Retell API key, replace the mock methods
with real HTTP calls to https://api.retellai.com/v2/create-agent

Environment variable:
    RETELL_API_KEY - set this to your real Retell API key to use live mode.

Usage (mock):
    python retell_mock_client.py --spec outputs/accounts/acme_fire_001/v1/agent_spec.json

Usage (live, requires RETELL_API_KEY):
    RETELL_API_KEY=your_key python retell_mock_client.py --spec ... --live
"""
import argparse
import json
import os
import uuid
from typing import Any, Dict

try:
    import requests
    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False


RETELL_API_BASE = "https://api.retellai.com"


# ---------------------------------------------------------------------------
# Mock implementation
# ---------------------------------------------------------------------------

def mock_create_agent(spec: Dict[str, Any]) -> Dict[str, Any]:
    """Simulate creating an agent; returns a fake response."""
    mock_id = f"mock_agent_{spec.get('agent_name', 'unknown').lower().replace(' ', '_')}_{spec.get('version', 'v1')}"
    return {
        "agent_id": mock_id,
        "agent_name": spec.get("agent_name"),
        "version": spec.get("version"),
        "status": "created",
        "mock": True
    }


# ---------------------------------------------------------------------------
# Live implementation (Retell API v2)
# ---------------------------------------------------------------------------

def live_create_agent(spec: Dict[str, Any], api_key: str) -> Dict[str, Any]:
    """Create a real Retell agent using the Retell API.
    Docs: https://docs.retellai.com/api-references/create-agent
    """
    if not REQUESTS_AVAILABLE:
        raise ImportError("requests package is required for live mode. Run: pip install requests")

    url = f"{RETELL_API_BASE}/v2/create-agent"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }

    # Map spec fields to Retell API payload
    payload = {
        "agent_name": spec.get("agent_name"),
        "response_engine": {
            "type": "retell-llm",
            "llm_id": None  # Will need to create an LLM first in Retell
        },
        "voice_id": "11labs-Adrian",  # default; customize to match voice_style
        "language": "en-US",
    }

    # If system_prompt exists, you need to create an LLM object first
    # For simplicity, we skip that here and just store the spec locally
    # In production, call POST /v2/create-retell-llm first, then pass llm_id
    print("[retell-client] NOTE: In live mode, create a Retell LLM first with the system_prompt,")
    print("  then pass the llm_id here. See: https://docs.retellai.com/api-references/create-retell-llm")
    print("  Proceeding with agent creation only (no LLM attached).")

    resp = requests.post(url, headers=headers, json=payload, timeout=30)
    resp.raise_for_status()
    return resp.json()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Create a Retell agent from an agent_spec.json (mock or live)."
    )
    parser.add_argument("--spec", required=True, help="Path to agent_spec.json")
    parser.add_argument("--live", action="store_true", help="Use real Retell API (requires RETELL_API_KEY env var)")
    parser.add_argument("--output", help="Optional: path to write the API response JSON")
    args = parser.parse_args()

    with open(args.spec, "r", encoding="utf-8") as f:
        spec = json.load(f)

    if args.live:
        api_key = os.environ.get("RETELL_API_KEY")
        if not api_key:
            print("ERROR: RETELL_API_KEY environment variable is not set.")
            return
        print(f"[retell-client] LIVE mode: calling Retell API...")
        result = live_create_agent(spec, api_key)
    else:
        print(f"[retell-client] MOCK mode: simulating agent creation...")
        result = mock_create_agent(spec)

    print(json.dumps(result, indent=2))

    if args.output:
        os.makedirs(os.path.dirname(args.output), exist_ok=True)
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2)
        print(f"[retell-client] Response written: {args.output}")


if __name__ == "__main__":
    main()
