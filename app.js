const tg = window.Telegram?.WebApp;

if (tg) {
    tg.ready();
    tg.expand();
}

const API_URL = window.QUIZBEE_CONFIG?.API_URL || "";

let user = {
    telegram_id: 999000001,
    first_name: "Demo",
    username: "demo_player"
};

let state = {
    points: 0,
    prize_balance: 0,
    score: 0,
    streak: 0,
    referrals: 0,
    ads_watched: 0,
    games: []
};

let currentGame = null;
let currentChallenge = null;


// ============================================================
// TELEGRAM USER
// ============================================================

function getTelegramUser() {

    if (tg?.initDataUnsafe?.user) {
        return tg.initDataUnsafe.user;
    }

    return user;
}

user = getTelegramUser();


// ============================================================
// API
// ============================================================

async function api(path, options = {}) {

    const url = `${API_URL}${path}`;

    const headers = {
        "Content-Type": "application/json"
    };

    if (tg?.initData) {
        headers["X-Telegram-Init-Data"] = tg.initData;
    }

    const response = await fetch(url, {
        ...options,
        headers: {
            ...headers,
            ...(options.headers || {})
        }
    });

    const data = await response.json();

    if (!response.ok) {
        throw new Error(data.error || "Request failed");
    }

    return data;
}


// ============================================================
// TOAST
// ============================================================

function toast(message) {

    const el = document.getElementById("toast");

    if (!el) return;

    el.textContent = message;
    el.classList.add("show");

    setTimeout(() => {
        el.classList.remove("show");
    }, 2500);
}


// ============================================================
// NAVIGATION
// ============================================================

function showPage(page) {

    document.querySelectorAll(".page").forEach(el => {
        el.classList.remove("active");
    });

    const target = document.getElementById(`${page}Page`);

    if (target) {
        target.classList.add("active");
    }

    document.querySelectorAll(".nav-item").forEach(el => {
        el.classList.remove("active");
    });

    const navMap = {
        home: 0,
        games: 1,
        ads: 2,
        leaderboard: 3,
        profile: 4
    };

    if (navMap[page] !== undefined) {

        document.querySelectorAll(".nav-item")[navMap[page]]
            ?.classList.add("active");
    }

    if (page === "games") {
        renderGames();
    }

    if (page === "leaderboard") {
        loadLeaderboard("weekly");
    }

    if (page === "ads") {
        updateAds();
    }

    if (page === "profile") {
        updateProfile();
    }
}


function goHome() {
    showPage("home");
}


// ============================================================
// GAME HELPERS
// ============================================================

function gameDescription(id) {

    const descriptions = {

        guess_it:
            "Use clues to identify the hidden answer before everyone else.",

        impossible_question:
            "A brutally difficult weekly brain teaser. Keep trying until you solve it.",

        crowd_trap:
            "Pick a number nobody else picks. Outsmart the crowd.",

        survivor:
            "Choose one option each round. Pick the safe one or get eliminated.",

        dead_number:
            "Avoid the hidden Dead Numbers. One wrong choice can eliminate you.",

        impossible_choice:
            "Predict what the crowd will do. Your personal preference does not matter."
    };

    return descriptions[id] || "";
}


// ============================================================
// GAME CARD
// ============================================================

function renderGameCard(game) {

    const locked = !game.active;

    return `
        <div
            class="game-card ${locked ? "locked" : ""}"
            onclick="${locked ? "lockedGame()" : `openGame('${game.id}')`}"
        >

            <span class="status ${locked ? "locked" : "unlocked"}">
                ${locked ? "🔒 LOCKED" : "● LIVE"}
            </span>

            <div class="game-icon">
                ${game.icon || "🎮"}
            </div>

            <h3>${game.name}</h3>

            <p>${gameDescription(game.id)}</p>

            <div class="entry">
                Entry: ${game.entry_fee || 0} Points
            </div>

        </div>
    `;
}


// ============================================================
// GAMES LIST
// ============================================================

