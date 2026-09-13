(function () {
    let currentRoundId = null;

    const stagedGames = [
        "guess_it",
        "survivor",
        "dead_number"
    ];

    function h(v) {
        return escapeHtml(v ?? "");
    }

    function addUI() {
        if (
            document.getElementById(
                "competitionPage"
            )
        ) {
            return;
        }

        const main =
            document.querySelector("main");

        const nav =
            document.querySelector(
                ".bottom-nav"
            );

        if (!main || !nav) return;

        const page =
            document.createElement(
                "section"
            );

        page.id =
            "competitionPage";

        page.className =
            "page";

        page.innerHTML = `
            <div class="page-title">
                <div>
                    <h1>🏆 Competitions</h1>

                    <p>
                        Private round control,
                        stage setup and winner settlement
                    </p>
                </div>
            </div>

            <div class="panel">
                <h2>
                    Initialize Game Controls
                </h2>

                <p>
                    Run this once after installing
                    the new competition engine.
                </p>

                <button
                    class="primary-btn full"
                    onclick="competitionSetupGames()">
                    Initialize Competition Games
                </button>
            </div>

            <div class="panel">
                <h2>
                    Create New Competition Round
                </h2>

                <label>
                    Game
                </label>

                <select
                    id="compRoundGame"
                    onchange="competitionRoundGameChanged()">

                    <option value="guess_it">
                        🎯 Guess It
                    </option>

                    <option value="impossible_question">
                        💀 Impossible Question
                    </option>

                    <option value="crowd_trap">
                        🧠 The Crowd Trap
                    </option>

                    <option value="survivor">
                        🏆 The Survivor
                    </option>

                    <option value="dead_number">
                        ☠️ Dead Number
                    </option>

                    <option value="impossible_choice">
                        🤔 Impossible Choice
                    </option>

                </select>

                <label>
                    Round Title
                </label>

                <input
                    id="compRoundTitle"
                    placeholder="e.g. Guess It — September Week 1"
                >

                <label>
                    Prize Pool (USD)
                </label>

                <input
                    id="compRoundPrize"
                    type="number"
                    min="0"
                    step="0.01"
                    value="10"
                >

                <label>
                    Entry Fees by Stage
                </label>

                <input
                    id="compRoundFees"
                    value="10,10,10,10,10,10,30"
                    placeholder="10,10,10,10,10,10,30"
                >

                <small>
                    For 7-stage games:
                    stage 1–6 default to 10 points
                    and stage 7 defaults to 30.
                    You can edit them.
                </small>

                <label>
                    Round Start
                </label>

                <input
                    id="compRoundStart"
                    type="datetime-local"
                >

                <button
                    class="primary-btn full"
                    onclick="competitionCreateRound()">
                    CREATE ROUND
                </button>
            </div>

            <div class="panel">

                <div class="panel-header">

                    <h2>
                        Competition Rounds
                    </h2>

                    <button
                        class="secondary-btn"
                        onclick="competitionLoadRounds()">
                        Refresh
                    </button>

                </div>

                <div
                    id="competitionRoundsList"
                    class="list">
                    Loading...
                </div>

            </div>

            <div
                class="panel hidden"
                id="competitionRoundDetailPanel">

                <div class="panel-header">

                    <h2>
                        Round Control
                    </h2>

                    <button
                        class="secondary-btn"
                        onclick="competitionLoadRound(currentRoundId)">
                        Refresh
                    </button>

                </div>

                <div
                    id="competitionRoundDetail">
                </div>

            </div>
        `;

        main.appendChild(page);

        const navButton =
            document.createElement(
                "button"
            );

        navButton.className =
            "nav-item";

        navButton.innerHTML =
            `<span>🏆</span>Competitions`;

        navButton.onclick =
            window.showCompetitionAdmin;

        nav.insertBefore(
            navButton,
            nav.lastElementChild
        );
    }

    window.showCompetitionAdmin =
    function () {

        addUI();

        document
            .querySelectorAll(".page")
            .forEach(
                p =>
                    p.classList.remove(
                        "active"
                    )
            );

        const page =
            document.getElementById(
                "competitionPage"
            );

        if (page) {
            page.classList.add(
                "active"
            );
        }

        document
            .querySelectorAll(
                ".nav-item"
            )
            .forEach(
                b =>
                    b.classList.remove(
                        "active"
                    )
            );

        const buttons =
            document.querySelectorAll(
                ".nav-item"
            );

        if (buttons.length) {
            buttons[
                buttons.length - 2
            ]?.classList.add(
                "active"
            );
        }

        competitionLoadRounds();
    };

    window.competitionSetupGames =
    async function () {

        try {

            await api(
                "/api/admin/competition/setup-games",
                {
                    method: "POST",
                    body: JSON.stringify({})
                }
            );

            showToast(
                "Competition games initialized."
            );

            await competitionLoadRounds();

        } catch (e) {

            showToast(
                e.message
            );
        }
    };

    window.competitionRoundGameChanged =
    function () {

        const game =
            document.getElementById(
                "compRoundGame"
            )?.value;

        const fees =
            document.getElementById(
                "compRoundFees"
            );

        if (fees) {

            fees.value =
                stagedGames.includes(game)
                    ? "10,10,10,10,10,10,30"
                    : "10";
        }
    };

    function localIso(id) {

        const value =
            document.getElementById(
                id
            )?.value;

        return value
            ? new Date(value).toISOString()
            : null;
    }

    window.competitionCreateRound =
    async function () {

        try {

            const game =
                document.getElementById(
                    "compRoundGame"
                ).value;

            const fees =
                document.getElementById(
                    "compRoundFees"
                ).value
                .split(",")
                .map(
                    x =>
                        Number(
                            x.trim()
                        )
                )
                .filter(
                    x =>
                        Number.isFinite(x)
                );

            const data =
                await api(
                    "/api/admin/competition/rounds/create",
                    {
                        method: "POST",

                        body:
                            JSON.stringify({
                                game_id: game,

                                title:
                                    document
                                        .getElementById(
                                            "compRoundTitle"
                                        )
                                        .value
                                        .trim(),

                                prize_pool_usd:
                                    Number(
                                        document
                                            .getElementById(
                                                "compRoundPrize"
                                            )
                                            .value ||
                                        0
                                    ),

                                entry_fees:
                                    fees,

                                start_at:
                                    localIso(
                                        "compRoundStart"
                                    )
                            })
                    }
                );

            showToast(
                `Round created: ${data.round_id}`
            );

            currentRoundId =
                data.round_id;

            await competitionLoadRound(
                currentRoundId
            );

            await competitionLoadRounds();

        } catch (e) {

            showToast(
                e.message
            );
        }
    };

    window.competitionLoadRounds =
    async function () {

        addUI();

        const list =
            document.getElementById(
                "competitionRoundsList"
            );

        if (!list) return;

        list.innerHTML =
            "Loading rounds...";

        try {

            const data =
                await api(
                    "/api/admin/competition/rounds"
                );

            const rounds =
                data.rounds || [];

            if (!rounds.length) {

                list.innerHTML = `
                    <div class="list-card">
                        No competition rounds yet.
                    </div>
                `;

                return;
            }

            list.innerHTML =
                rounds.map(
                    r => `
                        <div class="list-card">

                            <div class="row">

                                <div>

                                    <h3>
                                        ${h(
                                            r.title ||
                                            r.game_id
                                        )}
                                    </h3>

                                    <p>
                                        ${h(r.game_id)}
                                        ·
                                        ${h(r.status)}
                                    </p>

                                </div>

                                <span class="badge">
                                    ${Number(
                                        r.winner_count ||
                                        0
                                    )}
                                    winners
                                </span>

                            </div>

                            <p>
                                Prize:
                                <strong>
                                    $${Number(
                                        r.prize_pool_usd ||
                                        0
                                    ).toFixed(2)}
                                </strong>
                            </p>

                            <p>
                                Current stage:
                                ${Number(
                                    r.current_stage ||
                                    1
                                )}
                                /
                                ${Number(
                                    r.total_stages ||
                                    1
                                )}
                            </p>

                            <button
                                class="primary-btn full"
                                onclick="competitionLoadRound('${h(r.id)}')">
                                OPEN ROUND
                            </button>

                        </div>
                    `
                )
                .join("");

        } catch (e) {

            list.innerHTML = `
                <div class="list-card">
                    ${h(e.message)}
                </div>
            `;
        }
    };

    function stageForm(
        round,
        nextStage
    ) {

        const game =
            round.game_id;

        const defaultFee =
            Number(
                (
                    round.entry_fees ||
                    [10]
                )[nextStage - 1] ||
                (
                    nextStage === 7
                        ? 30
                        : 10
                )
            );

        const optionsPlaceholder =
            game === "survivor"
                ? "15,14,13,12,11,10,9"
                : game === "impossible_choice"
                    ? "Option A,Option B,Option C,Option D"
                    : "";

        return `
            <div class="panel">

                <h3>
                    Prepare Stage ${nextStage}
                </h3>

                <p>
                    <strong>
                        Important:
                    </strong>

                    future stages are private.
                    Players only receive the
                    currently live stage.
                </p>

                <label>
                    Stage Title
                </label>

                <input
                    id="csTitle"
                    value="Day ${nextStage}"
                >

                <label>
                    Question / Prompt
                </label>

                <textarea
                    id="csQuestion"
                    placeholder="Enter today's challenge">
                </textarea>

                <label>
                    Entry Fee (Points)
                </label>

                <input
                    id="csFee"
                    type="number"
                    min="0"
                    value="${defaultFee}"
                >

                <label>
                    Start Time
                </label>

                <input
                    id="csStart"
                    type="datetime-local"
                >

                <label>
                    End Time
                </label>

                <input
                    id="csEnd"
                    type="datetime-local"
                >

                <label>
                    Clue (optional)
                </label>

                <textarea
                    id="csClue"
                    placeholder="Optional clue">
                </textarea>

                <label>
                    Generation
                </label>

                <select id="csGeneration">

                    <option value="admin">
                        Admin chooses actual answer
                    </option>

                    <option value="random">
                        System randomly generates answer
                    </option>

                </select>

                <label>
                    Options (comma separated)
                </label>

                <textarea
                    id="csOptions"
                    placeholder="${optionsPlaceholder}">
                </textarea>

                <label>
                    Correct Answer
                    (Guess It / Impossible Question)
                </label>

                <input
                    id="csCorrect"
                    placeholder="Admin-approved answer"
                >

                <label>
                    Accepted Answers
                    (comma separated)
                </label>

                <input
                    id="csAccepted"
                    placeholder="Answer 1, Answer 2"
                >

                <label>
                    Safe Option
                    (Survivor)
                </label>

                <input
                    id="csSafe"
                    placeholder="Admin-approved safe option"
                >

                <label>
                    Number Range — Minimum
                </label>

                <input
                    id="csMin"
                    type="number"
                    value="1"
                >

                <label>
                    Number Range — Maximum
                </label>

                <input
                    id="csMax"
                    type="number"
                    value="20"
                >

                <label>
                    Dead Numbers
                    (Dead Number)
                </label>

                <input
                    id="csDead"
                    placeholder="17, 23"
                >

                <label>
                    Dead Count (Random)
                </label>

                <input
                    id="csDeadCount"
                    type="number"
                    min="1"
                    value="3"
                >

                <label>
                    Impossible Choice Mechanic
                </label>

                <select id="csMechanic">

                    <option value="minority">
                        Minority
                    </option>

                    <option value="majority">
                        Majority
                    </option>

                    <option value="closest_target">
                        Closest to target percentage
                    </option>

                    <option value="within_range">
                        Within target percentage range
                    </option>

                </select>

                <label>
                    Target Percentage
                </label>

                <input
                    id="csTarget"
                    type="number"
                    step="0.1"
                    value="50"
                >

                <label>
                    Target Minimum %
                </label>

                <input
                    id="csTargetMin"
                    type="number"
                    step="0.1"
                    value="40"
                >

                <label>
                    Target Maximum %
                </label>

                <input
                    id="csTargetMax"
                    type="number"
                    step="0.1"
                    value="60"
                >

                <button
                    class="primary-btn full"
                    onclick="competitionCreateStage('${h(round.id)}', ${nextStage})">
                    CREATE STAGE
                </button>

            </div>
        `;
    }

    window.competitionCreateStage =
    async function (
        roundId,
        stageNo
    ) {

        try {

            const options =
                document
                    .getElementById(
                        "csOptions"
                    )
                    .value
                    .split(",")
                    .map(
                        x =>
                            x.trim()
                    )
                    .filter(Boolean);

            const accepted =
                document
                    .getElementById(
                        "csAccepted"
                    )
                    .value
                    .split(",")
                    .map(
                        x =>
                            x.trim()
                    )
                    .filter(Boolean);

            const dead =
                document
                    .getElementById(
                        "csDead"
                    )
                    .value
                    .split(",")
                    .map(
                        x =>
                            x.trim()
                    )
                    .filter(Boolean);

            const data =
                await api(
                    `/api/admin/competition/rounds/${encodeURIComponent(roundId)}/stages/create`,
                    {
                        method: "POST",

                        body:
                            JSON.stringify({

                                stage_no:
                                    stageNo,

                                title:
                                    document
                                        .getElementById(
                                            "csTitle"
                                        )
                                        .value
                                        .trim(),

                                question:
                                    document
                                        .getElementById(
                                            "csQuestion"
                                        )
                                        .value
                                        .trim(),

                                entry_fee:
                                    Number(
                                        document
                                            .getElementById(
                                                "csFee"
                                            )
                                            .value ||
                                        0
                                    ),

                                start_at:
                                    localIso(
                                        "csStart"
                                    ),

                                end_at:
                                    localIso(
                                        "csEnd"
                                    ),

                                clue:
                                    document
                                        .getElementById(
                                            "csClue"
                                        )
                                        .value
                                        .trim(),

                                generation_mode:
                                    document
                                        .getElementById(
                                            "csGeneration"
                                        )
                                        .value,

                                options,

                                correct_answer:
                                    document
                                        .getElementById(
                                            "csCorrect"
                                        )
                                        .value
                                        .trim(),

                                accepted_answers:
                                    accepted,

                                safe_option:
                                    document
                                        .getElementById(
                                            "csSafe"
                                        )
                                        .value
                                        .trim(),

                                min_number:
                                    Number(
                                        document
                                            .getElementById(
                                                "csMin"
                                            )
                                            .value ||
                                        1
                                    ),

                                max_number:
                                    Number(
                                        document
                                            .getElementById(
                                                "csMax"
                                            )
                                            .value ||
                                        20
                                    ),

                                dead_numbers:
                                    dead,

                                dead_count:
                                    Number(
                                        document
                                            .getElementById(
                                                "csDeadCount"
                                            )
                                            .value ||
                                        1
                                    ),

                                mechanic:
                                    document
                                        .getElementById(
                                            "csMechanic"
                                        )
                                        .value,

                                target_percentage:
                                    Number(
                                        document
                                            .getElementById(
                                                "csTarget"
                                            )
                                            .value ||
                                        50
                                    ),

                                target_min_percentage:
                                    Number(
                                        document
                                            .getElementById(
                                                "csTargetMin"
                                            )
                                            .value ||
                                        40
                                    ),

                                target_max_percentage:
                                    Number(
                                        document
                                            .getElementById(
                                                "csTargetMax"
                                            )
                                            .value ||
                                        60
                                    )
                            })
                    }
                );

            showToast(
                "Stage created. Review the actual secret below before approving it."
            );

            await competitionLoadRound(
                roundId
            );

        } catch (e) {

            showToast(
                e.message
            );
        }
    };

    window.competitionLoadRound =
    async function (roundId) {

        addUI();

        currentRoundId =
            roundId;

        const panel =
            document.getElementById(
                "competitionRoundDetailPanel"
            );

        const box =
            document.getElementById(
                "competitionRoundDetail"
            );

        if (!panel || !box) return;

        panel.classList.remove(
            "hidden"
        );

        box.innerHTML =
            "Loading round...";

        try {

            const data =
                await api(
                    `/api/admin/competition/rounds/${encodeURIComponent(roundId)}`
                );

            const r =
                data.round;

            const stages =
                data.stages || [];

            const nextStage =
                Number(
                    r.current_stage ||
                    1
                ) +
                (
                    stages.some(
                        s =>
                            Number(
                                s.stage_no
                            ) ===
                            Number(
                                r.current_stage
                            )
                    )
                        ? 1
                        : 0
                );

            let html = `
                <div class="panel">

                    <h2>
                        ${h(
                            r.title ||
                            r.game_id
                        )}
                    </h2>

                    <p>
                        Game:
                        <strong>
                            ${h(r.game_id)}
                        </strong>
                    </p>

                    <p>
                        Status:
                        <strong>
                            ${h(r.status)}
                        </strong>
                    </p>

                    <p>
                        Prize Pool:
                        <strong>
                            $${Number(
                                r.prize_pool_usd ||
                                0
                            ).toFixed(2)}
                        </strong>
                    </p>

                    <p>
                        Current Stage:
                        <strong>
                            ${Number(
                                r.current_stage ||
                                1
                            )}
                            /
                            ${Number(
                                r.total_stages ||
                                1
                            )}
                        </strong>
                    </p>

                </div>
            `;

            for (
                const s of stages
            ) {
                html +=
                    renderStageCard(
                        r,
                        s
                    );
            }

            if (
                r.status !== "settled" &&
                nextStage <=
                    Number(
                        r.total_stages ||
                        1
                    ) &&
                !stages.some(
                    s =>
                        Number(
                            s.stage_no
                        ) ===
                        nextStage
                )
            ) {
                html +=
                    stageForm(
                        r,
                        nextStage
                    );
            }

            html += `
                <div class="panel">

                    <h3>
                        Entries:
                        ${
                            data.entries?.length ||
                            0
                        }
                    </h3>

                    ${
                        (
                            data.entries ||
                            []
                        )
                        .slice(0, 100)
                        .map(
                            e => `
                                <div class="list-card">

                                    <strong>
                                        ${h(
                                            e.telegram_id
                                        )}
                                    </strong>

                                    <p>
                                        Stage
                                        ${Number(
                                            e.stage_no
                                        )}
                                        ·
                                        ${h(
                                            e.status
                                        )}
                                        ·
                                        ${h(
                                            e.answer ||
                                            "No answer yet"
                                        )}
                                    </p>

                                </div>
                            `
                        )
                        .join("")
                        ||
                        "<p>No entries yet.</p>"
                    }

                </div>

                <div class="panel">

                    <h3>
                        Results
                    </h3>

                    ${
                        (
                            data.results ||
                            []
                        )
                        .map(
                            x => `
                                <div class="list-card">

                                    <strong>
                                        ${h(
                                            x.telegram_id
                                        )}
                                    </strong>

                                    <p>
                                        $${Number(
                                            x.amount_usd ||
                                            0
                                        ).toFixed(2)}
                                    </p>

                                </div>
                            `
                        )
                        .join("")
                        ||
                        "<p>No winners recorded yet.</p>"
                    }

                </div>
            `;

            box.innerHTML =
                html;

        } catch (e) {

            box.innerHTML = `
                <div class="list-card">
                    ${h(e.message)}
                </div>
            `;
        }
    };

    function renderStageCard(
        round,
        s
    ) {

        const gid =
            round.game_id;

        const secret =
            gid === "dead_number"

                ? `
                    Dead numbers:
                    <strong>
                        ${h(
                            (s.dead_numbers || [])
                                .join(", ")
                        )}
                    </strong>
                  `

                : gid === "survivor"

                    ? `
                        Safe option:
                        <strong>
                            ${h(
                                s.safe_option ||
                                "—"
                            )}
                        </strong>
                      `

                    : (
                        gid === "guess_it" ||
                        gid === "impossible_question"
                    )

                        ? `
                            Correct answer:
                            <strong>
                                ${h(
                                    s.correct_answer ||
                                    "—"
                                )}
                            </strong>
                          `

                        : `
                            No hidden answer —
                            outcome is calculated
                            from player distribution.
                          `;

        return `
            <div class="panel">

                <div class="row">

                    <h3>
                        Stage
                        ${Number(s.stage_no)}
                        —
                        ${h(
                            s.title ||
                            "Untitled"
                        )}
                    </h3>

                    <span class="badge">
                        ${h(
                            s.status ||
                            "draft"
                        )}
                    </span>

                </div>

                <p>
                    Entry:
                    <strong>
                        ${Number(
                            s.entry_fee ||
                            0
                        )}
                        points
                    </strong>
                </p>

                <p>
                    Start:
                    ${h(
                        s.start_at ||
                        ""
                    )}
                </p>

                <p>
                    End:
                    ${h(
                        s.end_at ||
                        ""
                    )}
                </p>

                <div class="info-box">
                    🔐
                    ${secret}
                </div>

                <p>
                    Approval:
                    <strong>
                        ${
                            s.secret_approved
                                ? "APPROVED"
                                : "NOT APPROVED"
                        }
                    </strong>
                </p>

                <div class="form-actions">

                    ${
                        !s.secret_approved
                            ? `
                                <button
                                    class="primary-btn"
                                    onclick="competitionApproveStage(
                                        '${h(round.id)}',
                                        ${Number(s.stage_no)}
                                    )">
                                    APPROVE SECRET
                                </button>
                              `
                            : ""
                    }

                    ${
                        s.status === "draft" ||
                        s.status === "scheduled"
                            ? `
                                <button
                                    class="primary-btn"
                                    onclick="competitionStartStage(
                                        '${h(round.id)}',
                                        ${Number(s.stage_no)}
                                    )">
                                    START STAGE
                                </button>
                              `
                            : ""
                    }

                    ${
                        s.status === "live"
                            ? `
                                <button
                                    class="danger-btn"
                                    onclick="competitionEndStage(
                                        '${h(round.id)}',
                                        ${Number(s.stage_no)}
                                    )">
                                    END / SETTLE STAGE
                                </button>
                              `
                            : ""
                    }

                    ${
                        s.status === "closed" &&
                        Number(s.stage_no) <
                            Number(
                                round.total_stages
                            )
                            ? `
                                <button
                                    class="primary-btn"
                                    onclick="competitionAdvance(
                                        '${h(round.id)}'
                                    )">
                                    PREPARE NEXT STAGE
                                </button>
                              `
                            : ""
                    }

                </div>

            </div>
        `;
    }

    window.competitionApproveStage =
    async function (
        rid,
        stage
    ) {

        try {

            await api(
                `/api/admin/competition/rounds/${encodeURIComponent(rid)}/stages/${stage}/approve`,
                {
                    method: "POST"
                }
            );

            showToast(
                "Actual answer/safe/dead values approved."
            );

            competitionLoadRound(
                rid
            );

        } catch (e) {

            showToast(
                e.message
            );
        }
    };

    window.competitionStartStage =
    async function (
        rid,
        stage
    ) {

        if (
            !confirm(
                "Start this stage now? Players will be able to see its configuration."
            )
        ) {
            return;
        }

        try {

            await api(
                `/api/admin/competition/rounds/${encodeURIComponent(rid)}/stages/${stage}/start`,
                {
                    method: "POST"
                }
            );

            showToast(
                "Stage is live."
            );

            competitionLoadRound(
                rid
            );

        } catch (e) {

            showToast(
                e.message
            );
        }
    };

    window.competitionEndStage =
    async function (
        rid,
        stage
    ) {

        if (
            !confirm(
                "End this stage now? Submitted answers will be evaluated."
            )
        ) {
            return;
        }

        try {

            const data =
                await api(
                    `/api/admin/competition/rounds/${encodeURIComponent(rid)}/stages/${stage}/end`,
                    {
                        method: "POST"
                    }
                );

            showToast(
                `Stage closed. Winners: ${
                    data.winner_count ||
                    0
                }`
            );

            competitionLoadRound(
                rid
            );

        } catch (e) {

            showToast(
                e.message
            );
        }
    };

    window.competitionAdvance =
    async function (rid) {

        try {

            const data =
                await api(
                    `/api/admin/competition/rounds/${encodeURIComponent(rid)}/next-stage`,
                    {
                        method: "POST"
                    }
                );

            showToast(
                `Next stage ${data.next_stage} is ready for configuration.`
            );

            competitionLoadRound(
                rid
            );

        } catch (e) {

            showToast(
                e.message
            );
        }
    };

    document.addEventListener(
        "DOMContentLoaded",
        () => {

            addUI();

            const section =
                new URLSearchParams(
                    window.location.search
                ).get("section");

            if (
                section ===
                "competition"
            ) {

                setTimeout(
                    window.showCompetitionAdmin,
                    200
                );
            }
        }
    );

})();
