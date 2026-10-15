"""What all the databases share: the labels, the error type, and reading web pages."""

import re
import time

import requests

TIMEOUT = 30   # seconds to wait for a database before giving up
ATTEMPTS = 3   # how many times to try a request before giving up
RETRY_CODES = {429, 500, 502, 503, 504}  # "too many requests" and server errors: worth trying again

# The labels every database uses in its results, in this order.
# A database that never has a kind of file just leaves it as None.
LABELS = [
    "genome_fasta", "gff", "gtf", "cds", "rna", "protein", "feature_table",
    "assembly_report", "assembly_stats", "annotation_report", "md5",
]


class LinkError(Exception):
    """A problem getting the links of one assembly, with a message a user can understand."""


def fetch(url, what, source, params=None):
    """GET a page; turn network and server problems into a clear LinkError.

    Temporary problems (dropped connection, no answer, server overloaded) are
    retried a few times before giving up, since some servers (GWH) drop
    connections now and then.

    what: what we are getting (used in messages), e.g. "list of files".
    source: the database name (used in messages), e.g. "NCBI".
    """
    for attempt in range(1, ATTEMPTS + 1):
        try:
            response = requests.get(url, params=params, timeout=TIMEOUT)
        except requests.Timeout:
            problem = f"{source} did not answer within {TIMEOUT}s while getting the {what}"
        except requests.ConnectionError:
            problem = f"could not connect to {source} to get the {what} (check the internet connection)"
        else:
            if response.ok:
                return response
            problem = f"{source} answered with error {response.status_code} while getting the {what}"
            if response.status_code not in RETRY_CODES:
                break  # e.g. 404 (not found): trying again would not help
        if attempt < ATTEMPTS:
            time.sleep(2 * attempt)  # wait 2s, then 4s... before trying again
    raise LinkError(problem)


def list_files(folder_url, source):
    """Read a folder page and return the file names it contains (sub-folders are skipped)."""
    page = fetch(folder_url, "list of files", source).text
    return re.findall(r'href="([^"/?]+)"', page)