function renderGames() {

    const container = document.getElementById("gamesList");

    if (!container) return;

    container.innerHTML = state.games.map(game => {

        const locked = !game.active;

        return `
            <div
                class="game-list-card ${locked ? "locked-card" : ""}"
                onclick="${locked ? "lockedGame()" : `openGame('${game.id}')`}"
            >

                <div class="game-icon">
                    ${game.icon || "🎮"}
                </div>

                <div class="game-info">

                    <h3>${game.name}</h3>

                    <p>
                        ${gameDescription(game.id)}
                    </p>

                    <div class="entry">
                        Entry: ${game.entry_fee || 0} Points
                    </div>

                </div>

                <div>
                    ${locked ? "🔒" : "›"}
                </div>

            </div>
        `;
    }).join("");
}


// ============================================================
// HOME GAMES
// ============================================================

function renderHomeGames() {

    const container = document.getElementById("homeGames");

    if (!container) return;

    container.innerHTML = state.games
        .slice(0, 4)
        .map(renderGameCard)
        .join("");
}


// ============================================================
// LOCKED GAME
// ============================================================

function lockedGame() {

    toast("🔒 Coming Soon — this game is currently locked.");
}


// ============================================================
// OPEN GAME
// ============================================================

async function openGame(gameId) {

    const game = state.games.find(g => g.id === gameId);

    if (!game) return;

    if (!game.active) {
        lockedGame();
        return;
    }

    currentGame = game;

    document.getElementById("gameTitle").textContent =
        `${game.icon || "🎮"} ${game.name}`;

    document.getElementById("gameContent").innerHTML = `

        <div class="game-detail-card">

            <div class="game-detail-icon">
                ${game.icon || "🎮"}
            </div>

            <h2>${game.name}</h2>

            <p class="game-description">
                ${gameDescription(game.id)}
            </p>

            <div class="info-box">
                Entry fee:
                <strong>
                    ${game.entry_fee} QuizBee Points
                </strong>
            </div>

            <button
                class="primary-btn"
                onclick="enterGame()"
            >
                ENTER GAME — ${game.entry_fee} POINTS
            </button>

        </div>
    `;

    showPage("game");
}


// ============================================================
// ENTER GAME
// ============================================================

async function enterGame() {

    if (!currentGame) return;

    try {

        const result = await api(
            `/api/games/${currentGame.id}/enter`,
            {
                method: "POST",
                body: JSON.stringify({})
            }
        );

        if (result.user) {

            state.points =
                result.user.quizbee_points ?? state.points;

            state.prize_balance =
                result.user.prize_balance ?? state.prize_balance;

            updateBalances();
        }

        toast(
            result.already_entered
                ? "You already entered this challenge."
                : "Entry successful!"
        );

        if (result.challenge) {

            currentChallenge = result.challenge;

            renderChallenge(currentChallenge);

        } else {

            await loadChallenge();
        }

    } catch (error) {

        toast(error.message);
    }
}


// ============================================================
// LOAD CHALLENGE
// ============================================================

async function loadChallenge() {

    if (!currentGame) return;

    try {

        const data = await api(
            `/api/games/${currentGame.id}/challenge`
        );

        /*
         * Backend returns:
         *
         * {
         *   success: true,
         *   game: {...},
         *   challenge: {...}
         * }
         */

        currentChallenge = data.challenge;

        renderChallenge(currentChallenge);

    } catch (error) {

        toast(error.message);
    }
}


// ============================================================
// RENDER CHALLENGE
// ============================================================

function renderChallenge(challenge) {

    if (!challenge) {
        toast("No challenge available.");
        return;
    }

    /*
     * Backend types:
     *
     * guess
     * text
     * choice
     */

    if (challenge.game_id === "guess_it") {
        renderGuessIt(challenge);
        return;
    }

    if (challenge.game_id === "impossible_question") {
        renderImpossibleQuestion(challenge);
        return;
    }

    if (challenge.game_id === "crowd_trap") {
        renderNumberChoice(challenge, "crowd");
        return;
    }

    if (challenge.game_id === "survivor") {
        renderSurvivor(challenge);
        return;
    }

    if (challenge.game_id === "dead_number") {
        renderNumberChoice(challenge, "dead");
        return;
    }

    if (challenge.game_id === "impossible_choice") {
        renderImpossibleChoice(challenge);
        return;
    }

    toast("Unknown game type.");
}


