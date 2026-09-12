// ============================================================
// DAILY EARNING
// ============================================================

let dailyEarningRound = null;
let dailyEarningTimer = null;


// ============================================================
// LOAD DAILY EARNING
// ============================================================

async function loadDailyEarning() {

    const container =
        document.getElementById(
            "dailyEarningContent"
        );

    if (!container) {
        return;
    }

    container.innerHTML = `
        <div class="info-box">
            Loading Daily Earning...
        </div>
    `;

    try {

        const data =
            await api(
                "/api/daily-earning/current"
            );

        if (!data.success) {
            throw new Error(
                data.error ||
                "Unable to load Daily Earning."
            );
        }

        dailyEarningRound =
            data.round;

        renderDailyEarning();

    } catch (error) {

        console.error(
            "Daily Earning error:",
            error
        );

        container.innerHTML = `
            <div class="info-box">
                ${escapeHtml(
                    error.message ||
                    "Unable to load Daily Earning."
                )}
            </div>
        `;
    }
}


// ============================================================
// RENDER
// ============================================================

function renderDailyEarning() {

    const container =
        document.getElementById(
            "dailyEarningContent"
        );

    if (!container) {
        return;
    }

    if (!dailyEarningRound) {

        container.innerHTML = `
            <div class="earning-empty">
                <div class="earning-empty-icon">
                    💰
                </div>

                <h2>
                    No Daily Earning Yet
                </h2>

                <p>
                    Check back later for today's
                    earning opportunity.
                </p>

                <button
                    class="secondary-btn"
                    onclick="showPage('ads')"
                >
                    📺 WATCH ADS
                </button>
            </div>
        `;

        return;
    }

    const round =
        dailyEarningRound;

    const mode =
        round.mode === "task"
            ? "📋 Task"
            : "🧠 Question";

    const prize =
        Number(
            round.prize_pool_usd || 0
        ).toFixed(2);

    const maxEntries =
        Number(
            round.max_entries || 0
        );

    const participants =
        Number(
            round.participant_count || 0
        );

    const entered =
        !!round.user_entry;

    const status =
        round.user_entry?.status || "";

    let content = "";

    if (!entered) {

        content = `
            <div class="earning-card">

                <div class="earning-badge">
                    ${mode}
                </div>

                <h2>
                    ${escapeHtml(
                        round.title ||
                        "Daily Earning"
                    )}
                </h2>

                <div class="earning-prize">
                    $${prize}
                </div>

                <div class="earning-prize-label">
                    Total Prize Pool
                </div>

                <div class="earning-meta">

                    <div>
                        <span>Entry</span>
                        <strong>10 Points</strong>
                    </div>

                    <div>
                        <span>Slots</span>
                        <strong>
                            ${
                                maxEntries > 0
                                    ? `${participants}/${maxEntries}`
                                    : participants
                            }
                        </strong>
                    </div>

                </div>

                <div class="earning-help">
                    💡 Low on points? Watch 10 ads, gain 10 points, enter Daily Earning.
                </div> 

                ${
                    round.end_at
                        ? `
                            <div
                                id="dailyEarningTimer"
                                class="earning-timer"
                            >
                                Loading timer...
                            </div>
                        `
                        : ""
                }

                ${
                    round.question
                        ? `
                            <div class="earning-question">
                                ${escapeHtml(
                                    round.question
                                )}
                            </div>
                        `
                        : ""
                }

                ${
                    round.instructions
                        ? `
                            <div class="earning-instructions">
                                ${escapeHtml(
                                    round.instructions
                                )}
                            </div>
                        `
                        : ""
                }

                <button
                    class="primary-btn"
                    onclick="enterDailyEarning()"
                >
                    ENTER FOR 10 POINTS
                </button>

                <div class="earning-note">
                    ${
                        mode === "🧠 Question"
                            ? "Your answer will remain hidden until the timer ends."
                            : "Complete the task and submit your proof for review."
                    }
                </div>

            </div>
        `;

    } else {

        content = `
            <div class="earning-card">

                <div class="earning-badge">
                    ${mode}
                </div>

                <h2>
                    ${escapeHtml(
                        round.title ||
                        "Daily Earning"
                    )}
                </h2>

                <div class="earning-prize">
                    $${prize}
                </div>

                <div class="earning-prize-label">
                    Total Prize Pool
                </div>

                ${
                    round.end_at
                        ? `
                            <div
                                id="dailyEarningTimer"
                                class="earning-timer"
                            >
                                Loading timer...
                            </div>
                        `
                        : ""
                }

                ${
                    mode === "🧠 Question"
                        ? `
                            <div class="earning-question">
                                ${escapeHtml(
                                    round.question ||
                                    "Submit your answer below."
                                )}
                            </div>

                            <input
                                id="dailyEarningAnswer"
                                class="text-input"
                                type="text"
                                placeholder="Your answer..."
                                autocomplete="off"
                            >

                            <button
                                class="primary-btn"
                                onclick="submitDailyEarningAnswer()"
                            >
                                SUBMIT ANSWER
                            </button>

                            <div class="earning-note">
                                Your result will not be revealed until the timer ends.
                            </div>
                        `
                        : `
                            <div class="earning-instructions">
                                ${
                                    escapeHtml(
                                        round.instructions ||
                                        "Complete the task and submit proof."
                                    )
                                }
                            </div>

                            <textarea
                                id="dailyProofText"
                                class="text-input"
                                rows="4"
                                placeholder="Describe your proof or paste the required link..."
                            ></textarea>

                            <input
                                id="dailyProofUrl"
                                class="text-input"
                                type="text"
                                placeholder="Proof link (if required)"
                            >

                            <button
                                class="primary-btn"
                                onclick="submitDailyProof()"
                            >
                                SUBMIT PROOF
                            </button>

                            <div class="earning-note">
                                Your submission will be reviewed by an admin.
                            </div>
                        `
                }

                <div class="earning-status">
                    Status:
                    <strong>
                        ${escapeHtml(
                            status ||
                            "Entered"
                        )}
                    </strong>
                </div>

            </div>
        `;
    }

    container.innerHTML =
        content;

    startDailyEarningTimer();
}


