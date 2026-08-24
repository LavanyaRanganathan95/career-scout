#!/usr/bin/env python3
"""
Daily Career Scout digest.

Pulls current openings from Greenhouse, SmartRecruiters, and Workday sources
defined in config.json, filters them against a keyword list, compares them
to yesterday's snapshot (state.json), and writes a digest of only the NEW
postings to digest.txt (plain text) and digest.html (formatted). Optionally
emails the HTML digest via Resend.

Designed to run once a day via GitHub Actions (see .github/workflows/job_alert.yml).
"""

import datetime
import html
import json
import os
import sys
import time
import urllib.request
import urllib.error

CONFIG_PATH = os.path.join(os.path.dirname(__file__), "config.json")
STATE_PATH = os.path.join(os.path.dirname(__file__), "state.json")
DIGEST_PATH = os.path.join(os.path.dirname(__file__), "digest.txt")
DIGEST_HTML_PATH = os.path.join(os.path.dirname(__file__), "digest.html")
OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "output")

USER_AGENT = "Mozilla/5.0 (compatible; career-scout-bot/1.0)"


def http_get_json(url, headers=None):
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, **(headers or {})})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


def http_post_json(url, payload, headers=None):
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        method="POST",
        headers={
            "User-Agent": USER_AGENT,
            "Content-Type": "application/json",
            "Accept": "application/json",
            **(headers or {}),
        },
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


# ---------------------------------------------------------------------------
# Fetchers — each returns a list of {"id": str, "title": str, "location": str, "url": str}
# ---------------------------------------------------------------------------

def fetch_greenhouse(source):
    token = source["board_token"]
    url = f"https://boards-api.greenhouse.io/v1/boards/{token}/jobs"
    data = http_get_json(url)
    jobs = []
    for j in data.get("jobs", []):
        jobs.append({
            "id": str(j["id"]),
            "title": j.get("title", ""),
            "location": (j.get("location") or {}).get("name", ""),
            "url": j.get("absolute_url", ""),
        })
    return jobs


def fetch_smartrecruiters(source):
    company_id = source["company_id"]
    jobs = []
    offset = 0
    limit = 100
    while True:
        url = f"https://api.smartrecruiters.com/v1/companies/{company_id}/postings?limit={limit}&offset={offset}"
        data = http_get_json(url)
        content = data.get("content", [])
        if not content:
            break
        for j in content:
            location = j.get("location", {}) or {}
            loc_str = ", ".join(filter(None, [location.get("city"), location.get("country")]))
            jobs.append({
                "id": str(j["id"]),
                "title": j.get("name", ""),
                "location": loc_str,
                "url": j.get("applyUrl") or j.get("ref", ""),
            })
        offset += limit
        if offset >= data.get("totalFound", 0):
            break
        time.sleep(0.3)
    return jobs


def fetch_workday(source):
    tenant = source["tenant"]
    wd_host = source["wd_host"]
    site = source["site"]
    public_base_url = source["public_base_url"].rstrip("/")
    base = f"https://{tenant}.{wd_host}.myworkdayjobs.com"
    api_url = f"{base}/wday/cxs/{tenant}/{site}/jobs"

    jobs = []
    limit = 20
    offset = 0
    total = None
    headers = {
        "Referer": public_base_url,
    }
    while True:
        payload = {"appliedFacets": {}, "limit": limit, "offset": offset, "searchText": ""}
        try:
            data = http_post_json(api_url, payload, headers=headers)
        except urllib.error.HTTPError as e:
            print(f"  [warn] Workday {tenant}/{site} HTTP {e.code} at offset {offset}: {e.reason}")
            break
        postings = data.get("jobPostings", [])
        if not postings:
            break
        for p in postings:
            external_path = p.get("externalPath", "")
            jobs.append({
                "id": external_path or p.get("bulletFields", [""])[0] or p.get("title", ""),
                "title": p.get("title", ""),
                "location": p.get("locationsText", ""),
                # Previous implementation omitted the locale and career-site prefix:
                # "url": base + external_path if external_path else base,
                "url": public_base_url + external_path if external_path else public_base_url,
            })
        if total is None:
            total = data.get("total", len(postings))
        offset += limit
        if offset >= total:
            break
        time.sleep(0.5)  # be polite, avoid Workday throttling
    return jobs


