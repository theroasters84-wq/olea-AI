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
                print("✅ Προστέθηκε η στήλη 'topikes_ergasies'")
            except Exception as e:
                print(f"ℹ️ Η στήλη 'topikes_ergasies' υπάρχει ήδη ({e})")
                conn.rollback()

            # Προσθήκη στήλης teleftaia_enimerosi_ergasion
            try:
                conn.execute(text("ALTER TABLE ktimata ADD COLUMN teleftaia_enimerosi_ergasion TIMESTAMP"))
                print("✅ Προστέθηκε η στήλη 'teleftaia_enimerosi_ergasion'")
            except Exception as e:
                print(f"ℹ️ Η στήλη 'teleftaia_enimerosi_ergasion' υπάρχει ήδη ({e})")
                conn.rollback()

            # Προσθήκη στήλης fainologiko_stadio
            try:
                conn.execute(text("ALTER TABLE ktimata ADD COLUMN fainologiko_stadio VARCHAR(50) DEFAULT 'Άγνωστο'"))
                print("✅ Προστέθηκε η στήλη 'fainologiko_stadio'")
            except Exception as e:
                print(f"ℹ️ Η στήλη 'fainologiko_stadio' υπάρχει ήδη ({e})")
                conn.rollback()

            # Προσθήκη στήλης nero_ph
            try:
                conn.execute(text("ALTER TABLE ktimata ADD COLUMN nero_ph FLOAT"))
                print("✅ Προστέθηκε η στήλη 'nero_ph'")
            except Exception as e:
                print(f"ℹ️ Η στήλη 'nero_ph' υπάρχει ήδη ({e})")
                conn.rollback()

            # Προσθήκη στήλης nero_agwgimotita
            try:
                conn.execute(text("ALTER TABLE ktimata ADD COLUMN nero_agwgimotita FLOAT"))
                print("✅ Προστέθηκε η στήλη 'nero_agwgimotita'")
            except Exception as e:
                print(f"ℹ️ Η στήλη 'nero_agwgimotita' υπάρχει ήδη ({e})")
                conn.rollback()

            # Προσθήκη στήλης gdd_accumulated (ΝΕΟ)
            try:
                conn.execute(text("ALTER TABLE ktimata ADD COLUMN gdd_accumulated FLOAT DEFAULT 0.0"))
                print("✅ Προστέθηκε η στήλη 'gdd_accumulated'")
            except Exception as e:
                print(f"ℹ️ Η στήλη 'gdd_accumulated' υπάρχει ήδη ({e})")
                conn.rollback()

            # Προσθήκη στήλης ai_sumvouli_cache
            try:
                conn.execute(text("ALTER TABLE ktimata ADD COLUMN ai_sumvouli_cache TEXT"))
                print("✅ Προστέθηκε η στήλη 'ai_sumvouli_cache'")
            except Exception as e:
                print(f"ℹ️ Η στήλη 'ai_sumvouli_cache' υπάρχει ήδη ({e})")
                conn.rollback()

            # Προσθήκη στήλης ai_sumvouli_date
            try:
                conn.execute(text("ALTER TABLE ktimata ADD COLUMN ai_sumvouli_date TIMESTAMP"))
                print("✅ Προστέθηκε η στήλη 'ai_sumvouli_date'")
            except Exception as e:
                print(f"ℹ️ Η στήλη 'ai_sumvouli_date' υπάρχει ήδη ({e})")
                conn.rollback()

            # Προσθήκη στήλης polygon_geojson
            try:
                conn.execute(text("ALTER TABLE ktimata ADD COLUMN polygon_geojson TEXT"))
                print("✅ Προστέθηκε η στήλη 'polygon_geojson'")
            except Exception as e:
                print(f"ℹ️ Η στήλη 'polygon_geojson' υπάρχει ήδη ({e})")
                conn.rollback()
            
            # Προσθήκη νέων GDD στόχων
            try:
                conn.execute(text("ALTER TABLE ktimata ADD COLUMN gdd_target_anthisi INTEGER DEFAULT 600"))
                print("✅ Προστέθηκε η στήλη 'gdd_target_anthisi'")
            except Exception as e:
                print(f"ℹ️ Η στήλη 'gdd_target_anthisi' υπάρχει ήδη ή σφάλμα: {e}")
                conn.rollback()

            try:
                conn.execute(text("ALTER TABLE ktimata ADD COLUMN gdd_target_sygkomidi INTEGER DEFAULT 2500"))
                print("✅ Προστέθηκε η στήλη 'gdd_target_sygkomidi'")
            except Exception as e:
                print(f"ℹ️ Η στήλη 'gdd_target_sygkomidi' υπάρχει ήδη ή σφάλμα: {e}")
                conn.rollback()

            conn.commit()
            print("🚀 Η βάση δεδομένων είναι έτοιμη!")

if __name__ == "__main__":
    update_db()