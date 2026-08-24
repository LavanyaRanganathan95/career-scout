# Career Scout

A free, self-hosted job alert tool. It checks company career pages every
day, using each platform's own public API (no fragile scraping), and writes a
digest containing only **jobs that are new since yesterday**. Email delivery
is optional.

Runs entirely on GitHub Actions' free tier — no server to manage, no paid
service required beyond a free email API tier.

## Why this exists

Job boards like LinkedIn and Indeed are noisy and often show postings days
late. Checking individual company career pages daily is thorough but
tedious. This tool automates the "check daily" part: it polls each
company's career site, remembers what it saw yesterday, and only tells you
about what's actually new.

## How it works

```
config.json  ──►  fetch_jobs.py  ──►  state.json (yesterday's snapshot)
                        │                    │
                        ▼                    ▼
                 fetch current jobs   diff against snapshot
                        │                    │
                        └──────► digest.txt / digest.html (only new postings)
                                       │
                                       ▼
                              email via Resend (optional)
```

Each day, a scheduled GitHub Actions workflow:

1. Fetches current job listings from every source in `config.json`, using
   each platform's public JSON API (Greenhouse, SmartRecruiters, or
   Workday's job search endpoint).
2. Optionally filters titles against a keyword list you define.
3. Compares results against `state.json`, the snapshot saved from
   yesterday's run.
4. Writes only the genuinely new postings to `digest.txt` and `digest.html`.
5. Optionally emails that digest to you, if you choose to enable Resend.
6. Saves a dated copy in `output/` so past days stay browsable even without
   email.
7. Commits the updated snapshot back to the repo for tomorrow's comparison.

## Supported platforms

| Platform | How it's fetched |
|---|---|
| Greenhouse | Public JSON API — no setup beyond a board token |
| SmartRecruiters | Public JSON API — no setup beyond a company ID |
| Workday | Public JSON search endpoint (POST-based) |

Companies on other platforms (custom-built sites, SAP SuccessFactors, sites
behind bot-protection like Cloudflare/Incapsula) aren't supported — those
generally don't expose a clean, stable API to poll, and scraping rendered
HTML is fragile and breaks easily when a site redesigns.

## Repo structure

```
career-scout/
├── .github/
│   └── workflows/
│       └── job_alert.yml   # the daily scheduled job
├── config.json               # sources + keyword filters — edit this
├── fetch_jobs.py               # the script
├── detect_source.py             # helper: check one URL at a time
├── build_config.py               # helper: check a whole list of URLs at once
├── example/                      # fictional input and output walkthrough
├── .gitignore
├── LICENSE
└── README.md
```

`state.json`, `digest.txt`, `digest.html`, and the `output/` folder are
generated automatically the first time you run it — they don't need to
exist beforehand.

See [`example/`](example/) for a complete fictional walkthrough: career-page
URLs in, generated configuration and unsupported list out, then a first-run
snapshot and a later new-job digest.

## Setup

1. **Fork or copy this repo** into your own GitHub account (private
   recommended, since your target company list is arguably useful
   competitive info about your job search).
2. **Add companies and keywords:** use `build_config.py` with your career-page
   URLs as described below, then edit the generated keyword list.
3. **Optional — set up email delivery:** You do not need a Resend account to
   use Career Scout. Without one, open the generated `digest.txt`,
   `digest.html`, or dated files in `output/` whenever you want to review new
   roles. If you want email notifications:
   - Create a free [Resend](https://resend.com) account (100 emails/day
     free tier, no card required).
   - Get an API key from the Resend dashboard.
   - In your repo: **Settings → Secrets and variables → Actions**, add:
     - `RESEND_API_KEY`
     - `DIGEST_EMAIL_TO` — the address you want the digest sent to
     - `DIGEST_EMAIL_FROM` — optional. Leave it unset for initial testing;
       Resend's testing sender can send only to the email address associated
       with your Resend account. To send to another address, verify your own
       domain in Resend and use an address from that domain.
   - In `config.json`, set `"email_enabled": true`.
4. **Trigger a manual test run** from the **Actions** tab → **Daily Job
   Digest** → **Run workflow**, ticking "Send a sample test email" first to
   confirm email delivery. This test is available only when
   `"email_enabled": true`.

## Adding your own companies

This repo intentionally ships with no company list or job-search terms. Two
ways to add your own, depending on whether you have one company or a whole
list:

### Option A: You have a list of career page URLs (recommended)

1. Put your URLs into a plain text file, one per line — call it
   `urls.txt`. Blank lines and lines starting with `#` are ignored, so
   feel free to paste your list as-is and annotate it.
2. Run:
   ```bash
   python3 build_config.py urls.txt
   ```
3. This generates two files:
   - **`config.json`** — one entry per URL it could handle, with company
     names guessed automatically from the URL (worth a quick skim to make
     sure they read correctly — guessing isn't perfect).
   - **`unsupported_urls.txt`** — every URL it couldn't handle, so you know
     exactly which companies need a native "job alert" signup set up
     manually instead of being auto-monitored.
4. Open `config.json` and replace the example `"keywords"` list with terms
   relevant to your actual search.

### Option B: You just want to check one URL

```bash
python3 detect_source.py "https://paste-the-url-here"
```

Gives you a single ready-to-paste JSON snippet for that one company, or an
honest "not supported" if it isn't one of the three platforms this tool
knows how to poll.

Either way, you do not need to understand the technical details behind a
career site. Provide its full public career-page URL and Career Scout detects
supported platforms and creates the required configuration automatically.

### How to tell if a company is likely supported, before even running the script

Look at the URL itself:

| If the URL contains... | It's probably... |
|---|---|
| `greenhouse.io` | Greenhouse — supported |
| `smartrecruiters.com` | SmartRecruiters — supported |
| `myworkdayjobs.com` | Workday — supported |
| A custom-looking domain with no recognizable pattern (e.g. the company's own domain with `/careers`) | Likely a custom-built site or a platform this tool doesn't cover (SAP SuccessFactors, Oracle Recruiting Cloud, Phenom People) — **not** supported |

### Companies this tool can't support

Some career sites don't expose a public, stable way to fetch job listings —
either because they're custom-built, run on a platform without a public
API, or are actively blocked against automated requests (bot protection
like Cloudflare or Incapsula). For these, your best option is the site's
own **native "job alerts" / "notify me" signup**, if it offers one — most
career pages have this built in, even if this tool can't watch it for you.

## Other customization

- **Keywords** — edit the `keywords` array in `config.json`.
  Case-insensitive substring match against job titles.
- **Turn off keyword filtering** — set `"keyword_filter_enabled": false` to
  see every posting from your configured sources, unfiltered.
- **Turn on email delivery** — set `"email_enabled": true` only after adding
  the Resend secrets. Leave it `false` to use digest files without an email
  provider.
- **Change the schedule** — edit the cron expression in
  `.github/workflows/job_alert.yml` (default: `17 5 * * *`, 05:17 UTC).
  GitHub uses UTC and scheduled runs can be delayed, particularly at the
  beginning of an hour.

## Known limitations

- This is a title-keyword filter, not semantic search — differently worded
  but relevant postings can be missed. Review your keyword list
  periodically.
- Some company career pages may not be recognised automatically. When that
  happens, Career Scout lists them in `unsupported_urls.txt` so you can use
  the company's own job-alert signup instead.
- First run on any source establishes a silent baseline (no digest
  entries), so you don't get a flood of "new" postings that were actually
  already live before you started tracking.

## Feedback

Have an idea, found a bug, or ran into a confusing setup step? Please share
your feedback in the [Issues](../../issues) tab.

## License

MIT — use, modify, and share freely.
