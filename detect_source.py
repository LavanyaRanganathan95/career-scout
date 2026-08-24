#!/usr/bin/env python3
"""
Paste in any career page URL, and this tells you what to add to config.json
— or tells you honestly that the platform isn't supported.

Single-URL usage:
    python3 detect_source.py "https://job-boards.greenhouse.io/acme-labs"

For checking a whole list of URLs at once and generating config.json
automatically, use build_config.py instead — it uses this same detection
logic under the hood.
"""

import json
import re
import sys


def detect(url):
    """Given a career page URL, return a dict describing the detected
    platform and the config.json entry to use — or None if unsupported."""
    # Greenhouse: job-boards.greenhouse.io/{token} or boards.greenhouse.io/{token}
    m = re.search(r"(?:job-boards|boards)\.greenhouse\.io/([a-zA-Z0-9_-]+)", url)
    if m:
        token = m.group(1)
        return {
            "platform": "greenhouse",
            "confidence": "high",
            "entry": {
                "name": "<company name>",
                "type": "greenhouse",
                "board_token": token,
            },
        }

    # SmartRecruiters: careers.smartrecruiters.com/{CompanyID}
    m = re.search(r"careers\.smartrecruiters\.com/([a-zA-Z0-9_-]+)", url)
    if m:
        company_id = m.group(1)
        return {
            "platform": "smartrecruiters",
            "confidence": "high",
            "entry": {
                "name": "<company name>",
                "type": "smartrecruiters",
                "company_id": company_id,
            },
        }

    # Workday career pages include a locale and career-site segment. Keep the
    # complete public prefix because the API returns only a relative job path.
    m = re.search(
        r"^(https?://([a-zA-Z0-9_-]+)\.(wd\d+)\.myworkdayjobs\.com)"
        r"/([a-z]{2,3}-[a-zA-Z]{2,4})/([a-zA-Z0-9_-]+)(?:/|$)",
        url,
    )
    if m:
        base, tenant, wd_host, locale, site = m.groups()
        return {
            "platform": "workday",
            "confidence": "medium",
            "entry": {
                "name": "<company name>",
                "type": "workday",
                "tenant": tenant,
                "wd_host": wd_host,
                "site": site,
                "public_base_url": f"{base}/{locale}/{site}",
            },
            "note": (
                "Workday's URL structure varies more than Greenhouse/SmartRecruiters. "
                "Provide a public Workday career-page URL that includes its locale and "
                "career-site segment (for example, '/en-US/Company_Careers'). The "
                "detector keeps that exact prefix so job links remain clickable."
            ),
        }

    return None


def main():
    if len(sys.argv) != 2:
        print(__doc__)
        sys.exit(1)

    url = sys.argv[1]
    result = detect(url)

    if result is None:
        print(f"Could not identify a supported platform for:\n  {url}\n")
        print(
            "This usually means the site runs on a custom-built career page, or a "
            "platform this tool doesn't support yet (e.g. SAP SuccessFactors, Phenom "
            "People, Oracle Recruiting Cloud). Those don't expose a stable public API "
            "the same way Greenhouse/SmartRecruiters/Workday do, so this tool can't "
            "reliably watch them. Your best bet for these is the site's own native "
            "'job alerts' signup, if it has one."
        )
        sys.exit(1)

    print(f"Detected platform: {result['platform']} (confidence: {result['confidence']})\n")
    print("Add this to the \"sources\" array in config.json:\n")
    print(json.dumps(result["entry"], indent=2))
    print(f'\n(Replace "<company name>" with whatever label you want to see in your digest.)')
    if "note" in result:
        print(f"\nNote: {result['note']}")


if __name__ == "__main__":
    main()
