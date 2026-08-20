document.addEventListener("DOMContentLoaded", function () {
    let currentGame = "joker";

    // --- DARK MODE CONTROLLER ---
    const themeBtn = document.getElementById("btn-theme-toggle");
    const htmlEl = document.documentElement;

    const savedTheme = localStorage.getItem("theme") || "light";
    setTheme(savedTheme);

    themeBtn.addEventListener("click", () => {
        const newTheme = htmlEl.getAttribute("data-bs-theme") === "light" ? "dark" : "light";
        setTheme(newTheme);
    });

    function setTheme(theme) {
        htmlEl.setAttribute("data-bs-theme", theme);
        localStorage.setItem("theme", theme);
        themeBtn.innerText = theme === "light" ? "🌙 Dark Mode" : "☀️ Light Mode";
    }

    // --- GAME SWITCHER ---
    document.querySelectorAll(".navbar-nav .nav-link").forEach(link => {
        link.addEventListener("click", function (e) {
            e.preventDefault();
            document.querySelectorAll(".navbar-nav .nav-link").forEach(l => l.classList.remove("active"));
            this.classList.add("active");
            currentGame = this.getAttribute("data-game");
            loadAnalysisData();
        });
    });

    // --- GENERATOR FORM TOGGLES ---
    const genModeSelect = document.getElementById("gen-mode");
    genModeSelect.addEventListener("change", function () {
        const isRules = this.value === "rules";
        document.querySelectorAll(".rules-option").forEach(el => {
            el.classList.toggle("d-none", !isRules);
        });
    });

    // --- LOAD ANALYSIS DATA ---
    function loadAnalysisData() {
        fetch(`/api/draws/analysis?game=${currentGame}`)
            .then(res => res.json())
            .then(data => {
                const tbody = document.getElementById("analysis-tbody");
                tbody.innerHTML = "";

                if (!data.draws || data.draws.length === 0) {
                    tbody.innerHTML = "<tr><td colspan='4' class='text-center text-muted'>Δεν βρέθηκαν δεδομένα.</td></tr>";
                    return;
                }

                data.draws.forEach(draw => {
                    const tr = document.createElement("tr");

                    const ballsHtml = draw.numbers_analysis.map(item => {
                        let catClass = "cat-absent";
                        if (item.category === "1_appear") catClass = "cat-1";
                        if (item.category === "2_appears") catClass = "cat-2";
                        if (item.category === "3_plus_appears") catClass = "cat-3plus";

                        return `<span class="ball ${catClass}" title="${item.prev_appearances} εμφανίσεις στις προηγούμενες 10">${item.number}</span>`;
                    }).join(" ");

                    const jokerHtml = draw.joker ? `<span class="ball joker-ball">${draw.joker}</span>` : "-";

                    tr.innerHTML = `
                        <td><strong>#${draw.draw_id}</strong></td>
                        <td>${draw.draw_date}</td>
                        <td>${ballsHtml}</td>
                        <td>${jokerHtml}</td>
                    `;
                    tbody.appendChild(tr);
                });
            })
            .catch(err => console.error("Error loading analysis:", err));
    }

    // --- GENERATE TICKET ---
    document.getElementById("btn-generate").addEventListener("click", function () {
        const mode = genModeSelect.value;
        const lookback = document.getElementById("gen-lookback").value;
        const ruleType = document.getElementById("gen-rule-type").value;

        fetch(`/api/generate?game=${currentGame}&mode=${mode}&lookback=${lookback}&rule_type=${ruleType}`)
            .then(res => res.json())
            .then(data => {
                const resContainer = document.getElementById("gen-result");
                const mainBalls = data.numbers.map(n => `<span class="ball">${n}</span>`).join(" ");
                const jokerBall = data.joker ? `<span class="ball joker-ball">${data.joker}</span>` : "";

                resContainer.innerHTML = `
                    <h5 class="text-muted mb-3">Προτεινόμενο Δελτίο (${data.mode === 'rules' ? 'Με Κανόνες' : 'Τυχαίο'})</h5>
                    <div class="mb-2">${mainBalls} ${jokerBall}</div>
                `;
            });
    });

    // Initial Load
    loadAnalysisData();
});
