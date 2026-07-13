"""
=========================================================
Guide Loader
=========================================================

Reads a single tool's per-transcript CSV (on demand, not at
startup) and resolves each guide's Start/End position on the
transcript sequence, using whichever strategy that tool's
data supports:

  "target_seq"    (TIGER)       - the CSV already contains
                                   the transcript-strand
                                   target sequence; search
                                   that directly.

  "revcomp_guide" (DeepCas13,
                    CASowary)    - reverse-complement the
                                   guide sequence, then search
                                   that in the transcript.

  "guide_name"    (Cas13design) - position comes directly
                                   from MatchPos (confirmed,
                                   by checking sample rows, to
                                   be the END position of the
                                   guide on the transcript) --
                                   no sequence search needed.

Author : Harish Kumar R
=========================================================
"""

import pandas as pd

from config import TOOL_COLUMNS
from utils import (
    clean_sequence,
    reverse_complement,
    find_first_occurrence,
    guide_length,
)


# =========================================================
# In-memory cache for resolved guides
# =========================================================
# Keyed by (tool, filepath). Holds the fully position-resolved
# DataFrame for that tool/transcript -- i.e. the expensive part
# (reading the CSV and, for TIGER/DeepCas13/CASowary, searching
# for each guide's binding site in the transcript sequence).
#
# Ranking (apply_top_n) is NOT cached here on purpose: it's cheap
# (just a sort + head), and caching it per Top-N/show-all value
# would multiply cache entries for no real benefit. Re-clicking
# the same transcript with a different Top-N, or clicking Full
# Transcript / Zoom to Guides, no longer re-reads or re-searches
# the CSV at all -- only the first visualize of a given transcript
# pays that cost; everything after reuses this cache for the
# lifetime of the running app.
#
# This is a plain dict with no eviction. For ~5,700 transcripts x
# 4 tools this is bounded and comfortably fits in memory even if
# every transcript in the dataset eventually gets visualized in
# one session; restart the app to clear it if that's ever a
# concern.
_resolved_guides_cache = {}


def _resolve_position(row, mode, cols, transcript_seq):
    """
    Returns (start, end, guide_seq) for a single row, or
    (None, None, guide_seq) if the position could not be
    resolved (e.g. guide not found in transcript -- this can
    legitimately happen, e.g. for guides affected by the
    known CASowary AT-rich / cross-version mapping issue
    documented in the original MROP pipeline).
    """

    guide_seq = clean_sequence(row.get(cols["seq_col"]))

    if mode == "target_seq":

        target_seq = clean_sequence(row.get(cols["target_col"]))

        start, end = find_first_occurrence(transcript_seq, target_seq)

        return start, end, guide_seq

    if mode == "revcomp_guide":

        target_seq = reverse_complement(guide_seq)

        start, end = find_first_occurrence(transcript_seq, target_seq)

        return start, end, guide_seq

    if mode == "guide_name":

        matchpos = row.get(cols["matchpos_col"])

        if pd.isna(matchpos):
            return None, None, guide_seq

        end = int(matchpos)

        start = end - guide_length(guide_seq) + 1

        return start, end, guide_seq

    raise ValueError(f"Unknown position_mode: {mode}")


def _compute_normalized_scores(df, tool):
    """
    Adds a 'Normalized_Score' column to df (in place is avoided --
    returns a new column array) on a 0-1, higher-is-better scale,
    using whichever method config.py specifies for this tool. See
    the "Normalized score notes" block in config.py for the
    reasoning behind each method.
    """

    method = TOOL_COLUMNS[tool]["normalize_method"]

    if df.empty:
        return pd.Series(dtype="float64")

    if method == "existing_column":

        col = TOOL_COLUMNS[tool]["normalized_score_col"]

        # The existing column lives in the raw CSV, not in our
        # resolved records -- it gets attached by the caller
        # (load_guides_for_transcript) by re-reading it alongside
        # Score, so by the time we get here it's already present
        # as df["_raw_normalized"].
        return pd.to_numeric(df["_raw_normalized"], errors="coerce")

    if method == "minmax_per_transcript":

        scores = pd.to_numeric(df["Score"], errors="coerce")

        score_min = scores.min()
        score_max = scores.max()

        if pd.isna(score_min) or pd.isna(score_max) or score_max == score_min:
            # All guides tied (or all NaN) -- nothing meaningful to
            # spread across 0-1; treat every valid score as equally
            # "best" rather than dividing by zero.
            return scores.apply(lambda v: 1.0 if pd.notna(v) else float("nan"))

        return (scores - score_min) / (score_max - score_min)

    if method == "casowary_class_invert":

        classes = pd.to_numeric(df["Score"], errors="coerce")

        # Class 0 (best) -> 1.0, Class 3 (worst) -> 0.0
        return 1.0 - (classes / 3.0)

    raise ValueError(f"Unknown normalize_method: {method}")


