from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
import sqlite3
import requests
import calendar
import random
from datetime import datetime
from typing import Optional
from contextlib import asynccontextmanager
from apscheduler.schedulers.background import BackgroundScheduler

DB_NAME = "lottery.db"

GAME_IDS = {
    "joker": 5104,
    "lotto": 5103
}

# Αρχικοποίηση APScheduler
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

    now = datetime.now()
    current_year = now.year
    current_month = now.month

    total_inserted = 0
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
        "Accept": "application/json"
    }

    for year in range(2010, current_year + 1):
        max_month = current_month if year == current_year else 12

        for month in range(1, max_month + 1):
            last_day = calendar.monthrange(year, month)[1]
            start_date = f"{year}-{month:02d}-01"
            end_date = f"{year}-{month:02d}-{last_day:02d}"

            if year == current_year and month == current_month:
                end_date = now.strftime("%Y-%m-%d")

            url = f"https://api.opap.gr/draws/v3.0/{game_id}/draw-date/{start_date}/{end_date}"

            try:
                res = requests.get(url, headers=headers, timeout=10)
                if res.status_code != 200:
                    continue

                data = res.json()
                draws = data.get('content', []) if isinstance(data, dict) else data

                inserted_this_month = 0
                for draw in draws:
                    draw_id = draw.get('drawId')
                    draw_time_raw = draw.get('drawTime')
                    
                    if isinstance(draw_time_raw, int):
                        draw_date = datetime.fromtimestamp(draw_time_raw / 1000).strftime('%Y-%m-%d')
                    elif isinstance(draw_time_raw, str):
                        draw_date = draw_time_raw.split("T")[0]
                    else:
                        draw_date = start_date

                    winning_numbers = draw.get('winningNumbers', {})
                    list_nums = winning_numbers.get('list', [])
                    bonus_nums = winning_numbers.get('bonus', [])

                    if len(list_nums) >= 5:
                        num1, num2, num3, num4, num5 = list_nums[:5]
                        num6 = list_nums[5] if len(list_nums) > 5 else None
                        joker = bonus_nums[0] if bonus_nums else None

                        cursor.execute('''
                            INSERT OR IGNORE INTO draws 
                            (game_type, draw_id, draw_date, num1, num2, num3, num4, num5, num6, joker)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        ''', (game_type, draw_id, draw_date, num1, num2, num3, num4, num5, num6, joker))
                        
                        if cursor.rowcount > 0:
                            inserted_this_month += 1

                conn.commit()
                total_inserted += inserted_this_month

            except Exception:
                pass

    conn.close()
    return total_inserted

def scheduled_sync_job():
    """Περιοδικός συγχρονισμός κάθε 24 ώρες."""
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
    
    # Προσθήκη εργασίας αυτόματου συγχρονισμού κάθε 24 ώρες
    scheduler.add_job(scheduled_sync_job, 'interval', hours=24)
    scheduler.start()
    
    yield  # Η εφαρμογή τρέχει και δέχεται αιτήματα
    
    # --- SHUTDOWN LOGIC ---
    scheduler.shutdown()

app = FastAPI(title="Lottery Stats Platform", lifespan=lifespan)

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

    query = "SELECT num1, num2, num3, num4, num5, num6, joker FROM draws WHERE game_type = ?"
    params = [game]

    if year and year != "all":
        query += " AND strftime('%Y', draw_date) = ?"
        params.append(str(year))

    cursor.execute(query, params)
    rows = cursor.fetchall()
    conn.close()

    max_main_number = 45 if game == "joker" else 49
    max_bonus_number = 20 if game == "joker" else 0

    frequencies = {i: 0 for i in range(1, max_main_number + 1)}
    joker_frequencies = {i: 0 for i in range(1, max_bonus_number + 1)} if max_bonus_number > 0 else {}

    total_draws = len(rows)

    for row in rows:
        limit = 5 if game == "joker" else 6
        for num in row[:limit]:
            if num in frequencies:
                frequencies[num] += 1
        
        if game == "joker" and row[6] is not None:
            if row[6] in joker_frequencies:
                joker_frequencies[row[6]] += 1

    return {
        "status": "success",
        "game": game,
        "total_draws": total_draws,
        "frequencies": frequencies,
        "joker_frequencies": joker_frequencies
    }

# Ανάλυση Επαναλήψεων (Τελευταίες 10 κληρώσεις vs Προηγούμενες 10)
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

# 1. Απλή Τυχαία Γεννήτρια
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

# 2. Έξυπνη Γεννήτρια με Κανόνες
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

        if len(candidates) < count_needed:
            chosen = candidates
        else:
            chosen = random.sample(candidates, count_needed)

        selected_numbers.extend(chosen)
        used_numbers.update(chosen)

    needed_total = 5 if game == "joker" else 6
    while len(selected_numbers) < needed_total:
        remaining = [n for n in range(1, max_num + 1) if n not in used_numbers]
        if not remaining:
            break
        pick = random.choice(remaining)
        selected_numbers.append(pick)
        used_numbers.add(pick)

    joker_number = random.randint(1, 20) if game == "joker" else None
    selected_numbers.sort()

    return {
        "status": "success",
        "numbers": selected_numbers,
        "joker": joker_number
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="127.0.0.1", port=8050, reload=True)