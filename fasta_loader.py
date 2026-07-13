"""
=========================================================
FASTA Loader
=========================================================

Parses the combined, multi-record PlasmoDB fasta files for
transcripts and CDS sequences into simple lookup dicts keyed
by transcript ID.

PlasmoDB header format (confirmed from the actual files):

>PF3D7_0100100.1 | gene=PF3D7_0100100 | organism=... |
 gene_product=... | transcript_product=... |
 location=Pf3D7_01_v3:29510-37126(+) | length=6492 |
 sequence_SO=chromosome | SO=protein_coding_gene |
 is_pseudo=false

CDS headers use the same leading "<id> | ... |" layout but
without the gene_product/transcript_product/is_pseudo fields.
We only ever need the ID (text right after '>', before the
first space or '|'), so the parser does not depend on which
extra fields are present, or their order.

Author : Harish Kumar R
=========================================================
"""

from utils import clean_sequence, normalize_transcript_id


def _parse_fasta(path):
    """
    Generic multi-record FASTA parser.

    Returns a dict: { transcript_id : sequence (cleaned) }

    The transcript ID is taken as the first whitespace-
    delimited token after '>', which for every header we've
    seen is the bare PF3D7_XXXXXXX.N ID with no extra
    decoration -- so no regex stripping of prefixes is
    needed here (unlike the old MROP pipeline, which had to
    handle "transcript_"/"cds_" prefixed IDs from a different
    source workbook).
    """

    sequences = {}

    current_id = None
    current_chunks = []

    with open(path, "r") as handle:

        for line in handle:

            line = line.rstrip("\n")

            if line.startswith(">"):

                # Flush the previous record before starting a new one
                if current_id is not None:
                    sequences[current_id] = clean_sequence(
                        "".join(current_chunks)
                    )

                header = line[1:]  # drop '>'

                # ID is everything up to the first space or '|'
                raw_id = header.split()[0] if header.split() else ""

                current_id = normalize_transcript_id(raw_id)

                current_chunks = []

            else:

                current_chunks.append(line)

        # Flush the last record in the file
        if current_id is not None:
            sequences[current_id] = clean_sequence(
                "".join(current_chunks)
            )

    return sequences


class FastaStore:
    """
    Loads both the transcript fasta and the CDS fasta once,
    at app startup, and exposes simple dict-style lookups.

    Not every transcript will have a matching CDS entry (some
    are ncRNAs / pseudogenes with no annotated coding sequence)
    -- that is expected, not an error, and callers should treat
    a missing CDS lookup as "no CDS annotation" rather than a
    bug.
    """

    def __init__(self, transcript_fasta_path, cds_fasta_path):

        print("\nLoading transcript FASTA...")

        self.transcripts = _parse_fasta(transcript_fasta_path)

        print(f"{len(self.transcripts):,} transcript sequences loaded.")

        print("Loading CDS FASTA...")

        self.cds = _parse_fasta(cds_fasta_path)

        print(f"{len(self.cds):,} CDS sequences loaded.")

    # -----------------------------------------------------
    # Transcript lookups
    # -----------------------------------------------------

    def get_transcript_sequence(self, transcript_id):

        transcript_id = normalize_transcript_id(transcript_id)

        return self.transcripts.get(transcript_id)

    def get_all_transcript_ids(self):

        return sorted(self.transcripts.keys())

    def get_transcript_length(self, transcript_id):

        seq = self.get_transcript_sequence(transcript_id)

        return len(seq) if seq is not None else None

    # -----------------------------------------------------
    # CDS lookups
    # -----------------------------------------------------

    def get_cds_sequence(self, transcript_id):

        transcript_id = normalize_transcript_id(transcript_id)

        return self.cds.get(transcript_id)

    def has_cds(self, transcript_id):

        return self.get_cds_sequence(transcript_id) is not None


# =========================================================
# Testing
# =========================================================

if __name__ == "__main__":

    from config import TRANSCRIPT_FASTA, CDS_FASTA

    store = FastaStore(TRANSCRIPT_FASTA, CDS_FASTA)

    test_id = "PF3D7_0100100.1"

    print()
    print(f"Transcript length [{test_id}]:", store.get_transcript_length(test_id))
    print(f"Has CDS [{test_id}]:", store.has_cds(test_id))

    if store.has_cds(test_id):
        print(f"CDS length [{test_id}]:", len(store.get_cds_sequence(test_id)))
