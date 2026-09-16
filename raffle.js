/* ============================================================
   QUIZBEE RAFFLE DRAW
   User-facing raffle system
============================================================ */

let raffleTimer = null;
let raffleCurrent = null;
let raffleLoading = false;


/* ============================================================
   HELPERS
============================================================ */

function raffleEscape(value) {

    if (typeof escapeHtml === "function") {
        return escapeHtml(value);
    }

    return String(value ?? "")
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#039;");
}


function raffleFormatNumber(value) {
    return Number(value || 0).toLocaleString();
}


function rafflePurchaseId() {

    if (window.crypto?.randomUUID) {
        return window.crypto.randomUUID();
    }

    return `raffle-${Date.now()}-${Math.random()
        .toString(36)
        .slice(2)}`;
}


function raffleFormatDate(value) {

    if (!value) {
        return "—";
    }

    const date = new Date(value);

    if (Number.isNaN(date.getTime())) {
        return "—";
    }

    return date.toLocaleString(undefined, {
        dateStyle: "medium",
        timeStyle: "short"
    });
}


function raffleStatusLabel(status) {

    if (status === "live") {
        return "🟢 LIVE NOW";
    }

    if (status === "scheduled") {
        return "🕐 STARTING SOON";
    }

    if (status === "ended") {
        return "🔴 ENDED";
    }

    return "🔒 UNAVAILABLE";
}


/* ============================================================
   TIMER
============================================================ */

function raffleStopTimer() {

    if (raffleTimer) {

        clearInterval(
            raffleTimer
        );

        raffleTimer = null;
    }
}


function raffleCountdown(
    target,
    status
) {

    const element =
        document.getElementById(
            "raffleCountdown"
        );

    if (!element) {
        return;
    }

    const targetTime =
        new Date(target).getTime();

    const remaining =
        targetTime - Date.now();


    if (remaining <= 0) {

        element.textContent =
            status === "scheduled"
                ? "Starting now..."
                : "Raffle ending...";

        raffleStopTimer();

        setTimeout(() => {

            loadUserRaffle(true);

        }, 1000);

        return;
    }


    const totalSeconds =
        Math.floor(
            remaining / 1000
        );

    const days =
        Math.floor(
            totalSeconds / 86400
        );

    const hours =
        Math.floor(
            (totalSeconds % 86400) / 3600
        );

    const minutes =
        Math.floor(
            (totalSeconds % 3600) / 60
        );

    const seconds =
        totalSeconds % 60;


    const parts = [];


    if (days > 0) {
        parts.push(`${days}d`);
    }

    if (
        hours > 0 ||
        days > 0
    ) {
        parts.push(`${hours}h`);
    }

    parts.push(`${minutes}m`);

    parts.push(`${seconds}s`);


    element.textContent =
        parts.join(" ");
}


function raffleStartTimer(
    target,
    status
) {

    raffleStopTimer();

    raffleCountdown(
        target,
        status
    );

    raffleTimer =
        setInterval(() => {

            raffleCountdown(
                target,
                status
            );

        }, 1000);
}


/* ============================================================
   LOADING / EMPTY STATES
============================================================ */

function raffleSetLoading(
    message = "Loading raffle..."
) {

    const container =
        document.getElementById(
            "raffleContent"
        );

    if (!container) {
        return;
    }

    container.innerHTML = `

        <div
            class="info-box"
            style="
                text-align:center;
                padding:30px 20px;
            "
        >

            <div
                style="
                    font-size:36px;
                    margin-bottom:10px;
                "
            >
                🎟️
            </div>

            <strong>
                ${raffleEscape(message)}
            </strong>

        </div>

    `;
}


function raffleEmptyState(
    title,
    message,
    icon = "🎟️"
) {

    const container =
        document.getElementById(
            "raffleContent"
        );

    if (!container) {
        return;
    }

    container.innerHTML = `

        <div
            class="info-box"
            style="
                text-align:center;
                padding:34px 20px;
            "
        >

            <div
                style="
                    font-size:52px;
                    margin-bottom:12px;
                "
            >
                ${icon}
            </div>

            <h2
                style="
                    margin:0 0 10px;
                "
            >
                ${raffleEscape(title)}
            </h2>

            <p
                style="
                    margin:0;
                    line-height:1.6;
                    opacity:.75;
                "
            >
                ${raffleEscape(message)}
            </p>

        </div>

    `;
}


/* ============================================================
   RENDER RAFFLE
============================================================ */

