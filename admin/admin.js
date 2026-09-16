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
    wallet: 4,
    raffle: 5,
    settings: 6
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

    if (page === "raffle") {
    loadRafflePage();
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

                <span class="badge ${
    user.blocked
    ? "danger"
    : ""
}">
    ${
        user.blocked
        ? "🚫 BLOCKED"
        : `${Number(
            user.quizbee_points || 0
        ).toLocaleString()} pts`
    }
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

        const blocked =
            Boolean(
                user.blocked
            );

        box.innerHTML = `

            <!-- USER OVERVIEW -->
            <div class="panel">

                <div class="row">

                    <div>

                        <h2>
                            ${escapeHtml(
                                [
                                    user.first_name,
                                    user.last_name
                                ]
                                .filter(Boolean)
                                .join(" ")
                                ||
                                user.username
                                ||
                                "User"
                            )}
                        </h2>

                        <p>
                            Telegram ID:
                            <strong>
                                ${escapeHtml(
                                    user.telegram_id ||
                                    telegramId
                                )}
                            </strong>
                        </p>

                        <p>
                            Username:
                            @${escapeHtml(
                                user.username ||
                                "none"
                            )}
                        </p>

                    </div>

                    <span class="badge ${
                        blocked
                        ? "danger"
                        : "active"
                    }">

                        ${
                            blocked
                            ? "🚫 BLOCKED"
                            : "✅ ACTIVE"
                        }

                    </span>

                </div>

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

                ${
                    blocked
                    ? `
                        <div class="info-box">

                            <strong>
                                🚫 Account Blocked
                            </strong>

                            <p>
                                Reason:
                                ${escapeHtml(
                                    user.blocked_reason ||
                                    "No reason recorded."
                                )}
                            </p>

                        </div>
                    `
                    : ""
                }

            </div>


            <!-- BALANCE MANAGEMENT -->
            <div class="panel">

                <h2>
                    💰 Balance Management
                </h2>

                <p>
                    Manually add or deduct
                    user balances.
                </p>

                <label>
                    Balance
                </label>

                <select
                    id="adjustBalanceType"
                >

                    <option value="points">
                        🪙 QuizBee Points
                    </option>

                    <option value="prize_balance">
                        💵 Prize Balance (USD)
                    </option>

                </select>


                <label>
                    Action
                </label>

                <select
                    id="adjustBalanceAction"
                >

                    <option value="add">
                        ➕ Add
                    </option>

                    <option value="deduct">
                        ➖ Deduct
                    </option>

                </select>


                <label>
                    Amount
                </label>

                <input
                    id="adjustBalanceAmount"
                    type="number"
                    min="0"
                    step="0.01"
                    placeholder="Enter amount"
                >


                <label>
                    Reason
                </label>

                <textarea
                    id="adjustBalanceReason"
                    placeholder="Required: promo, cheating penalty, correction, compensation, etc."
                ></textarea>


                <button
                    class="primary-btn full"
                    onclick="adjustUserBalance('${telegramId}')"
                >
                    Apply Balance Change
                </button>

            </div>


            <!-- ACCOUNT MANAGEMENT -->
            <div class="panel">

                <h2>
                    🛡️ Account Management
                </h2>

                ${
                    blocked
                    ? `

                        <button
                            class="primary-btn full"
                            onclick="unblockUser('${telegramId}')"
                        >
                            ✅ Unblock User
                        </button>

                    `
                    : `

                        <button
                            class="danger-btn full"
                            onclick="blockUser('${telegramId}')"
                        >
                            🚫 Block User
                        </button>

                    `
                }

            </div>


            <!-- TRANSACTIONS -->
            <div class="panel">

                <h2>
                    Transactions
                </h2>

                ${renderTransactions(
                    data.transactions || []
                )}

            </div>


            <!-- DAILY EARNING -->
            <div class="panel">

                <h2>
                    Daily Earning Entries
                </h2>

                ${renderEntries(
                    data.daily_entries || []
                )}

            </div>


            <!-- ADMIN HISTORY -->
            <div class="panel">

                <div class="row">

                    <h2>
                        Admin Actions
                    </h2>

                    <button
                        class="secondary-btn"
                        onclick="loadUserAdminActions('${telegramId}')"
                    >
                        Refresh
                    </button>

                </div>

                <div
                    id="userAdminActions"
                >
                    Loading...
                </div>

            </div>

        `;

        loadUserAdminActions(
            telegramId
        );

    } catch (error) {

        box.innerHTML =
            `<div class="list-card">
                ${escapeHtml(
                    error.message
                )}
            </div>`;
    }
}


