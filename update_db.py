import sqlite3

def update_db():
    print("🔄 Ενημέρωση βάσης δεδομένων...")
    conn = sqlite3.connect('vasi_dedomenwn.db')
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

    conn.commit()
    conn.close()
    print("🚀 Η βάση δεδομένων είναι έτοιμη!")

if __name__ == "__main__":
    update_db()