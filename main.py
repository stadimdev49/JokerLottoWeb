import sqlite3
import calendar
import requests
from datetime import datetime
from typing import List, Dict, Any, Optional

from fastapi import FastAPI, Request, Query, BackgroundTasks
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from apscheduler.schedulers.background import BackgroundScheduler

# ==========================================
# CONSTANTS & CONFIGURATION
# ==========================================
DB_NAME = "lottery.db"

GAME_IDS = {
    "joker": 5104,
    "lotto": 5103
}

app = FastAPI(title="Lottery Stats Platform", version="2.0")

# Mount Static & Templates
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")


# ==========================================
# DATABASE INITIALIZATION
# ==========================================
def init_db():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS draws (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            game_type TEXT NOT NULL,
            draw_id INTEGER UNIQUE,
            draw_date TEXT NOT NULL,
            num1 INTEGER,
            num2 INTEGER,
            num3 INTEGER,
            num4 INTEGER,
            num5 INTEGER,
            num6 INTEGER,
            joker INTEGER
        )
    ''')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_game_date ON draws (game_type, draw_date);')
    conn.commit()
    conn.close()

init_db()


# ==========================================
# OPAP API SYNC ENGINE
# ==========================================
def sync_game_data(game_type: str) -> int:
    """
    Κατεβάζει κληρώσεις από το API του ΟΠΑΠ με υποστήριξη Browser Headers
    και έξυπνο Incremental Sync από την τελευταία γνωστή ημερομηνία.
    """
    game_id = GAME_IDS.get(game_type)
    if not game_id:
        return 0

    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    now = datetime.now()
    current_year = now.year

    # 1. Βρίσκουμε την τελευταία ημερομηνία κλήρωσης στη βάση
    cursor.execute("SELECT MAX(draw_date) FROM draws WHERE game_type = ?", (game_type,))
    row = cursor.fetchone()
    last_date = row[0] if row else None

    # Αν η βάση είναι άδεια, ξεκινάμε από το 2020. Αλλιώς από τη χρονιά του last_date.
    start_year = 2020
    if last_date:
        try:
            start_year = int(last_date.split("-")[0])
        except Exception:
            pass

    total_inserted = 0

    # Headers για αποφυγή 403 Forbidden από Datacenters (Render/Cloud)
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "el-GR,el;q=0.9,en-US;q=0.8,en;q=0.7",
        "Origin": "https://www.opap.gr",
        "Referer": "https://www.opap.gr/"
    }

    for year in range(start_year, current_year + 1):
        max_month = now.month if year == current_year else 12

        for month in range(1, max_month + 1):
            last_day = calendar.monthrange(year, month)[1]
            start_date = f"{year}-{month:02d}-01"
            end_date = f"{year}-{month:02d}-{last_day:02d}"

            if year == current_year and month == now.month:
                end_date = now.strftime("%Y-%m-%d")

            url = f"https://api.opap.gr/draws/v3.0/{game_id}/draw-date/{start_date}/{end_date}"

            try:
                res = requests.get(url, headers=headers, timeout=12)
                if res.status_code != 200:
                    print(f"[SYNC WARN] API Returned Status {res.status_code} for {game_type} ({start_date})")
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

            except Exception as e:
                print(f"[SYNC ERROR] Failed to fetch {game_type} for {start_date}: {e}")

    conn.close()
    print(f"[SYNC SUCCESS] Fetched {total_inserted} new draws for {game_type}.")
    return total_inserted


def scheduled_sync_job():
    print("[SCHEDULER] Running periodic draw sync...")
    sync_game_data("joker")
    sync_game_data("lotto")


# ==========================================
# LIFESPAN & BACKGROUND SCHEDULER
# ==========================================
scheduler = BackgroundScheduler()

@app.on_event("startup")
def startup_event():
    # Εκτέλεση συγχρονισμού κατά την εκκίνηση
    print("[STARTUP] Initializing Database & Executing Startup Sync...")
    scheduled_sync_job()
    
    # Προγραμματισμός ανά 12 ώρες
    scheduler.add_job(scheduled_sync_job, 'interval', hours=12)
    scheduler.start()

@app.on_event("shutdown")
def shutdown_event():
    scheduler.shutdown()


# ==========================================
# FRONTEND ROUTES
# ==========================================
@app.get("/", response_class=HTMLResponse)
def read_root(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


# ==========================================
# REST API ENDPOINTS
# ==========================================
@app.get("/api/sync")
def trigger_sync(background_tasks: BackgroundTasks):
    """Χειροκίνητος συγχρονισμός μέσω API endpoint."""
    j_added = sync_game_data("joker")
    l_added = sync_game_data("lotto")
    return {
        "status": "success",
        "message": "Sync completed successfully",
        "joker_inserted": j_added,
        "lotto_inserted": l_added
    }


@app.get("/api/draws")
def get_draws(
    game: str = Query("joker", regex="^(joker|lotto)$"),
    limit: int = Query(20, ge=1, le=500)
):
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute('''
        SELECT draw_id, draw_date, num1, num2, num3, num4, num5, num6, joker
        FROM draws
        WHERE game_type = ?
        ORDER BY draw_date DESC, draw_id DESC
        LIMIT ?
    ''', (game, limit))

    rows = cursor.fetchall()
    conn.close()

    result = []
    for r in rows:
        nums = [r['num1'], r['num2'], r['num3'], r['num4'], r['num5']]
        if r['num6'] is not None:
            nums.append(r['num6'])
        result.append({
            "draw_id": r['draw_id'],
            "draw_date": r['draw_date'],
            "numbers": nums,
            "joker": r['joker']
        })

    return {"game": game, "total": len(result), "draws": result}


@app.get("/api/stats/frequencies")
def get_frequencies(
    game: str = Query("joker", regex="^(joker|lotto)$"),
    limit: int = Query(100, ge=5, le=2000)
):
    max_num = 45 if game == "joker" else 49
    max_joker = 20 if game == "joker" else 20

    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    if game == "joker":
        cursor.execute('''
            SELECT num1, num2, num3, num4, num5, joker
            FROM draws WHERE game_type = ?
            ORDER BY draw_date DESC, draw_id DESC LIMIT ?
        ''', (game, limit))
    else:
        cursor.execute('''
            SELECT num1, num2, num3, num4, num5, num6, joker
            FROM draws WHERE game_type = ?
            ORDER BY draw_date DESC, draw_id DESC LIMIT ?
        ''', (game, limit))

    rows = cursor.fetchall()
    conn.close()

    num_counts = {i: 0 for i in range(1, max_num + 1)}
    joker_counts = {i: 0 for i in range(1, max_joker + 1)}

    for r in rows:
        main_nums = r[:-1]
        j_val = r[-1]

        for n in main_nums:
            if n and 1 <= n <= max_num:
                num_counts[n] += 1
        if j_val and 1 <= j_val <= max_joker:
            joker_counts[j_val] += 1

    return {
        "game": game,
        "sample_size": len(rows),
        "numbers_frequency": num_counts,
        "joker_frequency": joker_counts if game == "joker" else {}
    }


# ==========================================
# LOCAL RUNNER
# ==========================================
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="127.0.0.1", port=8050, reload=True)