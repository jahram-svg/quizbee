const tg = window.Telegram?.WebApp;

if (tg) {
    tg.ready();
    tg.expand();
}

const CONFIG =
    window.QUIZBEE_CONFIG || {};

const API_URL =
    (CONFIG.API_URL || "")
    .replace(/\/$/, "");


let currentPage = "dashboard";
let currentRound = null;


/* ============================================================
   TELEGRAM
============================================================ */

function getInitData() {

    return tg?.initData || "";
}


/* ============================================================
   API
============================================================ */

async function api(
    path,
    options = {}
) {

    if (!API_URL) {
        throw new Error(
            "API_URL is not configured."
        );
    }

    const headers = {
        "Content-Type":
            "application/json",
        ...(options.headers || {})
    };

    const initData =
        getInitData();

    if (initData) {
        headers[
            "X-Telegram-Init-Data"
        ] = initData;
    }

    const response =
        await fetch(
            `${API_URL}${path}`,
            {
                ...options,
                headers
            }
        );

    let data;

    try {

        data =
            await response.json();

    } catch {

        throw new Error(
            `Server returned HTTP ${response.status}`
        );
    }

    if (!response.ok) {

        throw new Error(
            data.error ||
            `HTTP ${response.status}`
        );
    }

    return data;
}


/* ============================================================
   TOAST
============================================================ */

function showToast(message) {

    const toast =
        document.getElementById(
            "toast"
        );

    toast.textContent =
        message;

    toast.classList.add(
        "show"
    );

    setTimeout(() => {

        toast.classList.remove(
            "show"
        );

    }, 3000);
}


/* ============================================================
   PAGE NAVIGATION
============================================================ */

function showPage(page) {

    currentPage = page;

    document
        .querySelectorAll(".page")
        .forEach(
            section =>
                section.classList.remove(
                    "active"
                )
        );

    const pageElement =
        document.getElementById(
            `${page}Page`
        );

    if (pageElement) {

        pageElement.classList.add(
            "active"
        );
    }

    document
        .querySelectorAll(".nav-item")
        .forEach(
            button =>
                button.classList.remove(
                    "active"
                )
        );

    const navButtons =
        document.querySelectorAll(
            ".nav-item"
        );

    const navIndex = {
        dashboard: 0,
        users: 1,
        games: 2,
        daily: 3,
        wallet: 4
    };

    if (
        navButtons[
            navIndex[page]
        ]
    ) {

        navButtons[
            navIndex[page]
        ].classList.add(
            "active"
        );
    }

    if (page === "dashboard") {
        loadDashboard();
    }

    if (page === "users") {
        loadUsers();
    }

    if (page === "games") {
        loadGames();
        loadChallenges();
    }

    if (page === "daily") {
        loadDailyRounds();
    }

    if (page === "wallet") {
        loadWithdrawals();
    }

    if (page === "settings") {
        loadSettings();
    }
}


function refreshCurrentPage() {
    showPage(currentPage);
}


/* ============================================================
   BOOT
============================================================ */

async function boot() {

    try {

        if (!getInitData()) {

            throw new Error(
                "Open the Admin Panel inside Telegram."
            );
        }

        const data =
            await api(
                "/api/admin/bootstrap"
            );

        if (!data.success) {

            throw new Error(
                data.error ||
                "Admin authentication failed."
            );
        }

        document
            .getElementById(
                "loadingScreen"
            )
            .classList.add(
                "hidden"
            );

        document
            .getElementById(
                "adminApp"
            )
            .classList.remove(
                "hidden"
            );

        const admin =
            data.admin || {};

        document
            .getElementById(
                "adminWelcome"
            )
            .textContent =
            `Hello, ${admin.first_name || "Admin"}`;

        renderStats(
            data.stats || {}
        );

        renderDashboardDaily(
            data.active_daily_round
        );

        loadSettings();

    } catch (error) {

        console.error(error);

        document
            .getElementById(
                "loadingScreen"
            )
            .classList.add(
                "hidden"
            );

        document
            .getElementById(
                "deniedScreen"
            )
            .classList.remove(
                "hidden"
            );

        showToast(
            error.message
        );
    }
}


/* ============================================================
   DASHBOARD
============================================================ */

