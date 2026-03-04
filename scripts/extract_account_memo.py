import argparse
import json
import os
import re
from typing import Any, Dict, List, Optional


# ---------------------------------------------------------------------------
# Individual field extractors
# ---------------------------------------------------------------------------

def extract_company_name(text: str) -> Optional[str]:
    patterns = [
        r"(?:This is|You(?:'ve| have)? reached|Welcome to|Thank you for calling)\s+([A-Z][A-Za-z0-9 &,.']+?)(?:\.|,|!|\n)",
        r"([A-Z][A-Za-z0-9 &]+(?:Fire|Security|Protection|Services|Plumbing|Electric|HVAC|Roofing|Pest|Landscaping)[A-Za-z0-9 &]*)",
    ]
    for p in patterns:
        m = re.search(p, text)
        if m:
            return m.group(1).strip().rstrip(".,")
    return None


def extract_business_hours(text: str) -> Dict[str, Any]:
    result = {"timezone": None, "regular": [], "exceptions": []}

    # timezone
    tz_map = {
        "eastern": "America/New_York",
        "central": "America/Chicago",
        "mountain": "America/Denver",
        "pacific": "America/Los_Angeles",
        "EST": "America/New_York",
        "CST": "America/Chicago",
        "MST": "America/Denver",
        "PST": "America/Los_Angeles",
    }
    for key, tz in tz_map.items():
        if re.search(key, text, re.IGNORECASE):
            result["timezone"] = tz
            break

    # days + hours pattern
    day_pattern = (
        r"(Monday(?:\s+through|\s+to|\s*-\s*)Friday|Mon(?:\.|\s*-\s*)Fri|Mon\s+through\s+Fri)"
        r"[,\s]+"
        r"(\d{1,2})(?::(\d{2}))?\s*(am|pm|a\.m\.|p\.m\.)?\s*(?:to|-|through)\s*(\d{1,2})(?::(\d{2}))?\s*(am|pm|a\.m\.|p\.m\.)"
    )
    m = re.search(day_pattern, text, re.IGNORECASE)
    if m:
        start_h = int(m.group(2))
        start_min = int(m.group(3) or 0)
        start_ampm = (m.group(4) or "").lower().replace(".", "")
        end_h = int(m.group(5))
        end_min = int(m.group(6) or 0)
        end_ampm = (m.group(7) or "").lower().replace(".", "")

        if start_ampm == "pm" and start_h != 12:
            start_h += 12
        elif start_ampm == "am" and start_h == 12:
            start_h = 0
        if end_ampm == "pm" and end_h != 12:
            end_h += 12
        elif end_ampm == "am" and end_h == 12:
            end_h = 0

        result["regular"].append({
            "days": ["Mon", "Tue", "Wed", "Thu", "Fri"],
            "start": f"{start_h:02d}:{start_min:02d}",
            "end": f"{end_h:02d}:{end_min:02d}",
        })
    return result


def extract_office_address(text: str) -> Optional[str]:
    m = re.search(
        r"\b\d{2,5}\s+[A-Z][A-Za-z0-9]+(?:\s+[A-Za-z]+){0,3}\s+(?:Street|St|Ave|Avenue|Road|Rd|Blvd|Boulevard|Drive|Dr|Lane|Ln|Way|Ct|Court|Place|Pl)\b[^\n]*",
        text
    )
    if m:
        return m.group(0).strip()
    return None


def extract_services(text: str) -> List[str]:
    services = []
    found = re.findall(
        r"(?:we (?:handle|offer|do|provide|specialize in)|our services include)[^.]*\.",
        text, re.IGNORECASE
    )
    for phrase in found:
        parts = re.split(r",|\sand\s|\sor\s", phrase)
        for p in parts:
            p = re.sub(r"(?i)(we|our|services|handle|offer|provide|include|specialize in)", "", p).strip(" .")
            if len(p) > 3:
                services.append(p.lower())
    return list(dict.fromkeys(services))


def extract_emergency_definition(text: str) -> List[str]:
    triggers = []
    sentences = re.split(r"(?<=[.!?])\s+", text)
    for s in sentences:
        if re.search(r"emergency", s, re.IGNORECASE):
            s = s.strip()
            if len(s) < 200:
                triggers.append(s)
    return triggers[:5]  # cap at 5


