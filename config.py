import os

# ----------------------------
# Base directories
# ----------------------------

# This file's directory (Guide_visualizer2.0/)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

APP_DIR = BASE_DIR

DATA_DIR = os.getenv("GUIDEVIS_DATA", "/data")

# ----------------------------
# FASTA inputs (combined, multi-record PlasmoDB dumps)
# ----------------------------

INPUT_DIR = os.path.join(DATA_DIR, "input")

TRANSCRIPT_FASTA = os.path.join(
    INPUT_DIR,
    "PlasmoDB-68_Pfalciparum3D7_AnnotatedTranscripts.fasta"
)

CDS_FASTA = os.path.join(
    INPUT_DIR,
    "PlasmoDB-68_Pfalciparum3D7_AnnotatedCDSs.fasta"
)

# ----------------------------
# Per-tool guide prediction folders
# ----------------------------
# Each folder contains one CSV per transcript, named
# "<transcript_id>.csv" (e.g. "PF3D7_0100100.1.csv").

RESULTS_DIR = os.path.join(DATA_DIR, "Results")

TOOL_FOLDERS = {

    "TIGER": os.path.join(RESULTS_DIR, "tiger_result"),

    "DeepCas13": os.path.join(RESULTS_DIR, "Deepcas13_result"),

    "CASowary": os.path.join(RESULTS_DIR, "CASowary_result"),

    "Cas13design": os.path.join(RESULTS_DIR, "Cas13_result"),

}


TOOL_COLUMNS = {

    "TIGER": {
        "seq_col": "Guide Sequence",
        "target_col": "Target Sequence",
        "position_mode": "target_seq",
        "score_col": "Guide Score",
        "higher_is_better": True,
        "normalize_method": "minmax_per_transcript",
        "normalized_score_col": None,
    },

    "DeepCas13": {
        "seq_col": "seq",
        "target_col": None,
        "position_mode": "revcomp_guide",
        "score_col": "deepscore",
        "higher_is_better": True,
        "normalize_method": "minmax_per_transcript",
        "normalized_score_col": None,
    },

    "CASowary": {
        "seq_col": "Guide Sequence",
        "target_col": None,
        "position_mode": "revcomp_guide",
        "score_col": "Model Prediction",
        "higher_is_better": False,   # class 0 = best, see note above
        "normalize_method": "casowary_class_invert",
        "normalized_score_col": None,
    },

    "Cas13design": {
        "seq_col": "GuideSeq",
        "target_col": None,
        "position_mode": "guide_name",
        "name_col": "GuideName",
        "matchpos_col": "MatchPos",
        "score_col": "GuideScores",
        "higher_is_better": True,
        "normalize_method": "existing_column",
        "normalized_score_col": "standardizedGuideScores",
    },

}

# ----------------------------
# Colors (tool tracks + UTR/CDS track)
# ----------------------------

TOOL_COLORS = {

    "TIGER": "#1f77b4",

    "DeepCas13": "#2ca02c",

    "CASowary": "#ff7f0e",

    "Cas13design": "#d62728",

}

UTR_CDS_COLORS = {

    "5UTR": "#b0b0b0",

    "CDS": "#6fae6f",

    "3UTR": "#b0b0b0",

    "undetermined": "#e0e0e0",

}

# ----------------------------
# Default Top-N per tool (independent sliders in the UI)
# ----------------------------

DEFAULT_TOP_N = {

    "TIGER": 20,

    "DeepCas13": 20,

    "CASowary": 20,

    "Cas13design": 20,

}

MAX_TOP_N = 5000   # slider ceiling; "show all" is handled as a checkbox in the UI

MAX_RENDERED_PER_TOOL = 10000

# ----------------------------
# Flask
# ----------------------------

HOST = "0.0.0.0"

PORT = 5001

DEBUG = False

# ----------------------------
# Per-tool column layout
# ----------------------------
# "seq_col"     : column holding the guide sequence itself
# "position_mode":
#     "target_seq"   -> a column already holds the transcript-
#                        strand target site; search that directly
#     "revcomp_guide" -> reverse-complement the guide sequence,
#                        then search that in the transcript
#     "guide_name"   -> parse start/end directly out of a name
#                        column (no searching needed)
# "score_col"   : column to rank guides by
# "higher_is_better": scoring direction (see README notes below)
#
# ---------------------------------------------------------
# Scoring direction notes (verified against tool papers):
#
# TIGER        - Guide Score, 0-1, higher = more knockdown.
#                Source: TIGER online tool documentation.
#
# Cas13design  - GuideScores (raw) / quartiles (1-4), higher
#                score and higher quartile (Q4) = more active,
#                on-target guide.
#                Source: Cas13 Design webtool paper (bioRxiv).
#
# CASowary     - Model Prediction is a CLASS LABEL (0-3), not
#                a typical score. Class 0 = guides expected to
#                leave 0-25% residual transcript expression
#                (= highest knockdown = BEST). Class 3 = 75-100%
#                residual expression (= worst). i.e. LOWER class
#                number is better -- the opposite of what the
#                column name suggests at a glance.
#                Source: CASowary paper (Bisht et al., BMC
#                Genomics 2022) - confirmed against Harish's own
#                benchmarking observations.
#
# DeepCas13    - "deepscore" / "Deep Score", 0-1. Higher score
#                correlates with stronger knockdown (more
#                negative log-fold-change). Confirmed directly
#                from the DeepCas13 paper (Cheng et al., Nature
#                Communications 2023): guides with the highest
#                Deep Scores showed better knockdown in qRT-PCR
#                validation.
# ---------------------------------------------------------
#
# ---------------------------------------------------------
# Normalized score notes:
#
# A "normalized score" is always reported on a 0-1 scale where
# HIGHER = BETTER, regardless of the tool's raw scoring direction
# -- this keeps the normalized column directly comparable across
# all four tools at a glance, even though their raw/actual score
# columns are not on comparable scales (and, for CASowary, are
# not even oriented the same way).
#
# Cas13design  - the CSV already ships a standardizedGuideScores
#                column from the tool's own authors; used as-is
#                rather than recomputed, per Harish's preference.
#
# TIGER,
# DeepCas13    - no existing normalized column; computed as
#                per-transcript min-max normalization of the raw
#                score: (score - min) / (max - min) among the
#                guides present for that transcript. The best
#                guide ON THIS TRANSCRIPT becomes 1.0, the worst
#                becomes 0.0. (Per-transcript, not genome-wide --
#                this is fast/instant and matches what Harish
#                asked for; it does mean a 0.8 on one transcript
#                isn't directly comparable to a 0.8 on another,
#                only within a transcript.)
#
# CASowary     - no existing normalized column, and the raw score
#                is an inverted class label. Computed as
#                1 - (class / 3), so class 0 (best) -> 1.0 and
#                class 3 (worst) -> 0.0, putting it on the same
#                higher-is-better 0-1 scale as the others. This
#                does NOT change the raw/actual score shown
#                alongside it, which still displays the true
#                class number for verification against source data.
# ---------------------------------------------------------