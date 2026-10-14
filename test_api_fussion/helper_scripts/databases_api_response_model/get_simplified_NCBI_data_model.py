import requests
from simplify_dict import get_data_model_simplified

URL = "https://api.ncbi.nlm.nih.gov/datasets/v2/genome/taxon/chordata/dataset_report"

def fetch_all_reports(page_size=1000):
    session = requests.Session()
    params = {"page_size": page_size}
    reports = []

    while True:
        response = session.get(URL, params=params, timeout=60)
        response.raise_for_status()
        data = response.json()

        reports.extend(data.get("reports", []))

        token = data.get("next_page_token")
        if not token:
            break
        params["page_token"] = token

        print(f"{len(reports)} / {data.get('total_count', '?')}")

    return reports

#reports = fetch_all_reports()
#print(len(reports))
#print(get_data_model_simplified(reports))
