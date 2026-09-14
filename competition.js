(function () {
    let selected = null;
    let timer = null;
    let stageData = null;

    const STAGED = ["guess_it", "survivor", "dead_number"];

    function stopTimer() {
        if (timer) {
            clearInterval(timer);
            timer = null;
        }
    }

    function competitionApi(path, options = {}) {
        return api(path, options);
    }

    function gameName(game) {
        return `${game?.emoji || game?.icon || "🎮"} ${game?.name || "QuizBee Game"}`;
    }

    function formatTime(ms) {
        if (ms <= 0) return "00:00";

        const total = Math.floor(ms / 1000);
        const d = Math.floor(total / 86400);
        const h = Math.floor((total % 86400) / 3600);
        const m = Math.floor((total % 3600) / 60);
        const s = total % 60;

        if (d > 0) {
            return `${d}d ${String(h).padStart(2, "0")}h ${String(m).padStart(2, "0")}m`;
        }

        if (h > 0) {
            return `${String(h).padStart(2, "0")}h ${String(m).padStart(2, "0")}m ${String(s).padStart(2, "0")}s`;
        }

        return `${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}`;
    }

    function renderShell(title, body) {
        const box = document.getElementById("gameContent");

        if (!box) return;

        box.innerHTML = `
            <div class="game-detail-card">
                <div class="challenge-box">
                    <h3>${escapeHtml(title)}</h3>
                    ${body}
                </div>
            </div>
        `;
    }

    function renderAggregateSummary(
    result,
    finalStage = false
) {
    if (!result) {
        return "";
    }

    const total = Number(
        result.stage_total_entries || 0
    );

    const submitted = Number(
        result.stage_submitted_count || 0
    );

    const advanced = Number(
        result.stage_advanced_count || 0
    );

    const winners = Number(
        result.stage_winner_count || 0
    );

    const failed = Number(
        result.stage_failed_count ??
        Math.max(
            total -
            (
                finalStage
                    ? winners
                    : advanced
            ),
            0
        )
    );

    if (!total) {
        return "";
    }

    return `
        <div class="competition-result-summary">

            <div class="competition-result-summary-title">
                📊 Stage Results
            </div>

            <div class="competition-result-row">
                👥 Total participants:
                <strong>${total}</strong>
            </div>

            <div class="competition-result-row">
                📝 Answers submitted:
                <strong>${submitted}</strong>
            </div>

            ${
                finalStage
                    ? `
                        <div class="competition-result-row">
                            🏆 People who won:
                            <strong>${winners}</strong>
                        </div>
                    `
                    : `
                        <div class="competition-result-row">
                            🎉 People who advanced:
                            <strong>${advanced}</strong>
                        </div>
                    `
            }

            <div class="competition-result-row">
                ❌ People who failed:
                <strong>${failed}</strong>
            </div>

        </div>
    `;
                                                     }
    function renderStatus(data) {
        stopTimer();
        selected = null;
        stageData = data.stage || null;

        if (data.user) {
            updateUserState(data.user);
        }

        const round = data.round || {};
        const stage = data.stage || {};
        const game = data.game || currentGame || {};

        const fee = Number(
            data.entry_fee ??
            stage.entry_fee ??
            0
        );

        if (data.status === "no_round") {
            renderShell(gameName(game), `
                <div class="info-box">
                    No round is currently available.
                </div>
                <button class="secondary-btn full" onclick="competitionRefresh()">
                    REFRESH
                </button>
            `);
            return;
        }

        if (data.status === "winner") {
            const result = data.result || {};

            renderShell(gameName(game), `
                <div class="info-box">
                    🏆 <strong>Congratulations! You won!</strong>
                </div>

                <p>
                    ${escapeHtml(
                        result.message ||
                        "You survived the competition and are a winner."
                    )}
                </p>

                ${
                    Number(result.amount_usd || 0) > 0
                        ? `
                            <div class="info-box">
                                💰 Prize won:
                                <strong>
                                    $${Number(result.amount_usd).toFixed(2)}
                                </strong>
                            </div>
                        `
                        : ""
                }

                ${
                    result.correct_answer !== null &&
                    result.correct_answer !== undefined &&
                    result.correct_answer !== ""
                        ? `
                            <div class="info-box">
                                Correct answer:
                                <strong>
                                    ${escapeHtml(String(result.correct_answer))}
                                </strong>
                            </div>
                        `
                        : ""
                }
                ${renderAggregateSummary(result, true)}
            `);
            return;
        }

        if (data.status === "advanced") {
            const result = data.result || {};
            const nextStage = Number(result.next_stage || 0);

            renderShell(gameName(game), `
                <div class="info-box">
                    🎉 <strong>
                        You passed Stage ${Number(result.stage_no || 1)}!
                    </strong>
                </div>

                <div class="info-box">
                    ➡️ <strong>
                        You advanced ${
                            nextStage
                                ? `to Stage ${nextStage}`
                                : "to the next stage"
                        }.
                    </strong>
                </div>

                ${
                    result.correct_answer !== null &&
                    result.correct_answer !== undefined &&
                    result.correct_answer !== ""
                        ? `
                            <div class="info-box">
                                Correct answer:
                                <strong>
                                    ${escapeHtml(String(result.correct_answer))}
                                </strong>
                            </div>
                        `
                        : ""
                }
                ${renderAggregateSummary(result, false)}

                <p>
                    Return when the next stage is live and pay
                    its entry fee to continue.
                </p>

                <button class="secondary-btn full" onclick="competitionRefresh()">
                    CHECK NEXT STAGE
                </button>
            `);
            return;
        }

        if (data.status === "eliminated") {
            const result = data.result || {};

            renderShell(gameName(game), `
                <div class="info-box">
                    ❌ <strong>You have been eliminated.</strong>
                </div>

                <p>
                    ${escapeHtml(
                        result.message ||
                        data.message ||
                        "You did not pass this stage."
                    )}
                </p>

                ${
                    result.correct_answer !== null &&
                    result.correct_answer !== undefined &&
                    result.correct_answer !== ""
                        ? `
                            <div class="info-box">
                                Correct answer:
                                <strong>
                                    ${escapeHtml(String(result.correct_answer))}
                                </strong>
                            </div>
                        `
                        : ""
                }
                ${renderAggregateSummary(
    result,
    Boolean(result.final)
)}

                <p>
                    You cannot re-enter this round.
                    Wait for a fresh competition round.
                </p>
            `);
            return;
        }

        if (data.status === "finished") {
            renderShell(gameName(game), `
                <div class="info-box">
                    🏁 <strong>This competition has finished.</strong>
                </div>

                <p>
                    Final winners:
                    <strong>${Number(round.winner_count || 0)}</strong>
                </p>

                ${
                    Number(round.prize_pool_usd || 0) > 0
                        ? `
                            <p>
                                Prize pool:
                                <strong>
                                    $${Number(round.prize_pool_usd).toFixed(2)}
                                </strong>
                            </p>
                        `
                        : ""
                }
            `);
            return;
        }

        if (data.status === "round_not_started") {
            const previous = data.previous_result || null;

            if (previous && previous.advanced) {
                renderShell(gameName(game), `
                    <div class="info-box">
                        🎉 <strong>
                            You advanced from Stage
                            ${Number(previous.stage_no || 1)}!
                        </strong>
                    </div>
                    ${renderAggregateSummary(previous, false)}

                    <div class="info-box">
                        ⏳ <strong>
                            Stage ${Number(round.current_stage || 2)}
                            has not started yet.
                        </strong>
                    </div>

                    <p>
                        QuizBee Admin is preparing the next stage.
                        Come back when it goes live.
                    </p>

                    <button class="secondary-btn full" onclick="competitionRefresh()">
                        CHECK AGAIN
                    </button>
                `);
            } else {
                renderShell(gameName(game), `
                    <div class="info-box">
                        ⏳ <strong>Round not started yet.</strong>
                    </div>

                    <p>
                        The next stage is being prepared by QuizBee Admin.
                    </p>

                    <button class="secondary-btn full" onclick="competitionRefresh()">
                        CHECK AGAIN
                    </button>
                `);
            }
            return;
        }

        if (data.status === "needs_entry") {
            renderShell(gameName(game), `
                ${
                    round.title
                        ? `<p><strong>${escapeHtml(round.title)}</strong></p>`
                        : ""
                }

                <div class="info-box">
                    Stage
                    <strong>${Number(stage.stage_no || round.current_stage || 1)}</strong>
                    <br>
                    Entry:
                    <strong>${fee} QuizBee Points</strong>
                    ${
                        Number(stage.stage_no || 1) === 7
                            ? `<br><strong>Final stage fee: ${fee} points</strong>`
                            : ""
                    }
                </div>

                ${
                    stage.end_at
                        ? `<div class="competition-timer" id="competitionTimer"></div>`
                        : ""
                }

                <button class="primary-btn full" onclick="competitionEnter()">
                    ENTER - ${fee} POINTS
                </button>
            `);

            startTimer(stage.end_at);
            return;
        }

        if (data.status === "submitted") {
            renderShell(gameName(game), `
                <div class="info-box">
                    🔒 <strong>Answer locked.</strong>
                </div>

                <p>
                    ${escapeHtml(
                        data.message ||
                        "Your answer has been recorded. Wait for the stage to conclude."
                    )}
                </p>

                <button class="secondary-btn full" onclick="competitionRefresh()">
                    REFRESH STATUS
                </button>
            `);

            startTimer(stage.end_at);
            return;
        }

        if (data.status === "ready") {
            renderChallenge(data);
            return;
        }

        renderShell(
            gameName(game),
            `<div class="info-box">${escapeHtml(
                data.message || "Unable to load this round."
            )}</div>`
        );
    }

    function startTimer(endAt) {
        stopTimer();

        if (!endAt) return;

        const end = new Date(endAt).getTime();

        const tick = () => {
            const el = document.getElementById(
                "competitionTimer"
            );

            const remaining = end - Date.now();

            if (el) {
                el.textContent =
                    ` Time remaining: ${formatTime(remaining)}`;
            }

            if (remaining <= 0) {
                stopTimer();

                setTimeout(
                    competitionRefresh,
                    300
                );
            }
        };

        tick();

        timer = setInterval(
            tick,
            1000
        );
    }

    function renderChallenge(data) {
        const game = data.game || currentGame || {};
        const stage = data.stage || {};

        const id = game.id;

        const stageNo = Number(
            stage.stage_no || 1
        );

        const fee = Number(
            stage.entry_fee ||
            data.entry_fee ||
            0
        );

        const question =
            stage.question ||
            stage.title ||
            "Choose carefully.";

        let body = `
            <div class="info-box">
                stage
                <strong>${stageNo}</strong>
                · Entry
                <strong>${fee} points</strong>
            </div>

            ${
                stage.clue
                    ? `
                        <div class="info-box">

                            <strong>Clue:</strong>
                            ${escapeHtml(stage.clue)}
                        </div>
                      `
                    : ""
            }

            <div class="question">
                ${escapeHtml(question)}
            </div>

            <div
                class="competition-timer"
                id="competitionTimer">
            </div>
        `;

        if (
            id === "guess_it" ||
            id === "impossible_question"
        ) {
            body += `
                <input
                    id="competitionAnswer"
                    class="number-input"
                    type="text"
                    placeholder="Your answer…"
                    autocomplete="off"
                >

                <button
                    class="primary-btn full"
                    onclick="competitionSubmitText()">
                    SUBMIT ANSWER
                </button>
            `;
        }

        else if (
            id === "crowd_trap" ||
            id === "dead_number"
        ) {
            const min = Number(
                stage.min_number ?? 1
            );

            const max = Number(
                stage.max_number ?? 20
            );

            body += `
                <div class="info-box">
                    choose one number from
                    <strong>${min}</strong>
                    to
                    <strong>${max}</strong>.
                </div>

                <input
                    id="competitionNumber"
                    class="number-input"
                    type="number"
                    min="${min}"
                    max="${max}"
                    placeholder="Enter your number"
                >

                <button
                    class="primary-btn full"
                    onclick="competitionSubmitNumber()">
                    LOCK MY NUMBER
                </button>
            `;
        }

        else {
            const options =
                Array.isArray(stage.options)
                    ? stage.options
                    : [];

            body += `
                <div
                    class="options"
                    id="competitionOptions">
            `;

            body += options.map(
                (option, index) => `
                    <button
                        class="option-btn"
                        data-comp-index="${index}"
                        onclick="competitionSelect(${index})">
                        ${escapeHtml(option)}
                    </button>
                `
            ).join("");

            body += `
                </div>

                <button
                    id="competitionChoiceButton"
                    class="primary-btn full"
                    onclick="competitionSubmitChoice()"
                    disabled>
                    SUBMIT CHOICE
                </button>
            `;
        }

        renderShell(
            gameName(game),
            body
        );

        startTimer(stage.end_at);
    }

    window.competitionRefresh = async function () {
        if (!currentGame) return;

        const box =
            document.getElementById(
                "gameContent"
            );

        if (box) {
            box.innerHTML = `
                <div class="game-detail-card">
                    <div class="info-box">
                        loading round…
                    </div>
                </div>
            `;
        }

        try {
            const data = await competitionApi(
                `/api/competition/${encodeURIComponent(currentGame.id)}/state`
            );

            if (!data.success) {
                throw new Error(
                    data.error ||
                    "Unable to load round."
                );
            }

            renderStatus(data);
        }

        catch (error) {
            renderShell(
                gameName(currentGame),
                `
                    <div class="info-box">
                        ${escapeHtml(error.message)}
                    </div>

                    <button
                        class="primary-btn full"
                        onclick="competitionRefresh()">
                        TRY AGAIN
                    </button>
                `
            );
        }
    };

    window.openGame = async function (gameId) {
        const game =
            games.find(
                item => item.id === gameId
            );

        if (!game) {
            return showToast(
                "Game not found."
            );
        }

        if (!game.active) {
            return lockedGame();
        }

        currentGame = game;
        currentChallenge = null;
        selected = null;

        const title =
            document.getElementById(
                "gameTitle"
            );

        if (title) {
            title.textContent =
                gameName(game);
        }

        showPage("game");

        await competitionRefresh();
    };

    window.enterGame =
    window.competitionEnter =
    async function () {
        if (!currentGame) return;

        try {
            const data =
                await competitionApi(
                    `/api/competition/${encodeURIComponent(currentGame.id)}/enter`,
                    {
                        method: "POST",
                        body: JSON.stringify({})
                    }
                );

            if (data.user) {
                updateUserState(
                    data.user
                );
            }

            showToast(
                data.already_entered
                    ? "You already paid for this stage."
                    : "Entry successful! "
            );

            await competitionRefresh();
        }

        catch (error) {
            showToast(
                error.message ||
                "Unable to enter stage."
            );
        }
    };

    async function submit(answer) {
        if (!currentGame) return;

        const buttons =
            document.querySelectorAll(
                "#gameContent button, #gameContent input"
            );

        buttons.forEach(
            x => x.disabled = true
        );

        try {
            const data =
                await competitionApi(
                    `/api/competition/${encodeURIComponent(currentGame.id)}/submit`,
                    {
                        method: "POST",
                        body: JSON.stringify({
                            answer
                        })
                    }
                );

            if (data.user) {
                updateUserState(
                    data.user
                );
            }

            showToast(
                data.message ||
                "Answer submitted."
            );

            await competitionRefresh();
        }

        catch (error) {
            showToast(
                error.message ||
                "Unable to submit answer."
            );

            buttons.forEach(
                x => x.disabled = false
            );
        }
    }

    window.competitionSubmitText =
    async function () {
        const input =
            document.getElementById(
                "competitionAnswer"
            );

        if (
            !input ||
            !input.value.trim()
        ) {
            return showToast(
                "Enter an answer first."
            );
        }

        await submit(
            input.value.trim()
        );
    };

    window.competitionSubmitNumber =
    async function () {
        const input =
            document.getElementById(
                "competitionNumber"
            );

        if (
            !input ||
            input.value === ""
        ) {
            return showToast(
                "Enter a number."
            );
        }

        const n =
            Number(input.value);

        const stage =
            stageData || {};

        if (
            !Number.isInteger(n) ||
            n < Number(
                stage.min_number ?? 1
            ) ||
            n > Number(
                stage.max_number ?? 20
            )
        ) {
            return showToast(
                "Choose a valid number in the allowed range."
            );
        }

        await submit(
            String(n)
        );
    };

    window.competitionSelect =
    function (index) {
        selected = index;

        document
            .querySelectorAll(
                "[data-comp-index]"
            )
            .forEach(button => {
                button.style.borderColor = "";
                button.style.background = "";
            });

        const selectedButton =
            document.querySelector(
                `[data-comp-index="${index}"]`
            );

        if (selectedButton) {
            selectedButton.style.borderColor =
                "var(--yellow)";

            selectedButton.style.background =
                "#303642";
        }

        const button =
            document.getElementById(
                "competitionChoiceButton"
            );

        if (button) {
            button.disabled = false;
        }
    };

    window.competitionSubmitChoice =
    async function () {
        if (selected === null) {
            return showToast(
                "Select an option first."
            );
        }

        const options =
            Array.isArray(stageData?.options)
                ? stageData.options
                : [];

        if (
            options[selected] === undefined
        ) {
            return showToast(
                "Invalid choice."
            );
        }

        await submit(
            options[selected]
        );
    };

    // Small visual layer.
    // Avoids touching the existing stylesheet.
    const style =
        document.createElement("style");

    style.textContent = `
        .competition-timer {
            margin: 12px 0;
            padding: 10px;
            border-radius: 10px;
            text-align: center;
            font-weight: 700;
            background: rgba(255,255,255,.06);
        }

        #gameContent .full {
            width: 100%;
            margin-top: 10px;
        }
    `;

    document.head.appendChild(style);
})();
 
