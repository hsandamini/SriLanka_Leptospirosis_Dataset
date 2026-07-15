"""
Step 2: Download every PDF listed in wer_pdf_links.json into ./pdfs/
Resumable: re-running skips files that already exist and look complete.
"""

import json
import os
import time
import requests

HEADERS = {
    "User-Agent": "Mozilla/5.0 (research data collection; contact: your-email@example.com)"
}

OUT_DIR = "pdfs"


def safe_filename(entry):
    year = entry.get("year") or "unknown_year"
    week = entry.get("week") or "unknown_week"
    original_name = entry["pdf_url"].split("/")[-1]
    return f"{year}_w{int(week):02d}_{original_name}" if isinstance(week, int) else f"{year}_{original_name}"


def main():
    os.makedirs(OUT_DIR, exist_ok=True)

    with open("wer_pdf_links.json") as f:
        entries = json.load(f)

    print(f"{len(entries)} PDFs to download")

    failures = []
    session = requests.Session()

    for i, entry in enumerate(entries, 1):
        fname = safe_filename(entry)
        fpath = os.path.join(OUT_DIR, fname)
        entry["local_path"] = fpath

        if os.path.exists(fpath) and os.path.getsize(fpath) > 1000:
            continue

        print(f"[{i}/{len(entries)}] Downloading {entry['pdf_url']} -> {fpath}")
        try:
            resp = session.get(entry["pdf_url"], headers=HEADERS, timeout=60)
            resp.raise_for_status()
            with open(fpath, "wb") as f:
                f.write(resp.content)
        except Exception as e:
            print(f"  FAILED: {e}")
            failures.append({"entry": entry, "error": str(e)})

        time.sleep(0.3)

    with open("wer_pdf_links.json", "w") as f:
        json.dump(entries, f, indent=2)

    if failures:
        with open("download_failures.json", "w") as f:
            json.dump(failures, f, indent=2)
        print(f"\n{len(failures)} downloads failed. See download_failures.json")
    else:
        print("\nAll downloads succeeded.")


if __name__ == "__main__":
    main()