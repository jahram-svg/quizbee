/* ============================================================
   QUIZBEE NOTIFICATIONS
============================================================ */

let notificationItems = [];
let notificationUnreadCount = 0;


/* ============================================================
   NOTIFICATION PAGE
============================================================ */

function createNotificationPage() {

    if (
        document.getElementById(
            "notificationsPage"
        )
    ) {
        return;
    }

    const main =
        document.querySelector("main");

    if (!main) {
        return;
    }

    const page =
        document.createElement("section");

    page.id =
        "notificationsPage";

    page.className =
        "page";

    page.innerHTML = `

        <div class="page-heading">

            <button
                class="back-btn"
                onclick="goHome()"
            >
                ‹
            </button>

            <h1>
                🔔 Notifications
            </h1>

        </div>


        <div
            class="notification-actions"
            id="notificationActions"
        >
            <button
                class="secondary-btn"
                onclick="markAllNotificationsRead()"
            >
                ✓ Mark all as read
            </button>
        </div>


        <div
            id="notificationsList"
            class="notifications-list"
        >

            <div class="info-box">
                Loading notifications...
            </div>

        </div>

    `;

    main.appendChild(page);
}


/* ============================================================
   NOTIFICATION BELL
============================================================ */

function createNotificationBell() {

    if (
        document.getElementById(
            "notificationBell"
        )
    ) {
        return;
    }

    const topbar =
        document.querySelector(
            ".topbar"
        );

    if (!topbar) {
        return;
    }

    const button =
        document.createElement("button");

    button.id =
        "notificationBell";

    button.className =
        "notification-bell";

    button.onclick =
        function () {

            showPage(
                "notifications"
            );

            loadNotifications();

        };

    button.innerHTML = `

        <span class="notification-bell-icon">
            🔔
        </span>

        <span
            id="notificationBadge"
            class="notification-badge hidden"
        >
            0
        </span>

    `;

    topbar.appendChild(button);
}


/* ============================================================
   LOAD NOTIFICATIONS
============================================================ */

async function loadNotifications() {

    const list =
        document.getElementById(
            "notificationsList"
        );

    if (!list) {
        return;
    }

    list.innerHTML = `
        <div class="info-box">
            Loading notifications...
        </div>
    `;

    try {

        const data =
            await api(
                "/api/notifications"
            );

        notificationItems =
            data.notifications || [];

        notificationUnreadCount =
            Number(
                data.unread_count || 0
            );

        updateNotificationBadge();

        renderNotifications();

    } catch (error) {

        console.error(
            "Notification load error:",
            error
        );

        list.innerHTML = `

            <div class="info-box">

                ⚠️ Unable to load notifications.

                <br><br>

                <button
                    class="primary-btn"
                    onclick="loadNotifications()"
                >
                    Try Again
                </button>

            </div>

        `;

    }
}


/* ============================================================
   BADGE
============================================================ */

function updateNotificationBadge() {

    const badge =
        document.getElementById(
            "notificationBadge"
        );

    if (!badge) {
        return;
    }

    const count =
        Number(
            notificationUnreadCount || 0
        );

    if (count <= 0) {

        badge.classList.add(
            "hidden"
        );

        badge.textContent =
            "0";

        return;
    }

    badge.classList.remove(
        "hidden"
    );

    badge.textContent =
        count > 99
            ? "99+"
            : String(count);
}


/* ============================================================
   RENDER
============================================================ */

function renderNotifications() {

    const list =
        document.getElementById(
            "notificationsList"
        );

    if (!list) {
        return;
    }

    if (!notificationItems.length) {

        list.innerHTML = `

            <div class="notification-empty">

                <div class="notification-empty-icon">
                    🔔
                </div>

                <h2>
                    No notifications
                </h2>

                <p>
                    You're all caught up.
                </p>

            </div>

        `;

        return;
    }

    list.innerHTML =
        notificationItems
            .map(
                renderNotification
            )
            .join("");
}


/* ============================================================
   SINGLE NOTIFICATION
============================================================ */

