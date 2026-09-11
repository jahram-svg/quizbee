// ============================================================
// QUIZBEE WALLET SYSTEM
// ============================================================

let walletTransactions = [];
let walletWithdrawals = [];
let walletPointOrders = [];


// ============================================================
// CONFIG
// ============================================================

const WALLET_SUPPORT_BOT =
    window.QUIZBEE_CONFIG?.SUPPORT_BOT_USERNAME ||
    "";


// ============================================================
// OPEN TELEGRAM SUPPORT
// ============================================================

function openPurchaseSupport(
    type
) {

    if (!WALLET_SUPPORT_BOT) {

        showToast(
            "Payment support is not configured yet."
        );

        return;
    }

    let message = "";

    if (type === "nigeria") {

        message =
            "purchase 100ngn 50coins";

    } else if (type === "crypto") {

        message =
            "purchase 1usd 1000coins";

    } else {

        message =
            "I want to buy QuizBee Points.";

    }

    const url =
        `https://t.me/${WALLET_SUPPORT_BOT}?text=${encodeURIComponent(
            message
        )}`;

    if (
        window.Telegram &&
        Telegram.WebApp &&
        Telegram.WebApp.openTelegramLink
    ) {

        Telegram.WebApp.openTelegramLink(
            url
        );

    } else {

        window.open(
            url,
            "_blank"
        );

    }
}


// ============================================================
// BUY POINTS
// ============================================================

async function buyPoints() {

    const container =
        document.getElementById(
            "gameContent"
        );

    if (!container) {
        return;
    }

    showPage("game");

    const gamePage =
        document.getElementById(
            "gamePage"
        );

    if (gamePage) {

        const title =
            document.getElementById(
                "gameTitle"
            );

        if (title) {
            title.textContent =
                "💰 Buy QuizBee Points";
        }
    }

    container.innerHTML = `

        <div class="wallet-page">

            <div class="wallet-balance-card">

                <span>
                    Your QuizBee Points
                </span>

                <strong id="walletPointsDisplay">
                    0
                </strong>

                <small>
                    Points are used to enter games.
                </small>

            </div>


            <div class="wallet-section-title">
                Choose a payment method
            </div>


            <button
                class="wallet-option"
                onclick="openPurchaseSupport('nigeria')"
            >

                <div class="wallet-option-icon">
                    🇳🇬
                </div>

                <div class="wallet-option-info">

                    <strong>
                        Nigeria
                    </strong>

                    <span>
                        ₦100 → 50 QuizBee Points
                    </span>

                    <small>
                        Manual payment
                    </small>

                </div>

                <div class="wallet-arrow">
                    ›
                </div>

            </button>


            <button
                class="wallet-option"
                onclick="openPurchaseSupport('crypto')"
            >

                <div class="wallet-option-icon">
                    🌎
                </div>

                <div class="wallet-option-info">

                    <strong>
                        Crypto
                    </strong>

                    <span>
                        $1 → 1,000 QuizBee Points
                    </span>

                    <small>
                        Manual payment
                    </small>

                </div>

                <div class="wallet-arrow">
                    ›
                </div>

            </button>


            <button
                class="wallet-option stars-option"
                onclick="startStarsPurchase()"
            >

                <div class="wallet-option-icon">
                    ⭐
                </div>

                <div class="wallet-option-info">

                    <strong>
                        Telegram Stars
                    </strong>

                    <span>
                        Buy points instantly
                    </span>

                    <small>
                        Telegram payment
                    </small>

                </div>

                <div class="wallet-arrow">
                    ›
                </div>

            </button>


            <div class="wallet-note">

                <strong>
                    Manual payments
                </strong>

                <p>
                    After making a manual payment,
                    send your payment proof through
                    QuizBee Support. Your points will
                    be added after the payment is
                    verified.
                </p>

            </div>


            <button
                class="secondary-wallet-btn"
                onclick="showWalletHistory()"
            >
                📜 Transaction History
            </button>

        </div>

    `;

    const balance =
        document.getElementById(
            "walletPointsDisplay"
        );

    if (
        balance &&
        typeof currentUser !== "undefined" &&
        currentUser
    ) {

        balance.textContent =
            Number(
                currentUser.quizbee_points || 0
            ).toLocaleString();

    }

}


