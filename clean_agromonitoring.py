import os
import requests
from core import efarmogi, vasi
from models import Ktima

def clean_orphaned_polygons():
    api_key = os.getenv('AGROMONITORING_API_KEY')
    if not api_key:
        print("❌ Δεν βρέθηκε το AGROMONITORING_API_KEY στο .env")
        return

    with efarmogi.app_context():
        # 1. Βρίσκουμε όλα τα ID που είναι ΑΠΟΘΗΚΕΥΜΕΝΑ στη βάση μας
        active_ktimata = Ktima.query.filter(Ktima.agromonitoring_poly_id.isnot(None)).all()
        local_poly_ids = [k.agromonitoring_poly_id for k in active_ktimata]
        
        print(f"🔍 Βρέθηκαν {len(local_poly_ids)} ενεργά πολύγωνα στην τοπική βάση δεδομένων.")
        
        # 2. Φέρνουμε ΟΛΑ τα πολύγωνα από τον λογαριασμό Agromonitoring
        print("📡 Επικοινωνία με Agromonitoring API...")
        res = requests.get(f"http://api.agromonitoring.com/agro/1.0/polygons?appid={api_key}", timeout=10)
        
        if res.status_code != 200:
            print(f"❌ Σφάλμα επικοινωνίας: {res.status_code} - {res.text}")
            return
            
        remote_polygons = res.json()
        print(f"🛰️ Βρέθηκαν {len(remote_polygons)} πολύγωνα συνολικά στον λογαριασμό σας στο Agromonitoring.")
        
        # 3. Βρίσκουμε τα "Ορφανά" (αυτά που υπάρχουν στο API αλλά ΟΧΙ στη βάση μας)
        orphans = [p for p in remote_polygons if p.get('id') not in local_poly_ids]
        
        if not orphans:
            print("✅ Όλα είναι τέλεια συγχρονισμένα! Δεν υπάρχουν 'ορφανά' πολύγωνα για διαγραφή.")
            return
            
        print(f"\n⚠️ ΕΝΤΟΠΙΣΤΗΚΑΝ {len(orphans)} 'ΟΡΦΑΝΑ' ΠΟΛΥΓΩΝΑ (Παλιά/Διαγραμμένα):")
        for idx, p in enumerate(orphans):
            print(f"  {idx+1}. Όνομα: {p.get('name', 'Άγνωστο')} | ID: {p.get('id')} | Έκταση: {p.get('area', 0):.2f} εκτάρια")
            
        # 4. Ερώτηση για διαγραφή
        apantisi = input(f"\nΘέλετε να διαγραφούν οριστικά αυτά τα {len(orphans)} πολύγωνα για να καθαρίσει ο λογαριασμός σας; (ναι/οχι): ")
        
        if apantisi.lower() in ['ναι', 'nai', 'yes', 'y', 'ν']:
            print("🗑️ Έναρξη διαγραφής...")
            success_count = 0
            for p in orphans:
                poly_id = p.get('id')
                del_res = requests.delete(f"http://api.agromonitoring.com/agro/1.0/polygons/{poly_id}?appid={api_key}", timeout=10)
                if del_res.status_code == 204:
                    print(f"  ✅ Διαγράφηκε: {p.get('name')} ({poly_id})")
                    success_count += 1
                else:
                    print(f"  ❌ Αποτυχία διαγραφής: {p.get('name')} (Status: {del_res.status_code})")
            
            print(f"\n🎉 Ολοκληρώθηκε! Καθαρίστηκαν {success_count}/{len(orphans)} πολύγωνα.")
        else:
            print("Ακύρωση διαγραφής.")

if __name__ == '__main__':
    print("="*50)
    print("🧹 Εργαλείο Εκκαθάρισης Agromonitoring")
    print("="*50)
    clean_orphaned_polygons()