function raffleRender(data) {

    const container =
        document.getElementById(
            "raffleContent"
        );

    if (!container) {
        return;
    }


    raffleCurrent =
        data?.raffle || null;


    if (!data?.enabled) {

        raffleStopTimer();

        raffleEmptyState(
            "Raffle Draw is Locked",
            "Raffle Draw is currently unavailable. Please check back later.",
            "🔒"
        );

        return;
    }


    if (!raffleCurrent) {

        raffleStopTimer();

        raffleEmptyState(
            "No Active Raffle",
            "There is no scheduled or live raffle right now. Check back soon.",
            "🎟️"
        );

        return;
    }


    const raffle =
        raffleCurrent;

    const status =
        raffle.status ||
        "invalid";

    const isLive =
        status === "live";

    const isScheduled =
        status === "scheduled";


    const prizeImage =
        String(
            raffle.prize_image || ""
        ).trim();


    const countdownTarget =
        isScheduled
            ? raffle.start_at
            : raffle.end_at;


    container.innerHTML = `

        <div
            class="info-box"
            style="
                padding:10px 14px;
                text-align:center;
                margin-bottom:14px;
            "
        >

            <strong>
                ${raffleStatusLabel(status)}
            </strong>

        </div>


        <div
            class="game-detail-card"
            style="
                overflow:hidden;
            "
        >

            ${
                prizeImage

                    ? `

                        <img
                            src="${raffleEscape(
                                prizeImage
                            )}"
                            alt="${raffleEscape(
                                raffle.prize_name ||
                                "Raffle prize"
                            )}"
                            style="
                                width:100%;
                                max-height:240px;
                                object-fit:cover;
                                border-radius:18px;
                                margin-bottom:16px;
                            "
                            onerror="
                                this.style.display='none'
                            "
                        >

                    `

                    : `

                        <div
                            style="
                                height:190px;
                                border-radius:18px;
                                display:flex;
                                align-items:center;
                                justify-content:center;
                                background:rgba(
                                    255,
                                    255,
                                    255,
                                    .05
                                );
                                font-size:70px;
                                margin-bottom:16px;
                            "
                        >
                            🎁
                        </div>

                    `
            }


            <div
                style="
                    text-align:center;
                "
            >

                <div
                    style="
                        font-size:12px;
                        opacity:.65;
                        text-transform:uppercase;
                        letter-spacing:1px;
                    "
                >
                    RAFFLE PRIZE
                </div>


                <h2
                    style="
                        margin:6px 0 12px;
                    "
                >
                    ${raffleEscape(
                        raffle.prize_name ||
                        "QuizBee Raffle Prize"
                    )}
                </h2>


                <div
                    class="reward-box"
                    style="
                        margin-bottom:14px;
                    "
                >

                    <span>
                        Ticket Price
                    </span>

                    <strong>
                        100 Points
                    </strong>

                </div>


                <div
                    class="info-box"
                    style="
                        margin-bottom:14px;
                    "
                >

                    <div
                        style="
                            font-size:12px;
                            opacity:.65;
                            margin-bottom:5px;
                        "
                    >
                        ${
                            isScheduled
                                ? "STARTS IN"
                                : "ENDS IN"
                        }
                    </div>


                    <strong
                        id="raffleCountdown"
                        style="
                            font-size:24px;
                        "
                    >
                        --
                    </strong>

                </div>


                <div
                    style="
                        font-size:12px;
                        line-height:1.7;
                        opacity:.7;
                        margin-bottom:16px;
                    "
                >

                    ${
                        isScheduled
                            ? "Starts"
                            : "Ends"
                    }:

                    ${raffleFormatDate(
                        countdownTarget
                    )}

                </div>

            </div>


            ${
                isLive

                    ? `

                        <div
                            class="info-box"
                            style="
                                margin-bottom:14px;
                            "
                        >

                            🎟️ Every ticket costs

                            <strong>
                                100 QuizBee Points
                            </strong>.

                            Buy multiple tickets
                            to get multiple entries.

                        </div>


                        <label
                            style="
                                display:block;
                                margin-bottom:7px;
                                font-weight:600;
                            "
                        >
                            Number of Tickets
                        </label>


                        <div
                            style="
                                display:flex;
                                gap:10px;
                                align-items:stretch;
                                margin-bottom:12px;
                            "
                        >

                            <button
                                type="button"
                                class="secondary-btn"
                                style="
                                    min-width:48px;
                                "
                                onclick="
                                    changeRaffleQuantity(-1)
                                "
                            >
                                −
                            </button>


                            <input
                                id="raffleQuantity"
                                class="number-input"
                                type="number"
                                min="1"
                                max="100"
                                value="1"
                                inputmode="numeric"
                                oninput="
                                    updateRaffleCost()
                                "
                                style="
                                    flex:1;
                                    text-align:center;
                                "
                            >


                            <button
                                type="button"
                                class="secondary-btn"
                                style="
                                    min-width:48px;
                                "
                                onclick="
                                    changeRaffleQuantity(1)
                                "
                            >
                                +
                            </button>

                        </div>


                        <div
                            class="reward-box"
                            style="
                                margin-bottom:12px;
                            "
                        >

                            <span>
                                Total Cost
                            </span>

                            <strong
                                id="raffleTotalCost"
                            >
                                100 Points
                            </strong>

                        </div>


                        <button
                            id="buyRaffleButton"
                            class="primary-btn full"
                            onclick="
                                buyRaffleTickets()
                            "
                        >
                            🎟️ BUY TICKETS
                        </button>

                    `

                    : `

                        <div
                            class="info-box"
                            style="
                                text-align:center;
                            "
                        >

                            🕐 Ticket purchases
                            will open when the
                            raffle starts.

                        </div>

                    `
            }

        </div>


        <div
            id="raffleMyTickets"
            style="
                margin-top:16px;
            "
        >

            <div class="info-box">
                Loading your tickets...
            </div>

        </div>


        <div
            class="info-box"
            style="
                margin-top:16px;
                line-height:1.6;
                text-align:center;
            "
        >

            📢 The winner will be announced
            in the official QuizBee Telegram
            channel after the raffle ends.

        </div>

    `;


    raffleStartTimer(
        countdownTarget,
        status
    );


    if (isLive) {
        updateRaffleCost();
    }


    loadMyRaffleTickets(
        raffle.raffle_id
    );
}