function renderNotification(
    notification
) {

    const id =
        escapeAttribute(
            notification.id || ""
        );

    const title =
        escapeHtml(
            notification.title ||
            "Notification"
        );

    const message =
        escapeHtml(
            notification.message ||
            ""
        );

    const type =
        escapeHtml(
            notification.type ||
            "general"
        );

    const created =
        formatNotificationDate(
            notification.created_at
        );

    const unread =
        notification.read !== true;

    const actionUrl =
        notification.action_url || "";

    const buttonText =
        notification.button_text || "";

    return `

        <div
            class="
                notification-card
                ${unread ? "unread" : ""}
            "
            data-notification-id="${id}"
            onclick="openNotification('${id}')"
        >

            <div class="notification-icon">
                ${getNotificationIcon(type)}
            </div>


            <div class="notification-content">

                <div class="notification-title-row">

                    <strong>
                        ${title}
                    </strong>

                    ${
                        unread
                        ? `
                            <span class="notification-dot">
                            </span>
                        `
                        : ""
                    }

                </div>


                <p>
                    ${message}
                </p>


                <small>
                    ${created}
                </small>


                ${
                    actionUrl && buttonText
                    ? `
                        <button
                            class="notification-action-btn"
                            onclick="
                                event.stopPropagation();
                                openNotificationAction(
                                    '${escapeJs(actionUrl)}',
                                    '${escapeJs(buttonText)}',
                                    '${id}'
                                )
                            "
                        >
                            ${escapeHtml(buttonText)}
                        </button>
                    `
                    : ""
                }

            </div>

        </div>

    `;
}


/* ============================================================
   OPEN NOTIFICATION
============================================================ */

async function openNotification(
    notificationId
) {

    const item =
        notificationItems.find(
            notification =>
                notification.id ===
                notificationId
        );

    if (!item) {
        return;
    }

    if (!item.read) {

        try {

            await api(
                `/api/notifications/${encodeURIComponent(
                    notificationId
                )}/read`,
                {
                    method: "POST",
                    body: JSON.stringify({})
                }
            );

            item.read = true;

            notificationUnreadCount =
                Math.max(
                    0,
                    notificationUnreadCount - 1
                );

            updateNotificationBadge();

            renderNotifications();

        } catch (error) {

            console.error(
                "Mark notification read error:",
                error
            );

        }

    }

}


/* ============================================================
   ACTION
============================================================ */

async function openNotificationAction(
    url,
    buttonText,
    notificationId
) {

    await openNotification(
        notificationId
    );

    if (!url) {
        return;
    }

    try {

        if (
            typeof tg !== "undefined" &&
            tg &&
            typeof tg.openLink ===
                "function"
        ) {

            tg.openLink(url);

        } else {

            window.open(
                url,
                "_blank"
            );

        }

    } catch {

        window.open(
            url,
            "_blank"
        );

    }
}


/* ============================================================
   MARK ALL READ
============================================================ */

async function markAllNotificationsRead() {

    try {

        const data =
            await api(
                "/api/notifications/read-all",
                {
                    method: "POST",
                    body: JSON.stringify({})
                }
            );

        notificationItems =
            notificationItems.map(
                item => ({
                    ...item,
                    read: true
                })
            );

        notificationUnreadCount =
            0;

        updateNotificationBadge();

        renderNotifications();

        showToast(
            data.marked_read
                ? "All notifications marked as read."
                : "No unread notifications."
        );

    } catch (error) {

        showToast(
            error.message ||
            "Unable to mark notifications as read."
        );

    }
}


/* ============================================================
   ICONS
============================================================ */

function getNotificationIcon(
    type
) {

    const icons = {

        competition:
            "🏆",

        round:
            "🎮",

        stage:
            "⚡",

        elimination:
            "❌",

        advancement:
            "🎉",

        winner:
            "🏆",

        prize:
            "💰",

        reward:
            "🎁",

        raffle:
            "🎟️",

        daily:
            "💵",

        announcement:
            "📢",

        maintenance:
            "🚧",

        warning:
            "⚠️",

        general:
            "🔔"

    };

    return (
        icons[type] ||
        icons.general
    );
}


/* ============================================================
   DATE
============================================================ */

function formatNotificationDate(
    value
) {

    if (!value) {
        return "";
    }

    try {

        const date =
            new Date(value);

        if (
            Number.isNaN(
                date.getTime()
            )
        ) {
            return "";
        }

        return date.toLocaleString();

    } catch {

        return "";
    }
}


/* ============================================================
   INITIALIZE
============================================================ */

function initNotifications() {

    createNotificationPage();

    createNotificationBell();

    /*
     * Load the unread count immediately
     * after the main app has authenticated.
     */
    if (typeof getInitData === "function") {

        if (getInitData()) {

            loadNotifications()
                .catch(
                    () => {}
                );

        }

    }

}


document.addEventListener(
    "DOMContentLoaded",
    initNotifications
);
