"""Collect the links to the files of a GWH assembly (without downloading them).

Only genomes submitted directly to GWH (accessions starting with GWH) are handled here.
GWH's copies of NCBI genomes (GCA_/GCF_) are better taken from NCBI itself, with ncbi_links.
"""

import re

from .common import LABELS, LinkError, fetch, list_files

# The search service of the GWH website. Unlike GWH's public API
# (/gwh/api/public/assembly/), it also knows the recent genomes.
SEARCH_URL = "https://ngdc.cncb.ac.cn/gwh/gwhSearch/api"
SEARCH_PARAMS = {  # the service expects all of these, even when empty
    "species": "", "source": "", "genome_representation": "",
    "assembly_level": "", "scientific_name": "", "bioproject": "",
    "has_annotation": "", "has_reannotation": "",
    "release_date_from": "", "release_date_to": "",
    "genome_size_from": "", "genome_size_to": "",
    "sort_by": "id.keyword", "sort_order": "ASC",
    "page": 1, "length": 10,
}
DOWNLOAD_URL = "https://download.cncb.ac.cn/gwh/"  # start of the folder links of direct submissions

# GWH, 4 letters, 8 digits, then optionally a dot and a version number
# (GWHBHRQ00000000, GWHKEQZ00000000.1)
ACCESSION_FORMAT = re.compile(r"GWH[A-Z]{4}\d{8}(\.\d+)?")

# label -> how the file name ends on GWH (the name is the accession followed by this)
# GWH has no GTF and no report files: those labels stay None.
GWH_ENDINGS = {
    "genome_fasta":  ".genome.fasta.gz",
    "gff":           ".gff.gz",
    "cds":           ".CDS.fasta.gz",
    "rna":           ".RNA.fasta.gz",
    "protein":       ".Protein.faa.gz",
    "feature_table": ".feature.gz",
    "md5":           "_md5.txt",
}


def remove_html(text):
    """'<a href='...'>GWHBHRQ00000000</a>' -> 'GWHBHRQ00000000'"""
    return re.sub(r"<[^>]+>", "", text)


def get_folder_info(accession):
    """Ask GWH's search for the full accession (with version, if it has one), the folder link and the species."""
    params = {**SEARCH_PARAMS, "term": accession}
    records = fetch(SEARCH_URL, "assembly information", "GWH", params=params).json().get("data") or []

    # the search can return other records that mention the accession: keep the genome itself
    for record in records:
        found = remove_html(record["attrs"].get("accession", ""))
        if found == accession or found.startswith(accession + "."):
            folder_url = DOWNLOAD_URL + record["attrs"]["ftp_directory"] + "/"
            return found, folder_url, record["attrs"].get("scientific_name")
    raise LinkError(f"{accession} was not found on GWH")


def gwh_links(accession, folder_url=None, species=None):
    """Return the full accession, the species and {label: link} for one GWH assembly.

    folder_url is optional: when it is already known (e.g. from the search
    results), GWH is not asked again, and the species is the one given (or None).
    A link is None when the file does not exist.

    Raises LinkError with a readable message when the links cannot be collected.
    """
    if not ACCESSION_FORMAT.fullmatch(accession):
        raise LinkError(f"{accession!r} is not a GWH accession (expected e.g. GWHBHRQ00000000)")

    if folder_url is None:
        accession, folder_url, species = get_folder_info(accession)
    files = list_files(folder_url, "GWH")

    links = {label: None for label in LABELS}
    for label, ending in GWH_ENDINGS.items():
        if accession + ending in files:  # GWH file names are always the accession + the ending
            links[label] = folder_url + accession + ending
    return {"accession": accession, "species": species, "links": links}
