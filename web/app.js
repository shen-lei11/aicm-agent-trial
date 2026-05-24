// AICM Orchestrator Frontend Controller

class AIMMOrchestrator {
    constructor() {
        this.sessionId = null;
        this.pollingInterval = null;
        this.logLines = [];
        this.setupEventListeners();
    }

    setupEventListeners() {
        document.getElementById("btn-start").addEventListener("click", () => this.startPipeline());
        document.getElementById("btn-submit-answers").addEventListener("click", () =>
            this.submitAnswers()
        );
    }

    log(message, type = "info") {
        const timestamp = new Date().toLocaleTimeString();
        this.logLines.push({ message, type, timestamp });
        this.renderProgressLog();
        console.log(`[${type.toUpperCase()}] ${message}`);
    }

    renderProgressLog() {
        const logContainer = document.getElementById("progress-log");
        logContainer.innerHTML = this.logLines
            .map(
                (line) =>
                    `<div class="progress-line ${line.type}">
                [${line.timestamp}] ${line.message}
            </div>`
            )
            .join("");
        logContainer.scrollTop = logContainer.scrollHeight;
    }

    async startPipeline() {
        const discoveryNote = document.getElementById("discovery-note").value;
        if (!discoveryNote.trim()) {
            alert("Please paste a discovery note");
            return;
        }

        // Collect preflight answers
        const preflightAnswers = {};
        document.querySelectorAll(".preflight-chips input:checked").forEach((checkbox) => {
            preflightAnswers[checkbox.value] = "yes";
        });

        // Switch to running phase
        this.switchPhase("running");
        this.logLines = [];
        this.log("🚀 Starting pipeline...");

        try {
            const response = await fetch("/api/start", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ discovery_note: discoveryNote }),
            });

            const data = await response.json();
            this.sessionId = data.session_id;
            this.log(`✓ Session created: ${this.sessionId.substring(0, 8)}...`);

            // Start polling
            this.startPolling();
        } catch (error) {
            this.log(`✗ Failed to start pipeline: ${error.message}`, "error");
        }
    }

    startPolling() {
        this.pollingInterval = setInterval(async () => {
            try {
                const response = await fetch(`/api/status/${this.sessionId}`);
                const status = await response.json();

                this.handleStatusUpdate(status);
            } catch (error) {
                console.error("Polling error:", error);
            }
        }, 4000);
    }

    handleStatusUpdate(status) {
        const { state, pending_questions, result } = status;

        // Only log when state actually changes (not on every poll)
        const stateMessages = {
            input_structuring: "Input Structuring Agent running...",
            base_filtering: "Base Filtering Agent running (parallel batches)...",
            missing_info_check: "Generating questions and gap analysis...",
            complete: "Pipeline complete",
        };

        if (state !== this._lastState && stateMessages[state]) {
            this.log(stateMessages[state]);
            this._lastState = state;
        }

        // Handle transitions
        if (state === "complete") {
            clearInterval(this.pollingInterval);
            this.log("Fetching results...");
            this.fetchResults();
        }
    }

    showQuestionsModal(questions) {
        const form = document.getElementById("questions-form");
        form.innerHTML = questions
            .map(
                (q) => `
            <div class="question-item">
                <label>${q.question}</label>
                <input type="text" name="q_${q.question_id}" placeholder="Your answer..." />
            </div>
        `
            )
            .join("");

        this.switchPhase("questions");
    }

    async submitAnswers() {
        const answers = {};
        document.querySelectorAll("#questions-form input").forEach((input) => {
            answers[input.name] = input.value;
        });

        try {
            await fetch(`/api/answer/${this.sessionId}`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ answers }),
            });

            this.log("✓ Answers submitted");
            this.switchPhase("running");
            this.startPolling();
        } catch (error) {
            this.log(`✗ Failed to submit answers: ${error.message}`, "error");
        }
    }

    async fetchResults() {
        try {
            const response = await fetch(`/api/result/${this.sessionId}`);
            if (response.status === 202) {
                // Still running, keep polling
                setTimeout(() => this.fetchResults(), 2000);
                return;
            }

            const result = await response.json();
            this.renderResults(result);
            this.switchPhase("results");
            this.log("✓ Results displayed", "success");
        } catch (error) {
            this.log(`✗ Failed to fetch results: ${error.message}`, "error");
        }
    }

    renderResults(result) {
        const container = document.getElementById("results-container");
        const decisions = result.filtered_controls?.decisions || [];
        const questions = result.gap_analysis?.client_question_set || [];

        // Group by decision type (new priority tiers)
        const groups = {
            "Primary Requirement": [],
            "Secondary Recommendation": [],
            "Needs Clarification": [],
            "Not Applicable": [],
        };
        for (const d of decisions) {
            if (d.decision in groups) groups[d.decision].push(d);
        }

        // Map control_id -> questions that affect it
        const ctrlQ = {};
        for (const q of questions) {
            for (const ctrl of (q.affected_controls_or_domains || [])) {
                (ctrlQ[ctrl] = ctrlQ[ctrl] || []).push(q);
            }
        }

        // Summary bar
        let html = `
        <div class="results-summary">
            <div class="summary-stat"><span class="stat-num">${decisions.length}</span><span class="stat-label">Assessed</span></div>
            <div class="summary-stat s-keep"><span class="stat-num">${groups["Primary Requirement"].length}</span><span class="stat-label">Primary</span></div>
            <div class="summary-stat s-baseline"><span class="stat-num">${groups["Secondary Recommendation"].length}</span><span class="stat-label">Secondary</span></div>
            <div class="summary-stat s-nmi"><span class="stat-num">${groups["Needs Clarification"].length}</span><span class="stat-label">Needs Clarification</span></div>
            <div class="summary-stat s-q"><span class="stat-num">${questions.length}</span><span class="stat-label">Questions</span></div>
        </div>`;

        // Primary Requirement section
        if (groups["Primary Requirement"].length) {
            html += `<div class="result-section">
                <h3 class="sec-hdr hdr-keep">Primary Requirements (${groups["Primary Requirement"].length})</h3>
                <p class="sec-desc">Directly triggered by your scenario</p>
                ${groups["Primary Requirement"].map(d => `
                <div class="ctrl-row">
                    <span class="ctrl-id">${d.control_id}</span>
                    <span class="ctrl-title">${d.control_title || ""}</span>
                    ${d.control_description ? `<div class="ctrl-desc">${d.control_description}</div>` : ""}
                    ${d.reason ? `<div class="ctrl-reason">${d.reason}</div>` : ""}
                </div>`).join("")}
            </div>`;
        }

        // Secondary Recommendation section
        if (groups["Secondary Recommendation"].length) {
            html += `<div class="result-section">
                <h3 class="sec-hdr hdr-baseline">Secondary Recommendations (${groups["Secondary Recommendation"].length})</h3>
                <p class="sec-desc">Universal best practices and governance hygiene</p>
                ${groups["Secondary Recommendation"].map(d => `
                <div class="ctrl-row">
                    <span class="ctrl-id">${d.control_id}</span>
                    <span class="ctrl-title">${d.control_title || ""}</span>
                    ${d.control_description ? `<div class="ctrl-desc">${d.control_description}</div>` : ""}
                </div>`).join("")}
            </div>`;
        }

        // Needs Clarification section — with linked questions
        if (groups["Needs Clarification"].length) {
            html += `<div class="result-section">
                <h3 class="sec-hdr hdr-nmi">Needs Clarification (${groups["Needs Clarification"].length})</h3>
                <p class="sec-desc">Cannot be decided until the questions below are answered</p>
                ${groups["Needs Clarification"].map(d => {
                    const qs = ctrlQ[d.control_id] || [];
                    return `<div class="ctrl-row nmi-row">
                        <span class="ctrl-id">${d.control_id}</span>
                        <span class="ctrl-title">${d.control_title || ""}</span>
                        ${d.control_description ? `<div class="ctrl-desc">${d.control_description}</div>` : ""}
                        ${d.missing_dependency ? `<div class="ctrl-reason">Missing: ${d.missing_dependency}</div>` : ""}
                        ${qs.map(q => `
                        <div class="ctrl-question">
                            <span class="q-badge">Q</span> ${q.question}
                        </div>`).join("")}
                    </div>`;
                }).join("")}
            </div>`;
        }

        // Split questions into gap vs NMI-control categories
        const gapQs  = questions.filter(q => q.source === "missing_gap" || (!q.source && questions.indexOf(q) === questions.indexOf(q)));
        const nmiQs  = questions.filter(q => q.source === "nmi_control");
        const otherQs = questions.filter(q => q.source !== "missing_gap" && q.source !== "nmi_control");
        // If no source tags, fall back to showing all together
        const hasSourceTags = questions.some(q => q.source);

        const renderQBlock = (q, i) => `
        <div class="q-block">
            <div class="q-num">Q${i + 1}</div>
            <div class="q-body">
                <div class="q-text">${q.question}</div>
                ${q.decision_impact ? `<div class="q-impact">${q.decision_impact}</div>` : ""}
                ${q.affected_controls_or_domains?.length ? `<div class="q-controls">${q.affected_controls_or_domains.join(", ")}</div>` : ""}
            </div>
        </div>`;

        if (hasSourceTags) {
            if (gapQs.length) {
                html += `<div class="result-section">
                    <h3 class="sec-hdr hdr-q">Missing Information Gaps (${gapQs.length})</h3>
                    <p class="sec-desc">Information absent from the discovery note that blocks multiple decisions</p>
                    ${gapQs.map(renderQBlock).join("")}
                </div>`;
            }
            if (nmiQs.length) {
                html += `<div class="result-section">
                    <h3 class="sec-hdr hdr-nmi">Control Clarifications Needed (${nmiQs.length})</h3>
                    <p class="sec-desc">One question per "Needs Clarification" control — answers will resolve its decision</p>
                    ${nmiQs.map(renderQBlock).join("")}
                </div>`;
            }
            if (otherQs.length) {
                html += `<div class="result-section">
                    <h3 class="sec-hdr hdr-q">Additional Questions (${otherQs.length})</h3>
                    ${otherQs.map(renderQBlock).join("")}
                </div>`;
            }
        } else if (questions.length) {
            html += `<div class="result-section">
                <h3 class="sec-hdr hdr-q">Questions to Ask Client (${questions.length})</h3>
                ${questions.map(renderQBlock).join("")}
            </div>`;
        }

        container.innerHTML = html;
    }

    switchPhase(phaseName) {
        document.querySelectorAll(".phase").forEach((p) => p.classList.remove("active"));
        document.getElementById(`phase-${phaseName}`).classList.add("active");
    }
}

// Initialize on page load
document.addEventListener("DOMContentLoaded", () => {
    window.orchestrator = new AIMMOrchestrator();
});