/* ============================================================
   USER MANAGEMENT
============================================================ */

async function adjustUserBalance(
    telegramId
) {

    const balanceType =
        document
        .getElementById(
            "adjustBalanceType"
        )
        .value;

    const action =
        document
        .getElementById(
            "adjustBalanceAction"
        )
        .value;

    const amount =
        document
        .getElementById(
            "adjustBalanceAmount"
        )
        .value;

    const reason =
        document
        .getElementById(
            "adjustBalanceReason"
        )
        .value
        .trim();

    if (!amount) {

        showToast(
            "Enter an amount."
        );

        return;
    }

    if (Number(amount) <= 0) {

        showToast(
            "Amount must be greater than zero."
        );

        return;
    }

    if (!reason) {

        showToast(
            "A reason is required."
        );

        return;
    }

    const balanceName =
        balanceType === "points"
        ? "QuizBee Points"
        : "Prize Balance";

    const actionName =
        action === "add"
        ? "add"
        : "deduct";

    const confirmed =
        confirm(
            `Are you sure you want to ${actionName} ${amount} ${balanceName}?\n\nReason: ${reason}`
        );

    if (!confirmed) {
        return;
    }

    try {

        const data =
            await api(
                `/api/admin/users/${encodeURIComponent(telegramId)}/adjust-balance`,
                {
                    method: "POST",

                    body:
                        JSON.stringify({

                            balance_type:
                                balanceType,

                            action:
                                action,

                            amount:
                                Number(amount),

                            reason:
                                reason

                        })
                }
            );

        showToast(
            `Balance updated successfully. New balance: ${
                balanceType === "points"
                ? Number(
                    data.new_balance || 0
                  ).toLocaleString()
                : `$${Number(
                    data.new_balance || 0
                  ).toFixed(2)}`
            }`
        );

        await openUser(
            telegramId
        );

    } catch (error) {

        showToast(
            error.message
        );
    }
}


async function blockUser(
    telegramId
) {

    const reason =
        prompt(
            "Why are you blocking this user?"
        );

    if (!reason) {
        return;
    }

    const confirmed =
        confirm(
            "Block this user?\n\n" +
            "They will no longer be allowed to use QuizBee."
        );

    if (!confirmed) {
        return;
    }

    try {

        await api(
            `/api/admin/users/${encodeURIComponent(telegramId)}/block`,
            {
                method: "POST",

                body:
                    JSON.stringify({
                        reason:
                            reason.trim()
                    })
            }
        );

        showToast(
            "User blocked."
        );

        await openUser(
            telegramId
        );

    } catch (error) {

        showToast(
            error.message
        );
    }
}


async function unblockUser(
    telegramId
) {

    const reason =
        prompt(
            "Why are you unblocking this user?"
        );

    if (!reason) {
        return;
    }

    try {

        await api(
            `/api/admin/users/${encodeURIComponent(telegramId)}/unblock`,
            {
                method: "POST",

                body:
                    JSON.stringify({
                        reason:
                            reason.trim()
                    })
            }
        );

        showToast(
            "User unblocked."
        );

        await openUser(
            telegramId
        );

    } catch (error) {

        showToast(
            error.message
        );
    }
}


