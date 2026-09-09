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


function getTelegramUser() {

    if (tg?.initDataUnsafe?.user) {
        return tg.initDataUnsafe.user;
    }

    return user;
}


user = getTelegramUser();


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


function toast(message) {

    const el = document.getElementById("toast");

    el.textContent = message;
    el.classList.add("show");

    setTimeout(() => {
        el.classList.remove("show");
    }, 2500);
}


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


function renderGameCard(game) {

    const locked = game.status !== "active";

    return `
        <div
            class="game-card ${locked ? "locked" : ""}"
            onclick="${locked ? "lockedGame()" : `openGame('${game.id}')`}"
        >

            <span class="status ${locked ? "locked" : "unlocked"}">
                ${locked ? "🔒 LOCKED" : "● LIVE"}
            </span>

            <div class="game-icon">${game.emoji}</div>

            <h3>${game.name}</h3>

            <p>${gameDescription(game.id)}</p>

        </div>
    `;
}


function renderGames() {

    const container = document.getElementById("gamesList");

    container.innerHTML = state.games.map(game => {

        const locked = game.status !== "active";

        return `
            <div
                class="game-list-card ${locked ? "locked-card" : ""}"
                onclick="${locked ? "lockedGame()" : `openGame('${game.id}')`}"
            >

                <div class="game-icon">${game.emoji}</div>

                <div class="game-info">
                    <h3>${game.name}</h3>
                    <p>${gameDescription(game.id)}</p>
                    <div class="entry">
                        Entry: ${game.entry_points} Points
                    </div>
                </div>

                <div>
                    ${locked ? "🔒" : "›"}
                </div>

            </div>
        `;
    }).join("");
}


function renderHomeGames() {

    const container = document.getElementById("homeGames");

    container.innerHTML = state.games
        .slice(0, 4)
        .map(renderGameCard)
        .join("");
}


function lockedGame() {

    toast("🔒 Coming Soon — this game is currently locked.");
}


async function openGame(gameId) {

    const game = state.games.find(g => g.id === gameId);

    if (!game) return;

    if (game.status !== "active") {
        lockedGame();
        return;
    }

    currentGame = game;

    document.getElementById("gameTitle").textContent =
        `${game.emoji} ${game.name}`;

    document.getElementById("gameContent").innerHTML = `
        <div class="game-detail-card">

            <div class="game-detail-icon">
                ${game.emoji}
            </div>

            <h2>${game.name}</h2>

            <p class="game-description">
                ${gameDescription(game.id)}
            </p>

            <div class="info-box">
                Entry fee: <strong>${game.entry_points} QuizBee Points</strong>
            </div>

            <button
                class="primary-btn"
                onclick="enterGame()"
            >
                ENTER GAME — ${game.entry_points} POINTS
            </button>

        </div>
    `;

    showPage("game");
}


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

        state.points = result.points;

        updateBalances();

        toast("Entry successful!");

        await loadChallenge();

    } catch (error) {

        toast(error.message);

    }
}


async function loadChallenge() {

    try {

        const data = await api(
            `/api/games/${currentGame.id}/challenge`
        );

        currentChallenge = data;

        renderChallenge(data);

    } catch (error) {

        toast(error.message);

    }
}


function renderChallenge(challenge) {

    const container = document.getElementById("gameContent");

    if (challenge.type === "guess_it") {
        renderGuessIt(challenge);
        return;
    }

    if (challenge.type === "impossible_question") {
        renderImpossibleQuestion(challenge);
        return;
    }

    if (challenge.type === "crowd_trap") {
        renderNumberChoice(challenge, "crowd");
        return;
    }

    if (challenge.type === "survivor") {
        renderSurvivor(challenge);
        return;
    }

    if (challenge.type === "dead_number") {
        renderNumberChoice(challenge, "dead");
        return;
    }

    if (challenge.type === "impossible_choice") {
        renderImpossibleChoice(challenge);
        return;
    }
}


