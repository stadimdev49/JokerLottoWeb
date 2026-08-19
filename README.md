# 🎰 Lottery Stats Platform (Joker & Lotto Analytics)

Δικτυακή πλατφόρμα ανάλυσης κληρώσεων Τζόκερ και Lotto (ΟΠΑΠ). Παρέχει στατιστικά στοιχεία συχνότητας, ανάλυση επαναλήψεων αριθμών (10 vs 10 κληρώσεις), αυτόματο συγχρονισμό δεδομένων και διπλή γεννήτρια δελτίων (τυχαία & βάσει κανόνων καθυστέρησης/συχνότητας).

---

## 🚀 Χαρακτηριστικά

- **FastAPI & Async Engine:** Ταχύτατο backend με αυτόματους REST API σταθμούς.
- **24h Auto Sync (APScheduler):** Περιοδικό κατέβασμα νέων κληρώσεων από το API v3.0 του ΟΠΑΠ.
- **SQLite Local Caching:** Γρήγορη εκτέλεση ερωτημάτων χωρίς καθυστερήσεις δικτύου.
- **Analytics & Visualizations:** Ιστόγραμμα συχνότητας (Chart.js), dynamic matrix και ανάλυση επαναλήψεων τελευταίων 10 κληρώσεων.
- **Dual Ticket Generators:** 
  1. Απλή Τυχαία Γεννήτρια.
  2. Έξυπνη Γεννήτρια με σύνθετους κανόνες (min delay, συχνότητα σε παράθυρο N κληρώσεων).

---

## 🛠️ Τοπική Εγκατάσταση (Local Setup)

1. **Cloning του Repository:**
   ```bash
   git clone [https://github.com/USERNAME/joker-stats-platform.git](https://github.com/USERNAME/joker-stats-platform.git)
   cd joker-stats-platform