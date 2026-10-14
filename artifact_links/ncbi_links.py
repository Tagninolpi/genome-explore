"""Collect the links to the files of an NCBI assembly (without downloading them)."""

import re

import requests

# all_assemblies: also find older versions (e.g. GCF_000002285.3), which NCBI hides by default
DATASETS_URL = (
    "https://api.ncbi.nlm.nih.gov/datasets/v2/genome/accession/{accession}/dataset_report"
    "?filters.assembly_version=all_assemblies"
)
FTP_URL = "https://ftp.ncbi.nlm.nih.gov/genomes/all/"
TIMEOUT = 30  # seconds to wait for NCBI before giving up

# GCA_ or GCF_, 9 digits, then optionally a dot and a version number
# (GCF_018350175.1, or GCF_018350175 and NCBI picks the latest version)
ACCESSION_FORMAT = re.compile(r"GC[AF]_\d{9}(\.\d+)?")

# label -> how the file name ends on NCBI
NCBI_ENDINGS = {
    "genome_fasta":      "_genomic.fna.gz",
    "gff":               "_genomic.gff.gz",
    "gtf":               "_genomic.gtf.gz",
    "cds":               "_cds_from_genomic.fna.gz",
    "rna":               "_rna.fna.gz",
    "protein":           "_protein.faa.gz",
    "assembly_report":   "_assembly_report.txt",
    "assembly_stats":    "_assembly_stats.txt",
    "annotation_report": "_annotation_report.xml",
    "md5":               "md5checksums.txt",
}


class LinkError(Exception):
    """A problem getting the links of one assembly, with a message a user can understand."""


def fetch(url, what):
    """GET a page from NCBI; turn network and server problems into a clear LinkError."""
    try:
        response = requests.get(url, timeout=TIMEOUT)
        response.raise_for_status()  # error codes such as 404 (not found) or 500 (server error)
    except requests.Timeout:
        raise LinkError(f"NCBI did not answer within {TIMEOUT}s while getting the {what}")
    except requests.ConnectionError:
        raise LinkError(f"could not connect to NCBI to get the {what} (check the internet connection)")
    except requests.HTTPError:
        raise LinkError(f"NCBI answered with error {response.status_code} while getting the {what}")
    return response


def get_assembly_info(accession):
    """Ask NCBI for the full accession (with version) and the assembly name.

    The name is written as it appears in folder names.
    """
    url = DATASETS_URL.format(accession=accession)
    reports = fetch(url, "assembly report").json().get("reports")
    if not reports:  # NCBI answers {} for an accession it does not know
        raise LinkError(f"{accession} was not found on NCBI")
    # without a version, NCBI lists every version of the assembly: keep the current one
    report = next((r for r in reports if r["assembly_info"].get("assembly_status") == "current"), reports[0])
    full_accession = report["accession"]  # always has a version, even if we asked without one
    assembly_name = report["assembly_info"]["assembly_name"].replace(" ", "_")
    return full_accession, assembly_name


def build_folder_url(accession, assembly_name):
    """GCF_018350175.1 -> .../GCF/018/350/175/GCF_018350175.1_<assembly_name>/"""
    digits = accession[4:13]
    return (
        f"{FTP_URL}{accession[:3]}/{digits[0:3]}/{digits[3:6]}/{digits[6:9]}/"
        f"{accession}_{assembly_name}/"
    )


def list_files(folder_url):
    """Read the folder page and return the file names it contains."""
    page = fetch(folder_url, "list of files").text
    return re.findall(r'href="([^"/?]+)"', page)


def ncbi_links(accession):
    """Return the full accession and {label: link} for one NCBI assembly.

    A link is None when the file does not exist.

    Raises LinkError with a readable message when the links cannot be collected.
    """
    if not ACCESSION_FORMAT.fullmatch(accession):
        raise LinkError(f"{accession!r} is not an NCBI accession (expected e.g. GCF_018350175.1)")

    accession, assembly_name = get_assembly_info(accession)
    folder_url = build_folder_url(accession, assembly_name)
    files = list_files(folder_url)

    prefix = f"{accession}_{assembly_name}"
    links = {}
    for label, ending in NCBI_ENDINGS.items():
        found = [f for f in files
                 if f == prefix + ending                                   # normal files: exact name
                 or (label == "annotation_report" and f.endswith(ending))  # starts with the species name
                 or f == ending]                                           # md5checksums.txt
        links[label] = folder_url + found[0] if found else None
    return {"accession": accession, "links": links}