// ============================================================
// ENTER
// ============================================================

async function enterDailyEarning() {

    if (!dailyEarningRound) {
        return;
    }

    try {

        const data =
            await api(
                "/api/daily-earning/enter",
                {
                    method: "POST",
                    body: JSON.stringify({
                        round_id:
                            dailyEarningRound.id
                    })
                }
            );

        if (!data.success) {
            throw new Error(
                data.error ||
                "Unable to enter."
            );
        }

        showToast(
            data.already_entered
                ? "You already entered this round."
                : "Entered Daily Earning! -10 Points"
        );

        await loadDailyEarning();

        if (data.quizbee_points !== undefined) {

            currentUser =
                currentUser || {};

            currentUser.quizbee_points =
                data.quizbee_points;

            updateUserState(
                currentUser
            );
        }

    } catch (error) {

        showToast(
            error.message ||
            "Unable to enter Daily Earning."
        );
    }
}


// ============================================================
// QUESTION ANSWER
// ============================================================

async function submitDailyEarningAnswer() {

    const input =
        document.getElementById(
            "dailyEarningAnswer"
        );

    if (!input) {
        return;
    }

    const answer =
        input.value.trim();

    if (!answer) {

        showToast(
            "Enter your answer first."
        );

        return;
    }

    try {

        const data =
            await api(
                "/api/daily-earning/answer",
                {
                    method: "POST",
                    body: JSON.stringify({
                        round_id:
                            dailyEarningRound.id,

                        answer:
                            answer
                    })
                }
            );

        if (!data.success) {
            throw new Error(
                data.error ||
                "Unable to submit answer."
            );
        }

        input.disabled = true;

        showToast(
            "Answer submitted! Result comes after the timer."
        );

    } catch (error) {

        showToast(
            error.message ||
            "Unable to submit answer."
        );
    }
}


// ============================================================
// TASK PROOF
// ============================================================

async function submitDailyProof() {

    const proofText =
        document.getElementById(
            "dailyProofText"
        );

    const proofUrl =
        document.getElementById(
            "dailyProofUrl"
        );

    const text =
        proofText
            ? proofText.value.trim()
            : "";

    const url =
        proofUrl
            ? proofUrl.value.trim()
            : "";

    if (!text && !url) {

        showToast(
            "Submit your proof first."
        );

        return;
    }

    try {

        const data =
            await api(
                "/api/daily-earning/proof",
                {
                    method: "POST",
                    body: JSON.stringify({
                        round_id:
                            dailyEarningRound.id,

                        proof_text:
                            text,

                        proof_url:
                            url
                    })
                }
            );

        if (!data.success) {
            throw new Error(
                data.error ||
                "Unable to submit proof."
            );
        }

        showToast(
            "Proof submitted for review."
        );

        await loadDailyEarning();

    } catch (error) {

        showToast(
            error.message ||
            "Unable to submit proof."
        );
    }
}


// ============================================================
// TIMER
// ============================================================

function startDailyEarningTimer() {

    clearInterval(
        dailyEarningTimer
    );

    if (
        !dailyEarningRound ||
        !dailyEarningRound.end_at
    ) {
        return;
    }

    function updateTimer() {

        const timer =
            document.getElementById(
                "dailyEarningTimer"
            );

        if (!timer) {
            return;
        }

        const end =
            new Date(
                dailyEarningRound.end_at
            ).getTime();

        const remaining =
            end - Date.now();

        if (remaining <= 0) {

            timer.textContent =
                "⏰ ROUND ENDED";

            clearInterval(
                dailyEarningTimer
            );

            setTimeout(
                loadDailyEarning,
                1500
            );

            return;
        }

        const totalSeconds =
            Math.floor(
                remaining / 1000
            );

        const hours =
            Math.floor(
                totalSeconds / 3600
            );

        const minutes =
            Math.floor(
                (totalSeconds % 3600) / 60
            );

        const seconds =
            totalSeconds % 60;

        timer.textContent =
            `⏱️ ${String(hours).padStart(2, "0")}:${String(minutes).padStart(2, "0")}:${String(seconds).padStart(2, "0")}`;
    }

    updateTimer();

    dailyEarningTimer =
        setInterval(
            updateTimer,
            1000
        );
      }