def load_guides_for_transcript(tool, filepath, transcript_seq):
    """
    Parameters
    ----------
    tool            : str, e.g. "TIGER"
    filepath        : str, path to that tool's CSV for one transcript
    transcript_seq   : str, the cleaned transcript sequence (needed
                       to resolve Start/End for tools that require
                       a sequence search)

    Returns
    -------
    pandas.DataFrame with columns:
        Tool, Guide, Start, End, Guide_Length, Score, Normalized_Score
    Score is the tool's raw/actual score column value, unchanged
    from the source CSV (for CASowary this is the raw class number,
    0-3). Normalized_Score is always on a 0-1, higher-is-better
    scale regardless of tool -- see config.py for exactly how each
    tool's normalization is computed.

    Rows where the position could not be resolved are dropped
    (with a count printed to the console for visibility, since
    silently losing rows should never be invisible).

    Cached by (tool, filepath) -- repeat calls for the same
    tool/transcript combination return instantly instead of
    re-reading the CSV and re-running position searches.
    """

    cache_key = (tool, filepath)

    if cache_key in _resolved_guides_cache:
        return _resolved_guides_cache[cache_key]

    cols = TOOL_COLUMNS[tool]

    df = pd.read_csv(filepath)

    needs_existing_normalized_col = (
        cols["normalize_method"] == "existing_column"
    )
    normalized_col_name = cols.get("normalized_score_col")

    records = []
    unresolved = 0

    for _, row in df.iterrows():

        start, end, guide_seq = _resolve_position(
            row,
            cols["position_mode"],
            cols,
            transcript_seq,
        )

        if start is None or end is None:
            unresolved += 1
            continue

        score = row.get(cols["score_col"])

        record = {
            "Tool": tool,
            "Guide": guide_seq,
            "Start": start,
            "End": end,
            "Guide_Length": len(guide_seq),
            "Score": score,
        }

        if needs_existing_normalized_col:
            record["_raw_normalized"] = row.get(normalized_col_name)

        records.append(record)

    if unresolved:
        print(
            f"  [{tool}] {unresolved} of {len(df)} guides could not be "
            f"positioned on the transcript and were skipped."
        )

    result = pd.DataFrame(records)

    result["Normalized_Score"] = _compute_normalized_scores(result, tool)

    # Drop the scratch column used only to carry the existing
    # normalized column through position resolution -- callers
    # should only ever see Normalized_Score, not the raw column
    # name, so the rest of the app stays tool-agnostic.
    if "_raw_normalized" in result.columns:
        result = result.drop(columns=["_raw_normalized"])

    _resolved_guides_cache[cache_key] = result

    return result


def apply_top_n(guides_df, tool, top_n, show_all=False):
    """
    Sorts guides_df by that tool's score column (respecting
    its higher_is_better direction) and keeps only the top N.

    If show_all is True, top_n is ignored and every guide is
    returned (still sorted, for consistent hover/lane order).
    """

    if guides_df.empty:
        return guides_df

    higher_is_better = TOOL_COLUMNS[tool]["higher_is_better"]

    sorted_df = guides_df.sort_values(
        by="Score",
        ascending=not higher_is_better,
        na_position="last",
    )

    if show_all:
        return sorted_df.reset_index(drop=True)

    return sorted_df.head(top_n).reset_index(drop=True)


# =========================================================
# Testing
# =========================================================

if __name__ == "__main__":

    from config import TOOL_FOLDERS, TRANSCRIPT_FASTA, CDS_FASTA
    from fasta_loader import FastaStore
    from guide_index import GuideIndex

    store = FastaStore(TRANSCRIPT_FASTA, CDS_FASTA)
    index = GuideIndex(TOOL_FOLDERS)

    test_id = "PF3D7_0100100.1"
    transcript_seq = store.get_transcript_sequence(test_id)

    for tool in TOOL_FOLDERS:

        filepath = index.get_filepath(tool, test_id)

        if filepath is None:
            print(f"{tool}: no file for {test_id}")
            continue

        guides = load_guides_for_transcript(tool, filepath, transcript_seq)

        top = apply_top_n(guides, tool, top_n=5)

        print(f"\n{tool}: {len(guides)} guides resolved, showing top 5 by score")
        print(top[["Guide", "Start", "End", "Score", "Normalized_Score"]])