function renderStats(stats) {

    document
        .getElementById(
            "statUsers"
        )
        .textContent =
        stats.users || 0;

    document
        .getElementById(
            "statPoints"
        )
        .textContent =
        Number(
            stats.total_points || 0
        ).toLocaleString();

    document
        .getElementById(
            "statPrize"
        )
        .textContent =
        `$${Number(
            stats.total_prize_balance || 0
        ).toFixed(2)}`;

    document
        .getElementById(
            "statGames"
        )
        .textContent =
        `${stats.active_games || 0}/${stats.total_games || 0}`;

    document
        .getElementById(
            "statWithdrawals"
        )
        .textContent =
        stats.pending_withdrawals || 0;

    document
        .getElementById(
            "statOrders"
        )
        .textContent =
        stats.pending_point_orders || 0;
}


function renderDashboardDaily(round) {

    const box =
        document.getElementById(
            "dashboardDaily"
        );

    if (!round) {

        box.innerHTML =
            `<p>No active Daily Earning round.</p>`;

        return;
    }

    const max =
        Number(
            round.max_entries || 0
        );

    box.innerHTML = `

        <div class="list-card">

            <div class="row">

                <div>

                    <h3>
                        ${escapeHtml(
                            round.title ||
                            "Daily Earning"
                        )}
                    </h3>

                    <p>
                        Mode:
                        ${escapeHtml(
                            round.mode ||
                            ""
                        )}
                    </p>

                </div>

                <span class="badge ${escapeHtml(
                    round.status || ""
                )}">
                    ${escapeHtml(
                        round.status || ""
                    )}
                </span>

            </div>

            <p>
                Prize Pool:
                <strong>
                    $${Number(
                        round.prize_pool_usd || 0
                    ).toFixed(2)}
                </strong>
            </p>

            <p>
                Maximum:
                ${max}
            </p>

            <button
                class="primary-btn full"
                onclick="openDailyRound('${round.id}')"
            >
                Open Round
            </button>

        </div>
    `;
}


async function loadDashboard() {

    try {

        const data =
            await api(
                "/api/admin/bootstrap"
            );

        renderStats(
            data.stats || {}
        );

        renderDashboardDaily(
            data.active_daily_round
        );

    } catch (error) {

        showToast(
            error.message
        );
    }
}


/* ============================================================
   USERS
============================================================ */

async function loadUsers() {

    const list =
        document.getElementById(
            "usersList"
        );

    list.innerHTML =
        "Loading users...";

    try {

        const search =
            document.getElementById(
                "userSearch"
            ).value.trim();

        const data =
            await api(
                `/api/admin/users?search=${encodeURIComponent(search)}`
            );

        const users =
            data.users || [];

        if (!users.length) {

            list.innerHTML =
                `<div class="list-card">
                    No users found.
                </div>`;

            return;
        }

        list.innerHTML =
            users.map(
                renderUserCard
            ).join("");

    } catch (error) {

        list.innerHTML =
            `<div class="list-card">
                ${escapeHtml(
                    error.message
                )}
            </div>`;
    }
}


function renderUserCard(user) {

    const name =
        [
            user.first_name,
            user.last_name
        ]
        .filter(Boolean)
        .join(" ")
        ||
        user.username
        ||
        "Unknown User";

    return `

        <div class="list-card">

            <div class="row">

                <div>

                    <h3>
                        ${escapeHtml(name)}
                    </h3>

                    <p>
                        Telegram ID:
                        ${escapeHtml(
                            user.telegram_id || ""
                        )}
                    </p>

                    <p>
                        @${escapeHtml(
                            user.username || "no_username"
                        )}
                    </p>

                </div>

                <span class="badge">
                    ${Number(
                        user.quizbee_points || 0
                    ).toLocaleString()}
                    pts
                </span>

            </div>

            <p>
                Prize Balance:
                <strong>
                    $${Number(
                        user.prize_balance || 0
                    ).toFixed(2)}
                </strong>
            </p>

            <button
                class="secondary-btn full"
                onclick="openUser('${user.telegram_id}')"
            >
                View User
            </button>

        </div>
    `;
}


