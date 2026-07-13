"""
=========================================================
Cas13 Guide RNA Visualizer 2.0
=========================================================

Flask Application

Author : Harish Kumar R
=========================================================
"""

import pandas as pd

from flask import Flask
from flask import jsonify
from flask import request
from flask import render_template

from config import (
    TRANSCRIPT_FASTA,
    CDS_FASTA,
    TOOL_FOLDERS,
    TOOL_COLUMNS,
    DEFAULT_TOP_N,
    MAX_TOP_N,
    HOST,
    PORT,
    DEBUG,
)

from fasta_loader import FastaStore
from guide_index import GuideIndex
from guide_loader import load_guides_for_transcript, apply_top_n
from cds_mapper import map_utr_cds
from plotter import GuidePlotter


# =====================================================
# Flask App
# =====================================================

app = Flask(__name__)


# =====================================================
# Load Data (Only Once, at startup)
# =====================================================

print("\nInitializing Guide Visualizer 2.0...\n")

fasta_store = FastaStore(TRANSCRIPT_FASTA, CDS_FASTA)

guide_index = GuideIndex(TOOL_FOLDERS)

plotter = GuidePlotter()

print("\nGuide Visualizer 2.0 Ready.\n")


# =====================================================
# Home Page
# =====================================================

@app.route("/")
def home():

    return render_template(
        "guide_position.html",
        tools=list(TOOL_FOLDERS.keys()),
        default_top_n=DEFAULT_TOP_N,
        max_top_n=MAX_TOP_N,
    )


# =====================================================
# Return All Transcript IDs
# =====================================================
# Source of truth is the transcript FASTA (the authoritative
# list of real P. falciparum transcripts), not the union of
# guide-prediction filenames -- a transcript might be missing
# guide predictions for one or more tools without that meaning
# it isn't a real transcript.

@app.route("/api/transcripts")
def transcript_ids():

    return jsonify(

        fasta_store.get_all_transcript_ids()

    )


# =====================================================
# Visualize
# =====================================================

@app.route("/api/visualize", methods=["POST"])
def visualize():

    data = request.get_json()

    transcript_id = data.get("transcript")

    tools = data.get("tools", [])

    top_n_settings = data.get("top_n", {})   # { tool: int }
    show_all_settings = data.get("show_all", {})  # { tool: bool }

    transcript_seq = fasta_store.get_transcript_sequence(transcript_id)

    if transcript_seq is None:
        return jsonify({
            "status": "error",
            "message": f"Transcript '{transcript_id}' not found."
        }), 400

    transcript_length = len(transcript_seq)

    # ---- UTR/CDS mapping ----

    cds_seq = fasta_store.get_cds_sequence(transcript_id)

    utr_mapping = map_utr_cds(transcript_seq, cds_seq)

    # ---- Load + rank guides per selected tool ----

    guides_by_tool = {}

    for tool in tools:

        if tool not in TOOL_COLUMNS:
            continue

        filepath = guide_index.get_filepath(tool, transcript_id)

        if filepath is None:
            guides_by_tool[tool] = pd.DataFrame()
            continue

        raw_guides = load_guides_for_transcript(
            tool, filepath, transcript_seq
        )

        top_n = int(top_n_settings.get(tool, DEFAULT_TOP_N.get(tool, 20)))
        show_all = bool(show_all_settings.get(tool, False))

        guides_by_tool[tool] = apply_top_n(
            raw_guides, tool, top_n, show_all
        )

    total_guides = sum(len(df) for df in guides_by_tool.values())

    print(f"\nVisualizing {transcript_id}: {total_guides} guides plotted")

    fig, zoom_bounds, utr_note = plotter.create_plot(
        transcript_id,
        transcript_length,
        guides_by_tool,
        utr_mapping,
    )

    plot_html = plotter.figure_to_html(fig)

    return jsonify({
        "status": "success",
        "plot": plot_html,
        "zoom_bounds": zoom_bounds,
        "utr_status": utr_mapping["status"],
        "utr_note": utr_note,
        "transcript_length": transcript_length,
        "guide_counts": {
            tool: len(df) for tool, df in guides_by_tool.items()
        },
    })


# =====================================================
# Run Server
# =====================================================

if __name__ == "__main__":

    app.run(
        debug=DEBUG,
        host=HOST,
        port=PORT,
    )