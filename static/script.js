document.addEventListener("DOMContentLoaded", () => {
    // State Management
    const state = {
        game: "joker",
        theme: localStorage.getItem("theme") || "light"
    };

    // --- 1. THEME TOGGLE ---
    const htmlEl = document.documentElement;
    const themeBtn = document.getElementById("btn-theme-toggle");

    function applyTheme(theme) {
        state.theme = theme;
        htmlEl.setAttribute("data-bs-theme", theme);
        localStorage.setItem("theme", theme);
        if (themeBtn) {
            themeBtn.innerText = theme === "light" ? "🌙 Dark Mode" : "☀️ Light Mode";
        }
    }

    if (themeBtn) {
        themeBtn.addEventListener("click", () => {
            applyTheme(state.theme === "light" ? "dark" : "light");
        });
    }
    applyTheme(state.theme);

    // --- 2. GAME SWITCHING (Joker / Lotto) ---
    const navLinks = document.querySelectorAll(".navbar-nav .nav-link");
    navLinks.forEach(link => {
        link.addEventListener("click", async (e) => {
            e.preventDefault();
            
            navLinks.forEach(l => l.classList.remove("active"));
            link.classList.add("active");

            const newGame = link.getAttribute("data-game");
            if (newGame && newGame !== state.game) {
                state.game = newGame;
                
                // Reset Year Dropdown to "all"
                const yearSelect = document.getElementById("year-select");
                if (yearSelect) yearSelect.value = "all";

                await refreshAll();
            }
        });
    });

    // --- 3. YEAR SELECTOR EVENT ---
    const yearSelect = document.getElementById("year-select");
    if (yearSelect) {
        yearSelect.addEventListener("change", () => {
            fetchStats(yearSelect.value);
        });
    }

    // --- 4. API FETCHERS ---

    // A. Years Dropdown
    async function fetchYears() {
        const select = document.getElementById("year-select");
        if (!select) return;

        try {
            const res = await fetch(`/api/years?game=${state.game}`);
            if (!res.ok) throw new Error("Network response was not ok");
            const data = await res.json();

            // Clear existing options except 'all'
            select.innerHTML = '<option value="all">Συνολικά (Όλα τα έτη)</option>';

            if (data.status === "success" && Array.isArray(data.years)) {
                data.years.forEach(yr => {
                    const opt = document.createElement("option");
                    opt.value = yr;
                    opt.textContent = yr;
                    select.appendChild(opt);
                });
            }
        } catch (err) {
            console.error("Error fetching years:", err);
        }
    }

    // B. Repetitions Analysis
    async function fetchRepetitions() {
        const tbody = document.getElementById("rep-tbody");
        if (!tbody) return;

        try {
            const res = await fetch(`/api/stats/repetitions?game=${state.game}`);
            const data = await res.json();

            tbody.innerHTML = "";

            if (data.status !== "success" || !data.repetitions || data.repetitions.length === 0) {
                tbody.innerHTML = `<tr><td colspan="3" class="text-center text-muted">Δεν υπάρχουν διαθέσιμα δεδομένα.</td></tr>`;
                return;
            }

            data.repetitions.forEach(draw => {
                const tr = document.createElement("tr");
                const details = draw.details || {};
                let ballsHtml = "";

                draw.numbers.forEach(num => {
                    let catClass = "cat-absent";
                    if (details["1"] && details["1"].includes(num)) catClass = "cat-1";
                    if (details["2"] && details["2"].includes(num)) catClass = "cat-2";
                    if (details["3+"] && details["3+"].includes(num)) catClass = "cat-3plus";

                    ballsHtml += `<span class="ball ${catClass}">${num}</span> `;
                });

                tr.innerHTML = `
                    <td><strong>#${draw.draw_id}</strong></td>
                    <td>${draw.draw_date}</td>
                    <td>${ballsHtml}</td>
                `;
                tbody.appendChild(tr);
            });
        } catch (err) {
            console.error("Error fetching repetitions:", err);
            tbody.innerHTML = `<tr><td colspan="3" class="text-center text-danger">Σφάλμα κατά τη φόρτωση.</td></tr>`;
        }
    }

    // C. Frequencies
    async function fetchStats(year = "all") {
        try {
            const res = await fetch(`/api/stats?game=${state.game}&year=${year}`);
            const data = await res.json();

            if (data.status !== "success") return;

            // Update Total Draws Header
            const totalEl = document.getElementById("total-draws");
            if (totalEl) totalEl.innerText = data.total_draws || 0;

            // Render Main Frequencies Grid
            renderStatGrid("main-freq-grid", data.frequencies);

            // Render Joker Frequencies Grid (If applicable)
            const jokerContainer = document.getElementById("joker-freq-container");
            if (jokerContainer) {
                if (state.game === "joker") {
                    jokerContainer.style.display = "block";
                    renderStatGrid("joker-freq-grid", data.joker_frequencies);
                } else {
                    jokerContainer.style.display = "none";
                }
            }
        } catch (err) {
            console.error("Error fetching stats:", err);
        }
    }

    function renderStatGrid(containerId, freqData) {
        const container = document.getElementById(containerId);
        if (!container) return;
        container.innerHTML = "";

        if (!freqData) return;

        Object.keys(freqData).forEach(num => {
            const card = document.createElement("div");
            card.className = "stat-card";
            card.innerHTML = `
                <div class="stat-number">${num}</div>
                <div class="stat-count">${freqData[num]} φορές</div>
            `;
            container.appendChild(card);
        });
    }

    // --- 5. GENERATORS CONTROLLER ---

    // A. Random Generator
    const btnRandom = document.getElementById("btn-gen-random");
    if (btnRandom) {
        btnRandom.addEventListener("click", async () => {
            try {
                const res = await fetch(`/api/generate/random?game=${state.game}`);
                const data = await res.json();
                renderGeneratedResult(data, "Τυχαία Παραγωγή");
            } catch (err) {
                console.error("Random Generator Error:", err);
            }
        });
    }

    // B. Rules Generator
    const btnRules = document.getElementById("btn-gen-rules");
    if (btnRules) {
        btnRules.addEventListener("click", async () => {
            const ruleRows = document.querySelectorAll(".rule-row");
            const rules = [];

            ruleRows.forEach(row => {
                const countEl = row.querySelector(".rule-count");
                const minEl = row.querySelector(".rule-min-delay");
                const maxEl = row.querySelector(".rule-max-delay");

                const countVal = countEl ? parseInt(countEl.value) : 1;
                const minVal = minEl && minEl.value !== "" ? parseInt(minEl.value) : null;
                const maxVal = maxEl && maxEl.value !== "" ? parseInt(maxEl.value) : null;

                rules.push({
                    count: isNaN(countVal) ? 1 : countVal,
                    min_delay: isNaN(minVal) ? null : minVal,
                    max_delay: isNaN(maxVal) ? null : maxVal
                });
            });

            try {
                const res = await fetch("/api/generate/rules", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ game: state.game, rules: rules })
                });
                const data = await res.json();
                renderGeneratedResult(data, "Έξυπνη Παραγωγή με Κανόνες");
            } catch (err) {
                console.error("Rules Generator Error:", err);
            }
        });
    }

    function renderGeneratedResult(data, title) {
        const resBox = document.getElementById("gen-result");
        if (!resBox) return;

        if (!data || data.status !== "success" || !Array.isArray(data.numbers)) {
            resBox.innerHTML = `<span class="text-danger fw-bold">⚠️ Αποτυχία παραγωγής: ${data?.message || 'Σφάλμα διακομιστή'}</span>`;
            return;
        }

        const mainBalls = data.numbers.map(n => `<span class="ball">${n}</span>`).join(" ");
        const jokerBall = data.joker ? `<span class="ball joker-ball">${data.joker}</span>` : "";

        resBox.innerHTML = `
            <h6 class="text-muted mb-3">${title}</h6>
            <div class="d-flex justify-content-center align-items-center gap-1 flex-wrap">
                ${mainBalls} ${jokerBall}
            </div>
        `;
    }

    // --- 6. INITIALIZATION ---
    async function refreshAll() {
        await fetchYears();
        fetchRepetitions();
        const currentYearVal = yearSelect ? yearSelect.value : "all";
        fetchStats(currentYearVal);
    }

    // Start App
    refreshAll();
});
