const tg = window.Telegram?.WebApp;

if (tg) {
    tg.ready();
    tg.expand();
}

// =====================================================
// QUIZBEE DEMO DATA
// =====================================================

const state = {
    points: 240,
    prizeBalance: 0,
    score: 0,
    streak: 4,
    referrals: 7,

    currentGame: null,
    currentQuestion: null,
    currentClueIndex: 0,
    attempts: 0,

    games: {
        guess: {
            id: "guess",
            title: "🎯 Guess It",
            description: "Use the clues to identify the answer.",
            entryFee: 10,
            reward: 25
        },

        whoami: {
            id: "whoami",
            title: "🕵️ Who Am I?",
            description: "Identify the mystery person from progressive clues.",
            entryFee: 10,
            reward: 100
        },

        impossible: {
            id: "impossible",
            title: "💀 Impossible Question",
            description: "One extremely difficult question. Can you solve it?",
            entryFee: 10,
            reward: 100
        }
    },

    questions: {
        guess: [
            {
                clues: [
                    "I am a footballer.",
                    "I have won the Ballon d'Or.",
                    "I am famous for my left foot.",
                    "I have played in Spain."
                ],
                answer: "lionel messi",
                accepted: ["lionel messi", "messi"]
            },
            {
                clues: [
                    "I am a country.",
                    "I am in West Africa.",
                    "My capital is Abuja.",
                    "My largest city is Lagos."
                ],
                answer: "nigeria",
                accepted: ["nigeria"]
            },
            {
                clues: [
                    "I am an animal.",
                    "I am known for my black and white stripes.",
                    "I am closely related to horses."
                ],
                answer: "zebra",
                accepted: ["zebra"]
            }
        ],

        whoami: [
            {
                clues: [
                    "I am a footballer.",
                    "I am famous for my number 7.",
                    "I have played for Manchester United.",
                    "I have won the Champions League."
                ],
                answer: "cristiano ronaldo",
                accepted: ["cristiano ronaldo", "ronaldo", "cr7"]
            },
            {
                clues: [
                    "I am a fictional character.",
                    "I am from an anime.",
                    "I am known for my straw hat.",
                    "I want to become the Pirate King."
                ],
                answer: "monkey d luffy",
                accepted: ["monkey d luffy", "luffy"]
            }
        ],

        impossible: [
            {
                clues: [
                    "A man walks into a room.",
                    "There are three switches outside the room.",
                    "Only one switch controls the light bulb inside.",
                    "The man can enter the room only once.",
                    "How can he determine which switch controls the bulb?"
                ],
                answer: "use heat",
                accepted: [
                    "use heat",
                    "turn one on",
                    "turn one switch on",
                    "heat the bulb",
                    "use the bulb heat"
                ]
            }
        ]
    }
};


// =====================================================
// INITIALIZATION
// =====================================================

document.addEventListener("DOMContentLoaded", () => {
    renderHome();
    updateUI();
});


// =====================================================
// NORMALIZE ANSWERS
// =====================================================

function normalizeAnswer(answer) {
    return answer
        .toLowerCase()
        .trim()
        .replace(/\s+/g, " ")
        .replace(/[.,!?]/g, "");
}


// =====================================================
// CHECK ANSWER
// =====================================================

function isCorrect(userAnswer, question) {
    const normalized = normalizeAnswer(userAnswer);

    return question.accepted.some(answer =>
        normalizeAnswer(answer) === normalized
    );
}


// =====================================================
// UI HELPERS
// =====================================================

function updateUI() {
    const pointsElement = document.getElementById("points");
    const prizeElement = document.getElementById("prize-balance");
    const scoreElement = document.getElementById("score");
    const streakElement = document.getElementById("streak");
    const referralsElement = document.getElementById("referrals");

    if (pointsElement) {
        pointsElement.textContent = state.points;
    }

    if (prizeElement) {
        prizeElement.textContent = formatMoney(state.prizeBalance);
    }

    if (scoreElement) {
        scoreElement.textContent = state.score;
    }

    if (streakElement) {
        streakElement.textContent = state.streak;
    }

    if (referralsElement) {
        referralsElement.textContent = state.referrals;
    }
}


function formatMoney(amount) {
    return `₦${Number(amount).toLocaleString()}`;
}


function showScreen(screenId) {
    document.querySelectorAll(".screen").forEach(screen => {
        screen.classList.remove("active");
    });

    const screen = document.getElementById(screenId);

    if (screen) {
        screen.classList.add("active");
    }

    window.scrollTo(0, 0);
}


// =====================================================
// HOME
// =====================================================

function renderHome() {
    showScreen("home");

    const container = document.getElementById("game-list");

    if (!container) return;

    container.innerHTML = "";

    Object.values(state.games).forEach(game => {
        const card = document.createElement("div");

        card.className = "game-card";

        card.innerHTML = `
            <div class="game-icon">${game.title.split(" ")[0]}</div>

            <div class="game-info">
                <h3>${game.title.substring(game.title.indexOf(" ") + 1)}</h3>
                <p>${game.description}</p>
                <span class="entry-fee">
                    Entry: ${game.entryFee} Points
                </span>
            </div>

            <button onclick="startGame('${game.id}')">
                Play
            </button>
        `;

        container.appendChild(card);
    });
}


