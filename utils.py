"""
=========================================================
Guide Visualizer 2.0 - Utility Functions
=========================================================

Author : Harish Kumar R
=========================================================
"""

import re
from Bio.Seq import Seq


# ==========================================================
# Clean Sequence
# ==========================================================

def clean_sequence(sequence):
    """
    Uppercase, strip whitespace/newlines, and keep only
    valid nucleotide characters.
    """

    if sequence is None:
        return ""

    sequence = str(sequence).upper()

    sequence = re.sub(r"\s+", "", sequence)

    sequence = re.sub(r"[^ATGCU]", "", sequence)

    return sequence


# ==========================================================
# Reverse Complement
# ==========================================================

def reverse_complement(sequence):
    """
    Reverse complement using Biopython. Any 'U' is treated
    as 'T' for complementing purposes since guide sequences
    in these CSVs are written using DNA letters.
    """

    sequence = clean_sequence(sequence).replace("U", "T")

    return str(
        Seq(sequence).reverse_complement()
    )


# ==========================================================
# Find All Occurrences (1-based positions)
# ==========================================================

def find_all_occurrences(sequence, target):
    """
    Return every 1-based start position where `target`
    occurs as a substring of `sequence`.
    """

    sequence = clean_sequence(sequence)
    target = clean_sequence(target)

    if not target:
        return []

    positions = []

    start = 0

    while True:

        pos = sequence.find(target, start)

        if pos == -1:
            break

        positions.append(pos + 1)

        start = pos + 1

    return positions


# ==========================================================
# Find First Occurrence (1-based start, end)
# ==========================================================

def find_first_occurrence(sequence, target):
    """
    Convenience wrapper: returns (start, end) 1-based, or
    (None, None) if target is not found in sequence.
    """

    positions = find_all_occurrences(sequence, target)

    if not positions:
        return None, None

    start = positions[0]

    end = start + len(clean_sequence(target)) - 1

    return start, end


# ==========================================================
# Guide Length
# ==========================================================

def guide_length(guide):
    return len(clean_sequence(guide))


# ==========================================================
# Normalize Transcript ID
# ==========================================================
# PlasmoDB transcript IDs in this dataset are already in the
# canonical "PF3D7_XXXXXXX.N" form. This function defends
# against stray whitespace / case differences only, so the
# same lookup keys are used everywhere (fasta headers, CSV
# filenames, dropdown values).

def normalize_transcript_id(transcript_id):

    if transcript_id is None:
        return None

    transcript_id = str(transcript_id).strip()

    if transcript_id == "":
        return None

    return transcript_id
