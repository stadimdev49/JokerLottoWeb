let currentGame = 'joker';
let chartInstance = null;

document.addEventListener('DOMContentLoaded', () => {
    populateYearDropdown();
    loadStats();
    loadRepetitions();
    addRuleRow();
});

function populateYearDropdown() {
    const yearSelect = document.getElementById('year-select');
    const currentYear = new Date().getFullYear();
    
    for (let year = currentYear; year >= 2010; year--) {
        const option = document.createElement('option');
        option.value = year;
        option.textContent = year;
        yearSelect.appendChild(option);
    }
}

function switchGame(game) {
    currentGame = game;
    
    document.getElementById('btn-joker').classList.toggle('active', game === 'joker');
    document.getElementById('btn-lotto').classList.toggle('active', game === 'lotto');
    document.getElementById('active-game-label').textContent = game.toUpperCase();
    
    loadStats();
    loadRepetitions();
}

async function loadStats() {
    const year = document.getElementById('year-select').value;
    
    try {
        const res = await fetch(`/api/stats?game=${currentGame}&year=${year}`);
        const data = await res.json();

        document.getElementById('total-draws-count').textContent = data.total_draws.toLocaleString();
        
        renderGrid(data.frequencies);
        renderChart(data.frequencies);
    } catch (err) {
        console.error("Σφάλμα κατά τη φόρτωση των στατιστικών:", err);
    }
}

async function loadRepetitions() {
    try {
        const res = await fetch(`/api/stats/repetitions?game=${currentGame}`);
        const data = await res.json();

        if (data.status === 'success') {
            renderRepetitionTable(data.repetitions);
        }
    } catch (err) {
        console.error("Σφάλμα κατά τη φόρτωση των επαναλήψεων:", err);
    }
}

function renderRepetitionTable(items) {
    const tbody = document.getElementById('repetitionTableBody');
    tbody.innerHTML = '';

    items.forEach(item => {
        const tr = document.createElement('tr');
        
        const numsStr = item.numbers.join(', ');

        tr.innerHTML = `
            <td><strong>#${item.draw_id}</strong><br><small style="color:var(--text-muted);">${item.draw_date}</small></td>
            <td><span style="color:var(--accent-cyan); font-weight:bold;">${numsStr}</span></td>
            <td><span class="badge-count badge-zero">${item.counts.zero}</span> <small>(${item.details['0'].join(',') || '-'})</small></td>
            <td><span class="badge-count badge-one">${item.counts.one}</span> <small>(${item.details['1'].join(',') || '-'})</small></td>
            <td><span class="badge-count badge-two">${item.counts.two}</span> <small>(${item.details['2'].join(',') || '-'})</small></td>
            <td><span class="badge-count badge-three">${item.counts.three_plus}</span> <small>(${item.details['3+'].join(',') || '-'})</small></td>
        `;

        tbody.appendChild(tr);
    });
}

function renderGrid(frequencies) {
    const grid = document.getElementById('numberGrid');
    grid.innerHTML = '';

    Object.entries(frequencies).forEach(([num, count]) => {
        const div = document.createElement('div');
        div.className = 'grid-num-card';
        div.innerHTML = `
            <span class="num-ball">${num}</span>
            <span class="num-count">${count} εμφο.</span>
        `;
        grid.appendChild(div);
    });
}

