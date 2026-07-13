document.addEventListener("DOMContentLoaded", function () {

    initTranscriptDropdown();

});


// Stores the zoom bounds returned by the last successful
// /api/visualize call, so the Full Transcript / Zoom to
// Guides buttons can use them without another server call.
let currentZoomBounds = null;

// Choices.js instance for the searchable transcript dropdown
let transcriptChoices = null;


// =====================================================
// Find the Plotly chart div that was just injected.
//
// Plotly assigns each chart a random UUID as its div id
// (e.g. id="b9fa2ca9-a053-..."), so the frontend can't
// hardcode that id. Instead we look it up by the class
// Plotly always assigns: "plotly-graph-div". Since this
// app only ever shows one chart at a time, the first match
// inside the plot container is the one we want.
// =====================================================

function getPlotlyDiv() {

    const container = document.getElementById("plot");

    return container.querySelector(".plotly-graph-div");

}


// =====================================================
// Inject HTML that contains <script> tags.
//
// (Carried over unchanged from the v1 build -- innerHTML
// does not execute injected <script> tags, so each one has
// to be manually recreated and re-appended for Plotly's
// own embedded script to actually run.)
// =====================================================

function injectHtmlWithScripts(container, html) {

    container.innerHTML = html;

    const oldScripts = Array.from(
        container.querySelectorAll("script")
    );

    oldScripts.forEach(function (oldScript) {
        oldScript.remove();
    });

    function runScriptsInOrder(index) {

        if (index >= oldScripts.length) {
            return;
        }

        const oldScript = oldScripts[index];
        const newScript = document.createElement("script");

        if (oldScript.src) {

            newScript.src = oldScript.src;

            newScript.onload = function () {
                runScriptsInOrder(index + 1);
            };

            newScript.onerror = function () {
                console.error(
                    "Failed to load script:", oldScript.src
                );
                runScriptsInOrder(index + 1);
            };

            container.appendChild(newScript);

        } else {

            newScript.textContent = oldScript.textContent;

            container.appendChild(newScript);

            runScriptsInOrder(index + 1);

        }

    }

    runScriptsInOrder(0);

}


// =====================================================
// Transcript Dropdown (searchable via Choices.js)
// =====================================================

async function initTranscriptDropdown() {

    const response = await fetch("/api/transcripts");

    const transcripts = await response.json();

    const dropdown = document.getElementById("transcript");

    dropdown.innerHTML = "";

    transcripts.forEach(function (gene) {

        const option = document.createElement("option");

        option.value = gene;

        option.text = gene;

        dropdown.appendChild(option);

    });

    // Choices.js turns the plain <select> into a searchable,
    // type-ahead dropdown with keyboard navigation. searchEnabled
    // + searchResultLimit keep it responsive even with thousands
    // of transcripts in the list.
    transcriptChoices = new Choices(dropdown, {
        searchEnabled: true,
        searchResultLimit: 50,
        itemSelectText: "",
        shouldSort: false,
        placeholder: true,
        placeholderValue: "Search or select a transcript...",
    });

}


// =====================================================
// Collect per-tool settings (checked tools, top-N, show-all)
// =====================================================

function collectToolSettings() {

    const tools = [];
    const topN = {};
    const showAll = {};

    document.querySelectorAll(".tool-card").forEach(function (card) {

        const tool = card.dataset.tool;

        const checkbox = card.querySelector(".tool-checkbox");

        if (!checkbox.checked) {
            return;
        }

        tools.push(tool);

        const topNInput = card.querySelector(".topn-input");
        const showAllCheckbox = card.querySelector(".showall-checkbox");

        topN[tool] = parseInt(topNInput.value, 10) || 1;
        showAll[tool] = showAllCheckbox.checked;

        // Disable the Top-N number input while "show all" is
        // checked, so it's visually clear which one is active.
        topNInput.disabled = showAllCheckbox.checked;

    });

    return { tools: tools, topN: topN, showAll: showAll };

}

// Keep the Top-N input disabled state in sync as the user
// toggles "Show all" checkboxes (not just at submit time).
document.querySelectorAll(".showall-checkbox").forEach(function (checkbox) {

    checkbox.addEventListener("change", function () {

        const card = checkbox.closest(".tool-card");

        const topNInput = card.querySelector(".topn-input");

        topNInput.disabled = checkbox.checked;

    });

});


// =====================================================
// Visualize Button
// =====================================================