/* ============================================================
   QUANTITY
============================================================ */

function changeRaffleQuantity(
    change
) {

    const input =
        document.getElementById(
            "raffleQuantity"
        );

    if (!input) {
        return;
    }


    let quantity =
        Number(
            input.value || 1
        );


    quantity +=
        Number(
            change || 0
        );


    quantity =
        Math.max(
            1,
            Math.min(
                100,
                quantity
            )
        );


    input.value =
        quantity;


    updateRaffleCost();
}


function updateRaffleCost() {

    const input =
        document.getElementById(
            "raffleQuantity"
        );

    const total =
        document.getElementById(
            "raffleTotalCost"
        );


    if (!input || !total) {
        return;
    }


    let quantity =
        Number(
            input.value || 1
        );


    if (
        !Number.isFinite(
            quantity
        )
    ) {

        quantity = 1;

    }


    quantity =
        Math.max(
            1,
            Math.min(
                100,
                Math.floor(
                    quantity
                )
            )
        );


    input.value =
        quantity;


    total.textContent =
        `${raffleFormatNumber(
            quantity * 100
        )} Points`;
}


/* ============================================================
   USER TICKETS
============================================================ */

async function loadMyRaffleTickets(
    raffleId
) {

    const container =
        document.getElementById(
            "raffleMyTickets"
        );


    if (
        !container ||
        !raffleId
    ) {
        return;
    }


    try {

        const data =
            await api(
                `/api/raffles/${encodeURIComponent(
                    raffleId
                )}/my-tickets`
            );


        const tickets =
            data.tickets || [];


        if (!tickets.length) {

            container.innerHTML = `

                <div
                    class="info-box"
                    style="
                        text-align:center;
                    "
                >

                    <strong>
                        You have no tickets yet.
                    </strong>

                    <br>

                    <span
                        style="
                            opacity:.7;
                        "
                    >
                        Your purchased ticket IDs
                        will appear here.
                    </span>

                </div>

            `;

            return;
        }


        container.innerHTML = `

            <div
                class="panel"
                style="
                    padding:18px;
                "
            >

                <div
                    style="
                        display:flex;
                        justify-content:space-between;
                        gap:10px;
                        align-items:center;
                        margin-bottom:12px;
                    "
                >

                    <h3
                        style="
                            margin:0;
                        "
                    >
                        🎟️ My Tickets
                    </h3>

                    <strong>
                        ${tickets.length}
                    </strong>

                </div>


                <div
                    style="
                        display:flex;
                        flex-wrap:wrap;
                        gap:7px;
                    "
                >

                    ${
                        tickets
                            .map(
                                ticket => `

                                    <span
                                        style="
                                            padding:7px 9px;
                                            border-radius:9px;
                                            background:
                                                rgba(
                                                    255,
                                                    255,
                                                    255,
                                                    .06
                                                );
                                            font-size:12px;
                                        "
                                    >
                                        ${raffleEscape(
                                            ticket.ticket_id ||
                                            ticket.id
                                        )}
                                    </span>

                                `
                            )
                            .join("")
                    }

                </div>

            </div>

        `;

    } catch (error) {

        console.error(
            "Raffle tickets error:",
            error
        );


        container.innerHTML = `

            <div
                class="info-box"
                style="
                    text-align:center;
                "
            >
                Unable to load your raffle tickets.
            </div>

        `;
    }
}


