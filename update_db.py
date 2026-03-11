import sqlite3
import os

def update_db():
    basedir = os.path.abspath(os.path.dirname(__file__))
    db_path = os.path.join(basedir, 'vasi_dedomenwn.db')
    print(f"🔄 Ενημέρωση βάσης δεδομένων: {db_path}")
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    
    # Προσθήκη στήλης topikes_ergasies
    try:
        c.execute("ALTER TABLE ktimata ADD COLUMN topikes_ergasies TEXT")
        print("✅ Προστέθηκε η στήλη 'topikes_ergasies'")
    except sqlite3.OperationalError:
        print("ℹ️ Η στήλη 'topikes_ergasies' υπάρχει ήδη")

    # Προσθήκη στήλης teleftaia_enimerosi_ergasion
    try:
        c.execute("ALTER TABLE ktimata ADD COLUMN teleftaia_enimerosi_ergasion DATETIME")
        print("✅ Προστέθηκε η στήλη 'teleftaia_enimerosi_ergasion'")
    except sqlite3.OperationalError:
        print("ℹ️ Η στήλη 'teleftaia_enimerosi_ergasion' υπάρχει ήδη")

    # Προσθήκη στήλης fainologiko_stadio
    try:
        c.execute("ALTER TABLE ktimata ADD COLUMN fainologiko_stadio VARCHAR(50) DEFAULT 'Άγνωστο'")
        print("✅ Προστέθηκε η στήλη 'fainologiko_stadio'")
    except sqlite3.OperationalError:
        print("ℹ️ Η στήλη 'fainologiko_stadio' υπάρχει ήδη")

    # Προσθήκη στήλης gdd_accumulated (ΝΕΟ)
    try:
        c.execute("ALTER TABLE ktimata ADD COLUMN gdd_accumulated FLOAT DEFAULT 0.0")
        print("✅ Προστέθηκε η στήλη 'gdd_accumulated'")
    except sqlite3.OperationalError:
        print("ℹ️ Η στήλη 'gdd_accumulated' υπάρχει ήδη")

    conn.commit()
    conn.close()
    print("🚀 Η βάση δεδομένων είναι έτοιμη!")

if __name__ == "__main__":
    update_db()