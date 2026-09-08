// ============================================================
// QUIZBEE FRONTEND GAME ENGINE
// DEVELOPMENT / DEMO VERSION
// ============================================================

const tg = window.Telegram?.WebApp;

if (tg) {
    tg.ready();
    tg.expand();
}


// ============================================================
// PLAYER STATE
// ============================================================

const state = {

    points: 240,

    prizeBalance: 0,

    score: 0,

    streak: 0,

    referrals: 0,

    adsWatched: 0,

    currentGame: null,

    currentQuestion: null,

    currentClueIndex: 0,

    attempts: 0

};


// ============================================================
// GAME CONFIGURATION
// ============================================================

const games = [

    {
        id: "guess",

        icon: "🎯",

        name: "Guess It",

        description:
            "Use clues to identify the hidden answer.",

        entryFee: 10,

        unlocked: true
    },

    {
        id: "impossible",

        icon: "💀",

        name: "Impossible Question",

        description:
            "A brutal brain teaser. Multiple attempts allowed.",

        entryFee: 10,

        unlocked: true
    },

    {
        id: "crowd",

        icon: "🧠",

        name: "The Crowd Trap",

        description:
            "Choose a number nobody else chooses.",

        entryFee: 10,

        unlocked: false
    },

    {
        id: "survivor",

        icon: "🏆",

        name: "The Survivor",

        description:
            "Survive every round until the final.",

        entryFee: 10,

        unlocked: false
    },

    {
        id: "deadnumber",

        icon: "☠️",

        name: "Dead Number",

        description:
            "Choose a number. Avoid the dead numbers.",

        entryFee: 10,

        unlocked: false
    },

    {
        id: "choice",

        icon: "🤔",

        name: "Impossible Choice",

        description:
            "Predict what the crowd will choose.",

        entryFee: 10,

        unlocked: false
    }

];


// ============================================================
// QUESTION DATA
// ============================================================

const questions = {

    guess: [

        {
            clues: [

                "I am a footballer.",

                "I have won the Ballon d'Or.",

                "I am famous for my left foot.",

                "I have played in Spain."

            ],

            answer: "lionel messi",

            accepted: [
                "lionel messi",
                "messi"
            ]
        },

        {
            clues: [

                "I am a country.",

                "I am in West Africa.",

                "My capital is Abuja.",

                "My largest city is Lagos."

            ],

            answer: "nigeria",

            accepted: [
                "nigeria"
            ]
        },

        {
            clues: [

                "I am an animal.",

                "I have black and white stripes.",

                "I am closely related to horses."

            ],

            answer: "zebra",

            accepted: [
                "zebra"
            ]
        },

        {
            clues: [

                "I am a planet.",

                "I am known as the Red Planet.",

                "I am the fourth planet from the Sun."

            ],

            answer: "mars",

            accepted: [
                "mars"
            ]
        }

    ],


    impossible: [

        {
            clues: [

                "You have three switches outside a room.",

                "Inside the room is one light bulb.",

                "Only one switch controls the bulb.",

                "You may enter the room only once.",

                "How can you identify the correct switch?"

            ],

            answer: "use heat",

            accepted: [

                "use heat",
                "use the heat",
                "turn one on then off",
                "turn one switch on then off",
                "heat the bulb",
                "use bulb heat"

            ]
        },

        {
            clues: [

                "A farmer has 17 sheep.",

                "All but 9 die.",

                "How many sheep are left?"

            ],

            answer: "9",

            accepted: [
                "9",
                "nine"
            ]
        }

    ]

};


// ============================================================
// INITIALIZATION
// ============================================================

document.addEventListener(
    "DOMContentLoaded",
    initialize
);


function initialize() {

    renderGames();

    updateStats();

    updateAdUI();

    updateTelegramUser();

}


// ============================================================
// TELEGRAM USER
// ============================================================

