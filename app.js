const tg = window.Telegram?.WebApp;

if (tg) {
    tg.ready();
    tg.expand();
}

const CONFIG = window.QUIZBEE_CONFIG || {};

const API_URL = (
    CONFIG.API_URL || ""
).replace(/\/$/, "");

let currentUser = null;
let games = [];
let currentGame = null;
let currentChallenge = null;
let currentPage = "home";
let adsWatched = 0;
let selectedChoice = null;


/* ============================================================
   TELEGRAM
   ============================================================ */

function getTelegramUser() {

    if (!tg?.initDataUnsafe?.user) {
        return null;
    }

    const user =
        tg.initDataUnsafe.user;

    return {
        telegram_id: user.id,
        first_name:
            user.first_name || "",
        last_name:
            user.last_name || "",
        username:
            user.username || ""
    };
}


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
            data.message ||
            `HTTP ${response.status}`
        );

    }

    return data;
}


/* ============================================================
   UI HELPERS
   ============================================================ */

function showToast(message) {

    let toast =
        document.getElementById(
            "toast"
        );

    if (!toast) {

        toast =
            document.createElement(
                "div"
            );

        toast.id = "toast";

        toast.className =
            "toast";

        document.body.appendChild(
            toast
        );
    }

    toast.textContent =
        message;

    toast.classList.add(
        "show"
    );

    setTimeout(() => {

        toast.classList.remove(
            "show"
        );

    }, 2500);
}


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
   GAME NORMALIZATION
   ============================================================ */

function normalizeGames(
    serverGames
) {

    return (
        serverGames || []
    ).map(game => ({

        ...game,

        id:
            game.id,

        name:
            game.name ||
            "Game",

        description:
            game.description ||
            "",

        emoji:
            game.icon ||
            game.emoji ||
            "🎮",

        status:
            game.active === true
                ? "active"
                : "locked",

        active:
            game.active === true,

        entry_points:
            Number(
                game.entry_fee ??
                game.entry_points ??
                0
            ),

        reward_points:
            Number(
                game.reward_points ??
                game.reward ??
                0
            )

    }));
}


/* ============================================================
   USER STATE
   ============================================================ */

