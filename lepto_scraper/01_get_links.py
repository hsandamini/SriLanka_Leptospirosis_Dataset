"""
Step 1: Crawl https://www.epid.gov.lk/weekly-epidemiological-report and
collect every WER PDF link along with its Year / Week / date-range metadata.
"""

import re
import time
import json
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin

BASE = "https://www.epid.gov.lk/weekly-epidemiological-report"

# If you discover additional archive URLs (e.g. per-year pages, or a
# "load more" API endpoint) for years 2007-2015, add them here.
EXTRA_SEED_URLS = [
    # "https://www.epid.gov.lk/weekly-epidemiological-report?year=2010",
]

HEADERS = {
    "User-Agent": "Mozilla/5.0 (research data collection; contact: your-email@example.com)"
}

WEEK_RE = re.compile(r"Week\s+(\d+)", re.IGNORECASE)
DATE_RANGE_RE = re.compile(r"(\d{4}\.\d{2}\.\d{2})\s*-\s*(\d{4}\.\d{2}\.\d{2})")
YEAR_HEADING_RE = re.compile(r"Weekly Epidemiological Report\s*-\s*(\d{4})")


def fetch(url, session):
    resp = session.get(url, headers=HEADERS, timeout=30)
    resp.raise_for_status()
    return resp.text


def parse_entries(html):
    soup = BeautifulSoup(html, "html.parser")
    entries = []
    current_year = None

    for tag in soup.find_all(["h1", "h2", "h3", "h4", "p", "li", "div", "a"]):
        text = tag.get_text(" ", strip=True)

        year_match = YEAR_HEADING_RE.search(text)
        if year_match:
            current_year = int(year_match.group(1))

        if tag.name == "a" and tag.get("href", "").lower().endswith(".pdf"):
            pdf_url = urljoin(BASE, tag["href"])
            context = tag.find_parent(["li", "div"])
            context_text = context.get_text(" ", strip=True) if context else text

            week_match = WEEK_RE.search(context_text)
            date_match = DATE_RANGE_RE.search(context_text)

            entries.append({
                "year": current_year,
                "week": int(week_match.group(1)) if week_match else None,
                "start_date": date_match.group(1) if date_match else None,
                "end_date": date_match.group(2) if date_match else None,
                "pdf_url": pdf_url,
            })

    return entries


def find_pagination_links(html, base_url):
    soup = BeautifulSoup(html, "html.parser")
    links = set()

    next_link = soup.find("a", rel="next")
    if next_link and next_link.get("href"):
        links.add(urljoin(base_url, next_link["href"]))

    for a in soup.find_all("a", href=True):
        if re.search(r"[?&]page=\d+", a["href"]):
            links.add(urljoin(base_url, a["href"]))

    return links


def main():
    session = requests.Session()
    to_visit = [BASE] + EXTRA_SEED_URLS
    visited = set()
    all_entries = []
    seen_pdfs = set()

    safety_limit = 200
    pages_crawled = 0

    while to_visit and pages_crawled < safety_limit:
        url = to_visit.pop(0)
        if url in visited:
            continue
        visited.add(url)
        pages_crawled += 1

        print(f"Fetching: {url}")
        try:
            html = fetch(url, session)
        except Exception as e:
            print(f"  FAILED: {e}")
            continue

        entries = parse_entries(html)
        new_count = 0
        for e in entries:
            if e["pdf_url"] not in seen_pdfs:
                seen_pdfs.add(e["pdf_url"])
                all_entries.append(e)
                new_count += 1
        print(f"  Found {len(entries)} PDF links on this page ({new_count} new)")

        for link in find_pagination_links(html, url):
            if link not in visited:
                to_visit.append(link)

        time.sleep(0.5)

    print(f"\nTotal unique PDF reports found: {len(all_entries)}")

    all_entries.sort(key=lambda e: (e["year"] or 0, e["week"] or 0))

    with open("wer_pdf_links.json", "w") as f:
        json.dump(all_entries, f, indent=2)

    years_found = sorted({e["year"] for e in all_entries if e["year"]})
    print(f"Years covered: {years_found}")
    print("Saved link list to wer_pdf_links.json")

    if not years_found or min(years_found) > 2007:
        print(
            "\nNOTE: It looks like older reports (2007-{}) were not found "
            "on this page.".format(min(years_found) - 1 if years_found else 2015)
        )
        print(
            "Open https://www.epid.gov.lk/weekly-epidemiological-report in a "
            "browser, scroll to the bottom, and check the Network tab in dev "
            "tools for a 'load more' request URL or pagination pattern. Add "
            "it to EXTRA_SEED_URLS at the top of this script and re-run."
        )


if __name__ == "__main__":
    main()