function updateTelegramUser() {

    const user =
        tg?.initDataUnsafe?.user;

    if (!user) return;

    const name =
        user.first_name ||
        "QuizBee Player";

    const username =
        user.username
            ? "@" + user.username
            : "Telegram User";

    const nameElement =
        document.getElementById("profile-name");

    const usernameElement =
        document.getElementById("profile-username");

    if (nameElement) {
        nameElement.textContent = name;
    }

    if (usernameElement) {
        usernameElement.textContent = username;
    }
}


// ============================================================
// NORMALIZE ANSWER
// ============================================================

function normalizeAnswer(value) {

    return value
        .toLowerCase()
        .trim()
        .replace(/\s+/g, " ")
        .replace(/[.,!?]/g, "");

}


// ============================================================
// CHECK ANSWER
// ============================================================

function checkAnswer(value, question) {

    const normalized =
        normalizeAnswer(value);

    return question.accepted.some(
        answer =>
            normalizeAnswer(answer) === normalized
    );

}


// ============================================================
// RENDER GAMES
// ============================================================

function renderGames() {

    const container =
        document.getElementById("game-list");

    if (!container) return;

    container.innerHTML = "";

    games.forEach(game => {

        const card =
            document.createElement("div");

        card.className =
            "game-card" +
            (!game.unlocked
                ? " locked-overlay"
                : "");

        const status =
            game.unlocked
                ? `
                    <span class="status-badge status-open">
                        ✅ OPEN
                    </span>
                  `
                : `
                    <span class="status-badge status-locked">
                        🔒 Coming Soon
                    </span>
                  `;

        const button =
            game.unlocked
                ? `
                    <button
                        class="game-button"
                        onclick="startGame('${game.id}')"
                    >
                        Play
                    </button>
                  `
                : `
                    <button
                        class="game-button locked"
                        onclick="lockedGame()"
                    >
                        🔒
                    </button>
                  `;

        card.innerHTML = `

            <div class="game-icon">
                ${game.icon}
            </div>

            <div class="game-info">

                <h3>
                    ${game.name}
                </h3>

                <p>
                    ${game.description}
                </p>

                <div class="game-meta">

                    ${status}

                    ${
                        game.unlocked
                            ? `
                                <span class="entry-badge">
                                    Entry ${game.entryFee} Points
                                </span>
                              `
                            : ""
                    }

                </div>

            </div>

            ${button}

        `;

        container.appendChild(card);

    });

}


// ============================================================
// LOCKED GAME
// ============================================================

function lockedGame() {

    alert(
        "🔒 Coming Soon!\n\n" +
        "This game will be unlocked as QuizBee grows."
    );

}


// ============================================================
// START GAME
// ============================================================

function startGame(gameId) {

    const game =
        games.find(
            item => item.id === gameId
        );

    if (!game || !game.unlocked) {

        lockedGame();

        return;
    }


    if (state.points < game.entryFee) {

        alert(
            "You don't have enough QuizBee Points."
        );

        return;
    }


    const availableQuestions =
        questions[gameId];

    if (
        !availableQuestions ||
        availableQuestions.length === 0
    ) {

        alert(
            "No question is available yet."
        );

        return;
    }


    // Deduct entry

    state.points -= game.entryFee;


    // Select question

    state.currentGame =
        gameId;

    state.currentQuestion =
        availableQuestions[
            Math.floor(
                Math.random() *
                availableQuestions.length
            )
        ];


    state.currentClueIndex = 0;

    state.attempts = 0;


    renderGame();

    updateStats();

}


// ============================================================
// RENDER GAME
// ============================================================

function renderGame() {

    showScreen("game");

    const title =
        document.getElementById("game-title");

    const content =
        document.getElementById("game-content");


    const game =
        games.find(
            item =>
                item.id ===
                state.currentGame
        );


    if (!game) return;


    title.textContent =
        `${game.icon} ${game.name}`;


    if (
        state.currentGame ===
        "guess"
    ) {

        renderGuess(content);

        return;
    }


    if (
        state.currentGame ===
        "impossible"
    ) {

        renderImpossible(content);

        return;
    }

}