function updateUserState(
    user
) {

    if (!user) return;

    currentUser =
        user;

    const points =
        Number(
            user.quizbee_points ??
            user.points ??
            0
        );

    const prizeBalance =
        Number(
            user.prize_balance ??
            0
        );

    const streak =
        Number(
            user.streak_days ??
            user.streak ??
            0
        );

    const referrals =
        Number(
            user.referrals_count ??
            user.referrals ??
            0
        );

    const totalEarned =
        Number(
            user.total_earned ??
            user.score ??
            0
        );


    const pointsEl =
        document.getElementById(
            "pointsBalance"
        );

    const prizeEl =
        document.getElementById(
            "prizeBalance"
        );


    if (pointsEl) {

        pointsEl.textContent =
            points.toLocaleString();

    }


    if (prizeEl) {

        prizeEl.textContent =
            `₦${prizeBalance.toLocaleString()}`;

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
            }!`;

    }


    const profileName =
        document.getElementById(
            "profileName"
        );

    const profileUsername =
        document.getElementById(
            "profileUsername"
        );

    const profileScore =
        document.getElementById(
            "profileScore"
        );

    const profileStreak =
        document.getElementById(
            "profileStreak"
        );

    const profileReferrals =
        document.getElementById(
            "profileReferrals"
        );


    if (profileName) {

        profileName.textContent =
            user.first_name ||
            "Player";

    }


    if (profileUsername) {

        profileUsername.textContent =
            user.username
                ? `@${user.username}`
                : "@player";

    }


    if (profileScore) {

        profileScore.textContent =
            totalEarned.toLocaleString();

    }


    if (profileStreak) {

        profileStreak.textContent =
            streak;

    }


    if (profileReferrals) {

        profileReferrals.textContent =
            referrals;

    }
}


/* ============================================================
   BOOTSTRAP
   ============================================================ */

async function bootstrap() {

    try {

        if (!getInitData()) {

            throw new Error(
                "QuizBee must be opened inside Telegram."
            );

        }

        const data =
            await api(
                "/api/bootstrap",
                {
                    method:
                        "POST",

                    body:
                        JSON.stringify({
                            telegram_user:
                                getTelegramUser()
                        })
                }
            );


        if (!data.success) {

            throw new Error(
                data.error ||
                "Bootstrap failed."
            );

        }


        updateUserState(
            data.user
        );


        games =
            normalizeGames(
                data.games
            );


        renderGames();

        showPage("home");


    } catch (error) {

        console.error(
            "Bootstrap error:",
            error
        );


        showToast(
            error.message ||
            "Unable to connect to QuizBee."
        );

    }
}


/* ============================================================
   GAMES
   ============================================================ */

function renderGames() {

    const homeGames =
        document.getElementById(
            "homeGames"
        );

    const gamesList =
        document.getElementById(
            "gamesList"
        );


    const activeGames =
        games.filter(
            game =>
                game.active
        );


    if (homeGames) {

        homeGames.innerHTML =
            activeGames
                .slice(0, 4)
                .map(
                    game =>
                        gameCard(game)
                )
                .join("");

    }


    if (gamesList) {

        gamesList.innerHTML =
            games
                .map(
                    game =>
                        gameListItem(
                            game
                        )
                )
                .join("");

    }
}


function gameCard(game) {

    return `

        <div
            class="game-card ${
                game.active
                    ? ""
                    : "locked"
            }"
            onclick="openGame('${escapeHtml(game.id)}')"
        >

            <div class="game-icon">
                ${escapeHtml(
                    game.emoji
                )}
            </div>

            <div class="game-info">

                <h3>
                    ${escapeHtml(
                        game.name
                    )}
                </h3>

                <p>
                    ${escapeHtml(
                        game.description
                    )}
                </p>

            </div>

            ${
                game.active
                    ? `
                        <span class="game-entry">
                            ${game.entry_points} pts
                        </span>
                    `
                    : `
                        <span class="lock-label">
                            🔒
                        </span>
                    `
            }

        </div>

    `;
}


function gameListItem(game) {

    return `

        <div
            class="game-list-item ${
                game.active
                    ? ""
                    : "locked"
            }"
            onclick="openGame('${escapeHtml(game.id)}')"
        >

            <div class="game-icon">
                ${escapeHtml(
                    game.emoji
                )}
            </div>

            <div class="game-info">

                <h3>
                    ${escapeHtml(
                        game.name
                    )}
                </h3>

                <p>
                    ${escapeHtml(
                        game.description
                    )}
                </p>

            </div>

            ${
                game.active
                    ? `
                        <div class="game-entry">
                            ${game.entry_points} pts
                        </div>
                    `
                    : `
                        <div class="coming-soon">
                            🔒 Coming Soon
                        </div>
                    `
            }

        </div>

    `;
}


/* ============================================================
   OPEN GAME
   ============================================================ */

async function openGame(
    gameId
) {

    const game =
        games.find(
            item =>
                item.id === gameId
        );


    if (!game) {

        showToast(
            "Game not found."
        );

        return;
    }


    currentGame =
        game;


    if (!game.active) {

        showToast(
            "🔒 This game is coming soon."
        );

        return;
    }


    document.getElementById(
        "gameTitle"
    ).textContent =
        game.name;


    showPage("game");


    await enterGame(
        game.id
    );
}


/* ============================================================
   ENTER GAME
   ============================================================ */

async function enterGame(
    gameId
) {

    const container =
        document.getElementById(
            "gameContent"
        );


    container.innerHTML = `
        <div class="loading">
            Entering game...
        </div>
    `;


    try {

        const data =
            await api(
                `/api/games/${encodeURIComponent(gameId)}/enter`,
                {
                    method:
                        "POST"
                }
            );


        if (!data.success) {

            throw new Error(
                data.error ||
                "Unable to enter game."
            );

        }


        if (data.user) {

            updateUserState(
                data.user
            );

        }


        currentChallenge =
            data.challenge;


        selectedChoice =
            null;


        renderChallenge();


    } catch (error) {

        console.error(
            "Game entry error:",
            error
        );


        container.innerHTML = `

            <div class="empty-state">

                <h3>
                    Unable to enter game
                </h3>

                <p>
                    ${escapeHtml(
                        error.message
                    )}
                </p>

                <button
                    class="primary-btn"
                    onclick="enterGame('${escapeHtml(gameId)}')"
                >
                    TRY AGAIN
                </button>

            </div>

        `;
    }
}


/* ============================================================
   LOAD CHALLENGE
   ============================================================ */

async function loadChallenge(
    gameId
) {

    const container =
        document.getElementById(
            "gameContent"
        );


    container.innerHTML = `
        <div class="loading">
            Loading challenge...
        </div>
    `;


    try {

        const data =
            await api(
                `/api/games/${encodeURIComponent(gameId)}/challenge`
            );


        if (
            !data.success ||
            !data.challenge
        ) {

            throw new Error(
                data.error ||
                "No challenge available."
            );

        }


        currentChallenge =
            data.challenge;


        selectedChoice =
            null;


        renderChallenge();


    } catch (error) {

        console.error(
            "Challenge error:",
            error
        );


        container.innerHTML = `

            <div class="empty-state">

                <h3>
                    Challenge unavailable
                </h3>

                <p>
                    ${escapeHtml(
                        error.message
                    )}
                </p>

                <button
                    class="primary-btn"
                    onclick="loadChallenge('${escapeHtml(gameId)}')"
                >
                    TRY AGAIN
                </button>

            </div>

        `;
    }
}


/* ============================================================
   RENDER CHALLENGE
   ============================================================ */

function renderChallenge() {

    const container =
        document.getElementById(
            "gameContent"
        );


    if (
        !currentChallenge ||
        !currentGame
    ) {

        container.innerHTML = `

            <div class="empty-state">
                No challenge available.
            </div>

        `;

        return;
    }


    const question =
        currentChallenge.question ||
        "Question unavailable.";


    const options =
        currentChallenge.options ||
        [];


    if (
        currentGame.id ===
        "guess_it"
    ) {

        container.innerHTML = `

            <div class="challenge-card">

                <div class="challenge-icon">
                    🎯
                </div>

                <div class="challenge-reward">
                    Reward:
                    +${
                        Number(
                            currentChallenge.reward_points ||
                            0
                        )
                    } points
                </div>

                <h2>
                    ${escapeHtml(
                        question
                    )}
                </h2>

                ${
                    currentChallenge
                        .image_url
                        ? `
                            <img
                                src="${escapeHtml(
                                    currentChallenge.image_url
                                )}"
                                class="challenge-image"
                                alt="Challenge"
                            >
                        `
                        : ""
                }

                <input
                    id="answerInput"
                    class="answer-input"
                    type="text"
                    placeholder="Enter your answer"
                    autocomplete="off"
                >

                <button
                    class="primary-btn"
                    onclick="submitGameAnswer()"
                >
                    SUBMIT ANSWER
                </button>

            </div>

        `;

        return;
    }


    if (
        currentGame.id ===
        "impossible_question"
    ) {

        container.innerHTML = `

            <div class="challenge-card">

                <div class="challenge-icon">
                    💀
                </div>

                <div class="challenge-reward">
                    Reward:
                    +${
                        Number(
                            currentChallenge.reward_points ||
                            0
                        )
                    } points
                </div>

                <h2>
                    ${escapeHtml(
                        question
                    )}
                </h2>

                <input
                    id="answerInput"
                    class="answer-input"
                    type="text"
                    placeholder="Your answer..."
                    autocomplete="off"
                >

                <button
                    class="primary-btn"
                    onclick="submitGameAnswer()"
                >
                    SUBMIT ANSWER
                </button>

                <p class="attempt-note">
                    You can try again if your answer is wrong.
                </p>

            </div>

        `;

        return;
    }


    if (

        currentGame.id ===
            "crowd_trap"

        ||

        currentGame.id ===
            "survivor"

        ||

        currentGame.id ===
            "dead_number"

        ||

        currentGame.id ===
            "impossible_choice"

    ) {

        container.innerHTML = `

            <div class="challenge-card">

                <div class="challenge-icon">
                    ${escapeHtml(
                        currentGame.emoji
                    )}
                </div>

                <div class="challenge-reward">
                    Reward:
                    +${
                        Number(
                            currentChallenge.reward_points ||
                            0
                        )
                    } points
                </div>

                <h2>
                    ${escapeHtml(
                        question
                    )}
                </h2>

                <div class="choice-grid">

                    ${
                        options
                            .map(
                                (
                                    option,
                                    index
                                ) => `

                                    <button
                                        class="choice-btn"
                                        onclick="selectChoice(${index})"
                                        data-option-index="${index}"
                                    >
                                        ${escapeHtml(
                                            option
                                        )}
                                    </button>

                                `
                            )
                            .join("")
                    }

                </div>

                <button
                    id="submitChoiceButton"
                    class="primary-btn"
                    onclick="submitSelectedChoice()"
                    disabled
                >
                    SUBMIT CHOICE
                </button>

            </div>

        `;

        return;
    }


    container.innerHTML = `

        <div class="challenge-card">

            <h2>
                ${escapeHtml(
                    question
                )}
            </h2>

            <input
                id="answerInput"
                class="answer-input"
                type="text"
                placeholder="Your answer..."
            >

            <button
                class="primary-btn"
                onclick="submitGameAnswer()"
            >
                SUBMIT ANSWER
            </button>

        </div>

    `;
}


/* ============================================================
   CHOICE
   ============================================================ */

function selectChoice(
    index
) {

    selectedChoice =
        index;


    document
        .querySelectorAll(
            ".choice-btn"
        )
        .forEach(
            button => {

                button.classList.remove(
                    "selected"
                );

            }
        );


    const selected =
        document.querySelector(
            `[data-option-index="${index}"]`
        );


    if (selected) {

        selected.classList.add(
            "selected"
        );

    }


    const submitButton =
        document.getElementById(
            "submitChoiceButton"
        );


    if (submitButton) {

        submitButton.disabled =
            false;

    }
}


/* ============================================================
   ANSWERS
   ============================================================ */

async function submitSelectedChoice() {

    if (
        selectedChoice ===
        null
    ) {

        showToast(
            "Select an option first."
        );

        return;
    }


    const options =
        currentChallenge.options ||
        [];


    const answer =
        options[
            selectedChoice
        ];


    await submitAnswer(
        answer
    );
}


async function submitGameAnswer() {

    const input =
        document.getElementById(
            "answerInput"
        );


    if (!input) {
        return;
    }


    const answer =
        input.value.trim();


    if (!answer) {

        showToast(
            "Enter an answer first."
        );

        return;
    }


    await submitAnswer(
        answer
    );
}


async function submitAnswer(
    answer
) {

    if (
        !currentChallenge ||
        !currentGame
    ) {

        showToast(
            "No active challenge."
        );

        return;
    }


    const buttons =
        document.querySelectorAll(
            "button"
        );


    buttons.forEach(
        button => {

            if (

                button.classList.contains(
                    "primary-btn"
                )

                ||

                button.classList.contains(
                    "choice-btn"
                )

            ) {

                button.disabled =
                    true;

            }

        }
    );


    try {

        const data =
            await api(
                `/api/games/${encodeURIComponent(currentGame.id)}/answer`,
                {
                    method:
                        "POST",

                    body:
                        JSON.stringify({

                            challenge_id:
                                currentChallenge.id,

                            answer:
                                answer

                        })
                }
            );


        if (data.user) {

            updateUserState(
                data.user
            );

        }


        if (data.correct) {

            showToast(

                `🎉 Correct! +${
                    Number(
                        data.reward_points ??
                        data.reward ??
                        0
                    )
                } points`

            );


            setTimeout(
                () => {

                    loadChallenge(
                        currentGame.id
                    );

                },
                1200
            );

        } else {

            showToast(

                data.message ||
                "❌ Wrong answer. Try again."

            );


            document
                .querySelectorAll(
                    "button"
                )
                .forEach(
                    button => {

                        button.disabled =
                            false;

                    }
                );

        }


    } catch (error) {

        console.error(
            "Answer error:",
            error
        );


        showToast(
            error.message ||
            "Unable to submit answer."
        );


        document
            .querySelectorAll(
                "button"
            )
            .forEach(
                button => {

                    button.disabled =
                        false;

                }
            );

    }
}


/* ============================================================
   ADS
   ============================================================ */

async function watchAd() {

    const button =
        document.getElementById(
            "watchAdButton"
        );


    if (button) {

        button.disabled =
            true;

    }


    try {

        const data =
            await api(
                "/api/ads/mock-complete",
                {
                    method:
                        "POST"
                }
            );


        if (data.user) {

            updateUserState(
                data.user
            );

        }


        adsWatched =
            Number(
                data.ads_watched ??
                adsWatched + 1
            );


        updateAdsUI();


        showToast(

            `📺 Ad completed! +${
                Number(
                    data.reward_points ??
                    data.reward ??
                    1
                )
            } point`

        );


    } catch (error) {

        console.error(
            "Ad error:",
            error
        );


        showToast(
            error.message ||
            "Unable to complete ad."
        );

    }


    if (button) {

        button.disabled =
            false;

    }
}


function updateAdsUI() {

    const progress =
        document.getElementById(
            "adsProgress"
        );


    const progressBar =
        document.getElementById(
            "adsProgressBar"
        );


    if (progress) {

        progress.textContent =
            `${adsWatched}/10`;

    }


    if (progressBar) {

        progressBar.style.width =
            `${
                Math.min(
                    adsWatched / 10 * 100,
                    100
                )
            }%`;

    }
}


/* ============================================================
   LEADERBOARD
   ============================================================ */

async function loadLeaderboard(
    type = "weekly",
    clickedButton = null
) {

    const container =
        document.getElementById(
            "leaderboardList"
        );


    if (!container) {
        return;
    }


    container.innerHTML =
        "Loading...";


    document
        .querySelectorAll(
            ".tabs button"
        )
        .forEach(
            button => {

                button.classList.remove(
                    "active"
                );

            }
        );


    if (clickedButton) {

        clickedButton.classList.add(
            "active"
        );

    }


    try {

        const data =
            await api(
                `/api/leaderboard?period=${encodeURIComponent(type)}`
            );


        const leaderboard =
            data.leaderboard ||
            [];


        if (!leaderboard.length) {

            container.innerHTML = `

                <div class="empty-state">
                    No leaderboard data yet.
                </div>

            `;

            return;
        }


        container.innerHTML =
            leaderboard
                .map(
                    (
                        player,
                        index
                    ) => `

                        <div class="leaderboard-row">

                            <div class="leaderboard-rank">
                                #${index + 1}
                            </div>

                            <div class="leaderboard-player">

                                <strong>
                                    ${escapeHtml(
                                        player.first_name ||
                                        player.username ||
                                        "Player"
                                    )}
                                </strong>

                                ${
                                    player.username
                                        ? `
                                            <span>
                                                @${escapeHtml(
                                                    player.username
                                                )}
                                            </span>
                                        `
                                        : ""
                                }

                            </div>

                            <div class="leaderboard-score">
                                ${Number(
                                    player.total_earned ||
                                    0
                                ).toLocaleString()}
                            </div>

                        </div>

                    `
                )
                .join("");


    } catch (error) {

        console.error(
            "Leaderboard error:",
            error
        );


        container.innerHTML = `

            <div class="empty-state">
                Unable to load leaderboard.
            </div>

        `;

    }
}


/* ============================================================
   PROFILE
   ============================================================ */

async function loadProfile() {

    try {

        const data =
            await api(
                "/api/profile"
            );


        if (
            data.success &&
            data.user
        ) {

            updateUserState(
                data.user
            );

        }


    } catch (error) {

        console.error(
            "Profile error:",
            error
        );

    }
}


/* ============================================================
   NAVIGATION
   ============================================================ */

function showPage(
    page
) {

    const pages =
        document.querySelectorAll(
            ".page"
        );


    pages.forEach(
        section => {

            section.classList.remove(
                "active"
            );

        }
    );


    const target =
        document.getElementById(
            `${page}Page`
        );


    if (target) {

        target.classList.add(
            "active"
        );

    }


    currentPage =
        page;


    document
        .querySelectorAll(
            ".nav-item"
        )
        .forEach(
            item => {

                item.classList.remove(
                    "active"
                );

            }
        );


    const navMap = {

        home: 0,

        games: 1,

        ads: 2,

        leaderboard: 3,

        profile: 4

    };


    const navIndex =
        navMap[page];


    if (
        navIndex !== undefined
    ) {

        const navItems =
            document.querySelectorAll(
                ".nav-item"
            );


        if (navItems[navIndex]) {

            navItems[
                navIndex
            ].classList.add(
                "active"
            );

        }

    }


    if (
        page ===
        "leaderboard"
    ) {

        loadLeaderboard(
            "weekly"
        );

    }


    if (
        page ===
        "profile"
    ) {

        loadProfile();

    }


    if (
        page ===
        "ads"
    ) {

        updateAdsUI();

    }


    window.scrollTo({

        top: 0,

        behavior:
            "smooth"

    });
}


function goHome() {

    showPage(
        "home"
    );
}


function buyPoints() {

    showToast(
        "Point purchases will be connected next."
    );
}


function withdrawPrize() {

    showToast(
        "Prize withdrawal will be connected next."
    );
}


/* ============================================================
   START
   ============================================================ */

document.addEventListener(
    "DOMContentLoaded",
    () => {

        console.log(
            "QuizBee frontend loaded."
        );

        console.log(
            "API URL:",
            API_URL
        );


        if (!API_URL) {

            showToast(
                "QuizBee API URL is missing."
            );

            return;
        }


        if (!getInitData()) {

            console.warn(
                "Telegram initData is missing."
            );

            showToast(
                "Open QuizBee from Telegram."
            );

            return;
        }


        bootstrap();

    }
);