def extract_emergency_routing(text: str) -> Dict[str, Any]:
    rules = {"primary_contacts": [], "order": "", "fallback": ""}
    if re.search(r"on.call", text, re.IGNORECASE):
        rules["primary_contacts"].append({"name": "On-call technician", "phone": None})
    if re.search(r"service manager", text, re.IGNORECASE):
        rules["primary_contacts"].append({"name": "Service manager", "phone": None})
    if re.search(r"owner", text, re.IGNORECASE):
        rules["primary_contacts"].append({"name": "Owner", "phone": None})

    rules["order"] = "Try each contact in order until one answers"

    if re.search(r"(nobody|no one|doesn't answer|not available|voicemail)", text, re.IGNORECASE):
        rules["fallback"] = "If nobody answers, take a detailed message and mark urgent for morning follow-up"
    else:
        rules["fallback"] = "If transfer fails, take a message and assure urgent callback"
    return rules


def extract_non_emergency_routing(text: str) -> Dict[str, Any]:
    rules = []
    keyword_map = [
        (r"billing", "For billing questions, route to accounting"),
        (r"schedul", "For scheduling, route to the main office line"),
        (r"inspect", "For inspection requests, route to the scheduling team"),
        (r"estimat", "For estimates, route to the sales team"),
        (r"general", "For general inquiries, route to the main office"),
    ]
    for pattern, rule in keyword_map:
        if re.search(pattern, text, re.IGNORECASE):
            rules.append(rule)
    return {"rules": rules}


def extract_integration_constraints(text: str) -> List[str]:
    constraints = []
    for m in re.finditer(
        r"(?:never|do not|don'?t|avoid|make sure not to|do not create)[^.!?]*[.!?]",
        text, re.IGNORECASE
    ):
        s = m.group(0).strip()
        if len(s) > 5:
            constraints.append(s)
    return constraints


def build_memo(text: str, account_id: str) -> Dict[str, Any]:
    questions: List[str] = []

    company_name = extract_company_name(text)
    if not company_name:
        questions.append("Company name not clearly identifiable from transcript.")

    business_hours = extract_business_hours(text)
    if not business_hours["regular"]:
        questions.append("Business hours (days, start, end times) not clearly specified.")
    if not business_hours["timezone"]:
        questions.append("Timezone not specified.")

    office_address = extract_office_address(text)
    if not office_address:
        questions.append("Office address not clearly specified.")

    services_supported = extract_services(text)
    if not services_supported:
        questions.append("Services offered by this company are not clearly specified.")

    emergency_definition = extract_emergency_definition(text)
    if not emergency_definition:
        questions.append("Emergency definition is not clearly specified.")

    emergency_routing_rules = extract_emergency_routing(text)
    if not emergency_routing_rules["primary_contacts"]:
        questions.append("Emergency routing contacts (on-call, manager) not specified.")

    non_emergency_routing_rules = extract_non_emergency_routing(text)
    if not non_emergency_routing_rules["rules"]:
        questions.append("Non-emergency routing rules (billing, scheduling, etc.) not specified.")

    integration_constraints = extract_integration_constraints(text)

    return {
        "account_id": account_id,
        "company_name": company_name,
        "business_hours": business_hours,
        "office_address": office_address,
        "services_supported": services_supported,
        "emergency_definition": emergency_definition,
        "emergency_routing_rules": emergency_routing_rules,
        "non_emergency_routing_rules": non_emergency_routing_rules,
        "call_transfer_rules": {
            "timeout_seconds": 25,
            "max_retries": 2,
            "on_fail_message": "I was not able to reach anyone live, but I will have someone call you back as soon as possible."
        },
        "integration_constraints": integration_constraints,
        "after_hours_flow_summary": (
            "After hours: greet caller, confirm if emergency, if yes collect name/phone/address "
            "and attempt transfer. If transfer fails, take message and assure urgent callback."
        ),
        "office_hours_flow_summary": (
            "During office hours: greet, identify reason, collect name/phone, "
            "route to appropriate team. If transfer fails, take message."
        ),
        "questions_or_unknowns": questions,
        "notes": ""
    }


def main():
    parser = argparse.ArgumentParser(
        description="Extract structured account memo from a normalized transcript."
    )
    parser.add_argument("--input", required=True, help="Path to normalized transcript")
    parser.add_argument("--output", required=True, help="Path to write memo.json")
    parser.add_argument("--account-id", required=True, help="Account identifier")
    args = parser.parse_args()

    with open(args.input, "r", encoding="utf-8") as f:
        text = f.read()

    memo = build_memo(text, args.account_id)

    os.makedirs(os.path.dirname(args.output), exist_ok=True)
    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(memo, f, indent=2)

    print(f"[extractor] Memo written: {args.output}")
    if memo["questions_or_unknowns"]:
        print(f"[extractor] {len(memo['questions_or_unknowns'])} unknowns logged.")


if __name__ == "__main__":
    main()
