// TxPeek Mini App
// Works both as Telegram Mini App (with backend) and standalone on GitHub Pages (demo mode)

const tg = window.Telegram?.WebApp;

// API base — set to your backend URL when deployed, empty = demo mode
const API_BASE = "";

let userId = null;
let isDemoMode = true;

// --- Init ---

document.addEventListener("DOMContentLoaded", () => {
    if (tg) {
        tg.ready();
        tg.expand();
        tg.setHeaderColor("#0f0f1a");
        tg.setBackgroundColor("#0f0f1a");

        userId = tg.initDataUnsafe?.user?.id;
        const user = tg.initDataUnsafe?.user;

        if (user) {
            document.getElementById("username").textContent =
                user.first_name || user.username || "Детектив";
        }
    }

    // Try loading from real API, fall back to demo
    if (API_BASE && userId) {
        isDemoMode = false;
        loadProfile(userId);
        loadLeaderboard();
        loadStats();
    } else {
        showDemoData();
    }

    document.getElementById("check-btn").addEventListener("click", checkAddress);
    document.getElementById("address-input").addEventListener("keydown", (e) => {
        if (e.key === "Enter") checkAddress();
    });
});

// --- Demo mode ---

function showDemoData() {
    // Profile
    document.getElementById("xp-fill").style.width = "35%";
    document.getElementById("xp-label").textContent = "35 / 100 XP";

    // Demo leaderboard
    const leaderboard = [
        { rank: 1, name: "CryptoSherlock", level: "Детектив", xp: 2450 },
        { rank: 2, name: "BlockHunter", level: "Аналитик", xp: 1800 },
        { rank: 3, name: "ChainWatcher", level: "Следопыт", xp: 950 },
    ];

    const medals = { 1: "1", 2: "2", 3: "3" };
    const container = document.getElementById("leaderboard");
    container.innerHTML = leaderboard
        .map(
            (u) => `
        <div class="lb-item">
            <span class="lb-rank">${medals[u.rank]}</span>
            <div class="lb-info">
                <div class="lb-name">${u.name}</div>
                <div class="lb-level">${u.level}</div>
            </div>
            <span class="lb-xp">${u.xp} XP</span>
        </div>
    `
        )
        .join("");

    // Demo stats
    document.getElementById("global-users").textContent = "—";
    document.getElementById("global-checks").textContent = "—";
    document.getElementById("global-risky").textContent = "—";
}

// --- Real API calls ---

async function loadProfile(telegramId) {
    try {
        const resp = await fetch(`${API_BASE}/webapp/api/profile/${telegramId}`);
        const data = await resp.json();
        if (data.error) return;

        const u = data.user;
        document.getElementById("username").textContent =
            u.first_name || u.username || "Детектив";
        document.getElementById("level-badge").textContent =
            `Ур. ${u.level} — ${u.level_name}`;
        document.getElementById("level").textContent = u.level;
        document.getElementById("checks-count").textContent = u.checks_count;
        document.getElementById("streak").textContent = u.streak;

        const totalXp = u.xp + u.xp_to_next;
        const pct = totalXp > 0 ? (u.xp / totalXp) * 100 : 0;
        document.getElementById("xp-fill").style.width = `${pct}%`;
        document.getElementById("xp-label").textContent = `${u.xp} / ${totalXp} XP`;

        renderRecentChecks(data.recent_checks);
    } catch (e) {
        console.log("API unavailable, running in demo mode");
    }
}

async function loadLeaderboard() {
    try {
        const resp = await fetch(`${API_BASE}/webapp/api/leaderboard`);
        const data = await resp.json();

        const container = document.getElementById("leaderboard");
        const medals = { 1: "1", 2: "2", 3: "3" };

        if (data.leaderboard && data.leaderboard.length > 0) {
            container.innerHTML = data.leaderboard
                .map(
                    (u) => `
                <div class="lb-item">
                    <span class="lb-rank">${medals[u.rank] || u.rank}</span>
                    <div class="lb-info">
                        <div class="lb-name">${u.username}</div>
                        <div class="lb-level">${u.level_name}</div>
                    </div>
                    <span class="lb-xp">${u.xp} XP</span>
                </div>
            `
                )
                .join("");
        }
    } catch (e) {
        console.log("Leaderboard API unavailable");
    }
}

async function loadStats() {
    try {
        const resp = await fetch(`${API_BASE}/webapp/api/stats`);
        const data = await resp.json();

        document.getElementById("global-users").textContent = data.total_users;
        document.getElementById("global-checks").textContent = data.total_checks;
        document.getElementById("global-risky").textContent = data.risky_found;
    } catch (e) {
        console.log("Stats API unavailable");
    }
}

function renderRecentChecks(checks) {
    const container = document.getElementById("recent-checks");
    if (!checks || checks.length === 0) return;

    container.innerHTML = checks
        .map(
            (c) => `
        <div class="check-item">
            <div>
                <div class="check-address">${c.address}</div>
                <div class="check-chain">${c.chain}</div>
            </div>
            <div class="check-risk">
                <span class="risk-dot ${c.risk_level}"></span>
                ${Math.round(c.risk_score)}
            </div>
        </div>
    `
        )
        .join("");
}

// --- Address check ---

const ADDRESS_PATTERNS = {
    ethereum: /^0x[0-9a-fA-F]{40}$/,
    bitcoin: /^(1|3)[a-km-zA-HJ-NP-Z1-9]{25,34}$|^bc1[a-z0-9]{39,59}$/,
    tron: /^T[a-zA-Z0-9]{33}$/,
    solana: /^[1-9A-HJ-NP-Za-km-z]{32,44}$/,
};

function detectChain(address) {
    for (const [chain, pattern] of Object.entries(ADDRESS_PATTERNS)) {
        if (pattern.test(address)) return chain;
    }
    return null;
}

function checkAddress() {
    const input = document.getElementById("address-input");
    const resultDiv = document.getElementById("check-result");
    const address = input.value.trim();

    if (!address) return;

    resultDiv.classList.remove("hidden");

    const chain = detectChain(address);

    if (!chain) {
        resultDiv.className = "risk-medium";
        resultDiv.innerHTML = `
            <strong>Не удалось определить сеть</strong><br>
            Проверь правильность адреса. Поддерживаемые сети: Ethereum, Bitcoin, Solana, Tron.
        `;
        return;
    }

    // If in Telegram — send to bot for full analysis
    if (tg) {
        tg.sendData(JSON.stringify({ action: "check", address, chain }));
        resultDiv.className = "risk-low";
        resultDiv.innerHTML = `
            <strong>Отправлено боту</strong><br>
            Сеть: ${chain}<br>
            Полный отчёт придёт в чат. Жди пару секунд...
        `;
        return;
    }

    // Standalone demo — show detected chain
    const shortAddr = address.length > 16
        ? `${address.slice(0, 8)}...${address.slice(-6)}`
        : address;

    resultDiv.className = "risk-low";
    resultDiv.innerHTML = `
        <strong>Адрес распознан</strong><br>
        <span style="color:var(--text-muted)">Сеть:</span> ${chain}<br>
        <span style="color:var(--text-muted)">Адрес:</span> <code>${shortAddr}</code><br><br>
        Для полного анализа откройте приложение через <a href="https://t.me/txpeek_bot" style="color:var(--accent)">@txpeek_bot</a>
    `;
}
