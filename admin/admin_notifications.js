/* ============================================================
   QUIZBEE ADMIN NOTIFICATIONS
============================================================ */

(function () {

    function h(value) {

        if (
            typeof escapeHtml ===
            "function"
        ) {
            return escapeHtml(
                value ?? ""
            );
        }

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


    /* ========================================================
       PAGE
    ======================================================== */

    function createPage() {

        if (
            document.getElementById(
                "adminNotificationsPage"
            )
        ) {
            return;
        }

        const main =
            document.querySelector(
                "main"
            );

        if (!main) {
            return;
        }

        const page =
            document.createElement(
                "section"
            );

        page.id =
            "adminNotificationsPage";

        page.className =
            "page";

        page.innerHTML = `

            <div class="page-heading">

                <h1>
                    🔔 Notifications
                </h1>

            </div>


            <div class="panel">

                <div class="panel-header">

                    <h2>
                        📢 Send Announcement
                    </h2>

                </div>


                <label>
                    Title
                </label>

                <input
                    id="adminNotificationTitle"
                    placeholder="Announcement title"
                >


                <label>
                    Message
                </label>

                <textarea
                    id="adminNotificationMessage"
                    rows="6"
                    placeholder="Write your notification..."
                ></textarea>


                <label>
                    Notification Type
                </label>

                <select
                    id="adminNotificationType"
                >

                    <option value="announcement">
                        📢 Announcement
                    </option>

                    <option value="competition">
                        🏆 Competition
                    </option>

                    <option value="reward">
                        🎁 Reward
                    </option>

                    <option value="raffle">
                        🎟️ Raffle
                    </option>

                    <option value="daily">
                        💵 Daily Earning
                    </option>

                    <option value="maintenance">
                        🚧 Maintenance
                    </option>

                    <option value="warning">
                        ⚠️ Warning
                    </option>

                    <option value="general">
                        🔔 General
                    </option>

                </select>


                <label>
                    Action URL
                    <small>
                        optional
                    </small>
                </label>

                <input
                    id="adminNotificationActionUrl"
                    placeholder="https://..."
                >


                <label>
                    Button Text
                    <small>
                        optional
                    </small>
                </label>

                <input
                    id="adminNotificationButtonText"
                    placeholder="Open QuizBee"
                >


                <label class="checkbox-row">

                    <input
                        id="adminNotificationTelegram"
                        type="checkbox"
                        checked
                    >

                    Send through Telegram too

                </label>


                <button
                    class="primary-btn full"
                    onclick="sendAdminNotificationBroadcast()"
                >
                    📢 SEND TO ALL USERS
                </button>

            </div>


            <div class="panel">

                <div class="panel-header">

                    <h2>
                        👤 Send to One User
                    </h2>

                </div>


                <label>
                    Telegram User ID
                </label>

                <input
                    id="adminSingleNotificationUser"
                    placeholder="Telegram ID"
                >


                <label>
                    Title
                </label>

                <input
                    id="adminSingleNotificationTitle"
                    placeholder="Notification title"
                >


                <label>
                    Message
                </label>

                <textarea
                    id="adminSingleNotificationMessage"
                    rows="5"
                    placeholder="Message..."
                ></textarea>


                <label class="checkbox-row">

                    <input
                        id="adminSingleNotificationTelegram"
                        type="checkbox"
                        checked
                    >

                    Send through Telegram too

                </label>


                <button
                    class="primary-btn full"
                    onclick="sendAdminNotificationUser()"
                >
                    🔔 SEND TO USER
                </button>

            </div>

        `;

        main.appendChild(page);
    }


    /* ========================================================
       NAV BUTTON
    ======================================================== */

    function createNavButton() {

        const nav =
            document.querySelector(
                ".bottom-nav"
            );

        if (!nav) {
            return;
        }

        if (
            document.getElementById(
                "adminNotificationsNav"
            )
        ) {
            return;
        }

        const button =
            document.createElement(
                "button"
            );

        button.id =
            "adminNotificationsNav";

        button.className =
            "nav-item";

        button.innerHTML =
            `<span>🔔</span>Notifications`;

        button.onclick =
            function () {

                showAdminNotifications();

            };

        /*
         * Put it before Settings.
         */
        const settings =
            Array.from(
                nav.querySelectorAll(
                    ".nav-item"
                )
            ).find(
                item =>
                    item.textContent
                        .includes(
                            "Settings"
                        )
            );

        if (settings) {

            nav.insertBefore(
                button,
                settings
            );

        } else {

            nav.appendChild(
                button
            );

        }
    }


    /* ========================================================
       SHOW PAGE
    ======================================================== */

    window.showAdminNotifications =
        function () {

            createPage();

            document
                .querySelectorAll(
                    ".page"
                )
                .forEach(
                    page =>
                        page.classList.remove(
                            "active"
                        )
                );

            const page =
                document.getElementById(
                    "adminNotificationsPage"
                );

            if (page) {

                page.classList.add(
                    "active"
                );

            }

            document
                .querySelectorAll(
                    ".nav-item"
                )
                .forEach(
                    item =>
                        item.classList.remove(
                            "active"
                        )
                );

            const nav =
                document.getElementById(
                    "adminNotificationsNav"
                );

            if (nav) {

                nav.classList.add(
                    "active"
                );

            }

        };


    /* ========================================================
       BROADCAST
    ======================================================== */

    window.sendAdminNotificationBroadcast =
        async function () {

            const title =
                document.getElementById(
                    "adminNotificationTitle"
                ).value.trim();

            const message =
                document.getElementById(
                    "adminNotificationMessage"
                ).value.trim();

            const type =
                document.getElementById(
                    "adminNotificationType"
                ).value;

            const actionUrl =
                document.getElementById(
                    "adminNotificationActionUrl"
                ).value.trim();

            const buttonText =
                document.getElementById(
                    "adminNotificationButtonText"
                ).value.trim();

            const sendTelegram =
                document.getElementById(
                    "adminNotificationTelegram"
                ).checked;


            if (!title) {

                showToast(
                    "Enter a notification title."
                );

                return;
            }

            if (!message) {

                showToast(
                    "Enter a notification message."
                );

                return;
            }


            if (
                !confirm(
                    "Send this notification to ALL users?"
                )
            ) {
                return;
            }


            try {

                const data =
                    await api(
                        "/api/notifications/admin/broadcast",
                        {
                            method: "POST",
                            body:
                                JSON.stringify({
                                    title,
                                    message,
                                    type,
                                    action_url:
                                        actionUrl,
                                    button_text:
                                        buttonText,
                                    send_telegram:
                                        sendTelegram
                                })
                        }
                    );

                showToast(
                    `Sent. Created: ${
                        data.created || 0
                    }`
                );

                document.getElementById(
                    "adminNotificationTitle"
                ).value = "";

                document.getElementById(
                    "adminNotificationMessage"
                ).value = "";

                document.getElementById(
                    "adminNotificationActionUrl"
                ).value = "";

                document.getElementById(
                    "adminNotificationButtonText"
                ).value = "";

            } catch (error) {

                showToast(
                    error.message
                );

            }
        };


    /* ========================================================
       SINGLE USER
    ======================================================== */

    window.sendAdminNotificationUser =
        async function () {

            const userId =
                document.getElementById(
                    "adminSingleNotificationUser"
                ).value.trim();

            const title =
                document.getElementById(
                    "adminSingleNotificationTitle"
                ).value.trim();

            const message =
                document.getElementById(
                    "adminSingleNotificationMessage"
                ).value.trim();

            const sendTelegram =
                document.getElementById(
                    "adminSingleNotificationTelegram"
                ).checked;


            if (!userId) {

                showToast(
                    "Enter the Telegram user ID."
                );

                return;
            }

            if (!title) {

                showToast(
                    "Enter a title."
                );

                return;
            }

            if (!message) {

                showToast(
                    "Enter a message."
                );

                return;
            }


            try {

                await api(
                    "/api/notifications/admin/user",
                    {
                        method: "POST",
                        body:
                            JSON.stringify({
                                user_id:
                                    userId,
                                title,
                                message,
                                type:
                                    "general",
                                send_telegram:
                                    sendTelegram
                            })
                    }
                );

                showToast(
                    "Notification sent."
                );

                document.getElementById(
                    "adminSingleNotificationUser"
                ).value = "";

                document.getElementById(
                    "adminSingleNotificationTitle"
                ).value = "";

                document.getElementById(
                    "adminSingleNotificationMessage"
                ).value = "";

            } catch (error) {

                showToast(
                    error.message
                );

            }

        };


    /* ========================================================
       INIT
    ======================================================== */

    function init() {

        createPage();

        createNavButton();

    }


    document.addEventListener(
        "DOMContentLoaded",
        init
    );

})();