function renderChart(frequencies) {
    const ctx = document.getElementById('frequencyChart').getContext('2d');
    const labels = Object.keys(frequencies);
    const values = Object.values(frequencies);

    if (chartInstance) {
        chartInstance.destroy();
    }

    const barColor = currentGame === 'joker' ? '#ffb703' : '#00f5d4';

    chartInstance = new Chart(ctx, {
        type: 'bar',
        data: {
            labels: labels,
            datasets: [{
                label: 'Συχνότητα Εμφάνισης',
                data: values,
                backgroundColor: barColor,
                borderRadius: 4
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { display: false }
            },
            scales: {
                x: { ticks: { color: '#8d99ae', font: { size: 10 } }, grid: { display: false } },
                y: { ticks: { color: '#8d99ae' }, grid: { color: '#1f263e' } }
            }
        }
    });
}

/* 1. Απλή Τυχαία Γεννήτρια */
async function generateSimpleTicket() {
    try {
        const res = await fetch(`/api/generate/random?game=${currentGame}`);
        const data = await res.json();
        if (data.status === 'success') {
            renderBalls('simpleTicketBalls', 'simpleResultBox', data.numbers, data.joker);
        }
    } catch (err) {
        console.error("Σφάλμα στην απλή γεννήτρια:", err);
    }
}

/* 2. Έξυπνη Γεννήτρια με Κανόνες */
function addRuleRow() {
    const container = document.getElementById('rules-container');
    const rowId = Date.now();

    const rowHtml = `
        <div class="rule-row" id="rule-${rowId}">
            <span>Θέλω</span>
            <input type="number" class="rule-count" value="2" min="1" max="5" style="width: 50px;">
            <span>αριθμούς με</span>

            <select class="rule-type" onchange="toggleRuleInputs(${rowId}, this.value)">
                <option value="delay">Καθυστέρηση (Min)</option>
                <option value="frequency">Εμφανίσεις σε παράθυρο N</option>
            </select>

            <span id="delay-inputs-${rowId}">
                > <input type="number" class="rule-min-delay" value="10" style="width: 60px;"> εμφ.
            </span>

            <span id="freq-inputs-${rowId}" style="display: none;">
                <input type="number" class="rule-exact-app" value="2" style="width: 50px;"> εμφ. στις 
                <input type="number" class="rule-window" value="15" style="width: 60px;"> κληρώσεις
            </span>

            <button class="btn nav-btn" style="color: var(--accent-pink); padding: 2px 6px;" onclick="removeRule(${rowId})">✖</button>
        </div>
    `;

    container.insertAdjacentHTML('beforeend', rowHtml);
}

function removeRule(rowId) {
    const row = document.getElementById(`rule-${rowId}`);
    if (row) row.remove();
}

function toggleRuleInputs(rowId, type) {
    const delaySpan = document.getElementById(`delay-inputs-${rowId}`);
    const freqSpan = document.getElementById(`freq-inputs-${rowId}`);

    if (type === 'delay') {
        delaySpan.style.display = 'inline';
        freqSpan.style.display = 'none';
    } else {
        delaySpan.style.display = 'none';
        freqSpan.style.display = 'inline';
    }
}

async function generateRulesTicket() {
    const rows = document.querySelectorAll('.rule-row');
    const rules = [];

    rows.forEach(row => {
        const count = row.querySelector('.rule-count').value;
        const type = row.querySelector('.rule-type').value;

        if (type === 'delay') {
            const minDelay = row.querySelector('.rule-min-delay').value;
            rules.push({ count: count, min_delay: minDelay });
        } else {
            const exactApp = row.querySelector('.rule-exact-app').value;
            const windowVal = row.querySelector('.rule-window').value;
            rules.push({ count: count, exact_appearances: exactApp, window: windowVal });
        }
    });

    try {
        const res = await fetch('/api/generate/rules', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ game: currentGame, rules: rules })
        });

        const data = await res.json();
        if (data.status === 'success') {
            renderBalls('rulesTicketBalls', 'rulesResultBox', data.numbers, data.joker);
        }
    } catch (err) {
        console.error("Σφάλμα στην έξυπνη γεννήτρια:", err);
    }
}

/* Κοινή συνάρτηση προβολής μπαλών */
function renderBalls(containerId, boxId, numbers, joker) {
    const container = document.getElementById(containerId);
    const resultBox = document.getElementById(boxId);
    container.innerHTML = '';

    numbers.forEach(num => {
        const ball = document.createElement('div');
        ball.className = 'generated-ball';
        ball.textContent = num;
        container.appendChild(ball);
    });

    if (joker) {
        const jBall = document.createElement('div');
        jBall.className = 'generated-ball joker-ball';
        jBall.textContent = joker;
        container.appendChild(jBall);
    }

    resultBox.style.display = 'block';
}