// ============================================================
// TELEGRAM STARS PLACEHOLDER
// ============================================================

function startStarsPurchase() {

    showToast(
        "⭐ Telegram Stars payment will be connected next."
    );

}


// ============================================================
// WITHDRAW PRIZE
// ============================================================

async function withdrawPrize() {

    const container =
        document.getElementById(
            "gameContent"
        );

    if (!container) {
        return;
    }

    showPage("game");

    const title =
        document.getElementById(
            "gameTitle"
        );

    if (title) {
        title.textContent =
            "💸 Withdraw Prize";
    }


    let balance = 0;

    if (
        typeof currentUser !== "undefined" &&
        currentUser
    ) {

        balance =
            Number(
                currentUser.prize_balance || 0
            );

    }


    container.innerHTML = `

        <div class="wallet-page">

            <div class="withdraw-balance-card">

                <span>
                    Available Prize Balance
                </span>

                <strong>
                    $${balance.toFixed(2)}
                </strong>

                <small>
                    No minimum withdrawal.
                    You can withdraw any amount
                    you have won.
                </small>

            </div>


            <div class="wallet-section-title">
                Withdrawal amount
            </div>


            <input
                id="withdrawAmount"
                class="wallet-input"
                type="number"
                min="0.01"
                step="0.01"
                max="${balance}"
                placeholder="Enter amount in USD"
            >


            <div class="wallet-section-title">
                Choose withdrawal method
            </div>


            <div class="withdraw-methods">

                <button
                    class="withdraw-method active"
                    id="bankMethodButton"
                    onclick="selectWithdrawalMethod('bank')"
                >

                    🇳🇬

                    <span>
                        Nigerian Bank
                    </span>

                </button>


                <button
                    class="withdraw-method"
                    id="cryptoMethodButton"
                    onclick="selectWithdrawalMethod('crypto')"
                >

                    💵

                    <span>
                        USDT BEP20
                    </span>

                </button>

            </div>


            <div id="withdrawFields">

                ${renderBankFields()}

            </div>


            <div class="wallet-note">

                <strong>
                    💡 Important
                </strong>

                <p>
                    Your withdrawal amount is
                    always recorded in USD.
                    Nigerian bank withdrawals
                    will be converted to NGN
                    when the payment is made.
                </p>

                <p>
                    USDT withdrawals are paid
                    using the BEP20 network.
                </p>

                <p>
                    More payment options coming soon.
                </p>

            </div>


            <button
                class="primary-btn wallet-submit-btn"
                onclick="submitWithdrawal()"
            >
                REQUEST WITHDRAWAL
            </button>


            <button
                class="secondary-wallet-btn"
                onclick="showWithdrawalHistory()"
            >
                📜 Withdrawal History
            </button>

        </div>

    `;

    window.currentWithdrawalMethod =
        "bank";

}


// ============================================================
// BANK FIELDS
// ============================================================

function renderBankFields() {

    return `

        <div class="wallet-form-group">

            <label>
                Bank name
            </label>

            <input
                id="bankName"
                class="wallet-input"
                type="text"
                placeholder="Your bank name"
            >

        </div>


        <div class="wallet-form-group">

            <label>
                Account number
            </label>

            <input
                id="accountNumber"
                class="wallet-input"
                type="text"
                inputmode="numeric"
                placeholder="Account number"
            >

        </div>


        <div class="wallet-form-group">

            <label>
                Account name
            </label>

            <input
                id="accountName"
                class="wallet-input"
                type="text"
                placeholder="Account holder name"
            >

        </div>

    `;

}


// ============================================================
// CRYPTO FIELDS
// ============================================================

function renderCryptoFields() {

    return `

        <div class="wallet-form-group">

            <label>
                USDT BEP20 Wallet Address
            </label>

            <input
                id="walletAddress"
                class="wallet-input"
                type="text"
                placeholder="Paste your BEP20 address"
                autocomplete="off"
            >

        </div>


        <div class="wallet-warning">

            ⚠️ Make sure this is a
            <strong>USDT BEP20</strong>
            address.

            Payments sent to the wrong
            network may be lost.

        </div>

    `;

}