async function loadUserAdminActions(
    telegramId
) {

    const box =
        document.getElementById(
            "userAdminActions"
        );

    if (!box) {
        return;
    }

    box.innerHTML =
        "Loading admin history...";

    try {

        const data =
            await api(
                `/api/admin/users/${encodeURIComponent(telegramId)}/admin-actions`
            );

        const actions =
            data.actions || [];

        if (!actions.length) {

            box.innerHTML =
                "<p>No manual admin actions recorded.</p>";

            return;
        }

        box.innerHTML =
            actions
            .map(
                renderAdminAction
            )
            .join("");

    } catch (error) {

        box.innerHTML =
            `<p>
                ${escapeHtml(
                    error.message
                )}
            </p>`;
    }
}


function renderAdminAction(
    item
) {

    const details =
        item.details || {};

    const amount =
        details.amount;

    return `

        <div class="list-card">

            <strong>
                ${escapeHtml(
                    item.action || ""
                )}
            </strong>

            <p>
                Admin:
                ${escapeHtml(
                    item.admin_first_name ||
                    item.admin_username ||
                    item.admin_telegram_id ||
                    ""
                )}
            </p>

            <p>
                Reason:
                ${escapeHtml(
                    item.reason ||
                    "No reason"
                )}
            </p>

            ${
                amount !== undefined
                ? `
                    <p>
                        Amount:
                        ${escapeHtml(
                            String(amount)
                        )}
                    </p>
                `
                : ""
            }

            ${
                details.old_balance !== undefined
                ? `
                    <p>
                        Balance:
                        ${escapeHtml(
                            String(
                                details.old_balance
                            )
                        )}
                        →
                        ${escapeHtml(
                            String(
                                details.new_balance
                            )
                        )}
                    </p>
                `
                : ""
            }

            <small>
                ${escapeHtml(
                    item.created_at ||
                    ""
                )}
            </small>

        </div>

    `;
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
    game.maintenance_mode
    ? "danger"
    : (
        game.active
        ? "active"
        : ""
    )
}">
    ${
        game.maintenance_mode
        ? "🚧 MAINTENANCE"
        : (
            game.active
            ? "ACTIVE"
            : "LOCKED"
        )
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

<button
    class="${
        game.maintenance_mode
        ? "primary-btn"
        : "secondary-btn"
    } full"
    onclick="toggleGameMaintenance(
        '${game.id}',
        ${!game.maintenance_mode}
    )"
>
    ${
        game.maintenance_mode
        ? "✅ End Maintenance"
        : "🚧 Put Under Maintenance"
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

async function toggleGameMaintenance(
    gameId,
    maintenance
) {

    try {

        await api(
            `/api/admin/games/${encodeURIComponent(
                gameId
            )}/update`,
            {
                method: "POST",

                body:
                    JSON.stringify({
                        maintenance_mode:
                            maintenance
                    })
            }
        );

        showToast(
            maintenance
            ? "🚧 Game placed under maintenance."
            : "✅ Game maintenance ended."
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
        "maintenanceMessage"
    )
    .value =
    settings.maintenance_message
    ||
    "QuizBee is currently under maintenance. Please check back soon.";

const exceptionIds =
    Array.isArray(
        settings.maintenance_exceptions
    )
    ? settings.maintenance_exceptions
    : [];

document
    .getElementById(
        "maintenanceExceptions"
    )
    .value =
    exceptionIds.join(
        "\n"
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

        maintenance_message:
            document
            .getElementById(
                "maintenanceMessage"
            ).value
            .trim(),

        maintenance_exceptions:
            document
            .getElementById(
                "maintenanceExceptions"
            ).value
            .split(/\r?\n|,/)
            .map(
                id =>
                    id.trim()
            )
            .filter(Boolean),

        daily_earning_enabled:
            document
            .getElementById(
                "dailyEnabled"
            ).checked

    })
            }
        );

        const maintenanceEnabled =
    document
    .getElementById(
        "maintenanceMode"
    ).checked;

