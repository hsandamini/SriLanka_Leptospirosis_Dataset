import fitz  # PyMuPDF

TARGET_FILES = [
    "pdfs/2024_w01_en_65b8d3689b762_Vol_51_no_01-english.pdf",
]


def inspect(fpath):
    print(f"\n{'='*80}\nFILE: {fpath}\n{'='*80}")
    doc = fitz.open(fpath)
    print(f"Total pages: {len(doc)}")
    for i, page in enumerate(doc):
        text = page.get_text("text")
        print(f"\n--- PAGE {i} (length {len(text)}) ---")
        print(text[:1500])  # first 1500 chars only, to keep it readable


if __name__ == "__main__":
    for f in TARGET_FILES:
        inspect(f)