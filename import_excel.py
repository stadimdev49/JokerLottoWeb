import os
import glob
import pandas as pd
import sqlite3
from datetime import datetime

DB_NAME = "lottery.db"
EXCEL_DIR = "data_excels"

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

def import_excels():
    init_db()
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    search_path = os.path.join(EXCEL_DIR, "*.xls*")
    files = glob.glob(search_path)

    if not files:
        print(f"Δεν βρέθηκαν αρχεία Excel στον φάκελο '{EXCEL_DIR}'.")
        conn.close()
        return

    total_imported_global = 0

    for file_path in files:
        filename = os.path.basename(file_path).lower()
        
        if "joker" in filename:
            game_type = "joker"
        elif "lotto" in filename:
            game_type = "lotto"
        else:
            print(f"Παράκαμψη αρχείου (δεν διακρίνεται αν είναι joker ή lotto): {filename}")
            continue

        print(f"Επεξεργασία αρχείου: {filename} ως {game_type.upper()}...")
        
        try:
            df = pd.read_excel(file_path)
            inserted_count = 0
            
            for _, row in df.iterrows():
                try:
                    d_id = int(row.iloc[0])
                    
                    # Ασφαλής μετατροπή ημερομηνίας σε YYYY-MM-DD
                    raw_date = row.iloc[1]
                    try:
                        d_date = pd.to_datetime(raw_date).strftime('%Y-%m-%d')
                    except Exception:
                        d_date = str(raw_date).split(" ")[0]

                    numbers = []
                    for col_val in row.iloc[2:]:
                        if pd.notna(col_val) and str(col_val).replace('.', '', 1).isdigit():
                            numbers.append(int(float(col_val)))

                    if game_type == "joker":
                        if len(numbers) >= 6:
                            n1, n2, n3, n4, n5 = numbers[:5]
                            n6 = None
                            jk = numbers[5]
                        else:
                            continue
                    else:  # lotto
                        if len(numbers) >= 6:
                            n1, n2, n3, n4, n5, n6 = numbers[:6]
                            jk = None
                        else:
                            continue

                    cursor.execute('''
                        INSERT OR IGNORE INTO draws 
                        (game_type, draw_id, draw_date, num1, num2, num3, num4, num5, num6, joker)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (game_type, d_id, d_date, n1, n2, n3, n4, n5, n6, jk))

                    if cursor.rowcount > 0:
                        inserted_count += 1
                except Exception:
                    continue

            conn.commit()
            print(f" -> Επιτυχία! Προστέθηκαν {inserted_count} εγγραφές από το {filename}.")
            total_imported_global += inserted_count

        except Exception as e:
            print(f"Σφάλμα κατά την ανάγνωση του {filename}: {str(e)}")

    conn.close()
    print(f"\n=== Η διαδικασία ολοκληρώθηκε! Συνολικά περάστηκαν στη βάση {total_imported_global} νέες κληρώσεις. ===")

if __name__ == "__main__":
    import_excels()