// ============================================================
// GUESS IT
// ============================================================

function renderGuessIt(challenge) {

    document.getElementById("gameContent").innerHTML = `

        <div class="game-detail-card">

            <div class="challenge-box">

                <h3>🎯 ${challenge.title || "Guess It"}</h3>

                <div class="question">
                    ${formatQuestion(challenge.question)}
                </div>

                ${
                    challenge.metadata?.image_url
                    ? `
                        <img
                            src="${challenge.metadata.image_url}"
                            class="challenge-image"
                            alt="Guess It clue"
                        >
                    `
                    : ""
                }

                <input
                    id="answerInput"
                    class="number-input"
                    type="text"
                    placeholder="Type your answer..."
                >

                <button
                    class="primary-btn"
                    onclick="submitAnswer()"
                >
                    SUBMIT ANSWER
                </button>

            </div>

        </div>
    `;
}


// ============================================================
// IMPOSSIBLE QUESTION
// ============================================================

function renderImpossibleQuestion(challenge) {

    document.getElementById("gameContent").innerHTML = `

        <div class="game-detail-card">

            <div class="challenge-box">

                <h3>
                    💀 ${challenge.title || "Weekly Impossible Question"}
                </h3>

                <div class="question">
                    ${formatQuestion(challenge.question)}
                </div>

                <div class="info-box">
                    You can keep trying until the challenge ends.
                    A wrong answer does not remove your entry.
                </div>

                <input
                    id="answerInput"
                    class="number-input"
                    type="text"
                    placeholder="Your answer..."
                >

                <button
                    class="primary-btn"
                    onclick="submitAnswer()"
                >
                    TRY ANSWER
                </button>

            </div>

        </div>
    `;
}


// ============================================================
// NUMBER GAMES
// ============================================================

function renderNumberChoice(challenge, mode) {

    const min = challenge.min ?? 1;
    const max = challenge.max ?? 20;

    document.getElementById("gameContent").innerHTML = `

        <div class="game-detail-card">

            <div class="challenge-box">

                <h3>
                    ${
                        mode === "crowd"
                            ? "🧠 The Crowd Trap"
                            : "☠️ Dead Number"
                    }
                </h3>

                <div class="question">
                    ${formatQuestion(challenge.question)}
                </div>

                <div class="info-box">
                    Choose between
                    <strong>${min}</strong>
                    and
                    <strong>${max}</strong>.
                </div>

                <input
                    id="numberInput"
                    class="number-input"
                    type="number"
                    min="${min}"
                    max="${max}"
                    placeholder="Enter your number"
                >

                <button
                    class="primary-btn"
                    onclick="submitNumber('${mode}')"
                >
                    LOCK MY CHOICE
                </button>

            </div>

        </div>
    `;
}


// ============================================================
// SURVIVOR
// ============================================================

function renderSurvivor(challenge) {

    const options = challenge.options || [];

    document.getElementById("gameContent").innerHTML = `

        <div class="game-detail-card">

            <div class="challenge-box">

                <h3>
                    🏆 ${challenge.title || "The Survivor"}
                </h3>

                <div class="question">
                    ${formatQuestion(challenge.question)}
                </div>

                <div class="info-box">
                    Choose one option carefully.
                </div>

                <div class="options">

                    ${options.map(option => `
                        <button
                            class="option-btn"
                            onclick="submitChoice('${escapeQuotes(option)}')"
                        >
                            ${option}
                        </button>
                    `).join("")}

                </div>

            </div>

        </div>
    `;
}


// ============================================================
// IMPOSSIBLE CHOICE
// ============================================================

function renderImpossibleChoice(challenge) {

    const options = challenge.options || [];

    document.getElementById("gameContent").innerHTML = `

        <div class="game-detail-card">

            <div class="challenge-box">

                <h3>
                    🤔 ${challenge.title || "Impossible Choice"}
                </h3>

                <div class="question">
                    ${formatQuestion(challenge.question)}
                </div>

                <div class="info-box">
                    Don't choose what YOU prefer.
                    Predict what the crowd will do.
                </div>

                <div class="options">

                    ${options.map(option => `
                        <button
                            class="option-btn"
                            onclick="submitChoice('${escapeQuotes(option)}')"
                        >
                            ${option}
                        </button>
                    `).join("")}

                </div>

            </div>

        </div>
    `;
}


