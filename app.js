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

    let data;

    try {
        data = await response.json();
    } catch {
        throw new Error(`Server returned ${response.status}`);
    }

    if (!response.ok) {
        throw new Error(
            data.error ||
            data.message ||
            "Request failed"
        );
    }

    return data;
}


// ============================================================
// UI HELPERS
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


function showPage(page) {

    document.querySelectorAll(".page").forEach(el => {
        el.classList.remove("active");
    });

    const target =
        document.getElementById(`${page}Page`);

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

        document
            .querySelectorAll(".nav-item")[navMap[page]]
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
// GAME INFORMATION
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
// NORMALIZE FIREBASE GAME DATA
// ============================================================

function normalizeGames(games) {

    return (games || []).map(game => {

        return {
            id: game.id,

            name: game.name,

            emoji:
                game.icon ||
                game.emoji ||
                "🎮",

            status:
                game.active === true
                    ? "active"
                    : "locked",

            entry_points:
                Number(
                    game.entry_fee ??
                    game.entry_points ??
                    10
                ),

            description:
                game.description ||
                gameDescription(game.id),

            sort_order:
                Number(game.sort_order || 0)
        };

    });
}


// ============================================================
// GAME RENDERING
// ============================================================

function renderGameCard(game) {

    const locked = game.status !== "active";

    return `
        <div
            class="game-card ${locked ? "locked" : ""}"
            onclick="${
                locked
                    ? "lockedGame()"
                    : `openGame('${game.id}')`
            }"
        >

            <span class="status ${locked ? "locked" : "unlocked"}">
                ${locked ? "🔒 LOCKED" : "● LIVE"}
            </span>

            <div class="game-icon">
                ${game.emoji}
            </div>

            <h3>
                ${game.name}
            </h3>

            <p>
                ${gameDescription(game.id)}
            </p>

        </div>
    `;
}


function renderGames() {

    const container =
        document.getElementById("gamesList");

    if (!container) return;

    if (!state.games.length) {

        container.innerHTML = `
            <div class="info-box">
                No games available yet.
            </div>
        `;

        return;
    }

    container.innerHTML =
        state.games.map(game => {

            const locked =
                game.status !== "active";

            return `
                <div
                    class="game-list-card ${locked ? "locked-card" : ""}"
                    onclick="${
                        locked
                            ? "lockedGame()"
                            : `openGame('${game.id}')`
                    }"
                >

                    <div class="game-icon">
                        ${game.emoji}
                    </div>

                    <div class="game-info">

                        <h3>
                            ${game.name}
                        </h3>

                        <p>
                            ${gameDescription(game.id)}
                        </p>

                        <div class="entry">
                            Entry:
                            ${game.entry_points}
                            Points
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

    const container =
        document.getElementById("homeGames");

    if (!container) return;

    container.innerHTML =
        state.games
            .slice(0, 4)
            .map(renderGameCard)
            .join("");
}


function lockedGame() {

    toast(
        "🔒 Coming Soon — this game is currently locked."
    );
}


// ============================================================
// OPEN GAME
// ============================================================

async function openGame(gameId) {

    const game =
        state.games.find(g => g.id === gameId);

    if (!game) {
        toast("Game not found.");
        return;
    }

    if (game.status !== "active") {
        lockedGame();
        return;
    }

    currentGame = game;

    const title =
        document.getElementById("gameTitle");

    if (title) {
        title.textContent =
            `${game.emoji} ${game.name}`;
    }

    const content =
        document.getElementById("gameContent");

    if (!content) return;

    content.innerHTML = `

        <div class="game-detail-card">

            <div class="game-detail-icon">
                ${game.emoji}
            </div>

            <h2>
                ${game.name}
            </h2>

            <p class="game-description">
                ${gameDescription(game.id)}
            </p>

            <div class="info-box">
                Entry fee:
                <strong>
                    ${game.entry_points}
                    QuizBee Points
                </strong>
            </div>

            <button
                class="primary-btn"
                onclick="enterGame()"
            >
                ENTER GAME —
                ${game.entry_points}
                POINTS
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
            updateUserState(result.user);
        }

        updateBalances();

        if (result.already_entered) {

            toast(
                "You already entered this challenge."
            );

        } else {

            toast("Entry successful! 🎉");
        }

        await loadChallenge();

    } catch (error) {

        console.error(error);

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
         *
         * We only want the challenge object here.
         */

        currentChallenge = data.challenge;

        if (!currentChallenge) {
            throw new Error(
                "No challenge data received."
            );
        }

        renderChallenge(currentChallenge);

    } catch (error) {

        console.error(error);

        toast(error.message);
    }
}


// ============================================================
// RENDER CHALLENGE
// ============================================================

function renderChallenge(challenge) {

    if (!currentGame) return;

    /*
     * We use the GAME ID rather than challenge.type.
     *
     * Firebase demo challenges use types like:
     * "guess", "text", and "choice".
     *
     * The game ID tells us exactly which UI to display.
     */

    if (currentGame.id === "guess_it") {

        renderGuessIt(challenge);
        return;
    }

    if (
        currentGame.id ===
        "impossible_question"
    ) {

        renderImpossibleQuestion(challenge);
        return;
    }

    if (currentGame.id === "crowd_trap") {

        renderNumberChoice(
            challenge,
            "crowd"
        );

        return;
    }

    if (currentGame.id === "survivor") {

        renderSurvivor(challenge);
        return;
    }

    if (currentGame.id === "dead_number") {

        renderNumberChoice(
            challenge,
            "dead"
        );

        return;
    }

    if (
        currentGame.id ===
        "impossible_choice"
    ) {

        renderImpossibleChoice(challenge);
        return;
    }

    toast("Unsupported game type.");
}


// ============================================================
// GUESS IT
// ============================================================

function renderGuessIt(challenge) {

    const container =
        document.getElementById("gameContent");

    container.innerHTML = `

        <div class="game-detail-card">

            <div class="challenge-box">

                <h3>
                    🎯 Guess It
                </h3>

                <div class="question">
                    ${
                        challenge.question ||
                        "Identify the hidden answer."
                    }
                </div>

                ${
                    challenge.metadata?.image_url
                        ? `
                        <img
                            src="${challenge.metadata.image_url}"
                            alt="Guess It"
                            style="
                                width:100%;
                                border-radius:16px;
                                margin:15px 0;
                            "
                        >
                        `
                        : ""
                }

                ${
                    challenge.clue
                        ? `
                        <div class="info-box">
                            ${challenge.clue}
                        </div>
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

    const container =
        document.getElementById("gameContent");

    container.innerHTML = `

        <div class="game-detail-card">

            <div class="challenge-box">

                <h3>
                    💀 Weekly Impossible Question
                </h3>

                <div class="question">
                    ${
                        challenge.question ||
                        "Solve the challenge."
                    }
                </div>

                <div class="info-box">
                    You can keep trying until
                    the challenge ends.
                    A wrong answer does not remove
                    your entry.
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

    const container =
        document.getElementById("gameContent");

    const options =
        Array.isArray(challenge.options)
            ? challenge.options
            : [];

    let min =
        challenge.min;

    let max =
        challenge.max;

    if (
        (min === undefined || max === undefined) &&
        options.length
    ) {

        const numbers =
            options
                .map(Number)
                .filter(n => !Number.isNaN(n));

        if (numbers.length) {

            min = Math.min(...numbers);
            max = Math.max(...numbers);
        }
    }

    if (min === undefined) min = 1;
    if (max === undefined) max = 20;

    container.innerHTML = `

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
                    ${
                        challenge.question ||
                        `Choose a number from ${min} to ${max}.`
                    }
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

    const container =
        document.getElementById("gameContent");

    const options =
        Array.isArray(challenge.options)
            ? challenge.options
            : [];

    container.innerHTML = `

        <div class="game-detail-card">

            <div class="challenge-box">

                <h3>
                    🏆 The Survivor
                </h3>

                <div class="question">
                    ${
                        challenge.question ||
                        "Choose one option."
                    }
                </div>

                <div class="info-box">
                    ${
                        challenge.round
                            ? `Round ${challenge.round} —`
                            : ""
                    }
                    ${options.length}
                    options.
                    Only one is safe.
                </div>

                <div class="options">

                    ${
                        options.map(option => `
                            <button
                                class="option-btn"
                                onclick="submitChoice('${escapeQuotes(option)}')"
                            >
                                ${option}
                            </button>
                        `).join("")
                    }

                </div>

            </div>

        </div>
    `;
}


// ============================================================
// IMPOSSIBLE CHOICE
// ============================================================

function renderImpossibleChoice(challenge) {

    const container =
        document.getElementById("gameContent");

    const options =
        Array.isArray(challenge.options)
            ? challenge.options
            : [];

    container.innerHTML = `

        <div class="game-detail-card">

            <div class="challenge-box">

                <h3>
                    🤔 Impossible Choice
                </h3>

                <div class="question">
                    ${
                        challenge.question ||
                        "Which would the crowd choose?"
                    }
                </div>

                <div class="info-box">
                    Don't choose what YOU prefer.
                    Predict what the crowd will do.
                </div>

                <div class="options">

                    ${
                        options.map(option => `
                            <button
                                class="option-btn"
                                onclick="submitChoice('${escapeQuotes(option)}')"
                            >
                                ${option}
                            </button>
                        `).join("")
                    }

                </div>

            </div>

        </div>
    `;
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
// ANSWERS
// ============================================================

async function submitAnswer() {

    const input =
        document.getElementById("answerInput");

    if (
        !input ||
        !input.value.trim()
    ) {

        toast("Enter an answer first.");
        return;
    }

    await submitGameAnswer(
        input.value.trim()
    );
}


async function submitNumber(mode) {

    const input =
        document.getElementById("numberInput");

    if (!input || input.value === "") {

        toast("Enter a number.");
        return;
    }

    const number =
        Number(input.value);

    if (!Number.isFinite(number)) {

        toast("Enter a valid number.");
        return;
    }

    await submitGameAnswer(
        String(number)
    );
}


async function submitChoice(choice) {

    await submitGameAnswer(choice);
}


// ============================================================
// SUBMIT GAME ANSWER
// ============================================================

async function submitGameAnswer(answer) {

    if (!currentGame) {

        toast("No game selected.");
        return;
    }

    if (!currentChallenge) {

        toast("No challenge loaded.");
        return;
    }

    if (!currentChallenge.id) {

        toast("Challenge ID missing.");
        return;
    }

    try {

        const result = await api(
            `/api/games/${currentGame.id}/answer`,
            {
                method: "POST",

                body: JSON.stringify({
                    challenge_id:
                        currentChallenge.id,

                    answer:
                        answer
                })
            }
        );

        if (result.correct) {

            toast(
                result.already_rewarded
                    ? "✅ Correct answer!"
                    : `🎉 Correct! +${
                        result.reward || 0
                    } Points`
            );

            if (result.points !== undefined) {

                state.points =
                    result.points;
            }

            updateBalances();

        } else {

            toast(
                result.message ||
                "❌ That's not correct. Try again."
            );
        }

    } catch (error) {

        console.error(error);

        toast(error.message);
    }
}


// ============================================================
// ADS
// ============================================================

async function watchAd() {

    const button =
        document.getElementById(
            "watchAdButton"
        );

    if (!button) return;

    button.disabled = true;
    button.textContent =
        "📺 WATCHING...";

    setTimeout(async () => {

        try {

            const result =
                await api(
                    "/api/ads/mock-complete",
                    {
                        method: "POST",
                        body: JSON.stringify({})
                    }
                );

            const reward =
                Number(result.reward || 1);

            state.points += reward;
            state.ads_watched += 1;

            updateBalances();
            updateAds();

            toast(
                `+${reward} QuizBee Point earned!`
            );

        } catch (error) {

            console.error(error);

            toast(error.message);
        }

        button.disabled = false;

        button.textContent =
            "📺 WATCH AD";

        updateAds();

    }, 1500);
}


function updateAds() {

    const watched =
        Number(state.ads_watched || 0);

    const progress =
        document.getElementById(
            "adsProgress"
        );

    const progressBar =
        document.getElementById(
            "adsProgressBar"
        );

    const button =
        document.getElementById(
            "watchAdButton"
        );

    if (progress) {

        progress.textContent =
            `${watched}/10`;
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
        document.getElementById(
            "pointsBalance"
        );

    const prize =
        document.getElementById(
            "prizeBalance"
        );

    if (points) {

        points.textContent =
            Number(state.points || 0)
                .toLocaleString();
    }

    if (prize) {

        prize.textContent =
            `₦${Number(
                state.prize_balance || 0
            ).toLocaleString()}`;
    }
}


// ============================================================
// USER STATE
// ============================================================

function updateUserState(firebaseUser) {

    if (!firebaseUser) return;

    state.points =
        Number(
            firebaseUser.quizbee_points ??
            firebaseUser.points ??
            state.points ??
            0
        );

    state.prize_balance =
        Number(
            firebaseUser.prize_balance ??
            0
        );

    state.score =
        Number(
            firebaseUser.total_earned ??
            firebaseUser.score ??
            0
        );

    state.streak =
        Number(
            firebaseUser.streak_days ??
            firebaseUser.streak ??
            0
        );

    state.referrals =
        Number(
            firebaseUser.referrals_count ??
            firebaseUser.referrals ??
            0
        );
}


// ============================================================
// PROFILE
// ============================================================

function updateProfile() {

    const name =
        document.getElementById(
            "profileName"
        );

    const username =
        document.getElementById(
            "profileUsername"
        );

    const score =
        document.getElementById(
            "profileScore"
        );

    const streak =
        document.getElementById(
            "profileStreak"
        );

    const referrals =
        document.getElementById(
            "profileReferrals"
        );

    if (name) {

        name.textContent =
            user.first_name ||
            "Player";
    }

    if (username) {

        username.textContent =
            user.username
                ? `@${user.username}`
                : "Telegram Player";
    }

    if (score) {

        score.textContent =
            Number(state.score || 0)
                .toLocaleString();
    }

    if (streak) {

        streak.textContent =
            state.streak || 0;
    }

    if (referrals) {

        referrals.textContent =
            state.referrals || 0;
    }
}


// ============================================================
// LEADERBOARD
// ============================================================

async function loadLeaderboard(
    type = "weekly",
    button = null
) {

    if (button) {

        document
            .querySelectorAll(".tabs button")
            .forEach(b =>
                b.classList.remove("active")
            );

        button.classList.add("active");
    }

    try {

        const data =
            await api(
                `/api/leaderboard?type=${type}`
            );

        const container =
            document.getElementById(
                "leaderboardList"
            );

        if (!container) return;

        const players =
            data.leaderboard || [];

        if (!players.length) {

            container.innerHTML = `
                <div class="info-box">
                    No players yet.
                </div>
            `;

            return;
        }

        container.innerHTML =
            players.map((player, index) => {

                const name =
                    player.first_name ||
                    player.username ||
                    "Player";

                const score =
                    Number(
                        player.total_earned || 0
                    );

                return `
                    <div class="rank-row">

                        <div class="rank-number">
                            ${
                                player.rank ||
                                index + 1
                            }
                        </div>

                        <div class="rank-name">
                            ${name}
                        </div>

                        <div class="rank-score">
                            ${score}
                        </div>

                    </div>
                `;

            }).join("");

    } catch (error) {

        console.error(error);

        const container =
            document.getElementById(
                "leaderboardList"
            );

        if (container) {

            container.innerHTML = `
                <div class="info-box">
                    Leaderboard unavailable.
                </div>
            `;
        }
    }
}


// ============================================================
// WALLET ACTIONS
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

        const data =
            await api(
                "/api/bootstrap",
                {
                    method: "POST",

                    body: JSON.stringify({
                        telegram_user: user
                    })
                }
            );

        console.log(
            "QuizBee bootstrap:",
            data
        );

        if (data.user) {

            updateUserState(
                data.user
            );
        }

        state.games =
            normalizeGames(
                data.games
            );

    } catch (error) {

        console.error(
            "Bootstrap failed:",
            error
        );

        /*
         * Only use the fallback if the API
         * cannot be reached.
         */

        state.games =
            defaultGames();

        toast(
            "Using demo data. Backend unavailable."
        );
    }

    const welcome =
        document.getElementById(
            "welcomeText"
        );

    if (welcome) {

        welcome.textContent =
            `Welcome, ${
                user.first_name ||
                "Player"
            } 👋`;
    }

    updateBalances();
    updateProfile();
    updateAds();

    renderGames();
    renderHomeGames();
}


// ============================================================
// DEMO FALLBACK
// ============================================================

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


// ============================================================
// START
// ============================================================

bootstrap();