async function openUser(telegramId) {

    showPageWithoutReload(
        "userDetails"
    );

    const box =
        document.getElementById(
            "userDetails"
        );

    box.innerHTML =
        "Loading user...";

    try {

        const data =
            await api(
                `/api/admin/users/${encodeURIComponent(telegramId)}`
            );

        const user =
            data.user || {};

        box.innerHTML = `

            <div class="panel">

                <h2>
                    ${escapeHtml(
                        user.first_name ||
                        user.username ||
                        "User"
                    )}
                </h2>

                <p>
                    Telegram ID:
                    <strong>
                        ${escapeHtml(
                            user.telegram_id || telegramId
                        )}
                    </strong>
                </p>

                <p>
                    Username:
                    @${escapeHtml(
                        user.username || "none"
                    )}
                </p>

                <hr>

                <p>
                    QuizBee Points:
                    <strong>
                        ${Number(
                            user.quizbee_points || 0
                        ).toLocaleString()}
                    </strong>
                </p>

                <p>
                    Prize Balance:
                    <strong>
                        $${Number(
                            user.prize_balance || 0
                        ).toFixed(2)}
                    </strong>
                </p>

                <p>
                    Total Earned:
                    ${Number(
                        user.total_earned || 0
                    ).toLocaleString()}
                </p>

                <p>
                    Total Spent:
                    ${Number(
                        user.total_spent || 0
                    ).toLocaleString()}
                </p>

                <p>
                    Referrals:
                    ${Number(
                        user.referrals_count || 0
                    )}
                </p>

            </div>


            <div class="panel">

                <h2>
                    Transactions
                </h2>

                ${renderTransactions(
                    data.transactions || []
                )}

            </div>


            <div class="panel">

                <h2>
                    Daily Earning Entries
                </h2>

                ${renderEntries(
                    data.daily_entries || []
                )}

            </div>
        `;

    } catch (error) {

        box.innerHTML =
            `<div class="list-card">
                ${escapeHtml(
                    error.message
                )}
            </div>`;
    }
}


function renderTransactions(items) {

    if (!items.length) {
        return "<p>No transactions.</p>";
    }

    return items
        .slice(0, 50)
        .map(item => `

            <div class="list-card">

                <strong>
                    ${escapeHtml(
                        item.type || ""
                    )}
                </strong>

                <p>
                    ${item.amount ?? 0}
                    ${escapeHtml(
                        item.currency || ""
                    )}
                </p>

                <p>
                    ${escapeHtml(
                        item.status || ""
                    )}
                </p>

            </div>

        `)
        .join("");
}


function renderEntries(items) {

    if (!items.length) {
        return "<p>No entries.</p>";
    }

    return items
        .slice(0, 50)
        .map(item => `

            <div class="list-card">

                <strong>
                    ${escapeHtml(
                        item.round_id || ""
                    )}
                </strong>

                <p>
                    Mode:
                    ${escapeHtml(
                        item.mode || ""
                    )}
                </p>

                <p>
                    Status:
                    ${escapeHtml(
                        item.status || ""
                    )}
                </p>

            </div>

        `)
        .join("");
}


function showPageWithoutReload(page) {

    document
        .querySelectorAll(".page")
        .forEach(
            section =>
                section.classList.remove(
                    "active"
                )
        );

    const element =
        document.getElementById(
            `${page}Page`
        );

    if (element) {
        element.classList.add(
            "active"
        );
    }
}


/* ============================================================
   GAMES
============================================================ */

async function loadGames() {

    const list =
        document.getElementById(
            "gamesList"
        );

    list.innerHTML =
        "Loading games...";

    try {

        const data =
            await api(
                "/api/admin/games"
            );

        const games =
            data.games || [];

        const filter =
            document.getElementById(
                "challengeGameFilter"
            );

        const select =
            document.getElementById(
                "challengeGame"
            );

        filter.innerHTML =
            `<option value="">
                All Games
            </option>`;

        select.innerHTML = "";

        games.forEach(game => {

            const option =
                document.createElement(
                    "option"
                );

            option.value =
                game.id;

            option.textContent =
                `${game.icon || "🎮"} ${game.name}`;

            filter.appendChild(
                option.cloneNode(true)
            );

            select.appendChild(
                option
            );
        });

        list.innerHTML =
            games
            .map(renderGameCard)
            .join("");

    } catch (error) {

        list.innerHTML =
            `<div class="list-card">
                ${escapeHtml(
                    error.message
                )}
            </div>`;
    }
}


