// TxPeek Mini App

const tg = window.Telegram?.WebApp;
let userId = null;

document.addEventListener("DOMContentLoaded", () => {
    if (tg) {
        tg.ready();
        tg.expand();

        userId = tg.initDataUnsafe?.user?.id;
        if (userId) {
            loadProfile(userId);
        }
    }

    loadLeaderboard();
    loadStats();
});

async function loadProfile(telegramId) {
    try {
        const resp = await fetch(`/webapp/api/profile/${telegramId}`);
        const data = await resp.json();

        if (data.error) return;

        const u = data.user;
        document.getElementById("username").textContent = u.first_name || u.username || "Детектив";
        document.getElementById("level-badge").textContent = `Ур. ${u.level} — ${u.level_name}`;
        document.getElementById("level").textContent = u.level;
        document.getElementById("checks-count").textContent = u.checks_count;
        document.getElementById("streak").textContent = u.streak;

        const totalXp = u.xp + u.xp_to_next;
        const pct = totalXp > 0 ? (u.xp / totalXp) * 100 : 0;
        document.getElementById("xp-fill").style.width = `${pct}%`;
        document.getElementById("xp-label").textContent = `${u.xp} / ${totalXp} XP`;

        // Render recent checks
        const container = document.getElementById("recent-checks");
        if (data.recent_checks && data.recent_checks.length > 0) {
            container.innerHTML = data.recent_checks
                .map(
                    (c) => `
                <div class="check-item">
                    <div>
                        <span class="check-address">${c.address}</span>
                        <span class="check-chain">${c.chain}</span>
                    </div>
                    <div>
                        <span class="risk-dot ${c.risk_level}"></span>
                        ${Math.round(c.risk_score)}
                    </div>
                </div>
            `
                )
                .join("");
        }
    } catch (e) {
        console.error("Failed to load profile:", e);
    }
}

async function loadLeaderboard() {
    try {
        const resp = await fetch("/webapp/api/leaderboard");
        const data = await resp.json();

        const container = document.getElementById("leaderboard");
        const medals = { 1: "🥇", 2: "🥈", 3: "🥉" };

        if (data.leaderboard && data.leaderboard.length > 0) {
            container.innerHTML = data.leaderboard
                .map(
                    (u) => `
                <div class="lb-item">
                    <span class="lb-rank">${medals[u.rank] || u.rank}</span>
                    <span class="lb-name">${u.username}</span>
                    <span class="lb-xp">${u.xp} XP</span>
                </div>
            `
                )
                .join("");
        } else {
            container.innerHTML = '<p class="muted">Пока пусто — будь первым!</p>';
        }
    } catch (e) {
        console.error("Failed to load leaderboard:", e);
    }
}

async function loadStats() {
    try {
        const resp = await fetch("/webapp/api/stats");
        const data = await resp.json();

        document.getElementById("global-users").textContent = data.total_users;
        document.getElementById("global-checks").textContent = data.total_checks;
        document.getElementById("global-risky").textContent = data.risky_found;
    } catch (e) {
        console.error("Failed to load stats:", e);
    }
}

async function checkAddress() {
    const input = document.getElementById("address-input");
    const resultDiv = document.getElementById("check-result");
    const address = input.value.trim();

    if (!address) return;

    resultDiv.className = "";
    resultDiv.textContent = "🔍 Проверяю...";

    // Send the address back to the bot via Telegram
    if (tg) {
        tg.sendData(JSON.stringify({ action: "check", address: address }));
        resultDiv.textContent = "📨 Отправлено боту — ответ придёт в чат!";
    } else {
        resultDiv.textContent = "⚠️ Откройте через Telegram для проверки";
    }
}
