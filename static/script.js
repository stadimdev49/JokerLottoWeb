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
            loadAllData();
        });
    });

    // Φόρτωση όλων των δεδομένων κατά την εναλλαγή ή έναρξη
    function loadAllData() {
        loadRepetitions();
        loadStats();
    }

    // 1. ΑΝΑΛΥΣΗ ΕΠΑΝΑΛΗΨΕΩΝ
    function loadRepetitions() {
        fetch(`/api/stats/repetitions?game=${currentGame}`)
            .then(res => res.json())
            .then(data => {
                const tbody = document.getElementById("rep-tbody");
                tbody.innerHTML = "";

                if (!data.repetitions || data.repetitions.length === 0) {
                    tbody.innerHTML = "<tr><td colspan='3' class='text-center text-muted'>Δεν βρέθηκαν δεδομένα.</td></tr>";
                    return;
                }

                data.repetitions.forEach(draw => {
                    const tr = document.createElement("tr");
                    const details = draw.details;
                    let ballsHtml = "";

                    draw.numbers.forEach(num => {
                        let catClass = "cat-absent";
                        if (details["1"].includes(num)) catClass = "cat-1";
                        if (details["2"].includes(num)) catClass = "cat-2";
                        if (details["3+"].includes(num)) catClass = "cat-3plus";

                        ballsHtml += `<span class="ball ${catClass}">${num}</span> `;
                    });

                    tr.innerHTML = `
                        <td><strong>#${draw.draw_id}</strong></td>
                        <td>${draw.draw_date}</td>
                        <td>${ballsHtml}</td>
                    `;
                    tbody.appendChild(tr);
                });
            })
            .catch(err => console.error("Repetitions error:", err));
    }

    // 2. ΣΥΧΝΟΤΗΤΕΣ ΑΡΙΘΜΩΝ
    function loadStats() {
        fetch(`/api/stats?game=${currentGame}&year=all`)
            .then(res => res.json())
            .then(data => {
                document.getElementById("total-draws").innerText = data.total_draws || 0;

                renderGrid("main-freq-grid", data.frequencies);

                const jokerContainer = document.getElementById("joker-freq-container");
                if (currentGame === "joker") {
                    jokerContainer.style.display = "block";
                    renderGrid("joker-freq-grid", data.joker_frequencies);
                } else {
                    jokerContainer.style.display = "none";
                }
            })
            .catch(err => console.error("Stats error:", err));
    }

    function renderGrid(containerId, dataObj) {
        const container = document.getElementById(containerId);
        container.innerHTML = "";
        if (!dataObj) return;

        Object.keys(dataObj).forEach(num => {
            const card = document.createElement("div");
            card.className = "stat-card";
            card.innerHTML = `
                <div class="stat-number">${num}</div>
                <div class="stat-count">${dataObj[num]} φορές</div>
            `;
            container.appendChild(card);
        });
    }

    // 3. ΓΕΝΝΗΤΡΙΕΣ ΑΡΙΘΜΩΝ
    // Α) Τυχαία Γεννήτρια
    document.getElementById("btn-gen-random").addEventListener("click", () => {
        fetch(`/api/generate/random?game=${currentGame}`)
            .then(res => res.json())
            .then(data => displayGenerated(data, "Τυχαία Παραγωγή"));
    });

    // Β) Γεννήτρια με Κανόνες
    document.getElementById("btn-gen-rules").addEventListener("click", () => {
        const ruleRows = document.querySelectorAll(".rule-row");
        const rules = [];

        ruleRows.forEach(row => {
            rules.push({
                count: row.querySelector(".rule-count").value,
                min_delay: row.querySelector(".rule-min-delay").value,
                max_delay: row.querySelector(".rule-max-delay").value
            });
        });

        fetch("/api/generate/rules", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ game: currentGame, rules: rules })
        })
            .then(res => res.json())
            .then(data => displayGenerated(data, "Παραγωγή με Κανόνες"));
    });

    function displayGenerated(data, modeTitle) {
        const resContainer = document.getElementById("gen-result");
        if (data.status !== "success") {
            resContainer.innerHTML = `<span class="text-danger">Σφάλμα κατά την παραγωγή δελτίου.</span>`;
            return;
        }

        const mainBalls = data.numbers.map(n => `<span class="ball">${n}</span>`).join(" ");
        const jokerBall = data.joker ? `<span class="ball joker-ball">${data.joker}</span>` : "";

        resContainer.innerHTML = `
            <h6 class="text-muted mb-3">Προτεινόμενο Δελτίο (${modeTitle})</h6>
            <div class="d-flex justify-content-center align-items-center gap-1">${mainBalls} ${jokerBall}</div>
        `;
    }

    // Αρχική Φόρτωση
    loadAllData();
});