function renderGameCard(game) {

    return `

        <div class="list-card">

            <div class="row">

                <div>

                    <h3>
                        ${escapeHtml(
                            game.icon || "🎮"
                        )}
                        ${escapeHtml(
                            game.name || game.id
                        )}
                    </h3>

                    <p>
                        ${escapeHtml(
                            game.description || ""
                        )}
                    </p>

                </div>

                <span class="badge ${
                    game.active
                    ? "active"
                    : ""
                }">

                    ${
                        game.active
                        ? "ACTIVE"
                        : "LOCKED"
                    }

                </span>

            </div>

            <p>
                Entry:
                <strong>
                    ${Number(
                        game.entry_fee || 0
                    )}
                    points
                </strong>
            </p>

            <button
                class="${
                    game.active
                    ? "danger-btn"
                    : "primary-btn"
                } full"
                onclick="toggleGame(
                    '${game.id}',
                    ${!game.active}
                )"
            >
                ${
                    game.active
                    ? "Lock Game"
                    : "Unlock Game"
                }
            </button>

        </div>
    `;
}


async function toggleGame(
    gameId,
    active
) {

    try {

        await api(
            `/api/admin/games/${gameId}/update`,
            {
                method: "POST",

                body:
                    JSON.stringify({
                        active
                    })
            }
        );

        showToast(
            active
            ? "Game unlocked."
            : "Game locked."
        );

        loadGames();

    } catch (error) {

        showToast(
            error.message
        );
    }
}


/* ============================================================
   CHALLENGES
============================================================ */

function showChallengeForm() {

    document
        .getElementById(
            "challengeForm"
        )
        .classList.remove(
            "hidden"
        );
}


function hideChallengeForm() {

    document
        .getElementById(
            "challengeForm"
        )
        .classList.add(
            "hidden"
        );
}


async function loadChallenges() {

    const list =
        document.getElementById(
            "challengesList"
        );

    list.innerHTML =
        "Loading challenges...";

    try {

        const gameId =
            document.getElementById(
                "challengeGameFilter"
            ).value;

        const url =
            gameId
            ? `/api/admin/challenges?game_id=${encodeURIComponent(gameId)}`
            : "/api/admin/challenges";

        const data =
            await api(url);

        const challenges =
            data.challenges || [];

        if (!challenges.length) {

            list.innerHTML =
                `<div class="list-card">
                    No challenges found.
                </div>`;

            return;
        }

        list.innerHTML =
            challenges
            .map(
                renderChallengeCard
            )
            .join("");

    } catch (error) {

        list.innerHTML =
            `<div class="list-card">
                ${escapeHtml(
                    error.message
                )}
            </div>`;
    }
}


function renderChallengeCard(challenge) {

    return `

        <div class="list-card">

            <div class="row">

                <div>

                    <h3>
                        ${escapeHtml(
                            challenge.title ||
                            "Untitled"
                        )}
                    </h3>

                    <p>
                        Game:
                        ${escapeHtml(
                            challenge.game_id || ""
                        )}
                    </p>

                </div>

                <span class="badge ${
                    challenge.active
                    ? "active"
                    : ""
                }">

                    ${
                        challenge.active
                        ? "ACTIVE"
                        : "INACTIVE"
                    }

                </span>

            </div>

            <p>
                ${escapeHtml(
                    challenge.question || ""
                )}
            </p>

            <p>
                Reward:
                ${Number(
                    challenge.reward_points || 0
                )}
                points
            </p>

            <button
                class="${
                    challenge.active
                    ? "danger-btn"
                    : "primary-btn"
                } full"
                onclick="toggleChallenge(
                    '${challenge.id}',
                    ${!challenge.active}
                )"
            >
                ${
                    challenge.active
                    ? "Deactivate"
                    : "Activate"
                }
            </button>

        </div>
    `;
}


async function createChallenge() {

    try {

        const accepted =
            document
            .getElementById(
                "challengeAccepted"
            )
            .value
            .split(",")
            .map(
                x => x.trim()
            )
            .filter(Boolean);

        await api(
            "/api/admin/challenges/create",
            {
                method: "POST",

                body:
                    JSON.stringify({

                        game_id:
                            document
                            .getElementById(
                                "challengeGame"
                            ).value,

                        title:
                            document
                            .getElementById(
                                "challengeTitle"
                            ).value,

                        question:
                            document
                            .getElementById(
                                "challengeQuestion"
                            ).value,

                        correct_answer:
                            document
                            .getElementById(
                                "challengeCorrect"
                            ).value,

                        accepted_answers:
                            accepted,

                        reward_points:
                            Number(
                                document
                                .getElementById(
                                    "challengeReward"
                                ).value
                            ),

                        type:
                            document
                            .getElementById(
                                "challengeType"
                            ).value,

                        active:
                            false
                    })
            }
        );

        showToast(
            "Challenge created."
        );

        hideChallengeForm();

        loadChallenges();

    } catch (error) {

        showToast(
            error.message
        );
    }
}


