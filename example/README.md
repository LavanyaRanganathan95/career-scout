# Example walkthrough

Everything in this folder is fictional. It is here to show the files the
scripts read and create; do not expect the example URLs to return real jobs.

## 1. Start with career-page URLs

Put one career-page URL on each line in `urls.txt`. It can include comments
and blank lines.

```bash
python3 build_config.py example/urls.txt
```

For the fictional input in this folder, the helper recognizes three URLs and
writes the equivalent of `config.generated.json`. It also writes
`unsupported_urls.txt`, containing the URL it cannot monitor.

Before using the generated `config.json`, replace its example keywords with
your own search terms.

## 2. Run the digest for the first time

```bash
python3 fetch_jobs.py
```

On a first run, the script saves the matching job identifiers to `state.json`
and deliberately sends no digest. This establishes a baseline, so you do not
receive an alert for jobs that already existed before you started. An
illustrative snapshot is in `state.after-first-run.json`.

## 3. Run it tomorrow

The script fetches the current postings again and compares their identifiers
with `state.json`. Jobs not present in yesterday's snapshot appear in the
digest. `digest.next-run.txt` shows an example where one new job appeared.
Email is optional: leave `"email_enabled": false` to use the digest files,
or set it to `true` and configure Resend secrets if you want notifications.

## What each helper is for

| Command | Purpose | Files created or updated |
|---|---|---|
| `python3 detect_source.py URL` | Check one career-page URL and print a source entry | None |
| `python3 build_config.py urls.txt` | Turn many supported career URLs into sources | `config.json`, `unsupported_urls.txt` |
| `python3 fetch_jobs.py` | Fetch jobs, compare with yesterday, write a digest | `state.json`, `digest.txt`, `digest.html`, `output/` |

The example configuration includes all three supported platforms. The
Workday entry also includes `public_base_url`; that is what makes its relative
API job paths into clickable public links.