function renderGuessIt(challenge) {

    document.getElementById("gameContent").innerHTML = `

        <div class="game-detail-card">

            <div class="challenge-box">

                <h3>🎯 Guess It</h3>

                <div class="question">
                    ${challenge.prompt}
                </div>

                <div class="info-box">
                    ${challenge.clue || ""}
                </div>

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


function renderImpossibleQuestion(challenge) {

    document.getElementById("gameContent").innerHTML = `

        <div class="game-detail-card">

            <div class="challenge-box">

                <h3>💀 Weekly Impossible Question</h3>

                <div class="question">
                    ${challenge.prompt}
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


function renderNumberChoice(challenge, mode) {

    document.getElementById("gameContent").innerHTML = `

        <div class="game-detail-card">

            <div class="challenge-box">

                <h3>
                    ${mode === "crowd"
                        ? "🧠 The Crowd Trap"
                        : "☠️ Dead Number"}
                </h3>

                <div class="question">
                    ${challenge.prompt}
                </div>

                <div class="info-box">
                    Choose between
                    <strong>${challenge.min}</strong>
                    and
                    <strong>${challenge.max}</strong>.
                </div>

                <input
                    id="numberInput"
                    class="number-input"
                    type="number"
                    min="${challenge.min}"
                    max="${challenge.max}"
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


function renderSurvivor(challenge) {

    document.getElementById("gameContent").innerHTML = `

        <div class="game-detail-card">

            <div class="challenge-box">

                <h3>🏆 The Survivor</h3>

                <div class="question">
                    ${challenge.prompt}
                </div>

                <div class="info-box">
                    Round ${challenge.round} —
                    ${challenge.options.length} options.
                    Only one is safe.
                </div>

                <div class="options">

                    ${challenge.options.map(option => `
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


function renderImpossibleChoice(challenge) {

    document.getElementById("gameContent").innerHTML = `

        <div class="game-detail-card">

            <div class="challenge-box">

                <h3>🤔 Impossible Choice</h3>

                <div class="question">
                    ${challenge.prompt}
                </div>

                <div class="info-box">
                    Don't choose what YOU prefer.
                    Predict what the crowd will do.
                </div>

                <div class="options">

                    ${challenge.options.map(option => `
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


function escapeQuotes(value) {

    return String(value)
        .replace(/\\/g, "\\\\")
        .replace(/'/g, "\\'");
}


async function submitAnswer() {

    const input = document.getElementById("answerInput");

    if (!input || !input.value.trim()) {
        toast("Enter an answer first.");
        return;
    }

    await submitGameAnswer(input.value.trim());
}


async function submitNumber(mode) {

    const input = document.getElementById("numberInput");

    const number = Number(input.value);

    if (!number) {
        toast("Enter a number.");
        return;
    }

    await submitGameAnswer(String(number));
}


async function submitChoice(choice) {

    await submitGameAnswer(choice);
}


async function submitGameAnswer(answer) {

    try {

        const result = await api(
            `/api/games/${currentGame.id}/answer`,
            {
                method: "POST",
                body: JSON.stringify({
                    answer: answer
                })
            }
        );

        if (result.correct) {

            toast("🎉 Correct! You survived!");

            state.score = result.score || state.score;

        } else {

            toast(
                result.message ||
                "❌ That's not correct. Try again."
            );

        }

        if (result.points !== undefined) {
            state.points = result.points;
            updateBalances();
        }

    } catch (error) {

        toast(error.message);

    }
}


async function watchAd() {

    const button = document.getElementById("watchAdButton");

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

            state.points = result.points;
            state.ads_watched = result.ads_watched;

            updateBalances();
            updateAds();

            toast("+1 QuizBee Point earned!");

        } catch (error) {

            toast(error.message);

        }

        button.disabled = false;
        button.textContent = "📺 WATCH AD";

    }, 1500);
}


function updateAds() {

    const watched = state.ads_watched || 0;

    document.getElementById("adsProgress").textContent =
        `${watched}/10`;

    document.getElementById("adsProgressBar").style.width =
        `${Math.min(watched, 10) * 10}%`;

    if (watched >= 10) {

        document.getElementById("watchAdButton").disabled = true;

        document.getElementById("watchAdButton").textContent =
            "✅ DAILY REWARD COMPLETE";

    }
}


function updateBalances() {

    document.getElementById("pointsBalance").textContent =
        state.points;

    document.getElementById("prizeBalance").textContent =
        `₦${Number(state.prize_balance || 0).toLocaleString()}`;
}


function updateProfile() {

    document.getElementById("profileName").textContent =
        user.first_name || "Player";

    document.getElementById("profileUsername").textContent =
        user.username
            ? `@${user.username}`
            : "Telegram Player";

    document.getElementById("profileScore").textContent =
        state.score || 0;

    document.getElementById("profileStreak").textContent =
        state.streak || 0;

    document.getElementById("profileReferrals").textContent =
        state.referrals || 0;
}


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

        if (!data.players.length) {

            container.innerHTML =
                `<div class="info-box">
                    No players yet.
                </div>`;

            return;
        }

        container.innerHTML =
            data.players.map((player, index) => `
                <div class="rank-row">

                    <div class="rank-number">
                        ${index + 1}
                    </div>

                    <div class="rank-name">
                        ${player.name}
                    </div>

                    <div class="rank-score">
                        ${player.score}
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


function buyPoints() {

    toast("💰 Point purchases will be connected later.");
}


function withdrawPrize() {

    toast("💸 Withdrawals will be connected after the wallet system.");
}


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

        state = {
            ...state,
            ...data.user,
            games: data.games
        };

    } catch (error) {

        console.log(error);

        // Demo fallback
        state.games = defaultGames();
    }

    document.getElementById("welcomeText").textContent =
        `Welcome, ${user.first_name || "Player"} 👋`;

    updateBalances();
    updateProfile();
    updateAds();
    renderGames();
    renderHomeGames();
}


function defaultGames() {

    return [
        {
            id: "guess_it",
            name: "Guess It",
            emoji: "🎯",
            status: "active",
            entry_points: 10
        },
        {
            id: "impossible_question",
            name: "Impossible Question",
            emoji: "💀",
            status: "active",
            entry_points: 10
        },
        {
            id: "crowd_trap",
            name: "The Crowd Trap",
            emoji: "🧠",
            status: "locked",
            entry_points: 10
        },
        {
            id: "survivor",
            name: "The Survivor",
            emoji: "🏆",
            status: "locked",
            entry_points: 10
        },
        {
            id: "dead_number",
            name: "Dead Number",
            emoji: "☠️",
            status: "locked",
            entry_points: 10
        },
        {
            id: "impossible_choice",
            name: "Impossible Choice",
            emoji: "🤔",
            status: "locked",
            entry_points: 10
        }
    ];
}


bootstrap();