async function toggleChallenge(
    id,
    active
) {

    try {

        await api(
            `/api/admin/challenges/${id}/update`,
            {
                method: "POST",

                body:
                    JSON.stringify({
                        active
                    })
            }
        );

        showToast(
            active
            ? "Challenge activated."
            : "Challenge deactivated."
        );

        loadChallenges();

    } catch (error) {

        showToast(
            error.message
        );
    }
}


/* ============================================================
   DAILY EARNING
============================================================ */

function toggleDailyMode() {

    const mode =
        document
        .getElementById(
            "dailyMode"
        ).value;

    document
        .getElementById(
            "dailyQuestionFields"
        )
        .classList.toggle(
            "hidden",
            mode !== "question"
        );

    document
        .getElementById(
            "dailyTaskFields"
        )
        .classList.toggle(
            "hidden",
            mode !== "task"
        );
}


async function createDailyRound() {

    try {

        const mode =
            document
            .getElementById(
                "dailyMode"
            ).value;

        const accepted =
            document
            .getElementById(
                "dailyAccepted"
            )
            .value
            .split(",")
            .map(
                x => x.trim()
            )
            .filter(Boolean);

        const start =
            document
            .getElementById(
                "dailyStart"
            ).value;

        const end =
            document
            .getElementById(
                "dailyEnd"
            ).value;

        if (!start || !end) {

            throw new Error(
                "Choose start and end time."
            );
        }

        const data =
            await api(
                "/api/daily-earning/admin/create",
                {
                    method: "POST",

                    body:
                        JSON.stringify({

                            title:
                                document
                                .getElementById(
                                    "dailyTitle"
                                ).value,

                            mode,

                            question:
                                document
                                .getElementById(
                                    "dailyQuestion"
                                ).value,

                            instructions:
                                document
                                .getElementById(
                                    "dailyInstructions"
                                ).value,

                            correct_answer:
                                document
                                .getElementById(
                                    "dailyCorrect"
                                ).value,

                            accepted_answers:
                                accepted,

                            prize_pool_usd:
                                Number(
                                    document
                                    .getElementById(
                                        "dailyPrize"
                                    ).value
                                ),

                            max_entries:
                                Number(
                                    document
                                    .getElementById(
                                        "dailyMax"
                                    ).value
                                ),

                            start_at:
                                new Date(
                                    start
                                ).toISOString(),

                            end_at:
                                new Date(
                                    end
                                ).toISOString(),

                            status:
                                "scheduled"
                        })
                }
            );

        showToast(
            `Round created: ${data.round_id}`
        );

        loadDailyRounds();

    } catch (error) {

        showToast(
            error.message
        );
    }
}


async function loadDailyRounds() {

    const list =
        document.getElementById(
            "dailyRoundsList"
        );

    list.innerHTML =
        "Loading rounds...";

    try {

        const data =
            await api(
                "/api/admin/daily-rounds"
            );

        const rounds =
            data.rounds || [];

        if (!rounds.length) {

            list.innerHTML =
                `<div class="list-card">
                    No Daily Earning rounds yet.
                </div>`;

            return;
        }

        list.innerHTML =
            rounds
            .map(
                renderDailyRoundCard
            )
            .join("");

    } catch (error) {

        list.innerHTML =
            `<div class="list-card">
                ${escapeHtml(
                    error.message
                )}
            </div>`;
    }
}


function renderDailyRoundCard(round) {

    return `

        <div class="list-card">

            <div class="row">

                <div>

                    <h3>
                        ${escapeHtml(
                            round.title ||
                            "Daily Earning"
                        )}
                    </h3>

                    <p>
                        ${escapeHtml(
                            round.mode || ""
                        )}
                    </p>

                </div>

                <span class="badge ${escapeHtml(
                    round.status || ""
                )}">
                    ${escapeHtml(
                        round.status || ""
                    )}
                </span>

            </div>

            <p>
                Prize:
                <strong>
                    $${Number(
                        round.prize_pool_usd || 0
                    ).toFixed(2)}
                </strong>
            </p>

            <p>
                Maximum:
                ${Number(
                    round.max_entries || 0
                )}
            </p>

            <button
                class="primary-btn full"
                onclick="openDailyRound('${round.id}')"
            >
                View Round
            </button>

        </div>
    `;
}


