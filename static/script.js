document.addEventListener("DOMContentLoaded", function () {
    let currentGame = "joker";

    // Tab Switching
    const tabs = document.querySelectorAll(".nav-link");
    tabs.forEach(tab => {
        tab.addEventListener("click", function (e) {
            e.preventDefault();
            tabs.forEach(t => t.classList.remove("active"));
            this.classList.add("active");

            currentGame = this.getAttribute("data-game") || "joker";
            loadAllData();
        });
    });

    // Initial Load
    loadAllData();

    function loadAllData() {
        loadStats();
        loadDraws();
        loadRepetitions();
    }

    // ----------------------------------------------------
    // 1. STATS & FREQUENCIES
    // ----------------------------------------------------
    function loadStats() {
        fetch(`/api/stats?game=${currentGame}&year=all`)
            .then(response => {
                if (!response.ok) throw new Error("Network response was not ok");
                return response.json();
            })
            .then(data => {
                console.log("Stats API Data:", data);

                // Ενημέρωση Συνολικών Κληρώσεων
                const totalDrawsEl = document.getElementById("total-draws");
                if (totalDrawsEl) {
                    totalDrawsEl.innerText = data.total_draws || 0;
                }

                // Ασφαλής ανάκτηση αντικειμένων για αριθμούς & τζόκερ
                const mainNumbers = data.numbers || data.numbers_frequency || {};
                const jokerNumbers = data.jokers || data.joker_frequency || {};

                // Render Grids
                renderGrid("main-numbers-grid", mainNumbers);
                
                const jokerContainer = document.getElementById("joker-grid-container");
                if (currentGame === "joker") {
                    if (jokerContainer) jokerContainer.style.display = "block";
                    renderGrid("joker-numbers-grid", jokerNumbers);
                } else {
                    if (jokerContainer) jokerContainer.style.display = "none";
                }
            })
            .catch(error => {
                console.error("Σφάλμα κατά τη φόρτωση των στατιστικών:", error);
            });
    }

    // ----------------------------------------------------
    // SAFE RENDER GRID (Δεν κρασάρει αν το obj είναι undefined)
    // ----------------------------------------------------
    function renderGrid(containerId, dataObj) {
        const container = document.getElementById(containerId);
        if (!container) return;

        container.innerHTML = "";

        // Έλεγχος αν το dataObj είναι έγκυρο αντικείμενο
        if (!dataObj || typeof dataObj !== "object" || Object.keys(dataObj).length === 0) {
            container.innerHTML = "<p class='text-muted'>Δεν υπάρχουν διαθέσιμα δεδομένα.</p>";
            return;
        }

        // Ταξινόμηση βάσει αριθμού (1, 2, 3...)
        const sortedKeys = Object.keys(dataObj).map(Number).sort((a, b) => a - b);

        sortedKeys.forEach(num => {
            const count = dataObj[num];
            const card = document.createElement("div");
            card.className = "stat-card";
            card.innerHTML = `
                <div class="stat-number">${num}</div>
                <div class="stat-count">${count} φορές</div>
            `;
            container.appendChild(card);
        });
    }

    // ----------------------------------------------------
    // 2. RECENT DRAWS TABLE
    // ----------------------------------------------------
    function loadDraws() {
        fetch(`/api/draws?game=${currentGame}&limit=20`)
            .then(res => res.json())
            .then(data => {
                const tbody = document.getElementById("draws-tbody");
                if (!tbody) return;

                tbody.innerHTML = "";
                const draws = data.draws || [];

                draws.forEach(draw => {
                    const tr = document.createElement("tr");
                    
                    const mainBalls = draw.numbers.map(n => `<span class="ball">${n}</span>`).join(" ");
                    const jokerBall = draw.joker ? `<span class="ball joker-ball">${draw.joker}</span>` : "-";

                    tr.innerHTML = `
                        <td><strong>#${draw.draw_id}</strong></td>
                        <td>${draw.draw_date}</td>
                        <td>${mainBalls}</td>
                        <td>${jokerBall}</td>
                    `;
                    tbody.appendChild(tr);
                });
            })
            .catch(err => console.error("Σφάλμα κληρώσεων:", err));
    }

    // ----------------------------------------------------
    // 3. REPETITIONS
    // ----------------------------------------------------
    function loadRepetitions() {
        fetch(`/api/stats/repetitions?game=${currentGame}`)
            .then(res => res.json())
            .then(data => {
                const repContainer = document.getElementById("repetitions-container");
                if (!repContainer) return;

                if (data.common_numbers && data.common_numbers.length > 0) {
                    const balls = data.common_numbers.map(n => `<span class="ball">${n}</span>`).join(" ");
                    repContainer.innerHTML = `<p>Κοινόι αριθμοί τελευταίων περιόδων: ${balls}</p>`;
                } else {
                    repContainer.innerHTML = "<p>Δεν βρέθηκαν επαναλαμβανόμενοι αριθμοί.</p>";
                }
            })
            .catch(err => console.error("Σφάλμα επαναλήψεων:", err));
    }
});
