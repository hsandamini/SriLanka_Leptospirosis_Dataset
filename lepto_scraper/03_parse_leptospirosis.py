"""
Step 3 (v10): Parse Leptospirosis case counts by district using PyMuPDF.

Fix from v9: some reports split Ampara district's health reporting into
two separate RDHS divisions - "Ampara" and "Kalmunai" - even though
Kalmunai is administratively part of Ampara district. Previously
"Kalmunai" wasn't recognized at all, so its numbers were silently
dropped. We now recognize it separately, then ADD its Leptospirosis
numbers into Ampara's totals to get the true district-level figure.

Leptospirosis is always the 6th disease listed in the real table, after:
Dengue Fever, Dysentery, Encephalitis, Enteric Fever, Food Poisoning.
So its A (weekly) and B (cumulative) numbers are the 11th and 12th
numbers collected for each district (0-indexed positions 10 and 11).

NOTE on dates: the archive lists each report with a "Week N" label, but
the table INSIDE each PDF actually covers the PREVIOUS week (a one-week
reporting lag). This script still records the archive's own label as
"year"/"week"/"start_date"/"end_date" for traceability back to the
source file, but the actual coverage dates are corrected afterward
during final data assembly (subtracting 7 days), not here.
"""

import json
import csv
import re
import fitz  # PyMuPDF

DISTRICTS = [
    "Colombo", "Gampaha", "Kalutara", "Kandy", "Matale", "Nuwara Eliya",
    "Galle", "Hambantota", "Matara", "Jaffna", "Kilinochchi", "Mannar",
    "Vavuniya", "Mullaitivu", "Batticaloa", "Ampara", "Trincomalee",
    "Kurunegala", "Puttalam", "Anuradhapura", "Polonnaruwa", "Badulla",
    "Monaragala", "Ratnapura", "Kegalle",
]

# Kalmunai is a separate RDHS reporting division but administratively
# part of Ampara district - its numbers get merged into Ampara's.
MERGE_INTO = {
    "kalmunai": "Ampara",
}

LEPTO_A_INDEX = 10
LEPTO_B_INDEX = 11

STOP_MARKERS = {"srilanka", "sourceweekly", "source", "key", "provinces",
                 "rdhsdivisions", "dpdhsdivisions", "datasources", "comments",
                 "printingofthispublication"}

TOKEN_RE = re.compile(r"\d+|[A-Za-z]+")
NOTIFIABLE_RE = re.compile(
    r"notifiable\s+diseases\s+reported\s+by\s+medical\s+officers\s+of\s+health",
    re.IGNORECASE
)


def norm(s):
    return re.sub(r"[^a-z]", "", s.lower())


DISTRICT_NORM_LIST = [(norm(d), d) for d in DISTRICTS]
DISTRICT_LOOKUP = {n: d for n, d in DISTRICT_NORM_LIST}


def match_district(token):
    """Returns the matched district name, or None. Special-cases
    Kalmunai to return a distinct marker so we can merge it later."""
    key = norm(token)
    if not key:
        return None
    if key in MERGE_INTO:
        return "__KALMUNAI__"
    if key in DISTRICT_LOOKUP:
        return DISTRICT_LOOKUP[key]
    if len(key) >= 4:
        candidates = [d for dnorm, d in DISTRICT_NORM_LIST
                      if dnorm.startswith(key) or dnorm.endswith(key)]
        if len(candidates) == 1:
            return candidates[0]
    return None


def tokenize(text):
    return TOKEN_RE.findall(text)


def district_count(text):
    tokens = tokenize(text)
    return sum(1 for tok in tokens if tok.isalpha() and match_district(tok))


def find_table_page(doc):
    for page in doc:
        text = page.get_text("text")
        if NOTIFIABLE_RE.search(text):
            return page

    for page in doc:
        text = page.get_text("text")
        if re.search(r"notifiable\s+diseases", text, re.IGNORECASE) and district_count(text) >= 15:
            return page

    best_page, best_count = None, 0
    for page in doc:
        count = district_count(page.get_text("text"))
        if count > best_count:
            best_page, best_count = page, count
    if best_count >= 15:
        return best_page
    return None


