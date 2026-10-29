import requests
import field_mappings as m
from time import perf_counter
import math
from concurrent.futures import ThreadPoolExecutor


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


def fetch_all_GWH_reports(taxon_id, page_size=500, workers=8):
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

    session = requests.Session()

    def get_page(page):
        r = session.get(URL, params={**params, "page": page}, timeout=60)
        r.raise_for_status()
        return r.json()

    first = get_page(1)
    total = first["totalHits"]
    n_pages = math.ceil(first["totalHits"] / page_size)
    reports = list(first["data"])
    print(f"{len(reports)} / {total}")

    with ThreadPoolExecutor(max_workers=workers) as ex:
        for js in ex.map(get_page, range(2, n_pages + 1)):
            reports.extend(js["data"])
            print(f"{len(reports)} / {total}")

    session.close()
    return reports


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

def get_fused_stats(fused,NCBI_tot,GWH_tot):
    NCBI_alone = 0
    GWH_alone = 0
    both = 0
    tot = 0
    for i,(accession,dict_pair)  in enumerate(fused.items()):
        if type(dict_pair["accession"]) ==str:
            both +=1
        elif dict_pair["accession"]["ncbi"]:
             NCBI_alone +=1
        else:
            GWH_alone +=1
        tot +=1
    if not(both+NCBI_alone == NCBI_tot):
        print("NCBI issue")
    if not(both+GWH_alone == GWH_tot):
            print("GWH issue")
    print(f"tot={tot} both={both} NCBI={NCBI_alone} GWH={GWH_alone}")        


def fetch_and_fuse(taxon_id,fields_mapping):
    t0 = perf_counter()
    # API requests
    print("start NCBI APi request")
    NCBI = fetch_all_NCBI_reports(taxon_id)
    t1 = perf_counter()
    print(f"request took: {t1 - t0:.3f}s")

    print("start GWH API request")
    GWH = fetch_all_GWH_reports(taxon_id)
    t2 = perf_counter()
    print(f"request took: {t2 - t1:.3f}s")

    # list to dict
    all_reports = {}
    for report in NCBI:
        if report["accession"] not in all_reports:
            all_reports[report["accession"]]= {"NCBI":report,"GWH":None}
        else:
            print(f"duplicate : {report["accession"]}")
    for report in GWH:
        if report["id"] in all_reports:
            if all_reports[report["id"]]["GWH"] == None:
                all_reports[report["id"]]["GWH"] = report
            else:
                print(f"duplicate:{report["id"]}")
        else:
            all_reports[report["id"]] = {"NCBI":None,"GWH":report}

    # keep usefull info and merge results
    all_fused = {}
    for accession,reports_dict in all_reports.items():
          all_fused[accession] = fuse(reports_dict["NCBI"],reports_dict["GWH"],fields_mapping)
    get_fused_stats(all_fused,len(NCBI),len(GWH))
    return all_fused

#all_res = fetch_and_fuse(7711,m.test1) # 9823 9606 #7711
#print(all_res)
#print(len(all_res))
