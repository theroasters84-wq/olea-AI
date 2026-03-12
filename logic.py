import os
import time
from datetime import datetime, timedelta
from core import vasi, efarmogi, ai_client
from models import Ktima, Ergasia, Exodo, Xrhsths, AnalysiEdafous
from geoponika import pare_kairo, pare_prognosi_kairou, geoponikos_elegxos, steile_email, get_epoxikes_ergasies

# Προληπτικός Σύμβουλος (Εγκυκλοπαίδεια)
def paragwgi_protasewn(ktima, thermokrasia, ygrasia, perigrafi):
    mhnas = datetime.now().month
    protaseis = []
    now = datetime.now()

    # Helper to find days since last specific task
    def get_last_task_info(keyword):
        relevant_tasks = [
            t for t in ktima.ergasies 
            if not t.archived and (keyword in t.eidos_ergasias or (t.farmaka_lipasmata and keyword in t.farmaka_lipasmata))
        ]
        if not relevant_tasks:
            return None, None
        latest_task = max(relevant_tasks, key=lambda x: x.imerominia)
        return (now - latest_task.imerominia).days, latest_task.imerominia

    # Get a list of completed tasks for the current season (for simple existence checks)
    completed_tasks_names = [e.eidos_ergasias for e in ktima.ergasies if not e.archived]

    # Phase 18: Agronomic Profiling Rules
    if ktima.klisi == 'Επικλινές/Πλαγιά' and ('βροχή' in perigrafi.lower() or 'βροχη' in perigrafi.lower()):
        protaseis.append("⚠️ Κλίση & Βροχή: Κίνδυνος έκπλυσης λιπάσματος. Αποφύγετε τη λίπανση πριν τη βροχή.")

    if ktima.typos_edafous == 'Αργιλώδες' and ('βροχή' in perigrafi.lower() or 'βροχη' in perigrafi.lower()):
        protaseis.append("⚠️ Αργιλώδες Έδαφος: Κίνδυνος ασφυξίας ριζών λόγω νεροκρατήματος. Ελέγξτε την αποστράγγιση.")

    if ktima.ardefsi == 'Ξηρικό' and thermokrasia > 30:
        protaseis.append("🔥 Ξηρικό & Ζέστη: Αποφύγετε το βαθύ όργωμα για να μην χαθεί η πολύτιμη υγρασία του εδάφους.")

    if ktima.klisi == 'Ρέμα/Κοιλότητα' and thermokrasia < 5 and mhnas in [12, 1, 2, 3]:
        protaseis.append("❄️ Ρέμα/Κοιλότητα: Αυξημένος κίνδυνος παγετού (frost pocket).")

    # Water Quality Rules
    if ktima.nero_agwgimotita and ktima.nero_agwgimotita > 3.0:
         protaseis.append("⚠️ Τοξικότητα Αλάτων: Η αγωγιμότητα του νερού είναι πολύ υψηλή (>3.0 mS/cm). Κίνδυνος ξηράνσεων στα φύλλα. Συνιστάται έκπλυση εδάφους ή χρήση βελτιωτικών.")

    # Soil Moisture Stress - Safely check for records
    if ktima.ugrasies:
        try:
            # Accessing the relationship triggers the lazy load.
            # If the collection is empty, [-1] will raise an IndexError.
            latest_moisture = ktima.ugrasies[-1].pososto
            if latest_moisture < 20 and mhnas in [6, 7, 8, 9]:
                protaseis.append(f"💧 Έντονο Υδατικό Στρες: Η υγρασία εδάφους είναι στο {latest_moisture}%. Απαιτείται άμεση άρδευση για να μην συρρικνωθεί ο καρπός.")
        except IndexError:
            # This is expected if no moisture records exist yet. Safely ignore.
            pass

    # Weather-Aware Fertilization (Months 2, 3, 4)
    if mhnas in [2, 3, 4]:
        if 'βροχή' not in perigrafi.lower() and 'βροχη' not in perigrafi.lower():
            protaseis.append("⚠️ Ανομβρία: Αν προγραμματίζετε επιφανειακή αζωτούχο λίπανση, προτιμήστε υδρολίπανση ή αναμείνατε βροχοπτώσεις για να μην εξατμιστεί το άζωτο.")

    # Άνοιξη (Μάρτιος, Απρίλιος)
    if mhnas in [3, 4]:
        # Fertilization check (Time-Aware: 60 days)
        days_since_fert, _ = get_last_task_info('Λίπανση')
        if days_since_fert is None:
             days_since_fert, _ = get_last_task_info('Άζωτο')

        if days_since_fert is None or days_since_fert > 60:
            protaseis.append("🌱 Άνοιξη: Ιδανική περίοδος για βασική λίπανση (Άζωτο & Βόριο).")

        # Pruning check
        has_pruned = any('Κλάδεμα' in task for task in completed_tasks_names)
        if not has_pruned:
            protaseis.append("✂️ Άνοιξη: Ολοκληρώστε το κλάδεμα διαμόρφωσης και καρποφορίας.")

        # --- MODIFIED COPPER/SPRAY LOGIC ---
        # Phenological stage takes precedence over simple humidity/time rules.
        if ktima.fainologiko_stadio == 'Άνθιση':
            protaseis.append("🛑 ΑΠΑΓΟΡΕΥΣΗ ΨΕΚΑΣΜΩΝ: Το δέντρο βρίσκεται σε Άνθιση! Σταματήστε ΑΜΕΣΩΣ κάθε ψεκασμό (ειδικά με χαλκό ή διαφυλλικά) για να μην προκαλέσετε κάψιμο των ανθέων και πτώση της παραγωγής.")
        elif ktima.fainologiko_stadio == 'Σχηματισμός Ταξιανθιών':
            days_since_copper, _ = get_last_task_info('Χαλκ')
            if days_since_copper is None or days_since_copper > 25:
                protaseis.append("⚠️ Κρίσιμο Στάδιο: Τα δέντρα είναι στο 'μούρο' (Σχηματισμός Ταξιανθιών) και η προστασία του χαλκού έχει λήξει. Απαιτείται άμεσα ψεκασμός πριν ανοίξουν τα άνθη.")
        # Fallback to original time/humidity logic if stage is not critical (e.g., 'Άγνωστο', 'Λήθαργος')
        elif ygrasia > 65:
            days_since_copper, _ = get_last_task_info('Χαλκ')
            if days_since_copper is not None:
                if days_since_copper <= 25:
                    protaseis.append(f"🛡️ Ενεργή Προστασία: Υψηλή υγρασία, αλλά ο ελαιώνας προστατεύεται από τον χαλκό που εφαρμόστηκε πριν {days_since_copper} μέρες.")
                else:
                    protaseis.append(f"⚠️ Λήξη Προστασίας: Έχουν περάσει {days_since_copper} μέρες από τον τελευταίο ψεκασμό χαλκού. Η δράση του έχει εξασθενήσει. Λόγω υγρασίας, απαιτείται επαναληπτικός ψεκασμός.")
            else:
                protaseis.append("💧 Υψηλή υγρασία: Συνιστάται προληπτικός ψεκασμός με χαλκούχα για το Κυκλοκόνιο.")
        
        days_since_copper, copper_date = get_last_task_info('Χαλκ')
        if days_since_copper is not None and days_since_copper <= 7:
            protaseis.append(f"✅ Εφαρμόστηκε Χαλκός στις {copper_date.strftime('%d/%m')}. Αποφύγετε αμινοξέα για ακόμα {7 - days_since_copper} ημέρες.")
        else:
            protaseis.append("⚠️ Προσοχή στους ψεκασμούς: ΜΗΝ αναμειγνύετε ποτέ χαλκό με αμινοξέα (κίνδυνος φυτοτοξικότητας)!")
    
    # Άνθιση / Αρχές Καλοκαιριού (Μάιος, Ιούνιος)
    elif mhnas in [5, 6]:
        if ktima.fainologiko_stadio == 'Άνθιση':
             protaseis.append("🌼 Περίοδος Άνθισης/Μούρου: ΑΠΑΓΟΡΕΥΕΤΑΙ η χρήση χαλκού (καίει το άνθος). Προγραμματίστε καταπολέμηση ζιζανίων.")
    
    # Καλοκαίρι (Ιούλιος, Αύγουστος)
    elif mhnas in [7, 8]:
        protaseis.append("☀️ Καλοκαίρι: Κρίσιμη περίοδος για άρδευση (πήξη πυρήνα).")
            
    # Φθινόπωρο / Χειμώνας (Σεπτέμβριος - Φεβρουάριος)
    elif mhnas in [9, 10, 11, 12, 1, 2]:
        protaseis.append("🍂 Ελαιογένεση/Συγκομιδή: Έμφαση στο Κάλιο. Μετά τη συγκομιδή ή χαλάζι/παγετό, ψεκάστε άμεσα με χαλκό για απολύμανση πληγών.")

    # Scientific Memory: Boron & Temperature Rule (Refactored for performance and safety)
    if thermokrasia < 12:
        days_since_boron, _ = get_last_task_info('Βόριο')
        if days_since_boron is not None:
            protaseis.append("🛡️ Κάλυψη Βορίου: Επόμενος έλεγχος σε 15-20 ημέρες.")
        elif days_since_boron is None or days_since_boron > 25:
            protaseis.append("📊 Επιστημονική Μνήμη: Η θερμοκρασία είναι < 12°C. Προτείνεται εφαρμογή Βορίου, καθώς η απορρόφησή του είναι μειωμένη σε χαμηλές θερμοκρασίες και μπορεί να χρειαστεί επανάληψη.")

    # Spray Countdown & Reminder
    days_since_spray, _ = get_last_task_info('Ψεκασμός')
    if days_since_spray is not None:
        if days_since_spray <= 12:
            protaseis.append(f"⏳ Επόμενος ψεκασμός σε ~{12 - days_since_spray} ημέρες.")
        else:
            protaseis.append("🎯 Επαναληπτικός Ψεκασμός: Έχουν περάσει πάνω από 12 ημέρες. Απαιτείται νέα προληπτική κάλυψη.")

    # Smart Dacus Management (June - October)
    if mhnas in [6, 7, 8, 9, 10]:
        if thermokrasia >= 34:
            protaseis.append("☀️ Καύσωνας & Δάκος: Η θερμοκρασία ξεπερνά τους 34°C. ΑΠΑΓΟΡΕΥΕΤΑΙ ο ψεκασμός. Ο πληθυσμός του δάκου καταρρέει φυσικά από τη ζέστη. Εξοικονομήστε χρήματα και φάρμακα!")
        elif 20 <= thermokrasia <= 30 and ygrasia > 60 and ktima.fainologiko_stadio in ['Ανάπτυξη Καρπού', 'Ωρίμανση']:
            protaseis.append("🪰 Κίνδυνος Δάκου: Οι τρέχουσες συνθήκες (δροσιά και υγρασία) είναι ιδανικές για δακοπροσβολή στον καρπό. Ελέγξτε άμεσα τις παγίδες σας και προγραμματίστε δολωματικό ψεκασμό αν τα επίπεδα είναι υψηλά.")

    # Adaptive Memory from Diagnosis
    if ktima.diagnoseis:
        teleytaia_diagnosi = ktima.diagnoseis[-1]
        protaseis.append(f"👁️ Μνήμη Διάγνωσης: Το AI είχε εντοπίσει πρόσφατα: {teleytaia_diagnosi.apotelesma}. Προσαρμόστε τις ενέργειές σας.")

    # Smart Fertilization Logic
    if ktima.analuseis_edafous:
        teleytaia_analysi = ktima.analuseis_edafous[-1]
        if teleytaia_analysi.ph and teleytaia_analysi.ph > 7.5:
            protaseis.append("⚠️ Υψηλό pH (>7.5): Κίνδυνος έλλειψης Βορίου και Ιχνοστοιχείων. Προτείνεται διαφυλλική εφαρμογή.")

    # GDD Model Logic (Precision Agriculture)
    gdd = ktima.gdd_accumulated or 0.0
    if 140 <= gdd <= 160:
        protaseis.append("🎯 Κρίσιμη Ειδοποίηση (Ακρίβεια GDD): Βάσει των Βαθμοημερών της περιοχής, ξεκινά η εκκόλαψη της ανθόβιας γενιάς του Πυρηνοτρήτη. Έχετε 3-4 ημέρες για το μέγιστο αποτέλεσμα ψεκασμού.")
    elif 300 <= gdd <= 330:
        protaseis.append("🎯 Κρίσιμη Ειδοποίηση (Ακρίβεια GDD): Έναρξη της καρπόβιας γενιάς του Πυρηνοτρήτη! Προστατέψτε τους νεαρούς καρπούς.")
    elif gdd > 800 and mhnas in [6, 7, 8]:
        protaseis.append("🎯 Κρίσιμη Ειδοποίηση (Ακρίβεια GDD): Η συσσωρευμένη θερμότητα (GDD) ευνοεί την έναρξη των καλοκαιρινών γενεών του Δάκου. Αυξήστε την επιτήρηση με παγίδες.")

    # --- ΝΕΑ ΔΥΝΑΤΟΤΗΤΑ: Προστασία Βάσει Ηλικίας ---
    if ktima.ilikia_dentron == 'Νεαρά (1-5 ετών)':
        # Αν ο σύμβουλος πρότεινε κλάδεμα καρποφορίας, το διορθώνουμε
        protaseis = [p for p in protaseis if "κλάδεμα διαμόρφωσης και καρποφορίας" not in p]
        if mhnas in [2, 3]:
            protaseis.append("🌱 Νεαρά Δέντρα: Απαγορεύεται το αυστηρό κλάδεμα καρποφορίας. Περιοριστείτε σε ελαφρύ καθάρισμα διαμόρφωσης.")
    
    # --- ΝΕΑ ΔΥΝΑΤΟΤΗΤΑ: Έξυπνος Έλεγχος Αποθήκης ---
    # Ελέγχουμε αν ο χρήστης έχει στην αποθήκη τα υλικά που προτείνει ο σύμβουλος
    if ktima.idioktitis and ktima.idioktitis.apothiki_items:
        required_materials = []
        if any("Χαλκ" in p for p in protaseis): required_materials.append(("Χαλκό", "χαλκ"))
        if any("Βόριο" in p for p in protaseis): required_materials.append(("Βόριο", "βόρι"))
        if any("Δάκο" in p for p in protaseis): required_materials.append(("Εντομοκτόνο/Δόλωμα", "δάκ"))

        for mat_name, keyword in required_materials:
            has_stock = any(keyword in item.onoma_proiontos.lower() or keyword in item.eidos.lower() for item in ktima.idioktitis.apothiki_items)
            if not has_stock:
                protaseis.append(f"🛒 Λίστα Αγορών: Ο σύμβουλος πρότεινε {mat_name}, αλλά δεν βρέθηκε σχετικό προϊόν στην Αποθήκη σας.")

    return protaseis

