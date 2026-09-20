#!/usr/bin/env python3
"""CineAI — terminal demo. No UI required.

Examples:
    python cli.py "Who directed Spirited Away?"
    python cli.py "how many episodes does attack on titan have" --template
    python cli.py "recommend an anime like Death Note" --llm
"""

from __future__ import annotations

import argparse
import json
import sys

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from moan import ask


def main() -> int:
    parser = argparse.ArgumentParser(description="CineAI — Movie & Anime Q&A (terminal)")
    parser.add_argument("question", nargs="+", help="your question (quote it)")
    parser.add_argument("--template", action="store_true", help="force the no-LLM local answer engine")
    parser.add_argument("--llm", action="store_true", help="force the LLM (requires LLM_API_KEY)")
    parser.add_argument("--json", action="store_true", help="print raw JSON instead of styled text")
    args = parser.parse_args()

    question = " ".join(args.question)
    mode = "template" if args.template else ("llm" if args.llm else "auto")
    answer = ask(question, mode=mode)

    if args.json:
        print(json.dumps(answer.to_dict(), indent=2))
        return 0

    print()
    print(f"  Q:  {answer.question}")
    print(f"  A:  {answer.answer}")
    if answer.sources:
        print(f"      sources: {', '.join(s.url for s in answer.sources)}")
    print(f"      engine:   {answer.provider}")
    for warning in answer.warnings:
        if warning != answer.answer:
            print(f"      note:     {warning}")
    print()
    return 0


if __name__ == "__main__":
    sys.exit(main())