// ============================================================
// SELECT WITHDRAWAL METHOD
// ============================================================

function selectWithdrawalMethod(
    method
) {

    window.currentWithdrawalMethod =
        method;

    const bankButton =
        document.getElementById(
            "bankMethodButton"
        );

    const cryptoButton =
        document.getElementById(
            "cryptoMethodButton"
        );

    if (bankButton) {

        bankButton.classList.toggle(
            "active",
            method === "bank"
        );

    }

    if (cryptoButton) {

        cryptoButton.classList.toggle(
            "active",
            method === "crypto"
        );

    }

    const fields =
        document.getElementById(
            "withdrawFields"
        );

    if (!fields) {
        return;
    }

    fields.innerHTML =
        method === "bank"
            ? renderBankFields()
            : renderCryptoFields();

}


// ============================================================
// SUBMIT WITHDRAWAL
// ============================================================

async function submitWithdrawal() {

    const amountInput =
        document.getElementById(
            "withdrawAmount"
        );

    if (!amountInput) {
        return;
    }

    const amount =
        Number(
            amountInput.value
        );

    const balance =
        Number(
            currentUser?.prize_balance || 0
        );


    if (
        !Number.isFinite(amount) ||
        amount <= 0
    ) {

        showToast(
            "Enter a valid withdrawal amount."
        );

        return;

    }


    if (amount > balance) {

        showToast(
            "You cannot withdraw more than your Prize Balance."
        );

        return;

    }


    const method =
        window.currentWithdrawalMethod ||
        "bank";


    let body = {
        amount:
            amount,
        method:
            method === "bank"
                ? "nigerian_bank"
                : "usdt_bep20"
    };


    if (
        method === "bank"
    ) {

        const bankName =
            document.getElementById(
                "bankName"
            )?.value.trim();

        const accountNumber =
            document.getElementById(
                "accountNumber"
            )?.value.trim();

        const accountName =
            document.getElementById(
                "accountName"
            )?.value.trim();


        if (
            !bankName ||
            !accountNumber ||
            !accountName
        ) {

            showToast(
                "Complete all bank details."
            );

            return;

        }


        body.bank_name =
            bankName;

        body.account_number =
            accountNumber;

        body.account_name =
            accountName;

    } else {

        const walletAddress =
            document.getElementById(
                "walletAddress"
            )?.value.trim();


        if (!walletAddress) {

            showToast(
                "Enter your USDT BEP20 wallet address."
            );

            return;

        }


        body.wallet_address =
            walletAddress;

    }


    const button =
        document.querySelector(
            ".wallet-submit-btn"
        );

    if (button) {

        button.disabled =
            true;

        button.textContent =
            "SUBMITTING...";

    }


    try {

        const data =
            await api(
                "/api/wallet/withdraw",
                {
                    method: "POST",
                    body:
                        JSON.stringify(
                            body
                        )
                }
            );


        if (
            data.user
        ) {

            updateUserState(
                data.user
            );

        }


        if (
            currentUser
        ) {

            currentUser.prize_balance =
                balance -
                amount;

            updateUserState(
                currentUser
            );

        }


        showToast(
            "✅ Withdrawal request submitted."
        );


        setTimeout(
            () => {

                showPage(
                    "profile"
                );

            },
            1200
        );


    } catch (error) {

        console.error(
            "Withdrawal error:",
            error
        );

        showToast(
            error.message ||
            "Unable to submit withdrawal."
        );


        if (button) {

            button.disabled =
                false;

            button.textContent =
                "REQUEST WITHDRAWAL";

        }

    }

}


// ============================================================
// TRANSACTION HISTORY
// ============================================================