def generate_local_tasks_via_ai(ktima):
    now = datetime.now()
    
    # Check if cache is valid (same month and year)
    if ktima.teleftaia_enimerosi_ergasion and \
       ktima.teleftaia_enimerosi_ergasion.month == now.month and \
       ktima.teleftaia_enimerosi_ergasion.year == now.year and \
       ktima.topikes_ergasies:
        return ktima.topikes_ergasies.split(',')

    # Call AI
    try:
        prompt = (f"Είσαι ειδικός γεωπόνος. Το ελαιόκτημα βρίσκεται στις συντεταγμένες {ktima.geografiko_platos}, {ktima.geografiko_mikos} στην Ελλάδα "
                  f"(υπολόγισε το τοπικό μικροκλίμα, π.χ. παραθαλάσσιο vs ορεινό). Ο τρέχων μήνας είναι ο {now.month}. "
                  f"Δώσε μου ΜΟΝΟ μια λίστα με τις 3-5 απολύτως απαραίτητες εργασίες για αυτή την περιοχή αυτόν τον μήνα, "
                  f"χωρισμένες με κόμμα (,). Μην γράψεις καμία άλλη λέξη ή εισαγωγή. "
                  f"Παράδειγμα: Διαχείριση Ζιζανίων,Ψεκασμός με Χαλκό,Βασική Λίπανση")
        
        # Retry Logic
        response = None
        for attempt in range(3):
            try:
                response = ai_client.models.generate_content(model='gemini-2.5-flash', contents=prompt)
                break
            except Exception:
                time.sleep(2)
        
        if not response:
            # Fallback αν αποτύχει το AI
            return get_epoxikes_ergasies(now.month)

        tasks_str = response.text.strip().replace('\n', '').replace('.', '')
        
        ktima.topikes_ergasies = tasks_str
        ktima.teleftaia_enimerosi_ergasion = now
        vasi.session.commit()
        
        return tasks_str.split(',')
    except Exception as e:
        print(f"AI Task Error: {e}")
        vasi.session.rollback()
        # Fallback to static logic if AI fails
        return get_epoxikes_ergasies(now.month)

