import argparse
import json
import os
from typing import Any, Dict

from jinja2 import Template


DEFAULT_PROMPT_PATH = "/project/config/prompt_templates/base_system_prompt.txt"


def humanize_business_hours(bh: Dict[str, Any]) -> str:
    if not bh or not bh.get("regular"):
        return "not specified - please clarify with the customer"
    reg = bh["regular"][0]
    days = ", ".join(reg.get("days", [])) or "unspecified days"
    start = reg.get("start", "??")
    end = reg.get("end", "??")
    tz = bh.get("timezone") or "unspecified timezone"
    result = f"{days} from {start} to {end} ({tz})"
    if len(bh["regular"]) > 1:
        extra = bh["regular"][1:]
        for r in extra:
            ds = ", ".join(r.get("days", []))
            result += f"; {ds} from {r.get('start','??')} to {r.get('end','??')}"
    return result


def humanize_list(lst) -> str:
    if not lst:
        return "not specified"
    return "; ".join(str(x) for x in lst)


def non_emergency_summary(non_emergency_rules: Dict[str, Any]) -> str:
    rules = non_emergency_rules.get("rules", [])
    if not rules:
        return "follow the company standard routing: take a message, collect name, callback number, and reason."
    return " ".join(rules)


def load_prompt_template(path: str) -> str:
    if not os.path.exists(path):
        raise FileNotFoundError(f"Prompt template not found: {path}")
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def build_agent_spec(memo: Dict[str, Any], version: str, base_prompt: str) -> Dict[str, Any]:
    tmpl = Template(base_prompt)
    system_prompt = tmpl.render(
        company_name=memo.get("company_name") or "the company",
        business_hours_human=humanize_business_hours(memo.get("business_hours") or {}),
        office_address=memo.get("office_address") or "not specified",
        emergency_definition_human=humanize_list(memo.get("emergency_definition") or []),
        non_emergency_routing_summary=non_emergency_summary(memo.get("non_emergency_routing_rules") or {})
    )

    company = memo.get("company_name") or "Company"
    bh = memo.get("business_hours") or {}
    er = memo.get("emergency_routing_rules") or {}
    ctr = memo.get("call_transfer_rules") or {}

    return {
        "agent_name": f"{company} Phone Agent",
        "voice_style": "friendly_professional_female",
        "version": version,
        "timezone": bh.get("timezone"),
        "business_hours": bh,
        "office_address": memo.get("office_address"),
        "services_supported": memo.get("services_supported") or [],
        "emergency_routing": {
            "definition": memo.get("emergency_definition") or [],
            "contacts": er.get("primary_contacts") or [],
            "routing_order": er.get("order") or "",
            "fallback": er.get("fallback") or "",
            "transfer_timeout_seconds": ctr.get("timeout_seconds", 25),
            "max_transfer_retries": ctr.get("max_retries", 2)
        },
        "non_emergency_routing": memo.get("non_emergency_routing_rules") or {},
        "call_transfer_protocol": {
            "on_before_transfer": "Let the caller know you are connecting them and they might hear a brief silence.",
            "on_transfer_fail": ctr.get("on_fail_message", "I was not able to reach anyone live, but I will have someone call you back as soon as possible."),
            "post_fail_next_steps": "Confirm that someone will call them back as soon as possible."
        },
        "integration_constraints": memo.get("integration_constraints") or [],
        "tool_placeholders": {
            "create_ticket_tool": {
                "description": "Internal tool to create a support or service ticket.",
                "inputs": ["name", "phone", "reason", "urgency", "address"],
                "outputs": ["ticket_id"]
            }
        },
        "questions_or_unknowns": memo.get("questions_or_unknowns") or [],
        "system_prompt": system_prompt
    }


def main():
    parser = argparse.ArgumentParser(
        description="Generate a Retell Agent Spec JSON from a memo JSON."
    )
    parser.add_argument("--memo", required=True, help="Path to memo.json")
    parser.add_argument("--version", required=True, help="Version tag, e.g. v1 or v2")
    parser.add_argument("--output", required=True, help="Path to write agent_spec.json")
    parser.add_argument(
        "--prompt-template",
        default=DEFAULT_PROMPT_PATH,
        help=f"Path to base_system_prompt.txt (default: {DEFAULT_PROMPT_PATH})"
    )
    args = parser.parse_args()

    with open(args.memo, "r", encoding="utf-8") as f:
        memo = json.load(f)

    base_prompt = load_prompt_template(args.prompt_template)
    spec = build_agent_spec(memo, args.version, base_prompt)

    os.makedirs(os.path.dirname(args.output), exist_ok=True)
    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(spec, f, indent=2)

    print(f"[spec-generator] Agent spec ({args.version}) written: {args.output}")


if __name__ == "__main__":
    main()