def parse_page_rows(page):
    tokens = tokenize(page.get_text("text"))

    results = {}
    current_district = None
    buffer = []

    for tok in tokens:
        if tok.isdigit():
            if current_district is not None:
                buffer.append(int(tok))
            continue

        matched = match_district(tok)
        if matched:
            if current_district and buffer:
                results[current_district] = buffer  # keep LATEST occurrence
            current_district = matched
            buffer = []
            continue

        key = norm(tok)
        if key in STOP_MARKERS:
            if current_district and buffer:
                results[current_district] = buffer
            current_district = None
            buffer = []
            continue

        if current_district and buffer:
            results[current_district] = buffer
        current_district = None
        buffer = []

    if current_district and buffer:
        results[current_district] = buffer

    return results


def parse_pdf(fpath):
    try:
        doc = fitz.open(fpath)
        page = find_table_page(doc)
        if page is None:
            return None, "Could not find a page with enough recognizable district rows"

        rows = parse_page_rows(page)
        # Count real districts only (exclude the Kalmunai marker) for the threshold check
        real_district_count = sum(1 for d in rows if d != "__KALMUNAI__")
        if real_district_count < 15:
            return None, f"Only found {real_district_count} district rows (expected ~25)"

        results = []
        incomplete = []
        kalmunai_lepto = None

        for district, numbers in rows.items():
            if district == "__KALMUNAI__":
                if len(numbers) > LEPTO_B_INDEX:
                    kalmunai_lepto = (numbers[LEPTO_A_INDEX], numbers[LEPTO_B_INDEX])
                continue
            if len(numbers) > LEPTO_B_INDEX:
                results.append([district, numbers[LEPTO_A_INDEX], numbers[LEPTO_B_INDEX]])
            else:
                incomplete.append(f"{district}({len(numbers)}nums)")

        # Merge Kalmunai's Leptospirosis numbers into Ampara's, if both present
        if kalmunai_lepto is not None:
            merged = False
            for entry in results:
                if entry[0] == "Ampara":
                    entry[1] += kalmunai_lepto[0]
                    entry[2] += kalmunai_lepto[1]
                    merged = True
                    break
            if not merged:
                # Ampara itself wasn't captured but Kalmunai was - use
                # Kalmunai's numbers as Ampara's (better than nothing)
                results.append(["Ampara", kalmunai_lepto[0], kalmunai_lepto[1]])

        if not results:
            return None, "Found district rows but none had enough numbers for Leptospirosis"

        method = "pymupdf_v10"
        if incomplete:
            method += f" (incomplete for: {', '.join(incomplete)})"

        return [tuple(r) for r in results], method
    except Exception as e:
        return None, f"Exception: {e}"


def main():
    with open("wer_pdf_links.json") as f:
        entries = json.load(f)

    rows = []
    failures = []

    for i, entry in enumerate(entries, 1):
        fpath = entry.get("local_path")
        if not fpath:
            continue
        print(f"[{i}/{len(entries)}] Parsing {fpath}")
        result, info = parse_pdf(fpath)

        if result is None:
            failures.append({
                "year": entry.get("year"),
                "week": entry.get("week"),
                "pdf": fpath,
                "reason": info,
            })
            continue

        for district, a_val, b_val in result:
            rows.append({
                "year": entry.get("year"),
                "week": entry.get("week"),
                "start_date": entry.get("start_date"),
                "end_date": entry.get("end_date"),
                "district": district,
                "leptospirosis_cases_week": a_val,
                "leptospirosis_cases_cumulative": b_val,
                "parse_method": info,
                "source_pdf": fpath,
            })

    with open("leptospirosis_weekly_by_district.csv", "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()) if rows else [
            "year", "week", "start_date", "end_date", "district",
            "leptospirosis_cases_week", "leptospirosis_cases_cumulative",
            "parse_method", "source_pdf"])
        writer.writeheader()
        writer.writerows(rows)

    with open("failed_parses.csv", "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["year", "week", "pdf", "reason"])
        writer.writeheader()
        writer.writerows(failures)

    print(f"\nParsed rows: {len(rows)}")
    print(f"Failed PDFs: {len(failures)} (see failed_parses.csv)")
    print("Output: leptospirosis_weekly_by_district.csv")


if __name__ == "__main__":
    main()