FETCHERS = {
    "greenhouse": fetch_greenhouse,
    "smartrecruiters": fetch_smartrecruiters,
    "workday": fetch_workday,
}


# ---------------------------------------------------------------------------
# Core logic
# ---------------------------------------------------------------------------

def load_json(path, default):
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return default


def save_json(path, obj):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, indent=2, ensure_ascii=False)


def matches_keywords(title, keywords):
    title_lower = title.lower()
    return any(kw.lower() in title_lower for kw in keywords)


def run_test_email(email_enabled):
    """Send a sample digest immediately, bypassing fetch/diff logic entirely.
    Use this to confirm Resend + secrets are wired up correctly, without
    waiting for a real new posting to show up."""
    fake_postings = {
        "Example Co": [
            {
                "id": "test-1",
                "title": "Sample Scientist Role — Liquid Biopsy",
                "location": "Remote / Example City",
                "url": "https://example.com/jobs/test-1",
            }
        ]
    }
    digest_text = build_text_digest(fake_postings, 1)
    digest_html = build_html_digest(fake_postings, 1)
    print("--- TEST DIGEST (not based on real data) ---")
    print(digest_text)
    if email_enabled:
        maybe_send_email(digest_text, digest_html, 1)
    else:
        print('[info] Email delivery is disabled in config.json — test email not sent.')


def main():
    config = load_json(CONFIG_PATH, None)
    if config is None:
        print("config.json not found", file=sys.stderr)
        sys.exit(1)

    email_enabled = config.get("email_enabled", False)
    if "--test-email" in sys.argv:
        run_test_email(email_enabled)
        return

    state = load_json(STATE_PATH, {})  # {source_name: [job_ids...]}
    keywords = config.get("keywords", [])
    filter_enabled = config.get("keyword_filter_enabled", True)

    new_state = {}
    new_postings_by_source = {}

    for source in config["sources"]:
        name = source["name"]
        src_type = source["type"]
        fetcher = FETCHERS.get(src_type)
        if not fetcher:
            print(f"  [warn] unknown source type '{src_type}' for {name}, skipping")
            continue

        print(f"Fetching {name} ({src_type})...")
        try:
            jobs = fetcher(source)
        except Exception as e:
            print(f"  [error] failed to fetch {name}: {e}")
            # Keep previous state untouched so we don't lose track / spam "new" on next success
            new_state[name] = state.get(name, [])
            continue

        print(f"  -> {len(jobs)} total postings")

        if filter_enabled and keywords:
            jobs = [j for j in jobs if matches_keywords(j["title"], keywords)]
            print(f"  -> {len(jobs)} match keyword filter")

        current_ids = [j["id"] for j in jobs]
        new_state[name] = current_ids

        previous_ids = set(state.get(name, []))
        new_jobs = [j for j in jobs if j["id"] not in previous_ids]

        if previous_ids:  # only report "new" if we actually have a prior snapshot
            if new_jobs:
                new_postings_by_source[name] = new_jobs
        else:
            print(f"  -> first run for {name}, establishing baseline (no digest entries)")

    save_json(STATE_PATH, new_state)

    total_new = sum(len(v) for v in new_postings_by_source.values())

    digest_text = build_text_digest(new_postings_by_source, total_new)
    digest_html = build_html_digest(new_postings_by_source, total_new)

    with open(DIGEST_PATH, "w", encoding="utf-8") as f:
        f.write(digest_text)
    with open(DIGEST_HTML_PATH, "w", encoding="utf-8") as f:
        f.write(digest_html)

    archive_today(digest_text, digest_html)

    print("\n--- DIGEST ---")
    print(digest_text)

    if total_new > 0:
        if email_enabled:
            maybe_send_email(digest_text, digest_html, total_new)
        else:
            print('[info] Email delivery is disabled in config.json.')


