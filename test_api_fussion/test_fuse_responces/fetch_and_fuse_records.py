import requests
import field_mappings as m


def fetch_all_NCBI_reports(taxon,page_size=1000):
    URL = f"https://api.ncbi.nlm.nih.gov/datasets/v2/genome/taxon/{taxon}/dataset_report"
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


def fetch_all_GWH_reports(taxon_id, page_size=500):
    URL = "https://ngdc.cncb.ac.cn/gwh/gwhSearch/api"
    params = {
        "term": f"attrs.taxonomy_id:({taxon_id}) OR attrs.tax_lineage:({taxon_id})",
        "species": "", "source": "", "genome_representation": "",
        "assembly_level": "", "scientific_name": "", "bioproject": "",
        "has_annotation": "", "has_reannotation": "",
        "release_date_from": "", "release_date_to": "",
        "genome_size_from": "", "genome_size_to": "",
        "sort_by": "id.keyword", "sort_order": "ASC",
        "length": page_size,
    }
    reports, page = [], 1
    while True:
        r = requests.get(URL, params={**params, "page": page}, timeout=120)
        r.raise_for_status()
        js = r.json()
        reports += js["data"]
        if len(reports) >= js["totalHits"] or not js["data"]:
            return reports
        page += 1


def get_value(record, keys):
    """Walk `keys` through a raw dict. Returns None if the record, the keys
    or any step on the way is missing (a value that is really None is the same)."""
    if record is None or keys is None:
        return None
    value = record
    for key in keys:
        if not isinstance(value, dict) or key not in value:
            return None
        value = value[key]
    return value


def fuse(ncbi, gwh, mapping):
    """Fuse one raw NCBI dict and one raw GWH dict (either may be None)."""
    if ncbi is None and gwh is None:
        raise ValueError("fuse needs at least one of the two records")
    if mapping is None:
        raise ValueError("fuse needs the mapping table")

    fused = {}
    for name, ncbi_keys, gwh_keys in mapping:
        ncbi_value = get_value(ncbi, ncbi_keys)
        gwh_value = get_value(gwh, gwh_keys)
        if (ncbi_value is not None and gwh_value is not None
                and str(ncbi_value) == str(gwh_value)):
            fused[name] = ncbi_value
        else:
            fused[name] = {"ncbi": ncbi_value, "gwh": gwh_value}
    return fused

def fetch_and_fuse(taxon_id,fields_mapping):
    NCBI = fetch_all_NCBI_reports(taxon_id)
    GWH = fetch_all_GWH_reports(taxon_id)

    all_reports = {}

    for report in NCBI:
        all_reports[report["accession"]]= {"NCBI":report,"GWH":None}

    for report in GWH:
        if report["id"] in all_reports:
            all_reports[report["id"]]["GWH"] = report
        else:
            all_reports[report["id"]] = {"NCBI":None,"GWH":report}

    all_fused = {}

    for accession,reports_dict in all_reports.items():
          all_fused[accession] = fuse(reports_dict["NCBI"],reports_dict["GWH"],fields_mapping)

    return all_fused

all_res = fetch_and_fuse(9823,m.test1)
print(all_res)
print(len(all_res))