async function showWalletHistory() {

    const container =
        document.getElementById(
            "gameContent"
        );

    if (!container) {
        return;
    }

    container.innerHTML = `

        <div class="wallet-page">

            <div class="page-heading">
                <button
                    class="back-btn"
                    onclick="buyPoints()"
                >
                    ‹
                </button>

                <h1>
                    📜 Transactions
                </h1>
            </div>

            <div id="walletHistoryList">

                <div class="info-box">
                    Loading transactions...
                </div>

            </div>

        </div>

    `;


    try {

        const data =
            await api(
                "/api/wallet/transactions"
            );

        walletTransactions =
            data.transactions ||
            [];


        const list =
            document.getElementById(
                "walletHistoryList"
            );


        if (
            !walletTransactions.length
        ) {

            list.innerHTML = `

                <div class="info-box">
                    No transactions yet.
                </div>

            `;

            return;

        }


        list.innerHTML =
            walletTransactions
                .map(
                    transactionRow
                )
                .join("");


    } catch (error) {

        console.error(
            "Wallet history error:",
            error
        );

        const list =
            document.getElementById(
                "walletHistoryList"
            );

        if (list) {

            list.innerHTML = `

                <div class="info-box">
                    Unable to load transactions.
                </div>

            `;

        }

    }

}


// ============================================================
// TRANSACTION ROW
// ============================================================

function transactionRow(
    tx
) {

    const amount =
        Number(
            tx.amount || 0
        );

    const positive =
        amount >= 0;

    const sign =
        positive
            ? "+"
            : "";

    const currency =
        tx.currency ===
        "quizbee_points"
            ? "Points"
            : tx.currency || "";


    const date =
        tx.created_at
            ? new Date(
                tx.created_at
            ).toLocaleString()
            : "";


    return `

        <div class="wallet-history-row">

            <div>

                <strong>
                    ${escapeHtml(
                        tx.description ||
                        tx.type ||
                        "Transaction"
                    )}
                </strong>

                <small>
                    ${escapeHtml(
                        date
                    )}
                </small>

            </div>


            <div
                class="${
                    positive
                        ? "wallet-positive"
                        : "wallet-negative"
                }"
            >

                ${sign}${amount}
                ${escapeHtml(
                    currency
                )}

                <small>
                    ${escapeHtml(
                        tx.status ||
                        ""
                    )}
                </small>

            </div>

        </div>

    `;

}


// ============================================================
// WITHDRAWAL HISTORY
// ============================================================

async function showWithdrawalHistory() {

    const container =
        document.getElementById(
            "gameContent"
        );

    if (!container) {
        return;
    }

    container.innerHTML = `

        <div class="wallet-page">

            <div class="page-heading">

                <button
                    class="back-btn"
                    onclick="withdrawPrize()"
                >
                    ‹
                </button>

                <h1>
                    📜 Withdrawals
                </h1>

            </div>


            <div id="withdrawalHistoryList">

                <div class="info-box">
                    Loading withdrawals...
                </div>

            </div>

        </div>

    `;


    try {

        const data =
            await api(
                "/api/wallet/withdrawals"
            );

        walletWithdrawals =
            data.withdrawals ||
            [];


        const list =
            document.getElementById(
                "withdrawalHistoryList"
            );


        if (
            !walletWithdrawals.length
        ) {

            list.innerHTML = `

                <div class="info-box">
                    No withdrawal requests yet.
                </div>

            `;

            return;

        }


        list.innerHTML =
            walletWithdrawals
                .map(
                    withdrawalRow
                )
                .join("");


    } catch (error) {

        console.error(
            "Withdrawal history error:",
            error
        );

    }

}


// ============================================================
// WITHDRAWAL ROW
// ============================================================

function withdrawalRow(
    withdrawal
) {

    const amount =
        Number(
            withdrawal.amount ||
            0
        );


    const method =
        withdrawal.method ===
        "nigerian_bank"
            ? "🇳🇬 Nigerian Bank"
            : "💵 USDT BEP20";


    const date =
        withdrawal.created_at
            ? new Date(
                withdrawal.created_at
            ).toLocaleString()
            : "";


    return `

        <div class="wallet-history-row">

            <div>

                <strong>
                    ${method}
                </strong>

                <small>
                    ${escapeHtml(
                        date
                    )}
                </small>

            </div>


            <div class="wallet-withdrawal-amount">

                $${amount.toFixed(2)}

                <small>
                    ${escapeHtml(
                        withdrawal.status ||
                        "pending"
                    )}
                </small>

            </div>

        </div>

    `;

      }
