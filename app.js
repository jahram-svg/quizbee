const tg = window.Telegram?.WebApp;

if (tg) {
    tg.ready();
    tg.expand();
}

const CONFIG = window.QUIZBEE_CONFIG || {};
const API_URL = (CONFIG.API_URL || "").replace(/\/$/, "");

let currentUser = null;
let games = [];
let currentGame = null;
let currentChallenge = null;
let currentPage = "home";
let adsWatched = 0;
let selectedChoice = null;


// ============================================================
// TELEGRAM
// ============================================================

function getInitData() {
    return tg?.initData || "";
}

function getTelegramUser() {
    const telegramUser = tg?.initDataUnsafe?.user;

    if (!telegramUser) {
        return null;
    }

    return {
        telegram_id: telegramUser.id,
        first_name: telegramUser.first_name || "",
        last_name: telegramUser.last_name || "",
        username: telegramUser.username || ""
    };
}


// ============================================================
// API
// ============================================================

async function api(path, options = {}) {

    if (!API_URL) {
        throw new Error(
            "API_URL is not configured."
        );
    }

    const headers = {
        "Content-Type": "application/json",
        ...(options.headers || {})
    };

    const initData = getInitData();

    if (initData) {
        headers["X-Telegram-Init-Data"] = initData;
    }

    const response = await fetch(
        `${API_URL}${path}`,
        {
            ...options,
            headers
        }
    );

    let data;

    try {
        data = await response.json();
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


// ============================================================
// UI HELPERS
// ============================================================

function showToast(message) {

    const toast =
        document.getElementById("toast");

    if (!toast) {
        return;
    }

    toast.textContent = message;

    toast.classList.add("show");

    clearTimeout(showToast.timer);

    showToast.timer = setTimeout(() => {

        toast.classList.remove("show");

    }, 2500);
}


function escapeHtml(value) {

    return String(value ?? "")
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#039;");
}


function escapeAttribute(value) {
    return escapeHtml(value);
}


function escapeJs(value) {

    return String(value ?? "")
        .replace(/\\/g, "\\\\")
        .replace(/'/g, "\\'");
}


// ============================================================
// GAME NORMALIZATION
// ============================================================

function normalizeGames(serverGames) {

    return (serverGames || [])
        .map(game => ({

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

            active:
                game.active === true,

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

            reward_points:
                Number(
                    game.reward_points ??
                    game.reward ??
                    0
                ),

            sort_order:
                Number(
                    game.sort_order || 0
                )

        }))
        .sort(
            (a, b) =>
                a.sort_order -
                b.sort_order
        );
}


// ============================================================
// USER STATE
// ============================================================

function updateUserState(user) {

    if (!user) {
        return;
    }

    currentUser = user;

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

    const welcomeEl =
        document.getElementById(
            "welcomeText"
        );


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

    const profileAvatar =
        document.getElementById(
            "profileAvatar"
        );


    if (pointsEl) {

        pointsEl.textContent =
            points.toLocaleString();

    }


    if (prizeEl) {

        prizeEl.textContent =
    `$${prizeBalance.toFixed(2)}`;

    }


    if (welcomeEl) {

        welcomeEl.textContent =
            `Welcome, ${
                user.first_name ||
                "Player"
            }!`;

    }


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


    if (profileAvatar) {

        const first =
            (
                user.first_name ||
                "Q"
            )
            .trim()
            .charAt(0);

        profileAvatar.textContent =
            first
                ? first.toUpperCase()
                : "🐝";

    }
}


// ============================================================
// BOOTSTRAP
// ============================================================

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
                    method: "POST",
                    body: JSON.stringify({})
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


// ============================================================
// GAMES
// ============================================================

function renderGames() {

    const homeGames =
        document.getElementById(
            "homeGames"
        );

    const gamesList =
        document.getElementById(
            "gamesList"
        );


    /*
     * HOME
     *
     * Always show the first 4 games,
     * including locked games.
     */

    if (homeGames) {

        homeGames.innerHTML =
            games
                .slice(0, 4)
                .map(gameCard)
                .join("");


        if (!homeGames.innerHTML) {

            homeGames.innerHTML = `
                <div class="info-box">
                    No games available yet.
                </div>
            `;

        }

    }


    /*
     * GAMES PAGE
     *
     * Use the actual CSS class
     * that exists in style.css.
     */

    if (gamesList) {

        gamesList.innerHTML =
            games
                .map(gameListCard)
                .join("");


        if (!gamesList.innerHTML) {

            gamesList.innerHTML = `
                <div class="info-box">
                    No games available yet.
                </div>
            `;

        }

    }
}


// ============================================================
// HOME GAME CARD
// ============================================================

function gameCard(game) {

    const locked =
        !game.active;


    return `
        <div
            class="game-card ${
                locked
                    ? "locked"
                    : ""
            }"
            onclick="${
                locked
                    ? "lockedGame()"
                    : `openGame('${escapeJs(game.id)}')`
            }"
        >

            <span
                class="status ${
                    locked
                        ? "locked"
                        : "unlocked"
                }"
            >
                ${
                    locked
                        ? "🔒 LOCKED"
                        : "● LIVE"
                }
            </span>


            <div class="game-icon">

                ${escapeHtml(
                    game.emoji
                )}

            </div>


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
    `;
}


// ============================================================
// GAMES LIST CARD
// ============================================================

function gameListCard(game) {

    const locked =
        !game.active;


    return `
        <div
            class="game-list-card ${
                locked
                    ? "locked-card"
                    : ""
            }"
            onclick="${
                locked
                    ? "lockedGame()"
                    : `openGame('${escapeJs(game.id)}')`
            }"
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


                <div class="entry">

                    ${
                        locked
                            ? "🔒 Coming Soon"
                            : `Entry: ${game.entry_points} Points`
                    }

                </div>

            </div>


            <div>

                ${
                    locked
                        ? "🔒"
                        : "›"
                }

            </div>

        </div>
    `;
}


// ============================================================
// LOCKED GAME
// ============================================================

function lockedGame() {

    showToast(
        "🔒 Coming Soon — this game is currently locked."
    );

}


// ============================================================
// OPEN GAME
// ============================================================

async function openGame(gameId) {

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


    if (!game.active) {

        lockedGame();

        return;
    }


    currentGame =
        game;

    currentChallenge =
        null;

    selectedChoice =
        null;


    const title =
        document.getElementById(
            "gameTitle"
        );


    if (title) {

        title.textContent =
            `${game.emoji} ${game.name}`;

    }


    const content =
        document.getElementById(
            "gameContent"
        );


    if (content) {

        content.innerHTML = `

            <div class="game-detail-card">

                <div class="game-detail-icon">

                    ${escapeHtml(
                        game.emoji
                    )}

                </div>


                <h2>

                    ${escapeHtml(
                        game.name
                    )}

                </h2>


                <p class="game-description">

                    ${escapeHtml(
                        game.description
                    )}

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

    }


    showPage("game");

}


// ============================================================
// ENTER GAME
// ============================================================

async function enterGame() {

    if (!currentGame) {

        showToast(
            "No game selected."
        );

        return;
    }


    const container =
        document.getElementById(
            "gameContent"
        );


    if (container) {

        container.innerHTML = `

            <div class="game-detail-card">

                <div class="info-box">

                    Entering game...

                </div>

            </div>

        `;

    }


    try {

        const data =
            await api(
                `/api/games/${encodeURIComponent(
                    currentGame.id
                )}/enter`,
                {
                    method: "POST",
                    body: JSON.stringify({})
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
            data.challenge ||
            null;

        selectedChoice =
            null;


        if (!currentChallenge) {

            await loadChallenge(
                currentGame.id
            );

        } else {

            renderChallenge();

        }


        if (data.already_entered) {

            showToast(
                "You already entered this challenge."
            );

        } else {

            showToast(
                "Entry successful! 🎉"
            );

        }


    } catch (error) {

        console.error(
            "Game entry error:",
            error
        );


        if (container) {

            container.innerHTML = `

                <div class="game-detail-card">

                    <div class="info-box">

                        <strong>
                            Unable to enter game
                        </strong>

                        <br><br>

                        ${escapeHtml(
                            error.message
                        )}

                    </div>


                    <button
                        class="primary-btn"
                        onclick="enterGame()"
                    >

                        TRY AGAIN

                    </button>

                </div>

            `;

        }

    }
}


// ============================================================
// LOAD CHALLENGE
// ============================================================

async function loadChallenge(
    gameId
) {

    const container =
        document.getElementById(
            "gameContent"
        );


    if (container) {

        container.innerHTML = `

            <div class="game-detail-card">

                <div class="info-box">

                    Loading challenge...

                </div>

            </div>

        `;

    }


    try {

        const data =
            await api(
                `/api/games/${encodeURIComponent(
                    gameId
                )}/challenge`
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


        if (container) {

            container.innerHTML = `

                <div class="game-detail-card">

                    <div class="info-box">

                        <strong>
                            Challenge unavailable
                        </strong>

                        <br><br>

                        ${escapeHtml(
                            error.message
                        )}

                    </div>


                    <button
                        class="primary-btn"
                        onclick="loadChallenge('${escapeJs(
                            gameId
                        )}')"
                    >

                        TRY AGAIN

                    </button>

                </div>

            `;

        }

    }
}


// ============================================================
// CHALLENGE IMAGE
// ============================================================

function getChallengeImage(
    challenge
) {

    return (
        challenge.image_url ||
        challenge.metadata?.image_url ||
        ""
    );

}


// ============================================================
// RENDER CHALLENGE
// ============================================================

function renderChallenge() {

    const container =
        document.getElementById(
            "gameContent"
        );


    if (!container) {
        return;
    }


    if (
        !currentChallenge ||
        !currentGame
    ) {

        container.innerHTML = `

            <div class="game-detail-card">

                <div class="info-box">

                    No challenge available.

                </div>

            </div>

        `;

        return;
    }


    const challenge =
        currentChallenge;


    const question =
        challenge.question ||
        challenge.title ||
        "Question unavailable.";


    const options =
        Array.isArray(
            challenge.options
        )
            ? challenge.options
            : [];


    const reward =
        Number(
            challenge.reward_points ??
            challenge.reward ??
            0
        );


    if (
        currentGame.id ===
        "guess_it"
    ) {

        renderGuessIt(
            question,
            reward,
            challenge
        );

        return;
    }


    if (
        currentGame.id ===
        "impossible_question"
    ) {

        renderImpossibleQuestion(
            question,
            reward
        );

        return;
    }


    if (
        currentGame.id ===
            "crowd_trap" ||
        currentGame.id ===
            "dead_number"
    ) {

        renderNumberChoice(
            question,
            reward,
            challenge
        );

        return;
    }


    if (
        currentGame.id ===
            "survivor" ||
        currentGame.id ===
            "impossible_choice"
    ) {

        renderChoiceGame(
            question,
            reward,
            options
        );

        return;
    }


    renderTextChallenge(
        question,
        reward
    );

}


// ============================================================
// GUESS IT
// ============================================================

function renderGuessIt(
    question,
    reward,
    challenge
) {

    const container =
        document.getElementById(
            "gameContent"
        );


    const imageUrl =
        getChallengeImage(
            challenge
        );


    container.innerHTML = `

        <div class="game-detail-card">

            <div class="challenge-box">

                <h3>
                    🎯 Guess It
                </h3>


                <div class="info-box">

                    Reward:

                    <strong>
                        +${reward} Points
                    </strong>

                </div>


                <div class="question">

                    ${escapeHtml(
                        question
                    )}

                </div>


                ${
                    imageUrl
                        ? `

                            <img
                                src="${escapeAttribute(
                                    imageUrl
                                )}"
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

                                ${escapeHtml(
                                    challenge.clue
                                )}

                            </div>

                        `
                        : ""
                }


                <input
                    id="answerInput"
                    class="number-input"
                    type="text"
                    placeholder="Type your answer..."
                    autocomplete="off"
                >


                <button
                    class="primary-btn"
                    onclick="submitGameAnswer()"
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

function renderImpossibleQuestion(
    question,
    reward
) {

    const container =
        document.getElementById(
            "gameContent"
        );


    container.innerHTML = `

        <div class="game-detail-card">

            <div class="challenge-box">

                <h3>
                    💀 Weekly Impossible Question
                </h3>


                <div class="info-box">

                    Reward:

                    <strong>
                        +${reward} Points
                    </strong>

                </div>


                <div class="question">

                    ${escapeHtml(
                        question
                    )}

                </div>


                <div class="info-box">

                    You can keep trying until
                    the challenge ends.

                    A wrong answer does not
                    remove your entry.

                </div>


                <input
                    id="answerInput"
                    class="number-input"
                    type="text"
                    placeholder="Your answer..."
                    autocomplete="off"
                >


                <button
                    class="primary-btn"
                    onclick="submitGameAnswer()"
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

function renderNumberChoice(
    question,
    reward,
    challenge
) {

    const container =
        document.getElementById(
            "gameContent"
        );


    const options =
        Array.isArray(
            challenge.options
        )
            ? challenge.options
            : [];


    let min =
        challenge.min;


    let max =
        challenge.max;


    if (
        (
            min === undefined ||
            max === undefined
        ) &&
        options.length
    ) {

        const numbers =
            options
                .map(Number)
                .filter(
                    number =>
                        !Number.isNaN(
                            number
                        )
                );


        if (numbers.length) {

            min =
                Math.min(
                    ...numbers
                );

            max =
                Math.max(
                    ...numbers
                );

        }

    }


    if (min === undefined) {
        min = 1;
    }


    if (max === undefined) {
        max = 20;
    }


    const title =
        currentGame.id ===
        "crowd_trap"

            ? "🧠 The Crowd Trap"

            : "☠️ Dead Number";


    container.innerHTML = `

        <div class="game-detail-card">

            <div class="challenge-box">

                <h3>

                    ${title}

                </h3>


                <div class="info-box">

                    Reward:

                    <strong>
                        +${reward} Points
                    </strong>

                </div>


                <div class="question">

                    ${escapeHtml(
                        question
                    )}

                </div>


                <div class="info-box">

                    Choose between

                    <strong>
                        ${min}
                    </strong>

                    and

                    <strong>
                        ${max}
                    </strong>.

                </div>


                <input
                    id="numberInput"
                    class="number-input"
                    type="number"
                    min="${Number(min)}"
                    max="${Number(max)}"
                    placeholder="Enter your number"
                >


                <button
                    class="primary-btn"
                    onclick="submitNumber()"
                >

                    LOCK MY CHOICE

                </button>

            </div>

        </div>

    `;
}


// ============================================================
// SURVIVOR / IMPOSSIBLE CHOICE
// ============================================================

function renderChoiceGame(
    question,
    reward,
    options
) {

    const container =
        document.getElementById(
            "gameContent"
        );


    const title =
        currentGame.id ===
        "survivor"

            ? "🏆 The Survivor"

            : "🤔 Impossible Choice";


    const description =
        currentGame.id ===
        "survivor"

            ? "Choose carefully. Only one option is safe."

            : "Predict what the crowd will do. Your personal preference does not matter.";


    container.innerHTML = `

        <div class="game-detail-card">

            <div class="challenge-box">

                <h3>
                    ${title}
                </h3>


                <div class="info-box">

                    Reward:

                    <strong>
                        +${reward} Points
                    </strong>

                </div>


                <div class="question">

                    ${escapeHtml(
                        question
                    )}

                </div>


                <div class="info-box">

                    ${description}

                </div>


                <div class="options">

                    ${
                        options.length

                            ? options
                                .map(
                                    (
                                        option,
                                        index
                                    ) => `

                                        <button
                                            class="option-btn"
                                            data-option-index="${index}"
                                            onclick="selectChoice(${index})"
                                        >

                                            ${escapeHtml(
                                                option
                                            )}

                                        </button>

                                    `
                                )
                                .join("")

                            : `

                                <div class="info-box">

                                    No options available.

                                </div>

                            `
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

        </div>

    `;
}


// ============================================================
// GENERIC TEXT CHALLENGE
// ============================================================

function renderTextChallenge(
    question,
    reward
) {

    const container =
        document.getElementById(
            "gameContent"
        );


    container.innerHTML = `

        <div class="game-detail-card">

            <div class="challenge-box">

                <div class="info-box">

                    Reward:

                    <strong>
                        +${reward} Points
                    </strong>

                </div>


                <div class="question">

                    ${escapeHtml(
                        question
                    )}

                </div>


                <input
                    id="answerInput"
                    class="number-input"
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

            </div>

        </div>

    `;
}


// ============================================================
// CHOICE SELECTION
// ============================================================

function selectChoice(
    index
) {

    selectedChoice =
        index;


    document
        .querySelectorAll(
            ".option-btn"
        )
        .forEach(
            button => {

                button.style.borderColor =
                    "";

                button.style.background =
                    "";

            }
        );


    const selected =
        document.querySelector(
            `[data-option-index="${index}"]`
        );


    if (selected) {

        selected.style.borderColor =
            "var(--yellow)";

        selected.style.background =
            "#303642";

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


// ============================================================
// SUBMIT CHOICE
// ============================================================

async function submitSelectedChoice() {

    if (
        selectedChoice ===
        null ||
        !currentChallenge
    ) {

        showToast(
            "Select an option first."
        );

        return;
    }


    const options =
        Array.isArray(
            currentChallenge.options
        )
            ? currentChallenge.options
            : [];


    const answer =
        options[
            selectedChoice
        ];


    if (answer === undefined) {

        showToast(
            "Invalid choice."
        );

        return;
    }


    await submitAnswer(
        answer
    );

}


// ============================================================
// SUBMIT NUMBER
// ============================================================

async function submitNumber() {

    const input =
        document.getElementById(
            "numberInput"
        );


    if (
        !input ||
        input.value === ""
    ) {

        showToast(
            "Enter a number."
        );

        return;
    }


    const number =
        Number(
            input.value
        );


    if (!Number.isFinite(number)) {

        showToast(
            "Enter a valid number."
        );

        return;
    }


    await submitAnswer(
        String(number)
    );

}


// ============================================================
// SUBMIT TEXT ANSWER
// ============================================================

async function submitGameAnswer() {

    const input =
        document.getElementById(
            "answerInput"
        );


    if (!input) {

        showToast(
            "Answer field not found."
        );

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


// ============================================================
// SUBMIT ANSWER
// ============================================================

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
            "#gameContent button"
        );


    buttons.forEach(
        button => {

            button.disabled =
                true;

        }
    );


    try {

        const data =
            await api(
                `/api/games/${encodeURIComponent(
                    currentGame.id
                )}/answer`,
                {
                    method: "POST",

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

            const reward =
                Number(
                    data.reward_points ??
                    data.reward ??
                    0
                );


            /*
             * The current backend does not return
             * the updated user on a successful reward,
             * so update the displayed points locally.
             */

            if (
                reward > 0 &&
                currentUser
            ) {

                const currentPoints =
                    Number(
                        currentUser.quizbee_points ??
                        currentUser.points ??
                        0
                    );


                currentUser.quizbee_points =
                    currentPoints +
                    reward;


                currentUser.total_earned =
                    Number(
                        currentUser.total_earned ||
                        0
                    ) +
                    reward;


                updateUserState(
                    currentUser
                );

            }


            showToast(

                data.already_rewarded

                    ? "✅ Correct answer!"

                    : `🎉 Correct! +${reward} Points`

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


            buttons.forEach(
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


        buttons.forEach(
            button => {

                button.disabled =
                    false;

            }
        );

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


    if (button) {

        button.disabled =
            true;

        button.textContent =
            "📺 COMPLETING...";

    }


    try {

        const data =
            await api(
                "/api/ads/mock-complete",
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


        const reward =
            Number(
                data.reward_points ??
                data.reward ??
                1
            );


        adsWatched =
            Number(
                data.ads_watched ??
                adsWatched + 1
            );


        updateAdsUI();


        showToast(
            `📺 Ad completed! +${reward} point`
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


    } finally {

        if (button) {

            button.disabled =
                false;

            button.textContent =
                "📺 WATCH AD";

        }

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
            `${Math.min(
                adsWatched / 10 * 100,
                100
            )}%`;

    }

}


// ============================================================
// LEADERBOARD
// ============================================================

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


    container.innerHTML = `

        <div class="info-box">

            Loading leaderboard...

        </div>

    `;


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
                `/api/leaderboard?period=${encodeURIComponent(
                    type
                )}`
            );


        const leaderboard =
            data.leaderboard ||
            [];


        if (!leaderboard.length) {

            container.innerHTML = `

                <div class="info-box">

                    No leaderboard data yet.

                </div>

            `;

            return;
        }


        /*
         * IMPORTANT:
         *
         * These are the CSS classes that
         * actually exist in style.css:
         *
         * rank-row
         * rank-number
         * rank-name
         * rank-score
         */

        container.innerHTML =
            leaderboard
                .map(
                    (
                        player,
                        index
                    ) => {

                        const rank =
                            Number(
                                player.rank
                            ) ||
                            index + 1;


                        const name =
                            player.first_name ||
                            player.username ||
                            "Player";


                        const username =
                            player.username
                                ? `@${player.username}`
                                : "";


                        const score =
                            Number(
                                player.total_earned ||
                                0
                            )
                            .toLocaleString();


                        return `

                            <div class="rank-row">

                                <div class="rank-number">

                                    #${rank}

                                </div>


                                <div class="rank-name">

                                    <strong>

                                        ${escapeHtml(
                                            name
                                        )}

                                    </strong>


                                    ${
                                        username
                                            ? `

                                                <div
                                                    style="
                                                        color:var(--muted);
                                                        font-size:10px;
                                                        margin-top:3px;
                                                    "
                                                >

                                                    ${escapeHtml(
                                                        username
                                                    )}

                                                </div>

                                            `
                                            : ""
                                    }

                                </div>


                                <div class="rank-score">

                                    ${score}

                                </div>

                            </div>

                        `;

                    }
                )
                .join("");

    } catch (error) {

        console.error(
            "Leaderboard error:",
            error
        );


        container.innerHTML = `

            <div class="info-box">

                Unable to load leaderboard.

            </div>

        `;

    }

}


// ============================================================
// PROFILE
// ============================================================

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


        /*
         * Bootstrap already loaded the
         * user information.
         *
         * Do not replace it with
         * "Player" if this refresh
         * temporarily fails.
         */

        if (!currentUser) {

            showToast(

                error.message ||

                "Unable to load profile."

            );

        }

    }

}


// ============================================================
// NAVIGATION
// ============================================================

function showPage(
    page
) {

    document
        .querySelectorAll(
            ".page"
        )
        .forEach(
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
        navIndex !==
        undefined
    ) {

        const navItems =
            document.querySelectorAll(
                ".nav-item"
            );


        if (
            navItems[navIndex]
        ) {

            navItems[
                navIndex
            ].classList.add(
                "active"
            );

        }

    }


    if (
        page ===
        "games"
    ) {

        renderGames();

    }


    if (
        page ===
        "leaderboard"
    ) {

        loadLeaderboard(
            "weekly"
        );

    }


    if (page === "earning") {
    loadDailyEarning();
    }


    if (
        page ===
        "profile"
    ) {

        /*
         * Display the already-loaded
         * user immediately.
         */

        if (currentUser) {

            updateUserState(
                currentUser
            );

        }


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

        behavior: "smooth"

    });

}


// ============================================================
// OTHER ACTIONS
// ============================================================

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


// ============================================================
// START
// ============================================================

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