// ============================================================
// GUESS IT
// ============================================================

function renderGuess(container) {

    const question =
        state.currentQuestion;


    const clues =
        question.clues.slice(
            0,
            state.currentClueIndex + 1
        );


    const reward =
        25;


    container.innerHTML = `

        <div class="question-box">

            <div class="reward-banner">

                🎯 Correct answer:
                +${reward} Score

            </div>


            <h3>
                Identify the answer
            </h3>


            <div class="clues">

                ${clues.map(
                    (clue, index) => `

                    <div class="clue">

                        <span class="clue-number">
                            Clue ${index + 1}
                        </span>

                        <p>
                            ${clue}
                        </p>

                    </div>

                `).join("")}

            </div>


            <input
                id="answer-input"
                class="answer-input"
                type="text"
                placeholder="Enter your answer..."
                autocomplete="off"
            >


            <button
                class="primary-button"
                onclick="submitAnswer()"
            >
                Submit Answer
            </button>


            <div id="answer-feedback"></div>

        </div>

    `;


    focusAnswer();

}


// ============================================================
// IMPOSSIBLE QUESTION
// ============================================================

function renderImpossible(container) {

    const question =
        state.currentQuestion;


    container.innerHTML = `

        <div class="question-box">

            <div class="reward-banner">

                💀 Weekly Challenge

            </div>


            <h3>
                Think carefully.
            </h3>


            <div class="clues">

                ${question.clues.map(
                    (clue, index) => `

                    <div class="clue">

                        <span class="clue-number">
                            ${index + 1}
                        </span>

                        <p>
                            ${clue}
                        </p>

                    </div>

                `).join("")}

            </div>


            <p
                style="
                    font-size:11px;
                    color:#777;
                    margin-top:10px;
                "
            >
                You can try multiple times.
            </p>


            <input
                id="answer-input"
                class="answer-input"
                type="text"
                placeholder="Your answer..."
                autocomplete="off"
            >


            <button
                class="primary-button"
                onclick="submitAnswer()"
            >
                Submit Answer
            </button>


            <div id="answer-feedback"></div>

        </div>

    `;


    focusAnswer();

}


// ============================================================
// FOCUS INPUT
// ============================================================

function focusAnswer() {

    setTimeout(() => {

        const input =
            document.getElementById(
                "answer-input"
            );

        if (input) {
            input.focus();
        }

    }, 100);

}


// ============================================================
// SUBMIT ANSWER
// ============================================================

function submitAnswer() {

    const input =
        document.getElementById(
            "answer-input"
        );

    const feedback =
        document.getElementById(
            "answer-feedback"
        );


    if (!input || !feedback)
        return;


    const value =
        input.value.trim();


    if (!value) {

        feedback.innerHTML = `

            <div class="feedback wrong">

                Please enter an answer.

            </div>

        `;

        return;
    }


    state.attempts++;


    const correct =
        checkAnswer(
            value,
            state.currentQuestion
        );


    if (correct) {

        let earned =
            25;


        if (
            state.currentGame ===
            "impossible"
        ) {

            earned = 100;

        }


        state.score += earned;


        input.disabled = true;


        feedback.innerHTML = `

            <div class="feedback correct">

                🎉 <strong>Correct!</strong>

                <br>

                +${earned} Score

            </div>


            <button
                class="secondary-button"
                onclick="finishGame()"
            >
                Continue
            </button>

        `;


        updateStats();

        return;
    }


    // IMPOSSIBLE QUESTION

    if (
        state.currentGame ===
        "impossible"
    ) {

        feedback.innerHTML = `

            <div class="feedback wrong">

                ❌ Answer is wrong.

                <br>

                Try again.

            </div>

        `;


        input.value = "";

        input.focus();

        return;
    }


    // GUESS IT

    if (
        state.currentClueIndex <
        state.currentQuestion.clues.length - 1
    ) {

        state.currentClueIndex++;

        feedback.innerHTML = `

            <div class="feedback wrong">

                ❌ Not correct.

                <br>

                Here's another clue...

            </div>

        `;


        setTimeout(
            renderGame,
            650
        );


        return;
    }


    // ALL CLUES USED

    feedback.innerHTML = `

        <div class="feedback wrong">

            ❌ You didn't get it.

            <br><br>

            Correct answer:

            <strong>
                ${state.currentQuestion.answer}
            </strong>

        </div>


        <button
            class="secondary-button"
            onclick="finishGame()"
        >
            Finish
        </button>

    `;

}