// ============================================================
// QUESTION FORMATTER
// ============================================================

function formatQuestion(value) {

    if (!value) return "";

    return String(value)
        .replace(/\n/g, "<br>");
}


// ============================================================
// ESCAPE
// ============================================================

function escapeQuotes(value) {

    return String(value)
        .replace(/\\/g, "\\\\")
        .replace(/'/g, "\\'");
}


// ============================================================
// ANSWER
// ============================================================

async function submitAnswer() {

    const input = document.getElementById("answerInput");

    if (!input || !input.value.trim()) {
        toast("Enter an answer first.");
        return;
    }

    await submitGameAnswer(input.value.trim());
}


// ============================================================
// NUMBER ANSWER
// ============================================================

async function submitNumber(mode) {

    const input = document.getElementById("numberInput");

    if (!input || input.value === "") {
        toast("Enter a number.");
        return;
    }

    const number = Number(input.value);

    const min = currentChallenge?.min ?? 1;
    const max = currentChallenge?.max ?? 20;

    if (number < min || number > max) {
        toast(`Choose a number between ${min} and ${max}.`);
        return;
    }

    await submitGameAnswer(String(number));
}


// ============================================================
// CHOICE ANSWER
// ============================================================

async function submitChoice(choice) {

    await submitGameAnswer(choice);
}


// ============================================================
// SUBMIT GAME ANSWER
// ============================================================

async function submitGameAnswer(answer) {

    if (!currentGame || !currentChallenge) {
        toast("No active challenge.");
        return;
    }

    try {

        const result = await api(
            `/api/games/${currentGame.id}/answer`,
            {
                method: "POST",

                body: JSON.stringify({
                    challenge_id: currentChallenge.id,
                    answer: answer
                })
            }
        );

        if (result.correct) {

            toast(
                result.message ||
                "🎉 Correct! You won!"
            );

            if (result.reward) {

                state.points += Number(result.reward);

                updateBalances();
            }

        } else {

            toast(
                result.message ||
                "❌ That's not correct. Try again."
            );
        }

    } catch (error) {

        toast(error.message);
    }
}


// ============================================================
// ADS
// ============================================================

async function watchAd() {

    const button = document.getElementById("watchAdButton");

    if (!button) return;

    button.disabled = true;
    button.textContent = "📺 WATCHING...";

    setTimeout(async () => {

        try {

            const result = await api(
                "/api/ads/mock-complete",
                {
                    method: "POST",
                    body: JSON.stringify({})
                }
            );

            state.points += Number(result.reward || 1);
            state.ads_watched += 1;

            updateBalances();
            updateAds();

            toast(
                result.message ||
                "+1 QuizBee Point earned!"
            );

        } catch (error) {

            toast(error.message);
        }

        button.disabled = false;
        button.textContent = "📺 WATCH AD";

    }, 1500);
}


// ============================================================
// ADS UI
// ============================================================

function updateAds() {

    const watched = state.ads_watched || 0;

    const progress =
        document.getElementById("adsProgress");

    const progressBar =
        document.getElementById("adsProgressBar");

    const button =
        document.getElementById("watchAdButton");

    if (progress) {
        progress.textContent = `${watched}/10`;
    }

    if (progressBar) {
        progressBar.style.width =
            `${Math.min(watched, 10) * 10}%`;
    }

    if (button && watched >= 10) {

        button.disabled = true;

        button.textContent =
            "✅ DAILY REWARD COMPLETE";
    }
}


// ============================================================
// BALANCES
// ============================================================

function updateBalances() {

    const points =
        document.getElementById("pointsBalance");

    const prize =
        document.getElementById("prizeBalance");

    if (points) {
        points.textContent = state.points || 0;
    }

    if (prize) {

        prize.textContent =
            `₦${Number(
                state.prize_balance || 0
            ).toLocaleString()}`;
    }
}


// ============================================================
// PROFILE
// ============================================================

function updateProfile() {

    const name =
        document.getElementById("profileName");

    const username =
        document.getElementById("profileUsername");

    const score =
        document.getElementById("profileScore");

    const streak =
        document.getElementById("profileStreak");

    const referrals =
        document.getElementById("profileReferrals");

    if (name) {

        name.textContent =
            user.first_name || "Player";
    }

    if (username) {

        username.textContent =
            user.username
                ? `@${user.username}`
                : "Telegram Player";
    }

    if (score) {
        score.textContent = state.score || 0;
    }

    if (streak) {
        streak.textContent = state.streak || 0;
    }

    if (referrals) {
        referrals.textContent = state.referrals || 0;
    }
}


// ============================================================
// LEADERBOARD
// ============================================================

async function loadLeaderboard(type = "weekly", button = null) {

    if (button) {

        document.querySelectorAll(".tabs button")
            .forEach(b => b.classList.remove("active"));

        button.classList.add("active");
    }

    try {

        const data = await api(
            `/api/leaderboard?type=${type}`
        );

        const container =
            document.getElementById("leaderboardList");

        const players =
            data.leaderboard || [];

        if (!players.length) {

            container.innerHTML =
                `<div class="info-box">
                    No players yet.
                </div>`;

            return;
        }

        container.innerHTML =
            players.map((player, index) => `

                <div class="rank-row">

                    <div class="rank-number">
                        ${player.rank || index + 1}
                    </div>

                    <div class="rank-name">
                        ${player.first_name || player.username || "Player"}
                    </div>

                    <div class="rank-score">
                        ${player.total_earned || 0}
                    </div>

                </div>

            `).join("");

    } catch (error) {

        document.getElementById("leaderboardList").innerHTML =
            `<div class="info-box">
                Leaderboard unavailable.
            </div>`;
    }
}


// ============================================================
// FUTURE PAYMENTS
// ============================================================

function buyPoints() {

    toast(
        "💰 Point purchases will be connected later."
    );
}


function withdrawPrize() {

    toast(
        "💸 Withdrawals will be connected after the wallet system."
    );
}


// ============================================================
// BOOTSTRAP
// ============================================================

async function bootstrap() {

    try {

        const data = await api(
            "/api/bootstrap",
            {
                method: "POST",

                body: JSON.stringify({
                    telegram_user: user
                })
            }
        );

        const backendUser = data.user || {};

        state.points =
            backendUser.quizbee_points ?? 0;

        state.prize_balance =
            backendUser.prize_balance ?? 0;

        state.score =
            backendUser.total_earned ?? 0;

        state.streak =
            backendUser.streak_days ?? 0;

        state.referrals =
            backendUser.referrals_count ?? 0;

        state.games =
            data.games || [];

    } catch (error) {

        console.log("Bootstrap error:", error);

        state.games = defaultGames();
    }

    const welcome =
        document.getElementById("welcomeText");

    if (welcome) {

        welcome.textContent =
            `Welcome, ${user.first_name || "Player"} 👋`;
    }

    updateBalances();
    updateProfile();
    updateAds();
    renderGames();
    renderHomeGames();
}


// ============================================================
// FALLBACK GAMES
// ============================================================

function defaultGames() {

    return [

        {
            id: "guess_it",
            name: "Guess It",
            icon: "🎯",
            active: true,
            entry_fee: 10
        },

        {
            id: "impossible_question",
            name: "Impossible Question",
            icon: "💀",
            active: true,
            entry_fee: 10
        },

        {
            id: "crowd_trap",
            name: "The Crowd Trap",
            icon: "🧠",
            active: false,
            entry_fee: 10
        },

        {
            id: "survivor",
            name: "The Survivor",
            icon: "🏆",
            active: false,
            entry_fee: 10
        },

        {
            id: "dead_number",
            name: "Dead Number",
            icon: "☠️",
            active: false,
            entry_fee: 10
        },

        {
            id: "impossible_choice",
            name: "Impossible Choice",
            icon: "🤔",
            active: false,
            entry_fee: 10
        }
    ];
}


// ============================================================
// START
// ============================================================

bootstrap();
