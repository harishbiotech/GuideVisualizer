"""
=========================================================
Plotter
=========================================================

Builds the interactive Plotly figure:

  - A UTR/CDS background track along the transcript (grey /
    green / grey), when CDS mapping succeeded; a single plain
    grey bar when it didn't (see cds_mapper.py for why that's
    a valid, non-error outcome).
  - One lane-stack per tool above that, each guide drawn as a
    rectangle + an invisible wide marker for easy clicking and
    hover/copy.

Author : Harish Kumar R
=========================================================
"""

import plotly.graph_objects as go
from plotly.io import to_html

from config import TOOL_COLORS, UTR_CDS_COLORS, MAX_RENDERED_PER_TOOL
from cds_mapper import STATUS_OK, STATUS_NO_CDS, STATUS_NOT_LOCATABLE


class GuidePlotter:

    def __init__(self):
        pass

    # =====================================================
    # UTR / CDS background track
    # =====================================================

    def _build_utr_cds_track(self, utr_mapping, track_y):
        """
        Builds the UTR/CDS track as plain shape dicts + one
        hover-marker trace (rather than calling fig.add_shape()
        / fig.add_trace() directly -- see note in create_plot()
        on why that matters for performance).

        Returns (shapes, trace, note) where:
            shapes : list of shape dicts
            trace  : a single go.Scatter trace dict carrying all
                     hover markers for this track
            note   : str|None, UTR status note for the user
        """

        transcript_length = utr_mapping["transcript_length"]
        track_height = 0.5

        shapes = []
        xs, ys, hovertexts = [], [], []

        def queue_segment(x0, x1, color, label):
            shapes.append(dict(
                type="rect",
                x0=x0, x1=x1,
                y0=track_y - track_height / 2,
                y1=track_y + track_height / 2,
                fillcolor=color,
                line=dict(color="black", width=0.5),
                layer="below",
            ))
            xs.append((x0 + x1) / 2)
            ys.append(track_y)
            hovertexts.append(
                f"<b>{label}</b><br>{x0}-{x1} ({x1 - x0 + 1} nt)"
            )

        if utr_mapping["status"] in (STATUS_NO_CDS, STATUS_NOT_LOCATABLE):

            queue_segment(
                1, transcript_length,
                UTR_CDS_COLORS["undetermined"],
                "Transcript (UTR/CDS not determined)",
            )

            note = (
                "No CDS annotation found for this transcript"
                if utr_mapping["status"] == STATUS_NO_CDS
                else "CDS could not be located on this transcript "
                     "(possible annotation mismatch)"
            )

        else:

            note = None

            if utr_mapping["has_utr5"]:
                queue_segment(
                    utr_mapping["utr5_start"], utr_mapping["utr5_end"],
                    UTR_CDS_COLORS["5UTR"], "5' UTR",
                )

            queue_segment(
                utr_mapping["cds_start"], utr_mapping["cds_end"],
                UTR_CDS_COLORS["CDS"], "CDS",
            )

            if utr_mapping["has_utr3"]:
                queue_segment(
                    utr_mapping["utr3_start"], utr_mapping["utr3_end"],
                    UTR_CDS_COLORS["3UTR"], "3' UTR",
                )

            if not utr_mapping["has_utr5"] and not utr_mapping["has_utr3"]:
                note = "CDS spans the entire transcript -- no UTRs annotated"

        trace = go.Scatter(
            x=xs, y=ys,
            mode="markers",
            marker=dict(size=10, color="rgba(0,0,0,0)"),
            showlegend=False,
            hovertext=hovertexts,
            hoverinfo="text",
        )

        return shapes, trace, note

    # =====================================================
    # Create transcript + guides + UTR/CDS plot
    # =====================================================

    def create_plot(self, transcript_id, transcript_length, guides_by_tool, utr_mapping):
        """
        Parameters
        ----------
        transcript_id    : str
        transcript_length : int
        guides_by_tool   : dict { tool_name : DataFrame } -- each
                           DataFrame already filtered to the
                           selected Top-N for that tool, with
                           columns Tool/Guide/Start/End/
                           Guide_Length/Score/Normalized_Score
        utr_mapping      : dict, output of cds_mapper.map_utr_cds()

        Returns
        -------
        (plotly.graph_objects.Figure, dict zoom_bounds, str|None utr_note)

        PERFORMANCE NOTE: this function deliberately avoids calling
        fig.add_shape() / fig.add_trace() inside a loop. Each call
        to add_shape() re-validates and deep-copies the entire
        existing shapes list, making a loop of N add_shape() calls
        O(N^2) overall -- for a few hundred guides this alone took
        upward of 10 seconds. Instead, every shape is built as a
        plain dict and assigned ONCE to fig.layout.shapes at the
        end; every guide's hover/click marker for a given tool is
        batched into a single go.Scatter trace using parallel
        arrays (x, y, customdata, hovertext) rather than one trace
        per guide. Both changes are large constant-factor wins and
        don't change anything about what's visually rendered.
        """

        all_shapes = []
        all_traces = []

        # ---- UTR/CDS track sits at the bottom, just above y=0 ----

        utr_track_y = 0.6

        utr_shapes, utr_trace, utr_note = self._build_utr_cds_track(
            utr_mapping, utr_track_y
        )

        all_shapes.extend(utr_shapes)
        all_traces.append(utr_trace)

        # Transcript backbone line
        backbone_y = 1.6

        all_shapes.append(dict(
            type="line",
            x0=1, y0=backbone_y,
            x1=transcript_length, y1=backbone_y,
            line=dict(color="black", width=2),
        ))

        # ---- Guide lanes per tool (lane-stacking logic preserved) ----

        cursor = backbone_y + 1.0
        lane_height = 0.8

        all_guide_starts = []
        all_guide_ends = []

        tool_order = [
            tool for tool in guides_by_tool
            if not guides_by_tool[tool].empty
        ]

        # Track which tools got truncated for rendering, so the
        # caller can tell the user "showing 300 of 5,311" instead
        # of silently dropping guides. This is a RENDERING cap only
        # -- it does not change ranking; guides_by_tool is already
        # sorted by score (best first) by apply_top_n(), so capping
        # here keeps the highest-scoring guides on screen.
        truncated_counts = {}

        for tool in tool_order:

            mapped_df = guides_by_tool[tool]

            original_count = len(mapped_df)

            if MAX_RENDERED_PER_TOOL is not None and original_count > MAX_RENDERED_PER_TOOL:
                mapped_df = mapped_df.head(MAX_RENDERED_PER_TOOL)
                truncated_counts[tool] = original_count

            color = TOOL_COLORS.get(tool, "#888888")

            starts = mapped_df["Start"].tolist()
            ends = mapped_df["End"].tolist()
            guides_seq = mapped_df["Guide"].tolist()
            scores = mapped_df["Score"].tolist()
            normalized_scores = mapped_df["Normalized_Score"].tolist()

            # Stack guides into lanes so overlapping guides from the
            # same tool don't sit on top of each other. (Greedy
            # lane assignment over plain Python lists rather than
            # DataFrame .iterrows(), which is itself noticeably
            # faster at this scale.)
            lane_end = {}
            guide_lane = []

            for start, end in zip(starts, ends):

                placed_lane = None

                for lane, end_pos in lane_end.items():
                    if start >= end_pos:
                        placed_lane = lane
                        break

                if placed_lane is None:
                    placed_lane = len(lane_end)

                lane_end[placed_lane] = end
                guide_lane.append(placed_lane)

            n_lanes = max(guide_lane) + 1
            tool_base_y = cursor

            marker_x, marker_y, customdata, hovertexts = [], [], [], []

            for start, end, guide_seq, score, norm_score, lane in zip(
                starts, ends, guides_seq, scores, normalized_scores, guide_lane
            ):

                y_center = tool_base_y + lane * lane_height

                all_guide_starts.append(start)
                all_guide_ends.append(end)

                all_shapes.append(dict(
                    type="rect",
                    x0=start, x1=end,
                    y0=y_center - 0.3, y1=y_center + 0.3,
                    fillcolor=color,
                    line=dict(color="black", width=1),
                ))

                # `value == value` is False only for NaN -- used
                # instead of pd.isna() here since these are plain
                # Python floats at this point, not a Series.
                score_display = (
                    f"{score:.4f}" if score is not None and score == score
                    else "N/A"
                )
                norm_score_display = (
                    f"{norm_score:.4f}" if norm_score is not None and norm_score == norm_score
                    else "N/A"
                )

                marker_x.append((start + end) / 2)
                marker_y.append(y_center)
                customdata.append([
                    guide_seq, tool, start, end, score_display, norm_score_display
                ])
                hovertexts.append(
                    f"<b>{tool}</b><br>"
                    f"Guide : {guide_seq}<br>"
                    f"Actual Score : {score_display}<br>"
                    f"Normalized Score : {norm_score_display}<br>"
                    f"Start : {start}<br>"
                    f"End : {end}<br>"
                    "<i>Click to copy sequence</i>"
                )

            # One trace per tool carries every guide's hover marker
            # (instead of one trace per guide).
            all_traces.append(go.Scatter(
                x=marker_x, y=marker_y,
                mode="markers",
                marker=dict(size=16, color="rgba(0,0,0,0)"),
                showlegend=False,
                customdata=customdata,
                hovertext=hovertexts,
                hoverinfo="text",
            ))

            cursor += n_lanes * lane_height + 0.6

        # ---- Legend entries (one dummy trace per tool) ----

        for tool in tool_order:
            all_traces.append(go.Scatter(
                x=[None], y=[None],
                mode="markers",
                marker=dict(size=10, color=TOOL_COLORS.get(tool, "#888888")),
                name=tool,
                showlegend=True,
            ))

        y_top = cursor + 1

        # Cap the rendered height. Without this, a tool with many
        # lanes (heavily overlapping guides) could push y_top high
        # enough to ask the browser to render an extremely tall
        # SVG, which is slow independent of the shape-count cap
        # above.
        plot_height = min(2500, max(500, int(y_top * 40)))

        # ---- Build the figure: traces via the constructor (cheap,
        # one-shot), shapes via direct layout assignment (avoids the
        # O(n^2) add_shape() trap entirely) ----

        fig = go.Figure(data=all_traces)

        fig.update_layout(
            title=f"{transcript_id}",
            xaxis=dict(
                title="Transcript Position (nt)",
                range=[0, transcript_length + 20],
                showgrid=True,
                zeroline=False,
            ),
            yaxis=dict(visible=False, range=[-0.5, y_top]),
            height=plot_height,
            template="plotly_white",
            margin=dict(t=60, b=40),
            shapes=all_shapes,
        )

        # ---- Zoom bounds for the Full Transcript / Zoom to Guides buttons ----

        full_range = [0, transcript_length + 20]

        if all_guide_starts and all_guide_ends:
            margin = max(20, int((max(all_guide_ends) - min(all_guide_starts)) * 0.05))
            guide_range = [
                max(0, min(all_guide_starts) - margin),
                min(transcript_length + 20, max(all_guide_ends) + margin),
            ]
        else:
            guide_range = full_range

        zoom_bounds = {
            "full_range": full_range,
            "guide_range": guide_range,
        }

        # ---- Build a combined note (UTR status + truncation), so
        # the frontend only has to display one note field ----

        notes = []

        if utr_note:
            notes.append(utr_note)

        if truncated_counts:
            parts = [
                f"{tool}: showing top {MAX_RENDERED_PER_TOOL} of {count:,}"
                for tool, count in truncated_counts.items()
            ]
            notes.append(
                "Too many guides to render all at once -- "
                + "; ".join(parts)
                + ". Lower Top-N to see a different slice, or narrow "
                  "by score."
            )

        combined_note = " | ".join(notes) if notes else None

        return fig, zoom_bounds, combined_note

    # =====================================================
    # Convert Plotly Figure to HTML
    # =====================================================

    def figure_to_html(self, fig):
        return to_html(
            fig,
            full_html=False,
            include_plotlyjs="cdn",
        )