document
    .getElementById("visualize")
    .addEventListener("click", async function () {

        const transcript =
            document.getElementById("transcript").value;

        const settings = collectToolSettings();

        const response = await fetch(
            "/api/visualize",
            {
                method: "POST",

                headers: {
                    "Content-Type": "application/json"
                },

                body: JSON.stringify({

                    transcript: transcript,

                    tools: settings.tools,

                    top_n: settings.topN,

                    show_all: settings.showAll

                })
            }
        );

        const result = await response.json();

        const plotContainer = document.getElementById("plot");
        const utrNoteEl = document.getElementById("utr-note");

        if (result.status === "success") {

            // Remove the placeholder-centering class so the
            // real chart can fill the container instead of
            // being squeezed as a centered flex child.
            plotContainer.classList.remove("is-placeholder");

            injectHtmlWithScripts(plotContainer, result.plot);

            // Remember the zoom bounds from this render so the
            // Full Transcript / Zoom to Guides buttons can use
            // them immediately, with no extra server round-trip.
            currentZoomBounds = result.zoom_bounds || null;

            // Surface the UTR/CDS status note, if any (e.g. "no
            // CDS annotation" or "CDS spans entire transcript").
            // Absence of a note means real 5'/3' UTRs were found
            // and drawn -- no need to call attention to that.
            if (result.utr_note) {
                utrNoteEl.textContent = result.utr_note;
                utrNoteEl.classList.remove("is-hidden");
            } else {
                utrNoteEl.classList.add("is-hidden");
            }

            attachGuideClickHandler();

            hideGuideDetail();

        } else {

            currentZoomBounds = null;

            plotContainer.classList.add("is-placeholder");

            plotContainer.innerHTML =
                "<p style='color:#C0392B'>" +
                (result.message || "Something went wrong.") +
                "</p>";

            utrNoteEl.classList.add("is-hidden");

            hideGuideDetail();

        }

    });


// =====================================================
// Full Transcript Button
// =====================================================

document
    .getElementById("full")
    .addEventListener("click", function () {

        if (!currentZoomBounds) {
            return;  // nothing has been plotted yet
        }

        const plotDiv = getPlotlyDiv();

        if (!plotDiv) {
            return;
        }

        Plotly.relayout(plotDiv, {
            "xaxis.range": currentZoomBounds.full_range
        });

    });


// =====================================================
// Zoom to Guides Button
// =====================================================

document
    .getElementById("zoom")
    .addEventListener("click", function () {

        if (!currentZoomBounds) {
            return;  // nothing has been plotted yet
        }

        const plotDiv = getPlotlyDiv();

        if (!plotDiv) {
            return;
        }

        Plotly.relayout(plotDiv, {
            "xaxis.range": currentZoomBounds.guide_range
        });

    });


// =====================================================
// Click-to-copy guide detail panel
// =====================================================
// Each guide marker in plotter.py carries customdata in the
// shape [guideSeq, tool, start, end, scoreDisplay, normScoreDisplay].
// Plotly's "plotly_click" event fires with that data attached,
// which we use to populate and show the detail panel below the
// control panel.
// =====================================================

function attachGuideClickHandler() {

    // BUG FIX: injectHtmlWithScripts() only kicks off execution of
    // Plotly's embedded <script> tag -- it does not wait for
    // Plotly.newPlot() inside that script to actually finish
    // constructing the chart. Calling plotDiv.on(...) immediately
    // after injectHtmlWithScripts() returns was a race condition:
    // querySelector(".plotly-graph-div") can find the div before
    // Plotly has finished attaching its own methods (like .on()) to
    // it, causing "plotDiv.on is not a function" and silently
    // preventing the click-to-copy panel from ever opening.
    //
    // Fix: poll briefly until plotDiv.on genuinely exists, then
    // attach. This typically resolves within 1-2 animation frames
    // in practice, well under the timeout below.

    const maxAttempts = 50;       // ~1 second at 20ms intervals
    const intervalMs = 20;
    let attempts = 0;

    function tryAttach() {

        const plotDiv = getPlotlyDiv();

        if (plotDiv && typeof plotDiv.on === "function") {

            plotDiv.on("plotly_click", function (eventData) {

                if (!eventData || !eventData.points || eventData.points.length === 0) {
                    return;
                }

                const point = eventData.points[0];

                if (!point.customdata) {
                    return;  // user clicked something other than a guide marker
                }

                const [guideSeq, tool, start, end, scoreDisplay, normScoreDisplay] =
                    point.customdata;

                showGuideDetail(guideSeq, tool, start, end, scoreDisplay, normScoreDisplay);

            });

            return;
        }

        attempts += 1;

        if (attempts >= maxAttempts) {
            console.error(
                "Could not attach guide click handler: " +
                "plotDiv.on never became available."
            );
            return;
        }

        setTimeout(tryAttach, intervalMs);

    }

    tryAttach();

}

function showGuideDetail(guideSeq, tool, start, end, scoreDisplay, normScoreDisplay) {

    document.getElementById("gd-tool").textContent = tool;
    document.getElementById("gd-sequence").textContent = guideSeq;
    document.getElementById("gd-score").textContent = scoreDisplay;
    document.getElementById("gd-norm-score").textContent = normScoreDisplay;
    document.getElementById("gd-start").textContent = start;
    document.getElementById("gd-end").textContent = end;

    document.getElementById("guide-detail").classList.remove("is-hidden");

}

function hideGuideDetail() {

    document.getElementById("guide-detail").classList.add("is-hidden");

}

document
    .getElementById("gd-close")
    .addEventListener("click", hideGuideDetail);

document
    .getElementById("gd-copy")
    .addEventListener("click", async function () {

        const sequence = document.getElementById("gd-sequence").textContent;

        if (!sequence) {
            return;
        }

        try {

            await navigator.clipboard.writeText(sequence);

            const copyBtn = document.getElementById("gd-copy");
            const originalText = copyBtn.textContent;

            copyBtn.textContent = "Copied!";

            setTimeout(function () {
                copyBtn.textContent = originalText;
            }, 1500);

        } catch (err) {

            console.error("Failed to copy sequence:", err);

        }

    });