async function openDailyRound(roundId) {

    showPageWithoutReload(
        "dailyDetails"
    );

    const box =
        document.getElementById(
            "dailyDetails"
        );

    box.innerHTML =
        "Loading round...";

    currentRound =
        roundId;

    try {

        const data =
            await api(
                "/api/admin/daily-rounds"
            );

        const round =
            (data.rounds || [])
            .find(
                x => x.id === roundId
            );

        if (!round) {

            throw new Error(
                "Round not found."
            );
        }

        const entriesData =
            await api(
                `/api/admin/daily-rounds/${roundId}/entries`
            );

        const resultsData =
            await api(
                `/api/admin/daily-rounds/${roundId}/results`
            );

        const entries =
            entriesData.entries || [];

        const results =
            resultsData.results || [];

        box.innerHTML = `

            <div class="panel">

                <h2>
                    ${escapeHtml(
                        round.title || ""
                    )}
                </h2>

                <span class="badge ${escapeHtml(
                    round.status || ""
                )}">
                    ${escapeHtml(
                        round.status || ""
                    )}
                </span>

                <p>
                    Mode:
                    ${escapeHtml(
                        round.mode || ""
                    )}
                </p>

                <p>
                    Prize Pool:
                    <strong>
                        $${Number(
                            round.prize_pool_usd || 0
                        ).toFixed(2)}
                    </strong>
                </p>

                <p>
                    Maximum Participants:
                    ${Number(
                        round.max_entries || 0
                    )}
                </p>

                <p>
                    Participants:
                    ${entries.length}
                </p>

            </div>


            <div class="panel">

                <h2>
                    Round Actions
                </h2>

                ${
                    round.status === "active"
                    || round.status === "scheduled"
                    ? `
                        <button
                            class="primary-btn full"
                            onclick="activateDailyRound('${roundId}')"
                        >
                            Activate Round
                        </button>
                    `
                    : ""
                }

                ${
                    round.status !== "settled"
                    ? `
                        <button
                            class="primary-btn full"
                            onclick="settleDailyRound('${roundId}')"
                        >
                            🏁 Settle Round
                        </button>
                    `
                    : ""
                }

            </div>


            <div class="panel">

                <h2>
                    Entries (${entries.length})
                </h2>

                ${
                    entries.length
                    ? entries.map(
                        renderDailyEntry
                    ).join("")
                    : "<p>No entries.</p>"
                }

            </div>


            <div class="panel">

                <h2>
                    Results (${results.length})
                </h2>

                ${
                    results.length
                    ? results.map(
                        renderDailyResult
                    ).join("")
                    : "<p>No results yet.</p>"
                }

            </div>
        `;

    } catch (error) {

        box.innerHTML =
            `<div class="list-card">
                ${escapeHtml(
                    error.message
                )}
            </div>`;
    }
}


function renderDailyEntry(entry) {

    return `

        <div class="list-card">

            <strong>
                User:
                ${escapeHtml(
                    entry.telegram_id || ""
                )}
            </strong>

            <p>
                Status:
                ${escapeHtml(
                    entry.status || ""
                )}
            </p>

            ${
                entry.answer
                ? `
                    <p>
                        Answer:
                        ${escapeHtml(
                            entry.answer
                        )}
                    </p>
                `
                : ""
            }

            ${
                entry.proof_text
                ? `
                    <p>
                        Proof:
                        ${escapeHtml(
                            entry.proof_text
                        )}
                    </p>
                `
                : ""
            }

            ${
                entry.proof_url
                ? `
                    <p>
                        Proof URL:
                        ${escapeHtml(
                            entry.proof_url
                        )}
                    </p>
                `
                : ""
            }

            ${
                entry.status === "pending"
                ? `
                    <div class="form-actions">

                        <button
                            class="primary-btn"
                            onclick="approveEntry('${entry.id}')"
                        >
                            Approve
                        </button>

                        <button
                            class="danger-btn"
                            onclick="rejectEntry('${entry.id}')"
                        >
                            Reject
                        </button>

                    </div>
                `
                : ""
            }

        </div>
    `;
}


