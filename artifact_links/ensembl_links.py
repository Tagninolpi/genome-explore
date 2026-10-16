"""Collect the links to the files of an Ensembl assembly."""

import re

from .common import LABELS, LinkError, fetch, list_files

SEARCH_URL = "https://www.ensembl.org/api/search/genomes/v3"

# GCA_ or GCF_, 9 digits, then optionally a dot and a version number.
# Ensembl uses NCBI's accessions: mostly GCA_, and GCF_ when it reuses NCBI's annotation.
ACCESSION_FORMAT = re.compile(r"GC[AF]_\d{9}(\.\d+)?")

# label -> where the file is inside the genome's folder.
# Ensembl names its files the same way for every species, sorted into sub-folders.
# The .fai/.gzi/.csi files are indexes, not data: they are not listed.
# Ensembl has no CDS file, no feature table and no report files: those labels stay None.
ENSEMBL_FILES = {
    "genome_fasta": "genome/softmasked.fa.bgz",  # soft-masked, like NCBI's genome file
    "gff":          "geneset/genes.gff3.gz",
    "gtf":          "geneset/genes.gtf.gz",
    "rna":          "geneset/cdna.fa.bgz",
    "protein":      "geneset/pep.fa.bgz",
    "md5":          "genome/md5sum.txt",         # the one next to the genome sequence
}


def get_folder_info(accession):
    """Ask Ensembl's search for the full accession (with version), the folder link and the species.

    An assembly can have several annotations in Ensembl (e.g. one by Ensembl and one
    by another team), each in its own folder: Ensembl's own annotation is preferred.
    """
    params = {"query": accession, "per_page": 20}
    matches = fetch(SEARCH_URL, "genome information", "Ensembl", params=params).json().get("matches") or []

    # the search is free text: keep only the genomes with exactly this accession
    matches = [m for m in matches
               if m["assembly"]["accession_id"] == accession
               or m["assembly"]["accession_id"].startswith(accession + ".")]
    if not matches:
        raise LinkError(f"{accession} was not found on Ensembl")

    chosen = next((m for m in matches if m.get("annotation_provider") == "Ensembl"), matches[0])
    folder_url = chosen["ftp_url"].rstrip("/") + "/"
    return chosen["assembly"]["accession_id"], folder_url, chosen["scientific_name"]


def ensembl_links(accession, folder_url=None, species=None):
    """Return the full accession, the species and {label: link} for one Ensembl assembly.

    folder_url is optional: when it is already known (e.g. the ftp_url from the
    search results), Ensembl's search is not asked again, and the species is the one
    given (or None). A link is None when the file does not exist.

    Raises LinkError with a readable message when the links cannot be collected.
    """
    if not ACCESSION_FORMAT.fullmatch(accession):
        raise LinkError(f"{accession!r} is not an accession used by Ensembl (expected e.g. GCA_018350175.1)")

    if folder_url is None:
        accession, folder_url, species = get_folder_info(accession)

    # which sub-folders exist (genome/, geneset/...), then which files are in each
    page = fetch(folder_url, "list of sub-folders", "Ensembl").text
    subfolders = re.findall(r'href="([a-z_]+)/"', page)
    files = set()
    for sub in {path.split("/")[0] for path in ENSEMBL_FILES.values()}:
        if sub in subfolders:
            files.update(f"{sub}/{name}" for name in list_files(f"{folder_url}{sub}/", "Ensembl"))

    links = {label: None for label in LABELS}
    for label, path in ENSEMBL_FILES.items():
        if path in files:
            links[label] = folder_url + path
    return {"accession": accession, "species": species, "links": links}