// =====================================================
// START GAME
// =====================================================

function startGame(gameId) {
    const game = state.games[gameId];

    if (!game) return;

    if (state.points < game.entryFee) {
        alert("You don't have enough QuizBee Points.");
        return;
    }

    state.points -= game.entryFee;

    state.currentGame = gameId;
    state.attempts = 0;
    state.currentClueIndex = 0;

    const questions = state.questions[gameId];

    if (!questions || questions.length === 0) {
        alert("No question is available for this game yet.");
        state.points += game.entryFee;
        return;
    }

    state.currentQuestion =
        questions[Math.floor(Math.random() * questions.length)];

    renderGame();

    updateUI();
}


// =====================================================
// GAME SCREEN
// =====================================================

function renderGame() {
    showScreen("game");

    const game = state.games[state.currentGame];
    const question = state.currentQuestion;

    const title = document.getElementById("game-title");
    const content = document.getElementById("game-content");

    if (!title || !content) return;

    title.textContent = game.title;

    if (state.currentGame === "guess") {
        renderGuessIt(content, question);
    }

    if (state.currentGame === "whoami") {
        renderWhoAmI(content, question);
    }

    if (state.currentGame === "impossible") {
        renderImpossible(content, question);
    }
}


// =====================================================
// GUESS IT
// =====================================================

function renderGuessIt(container, question) {

    const visibleClues =
        question.clues.slice(
            0,
            Math.min(state.currentClueIndex + 1, question.clues.length)
        );

    container.innerHTML = `
        <div class="question-box">

            <h3>🔎 Clues</h3>

            <div class="clues">
                ${visibleClues.map((clue, index) => `
                    <div class="clue">
                        <strong>Clue ${index + 1}</strong>
                        <p>${clue}</p>
                    </div>
                `).join("")}
            </div>

            <input
                id="answer-input"
                type="text"
                placeholder="Enter your answer..."
                autocomplete="off"
            >

            <button class="submit-btn" onclick="submitAnswer()">
                Submit Answer
            </button>

            <div id="answer-feedback"></div>

        </div>
    `;
}


// =====================================================
// WHO AM I
// =====================================================

function renderWhoAmI(container, question) {

    const visibleClues =
        question.clues.slice(
            0,
            Math.min(state.currentClueIndex + 1, question.clues.length)
        );

    const rewards = [100, 80, 60, 40, 20];

    const currentReward =
        rewards[Math.min(state.currentClueIndex, rewards.length - 1)];

    container.innerHTML = `
        <div class="question-box">

            <div class="reward-banner">
                Current reward: ${currentReward} Score
            </div>

            <h3>🕵️ Who Am I?</h3>

            <div class="clues">
                ${visibleClues.map((clue, index) => `
                    <div class="clue">
                        <strong>Clue ${index + 1}</strong>
                        <p>${clue}</p>
                    </div>
                `).join("")}
            </div>

            <input
                id="answer-input"
                type="text"
                placeholder="Who am I?"
                autocomplete="off"
            >

            <button class="submit-btn" onclick="submitAnswer()">
                Submit Answer
            </button>

            <div id="answer-feedback"></div>

        </div>
    `;
}


// =====================================================
// IMPOSSIBLE QUESTION
// =====================================================

function renderImpossible(container, question) {

    container.innerHTML = `
        <div class="question-box impossible">

            <h3>💀 Impossible Question</h3>

            <p class="impossible-text">
                ${question.clues.join("<br><br>")}
            </p>

            <p class="attempt-info">
                You can try multiple times.
            </p>

            <input
                id="answer-input"
                type="text"
                placeholder="Think carefully..."
                autocomplete="off"
            >

            <button class="submit-btn" onclick="submitAnswer()">
                Submit Answer
            </button>

            <div id="answer-feedback"></div>

        </div>
    `;
}


// =====================================================
// SUBMIT ANSWER
// =====================================================

function submitAnswer() {

    const input = document.getElementById("answer-input");
    const feedback = document.getElementById("answer-feedback");

    if (!input || !feedback) return;

    const answer = input.value.trim();

    if (!answer) {
        feedback.innerHTML = `
            <div class="feedback wrong">
                Please enter an answer.
            </div>
        `;
        return;
    }

    state.attempts++;

    const correct = isCorrect(answer, state.currentQuestion);

    if (correct) {

        let earnedScore = 25;

        if (state.currentGame === "whoami") {

            const rewards = [100, 80, 60, 40, 20];

            earnedScore =
                rewards[
                    Math.min(
                        state.currentClueIndex,
                        rewards.length - 1
                    )
                ];
        }

        if (state.currentGame === "impossible") {
            earnedScore = 100;
        }

        state.score += earnedScore;

        feedback.innerHTML = `
            <div class="feedback correct">
                🎉 Correct!<br>
                +${earnedScore} Score
            </div>

            <button
                class="continue-btn"
                onclick="finishGame()"
            >
                Continue
            </button>
        `;

        input.disabled = true;

        updateUI();

        return;
    }


    // =================================================
    // WRONG ANSWER
    // =================================================

    if (state.currentGame === "impossible") {

        feedback.innerHTML = `
            <div class="feedback wrong">
                ❌ Answer is wrong.<br>
                Try again.
            </div>
        `;

        input.value = "";
        input.focus();

        return;
    }


    // Reveal next clue

    if (
        state.currentClueIndex <
        state.currentQuestion.clues.length - 1
    ) {

        state.currentClueIndex++;

        feedback.innerHTML = `
            <div class="feedback wrong">
                ❌ Not correct.
                Here's another clue.
            </div>
        `;

        setTimeout(() => {
            renderGame();
        }, 700);

    } else {

        feedback.innerHTML = `
            <div class="feedback wrong">
                ❌ Not correct.

                <br><br>

                The correct answer was:
                <strong>${state.currentQuestion.answer}</strong>
            </div>

            <button
                class="continue-btn"
                onclick="finishGame()"
            >
                Finish
            </button>
        `;
    }
}


