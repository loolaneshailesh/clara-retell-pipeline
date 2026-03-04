import argparse
import os
import re


def normalize_text(text: str) -> str:
    """Remove timestamps, speaker labels, and normalize whitespace."""
    # Remove timestamps like [00:01:23] or 00:01:23
    text = re.sub(r"\[\d{2}:\d{2}:\d{2}\]", " ", text)
    text = re.sub(r"\b\d{2}:\d{2}:\d{2}\b", " ", text)

    # Remove speaker labels like "Agent:", "Customer:", "Rep:", "Caller:", "Speaker N:"
    text = re.sub(
        r"^(Agent|Customer|Caller|Rep|Representative|Speaker \d+|Host|Guest):\s*",
        "",
        text,
        flags=re.MULTILINE
    )

    # Remove markdown-style headers or separators
    text = re.sub(r"^[-=]{3,}\s*$", "", text, flags=re.MULTILINE)

    # Collapse multiple blank lines into a single newline
    text = re.sub(r"\n{3,}", "\n\n", text)

    # Collapse multiple spaces/tabs
    text = re.sub(r"[ \t]+", " ", text)

    return text.strip()


def main():
    parser = argparse.ArgumentParser(
        description="Normalize a raw call transcript by removing timestamps and speaker labels."
    )
    parser.add_argument("--input", required=True, help="Path to the raw transcript .txt file")
    parser.add_argument("--output", required=True, help="Path to write the normalized transcript")
    args = parser.parse_args()

    with open(args.input, "r", encoding="utf-8") as f:
        raw = f.read()

    normalized = normalize_text(raw)

    os.makedirs(os.path.dirname(args.output), exist_ok=True)
    with open(args.output, "w", encoding="utf-8") as f:
        f.write(normalized)

    print(f"[normalizer] Done: {args.output}")


if __name__ == "__main__":
    main()
