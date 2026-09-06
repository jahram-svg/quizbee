const tg = window.Telegram.WebApp;

tg.ready();

tg.expand();


let user = tg.initDataUnsafe?.user || {

    id: 0,

    first_name: "QuizBee",

    username: "player"

};


let quizbeePoints = 0;

let prizeBalance = 0;

let score = 0;

let streak = 0;

let referrals = 0;


function showPage(pageId) {

    document.querySelectorAll(".page")
        .forEach(page => {

            page.classList.remove("active");

        });


    document
        .getElementById(pageId)
        .classList.add("active");


    window.scrollTo(0, 0);
}


function goHome() {

    showPage("home");

}


function openGame(game) {

    showPage("game");


    const content =
        document.getElementById("gameContent");


    if (game === "guess") {

        content.innerHTML = `

            <h2>🎯 Guess It</h2>

            <div class="info-card">

                <h3>Today's Challenge</h3>

                <p>
                    Guess the answer from the clues.
                </p>

                <br>

                <strong>
                    🟡 Entry: 10 Points
                </strong>

                <br><br>

                <button
                    onclick="startGame('guess')"
                    style="
                        width:100%;
                        padding:14px;
                        border:none;
                        border-radius:12px;
                        background:#111;
                        color:white;
                    "
                >
                    Start Game
                </button>

            </div>

        `;

    }


    if (game === "who") {

        content.innerHTML = `

            <h2>🕵️ Who Am I?</h2>

            <div class="info-card">

                <h3>Can you identify them?</h3>

                <p>
                    Receive clues and guess
                    who the mystery person is.
                </p>

                <br>

                <strong>
                    🟡 Entry: 10 Points
                </strong>

                <br><br>

                <button
                    onclick="startGame('who')"
                    style="
                        width:100%;
                        padding:14px;
                        border:none;
                        border-radius:12px;
                        background:#111;
                        color:white;
                    "
                >
                    Start Game
                </button>

            </div>

        `;

    }


    if (game === "impossible") {

        content.innerHTML = `

            <h2>💀 Impossible Question</h2>

            <div class="info-card">

                <h3>This week's question</h3>

                <p>
                    One question.
                    Seven days.
                    Good luck. 😂
                </p>

                <br>

                <strong>
                    🟡 Entry: 10 Points
                </strong>

                <br><br>

                <button
                    onclick="startGame('impossible')"
                    style="
                        width:100%;
                        padding:14px;
                        border:none;
                        border-radius:12px;
                        background:#111;
                        color:white;
                    "
                >
                    Enter Challenge
                </button>

            </div>

        `;

    }

}


function startGame(game) {

    if (quizbeePoints < 10) {

        tg.showAlert(
            "You need at least 10 QuizBee Points to enter this game."
        );

        return;

    }


    quizbeePoints -= 10;

    updateUI();


    tg.showAlert(
        "Game entry confirmed! 🐝"
    );

}


function buyPoints() {

    tg.showAlert(
        "Point purchases will be connected to payment processing."
    );

}


function withdraw() {

    if (prizeBalance <= 0) {

        tg.showAlert(
            "You don't have any withdrawable prize balance yet."
        );

        return;

    }


    tg.showAlert(
        "Withdrawal system coming soon."
    );

}


function updateUI() {

    document.getElementById("points")
        .textContent = quizbeePoints;


    document.getElementById("walletPoints")
        .textContent = quizbeePoints;


    document.getElementById("prizeBalance")
        .textContent = prizeBalance.toFixed(2);


    document.getElementById("profileScore")
        .textContent = score;


    document.getElementById("streak")
        .textContent = streak;


    document.getElementById("referrals")
        .textContent = referrals;


    document.getElementById("username")
        .textContent =
        user.first_name || "QuizBee Player";


    document.getElementById("telegramUsername")
        .textContent =
        user.username
            ? "@" + user.username
            : "Telegram User";


    document.getElementById("welcome")
        .textContent =
        `Welcome, ${user.first_name || "Player"} 👋`;

}


updateUI();