// =====================================================
// FINISH GAME
// =====================================================

function finishGame() {

    state.currentGame = null;
    state.currentQuestion = null;

    renderHome();
    updateUI();
}


// =====================================================
// WALLET
// =====================================================

function openWallet() {

    showScreen("wallet");

    const wallet = document.getElementById("wallet-content");

    if (!wallet) return;

    wallet.innerHTML = `

        <div class="wallet-card">
            <span>🐝 QuizBee Points</span>
            <strong>${state.points}</strong>
            <small>Play-only balance</small>
        </div>

        <div class="wallet-card prize">
            <span>🏆 Prize Balance</span>
            <strong>${formatMoney(state.prizeBalance)}</strong>
            <small>Withdrawable winnings</small>
        </div>

        <div class="wallet-note">
            QuizBee Points cannot be withdrawn.
            Prize Balance contains your actual winnings.
        </div>

        <button class="withdraw-btn" onclick="withdrawPrize()">
            Withdraw Prize
        </button>
    `;
}


function withdrawPrize() {

    if (state.prizeBalance <= 0) {
        alert("You don't have any withdrawable prize balance yet.");
        return;
    }

    alert(
        "Withdrawal system will be connected after the backend and payment system are built."
    );
}


// =====================================================
// PROFILE
// =====================================================

function openProfile() {

    showScreen("profile");

    const profile = document.getElementById("profile-content");

    if (!profile) return;

    const telegramUser =
        tg?.initDataUnsafe?.user;

    const name =
        telegramUser?.first_name ||
        "QuizBee Player";

    const username =
        telegramUser?.username
            ? `@${telegramUser.username}`
            : "Telegram User";

    profile.innerHTML = `

        <div class="profile-header">
            <div class="avatar">
                🐝
            </div>

            <h2>${name}</h2>

            <p>${username}</p>
        </div>

        <div class="stats-grid">

            <div class="stat">
                <strong>${state.score}</strong>
                <span>Score</span>
            </div>

            <div class="stat">
                <strong>${state.streak}</strong>
                <span>Day Streak</span>
            </div>

            <div class="stat">
                <strong>${state.referrals}</strong>
                <span>Referrals</span>
            </div>

        </div>

        <div class="milestone">
            <h3>🎁 Referral Milestones</h3>

            <p>
                10 referrals → +50 Points
            </p>

            <p>
                20 referrals → +100 Points
            </p>

            <p>
                Current referrals:
                <strong>${state.referrals}</strong>
            </p>
        </div>
    `;
}


// =====================================================
// LEADERBOARD
// =====================================================

function openLeaderboard() {

    showScreen("leaderboard");

    const leaderboard =
        document.getElementById("leaderboard-content");

    if (!leaderboard) return;

    const players = [
        { name: "QuizMaster", score: 980 },
        { name: "BrainBee", score: 820 },
        { name: "MysteryPro", score: 710 },
        { name: "You", score: state.score },
        { name: "BeeHunter", score: 480 }
    ];

    players.sort((a, b) => b.score - a.score);

    leaderboard.innerHTML = `
        <div class="leaderboard-list">

            ${players.map((player, index) => `
                <div class="leaderboard-row">

                    <span class="rank">
                        #${index + 1}
                    </span>

                    <span class="player-name">
                        ${player.name}
                    </span>

                    <strong>
                        ${player.score}
                    </strong>

                </div>
            `).join("")}

        </div>
    `;
}


// =====================================================
// NAVIGATION
// =====================================================

function goHome() {
    renderHome();
    updateUI();
}


function navigate(section) {

    if (section === "home") {
        goHome();
    }

    if (section === "wallet") {
        openWallet();
    }

    if (section === "profile") {
        openProfile();
    }

    if (section === "leaderboard") {
        openLeaderboard();
    }
}


// =====================================================
// BUY POINTS
// =====================================================

function buyPoints() {

    alert(
        "Payment system coming next. We will connect Nigerian and international payment options."
    );
}


// =====================================================
// TELEGRAM MAIN BUTTON
// =====================================================

if (tg) {
    tg.MainButton.hide();
            }