function renderDailyResult(result) {

    return `

        <div class="list-card">

            <strong>
                ${escapeHtml(
                    result.telegram_id || ""
                )}
            </strong>

            <p>
                Prize:
                <strong>
                    $${Number(
                        result.amount_usd || 0
                    ).toFixed(2)}
                </strong>
            </p>

        </div>
    `;
}


async function activateDailyRound(roundId) {

    try {

        await api(
            `/api/daily-earning/admin/${roundId}/activate`,
            {
                method: "POST"
            }
        );

        showToast(
            "Round activated."
        );

        openDailyRound(
            roundId
        );

    } catch (error) {

        showToast(
            error.message
        );
    }
}


async function settleDailyRound(roundId) {

    if (
        !confirm(
            "Settle this Daily Earning round now?"
        )
    ) {
        return;
    }

    try {

        const data =
            await api(
                `/api/daily-earning/admin/${roundId}/settle`,
                {
                    method: "POST"
                }
            );

        showToast(
            `Settled. Winners: ${data.winner_count || 0}`
        );

        openDailyRound(
            roundId
        );

    } catch (error) {

        showToast(
            error.message
        );
    }
}


async function approveEntry(entryId) {

    try {

        await api(
            `/api/daily-earning/admin/entries/${entryId}/approve`,
            {
                method: "POST"
            }
        );

        showToast(
            "Entry approved."
        );

        if (currentRound) {
            openDailyRound(
                currentRound
            );
        }

    } catch (error) {

        showToast(
            error.message
        );
    }
}


async function rejectEntry(entryId) {

    const note =
        prompt(
            "Reason for rejection (optional):"
        ) || "";

    try {

        await api(
            `/api/daily-earning/admin/entries/${entryId}/reject`,
            {
                method: "POST",

                body:
                    JSON.stringify({
                        admin_note:
                            note
                    })
            }
        );

        showToast(
            "Entry rejected."
        );

        if (currentRound) {
            openDailyRound(
                currentRound
            );
        }

    } catch (error) {

        showToast(
            error.message
        );
    }
}


/* ============================================================
   WALLET
============================================================ */

async function loadWithdrawals() {

    const list =
        document.getElementById(
            "walletList"
        );

    list.innerHTML =
        "Loading withdrawals...";

    try {

        const data =
            await api(
                "/api/wallet/admin/withdrawals?status=pending"
            );

        const items =
            data.withdrawals || [];

        if (!items.length) {

            list.innerHTML =
                `<div class="list-card">
                    No pending withdrawals.
                </div>`;

            return;
        }

        list.innerHTML =
            items.map(
                renderWithdrawal
            ).join("");

    } catch (error) {

        list.innerHTML =
            `<div class="list-card">
                ${escapeHtml(
                    error.message
                )}
            </div>`;
    }
}


function renderWithdrawal(item) {

    return `

        <div class="list-card">

            <h3>
                $${Number(
                    item.amount || 0
                ).toFixed(2)}
            </h3>

            <p>
                User:
                ${escapeHtml(
                    item.telegram_id || ""
                )}
            </p>

            <p>
                Method:
                ${escapeHtml(
                    item.method || ""
                )}
            </p>

            ${
                item.wallet_address
                ? `
                    <p>
                        Wallet:
                        ${escapeHtml(
                            item.wallet_address
                        )}
                    </p>
                `
                : ""
            }

            <div class="form-actions">

                <button
                    class="primary-btn"
                    onclick="approveWithdrawal('${item.id}')"
                >
                    Approve
                </button>

                <button
                    class="danger-btn"
                    onclick="rejectWithdrawal('${item.id}')"
                >
                    Reject
                </button>

            </div>

        </div>
    `;
}


async function approveWithdrawal(id) {

    try {

        await api(
            `/api/wallet/admin/withdrawals/${id}/approve`,
            {
                method: "POST"
            }
        );

        showToast(
            "Withdrawal approved."
        );

        loadWithdrawals();

    } catch (error) {

        showToast(
            error.message
        );
    }
}


