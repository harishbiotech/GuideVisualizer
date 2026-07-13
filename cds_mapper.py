"""
=========================================================
CDS / UTR Mapper
=========================================================

For a given transcript, finds where its CDS sequence sits
inside the full transcript sequence, and derives 5'UTR / CDS
/ 3'UTR coordinates from that.

IMPORTANT - this is intentionally defensive. Across ~5700
P. falciparum transcripts we expect several legitimate,
non-error outcomes:

  1. Normal case: CDS is a substring of the transcript with
     leftover sequence on one or both sides -> real 5'UTR
     and/or 3'UTR.

  2. CDS spans the entire transcript (start=1, end=transcript
     length) -> the gene genuinely has NO UTRs. This is a
     valid biological result, not a bug -- some P. falciparum
     transcripts have no annotated UTRs at all.

  3. No CDS record exists for this transcript ID in the CDS
     fasta at all (e.g. non-coding RNAs, certain pseudogenes).
     -> "no_cds_annotation".

  4. A CDS record exists, but it cannot be located as a clean
     substring of the transcript sequence. This does happen
     for a minority of genes (e.g. some var/PfEMP1 family
     genes show CDS-fasta lengths that don't reconcile with
     the transcript-fasta length for the same ID -- likely an
     annotation-version mismatch, similar in spirit to the
     CASowary 28nt/23nt sheet issue from the original MROP
     pipeline). -> "not_locatable".

Callers (the plotter) must handle all four outcomes without
crashing, and should render transcripts in case 3/4 as a
single plain bar with no CDS/UTR coloring, rather than
treating it as an error.

Harish Kumar R
=========================================================
"""

from utils import find_first_occurrence


# Outcome status constants
STATUS_OK = "ok"                          # case 1 or 2 (real or absent UTRs)
STATUS_NO_CDS = "no_cds_annotation"       # case 3
STATUS_NOT_LOCATABLE = "not_locatable"    # case 4


def map_utr_cds(transcript_seq, cds_seq):
    """
    Parameters
    ----------
    transcript_seq : str (cleaned, uppercase)
    cds_seq        : str or None (cleaned, uppercase)

    Returns
    -------
    dict with keys:
        status            : one of STATUS_OK / STATUS_NO_CDS /
                             STATUS_NOT_LOCATABLE
        transcript_length : int
        cds_start         : int or None (1-based, inclusive)
        cds_end           : int or None (1-based, inclusive)
        utr5_start        : int or None
        utr5_end          : int or None
        utr3_start        : int or None
        utr3_end          : int or None
        has_utr5          : bool
        has_utr3          : bool
    """

    transcript_length = len(transcript_seq)

    result = {
        "status": None,
        "transcript_length": transcript_length,
        "cds_start": None,
        "cds_end": None,
        "utr5_start": None,
        "utr5_end": None,
        "utr3_start": None,
        "utr3_end": None,
        "has_utr5": False,
        "has_utr3": False,
    }

    # ---- Case 3: no CDS annotation for this transcript at all ----

    if not cds_seq:
        result["status"] = STATUS_NO_CDS
        return result

    # ---- Try to locate the CDS within the transcript ----

    cds_start, cds_end = find_first_occurrence(transcript_seq, cds_seq)

    if cds_start is None:
        # Case 4: CDS exists but doesn't appear as a clean
        # substring of this transcript (annotation mismatch).
        result["status"] = STATUS_NOT_LOCATABLE
        return result

    # ---- Case 1 / 2: CDS located successfully ----

    result["status"] = STATUS_OK
    result["cds_start"] = cds_start
    result["cds_end"] = cds_end

    if cds_start > 1:
        result["utr5_start"] = 1
        result["utr5_end"] = cds_start - 1
        result["has_utr5"] = True

    if cds_end < transcript_length:
        result["utr3_start"] = cds_end + 1
        result["utr3_end"] = transcript_length
        result["has_utr3"] = True

    return result


# =========================================================
# Testing
# =========================================================

if __name__ == "__main__":

    from config import TRANSCRIPT_FASTA, CDS_FASTA
    from fasta_loader import FastaStore

    store = FastaStore(TRANSCRIPT_FASTA, CDS_FASTA)

    for test_id in ["PF3D7_0100100.1", "PF3D7_0100200.1", "PF3D7_0100300.1"]:

        transcript_seq = store.get_transcript_sequence(test_id)
        cds_seq = store.get_cds_sequence(test_id)

        if transcript_seq is None:
            print(f"{test_id}: transcript not found, skipping")
            continue

        mapping = map_utr_cds(transcript_seq, cds_seq)

        print(f"\n{test_id}")
        print(f"  status            : {mapping['status']}")
        print(f"  transcript_length : {mapping['transcript_length']}")
        print(f"  cds_start/end     : {mapping['cds_start']} / {mapping['cds_end']}")
        print(f"  has_utr5 / utr3   : {mapping['has_utr5']} / {mapping['has_utr3']}")
