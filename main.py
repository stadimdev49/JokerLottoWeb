from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
import sqlite3
import requests
import random
from datetime import datetime
from typing import Optional
from contextlib import asynccontextmanager
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

DB_NAME = "lottery.db"

GAME_IDS = {
    "joker": 5104,
    "lotto": 5103
}

# Αρχικοποίηση APScheduler για περιοδικό συγχρονισμό
scheduler = BackgroundScheduler()

def init_db():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS draws (
            game_type TEXT,
            draw_id INTEGER,
            draw_date TEXT,
            num1 INTEGER, num2 INTEGER, num3 INTEGER, num4 INTEGER, num5 INTEGER, num6 INTEGER,
            joker INTEGER,
            PRIMARY KEY (game_type, draw_id)
        )
    ''')
    conn.commit()
    conn.close()

def sync_game_data(game_type: str):
    game_id = GAME_IDS.get(game_type)
    if not game_id:
        return 0

    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    total_inserted = 0
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
        "Accept": "application/json"
    }

    try:
        # 1. Παίρνουμε την τελευταία ενεργή κλήρωση για να βρούμε το μέγιστο drawId
        latest_url = f"https://api.opap.gr/draws/v3.0/{game_id}/last"
        res = requests.get(latest_url, headers=headers, timeout=10)
        if res.status_code == 200:
            latest_draw = res.json()
            max_draw_id = latest_draw.get('drawId')
            if max_draw_id:
                # ΟΠΑΠ draw IDs: Υπολογισμός εκτιμώμενου εύρους για τα τελευταία χρόνια (από το 2022 και μετά ή και παλαιότερα)
                # Κάνουμε μαζικό fetch σε πακέτα (π.χ. ανά 500 IDs προς τα πίσω μέχρι να πιάσουμε ικανό ιστορικό)
                chunk_size = 500
                current_max = max_draw_id
                min_target_id = max(1, max_draw_id - 5000) # Καλύπτει πάνω από τα τελευταία έτη

                while current_max > min_target_id:
                    chunk_min = max(min_target_id, current_max - chunk_size + 1)
                    range_url = f"https://api.opap.gr/draws/v3.0/{game_id}/draw-id/{chunk_min}/{current_max}"
                    
                    try:
                        r_res = requests.get(range_url, headers=headers, timeout=10)
                        if r_res.status_code == 200:
                            r_data = r_res.json()
                            draws_list = r_data.get('content', r_data.get('result', [])) if isinstance(r_data, dict) else r_data
                            
                            for draw in draws_list:
                                d_id = draw.get('drawId')
                                d_time_raw = draw.get('drawTime')
                                if isinstance(d_time_raw, int):
                                    d_date = datetime.fromtimestamp(d_time_raw / 1000).strftime('%Y-%m-%d')
                                elif isinstance(d_time_raw, str):
                                    d_date = d_time_raw.split("T")[0]
                                else:
                                    d_date = datetime.now().strftime('%Y-%m-%d')

                                w_nums = draw.get('winningNumbers', {})
                                l_nums = w_nums.get('list', [])
                                b_nums = w_nums.get('bonus', [])

                                if len(l_nums) >= 5:
                                    n1, n2, n3, n4, n5 = l_nums[:5]
                                    n6 = l_nums[5] if len(l_nums) > 5 else None
                                    jk = b_nums[0] if b_nums else None

                                    cursor.execute('''
                                        INSERT OR IGNORE INTO draws 
                                        (game_type, draw_id, draw_date, num1, num2, num3, num4, num5, num6, joker)
                                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                                    ''', (game_type, d_id, d_date, n1, n2, n3, n4, n5, n6, jk))
                                    if cursor.rowcount > 0:
                                        total_inserted += 1
                            conn.commit()
                    except Exception:
                        pass

                    current_max = chunk_min - 1

    except Exception:
        pass

    conn.close()
    return total_inserted

def scheduled_sync_job():
    """Περιοδικός συγχρονισμός 3 φορές την ημέρα (20:00, 22:00, 00:00)."""
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Έναρξη προγραμματισμένου συγχρονισμού...")
    j_new = sync_game_data("joker")
    l_new = sync_game_data("lotto")
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Ολοκλήρωση: +{j_new} Τζόκερ, +{l_new} Lotto.")

@asynccontextmanager
async def lifespan(app: FastAPI):
    # --- STARTUP LOGIC ---
    init_db()
    sync_game_data("joker")
    sync_game_data("lotto")
    
    # Προσθήκη CronTrigger για εκτέλεση στις 20:00, 22:00 και 00:00 καθημερινά
    scheduler.add_job(
        scheduled_sync_job, 
        CronTrigger(hour="20,22,0", minute=0)
    )
    scheduler.start()
    
    yield
    
    # --- SHUTDOWN LOGIC ---
    scheduler.shutdown()

app = FastAPI(title="Lottery Analytics Platform", lifespan=lifespan)

app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    return templates.TemplateResponse(request=request, name="index.html")

@app.get("/api/sync")
async def force_sync():
    joker_new = sync_game_data("joker")
    lotto_new = sync_game_data("lotto")
    return {"status": "success", "joker_added": joker_new, "lotto_added": lotto_new}

@app.get("/api/stats")
async def get_stats(game: str = "joker", year: Optional[str] = "all"):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    query = "SELECT num1, num2, num3, num4, num5, num6, joker, draw_date FROM draws WHERE game_type = ?"
    params = [game]

    if year and year != "all":
        query += " AND strftime('%Y', draw_date) = ?"
        params.append(str(year))

    query += " ORDER BY draw_date DESC, draw_id DESC"

    cursor.execute(query, params)
    rows = cursor.fetchall()

    cursor.execute("SELECT MAX(draw_date) FROM draws WHERE game_type = ?", (game,))
    res_date = cursor.fetchone()
    last_draw_date = res_date[0] if res_date and res_date[0] else "Άγνωστη"

    conn.close()

    max_main_number = 45 if game == "joker" else 49
    max_bonus_number = 20 if game == "joker" else 0

    frequencies = {i: 0 for i in range(1, max_main_number + 1)}
    joker_frequencies = {i: 0 for i in range(1, max_bonus_number + 1)} if max_bonus_number > 0 else {}
    delays = {i: 9999 for i in range(1, max_main_number + 1)}

    total_draws = len(rows)
    limit = 5 if game == "joker" else 6

    for idx, row in enumerate(rows):
        main_nums = row[:limit]
        for num in main_nums:
            if num in frequencies:
                frequencies[num] += 1
                if delays[num] == 9999:
                    delays[num] = idx
        
        if game == "joker" and row[6] is not None:
            if row[6] in joker_frequencies:
                joker_frequencies[row[6]] += 1

    for i in delays:
        if delays[i] == 9999:
            delays[i] = total_draws

    return {
        "status": "success",
        "game": game,
        "total_draws": total_draws,
        "frequencies": frequencies,
        "delays": delays,
        "joker_frequencies": joker_frequencies,
        "last_updated": f"{last_draw_date} ({datetime.now().strftime('%H:%M')})"
    }

@app.get("/api/stats/repetitions")
async def get_repetitions_stats(game: str = "joker"):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    cursor.execute("""
        SELECT draw_id, draw_date, num1, num2, num3, num4, num5, num6 
        FROM draws 
        WHERE game_type = ? 
        ORDER BY draw_date DESC, draw_id DESC 
        LIMIT 20
    """, (game,))
    
    rows = cursor.fetchall()
    conn.close()

    if len(rows) < 11:
        return {"status": "error", "message": "Δεν υπάρχουν αρκετές κληρώσεις για ανάλυση."}

    limit_nums = 5 if game == "joker" else 6
    results = []

    for i in range(min(10, len(rows) - 10)):
        target_draw = rows[i]
        draw_id = target_draw[0]
        draw_date = target_draw[1]
        target_numbers = target_draw[2:2 + limit_nums]

        previous_10_draws = rows[i + 1 : i + 11]

        prev_freq = {}
        for prev_draw in previous_10_draws:
            for num in prev_draw[2:2 + limit_nums]:
                prev_freq[num] = prev_freq.get(num, 0) + 1

        breakdown = {"0": [], "1": [], "2": [], "3+": []}

        for num in target_numbers:
            count = prev_freq.get(num, 0)
            if count == 0:
                breakdown["0"].append(num)
            elif count == 1:
                breakdown["1"].append(num)
            elif count == 2:
                breakdown["2"].append(num)
            else:
                breakdown["3+"].append(num)

        results.append({
            "draw_id": draw_id,
            "draw_date": draw_date,
            "numbers": list(target_numbers),
            "counts": {
                "zero": len(breakdown["0"]),
                "one": len(breakdown["1"]),
                "two": len(breakdown["2"]),
                "three_plus": len(breakdown["3+"])
            },
            "details": breakdown
        })

    return {
        "status": "success",
        "game": game,
        "repetitions": results
    }

@app.get("/api/generate/random")
async def generate_simple_random(game: str = "joker"):
    max_num = 45 if game == "joker" else 49
    count = 5 if game == "joker" else 6
    
    numbers = sorted(random.sample(range(1, max_num + 1), count))
    joker = random.randint(1, 20) if game == "joker" else None
    
    return {
        "status": "success",
        "numbers": numbers,
        "joker": joker
    }

@app.post("/api/generate/rules")
async def generate_numbers_by_rules(request: Request):
    data = await request.json()
    game = data.get("game", "joker")
    rules = data.get("rules", [])

    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    cursor.execute("""
        SELECT num1, num2, num3, num4, num5, num6 
        FROM draws 
        WHERE game_type = ? 
        ORDER BY draw_date DESC, draw_id DESC
    """, (game,))
    draws = cursor.fetchall()
    conn.close()

    max_num = 45 if game == "joker" else 49
    limit_nums = 5 if game == "joker" else 6

    delays = {i: 9999 for i in range(1, max_num + 1)}
    for index, draw in enumerate(draws):
        main_draw_nums = draw[:limit_nums]
        for num in range(1, max_num + 1):
            if num in main_draw_nums and delays[num] == 9999:
                delays[num] = index

    selected_numbers = []
    used_numbers = set()

    for rule in rules:
        count_needed = int(rule.get("count", 1))
        min_delay = rule.get("min_delay")
        max_delay = rule.get("max_delay")
        exact_app = rule.get("exact_appearances")
        window = rule.get("window")

        candidates = []

        for num in range(1, max_num + 1):
            if num in used_numbers:
                continue

            valid = True

            if min_delay is not None and min_delay != "" and delays[num] < int(min_delay):
                valid = False
            if max_delay is not None and max_delay != "" and delays[num] > int(max_delay):
                valid = False

            if valid and window is not None and window != "" and exact_app is not None and exact_app != "":
                window_draws = draws[:int(window)]
                appearances = sum(1 for d in window_draws if num in d[:limit_nums])
                if appearances != int(exact_app):
                    valid = False

            if valid:
                candidates.append(num)

        if len(candidates) <= count_needed:
            chosen = candidates
        else:
            chosen = random.sample(candidates, count_needed)

        selected_numbers.extend(chosen)
        used_numbers.update(chosen)

    joker_number = random.randint(1, 20) if game == "joker" else None
    selected_numbers.sort()

    return {
        "status": "success",
        "numbers": selected_numbers,
        "count_generated": len(selected_numbers),
        "joker": joker_number
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="127.0.0.1", port=8050, reload=True)