/* ============================================================
   BUY TICKETS
============================================================ */

async function buyRaffleTickets() {

    if (raffleLoading) {
        return;
    }

    if (
        !raffleCurrent ||
        raffleCurrent.status !== "live"
    ) {
        showToast(
            "Ticket purchases are not currently open."
        );
        return;
    }

    const input =
        document.getElementById("raffleQuantity");

    const button =
        document.getElementById("buyRaffleButton");

    let quantity =
        Number(input?.value || 1);

    if (!Number.isFinite(quantity)) {
        showToast(
            "Enter a valid ticket quantity."
        );
        return;
    }

    quantity = Math.floor(quantity);

    if (
        quantity < 1 ||
        quantity > 100
    ) {
        showToast(
            "You can buy between 1 and 100 tickets at once."
        );
        return;
    }

    const totalCost =
        quantity * 100;

    const currentPoints =
        Number(
            currentUser?.quizbee_points ??
            currentUser?.points ??
            0
        );

    if (currentPoints < totalCost) {
        showToast(
            `You need ${raffleFormatNumber(totalCost)} Points.`
        );
        return;
    }

    raffleLoading = true;

    if (button) {
        button.disabled = true;
        button.textContent =
            "🎟️ PROCESSING...";
    }

    try {

        // KEEP YOUR EXISTING API PURCHASE CODE HERE

    } catch (error) {

        console.error(
            "Raffle purchase error:",
            error
        );

        showToast(
            error.message ||
            "Unable to purchase raffle tickets."
        );

    } finally {

        raffleLoading = false;

        if (button) {
            button.disabled = false;
            button.textContent =
                "🎟️ BUY TICKETS";
        }
    }
}


/* ============================================================
   LOAD CURRENT RAFFLE
============================================================ */

async function loadUserRaffle(
    force = false
) {

    if (
        raffleLoading &&
        !force
    ) {
        return;
    }


    raffleLoading =
        true;


    raffleSetLoading(
        "Loading raffle..."
    );


    try {

        const data =
            await api(
                "/api/raffles/current"
            );


        raffleRender(
            data
        );


    } catch (error) {

        console.error(
            "Raffle load error:",
            error
        );


        raffleStopTimer();


        const container =
            document.getElementById(
                "raffleContent"
            );


        if (container) {

            container.innerHTML = `

                <div
                    class="info-box"
                    style="
                        text-align:center;
                        padding:30px 20px;
                    "
                >

                    <div
                        style="
                            font-size:42px;
                            margin-bottom:10px;
                        "
                    >
                        ⚠️
                    </div>


                    <h2
                        style="
                            margin:0 0 10px;
                        "
                    >
                        Unable to load
                        Raffle Draw
                    </h2>


                    <p
                        style="
                            opacity:.7;
                            line-height:1.6;
                        "
                    >
                        ${raffleEscape(
                            error.message ||
                            "Please try again."
                        )}
                    </p>


                    <button
                        class="primary-btn"
                        onclick="
                            loadUserRaffle(true)
                        "
                    >
                        TRY AGAIN
                    </button>

                </div>

            `;

        }


    } finally {

        raffleLoading =
            false;

    }
}


/* ============================================================
   NAVIGATION HOOK
============================================================ */

function rafflePageOpened() {

    loadUserRaffle();

}


const quizbeeOriginalShowPage =
    window.showPage;


if (
    typeof quizbeeOriginalShowPage ===
    "function"
) {

    window.showPage =
        function(page) {

            quizbeeOriginalShowPage(
                page
            );


            if (
                page ===
                "raffle"
            ) {

                rafflePageOpened();

            } else {

                raffleStopTimer();

            }

        };

}


/* ============================================================
   INITIALIZE RAFFLE PAGE
============================================================ */

document.addEventListener(
    "DOMContentLoaded",
    () => {

        const rafflePage =
            document.getElementById(
                "rafflePage"
            );


        if (!rafflePage) {
            return;
        }


        rafflePage.innerHTML = `

            <div class="page-heading">

                <button
                    class="back-btn"
                    onclick="goHome()"
                >
                    ‹
                </button>

                <h1>
                    🎟️ Raffle Draw
                </h1>

            </div>


            <div id="raffleContent">

                <div
                    class="info-box"
                    style="
                        text-align:center;
                        padding:30px 20px;
                    "
                >
                    Loading Raffle Draw...
                </div>

            </div>

        `;

    }
);
