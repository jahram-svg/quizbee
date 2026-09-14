(function () {
    let currentRoundId = null;
    let selectedGame = "guess_it";

    const GAMES = {
        guess_it: {
            emoji: "🎯",
            name: "Guess It",
            staged: true,
            description: "7-stage elimination and survival challenge."
        },
        impossible_question: {
            emoji: "💀",
            name: "Impossible Question",
            staged: false,
            description: "One difficult question. One answer per player."
        },
        crowd_trap: {
            emoji: "🧠",
            name: "The Crowd Trap",
            staged: false,
            description: "Players choose privately. Unique choices survive."
        },
        survivor: {
            emoji: "🏆",
            name: "The Survivor",
            staged: true,
            description: "Choose the safe option and survive to the next stage."
        },
        dead_number: {
            emoji: "️",
            name: "Dead Number",
            staged: true,
            description: "Avoid the dead numbers and survive."
        },
        impossible_choice: {
            emoji: "🤔",
            name: "Impossible Choice",
            staged: false,
            description: "Predict the crowd using psychological game mechanics."
        }
    };

    const STAGED_GAMES = [
        "guess_it",
        "survivor",
        "dead_number"
    ];

    function h(value) {
        return escapeHtml(value ?? "");
    }

    function gameInfo(gameId) {
        return GAMES[gameId] || {
            emoji: "",
            name: gameId || "Competition",
            staged: false,
            description: ""
        };
    }

    function gameLabel(gameId) {
        const game = gameInfo(gameId);
        return `${game.emoji} ${game.name}`;
    }

    function addStyles() {
        if (document.getElementById("competitionAdminStyles")) return;

        const style = document.createElement("style");
        style.id = "competitionAdminStyles";

        style.textContent = `
            #competitionPage {
                padding-bottom: 100px;
            }

            #competitionPage .competition-tabs {
                display: grid;
                grid-template-columns: repeat(2, minmax(0, 1fr));
                gap: 8px;
                margin-bottom: 15px;
            }

            #competitionPage .competition-tab {
                border: 1px solid rgba(255,255,255,.10);
                background: rgba(255,255,255,.04);
                color: inherit;
                border-radius: 12px;
                padding: 12px 8px;
                cursor: pointer;
                text-align: left;
                font-weight: 700;
            }

            #competitionPage .competition-tab.active {
                border-color: var(--yellow);
                background: rgba(255,255,0,.08);
            }

            #competitionPage .competition-tab small {
                display: block;
                opacity: .65;
                margin-top: 4px;
                font-weight: 400;
                line-height: 1.25;
            }

            #competitionPage .competition-game-header {
                display: flex;
                justify-content: space-between;
                align-items: flex-start;
                gap: 12px;
                margin-bottom: 15px;
            }

            #competitionPage .competition-game-header h2 {
                margin: 0 0 5px;
            }

            #competitionPage .competition-game-header p {
                margin: 0;
                opacity: .7;
            }

            #competitionPage .competition-action-row {
                display: flex;
                gap: 8px;
                flex-wrap: wrap;
                margin-top: 12px;
            }

            #competitionPage .competition-action-row button {
                flex: 1;
                min-width: 130px;
            }

            #competitionPage .competition-stage {
                border: 1px solid rgba(255,255,255,.09);
                border-radius: 14px;
                padding: 14px;
                margin-top: 12px;
                background: rgba(255,255,255,.025);
            }

            #competitionPage .competition-stage-header {
                display: flex;
                justify-content: space-between;
                align-items: flex-start;
                gap: 10px;
            }

            #competitionPage .competition-stage-header h3 {
                margin: 0;
            }

            #competitionPage .competition-meta {
                display: grid;
                grid-template-columns: repeat(2, minmax(0, 1fr));
                gap: 8px;
                margin-top: 12px;
            }

            #competitionPage .competition-meta-box {
                background: rgba(255,255,255,.04);
                border-radius: 10px;
                padding: 9px;
            }

            #competitionPage .competition-meta-box small {
                display: block;
                opacity: .6;
                margin-bottom: 3px;
            }

            #competitionPage .competition-secret {
                margin-top: 12px;
                padding: 10px;
                border-radius: 10px;
                background: rgba(255,190,0,.07);
                border: 1px solid rgba(255,190,0,.12);
            }

            #competitionPage .competition-secret strong {
                display: block;
                margin-top: 4px;
            }

            #competitionPage .competition-form-grid {
                display: grid;
                grid-template-columns: repeat(2, minmax(0, 1fr));
                gap: 10px;
            }

            #competitionPage .competition-form-full {
                grid-column: 1 / -1;
            }

            #competitionPage .competition-help {
                font-size: 12px;
                opacity: .65;
                line-height: 1.4;
                margin-top: 5px;
            }

            #competitionPage .competition-empty {
                text-align: center;
                padding: 25px 12px;
                opacity: .65;
            }

            #competitionPage .competition-round-card {
                border: 1px solid rgba(255,255,255,.08);
                border-radius: 14px;
                padding: 14px;
                margin-bottom: 10px;
            }

            #competitionPage .competition-round-card h3 {
                margin: 0 0 5px;
            }

            #competitionPage .competition-round-top {
                display: flex;
                justify-content: space-between;
                gap: 10px;
                align-items: flex-start;
            }

            #competitionPage .competition-status {
                font-size: 11px;
                padding: 5px 8px;
                border-radius: 999px;
                background: rgba(255,255,255,.08);
                white-space: nowrap;
            }

            #competitionPage .competition-warning {
                margin-top: 10px;
                padding: 10px;
                border-radius: 10px;
                background: rgba(255,80,80,.08);
                border: 1px solid rgba(255,80,80,.12);
            }

            #competitionPage .competition-success {
                margin-top: 10px;
                padding: 10px;
                border-radius: 10px;
                background: rgba(80,220,120,.08);
                border: 1px solid rgba(80,220,120,.12);
            }

            #competitionPage .competition-edit-panel {
                margin-top: 12px;
                border-top: 1px solid rgba(255,255,255,.08);
                padding-top: 12px;
            }

            #competitionPage .competition-participant {
                display: flex;
                justify-content: space-between;
                gap: 10px;
                align-items: center;
                padding: 9px 0;
                border-bottom: 1px solid rgba(255,255,255,.06);
            }

            #competitionPage .competition-participant:last-child {
                border-bottom: 0;
            }

            @media (max-width: 600px) {
                #competitionPage .competition-form-grid {
                    grid-template-columns: 1fr;
                }

                #competitionPage .competition-form-full {
                    grid-column: auto;
                }

                #competitionPage .competition-meta {
                    grid-template-columns: 1fr 1fr;
                }
            }
        `;

        document.head.appendChild(style);
    }

    function addUI() {
        if (document.getElementById("competitionPage")) return;

        const main = document.querySelector("main");
        const nav = document.querySelector(".bottom-nav");

        if (!main || !nav) return;

        addStyles();

        const page = document.createElement("section");
        page.id = "competitionPage";
        page.className = "page";

        page.innerHTML = `
            <div class="page-title">
                <div>
                    <h1> Competitions</h1>
                    <p>Manage games, rounds, stages, players and winners</p>
                </div>
            </div>

            <div class="panel">
                <div class="competition-tabs" id="competitionGameTabs"></div>
            </div>

            <div class="panel">
                <div id="competitionGameHeader"></div>
            </div>

            <div class="panel">
                <div class="panel-header">
                    <h2>Rounds</h2>
                    <button class="secondary-btn" onclick="competitionLoadRounds()">REFRESH</button>
                </div>

                <div id="competitionRoundsList">
                    loading…
                </div>
            </div>

            <div class="panel hidden" id="competitionRoundDetailPanel">
                <div class="panel-header">
                    <h2>Manage Round</h2>
                    <button class="secondary-btn" onclick="competitionLoadRound(currentRoundId)">REFRESH</button>
                </div>

                <div id="competitionRoundDetail">
                    loading…
                </div>
            </div>
        `;

        main.appendChild(page);

        const navButton = document.createElement("button");
        navButton.className = "nav-item";
        navButton.innerHTML = `<span></span>Competitions`;
        navButton.onclick = window.showCompetitionAdmin;

        if (nav.lastElementChild) {
            nav.insertBefore(navButton, nav.lastElementChild);
        } else {
            nav.appendChild(navButton);
        }

        renderGameTabs();
        renderGameHeader();
    }

    function renderGameTabs() {
        const box = document.getElementById("competitionGameTabs");
        if (!box) return;

        box.innerHTML = Object.entries(GAMES).map(([id, game]) => `
            <button
                class="competition-tab ${selectedGame === id ? "active" : ""}"
                onclick="competitionSelectGame('${id}')"
            >
                ${game.emoji} ${h(game.name)}
                <small>${h(game.description)}</small>
            </button>
        `).join("");
    }

    function renderGameHeader() {
        const box = document.getElementById("competitionGameHeader");
        if (!box) return;

        const game = gameInfo(selectedGame);

        box.innerHTML = `
            <div class="competition-game-header">
                <div>
                    <h2>${game.emoji} ${h(game.name)}</h2>
                    <p>${h(game.description)}</p>
                </div>

                <span class="badge">
                    ${game.staged ? "7 STAGES" : "OPEN ROUND"}
                </span>
            </div>

            <div class="competition-action-row">
                <button class="primary-btn" onclick="competitionOpenCreateRound()">
                    ➕ CREATE ROUND
                </button>

                <button class="secondary-btn" onclick="competitionInitializeGames()">
                    ️ INITIALIZE
                </button>
            </div>

            <div class="competition-help">
                initialization only creates/repairs the six competition game definitions.
                it does not create questions, rounds or winners.
            </div>
        `;
    }

    window.showCompetitionAdmin = function () {
        addUI();

        document.querySelectorAll(".page").forEach(page => {
            page.classList.remove("active");
        });

        const page = document.getElementById("competitionPage");

        if (page) {
            page.classList.add("active");
        }

        document.querySelectorAll(".nav-item").forEach(button => {
            button.classList.remove("active");
        });

        const buttons = document.querySelectorAll(".nav-item");

        if (buttons.length >= 2) {
            buttons[buttons.length - 2]?.classList.add("active");
        }

        competitionLoadRounds();
    };

    window.competitionSelectGame = function (gameId) {
        if (!GAMES[gameId]) return;

        selectedGame = gameId;
        currentRoundId = null;

        const detailPanel = document.getElementById("competitionRoundDetailPanel");

        if (detailPanel) {
            detailPanel.classList.add("hidden");
        }

        renderGameTabs();
        renderGameHeader();
        competitionLoadRounds();
    };

    window.competitionInitializeGames = async function () {
        try {
            const data = await api("/api/competition/admin/setup-games", {
                method: "POST",
                body: JSON.stringify({})
            });

            showToast(
                data.message ||
                "Competition games initialized successfully."
            );

            await competitionLoadRounds();
        } catch (error) {
            showToast(error.message || "Unable to initialize games.");
        }
    };

    /*
     * ------------------------------------------------------------
     * CREATE ROUND
     * ------------------------------------------------------------
     */

    window.competitionOpenCreateRound = function () {
        const list = document.getElementById("competitionRoundsList");

        if (!list) return;

        const game = gameInfo(selectedGame);

        const defaultFees = game.staged
            ? "10,10,10,10,10,10,30"
            : "10";

        list.innerHTML = `
            <div class="panel">
                <div class="panel-header">
                    <h2>➕ Create ${h(game.name)} Round</h2>
                    <button
                        class="secondary-btn"
                        onclick="competitionLoadRounds()"
                    >
                        CANCEL
                    </button>
                </div>

                <div class="competition-form-grid">

                    <div class="competition-form-full">
                        <label>Round Title</label>
                        <input
                            id="compRoundTitle"
                            placeholder="${h(game.name)} - September Week 1"
                        >
                    </div>

                    <div>
                        <label>Prize Pool (USD)</label>
                        <input
                            id="compRoundPrize"
                            type="number"
                            min="0"
                            step="0.01"
                            value="10"
                        >
                    </div>

                    <div>
                        <label>Round Start</label>
                        <input
                            id="compRoundStart"
                            type="datetime-local"
                        >
                    </div>

                    <div class="competition-form-full">
                        <label>
                            entry Fees
                        </label>

                        <input
                            id="compRoundFees"
                            value="${defaultFees}"
                        >

                        <div class="competition-help">
                            ${game.staged
                                ? "Stage 1-6 default to 10 points. Stage 7 defaults to 30 points."
                                : "Single entry fee for this round."}
                        </div>
                    </div>

                    <div class="competition-form-full">
                        <button
                            class="primary-btn full"
                            onclick="competitionCreateRound()"
                        >
                            CREATE ${game.name.toUpperCase()} ROUND
                        </button>
                    </div>

                </div>
            </div>
        `;
    };

    function parseFees(value, staged) {
        const fees = String(value || "")
            .split(",")
            .map(item => Number(item.trim()))
            .filter(item => Number.isFinite(item) && item >= 0);

        if (!fees.length) {
            return staged
                ? [10, 10, 10, 10, 10, 10, 30]
                : [10];
        }

        return fees;
    }

    function localIso(id) {
        const value = document.getElementById(id)?.value;

        if (!value) return null;

        return new Date(value).toISOString();
    }

    window.competitionCreateRound = async function () {
        try {
            const game = gameInfo(selectedGame);

            const title =
                document.getElementById("compRoundTitle")?.value.trim() ||
                `${game.name} Round`;

            const prize =
                Number(
                    document.getElementById("compRoundPrize")?.value || 0
                );

            const fees = parseFees(
                document.getElementById("compRoundFees")?.value,
                game.staged
            );

            const startAt = localIso("compRoundStart");

            const data = await api(
                "/api/competition/admin/rounds/create",
                {
                    method: "POST",
                    body: JSON.stringify({
                        game_id: selectedGame,
                        title,
                        prize_pool_usd: prize,
                        entry_fees: fees,
                        start_at: startAt
                    })
                }
            );

            showToast(
                data.message ||
                `Round created: ${data.round_id}`
            );

            currentRoundId = data.round_id;

            await competitionLoadRounds();
            await competitionLoadRound(currentRoundId);

        } catch (error) {
            showToast(
                error.message ||
                "Unable to create competition round."
            );
        }
    };

    /*
     * ------------------------------------------------------------
     * LOAD ROUNDS
     * ------------------------------------------------------------
     */

    window.competitionLoadRounds = async function () {
        addUI();

        const list =
            document.getElementById("competitionRoundsList");

        if (!list) return;

        list.innerHTML = `
            <div class="competition-empty">
                loading ${h(gameInfo(selectedGame).name)} rounds…
            </div>
        `;

        try {
            const data = await api(
                `/api/competition/admin/rounds?game_id=${encodeURIComponent(selectedGame)}`
            );

            let rounds = data.rounds || [];

            /*
             * Compatibility fallback:
             * If backend returns all rounds regardless of game_id,
             * filter them here.
             */
            rounds = rounds.filter(
                round => !round.game_id || round.game_id === selectedGame
            );

            if (!rounds.length) {
                list.innerHTML = `
                    <div class="competition-empty">
                        <div style="font-size:32px;">
                            ${gameInfo(selectedGame).emoji}
                        </div>

                        <p>
                            no ${h(gameInfo(selectedGame).name)}
                            rounds yet.
                        </p>

                        <button
                            class="primary-btn"
                            onclick="competitionOpenCreateRound()"
                        >
                            CREATE FIRST ROUND
                        </button>
                    </div>
                `;

                return;
            }

            list.innerHTML = rounds.map(round => {
                const game = gameInfo(round.game_id || selectedGame);

                return `
                    <div class="competition-round-card">

                        <div class="competition-round-top">

                            <div>
                                <h3>
                                    ${game.emoji}
                                    ${h(round.title || game.name)}
                                </h3>

                                <p>
                                    ${h(round.game_id || selectedGame)}
                                </p>
                            </div>

                            <span class="competition-status">
                                ${h(round.status || "draft")}
                            </span>

                        </div>

                        <div class="competition-meta">

                            <div class="competition-meta-box">
                                <small>Prize Pool</small>
                                <strong>
                                    $${Number(
                                        round.prize_pool_usd || 0
                                    ).toFixed(2)}
                                </strong>
                            </div>

                            <div class="competition-meta-box">
                                <small>Stage</small>
                                <strong>
                                    ${Number(round.current_stage || 1)}
                                    /
                                    ${Number(round.total_stages || 1)}
                                </strong>
                            </div>

                            <div class="competition-meta-box">
                                <small>Winners</small>
                                <strong>
                                    ${Number(round.winner_count || 0)}
                                </strong>
                            </div>

                            <div class="competition-meta-box">
                                <small>Round ID</small>
                                <strong>
                                    ${h(round.id || "")}
                                </strong>
                            </div>

                        </div>

                        <div class="competition-action-row">

                            <button
                                class="primary-btn"
                                onclick="competitionLoadRound('${h(round.id)}')"
                            >
                                OPEN / MANAGE
                            </button>

                        </div>

                    </div>
                `;
            }).join("");

        } catch (error) {
            list.innerHTML = `
                <div class="competition-warning">
                    ${h(error.message)}
                </div>
            `;
        }
    };

    /*
     * ------------------------------------------------------------
     * LOAD ROUND DETAIL
     * ------------------------------------------------------------
     */

    window.competitionLoadRound = async function (roundId) {
        addUI();

        currentRoundId = roundId;

        const panel =
            document.getElementById("competitionRoundDetailPanel");

        const box =
            document.getElementById("competitionRoundDetail");

        if (!panel || !box) return;

        panel.classList.remove("hidden");

        box.innerHTML = `
            <div class="competition-empty">
                loading round…
            </div>
        `;

        try {
            const data = await api(
                `/api/competition/admin/rounds/${encodeURIComponent(roundId)}`
            );

            const round = data.round || {};
            const stages = data.stages || [];
            const entries = data.entries || [];
            const results = data.results || [];

            selectedGame = round.game_id || selectedGame;

            renderGameTabs();
            renderGameHeader();

            let html = renderRoundSummary(round);

            if (!stages.length) {
                html += `
                    <div class="panel">
                        <div class="competition-empty">
                            no stages have been created yet.
                        </div>

                        <button
                            class="primary-btn full"
                            onclick="competitionOpenStageEditor('${h(round.id)}', 1)"
                        >
                            CREATE FIRST STAGE
                        </button>
                    </div>
                `;
            } else {

                html += `
                    <div class="panel">
                        <h2>Stages</h2>
                    </div>
                `;

                for (const stage of stages) {
                    html += renderStageCard(round, stage);
                }

                /*
                 * Only allow the next stage to be prepared after
                 * the current stage is closed/settled.
                 */
                const currentStageNo =
                    Number(round.current_stage || 1);

                const totalStages =
                    Number(round.total_stages || 1);

                const currentStage =
                    stages.find(
                        stage =>
                            Number(stage.stage_no) === currentStageNo
                    );

                const nextStageNo = currentStageNo + 1;

                const nextStageExists =
                    stages.some(
                        stage =>
                            Number(stage.stage_no) === nextStageNo
                    );

                if (
                    currentStage &&
                    currentStage.status === "closed" &&
                    nextStageNo <= totalStages &&
                    !nextStageExists
                ) {
                    html += `
                        <div class="panel">
                            <h3>Next Stage</h3>

                            <p>
                                stage ${currentStageNo} has closed.
                                you can now prepare Stage ${nextStageNo}.
                            </p>

                            <button
                                class="primary-btn full"
                                onclick="competitionPrepareNextStage('${h(round.id)}')"
                            >
                                PREPARE STAGE ${nextStageNo}
                            </button>
                        </div>
                    `;
                }
            }

            html += renderParticipants(entries, round);
            html += renderResults(results);

            box.innerHTML = html;

        } catch (error) {

            box.innerHTML = `
                <div class="competition-warning">
                    ${h(error.message)}
                </div>
            `;
        }
    };

    function renderRoundSummary(round) {
        const game = gameInfo(round.game_id);

        return `
            <div class="panel">

                <div class="competition-game-header">

                    <div>
                        <h2>
                            ${game.emoji}
                            ${h(round.title || game.name)}
                        </h2>

                        <p>
                            ${h(game.name)}
                        </p>
                    </div>

                    <span class="competition-status">
                        ${h(round.status || "draft")}
                    </span>

                </div>

                <div class="competition-meta">

                    <div class="competition-meta-box">
                        <small>Prize Pool</small>
                        <strong>
                            $${Number(
                                round.prize_pool_usd || 0
                            ).toFixed(2)}
                        </strong>
                    </div>

                    <div class="competition-meta-box">
                        <small>Current Stage</small>
                        <strong>
                            ${Number(round.current_stage || 1)}
                            /
                            ${Number(round.total_stages || 1)}
                        </strong>
                    </div>

                    <div class="competition-meta-box">
                        <small>Participants</small>
                        <strong>
                            ${Number(round.participant_count || 0)}
                        </strong>
                    </div>

                    <div class="competition-meta-box">
                        <small>Winners</small>
                        <strong>
                            ${Number(round.winner_count || 0)}
                        </strong>
                    </div>

                </div>

                ${
                    round.status === "settled"
                        ? `
                            <div class="competition-success">
                                 this competition has been concluded.
                                winners have been recorded.
                            </div>
                        `
                        : ""
                }

            </div>
        `;
    }

    /*
     * ------------------------------------------------------------
     * STAGE CARD
     * ------------------------------------------------------------
     */

    function renderStageCard(round, stage) {
        const gameId = round.game_id;

        const stageNo =
            Number(stage.stage_no || 1);

        const status =
            String(stage.status || "draft");

        const editable =
            status === "draft" ||
            status === "scheduled";

        let secret = "";

        if (
            gameId === "guess_it" ||
            gameId === "impossible_question"
        ) {
            secret = `
                correct answer:
                <strong>
                    ${h(stage.correct_answer || "NOT SET")}
                </strong>
            `;
        } else if (gameId === "survivor") {
            secret = `
                safe option:
                <strong>
                    ${h(stage.safe_option || "NOT SET")}
                </strong>
            `;
        } else if (gameId === "dead_number") {
            const deadNumbers =
                Array.isArray(stage.dead_numbers)
                    ? stage.dead_numbers.join(", ")
                    : "";

            secret = `
                dead numbers:
                <strong>
                    ${h(deadNumbers || "NOT SET")}
                </strong>
            `;
        } else {
            secret = `
                outcome:
                <strong>
                    calculated from player choices
                </strong>
            `;
        }

        let buttons = "";

        /*
         * EDIT
         *
         * Editing is allowed before a stage becomes live.
         */
        if (editable) {
            buttons += `
                <button
                    class="secondary-btn"
                    onclick="competitionEditStage('${h(round.id)}', ${stageNo})"
                >
                    ✏️ EDIT
                </button>
            `;
        }

        /*
         * APPROVE
         */
        if (
            !stage.secret_approved &&
            status !== "live" &&
            status !== "closed"
        ) {
            buttons += `
                <button
                    class="primary-btn"
                    onclick="competitionApproveStage('${h(round.id)}', ${stageNo})"
                >
                     APPROVE SECRET
                </button>
            `;
        }

        /*
         * START
         */
        if (
            (status === "draft" || status === "scheduled") &&
            stage.secret_approved
        ) {
            buttons += `
                <button
                    class="primary-btn"
                    onclick="competitionStartStage('${h(round.id)}', ${stageNo})"
                >
                     START STAGE
                </button>
            `;
        }

        /*
         * If not approved, explicitly tell Admin why it cannot start.
         */
        if (
            (status === "draft" || status === "scheduled") &&
            !stage.secret_approved
        ) {
            buttons += `
                <div class="competition-warning">
                    ️ This stage cannot start until the actual
                    answer/safe value/dead numbers have been approved.
                </div>
            `;
        }

        /*
         * END / SETTLE
         */
        if (status === "live") {
            buttons += `
                <button
                    class="danger-btn"
                    onclick="competitionEndStage('${h(round.id)}', ${stageNo})"
                >
                     END / SETTLE STAGE
                </button>
            `;
        }

        /*
         * CLOSED STAGE
         */
        if (status === "closed") {
            buttons += `
                <div class="competition-success">
                    ✅ Stage concluded.
                    player outcomes have been calculated.
                </div>
            `;
        }

        /*
         * LIVE STAGE
         */
        if (status === "live") {
            buttons += `
                <div class="competition-warning">
                    🔴 This stage is LIVE.
                    editing is disabled while players are participating.
                </div>
            `;
        }

        return `
            <div class="panel competition-stage">

                <div class="competition-stage-header">

                    <div>
                        <h3>
                            stage ${stageNo}
${h(stage.title || "Untitled")}
                        </h3>

                        <p>
                            ${h(status.toUpperCase())}
                        </p>
                    </div>

                    <span class="competition-status">
                        ${h(status)}
                    </span>

                </div>

                <div class="competition-meta">

                    <div class="competition-meta-box">
                        <small>Entry</small>
                        <strong>
                            ${Number(stage.entry_fee || 0)}
                            points
                        </strong>
                    </div>

                    <div class="competition-meta-box">
                        <small>Approval</small>
                        <strong>
                            ${
                                stage.secret_approved
                                    ? "APPROVED"
                                    : "NOT APPROVED"
                            }
                        </strong>
                    </div>

                    <div class="competition-meta-box">
                        <small>Start</small>
                        <strong>
                            ${h(formatDate(stage.start_at))}
                        </strong>
                    </div>

                    <div class="competition-meta-box">
                        <small>End</small>
                        <strong>
                            ${h(formatDate(stage.end_at))}
                        </strong>
                    </div>

                </div>

                ${
                    stage.question
                        ? `
                            <div class="competition-secret">
                                <span>Question / Prompt</span>
                                <strong>
                                    ${h(stage.question)}
                                </strong>
                            </div>
                        `
                        : `
                            <div class="competition-warning">
                                ️ No question/prompt has been entered.
                            </div>
                        `
                }

                ${
                    stage.clue
                        ? `
                            <div class="competition-secret">
                                <span>Clue</span>
                                <strong>
                                    ${h(stage.clue)}
                                </strong>
                            </div>
                        `
                        : ""
                }

                <div class="competition-secret">
                    <span> Private Admin Secret</span>
                    ${secret}
                </div>

                ${
                    Array.isArray(stage.options) &&
                    stage.options.length
                        ? `
                            <div class="competition-secret">
                                <span>Options</span>
                                <strong>
                                    ${h(stage.options.join(" · "))}
                                </strong>
                            </div>
                        `
                        : ""
                }

                ${
                    status === "closed"
                        ? `
                            <div class="competition-result-summary">
                                <div class="competition-secret">
                                    <span>
                                        ${
                                            stageNo <
                                            Number(round.total_stages || 1)
                                                ? "Correct Answer / Stage Outcome"
                                                : "Final Answer / Stage Outcome"
                                        }
                                    </span>

                                    <strong>
                                        ${secret}
                                    </strong>
                                </div>

                                <div class="competition-meta">
                                    <div class="competition-meta-box">
                                        <small>
                                            ${
                                                stageNo <
                                                Number(round.total_stages || 1)
                                                    ? "Players Advanced"
                                                    : "Final Winners"
                                            }
                                        </small>

                                        <strong>
                                            ${Number(
                                                stage.advanced_count ??
                                                stage.winner_count ??
                                                0
                                            )}
                                        </strong>
                                    </div>
                                </div>

                                <div class="competition-success">
                                    🔒 Only the total is shown. Individual
                                    player contact details are hidden.
                                </div>
                            </div>
                        `
                        : ""
                }

                <div class="competition-action-row">
                    ${buttons}
                </div>

                <div
                    id="competitionEditStage_${stageNo}"
                    class="competition-edit-panel hidden"
                ></div>

            </div>
        `;
    }

    function formatDate(value) {
        if (!value) return "-";

        try {
            return new Date(value).toLocaleString();
        } catch {
            return String(value);
        }
    }

    /*
     * ------------------------------------------------------------
     * STAGE EDITOR
     * ------------------------------------------------------------
     */

    window.competitionEditStage = async function (roundId, stageNo) {
        try {
            const data = await api(
                `/api/competition/admin/rounds/${encodeURIComponent(roundId)}`
            );

            const round = data.round || {};
            const stage = (data.stages || []).find(
                item =>
                    Number(item.stage_no) === Number(stageNo)
            );

            if (!stage) {
                showToast("Stage not found.");
                return;
            }

            if (
                stage.status === "live" ||
                stage.status === "closed"
            ) {
                showToast(
                    "This stage can no longer be edited."
                );
                return;
            }

            const container =
                document.getElementById(
                    `competitionEditStage_${stageNo}`
                );

            if (!container) return;

            container.classList.remove("hidden");

            container.innerHTML =
                renderStageEditor(round, stage);

        } catch (error) {
            showToast(error.message);
        }
    };

    function renderStageEditor(round, stage) {
        const gameId = round.game_id;

        const options =
            Array.isArray(stage.options)
                ? stage.options.join(", ")
                : "";

        const accepted =
            Array.isArray(stage.accepted_answers)
                ? stage.accepted_answers.join(", ")
                : "";

        const dead =
            Array.isArray(stage.dead_numbers)
                ? stage.dead_numbers.join(", ")
                : "";

        return `
            <div class="panel">

                <div class="panel-header">
                    <h3>
                        ✏️ Edit Stage ${Number(stage.stage_no)}
                    </h3>

                    <button
                        class="secondary-btn"
                        onclick="competitionCloseStageEditor(${Number(stage.stage_no)})"
                    >
                        CLOSE
                    </button>
                </div>

                <div class="competition-form-grid">

                    <div class="competition-form-full">
                        <label>Stage Title</label>
                        <input
                            id="editStageTitle_${Number(stage.stage_no)}"
                            value="${h(stage.title || "")}"
                        >
                    </div>

                    <div class="competition-form-full">
                        <label>Question / Prompt</label>
                        <textarea
                            id="editStageQuestion_${Number(stage.stage_no)}"
                            placeholder="Enter the actual challenge"
                        >${h(stage.question || "")}</textarea>
                    </div>

                    <div>
                        <label>Entry Fee</label>
                        <input
                            id="editStageFee_${Number(stage.stage_no)}"
                            type="number"
                            min="0"
                            value="${Number(stage.entry_fee || 0)}"
                        >
                    </div>

                    <div>
                        <label>Start Time</label>
                        <input
                            id="editStageStart_${Number(stage.stage_no)}"
                            type="datetime-local"
                            value="${toLocalDateTime(stage.start_at)}"
                        >
                    </div>

                    <div>
                        <label>End Time</label>
                        <input
                            id="editStageEnd_${Number(stage.stage_no)}"
                            type="datetime-local"
                            value="${toLocalDateTime(stage.end_at)}"
                        >
                    </div>

                    <div class="competition-form-full">
                        <label>Clue (Optional)</label>
                        <textarea
                            id="editStageClue_${Number(stage.stage_no)}"
                            placeholder="Optional clue"
                        >${h(stage.clue || "")}</textarea>
                    </div>

                    <div class="competition-form-full">
                        <label>Options (comma separated)</label>
                        <textarea
                            id="editStageOptions_${Number(stage.stage_no)}"
                        >${h(options)}</textarea>
                    </div>

                    ${
                        gameId === "guess_it" ||
                        gameId === "impossible_question"
                            ? `
                                <div class="competition-form-full">
                                    <label>Correct Answer</label>
                                    <input
                                        id="editStageCorrect_${Number(stage.stage_no)}"
                                        value="${h(stage.correct_answer || "")}"
                                    >
                                </div>

                                <div class="competition-form-full">
                                    <label>
                                        accepted Answers
                                        (comma separated)
                                    </label>

                                    <input
                                        id="editStageAccepted_${Number(stage.stage_no)}"
                                        value="${h(accepted)}"
                                    >
                                </div>
                            `
                            : ""
                    }

                    ${
                        gameId === "survivor"
                            ? `
                                <div class="competition-form-full">
                                    <label>Safe Option</label>
                                    <input
                                        id="editStageSafe_${Number(stage.stage_no)}"
                                        value="${h(stage.safe_option || "")}"
                                    >
                                </div>
                            `
                            : ""
                    }

                    ${
                        gameId === "dead_number"
                            ? `
                                <div class="competition-form-full">
                                    <label>
                                        dead Numbers
                                        (comma separated)
                                    </label>

                                    <input
                                        id="editStageDead_${Number(stage.stage_no)}"
                                        value="${h(dead)}"
                                    >
                                </div>

                                <div>
                                    <label>Dead Count</label>
                                    <input
                                        id="editStageDeadCount_${Number(stage.stage_no)}"
                                        type="number"
                                        min="1"
                                        value="${Number(stage.dead_count || 1)}"
                                    >
                                </div>
                            `
                            : ""
                    }

                    <div>
                        <label>Minimum Number</label>
                        <input
                            id="editStageMin_${Number(stage.stage_no)}"
                            type="number"
                            value="${Number(stage.min_number || 1)}"
                        >
                    </div>

                    <div>
                        <label>Maximum Number</label>
                        <input
                            id="editStageMax_${Number(stage.stage_no)}"
                            type="number"
                            value="${Number(stage.max_number || 20)}"
                        >
                    </div>

                    ${
                        gameId === "impossible_choice"
                            ? `
                                <div class="competition-form-full">

                                    <label>
                                        impossible Choice Mechanic
                                    </label>

                                    <select
                                        id="editStageMechanic_${Number(stage.stage_no)}"
                                    >
                                        <option value="minority"
                                            ${stage.mechanic === "minority" ? "selected" : ""}>
                                            minority
                                        </option>

                                        <option value="majority"
                                            ${stage.mechanic === "majority" ? "selected" : ""}>
                                            majority
                                        </option>

                                        <option value="closest_target"
                                            ${stage.mechanic === "closest_target" ? "selected" : ""}>
                                            closest to target percentage
                                        </option>

                                        <option value="within_range"
                                            ${stage.mechanic === "within_range" ? "selected" : ""}>
                                            within target percentage range
                                        </option>
                                    </select>

                                </div>

                                <div>
                                    <label>Target %</label>
                                    <input
                                        id="editStageTarget_${Number(stage.stage_no)}"
                                        type="number"
                                        step="0.1"
                                        value="${Number(stage.target_percentage || 50)}"
                                    >
                                </div>

                                <div>
                                    <label>Target Minimum %</label>
                                    <input
                                        id="editStageTargetMin_${Number(stage.stage_no)}"
                                        type="number"
                                        step="0.1"
                                        value="${Number(stage.target_min_percentage || 40)}"
                                    >
                                </div>

                                <div>
                                    <label>Target Maximum %</label>
                                    <input
                                        id="editStageTargetMax_${Number(stage.stage_no)}"
                                        type="number"
                                        step="0.1"
                                        value="${Number(stage.target_max_percentage || 60)}"
                                    >
                                </div>
                            `
                            : ""
                    }

                    <div class="competition-form-full">

                        <div class="competition-warning">
                            ️ Saving changes resets secret approval.
                            you must review and approve the actual
                            answer/safe option/dead numbers again
                            before starting the stage.
                        </div>

                    </div>

                    <div class="competition-form-full">

                        <button
                            class="primary-btn full"
                            onclick="competitionSaveStage('${h(round.id)}', ${Number(stage.stage_no)})"
                        >
                             SAVE STAGE CHANGES
                        </button>

                    </div>

                </div>

            </div>
        `;
    }

    function toLocalDateTime(value) {
        if (!value) return "";

        try {
            const date = new Date(value);

            const pad = n =>
                String(n).padStart(2, "0");

            return (
                `${date.getFullYear()}-` +
                `${pad(date.getMonth() + 1)}-` +
                `${pad(date.getDate())}T` +
                `${pad(date.getHours())}:` +
                `${pad(date.getMinutes())}`
            );
        } catch {
            return "";
        }
    }

    window.competitionCloseStageEditor = function (stageNo) {
        const container =
            document.getElementById(
                `competitionEditStage_${stageNo}`
            );

        if (container) {
            container.classList.add("hidden");
            container.innerHTML = "";
        }
    };

    window.competitionSaveStage = async function (
        roundId,
        stageNo
    ) {
        try {
            const getValue = id =>
                document.getElementById(id)?.value?.trim() || "";

            const getNumber = id =>
                Number(
                    document.getElementById(id)?.value || 0
                );

            const splitList = id =>
                getValue(id)
                    .split(",")
                    .map(item => item.trim())
                    .filter(Boolean);

            const payload = {
                title:
                    getValue(`editStageTitle_${stageNo}`),

                question:
                    getValue(`editStageQuestion_${stageNo}`),

                entry_fee:
                    getNumber(`editStageFee_${stageNo}`),

                start_at:
                    toIsoFromInput(
                        `editStageStart_${stageNo}`
                    ),

                end_at:
                    toIsoFromInput(
                        `editStageEnd_${stageNo}`
                    ),

                clue:
                    getValue(`editStageClue_${stageNo}`),

                options:
                    splitList(`editStageOptions_${stageNo}`),

                correct_answer:
                    getValue(`editStageCorrect_${stageNo}`),

                accepted_answers:
                    splitList(`editStageAccepted_${stageNo}`),

                safe_option:
                    getValue(`editStageSafe_${stageNo}`),

                min_number:
                    getNumber(`editStageMin_${stageNo}`),

                max_number:
                    getNumber(`editStageMax_${stageNo}`),

                dead_numbers:
                    splitList(`editStageDead_${stageNo}`),

                dead_count:
                    getNumber(`editStageDeadCount_${stageNo}`),

                mechanic:
                    getValue(`editStageMechanic_${stageNo}`),

                target_percentage:
                    getNumber(`editStageTarget_${stageNo}`),

                target_min_percentage:
                    getNumber(`editStageTargetMin_${stageNo}`),

                target_max_percentage:
                    getNumber(`editStageTargetMax_${stageNo}`)
            };

            if (!payload.question) {
                showToast(
                    "Please enter the question/prompt."
                );
                return;
            }

            const data = await api(
                `/api/competition/admin/rounds/${encodeURIComponent(roundId)}/stages/${stageNo}/edit`,
                {
                    method: "POST",
                    body: JSON.stringify(payload)
                }
            );

            showToast(
                data.message ||
                "Stage updated successfully."
            );

            await competitionLoadRound(roundId);

        } catch (error) {
            showToast(
                error.message ||
                "Unable to save stage."
            );
        }
    };

    function toIsoFromInput(id) {
        const value =
            document.getElementById(id)?.value;

        if (!value) return null;

        return new Date(value).toISOString();
    }

    /*
     * ------------------------------------------------------------
     * CREATE STAGE
     * ------------------------------------------------------------
     */

    window.competitionPrepareNextStage = async function (roundId) {
        try {
            const data = await api(
                `/api/competition/admin/rounds/${encodeURIComponent(roundId)}/next-stage`,
                {
                    method: "POST"
                }
            );

            showToast(
                data.message ||
                `Stage ${data.next_stage} is ready.`
            );

            await competitionLoadRound(roundId);

        } catch (error) {
            showToast(
                error.message ||
                "Unable to prepare next stage."
            );
        }
    };

    window.competitionOpenStageEditor = function (
        roundId,
        stageNo
    ) {
        const box =
            document.getElementById("competitionRoundDetail");

        if (!box) return;

        const roundTitle =
            document.querySelector(
                "#competitionRoundDetail h2"
            );

        /*
         * Open a compact new-stage editor at the bottom.
         */
        const existing =
            document.getElementById(
                "competitionNewStageEditor"
            );

        if (existing) {
            existing.scrollIntoView({
                behavior: "smooth"
            });
            return;
        }

        const panel =
            document.createElement("div");

        panel.id =
            "competitionNewStageEditor";

        panel.className =
            "panel";

        panel.innerHTML =
            renderNewStageEditor(
                roundId,
                stageNo
            );

        box.appendChild(panel);

        panel.scrollIntoView({
            behavior: "smooth"
        });
    };

    function renderNewStageEditor(roundId, stageNo) {
        const gameId = selectedGame;

        const fee =
            stageNo === 7
                ? 30
                : 10;

        return `
            <div class="panel-header">
                <h2>
                    ➕ Create Stage ${Number(stageNo)}
                </h2>

                <button
                    class="secondary-btn"
                    onclick="document.getElementById('competitionNewStageEditor')?.remove()"
                >
                    CANCEL
                </button>
            </div>

            <div class="competition-warning">
                future stages remain private.
                players will not see this stage until you approve
                and start it.
            </div>

            <div class="competition-form-grid">

                <div class="competition-form-full">
                    <label>Stage Title</label>
                    <input
                        id="newStageTitle"
                        value="Day ${Number(stageNo)}"
                    >
                </div>

                <div class="competition-form-full">
                    <label>Question / Prompt</label>
                    <textarea
                        id="newStageQuestion"
                        placeholder="Enter today's challenge"
                    ></textarea>
                </div>

                <div>
                    <label>Entry Fee</label>
                    <input
                        id="newStageFee"
                        type="number"
                        min="0"
                        value="${fee}"
                    >
                </div>

                <div>
                    <label>Start Time</label>
                    <input
                        id="newStageStart"
                        type="datetime-local"
                    >
                </div>

                <div>
                    <label>End Time</label>
                    <input
                        id="newStageEnd"
                        type="datetime-local"
                    >
                </div>

                <div class="competition-form-full">
                    <label>Clue (Optional)</label>
                    <textarea
                        id="newStageClue"
                        placeholder="Optional clue"
                    ></textarea>
                </div>

                <div class="competition-form-full">
                    <label>Options (comma separated)</label>
                    <textarea
                        id="newStageOptions"
                        placeholder="Option A, Option B, Option C"
                    ></textarea>
                </div>

                ${
                    gameId === "guess_it" ||
                    gameId === "impossible_question"
                        ? `
                            <div class="competition-form-full">
                                <label>Correct Answer</label>
                                <input
                                    id="newStageCorrect"
                                    placeholder="Admin-approved answer"
                                >
                            </div>

                            <div class="competition-form-full">
                                <label>
                                    accepted Answers
                                </label>

                                <input
                                    id="newStageAccepted"
                                    placeholder="Answer 1, Answer 2"
                                >
                            </div>
                        `
                        : ""
                }

                ${
                    gameId === "survivor"
                        ? `
                            <div class="competition-form-full">
                                <label>Safe Option</label>
                                <input
                                    id="newStageSafe"
                                    placeholder="Admin-approved safe option"
                                >
                            </div>
                        `
                        : ""
                }

                ${
                    gameId === "dead_number"
                        ? `
                            <div class="competition-form-full">
                                <label>Dead Numbers</label>
                                <input
                                    id="newStageDead"
                                    placeholder="17, 23"
                                >
                            </div>

                            <div>
                                <label>Dead Count</label>
                                <input
                                    id="newStageDeadCount"
                                    type="number"
                                    min="1"
                                    value="3"
                                >
                            </div>
                        `
                        : ""
                }

                <div>
                    <label>Minimum Number</label>
                    <input
                        id="newStageMin"
                        type="number"
                        value="1"
                    >
                </div>

                <div>
                    <label>Maximum Number</label>
                    <input
                        id="newStageMax"
                        type="number"
                        value="20"
                    >
                </div>

                ${
                    gameId === "impossible_choice"
                        ? `
                            <div class="competition-form-full">
                                <label>Mechanic</label>

                                <select id="newStageMechanic">
                                    <option value="minority">
                                        minority
                                    </option>

                                    <option value="majority">
                                        majority
                                    </option>

                                    <option value="closest_target">
                                        closest to target percentage
                                    </option>

                                    <option value="within_range">
                                        within target percentage range
                                    </option>
                                </select>
                            </div>

                            <div>
                                <label>Target %</label>
                                <input
                                    id="newStageTarget"
                                    type="number"
                                    step="0.1"
                                    value="50"
                                >
                            </div>

                            <div>
                                <label>Target Minimum %</label>
                                <input
                                    id="newStageTargetMin"
                                    type="number"
                                    step="0.1"
                                    value="40"
                                >
                            </div>

                            <div>
                                <label>Target Maximum %</label>
                                <input
                                    id="newStageTargetMax"
                                    type="number"
                                    step="0.1"
                                    value="60"
                                >
                            </div>
                        `
                        : ""
                }

                <div class="competition-form-full">
                    <button
                        class="primary-btn full"
                        onclick="competitionCreateStage('${h(roundId)}', ${Number(stageNo)})"
                    >
                        CREATE STAGE
                    </button>
                </div>

            </div>
        `;
    }

    window.competitionCreateStage = async function (
        roundId,
        stageNo
    ) {
        try {
            const getValue = id =>
                document.getElementById(id)?.value?.trim() || "";

            const getNumber = id =>
                Number(
                    document.getElementById(id)?.value || 0
                );

            const splitList = id =>
                getValue(id)
                    .split(",")
                    .map(item => item.trim())
                    .filter(Boolean);

            const question =
                getValue("newStageQuestion");

            if (!question) {
                showToast(
                    "Please enter the question/prompt."
                );
                return;
            }

            const payload = {
                stage_no: Number(stageNo),

                title:
                    getValue("newStageTitle"),

                question,

                entry_fee:
                    getNumber("newStageFee"),

                start_at:
                    toIsoFromInput("newStageStart"),

                end_at:
                    toIsoFromInput("newStageEnd"),

                clue:
                    getValue("newStageClue"),

                generation_mode:
                    "admin",

                options:
                    splitList("newStageOptions"),

                correct_answer:
                    getValue("newStageCorrect"),

                accepted_answers:
                    splitList("newStageAccepted"),

                safe_option:
                    getValue("newStageSafe"),

                min_number:
                    getNumber("newStageMin"),

                max_number:
                    getNumber("newStageMax"),

                dead_numbers:
                    splitList("newStageDead"),

                dead_count:
                    getNumber("newStageDeadCount"),

                mechanic:
                    getValue("newStageMechanic"),

                target_percentage:
                    getNumber("newStageTarget"),

                target_min_percentage:
                    getNumber("newStageTargetMin"),

                target_max_percentage:
                    getNumber("newStageTargetMax")
            };

            const data = await api(
                `/api/competition/admin/rounds/${encodeURIComponent(roundId)}/stages/create`,
                {
                    method: "POST",
                    body: JSON.stringify(payload)
                }
            );

            showToast(
                data.message ||
                "Stage created successfully."
            );

            await competitionLoadRound(roundId);

        } catch (error) {
            showToast(
                error.message ||
                "Unable to create stage."
            );
        }
    };

    /*
     * ------------------------------------------------------------
     * APPROVE SECRET
     * ------------------------------------------------------------
     */

    window.competitionApproveStage = async function (
        roundId,
        stageNo
    ) {
        if (
            !confirm(
                "Approve the actual answer/safe option/dead numbers for this stage?"
            )
        ) {
            return;
        }

        try {
            const data = await api(
                `/api/competition/admin/rounds/${encodeURIComponent(roundId)}/stages/${stageNo}/approve`,
                {
                    method: "POST"
                }
            );

            showToast(
                data.message ||
                "Stage secret approved."
            );

            await competitionLoadRound(roundId);

        } catch (error) {
            showToast(
                error.message ||
                "Unable to approve stage."
            );
        }
    };

    /*
     * ------------------------------------------------------------
     * START STAGE
     * ------------------------------------------------------------
     */

    window.competitionStartStage = async function (
        roundId,
        stageNo
    ) {
        if (
            !confirm(
                "Start this stage now?\n\nPlayers will be able to participate once it is live."
            )
        ) {
            return;
        }

        try {
            const data = await api(
                `/api/competition/admin/rounds/${encodeURIComponent(roundId)}/stages/${stageNo}/start`,
                {
                    method: "POST"
                }
            );

            showToast(
                data.message ||
                "Stage is now live."
            );

            await competitionLoadRound(roundId);

        } catch (error) {
            showToast(
                error.message ||
                "Unable to start stage."
            );
        }
    };

    /*
     * ------------------------------------------------------------
     * END / SETTLE STAGE
     * ------------------------------------------------------------
     */

    window.competitionEndStage = async function (
        roundId,
        stageNo
    ) {
        if (
            !confirm(
                "End and settle this stage now?\n\nSubmitted player entries will be evaluated."
            )
        ) {
            return;
        }

        try {
            const data = await api(
                `/api/competition/admin/rounds/${encodeURIComponent(roundId)}/stages/${stageNo}/end`,
                {
                    method: "POST"
                }
            );

            showToast(
                data.message ||
                `Stage closed. Winners: ${data.winner_count || 0}`
            );

            /*
             * Important:
             * Refresh immediately so Admin sees the concluded
             * state and the results.
             */
            await competitionLoadRound(roundId);

        } catch (error) {
            showToast(
                error.message ||
                "Unable to settle stage."
            );
        }
    };

    /*
     * ------------------------------------------------------------
     * PARTICIPANTS
     * ------------------------------------------------------------
     */

    function renderParticipants(entries, round = {}) {
    const rows = Array.isArray(entries) ? entries : [];
    const limited = rows.slice(0, 100);

    return `
        <div class="panel">
            <div class="panel-header">
                <h2>
                    Participants (${rows.length})
                </h2>
            </div>

            ${
                limited.length
                    ? limited.map(entry => `
                        <div class="competition-participant">
                            <div>
                                <strong>
                                    ${h(
                                        entry.telegram_id ||
                                        entry.user_id ||
                                        "Unknown"
                                    )}
                                </strong>

                                <div style="opacity:.65;font-size:12px;">
                                    Stage ${Number(entry.stage_no || 1)}
                                    · ${h(entry.status || "unknown")}
                                    ${
                                        entry.passed === true
                                            ? " · Advanced"
                                            : entry.eliminated === true
                                                ? " · Eliminated"
                                                : ""
                                    }
                                </div>
                            </div>

                            <div style="text-align:right;">
                                ${
                                    entry.answer !== undefined &&
                                    entry.answer !== null &&
                                    entry.answer !== ""
                                        ? h(String(entry.answer))
                                        : "-"
                                }
                            </div>
                        </div>
                    `).join("")
                    : `
                        <div class="competition-empty">
                            No participants yet.
                        </div>
                    `
            }
        </div>
    `;
    }

    /*
     * ------------------------------------------------------------
     * RESULTS / WINNERS
     * ------------------------------------------------------------
     */

    function renderResults(results) {
        const rows = Array.isArray(results) ? results : [];

        const advanced = rows.filter(
            result => result.advanced === true
        ).length;

        const eliminated = rows.filter(
            result => result.eliminated === true
        ).length;

        const winners = rows.filter(
            result => result.winner === true
        ).length;

        const failed = rows.filter(
            result =>
                result.outcome === "failed" &&
                result.eliminated === true
        ).length;

        return `
            <div class="panel">
                <div class="panel-header">
                    <h2>📊 Results Summary</h2>
                </div>

                <div class="competition-meta">
                    <div class="competition-meta-box">
                        <small>Total Results</small>
                        <strong>${rows.length}</strong>
                    </div>

                    <div class="competition-meta-box">
                        <small>Advanced</small>
                        <strong>${advanced}</strong>
                    </div>

                    <div class="competition-meta-box">
                        <small>Eliminated</small>
                        <strong>${eliminated}</strong>
                    </div>

                    <div class="competition-meta-box">
                        <small>Final Winners</small>
                        <strong>${winners}</strong>
                    </div>
                </div>

                ${
                    failed
                        ? `
                            <div class="competition-warning">
                                ⏰ ${failed} player(s) failed to submit before
                                the stage ended.
                            </div>
                        `
                        : ""
                }

                <div class="competition-success">
                    🔒 Individual Telegram IDs/contact details are not shown
                    in the result summary.
                </div>
            </div>
        `;
    }

    /*
     * ------------------------------------------------------------
     * AUTOMATIC INITIALIZATION
     * ------------------------------------------------------------
     *
     * We no longer force Admin to initialize before doing normal
     * work. If setup is needed, the Initialize button remains
     * available as a repair/setup tool.
     */

    document.addEventListener(
        "DOMContentLoaded",
        function () {
            addUI();

            const section =
                new URLSearchParams(
                    window.location.search
                ).get("section");

            if (section === "competition") {
                setTimeout(
                    window.showCompetitionAdmin,
                    200
                );
            }
        }
    );

})();
(function () {
    const style = document.createElement("style");
    style.textContent = `
        .competition-result-summary {
            margin-top: 14px;
            padding-top: 14px;
            border-top: 1px solid rgba(255,255,255,.08);
        }
        .competition-result-summary .competition-meta {
            margin-top: 10px;
        }
    `;
    document.head.appendChild(style);
})();