// ============================================================
// FINISH GAME
// ============================================================

function finishGame() {

    state.currentGame = null;

    state.currentQuestion = null;

    goHome();

}


// ============================================================
// ADS
// ============================================================

function openAds() {

    showScreen("ads");

    updateAdUI();

}


function watchDemoAd() {

    if (
        state.adsWatched >= 10
    ) {

        alert(
            "🎉 Today's 10-ad reward has already been completed."
        );

        return;
    }


    state.adsWatched++;


    updateAdUI();


    if (
        state.adsWatched === 10
    ) {

        state.points += 10;


        alert(
            "🎉 Congratulations!\n\n" +
            "+10 QuizBee Points"
        );


        updateStats();

        return;
    }


    alert(
        `📺 Ad completed!\n\n` +
        `${state.adsWatched}/10 completed.`
    );

}


function updateAdUI() {

    const count =
        state.adsWatched;


    const percent =
        (count / 10) * 100;


    const text =
        document.getElementById(
            "ad-progress-text"
        );

    const bar =
        document.getElementById(
            "ad-progress-bar"
        );

    const pageCount =
        document.getElementById(
            "ads-count"
        );

    const pageBar =
        document.getElementById(
            "ads-page-progress"
        );


    if (text) {
        text.textContent =
            `${count} / 10`;
    }


    if (bar) {
        bar.style.width =
            `${percent}%`;
    }


    if (pageCount) {
        pageCount.textContent =
            `${count} / 10`;
    }


    if (pageBar) {
        pageBar.style.width =
            `${percent}%`;
    }

}


// ============================================================
// WALLET
// ============================================================

function openWallet() {

    showScreen("wallet");


    const container =
        document.getElementById(
            "wallet-content"
        );


    container.innerHTML = `

        <div class="wallet-card">

            <h3>
                🐝 QuizBee Points
            </h3>

            <span class="wallet-amount">
                ${state.points}
            </span>

            <small>
                Play-only balance.
                Cannot be withdrawn.
            </small>

        </div>


        <div class="wallet-card">

            <h3>
                🏆 Prize Balance
            </h3>

            <span class="wallet-amount">
                ₦${state.prizeBalance.toLocaleString()}
            </span>

            <small>
                Withdrawable competition winnings.
            </small>

        </div>


        <div class="wallet-note">

            QuizBee Points and Prize Balance
            are completely separate.

            <br><br>

            Points are used to enter games.

            Prize Balance contains actual
            winnings and is withdrawable.

        </div>


        <button
            class="primary-button"
            onclick="withdrawPrize()"
        >
            Withdraw Prize
        </button>


        <button
            class="secondary-button"
            onclick="buyPoints()"
        >
            🐝 Buy QuizBee Points
        </button>

    `;

}


function buyPoints() {

    alert(
        "Payment system will be connected in the payment stage."
    );

}


function withdrawPrize() {

    if (
        state.prizeBalance <= 0
    ) {

        alert(
            "You don't have a withdrawable prize balance yet."
        );

        return;
    }


    alert(
        "Withdrawal system will be connected after the secure backend is implemented."
    );

}


