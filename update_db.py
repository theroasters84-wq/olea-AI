import os
os.environ['SKIP_SCHEDULER'] = 'true' # Prevent scheduler from starting during import
from sqlalchemy import text
from core import vasi, efarmogi

def update_db():
    print("🔄 Ενημέρωση βάσης δεδομένων (μέσω SQLAlchemy)...")
    with efarmogi.app_context():
        # Ensure all tables exist
        vasi.create_all()
        
        with vasi.engine.connect() as conn:
            # Προσθήκη στήλης topikes_ergasies
            try:
                conn.execute(text("ALTER TABLE ktimata ADD COLUMN topikes_ergasies TEXT"))
                conn.commit()
                print("✅ Προστέθηκε η στήλη 'topikes_ergasies'")
            except Exception as e:
                print(f"ℹ️ Η στήλη 'topikes_ergasies' υπάρχει ήδη ({e})")
                conn.rollback()

            # Προσθήκη στήλης teleftaia_enimerosi_ergasion
            try:
                conn.execute(text("ALTER TABLE ktimata ADD COLUMN teleftaia_enimerosi_ergasion TIMESTAMP"))
                conn.commit()
                print("✅ Προστέθηκε η στήλη 'teleftaia_enimerosi_ergasion'")
            except Exception as e:
                print(f"ℹ️ Η στήλη 'teleftaia_enimerosi_ergasion' υπάρχει ήδη ({e})")
                conn.rollback()

            # Προσθήκη στήλης fainologiko_stadio
            try:
                conn.execute(text("ALTER TABLE ktimata ADD COLUMN fainologiko_stadio VARCHAR(50) DEFAULT 'Άγνωστο'"))
                conn.commit()
                print("✅ Προστέθηκε η στήλη 'fainologiko_stadio'")
            except Exception as e:
                print(f"ℹ️ Η στήλη 'fainologiko_stadio' υπάρχει ήδη ({e})")
                conn.rollback()

            # Προσθήκη στήλης nero_ph
            try:
                conn.execute(text("ALTER TABLE ktimata ADD COLUMN nero_ph FLOAT"))
                conn.commit()
                print("✅ Προστέθηκε η στήλη 'nero_ph'")
            except Exception as e:
                print(f"ℹ️ Η στήλη 'nero_ph' υπάρχει ήδη ({e})")
                conn.rollback()

            # Προσθήκη στήλης nero_agwgimotita
            try:
                conn.execute(text("ALTER TABLE ktimata ADD COLUMN nero_agwgimotita FLOAT"))
                conn.commit()
                print("✅ Προστέθηκε η στήλη 'nero_agwgimotita'")
            except Exception as e:
                print(f"ℹ️ Η στήλη 'nero_agwgimotita' υπάρχει ήδη ({e})")
                conn.rollback()

            # Προσθήκη στήλης gdd_accumulated (ΝΕΟ)
            try:
                conn.execute(text("ALTER TABLE ktimata ADD COLUMN gdd_accumulated FLOAT DEFAULT 0.0"))
                conn.commit()
                print("✅ Προστέθηκε η στήλη 'gdd_accumulated'")
            except Exception as e:
                print(f"ℹ️ Η στήλη 'gdd_accumulated' υπάρχει ήδη ({e})")
                conn.rollback()

            # Προσθήκη στήλης ai_sumvouli_cache
            try:
                conn.execute(text("ALTER TABLE ktimata ADD COLUMN ai_sumvouli_cache TEXT"))
                conn.commit()
                print("✅ Προστέθηκε η στήλη 'ai_sumvouli_cache'")
            except Exception as e:
                print(f"ℹ️ Η στήλη 'ai_sumvouli_cache' υπάρχει ήδη ({e})")
                conn.rollback()

            # Προσθήκη στήλης ai_sumvouli_date
            try:
                conn.execute(text("ALTER TABLE ktimata ADD COLUMN ai_sumvouli_date TIMESTAMP"))
                conn.commit()
                print("✅ Προστέθηκε η στήλη 'ai_sumvouli_date'")
            except Exception as e:
                print(f"ℹ️ Η στήλη 'ai_sumvouli_date' υπάρχει ήδη ({e})")
                conn.rollback()

            # Προσθήκη στήλης polygon_geojson
            try:
                conn.execute(text("ALTER TABLE ktimata ADD COLUMN polygon_geojson TEXT"))
                conn.commit()
                print("✅ Προστέθηκε η στήλη 'polygon_geojson'")
            except Exception as e:
                print(f"ℹ️ Η στήλη 'polygon_geojson' υπάρχει ήδη ({e})")
                conn.rollback()
                
            # Προσθήκη στήλης ypsometro
            try:
                conn.execute(text("ALTER TABLE ktimata ADD COLUMN ypsometro FLOAT"))
                conn.commit()
                print("✅ Προστέθηκε η στήλη 'ypsometro'")
            except Exception as e:
                print(f"ℹ️ Η στήλη 'ypsometro' υπάρχει ήδη ({e})")
                conn.rollback()
            
            # Προσθήκη νέων GDD στόχων
            try:
                conn.execute(text("ALTER TABLE ktimata ADD COLUMN gdd_target_anthisi INTEGER DEFAULT 600"))
                conn.commit()
                print("✅ Προστέθηκε η στήλη 'gdd_target_anthisi'")
            except Exception as e:
                print(f"ℹ️ Η στήλη 'gdd_target_anthisi' υπάρχει ήδη ή σφάλμα: {e}")
                conn.rollback()

            try:
                conn.execute(text("ALTER TABLE ktimata ADD COLUMN gdd_target_sygkomidi INTEGER DEFAULT 2500"))
                conn.commit()
                print("✅ Προστέθηκε η στήλη 'gdd_target_sygkomidi'")
            except Exception as e:
                print(f"ℹ️ Η στήλη 'gdd_target_sygkomidi' υπάρχει ήδη ή σφάλμα: {e}")
                conn.rollback()

            # --- Ενημέρωση Πίνακα Εργασιών (Ergasies) ---
            try:
                conn.execute(text("ALTER TABLE ergasies ADD COLUMN proelevsi VARCHAR(50) DEFAULT 'Αγρότης'"))
                conn.commit()
                print("✅ Προστέθηκε η στήλη 'proelevsi' στον πίνακα 'ergasies'")
            except Exception as e:
                print(f"ℹ️ Η στήλη 'proelevsi' υπάρχει ήδη στον πίνακα 'ergasies' ({e})")
                conn.rollback()

            # --- Ενημέρωση Πίνακα Χρηστών (Xrhsths) ---
            print("👤 Έλεγχος και ενημέρωση πίνακα χρηστών...")
            
            xrhstes_cols = [
                ("rolos", "VARCHAR(20) DEFAULT 'agroths'"),
                ("afm", "VARCHAR(9)"),
                ("ar_tautotitas", "VARCHAR(20)"),
                ("onoma", "VARCHAR(100)"),
                ("is_verified", "BOOLEAN DEFAULT TRUE"),
                ("ai_auto_ergasies", "BOOLEAN DEFAULT TRUE"),
                ("geoponos_auto_ergasies", "BOOLEAN DEFAULT TRUE")
            ]
            
            for col_name, col_type in xrhstes_cols:
                try:
                    # SQLite specific syntax check or strict try/catch
                    conn.execute(text(f"ALTER TABLE xrhstes ADD COLUMN {col_name} {col_type}"))
                    conn.commit()
                    print(f"✅ Προστέθηκε η στήλη '{col_name}' στον πίνακα 'xrhstes'")
                except Exception as e:
                    # Αγνοούμε το σφάλμα αν η στήλη υπάρχει ήδη
                    err_msg = str(e).lower()
                    if "duplicate column" in err_msg or "already exists" in err_msg:
                        print(f"ℹ️ Η στήλη '{col_name}' υπάρχει ήδη.")
                    else:
                        print(f"ℹ️ Σφάλμα κατά την προσθήκη της '{col_name}': {e}")
                    conn.rollback()

            # --- Ενημέρωση Πίνακα Ποικιλιών Κτήματος (KtimaPoikilia) ---
            try:
                conn.execute(text("ALTER TABLE ktima_poikilies ADD COLUMN ilikia_dentron VARCHAR(50)"))
                conn.commit()
                print("✅ Προστέθηκε η στήλη 'ilikia_dentron' στον πίνακα 'ktima_poikilies'")
            except Exception as e:
                print(f"ℹ️ Η στήλη 'ilikia_dentron' υπάρχει ήδη στον πίνακα 'ktima_poikilies' ({e})")
                conn.rollback()

            conn.commit()
            print("🚀 Η βάση δεδομένων είναι έτοιμη!")

if __name__ == "__main__":
    update_db()