from core import efarmogi, vasi
from models import Xrhsths

def set_geoponos_role(email):
    print(f"🔍 Αναζήτηση χρήστη: {email}...")
    with efarmogi.app_context():
        user = Xrhsths.query.filter_by(email=email).first()
        if user:
            user.rolos = 'geoponos'
            # Προαιρετικά: Ορίζουμε και ένα όνομα αν λείπει
            if not user.onoma:
                user.onoma = "Γεωπόνος Διαχειριστής"
            vasi.session.commit()
            print(f"✅ Επιτυχία! Ο χρήστης {email} έχει πλέον πρόσβαση στο Dashboard Γεωπόνου.")
        else:
            print(f"❌ Σφάλμα: Δεν βρέθηκε λογαριασμός με το email '{email}'. Κάντε πρώτα εγγραφή.")

if __name__ == "__main__":
    email_input = input("Δώσε το email του χρήστη που θέλεις να κάνεις Γεωπόνο: ")
    set_geoponos_role(email_input.strip())