def archive_today(digest_text, digest_html):
    """Save a dated copy of today's digest into output/, so past days can be
    looked up manually even if an email was missed or never sent (e.g. on a
    day with zero new postings)."""
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    date_str = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d")
    txt_path = os.path.join(OUTPUT_DIR, f"digest_{date_str}.txt")
    html_path = os.path.join(OUTPUT_DIR, f"digest_{date_str}.html")
    with open(txt_path, "w", encoding="utf-8") as f:
        f.write(digest_text)
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(digest_html)
    print(f"[info] Archived today's digest to {txt_path}")


def build_text_digest(new_postings_by_source, total_new):
    lines = []
    if total_new == 0:
        lines.append("No new matching positions today.")
    else:
        lines.append(f"{total_new} new matching position(s) found today:\n")
        for source_name, jobs in new_postings_by_source.items():
            lines.append(f"== {source_name} ==")
            for j in jobs:
                loc = f" ({j['location']})" if j["location"] else ""
                lines.append(f"- {j['title']}{loc}\n  {j['url']}")
            lines.append("")
    return "\n".join(lines)


def build_html_digest(new_postings_by_source, total_new):
    esc = html.escape

    if total_new == 0:
        body = "<p>No new matching positions today.</p>"
    else:
        sections = []
        for source_name, jobs in new_postings_by_source.items():
            items = []
            for j in jobs:
                loc = f' <span style="color:#666;">({esc(j["location"])})</span>' if j["location"] else ""
                items.append(
                    f'<li style="margin-bottom:10px;">'
                    f'<a href="{esc(j["url"])}" style="font-weight:600;color:#0b5fff;text-decoration:none;">{esc(j["title"])}</a>'
                    f'{loc}</li>'
                )
            sections.append(
                f'<h2 style="font-size:16px;margin:24px 0 8px;border-bottom:1px solid #eee;padding-bottom:4px;">{esc(source_name)}</h2>'
                f'<ul style="list-style:none;padding-left:0;margin:0;">{"".join(items)}</ul>'
            )
        body = (
            f'<p style="font-size:14px;color:#333;">'
            f'<strong>{total_new}</strong> new matching position(s) found today.</p>'
            + "".join(sections)
        )

    generated_at = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    return f"""<!DOCTYPE html>
<html>
<head><meta charset="utf-8"></head>
<body style="font-family:-apple-system,Helvetica,Arial,sans-serif;max-width:600px;margin:0 auto;padding:24px;color:#111;">
  <h1 style="font-size:20px;margin-bottom:4px;">Career Scout</h1>
  <p style="font-size:12px;color:#999;margin-top:0;margin-bottom:16px;">Generated {generated_at} · Created using Claude.ai</p>
  {body}
  <p style="margin-top:32px;font-size:12px;color:#999;">Generated automatically by Career Scout.</p>
</body>
</html>"""


def maybe_send_email(digest_text, digest_html, total_new):
    api_key = os.environ.get("RESEND_API_KEY")
    to_addr = os.environ.get("DIGEST_EMAIL_TO")
    # GitHub Actions supplies an empty string for an unset optional secret, so
    # use ``or`` to fall back to Resend's testing sender in that case.
    from_addr = os.environ.get("DIGEST_EMAIL_FROM") or "onboarding@resend.dev"

    if not api_key or not to_addr:
        print("\n[info] RESEND_API_KEY / DIGEST_EMAIL_TO not set — skipping email send.")
        return

    payload = {
        "from": from_addr,
        "to": [to_addr],
        "subject": f"Career Scout: {total_new} new matching position(s)",
        "html": digest_html,
        "text": digest_text,  # fallback for clients that don't render HTML
    }
    try:
        http_post_json(
            "https://api.resend.com/emails",
            payload,
            headers={"Authorization": f"Bearer {api_key}"},
        )
        print("[info] Digest email sent.")
    except Exception as e:
        print(f"[warn] Failed to send email: {e}")


if __name__ == "__main__":
    main()