# Αυτοματοποιημένος Έλεγχος (Background Job)
def aytomatizomenos_elegxos():
    with efarmogi.app_context():
        print("🔄 Εκτέλεση αυτοματοποιημένου ελέγχου πρόγνωσης...")
        xrhstes = Xrhsths.query.all()
        for xrhsths in xrhstes:
            for ktima in xrhsths.ktimata:
                # Λήψη πρόγνωσης 5 ημερών
                prognosi = pare_prognosi_kairou(ktima.geografiko_platos, ktima.geografiko_mikos)
                
                if prognosi:
                    # GDD Calculation (Improved: (Tmax + Tmin) / 2 - Tbase)
                    try:
                        # Παίρνουμε τις προβλέψεις του επόμενου 24ωρου (8 διαστήματα των 3 ωρών)
                        next_24h = prognosi[:8]
                        temps = [item['main']['temp'] for item in next_24h]
                        t_max = max(temps)
                        t_min = min(temps)
                        
                        avg_daily_temp = (t_max + t_min) / 2
                        if avg_daily_temp > 9.0:
                            ktima.gdd_accumulated = (ktima.gdd_accumulated or 0.0) + (avg_daily_temp - 9.0)
                            vasi.session.commit()
                    except Exception as e:
                        print(f"GDD Error {ktima.id}: {e}")
                        vasi.session.rollback()

                    apeiles = []
                    
                    # Έλεγχος κάθε 3ωρου διαστήματος
                    for stoixeio in prognosi:
                        thermokrasia = stoixeio['main']['temp']
                        ygrasia = stoixeio['main']['humidity']
                        dt_txt = stoixeio['dt_txt'] # Ημερομηνία και ώρα πρόβλεψης
                        
                        elegxos = geoponikos_elegxos(thermokrasia, ygrasia)
                        
                        # Αν υπάρχει κίνδυνος (κόκκινο ή πορτοκαλί), το καταγράφουμε
                        if elegxos['xroma'] in ['red', 'orange']:
                            apeiles.append(f"🕒 {dt_txt}: {thermokrasia}°C, {ygrasia}%. -> {elegxos['minima']}")
                    
                    # Αν βρέθηκαν απειλές, στέλνουμε ΕΝΑ συγκεντρωτικό email
                    if apeiles:
                        thema = f"⚠️ ΠΡΟΕΙΔΟΠΟΙΗΣΗ ΠΡΟΓΝΩΣΗΣ: {ktima.onoma_ktimatos}"
                        keimeno = f"Προσοχή! Εντοπίστηκαν επικίνδυνες συνθήκες για τις επόμενες ημέρες στο κτήμα '{ktima.onoma_ktimatos}':\n\n" + "\n".join(apeiles) + "\n\nΠαρακαλούμε λάβετε τα απαραίτητα μέτρα.\n\nΜε εκτίμηση,\nΗ ομάδα του Olea AI"
                        
                        if steile_email(xrhsths.email, thema, keimeno):
                            print(f"✅ Στάλθηκε email πρόγνωσης στον {xrhsths.email} για το {ktima.onoma_ktimatos}")