#!/usr/bin/env python3
"""
Give this a list of career page URLs, and it builds config.json for you
automatically — one entry per URL it recognizes — plus a separate file
listing the URLs it couldn't handle, so you know exactly what to set up
native "job alert" signups for instead.

Usage:
    python3 build_config.py urls.txt

Where urls.txt is a plain text file, one URL per line. Blank lines and
lines starting with # are ignored, so you can paste your list straight in
and add comments.

Output:
    config.json           — generated automatically, ready to use
    unsupported_urls.txt  — URLs this tool couldn't detect a platform for
"""

import json
import re
import sys

from detect_source import detect

CONFIG_OUTPUT = "config.json"
UNSUPPORTED_OUTPUT = "unsupported_urls.txt"

DEFAULT_KEYWORDS = [
    "software engineer",
    "data scientist",
    "research scientist",
    "product manager",
]


def guess_name(entry):
    """Turn a board_token / company_id / tenant into a readable display
    name. Heuristic only — always worth a quick manual check afterward."""
    raw = entry.get("board_token") or entry.get("company_id") or entry.get("tenant") or "?"
    # Split camelCase/PascalCase: "AcmeBiotech" -> "Acme Biotech"
    spaced = re.sub(r"(?<!^)(?=[A-Z])", " ", raw)
    # Turn hyphens/underscores into spaces too: "some-company" -> "some company"
    spaced = spaced.replace("-", " ").replace("_", " ")
    # Collapse repeated spaces, title-case each word
    words = [w for w in spaced.split(" ") if w]
    return " ".join(w.capitalize() if w.islower() else w for w in words)


def read_urls(path):
    urls = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            urls.append(line)
    return urls


def main():
    if len(sys.argv) != 2:
        print(__doc__)
        sys.exit(1)

    urls = read_urls(sys.argv[1])
    if not urls:
        print(f"No URLs found in {sys.argv[1]} — check the file has one URL per line.")
        sys.exit(1)

    sources = []
    unsupported = []

    print(f"Checking {len(urls)} URL(s)...\n")

    for url in urls:
        result = detect(url)
        if result is None:
            unsupported.append(url)
            print(f"  [unsupported] {url}")
            continue

        entry = dict(result["entry"])
        entry["name"] = guess_name(entry)
        sources.append(entry)
        print(f"  [{result['platform']}] {url}  ->  \"{entry['name']}\"")

    config = {
        "sources": sources,
        "_comment_keywords": (
            "Auto-generated example keywords below — replace with terms "
            "relevant to your search. Matching is case-insensitive substring "
            "match against job titles."
        ),
        "keywords": DEFAULT_KEYWORDS,
        "keyword_filter_enabled": True,
        "email_enabled": False,
    }

    with open(CONFIG_OUTPUT, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2, ensure_ascii=False)

    with open(UNSUPPORTED_OUTPUT, "w", encoding="utf-8") as f:
        if unsupported:
            f.write("# These URLs could not be automatically monitored.\n")
            f.write("# Set up native \"job alert\" / \"notify me\" signups on these sites directly.\n\n")
            f.write("\n".join(unsupported) + "\n")
        else:
            f.write("# Nothing here — every URL you provided was supported.\n")

    print(f"\n{len(sources)} source(s) written to {CONFIG_OUTPUT}")
    print(f"{len(unsupported)} unsupported URL(s) written to {UNSUPPORTED_OUTPUT}")
    if sources:
        print(
            f"\nHeads up: company names in {CONFIG_OUTPUT} were guessed from "
            f"the URL — double check they read correctly, and edit the "
            f"\"keywords\" list before your first real run."
        )


if __name__ == "__main__":
    main()