showToast(
    maintenanceEnabled
    ? "🚧 Maintenance mode enabled."
    : "✅ Settings saved."
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

        const search =
            document.getElementById(
                "userSearch"
            );

        if (search) {

            search.addEventListener(
                "keydown",
                event => {

                    if (
                        event.key === "Enter"
                    ) {

                        loadUsers();

                    }

                }
            );

        }

    }
);

function openRequestedAdminSection() {
    const params = new URLSearchParams(window.location.search);
    const section = params.get("section");

    if (!section) {
        return;
    }

    const sectionMap = {
        dashboard: "dashboard",
        games: "games",
        challenges: "challenges",
        daily: "daily",
        withdrawals: "withdrawals",
        orders: "orders",
        users: "users",
        transactions: "transactions",
        settings: "settings"
    };

    const target = sectionMap[section];

    if (!target) {
        return;
    }

    const element = document.getElementById(target);

    if (element) {
        element.scrollIntoView({
            behavior: "smooth",
            block: "start"
        });
    }
}


document.addEventListener(
    "DOMContentLoaded",
    openRequestedAdminSection
);

/* ============================================================
   RAFFLE DRAW
============================================================ */

let currentRaffle = null;


async function loadRafflePage() {

    await loadRaffleSettings();
    await loadRaffles();

}


async function loadRaffleSettings() {

    try {

        const data =
            await api(
                "/api/admin/bootstrap"
            );

        const enabled =
            Boolean(
                data.raffle_enabled
            );

        const checkbox =
            document.getElementById(
                "raffleEnabled"
            );

        const status =
            document.getElementById(
                "raffleSystemStatus"
            );

        if (checkbox) {
            checkbox.checked =
                enabled;
        }

        if (status) {

            status.textContent =
                enabled
                ? "Enabled"
                : "Locked";

            status.className =
                enabled
                ? "badge active"
                : "badge";
        }

    } catch (error) {

        showToast(
            error.message
        );

    }

}


async function toggleRaffleEnabled() {

    const checkbox =
        document.getElementById(
            "raffleEnabled"
        );

    const enabled =
        checkbox.checked;

    try {

        await api(
            "/api/admin/raffle/settings",
            {
                method: "POST",

                body:
                    JSON.stringify({
                        raffle_enabled:
                            enabled
                    })
            }
        );

        const status =
            document.getElementById(
                "raffleSystemStatus"
            );

        if (status) {

            status.textContent =
                enabled
                ? "Enabled"
                : "Locked";

            status.className =
                enabled
                ? "badge active"
                : "badge";
        }

        showToast(
            enabled
            ? "Raffle system enabled."
            : "Raffle system locked."
        );

    } catch (error) {

        checkbox.checked =
            !enabled;

        showToast(
            error.message
        );

    }

}


async function createRaffle() {

    const prizeName =
        document
        .getElementById(
            "rafflePrizeName"
        )
        .value
        .trim();

    const prizeImage =
        document
        .getElementById(
            "rafflePrizeImage"
        )
        .value
        .trim();

    const start =
        document
        .getElementById(
            "raffleStart"
        )
        .value;

    const end =
        document
        .getElementById(
            "raffleEnd"
        )
        .value;


    if (!prizeName) {

        showToast(
            "Enter the prize name."
        );

        return;
    }


    if (!start) {

        showToast(
            "Select the raffle start date and time."
        );

        return;
    }


    if (!end) {

        showToast(
            "Select the raffle end date and time."
        );

        return;
    }


    const startDate =
        new Date(start);

    const endDate =
        new Date(end);


    if (
        Number.isNaN(
            startDate.getTime()
        )
        ||
        Number.isNaN(
            endDate.getTime()
        )
    ) {

        showToast(
            "Invalid raffle date/time."
        );

        return;
    }


    if (
        endDate <= startDate
    ) {

        showToast(
            "End time must be after start time."
        );

        return;
    }


    try {

        await api(
            "/api/raffles/admin/create",
            {
                method: "POST",

                body:
                    JSON.stringify({

                        prize_name:
                            prizeName,

                        prize_image:
                            prizeImage,

                        start_at:
                            startDate.toISOString(),

                        end_at:
                            endDate.toISOString()

                    })
            }
        );


        showToast(
            "Raffle created successfully."
        );


        document
        .getElementById(
            "rafflePrizeName"
        )
        .value = "";


        document
        .getElementById(
            "rafflePrizeImage"
        )
        .value = "";


        document
        .getElementById(
            "raffleStart"
        )
        .value = "";


        document
        .getElementById(
            "raffleEnd"
        )
        .value = "";


        document
        .getElementById(
            "raffleImagePreview"
        )
        .innerHTML =
            "No image selected.";


        await loadRaffles();


    } catch (error) {

        showToast(
            error.message
        );

    }

}


