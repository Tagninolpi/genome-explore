import json
import math
import time
from concurrent.futures import ThreadPoolExecutor
from simplify_dict import get_data_model_simplified

import requests

URL = "https://ngdc.cncb.ac.cn/gwh/gwhSearch/api"

PARAMS = {
    "term": "attrs.taxonomy_id:(7711) OR attrs.tax_lineage:(7711)",  # Chordata
    "species": "", "source": "", "genome_representation": "",
    "assembly_level": "", "scientific_name": "", "bioproject": "",
    "has_annotation": "", "has_reannotation": "",
    "release_date_from": "", "release_date_to": "",
    "genome_size_from": "", "genome_size_to": "",
    "sort_by": "id.keyword",   # unique keyword field -> stable order
    "sort_order": "ASC",       # must be uppercase for this server
}

PAGE_SIZE = 500   # ~14 ms/record; bigger pages are not faster and fail more often
WORKERS = 4       # be polite to the server
RETRIES = 5
OUTPUT = "gwh_chordata.json"

session = requests.Session()


def fetch_page(page):
    """Fetch one page, retrying on dropped connections and server error bodies."""
    for attempt in range(1, RETRIES + 1):
        try:
            r = session.get(
                URL, params={**PARAMS, "page": page, "length": PAGE_SIZE}, timeout=120
            )
            r.raise_for_status()
            js = r.json()
            if "data" not in js:
                raise RuntimeError(f"server error body: {json.dumps(js)[:200]}")
            return js
        except Exception as e:
            if attempt == RETRIES:
                raise
            wait = 2 ** attempt
            print(f"page {page}: {type(e).__name__}, retry {attempt}/{RETRIES} in {wait}s")
            time.sleep(wait)


def main():
    t0 = time.perf_counter()

    first = fetch_page(1)
    total = first["totalHits"]
    n_pages = math.ceil(total / PAGE_SIZE)
    print(f"totalHits={total} -> {n_pages} pages of {PAGE_SIZE}")

    pages = {1: first["data"]}
    with ThreadPoolExecutor(max_workers=WORKERS) as pool:
        for page, js in zip(range(2, n_pages + 1),
                            pool.map(fetch_page, range(2, n_pages + 1))):
            pages[page] = js["data"]
            print(f"page {page}/{n_pages} ok ({len(js['data'])} records)")

    # every page except the last must be full
    for p in range(1, n_pages):
        if len(pages[p]) != PAGE_SIZE:
            print(f"WARNING: page {p} has {len(pages[p])} records, expected {PAGE_SIZE}")

    records = [rec for p in range(1, n_pages + 1) for rec in pages[p]]
    ids = [r["id"] for r in records]
    unique = len(set(ids))

    print(f"\nfetched={len(records)} unique_ids={unique} totalHits={total} "
          f"time={time.perf_counter() - t0:.0f}s")
    if unique != total or len(records) != total:
        print("MISMATCH: the dataset is NOT complete or contains duplicates. "
              "Not saving; investigate before using it.")
        return

    with open(OUTPUT, "w", encoding="utf-8") as f:
        json.dump(records, f)
    print(f"OK: complete and duplicate-free, saved to {OUTPUT}")


if __name__ == "__main__":
    #main()
    records = json.load(open("gwh_chordata.json", encoding="utf-8"))
    print(len(records))
    print(records[0].keys())
    print(get_data_model_simplified(records))