// ============================================================
// PROFILE
// ============================================================

function openProfile() {

    showScreen("profile");


    const container =
        document.getElementById(
            "profile-content"
        );


    const user =
        tg?.initDataUnsafe?.user;


    const name =
        user?.first_name ||
        "QuizBee Player";


    const username =
        user?.username
            ? `@${user.username}`
            : "Telegram User";


    container.innerHTML = `

        <div class="profile-card">

            <div class="avatar">
                🐝
            </div>

            <h2 id="profile-name">
                ${name}
            </h2>

            <p id="profile-username">
                ${username}
            </p>

        </div>


        <div class="profile-stats">

            <div class="profile-stat">

                <strong>
                    ${state.score}
                </strong>

                <span>
                    Score
                </span>

            </div>


            <div class="profile-stat">

                <strong>
                    ${state.streak}
                </strong>

                <span>
                    🔥 Streak
                </span>

            </div>


            <div class="profile-stat">

                <strong>
                    ${state.referrals}
                </strong>

                <span>
                    Referrals
                </span>

            </div>

        </div>


        <div class="info-card">

            <h3>
                🎁 Referral Rewards
            </h3>

            <p>
                10 referrals → +50 Points
            </p>

            <p>
                20 referrals → +100 Points
            </p>

        </div>


        <div class="info-card">

            <h3>
                🔥 Daily Streak
            </h3>

            <p>
                7 consecutive days → +10 Points
            </p>

        </div>

    `;

}


// ============================================================
// LEADERBOARD
// ============================================================

function openLeaderboard() {

    showScreen("leaderboard");


    const container =
        document.getElementById(
            "leaderboard-content"
        );


    const players = [

        {
            name: "QuizMaster",
            score: 980
        },

        {
            name: "BrainBee",
            score: 820
        },

        {
            name: "MysteryPro",
            score: 710
        },

        {
            name: "You",
            score: state.score
        },

        {
            name: "BeeHunter",
            score: 480
        }

    ];


    players.sort(
        (a, b) =>
            b.score - a.score
    );


    container.innerHTML = `

        <div class="leaderboard">

            ${players.map(
                (player, index) => `

                <div class="leader-row">

                    <span class="rank">
                        #${index + 1}
                    </span>

                    <span class="player">
                        ${player.name}
                    </span>

                    <span class="leader-score">
                        ${player.score}
                    </span>

                </div>

            `).join("")}

        </div>

    `;

}


// ============================================================
// STATS
// ============================================================

function updateStats() {

    const points =
        document.getElementById(
            "points"
        );

    const score =
        document.getElementById(
            "score"
        );

    const streak =
        document.getElementById(
            "streak"
        );

    const referrals =
        document.getElementById(
            "referrals"
        );


    if (points) {
        points.textContent =
            state.points;
    }


    if (score) {
        score.textContent =
            state.score;
    }


    if (streak) {
        streak.textContent =
            state.streak;
    }


    if (referrals) {
        referrals.textContent =
            state.referrals;
    }

}


// ============================================================
// NAVIGATION
// ============================================================

function showScreen(id) {

    document
        .querySelectorAll(".screen")
        .forEach(
            screen =>
                screen.classList.remove(
                    "active"
                )
        );


    const screen =
        document.getElementById(id);


    if (screen) {

        screen.classList.add(
            "active"
        );

    }


    window.scrollTo(
        0,
        0
    );

}


function goHome() {

    showScreen("home");

    updateStats();

}


function navigate(section) {

    switch (section) {

        case "home":

            goHome();

            break;


        case "leaderboard":

            openLeaderboard();

            break;


        case "wallet":

            openWallet();

            break;


        case "profile":

            openProfile();

            break;

    }

}


// ============================================================
// TELEGRAM MAIN BUTTON
// ============================================================

if (tg) {

    tg.MainButton.hide();

}
