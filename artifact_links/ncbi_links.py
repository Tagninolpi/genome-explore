"""Collect the links to the files of an NCBI assembly (without downloading them)."""

import re

from .common import LABELS, LinkError, fetch, list_files

# all_assemblies: also find older versions (e.g. GCF_000002285.3), which NCBI hides by default
DATASETS_URL = (
    "https://api.ncbi.nlm.nih.gov/datasets/v2/genome/accession/{accession}/dataset_report"
    "?filters.assembly_version=all_assemblies"
)
FTP_URL = "https://ftp.ncbi.nlm.nih.gov/genomes/all/"

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
    "feature_table":     "_feature_table.txt.gz",
    "assembly_report":   "_assembly_report.txt",
    "assembly_stats":    "_assembly_stats.txt",
    "annotation_report": "_annotation_report.xml",
    "md5":               "md5checksums.txt",
}


def get_assembly_info(accession):
    """Ask NCBI for the full accession (with version), the assembly name and the species.

    The assembly name is written as it appears in folder names.
    """
    url = DATASETS_URL.format(accession=accession)
    reports = fetch(url, "assembly report", "NCBI").json().get("reports")
    if not reports:  # NCBI answers {} for an accession it does not know
        raise LinkError(f"{accession} was not found on NCBI")
    # without a version, NCBI lists every version of the assembly: keep the current one
    report = next((r for r in reports if r["assembly_info"].get("assembly_status") == "current"), reports[0])
    full_accession = report["accession"]  # always has a version, even if we asked without one
    assembly_name = report["assembly_info"]["assembly_name"].replace(" ", "_")
    species = report["organism"]["organism_name"]
    return full_accession, assembly_name, species


def build_folder_url(accession, assembly_name):
    """GCF_018350175.1 -> .../GCF/018/350/175/GCF_018350175.1_<assembly_name>/"""
    digits = accession[4:13]
    return (
        f"{FTP_URL}{accession[:3]}/{digits[0:3]}/{digits[3:6]}/{digits[6:9]}/"
        f"{accession}_{assembly_name}/"
    )


def ncbi_links(accession, assembly_name=None, species=None):
    """Return the full accession, the species and {label: link} for one NCBI assembly.

    assembly_name is optional: when it is already known (e.g. from the search
    results), NCBI's API is not asked again. The accession must then have its version,
    and the species is the one given (or None).
    A link is None when the file does not exist.

    Raises LinkError with a readable message when the links cannot be collected.
    """
    if not ACCESSION_FORMAT.fullmatch(accession):
        raise LinkError(f"{accession!r} is not an NCBI accession (expected e.g. GCF_018350175.1)")

    if assembly_name is None:
        accession, assembly_name, species = get_assembly_info(accession)
    elif "." not in accession:
        raise LinkError(f"{accession} needs its version number (e.g. .1) when the assembly name is given")
    else:
        assembly_name = assembly_name.replace(" ", "_")
    folder_url = build_folder_url(accession, assembly_name)
    files = list_files(folder_url, "NCBI")

    prefix = f"{accession}_{assembly_name}"
    links = {label: None for label in LABELS}
    for label, ending in NCBI_ENDINGS.items():
        found = [f for f in files
                 if f == prefix + ending                                   # normal files: exact name
                 or (label == "annotation_report" and f.endswith(ending))  # starts with the species name
                 or f == ending]                                           # md5checksums.txt
        links[label] = folder_url + found[0] if found else None
    return {"accession": accession, "species": species, "links": links}