async function rejectWithdrawal(id) {

    const note =
        prompt(
            "Reason for rejection:"
        ) || "";

    try {

        await api(
            `/api/wallet/admin/withdrawals/${id}/reject`,
            {
                method: "POST",

                body:
                    JSON.stringify({
                        admin_note:
                            note
                    })
            }
        );

        showToast(
            "Withdrawal rejected."
        );

        loadWithdrawals();

    } catch (error) {

        showToast(
            error.message
        );
    }
}


async function loadPointOrders() {

    const list =
        document.getElementById(
            "walletList"
        );

    list.innerHTML =
        "Loading point purchases...";

    try {

        const data =
            await api(
                "/api/wallet/admin/point-orders?status=pending"
            );

        const items =
            data.orders || [];

        if (!items.length) {

            list.innerHTML =
                `<div class="list-card">
                    No pending point purchases.
                </div>`;

            return;
        }

        list.innerHTML =
            items.map(
                renderPointOrder
            ).join("");

    } catch (error) {

        list.innerHTML =
            `<div class="list-card">
                ${escapeHtml(
                    error.message
                )}
            </div>`;
    }
}


function renderPointOrder(item) {

    return `

        <div class="list-card">

            <h3>
                ${Number(
                    item.points || 0
                ).toLocaleString()}
                Points
            </h3>

            <p>
                User:
                ${escapeHtml(
                    item.telegram_id || ""
                )}
            </p>

            <p>
                Provider:
                ${escapeHtml(
                    item.provider || ""
                )}
            </p>

            <p>
                Amount:
                ${escapeHtml(
                    String(
                        item.amount ||
                        ""
                    )
                )}
            </p>

            <div class="form-actions">

                <button
                    class="primary-btn"
                    onclick="approvePointOrder('${item.id}')"
                >
                    Approve
                </button>

                <button
                    class="danger-btn"
                    onclick="rejectPointOrder('${item.id}')"
                >
                    Reject
                </button>

            </div>

        </div>
    `;
}


async function approvePointOrder(id) {

    try {

        await api(
            `/api/wallet/admin/point-orders/${id}/approve`,
            {
                method: "POST"
            }
        );

        showToast(
            "Points credited."
        );

        loadPointOrders();

    } catch (error) {

        showToast(
            error.message
        );
    }
}


async function rejectPointOrder(id) {

    const note =
        prompt(
            "Reason for rejection:"
        ) || "";

    try {

        await api(
            `/api/wallet/admin/point-orders/${id}/reject`,
            {
                method: "POST",

                body:
                    JSON.stringify({
                        admin_note:
                            note
                    })
            }
        );

        showToast(
            "Point purchase rejected."
        );

        loadPointOrders();

    } catch (error) {

        showToast(
            error.message
        );
    }
}


/* ============================================================
   SETTINGS
============================================================ */

async function loadSettings() {

    try {

        const data =
            await api(
                "/api/admin/settings"
            );

        const settings =
            data.settings || {};

        document
            .getElementById(
                "participantVisibility"
            )
            .value =
            settings.participant_visibility
            || "hidden";

        document
            .getElementById(
                "maintenanceMode"
            )
            .checked =
            Boolean(
                settings.maintenance_mode
            );

        document
            .getElementById(
                "dailyEnabled"
            )
            .checked =
            settings.daily_earning_enabled
            !== false;

    } catch (error) {

        console.error(error);
    }
}


async function saveSettings() {

    try {

        await api(
            "/api/admin/settings",
            {
                method: "POST",

                body:
                    JSON.stringify({

                        participant_visibility:
                            document
                            .getElementById(
                                "participantVisibility"
                            ).value,

                        maintenance_mode:
                            document
                            .getElementById(
                                "maintenanceMode"
                            ).checked,

                        daily_earning_enabled:
                            document
                            .getElementById(
                                "dailyEnabled"
                            ).checked
                    })
            }
        );

        showToast(
            "Settings saved."
        );

    } catch (error) {

        showToast(
            error.message
        );
    }
}


/* ============================================================
   SECURITY / HTML
============================================================ */

function escapeHtml(value) {

    return String(
        value ?? ""
    )
    .replace(
        /&/g,
        "&amp;"
    )
    .replace(
        /</g,
        "&lt;"
    )
    .replace(
        />/g,
        "&gt;"
    )
    .replace(
        /"/g,
        "&quot;"
    )
    .replace(
        /'/g,
        "&#039;"
    );
}


/* ============================================================
   START
============================================================ */

document.addEventListener(
    "DOMContentLoaded",
    () => {

        boot();

    }
);
