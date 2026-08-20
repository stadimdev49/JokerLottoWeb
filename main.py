import random
import sqlite3
import requests
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, Query
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from apscheduler.schedulers.background import BackgroundScheduler

DB_FILE = "lottery.db"

# --- DATABASE SETUP ---
def init_db():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS draws (
            game TEXT,
            draw_id INTEGER,
            draw_date TEXT,
            numbers TEXT,
            joker INTEGER,
            PRIMARY KEY (game, draw_id)
        )
    """)
    conn.commit()
    conn.close()

init_db()

# --- OPAP SYNC LOGIC (2 TIMES / 24h) ---
def sync_opap_data():
    print("[SCHEDULER] Εκτέλεση συγχρονισμού με τον ΟΠΑΠ...")
    games = ["joker", "lotto"]
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    for game in games:
        try:
            url = f"https://api.opap.gr/draws/v3.0/{game}/last-result/100"
            response = requests.get(url, timeout=10)
            if response.status_code == 200:
                draws = response.json()
                for d in draws:
                    draw_id = d.get("drawId")
                    draw_date = d.get("drawTime", "").split("T")[0]
                    winning_nums = d.get("winningNumbers", {})
                    list_nums = winning_nums.get("list", [])
                    bonus_list = winning_nums.get("bonus", [])
                    joker_val = bonus_list[0] if bonus_list else None

                    nums_str = ",".join(map(str, sorted(list_nums)))

                    cursor.execute("""
                        INSERT OR IGNORE INTO draws (game, draw_id, draw_date, numbers, joker)
                        VALUES (?, ?, ?, ?, ?)
                    """, (game, draw_id, draw_date, nums_str, joker_val))
                conn.commit()
                print(f"[SYNC SUCCESS] Ενημερώθηκαν τα δεδομένα για: {game}")
        except Exception as e:
            print(f"[SYNC ERROR] Σφάλμα στο παιχνίδι {game}: {e}")

    conn.close()

# --- SCHEDULER SETUP ---
scheduler = BackgroundScheduler()
# Εκτέλεση 2 φορές την ημέρα: στις 09:00 και στις 23:00
scheduler.add_job(sync_opap_data, 'cron', hour='9,23', minute='0')

@asynccontextmanager
async def lifespan(app: FastAPI):
    sync_opap_data()
    scheduler.start()
    yield
    scheduler.shutdown()

app = FastAPI(lifespan=lifespan)

app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# --- DATABASE HELPERS ---
def fetch_draws_from_db(game: str, limit: int = 100):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT draw_id, draw_date, numbers, joker 
        FROM draws 
        WHERE game = ? 
        ORDER BY draw_id DESC 
        LIMIT ?
    """, (game, limit))
    rows = cursor.fetchall()
    conn.close()

    result = []
    for r in rows:
        nums = [int(n) for n in r[2].split(",")] if r[2] else []
        result.append({
            "draw_id": r[0],
            "draw_date": r[1],
            "numbers": nums,
            "joker": r[3]
        })
    return result

# --- ENDPOINTS ---
@app.get("/", response_class=HTMLResponse)
@app.head("/")
def read_root(request: Request):
    return templates.TemplateResponse(request=request, name="index.html")

@app.get("/api/draws/analysis")
def get_draws_analysis(game: str = Query("joker", pattern="^(joker|lotto)$")):
    all_draws = fetch_draws_from_db(game, limit=30)
    if not all_draws:
        return {"game": game, "draws": []}

    analyzed_draws = []
    target_count = min(10, len(all_draws))

    for i in range(target_count):
        current_draw = all_draws[i]
        previous_10 = all_draws[i+1 : i+11]

        history_counts = {}
        for prev in previous_10:
            for num in prev.get("numbers", []):
                history_counts[num] = history_counts.get(num, 0) + 1

        num_analysis = []
        for num in current_draw.get("numbers", []):
            count = history_counts.get(num, 0)
            if count == 0:
                category = "absent"
            elif count == 1:
                category = "1_appear"
            elif count == 2:
                category = "2_appears"
            else:
                category = "3_plus_appears"

            num_analysis.append({
                "number": num,
                "prev_appearances": count,
                "category": category
            })

        analyzed_draws.append({
            "draw_id": current_draw["draw_id"],
            "draw_date": current_draw["draw_date"],
            "joker": current_draw.get("joker"),
            "numbers_analysis": num_analysis
        })

    return {"game": game, "draws": analyzed_draws}

@app.get("/api/generate")
def generate_ticket(
    game: str = Query("joker", pattern="^(joker|lotto)$"),
    mode: str = Query("random", pattern="^(random|rules)$"),
    lookback: int = Query(10, ge=5, le=100),
    rule_type: str = Query("hot", pattern="^(hot|cold|balanced)$")
):
    max_num = 45 if game == "joker" else 49
    select_count = 5 if game == "joker" else 6
    joker_max = 20 if game == "joker" else None

    if mode == "random":
        chosen_numbers = sorted(random.sample(range(1, max_num + 1), select_count))
        chosen_joker = random.randint(1, joker_max) if joker_max else None
        return {"numbers": chosen_numbers, "joker": chosen_joker, "mode": mode}

    all_draws = fetch_draws_from_db(game, limit=lookback)
    counts = {n: 0 for n in range(1, max_num + 1)}

    for draw in all_draws:
        for num in draw.get("numbers", []):
            if num in counts:
                counts[num] += 1

    sorted_by_freq = sorted(counts.items(), key=lambda x: x[1], reverse=True)

    if rule_type == "hot":
        pool = [num for num, _ in sorted_by_freq[:20]]
        chosen_numbers = sorted(random.sample(pool, select_count))
    elif rule_type == "cold":
        pool = [num for num, _ in sorted_by_freq[-20:]]
        chosen_numbers = sorted(random.sample(pool, select_count))
    else:  # balanced
        pool_hot = [num for num, _ in sorted_by_freq[:15]]
        pool_cold = [num for num, _ in sorted_by_freq[-15:]]
        chosen_numbers = sorted(random.sample(pool_hot, 3) + random.sample(pool_cold, select_count - 3))

    chosen_joker = random.randint(1, joker_max) if joker_max else None
    return {"numbers": chosen_numbers, "joker": chosen_joker, "mode": mode, "rule": rule_type}