async function loadRaffles() {

    const list =
        document.getElementById(
            "rafflesList"
        );

    if (!list) {
        return;
    }


    list.innerHTML =
        "Loading raffles...";


    try {

        const data =
            await api(
                "/api/raffles/admin"
            );

        const raffles =
            data.raffles || [];


        if (!raffles.length) {

            list.innerHTML =
                `<div class="list-card">
                    No raffles created yet.
                </div>`;

            return;
        }


        list.innerHTML =
            raffles
            .map(
                renderRaffleCard
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


function renderRaffleCard(item) {

    const raffle =
        item.raffle || {};

    const status =
        item.status || "unknown";

    const raffleId =
        item.id ||
        raffle.raffle_id ||
        "";


    return `

        <div class="list-card">

            <div class="row">

                <div>

                    <h3>
                        🎟️
                        ${escapeHtml(
                            raffle.prize_name ||
                            "Raffle"
                        )}
                    </h3>

                    <p>
                        ID:
                        ${escapeHtml(
                            raffleId
                        )}
                    </p>

                </div>


                <span
                    class="badge ${escapeHtml(
                        status
                    )}"
                >
                    ${escapeHtml(
                        status
                    )}
                </span>

            </div>


            <p>
                Ticket Price:
                <strong>
                    100 Points
                </strong>
            </p>


            <p>
                Tickets Sold:
                <strong>
                    ${Number(
                        raffle.ticket_counter ||
                        0
                    ).toLocaleString()}
                </strong>
            </p>


            <p>
                Start:
                ${formatRaffleDate(
                    raffle.start_at
                )}
            </p>


            <p>
                End:
                ${formatRaffleDate(
                    raffle.end_at
                )}
            </p>


            <div class="form-actions">

                <button
                    class="secondary-btn"
                    onclick="viewRaffleTickets('${escapeHtml(
                        raffleId
                    )}')"
                >
                    🎟️ Tickets
                </button>

                ${
                    status !== "ended"
                    ? `
                        <button
                            class="danger-btn"
                            onclick="endRaffle('${escapeHtml(
                                raffleId
                            )}')"
                        >
                            End
                        </button>
                    `
                    : ""
                }

            </div>


            <button
                class="danger-btn full"
                onclick="deleteRaffle('${escapeHtml(
                    raffleId
                )}')"
            >
                🗑️ Delete Raffle
            </button>

        </div>

    `;

}


function formatRaffleDate(value) {

    if (!value) {
        return "—";
    }

    const date =
        new Date(value);

    if (
        Number.isNaN(
            date.getTime()
        )
    ) {
        return "Invalid date";
    }

    return date.toLocaleString();

}


async function viewRaffleTickets(
    raffleId
) {

    const box =
        document.getElementById(
            "raffleDetails"
        );

    if (!box) {

        showToast(
            "Raffle details panel not found."
        );

        return;
    }

    box.classList.remove(
        "hidden"
    );

    box.innerHTML =
        `<div class="panel">
            <div class="panel-header">
                <h2>🎟️ Tickets</h2>
                <button
                    class="secondary-btn"
                    onclick="closeRaffleDetails()"
                >
                    Close
                </button>
            </div>

            <p>
                Loading tickets...
            </p>
        </div>`;

    try {

        const data =
            await api(
                `/api/raffles/admin/${encodeURIComponent(
                    raffleId
                )}/tickets`
            );

        const tickets =
            data.tickets || [];

        const ticketIds =
            data.ticket_ids || [];

        box.innerHTML = `

            <div class="panel">

                <div class="panel-header">

                    <h2>
                        🎟️ Tickets
                    </h2>

                    <button
                        class="secondary-btn"
                        onclick="closeRaffleDetails()"
                    >
                        Close
                    </button>

                </div>

                <p>
                    Total Tickets:
                    <strong>
                        ${tickets.length}
                    </strong>
                </p>

                <button
                    class="primary-btn full"
                    onclick='copyAllRaffleTickets(${JSON.stringify(
                        ticketIds
                    )})'
                >
                    📋 Copy All Tickets
                </button>

                <div class="info-box">

                    <strong>
                        Ticket IDs
                    </strong>

                    <p
                        id="raffleTicketLine"
                        style="
                            word-break: break-all;
                        "
                    >
                        ${
                            ticketIds.length
                            ? escapeHtml(
                                ticketIds.join(
                                    ", "
                                )
                            )
                            : "No tickets yet."
                        }
                    </p>

                </div>

                <label>
                    Search Ticket
                </label>

                <div class="search-box">

                    <input
                        id="raffleTicketSearch"
                        placeholder="QB-RF-000001"
                    >

                    <button
                        onclick="searchRaffleTicket('${escapeHtml(
                            raffleId
                        )}')"
                    >
                        Search
                    </button>

                </div>

                <div
                    id="raffleTicketSearchResult"
                ></div>

                <div class="list">

                    ${
                        tickets.length
                        ? tickets
                            .map(
                                renderRaffleTicket
                            )
                            .join("")
                        : `
                            <div class="list-card">
                                No tickets purchased yet.
                            </div>
                        `
                    }

                </div>

            </div>

        `;

    } catch (error) {

        box.innerHTML = `

            <div class="panel">

                <div class="panel-header">

                    <h2>
                        🎟️ Tickets
                    </h2>

                    <button
                        class="secondary-btn"
                        onclick="closeRaffleDetails()"
                    >
                        Close
                    </button>

                </div>

                <div class="info-box">

                    <strong>
                        ⚠️ Unable to load tickets
                    </strong>

                    <p>
                        ${escapeHtml(
                            error.message
                        )}
                    </p>

                    <button
                        class="primary-btn full"
                        onclick="viewRaffleTickets('${escapeHtml(
                            raffleId
                        )}')"
                    >
                        🔄 Try Again
                    </button>

                </div>

            </div>

        `;

    }

}


function renderRaffleTicket(
    ticket
) {

    const name =
        [
            ticket.first_name,
            ticket.username
                ? `@${ticket.username}`
                : ""
        ]
        .filter(Boolean)
        .join(" ");


    return `

        <div class="list-card">

            <div class="row">

                <strong>
                    ${escapeHtml(
                        ticket.ticket_id ||
                        ticket.id ||
                        ""
                    )}
                </strong>

                <span class="badge active">
                    Active
                </span>

            </div>


            <p>
                User:
                ${escapeHtml(
                    name ||
                    "Unknown"
                )}
            </p>


            <p>
                Telegram ID:
                ${escapeHtml(
                    ticket.telegram_id ||
                    ""
                )}
            </p>


            <p>
                Purchased:
                ${formatRaffleDate(
                    ticket.created_at
                )}
            </p>

        </div>

    `;

}


async function searchRaffleTicket(
    raffleId
) {

    const input =
        document.getElementById(
            "raffleTicketSearch"
        );

    const result =
        document.getElementById(
            "raffleTicketSearchResult"
        );


    const ticketId =
        input.value.trim();


    if (!ticketId) {

        showToast(
            "Enter a ticket ID."
        );

        return;
    }


    result.innerHTML =
        "Searching...";


    try {

        const data =
            await api(
                `/api/raffles/admin/${encodeURIComponent(
                    raffleId
                )}/tickets/search?ticket_id=${encodeURIComponent(
                    ticketId
                )}`
            );


        const ticket =
            data.ticket || {};


        result.innerHTML = `

            <div class="info-box">

                <strong>
                    🎟️ ${escapeHtml(
                        ticket.ticket_id ||
                        ticketId
                    )}
                </strong>

                <p>
                    Username:
                    @${escapeHtml(
                        ticket.username ||
                        "none"
                    )}
                </p>

                <p>
                    Name:
                    ${escapeHtml(
                        ticket.first_name ||
                        "Unknown"
                    )}
                </p>

                <p>
                    Telegram ID:
                    ${escapeHtml(
                        ticket.telegram_id ||
                        ""
                    )}
                </p>

                <p>
                    Purchase ID:
                    ${escapeHtml(
                        ticket.purchase_id ||
                        ""
                    )}
                </p>

            </div>

        `;

    } catch (error) {

        result.innerHTML =
            `<div class="info-box">
                ${escapeHtml(
                    error.message
                )}
            </div>`;

    }

}


async function copyAllRaffleTickets(
    ticketIds
) {

    if (!ticketIds.length) {

        showToast(
            "There are no tickets to copy."
        );

        return;
    }


    const text =
        ticketIds.join(
            ", "
        );


    try {

        await navigator.clipboard.writeText(
            text
        );

        showToast(
            "All ticket IDs copied."
        );

    } catch (error) {

        showToast(
            "Unable to copy tickets."
        );

    }

}


async function endRaffle(
    raffleId
) {

    if (
        !confirm(
            "End this raffle now?"
        )
    ) {
        return;
    }


    try {

        await api(
            `/api/raffles/admin/${encodeURIComponent(
                raffleId
            )}/end`,
            {
                method: "POST"
            }
        );


        showToast(
            "Raffle ended."
        );


        await loadRaffles();


    } catch (error) {

        showToast(
            error.message
        );

    }

}


async function deleteRaffle(
    raffleId
) {

    if (
        !confirm(
            "Delete this raffle and ALL of its tickets? This cannot be undone."
        )
    ) {
        return;
    }


    try {

        await api(
            `/api/raffles/admin/${encodeURIComponent(
                raffleId
            )}`,
            {
                method: "DELETE"
            }
        );


        showToast(
            "Raffle deleted."
        );


        closeRaffleDetails();

        await loadRaffles();


    } catch (error) {

        showToast(
            error.message
        );

    }

}


function closeRaffleDetails() {

    const box =
        document.getElementById(
            "raffleDetails"
        );

    if (box) {

        box.classList.add(
            "hidden"
        );

        box.innerHTML = "";

    }

}


/* ============================================================
   RAFFLE IMAGE PREVIEW
============================================================ */

document.addEventListener(
    "input",
    event => {

        if (
            event.target.id !==
            "rafflePrizeImage"
        ) {
            return;
        }

        const url =
            event.target.value.trim();

        const preview =
            document.getElementById(
                "raffleImagePreview"
            );

        if (!preview) {
            return;
        }

        if (!url) {

            preview.innerHTML =
                "No image selected.";

            return;
        }

        preview.innerHTML = `
            <img
                src="${escapeHtml(url)}"
                alt="Prize preview"
                style="
                    max-width: 100%;
                    max-height: 220px;
                    border-radius: 14px;
                "
            >
        `;

    }
); 
