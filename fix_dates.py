import sqlite3
import pandas as pd

DB_NAME = "lottery.db"

def fix_database_dates():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    cursor.execute("SELECT game_type, draw_id, draw_date FROM draws")
    rows = cursor.fetchall()
    
    print(f"Έλεγχος και διόρθωση {len(rows)} εγγραφών στη βάση...")
    updated_count = 0
    
    for game_type, draw_id, draw_date in rows:
        try:
            fixed_date = pd.to_datetime(draw_date).strftime('%Y-%m-%d')
            if fixed_date != draw_date:
                cursor.execute("""
                    UPDATE draws SET draw_date = ? 
                    WHERE game_type = ? AND draw_id = ?
                """, (fixed_date, game_type, draw_id))
                updated_count += 1
        except Exception:
            continue
            
    conn.commit()
    conn.close()
    print(f"Η διαδικασία ολοκληρώθηκε! Διορθώθηκαν οι ημερομηνίες σε {updated_count} εγγραφές.")

if __name__ == "__main__":
    fix_database_dates()