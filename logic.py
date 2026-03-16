import os
import time
from datetime import datetime, timedelta
from core import vasi, efarmogi, ai_client
from models import Ktima, Ergasia, Exodo, Xrhsths, AnalysiEdafous
from geoponika import pare_kairo, pare_prognosi_kairou, geoponikos_elegxos, steile_email, get_epoxikes_ergasies, get_agro_soil_data, get_agro_uvi, ypologismos_anagkon_nerou

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

    # Αντιμετώπιση Ψύχους / Παγετού με Αμινοξέα
    if thermokrasia <= 4:
        days_since_amino, _ = get_last_task_info('Αμινοξ')
        days_since_copper, _ = get_last_task_info('Χαλκ')
        
        can_apply_amino = True
        if days_since_copper is not None and days_since_copper <= 7:
            can_apply_amino = False
            
        if days_since_amino is not None and days_since_amino <= 15:
            protaseis.append(f"🛡️ Αντιπαγετική Προστασία: Τα δέντρα προστατεύονται από τα αμινοξέα/φύκια που εφαρμόσατε πριν {days_since_amino} ημέρες. Δεν απαιτείται άμεσα νέα εφαρμογή.")
        elif can_apply_amino:
            protaseis.append("❄️ Στρες Ψύχους: Λόγω χαμηλών θερμοκρασιών (<= 4°C), προτείνεται άμεσα διαφυλλικός ψεκασμός με Αμινοξέα και Εκχυλίσματα Φυκιών για την ανάρρωση των δέντρων.")
        else:
            protaseis.append(f"❄️ Στρες Ψύχους: Τα δέντρα χρειάζονται αμινοξέα για ανάρρωση, ΑΛΛΑ ρίξατε χαλκό πριν {days_since_copper} μέρες. Περιμένετε να περάσουν 7 μέρες συνολικά για να αποφύγετε τοξικότητα!")

    # Αντιμετώπιση Καύσωνα με Καολίνη / Ζεόλιθο (Τωρινός ή Επερχόμενος)
    prognosi_kauswna = False
    prognosi_all = pare_prognosi_kairou(ktima.geografiko_platos, ktima.geografiko_mikos)
    if prognosi_all:
        for p in prognosi_all:
            if p['main']['temp'] >= 35:
                prognosi_kauswna = True
                break

    if thermokrasia >= 35 or prognosi_kauswna:
        days_since_kaolin, _ = get_last_task_info('Καολίν')
        days_since_zeolite, _ = get_last_task_info('Ζεόλιθ')
        
        # Βρίσκουμε ποιο από τα δύο εφαρμόστηκε πιο πρόσφατα
        days_list = [d for d in [days_since_kaolin, days_since_zeolite] if d is not None]
        days_since_protection = min(days_list) if days_list else None
        
        if days_since_protection is not None and days_since_protection <= 20:
            protaseis.append(f"🛡️ Αντιθερμική Προστασία: Τα δέντρα προστατεύονται από το θερμικό στρες χάρη στην εφαρμογή καολίνη/ζεόλιθου πριν {days_since_protection} ημέρες.")
        else:
            if thermokrasia >= 35:
                protaseis.append("☀️ Κίνδυνος Καύσωνα: Η θερμοκρασία είναι >= 35°C! Προτείνεται άμεσα ψεκασμός με Καολίνη ή Ζεόλιθο για την αποφυγή ηλιακών εγκαυμάτων.")
            else:
                protaseis.append("⚠️ Επερχόμενος Καύσωνας: Η πρόγνωση (5 ημερών) δείχνει θερμοκρασίες >= 35°C! Προετοιμαστείτε και ψεκάστε με Καολίνη ή Ζεόλιθο προληπτικά.")

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
            if not ktima.analuseis_edafous:
                protaseis.append("🌱 Άνοιξη (Λίπανση): ⚠️ Χωρίς ανάλυση εδάφους, προτείνεται τυπική ισορροπημένη λίπανση. Για μέγιστη απόδοση και οικονομία συνιστάται εδαφοανάλυση!")
            else:
                protaseis.append("🌱 Άνοιξη (Λίπανση): Ιδανική περίοδος για βασική λίπανση (Άζωτο & Βόριο) προσαρμοσμένη στην ανάλυσή σας.")

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
        _, amino_date = get_last_task_info('Αμινοξ') # Check if Amino Acids exist
        
        # Logic: If Amino Acids were applied AFTER Copper, stop warning about the 7-day rule.
        amino_done_after_copper = False
        if copper_date and amino_date and amino_date >= copper_date:
            amino_done_after_copper = True

        if days_since_copper is not None and days_since_copper <= 7 and not amino_done_after_copper:
            protaseis.append(f"✅ Εφαρμόστηκε Χαλκός στις {copper_date.strftime('%d/%m')}. Αποφύγετε αμινοξέα για ακόμα {7 - days_since_copper} ημέρες.")
        elif not amino_done_after_copper:
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
        for diag in reversed(ktima.diagnoseis):
            res = diag.apotelesma or ""
            # Αγνοούμε δορυφόρο, chat και αναλύσεις για να πάρουμε μόνο πραγματικές διαγνώσεις (φωτογραφίες/ασθένειες)
            if not any(k in res for k in ["Δορυφόρος", "🛰️", "Συμπέρασμα AI", "Chat", "📄", "💧", "🌿"]):
                protaseis.append(f"👁️ Μνήμη Διάγνωσης: Το AI είχε εντοπίσει πρόσφατα: {res}. Προσαρμόστε τις ενέργειές σας.")
                break

    # Smart Fertilization Logic
    if ktima.analuseis_edafous:
        teleytaia_analysi = ktima.analuseis_edafous[-1]
        if teleytaia_analysi.ph and teleytaia_analysi.ph > 7.5:
            protaseis.append("⚠️ Υψηλό pH (>7.5): Κίνδυνος έλλειψης Βορίου και Ιχνοστοιχείων. Προτείνεται διαφυλλική εφαρμογή.")

    # --- ΔΟΡΥΦΟΡΙΚΗ ΝΟΗΜΟΣΥΝΗ ---
    # Ελέγχουμε αν υπάρχει πρόσφατη διάγνωση από τον δορυφόρο (τελευταίες 10 μέρες)
    if ktima.diagnoseis:
        for diag in reversed(ktima.diagnoseis):
            result = diag.apotelesma or ""
            if "Δορυφόρος" in result or "🛰️" in result:
                days_ago = (now - diag.imerominia).days
                if days_ago < 10:
                    clean_msg = result.replace('🛰️ Δορυφόρος (Live):', '').replace('🛰️ Δορυφόρος:', '').strip()
                    if len(clean_msg) > 200:
                        protaseis.append(f"🛰️ Δορυφόρος ({days_ago} ημ. πριν): {clean_msg[:200]}...")
                    else:
                        protaseis.append(f"🛰️ Δορυφόρος ({days_ago} ημ. πριν): {clean_msg}")
                break

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
    
    # --- ΝΕΑ ΔΥΝΑΤΟΤΗΤΑ: Προσαρμογή Βάσει Υψομέτρου ---
    if ktima.ypsometro and ktima.ypsometro > 400:
        if mhnas in [3, 4]:
            protaseis.append(f"⛰️ Ορεινό Κτήμα (Υψόμετρο {ktima.ypsometro}m): Η άνθιση και η βλαστική ανάπτυξη αναμένεται να καθυστερήσουν 1-2 εβδομάδες σε σχέση με τα πεδινά. Προσαρμόστε τους ψεκασμούς σας.")
        elif mhnas in [11, 12, 1, 2] and thermokrasia < 5:
            protaseis.append(f"⛰️ Ορεινό Κτήμα (Υψόμετρο {ktima.ypsometro}m): Πολύ υψηλός κίνδυνος παγετού λόγω υψομέτρου.")

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

    # --- ΝΕΑ ΔΥΝΑΤΟΤΗΤΑ: Agromonitoring Live Δεδομένα Εδάφους & UVI ---
    if hasattr(ktima, 'agro_data') and ktima.agro_data:
        soil = ktima.agro_data.get('soil')
        if soil and 'moisture' in soil:
            moisture_val = soil['moisture'] # Μετριέται σε m3/m3
            if moisture_val < 0.20 and mhnas in [5, 6, 7, 8, 9, 10]:
                if ktima.ardefsi == 'Αρδευόμενο':
                    litra = ypologismos_anagkon_nerou(thermokrasia, mhnas, ktima.arithmos_dentron, ktima.stremmata)
                    protaseis.append(f"💧 Κρίσιμη Υγρασία Εδάφους ({moisture_val*100:.1f}%): Απαιτείται άμεση άρδευση. Βάσει θερμοκρασίας, ρίξτε περίπου {litra*4} λίτρα ανά δέντρο (δόση για 4 ημέρες).")
                else:
                    protaseis.append(f"💧 Κρίσιμη Υγρασία Εδάφους Δορυφόρου ({moisture_val*100:.1f}%): Τα αποθέματα νερού στη ριζόσφαιρα εξαντλούνται. Απαιτείται άμεση άρδευση!")
        
        uvi_data = ktima.agro_data.get('uvi')
        if uvi_data and 'uvi' in uvi_data:
            uvi_val = uvi_data['uvi']
            if uvi_val >= 8:
                protaseis.append(f"☀️ Ακραίος Δείκτης UV ({uvi_val:.1f}): Υψηλός κίνδυνος ηλιακού εγκαύματος. ΑΠΑΓΟΡΕΥΟΝΤΑΙ οι ψεκασμοί τις μεσημεριανές ώρες (κίνδυνος φυτοτοξικότητας)!")

    return protaseis

# --- ΝΕΑ ΛΕΙΤΟΥΡΓΙΑ: Κεντρικός Συλλέκτης Δεδομένων για το AI (Holistic Context) ---
def xtise_plires_context(ktima):
    now = datetime.now()
    
    poikilies_analytika = ", ".join([f"{p.poikilia_onoma} ({p.arithmos_dentron} δέντρα)" for p in ktima.poikilies_details]) if ktima.poikilies_details else ktima.poikilia
    
    klisi_str = ktima.klisi or 'Άγνωστη'
    if klisi_str == 'Ρέμα/Κοιλότητα':
        klisi_str += " (ΟΔΗΓΙΑ: Βρίσκεται σε ρέμα/κοιλότητα. Λόγω αναστροφής θερμοκρασίας, αν η θερμοκρασία είναι < 5°C, προειδοποίησε έντονα για υψηλό κίνδυνο παγετού!)"

    analysi_str = "ΔΕΝ ΥΠΑΡΧΕΙ (ΟΔΗΓΙΑ: Πρότεινε τυπική λίπανση/θρέψη βάζοντας την επισήμανση ⚠️ [Τυπική Πρόταση - Συνιστάται Ανάλυση])"
    if ktima.analuseis_edafous:
        last_an = sorted(ktima.analuseis_edafous, key=lambda x: x.imerominia)[-1]
        analysi_str = f"Υπάρχει (Τελευταία: {last_an.imerominia.strftime('%d/%m/%Y')} - N:{last_an.azwto}, P:{last_an.fwsforos}, K:{last_an.kalio}, pH:{last_an.ph})"

    kalliergeia_str = getattr(ktima, 'kalliergeia_typos', 'Συμβατική')
    if kalliergeia_str == 'Βιολογική':
        kalliergeia_str += " (ΟΔΗΓΙΑ ΑΥΣΤΗΡΗ: Το κτήμα είναι ΒΙΟΛΟΓΙΚΟ. Απαγορεύονται αυστηρά τα χημικά ζιζανιοκτόνα (π.χ. Glyphosate), τα χημικά λιπάσματα και τα χημικά εντομοκτόνα. Πρότεινε ΜΟΝΟ εγκεκριμένα βιολογικά σκευάσματα π.χ. Χαλκό, Βάκιλλο, Φυσικό Πύρεθρο, Ζεόλιθο, Κοπριά κλπ.)"

    ctx = (f"--- ΠΡΟΦΙΛ ΚΤΗΜΑΤΟΣ ---\n"
           f"Κτήμα: {ktima.onoma_ktimatos}, Τύπος: {kalliergeia_str}\n"
           f"Ποικιλίες: {poikilies_analytika}, Υψόμετρο: {ktima.ypsometro if ktima.ypsometro else 'Άγνωστο'}m\n"
           f"Τοποθεσία (Lat, Lng): {ktima.geografiko_platos}, {ktima.geografiko_mikos} (ΟΔΗΓΙΑ: Αξιολόγησε τον χάρτη. Αν είναι παραθαλάσσιο με χαμηλό υψόμετρο, προειδοποίησε για κίνδυνο αλατονέφωσης/εγκαυμάτων από νοτιάδες αν ο καιρός είναι κακός.)\n"
           f"Έκταση: {ktima.stremmata} στρ., Δέντρα: {ktima.arithmos_dentron}\n"
           f"Ηλικία: {ktima.ilikia_dentron}, Πυκνότητα: {ktima.puknotita_dentron}\n"
           f"Έδαφος: {ktima.typos_edafous}, Κλίση: {klisi_str}\n"
           f"Ανάλυση Εδάφους: {analysi_str}\n"
           f"Διαχείριση: {ktima.diacheirisi_edafous}, Άρδευση: {ktima.ardefsi}\n"
           f"Στάδιο: {ktima.fainologiko_stadio}, GDD: {ktima.gdd_accumulated if ktima.gdd_accumulated else 0:.0f}\n\n")
           
    kairos = getattr(ktima, 'kairos', None) or pare_kairo(ktima.geografiko_platos, ktima.geografiko_mikos)
    if kairos:
        ctx += f"--- ΚΑΙΡΟΣ & ΔΟΡΥΦΟΡΟΣ (LIVE) ---\nΚαιρός: Θερμοκρασία {kairos['thermokrasia']}°C, Υγρασία {kairos['ygrasia']}%, {kairos['perigrafi']}\n"
        
        # Προσθήκη ανέμου και μετατροπή μοιρών σε κείμενο
        if 'anemos_taxytita' in kairos and 'anemos_dieythinsi' in kairos:
            speed = kairos['anemos_taxytita']
            deg = kairos['anemos_dieythinsi']
            bf = kairos.get('anemos_mpofor', 0)
            directions = ["Βόρειος (Βοριάς)", "Βορειοανατολικός", "Ανατολικός", "Νοτιοανατολικός", "Νότιος (Νοτιάς)", "Νοτιοδυτικός", "Δυτικός", "Βορειοδυτικός"]
            idx = round(deg / 45) % 8
            dir_text = directions[idx]
            ctx += f"Άνεμος: {bf} Μποφόρ ({speed} m/s), Κατεύθυνση: {dir_text} ({deg}°)\n"
            
        # Προσθήκη Οδηγίας Αντιμετώπισης Παγετού
        if kairos['thermokrasia'] <= 4:
            ctx += "ΟΔΗΓΙΑ ΠΑΓΕΤΟΥ: Θερμοκρασία <= 4°C (Στρες Ψύχους). Πρότεινε 'Διαφυλλική εφαρμογή με Αμινοξέα/Φύκια' για ανάρρωση, ΕΚΤΟΣ αν στο Ιστορικό Εργασιών φαίνεται εφαρμογή Χαλκού τις τελευταίες 7 ημέρες (κίνδυνος τοξικότητας) ή Αμινοξέων τις τελευταίες 15 ημέρες.\n"
        
        # --- ΠΡΟΣΘΗΚΗ ΠΡΟΓΝΩΣΗΣ ΚΑΙΡΟΥ ΣΤΟ AI ---
        prognosi = pare_prognosi_kairou(ktima.geografiko_platos, ktima.geografiko_mikos)
        
        # Προσθήκη Οδηγίας Αντιμετώπισης Καύσωνα (Τωρινού ή Επερχόμενου)
        max_forecast_temp = kairos['thermokrasia']
        if prognosi:
            max_forecast_temp = max([p['main']['temp'] for p in prognosi] + [kairos['thermokrasia']])
            
        if max_forecast_temp >= 35:
            ctx += "ΟΔΗΓΙΑ ΚΑΥΣΩΝΑ: Ανιχνεύθηκε θερμοκρασία >= 35°C (Τώρα ή στην Πρόγνωση). Πρότεινε 'Ψεκασμός με Καολίνη ή Ζεόλιθο' για ηλιοπροστασία, ΕΚΤΟΣ αν στο Ιστορικό Εργασιών φαίνεται εφαρμογή Καολίνη/Ζεόλιθου τις τελευταίες 20 ημέρες.\n"

        if prognosi:
            daily_forecast = {}
            for p in prognosi:
                d = p['dt_txt'].split(' ')[0]
                if d not in daily_forecast: daily_forecast[d] = []
                daily_forecast[d].append(p['weather'][0]['description'])
            forecast_summaries = []
            for d, descs in list(daily_forecast.items())[:4]:
                unique_descs = list(set(descs))
                forecast_summaries.append(f"{d[-5:]} ({', '.join(unique_descs)})")
            ctx += "Πρόγνωση (επόμενες 4 ημέρες): " + " | ".join(forecast_summaries) + "\n\n"
        
    agro_data = getattr(ktima, 'agro_data', None)
    if not agro_data and ktima.agromonitoring_poly_id:
        soil = get_agro_soil_data(ktima.agromonitoring_poly_id)
        uvi = get_agro_uvi(ktima.agromonitoring_poly_id)
        if soil or uvi: agro_data = {'soil': soil, 'uvi': uvi}
        
    if agro_data:
        s_data = agro_data.get('soil', {})
        u_data = agro_data.get('uvi', {})
        sm = f"{s_data.get('moisture')*100:.1f}%" if s_data and 'moisture' in s_data else 'N/A'
        uv = u_data.get('uvi', 'N/A') if u_data and 'uvi' in u_data else 'N/A'
        ctx += f"Δορυφόρος (Agromonitoring): Υγρασία Εδάφους (10cm): {sm}, UVI: {uv}\n\n"
        
    if ktima.diagnoseis:
        # Κρατάμε τις πρόσφατες διαγνώσεις, ΑΛΛΑ και τα συμπεράσματα του Onboarding για πάντα!
        recent = [d.apotelesma for d in sorted(ktima.diagnoseis, key=lambda x: x.imerominia, reverse=True) if (now - d.imerominia).days < 45 or "Συμπέρασμα" in d.apotelesma][:5]
        if recent: ctx += f"--- ΙΣΤΟΡΙΚΟ ΠΡΟΒΛΗΜΑΤΩΝ & ΕΥΡΗΜΑΤΑ ---\n{' | '.join(recent)}\n\n"
            
    if ktima.ergasies:
        completed = [f"{e.eidos_ergasias}{' - ' + e.farmaka_lipasmata if e.farmaka_lipasmata else ''} ({e.imerominia.strftime('%d/%m/%Y')})" for e in sorted(ktima.ergasies, key=lambda x: x.imerominia, reverse=True) if not e.archived and e.katastasi == 'Ολοκληρώθηκε'][:15]
        if completed: ctx += f"--- ΙΣΤΟΡΙΚΟ ΕΡΓΑΣΙΩΝ ---\nΤελευταίες Ολοκληρωμένες: {', '.join(completed)}\n\n"
        
        pending = [f"{e.eidos_ergasias} ({e.proelevsi})" for e in ktima.ergasies if not e.archived and e.katastasi == 'Εκκρεμεί']
        if pending: ctx += f"Εκκρεμείς Εργασίες στο σύστημα: {', '.join(pending)}\n\n"
            
    if ktima.idioktitis and ktima.idioktitis.apothiki_items:
        stock = [f"{i.onoma_proiontos}" for i in ktima.idioktitis.apothiki_items]
        if stock: ctx += f"--- ΑΠΟΘΗΚΗ ΥΛΙΚΩΝ ---\nΔιαθέσιμα: {', '.join(stock)}\n"
            
    if ktima.exoda:
        exoda_list = [f"{e.perigrafi}: {e.poso}€ ({e.imerominia.strftime('%d/%m/%Y')})" for e in sorted(ktima.exoda, key=lambda x: x.imerominia, reverse=True) if not e.archived][:10]
        synoliko_kostos = sum([e.poso for e in ktima.exoda if not e.archived])
        if exoda_list:
            ctx += f"--- ΟΙΚΟΝΟΜΙΚΑ / ΕΞΟΔΑ ---\nΣυνολικό Κόστος (Τρέχουσας Σεζόν): {synoliko_kostos}€\nΤελευταία Έξοδα: {', '.join(exoda_list)}\n\n"
            
    return ctx

def generate_smart_tasks(ktima):
    """
    ΝΕΑ ΛΕΙΤΟΥΡΓΙΑ: Συνδυάζει GDD, Δορυφόρο, Καιρό και Αποθήκη για έξυπνες προτάσεις.
    """
    now = datetime.now()
    
    # 1. Έλεγχος Cache (για να μην χρεώνουμε το AI σε κάθε refresh, κρατάμε τη συμβουλή για 1 μέρα)
    if ktima.teleftaia_enimerosi_ergasion and \
       ktima.teleftaia_enimerosi_ergasion.date() == now.date() and \
       ktima.topikes_ergasies:
        return ktima.topikes_ergasies.split('|')

    # 2. Ανάκτηση πλήρους Context
    plires_context = xtise_plires_context(ktima)
    
    kairos = getattr(ktima, 'kairos', None) or pare_kairo(ktima.geografiko_platos, ktima.geografiko_mikos)
    thermokrasia_now = kairos['thermokrasia'] if kairos else 25
    litra_ana_dentro = ypologismos_anagkon_nerou(thermokrasia_now, now.month, ktima.arithmos_dentron, ktima.stremmata)

    # 3. Κατασκευή του Smart Prompt (Ενοποιημένο)
    prompt = (
        f"Είσαι έμπειρος γεωπόνος. Ανάλυσε τα δεδομένα του ελαιώνα και πρότεινε ΟΛΕΣ τις απαραίτητες εργασίες για την τρέχουσα περίοδο.\n"
        f"{plires_context}\n"
        f"--- ΟΔΗΓΙΑ ---\n"
        f"FULL STACK ΠΡΟΣΕΓΓΙΣΗ: Πρότεινε ΟΛΕΣ τις αναγκαίες εργασίες χωρίς περιορισμό στον αριθμό. Αν το ιστορικό είναι κενό, δώσε ένα πλήρες, ολοκληρωμένο πρόγραμμα βέλτιστης υποστήριξης της καλλιέργειας (π.χ. λίπανση, κλάδεμα, ψεκασμοί). Αν ο αγρότης έχει ήδη καταχωρήσει εργασίες (π.χ. έκανε λίπανση), αφαίρεσέ τες θεωρώντας ότι οι ανάγκες του φυτού (π.χ. σε άζωτο/κάλιο) έχουν καλυφθεί επαρκώς.\n"
        f"Λάβε υπόψη τον καιρό, το ιστορικό εργασιών (μην επαναλαμβάνεις πρόσφατες ενέργειες), και τα αποθέματα. Αν το UVI είναι >= 8, ΜΗΝ προτείνεις ψεκασμό. Αν η υγρασία εδάφους είναι πολύ χαμηλή (< 20%), πρότεινε οπωσδήποτε άρδευση (αν είναι εφικτό).\n"
        f"ΒΑΣΙΚΗ ΠΡΟΛΗΨΗ & ΔΟΣΟΛΟΓΙΕΣ: Αν από το 'Ιστορικό Προβλημάτων' προκύπτει ότι πέρυσι υπήρξε έξαρση (π.χ. Δάκος, Κυκλοκόνιο), ΠΡΟΣΑΡΜΟΣΕ το πρόγραμμα κάνοντάς το πιο επιθετικό (π.χ. νωρίτερα ψεκασμοί, ανώτατη επιτρεπτή δόση). Την Άνοιξη (Μάρτιο-Απρίλιο) και το Φθινόπωρο, ο προληπτικός ψεκασμός με Χαλκό/Μυκητοκτόνο για ασθένειες (π.χ. Κυκλοκόνιο) είναι ΥΠΟΧΡΕΩΤΙΚΟΣ. Αν δεν έχει γίνει πρόσφατα, βάλτον στις κορυφαίες προτεραιότητες, εκτός αν το δέντρο ανθίζει.\n"
        f"Αν προτείνεις 'Άρδευση' (επειδή είναι αρδευόμενο και η υγρασία είναι χαμηλή), γράψε δίπλα στην παρένθεση ακριβώς: '({litra_ana_dentro * 4} Λίτρα/δέντρο)' ώστε ο αγρότης να ξέρει τη δοσολογία.\n"
        f"ΣΗΜΑΝΤΙΚΟ: Δίπλα σε ΚΑΘΕ εργασία, γράψε ΥΠΟΧΡΕΩΤΙΚΑ το χρονικό περιθώριο ή τη φαινολογική προϋπόθεση (π.χ. 'έως 15/04' ή 'πριν ανοίξει ο ανθός').\n"
        f"Αν ο χρόνος ή το κατάλληλο στάδιο για μια εργασία έχει ΠΕΡΑΣΕΙ (π.χ. προανθικά ιχνοστοιχεία ενώ το δέντρο ήδη ανθίζει), ΑΦΑΙΡΕΣΕ ΤΗΝ εντελώς από τις προτάσεις σου.\n"
        f"Δώσε ΜΟΝΟ μια λίστα εργασιών χωρισμένη ΑΥΣΤΗΡΑ με το σύμβολο | (κάθετη γραμμή). Μην χρησιμοποιήσεις κόμμα για διαχωρισμό των εργασιών. Χωρίς αρίθμηση ή εισαγωγή.\n"
        f"Παράδειγμα: Ψεκασμός με Χαλκό (έως 20/04) | Λίπανση Βορίου (πριν την άνθιση) | Καθαρισμός Χόρτων (άμεσα)"
    )

    try:
        response = ai_client.models.generate_content(model='gemini-2.5-flash', contents=prompt)
        tasks_str = response.text.strip().replace('\n', '')
        
        # Αποθήκευση στη βάση (Caching)
        ktima.topikes_ergasies = tasks_str
        ktima.teleftaia_enimerosi_ergasion = now
        
        return [t.strip() for t in tasks_str.split('|') if t.strip()]
    except Exception as e:
        print(f"Smart Task AI Error: {e}")
        return get_epoxikes_ergasies(now.month) # Fallback σε στατικές εργασίες

def generate_local_tasks_via_ai(ktima):
    now = datetime.now()
    
    # Check if cache is valid (same month and year)
    if ktima.teleftaia_enimerosi_ergasion and \
       ktima.teleftaia_enimerosi_ergasion.month == now.month and \
       ktima.teleftaia_enimerosi_ergasion.year == now.year and \
       ktima.topikes_ergasies:
        return ktima.topikes_ergasies.split('|')

    # Call AI
    try:
        plires_context = xtise_plires_context(ktima)
        prompt = (
            f"Είσαι ειδικός γεωπόνος. Ο τρέχων μήνας είναι ο {now.month}. Εδώ είναι η πλήρης εικόνα του ελαιώνα:\n{plires_context}\n"
            f"FULL STACK ΠΡΟΣΕΓΓΙΣΗ: Δώσε μου ΜΟΝΟ μια λίστα με ΟΛΕΣ τις απαραίτητες εργασίες για αυτή την περιοχή αυτόν τον μήνα, χωρίς περιορισμό στον αριθμό. "
            f"Αν δεν υπάρχει ιστορικό, δώσε ένα πλήρες πρόγραμμα. Αν έχουν γίνει εργασίες (π.χ. λίπανση), αφαίρεσέ τες θεωρώντας ότι το δέντρο έχει καλυφθεί. "
            f"Χωρισμένες ΑΥΣΤΗΡΑ με το σύμβολο | (κάθετη γραμμή). Μην γράψεις καμία άλλη λέξη ή εισαγωγή. "
            f"Παράδειγμα: Διαχείριση Ζιζανίων | Ψεκασμός με Χαλκό | Βασική Λίπανση"
        )
        
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

        tasks_str = response.text.strip().replace('\n', '')
        
        ktima.topikes_ergasies = tasks_str
        ktima.teleftaia_enimerosi_ergasion = now
        
        return [t.strip() for t in tasks_str.split('|') if t.strip()]
    except Exception as e:
        print(f"AI Task Error: {e}")
        # Fallback to static logic if AI fails
        return get_epoxikes_ergasies(now.month)

# --- ΝΕΑ ΛΕΙΤΟΥΡΓΙΑ: Συγχρονισμός AI (Εκτελείται στη δημιουργία, σε νέες εργασίες και κάθε πρωί) ---
def syghronismos_ai_ktimatos(ktima):
    """
    Διαβάζει όλο το ιστορικό και το context, και ανανεώνει άμεσα 
    τόσο τη 'Συμβουλή' όσο και τις 'Προτεινόμενες Εργασίες' του AI.
    """
    now = datetime.now()
    plires_context = xtise_plires_context(ktima)
    
    prompt = (
        f"Είσαι ο AI Γεωπόνος του Olea. Μελέτησε σχολαστικά τα δεδομένα του κτήματος:\n{plires_context}\n\n"
        f"ΟΔΗΓΙΕΣ:\n"
        f"1. Γράψε μια σύντομη ημερήσια συμβουλή-αξιολόγηση (max 2-3 προτάσεις). Ξεκίνα με τη λέξη 'ΣΥΜΒΟΥΛΗ:'. Αν προτείνεις κάποια εργασία με αυστηρή προθεσμία, ΠΡΟΕΙΔΟΠΟΙΗΣΕ τον αγρότη ξεκάθαρα εδώ (π.χ. 'Μην αμελήσετε τον ψεκασμό βορίου, ο οποίος πρέπει να γίνει αυστηρά πριν ανοίξει ο ανθός!').\n"
        f"2. FULL STACK ΠΡΟΣΕΓΓΙΣΗ: Πρότεινε ΟΛΕΣ τις απαραίτητες επόμενες εργασίες χωρίς περιορισμό. Αν δεν υπάρχει ιστορικό, δώσε ένα ολοκληρωμένο πρόγραμμα βέλτιστης υποστήριξης. Αν υπάρχουν ολοκληρωμένες εργασίες στο ιστορικό (π.χ. βασική λίπανση), ΜΗΝ τις προτείνεις ξανά, θεωρώντας ότι το έδαφος έχει πλέον αποθέματα.\n"
        f"ΒΑΣΙΚΗ ΠΡΟΛΗΨΗ & ΔΟΣΟΛΟΓΙΕΣ: Αν από το ιστορικό προκύπτει ότι πέρυσι υπήρξε σοβαρό πρόβλημα (π.χ. Δάκος, ασθένειες), ΠΡΟΣΑΡΜΟΣΕ το πρόγραμμα προληπτικά (πιο συχνοί ψεκασμοί, ανώτατη δόση). Την Άνοιξη (Μάρτιο-Απρίλιο) ο ψεκασμός με Χαλκό/Μυκητοκτόνο είναι κρίσιμος. Αν δεν υπάρχει στο ιστορικό, πρόσθεσέ τον οπωσδήποτε στις εργασίες.\n"
        f"ΓΙΑ ΚΑΘΕ ΕΡΓΑΣΙΑ πρέπει να γράφεις σε παρένθεση ΠΟΤΕ πρέπει να γίνει (π.χ. 'έως 10/05' ή 'οπωσδήποτε πριν την άνθιση'). "
        f"Αν μια εργασία έχει χάσει το ιδανικό της παράθυρο βάσει καιρού ή σταδίου (π.χ. ιχνοστοιχεία που έπρεπε να μπουν πριν ανθίσει, αλλά τώρα ανθίζει), ΑΦΑΙΡΕΣΕ ΤΗΝ ΟΡΙΣΤΙΚΑ. "
        f"Γράψε τες σε μια λίστα χωρισμένη ΑΥΣΤΗΡΑ ΜΟΝΟ με το σύμβολο | (κάθετη γραμμή), ξεκινώντας με τη λέξη 'ΕΡΓΑΣΙΕΣ:'.\n"
        f"3. ΕΡΩΤΗΣΗ ΠΡΟΣ ΑΓΡΟΤΗ: ΕΛΕΓΞΕ ΠΡΩΤΑ το 'ΙΣΤΟΡΙΚΟ ΠΡΟΒΛΗΜΑΤΩΝ & ΕΥΡΗΜΑΤΑ'. Αν υπάρχουν ήδη 'Συμπεράσματα AI' από προηγούμενες απαντήσεις (π.χ. για περσινό δάκο, ασθένειες, τρέχον στάδιο), ΑΠΑΓΟΡΕΥΕΤΑΙ ΑΥΣΤΗΡΑ να τον ξαναρωτήσεις τα ίδια! Αν ΔΕΝ του έχεις ξαναμιλήσει (άδειο ιστορικό συζητήσεων) και δεν έχει καταχωρημένες εργασίες, κάνε το αρχικό onboarding (Ξεκίνα με: 'ΕΡΩΤΗΣΗ: Καλώς ήρθατε!...'). Διαφορετικά, αν έχει ήδη απαντήσει σε βασικά ερωτήματα, ΜΗΝ κάνεις άλλη ερώτηση (άφησε το κενό), ΠΑΡΑ ΜΟΝΟ αν προέκυψε μια ΝΕΑ, πολύ συγκεκριμένη απορία (π.χ. μέσο ψεκασμού). ΑΠΑΓΟΡΕΥΕΤΑΙ ΑΥΣΤΗΡΑ να ρωτάς για τον καιρό, προβλέψεις βροχής ή πράγματα που μόλις σου απάντησε.\n"
        f"Παράδειγμα απάντησης:\n"
        f"ΣΥΜΒΟΥΛΗ: Οι συνθήκες είναι ιδανικές. Η υγρασία είναι καλή αλλά προσοχή στον δάκο.\n"
        f"ΕΡΓΑΣΙΕΣ: Ψεκασμός για Δάκο (έως 15/06) | Καθαρισμός Χόρτων (άμεσα) | Διαφυλλική Λίπανση (πριν ανοίξει ο ανθός)\n"
        f"ΕΡΩΤΗΣΗ: Για την καλύτερη προσέγγιση, απάντησέ μου: Το κόκκινο χρώμα στον χάρτη στο βόρειο τμήμα, αφορά γυμνό έδαφος ή είναι ξερά δέντρα;"
    )
    
    try:
        response = ai_client.models.generate_content(model='gemini-2.5-flash', contents=prompt)
        if not response or not response.text:
            return
            
        text = response.text.strip()
        symvouli = ""
        ergasies = ""
        erotisi = ""
        
        import re
        symvouli_match = re.search(r'ΣΥΜΒΟΥΛΗ:(.*?)(?=ΕΡΓΑΣΙΕΣ:|ΕΡΩΤΗΣΗ:|$)', text, re.DOTALL)
        ergasies_match = re.search(r'ΕΡΓΑΣΙΕΣ:(.*?)(?=ΕΡΩΤΗΣΗ:|$)', text, re.DOTALL)
        erotisi_match = re.search(r'ΕΡΩΤΗΣΗ:(.*?)$', text, re.DOTALL)
        
        if symvouli_match: symvouli = symvouli_match.group(1).strip().replace('\n', ' ')
        if ergasies_match: ergasies = ergasies_match.group(1).strip().replace('\n', '')
        if erotisi_match: erotisi = erotisi_match.group(1).strip()
                
        if symvouli:
            ktima.ai_sumvouli_cache = symvouli
            ktima.ai_sumvouli_date = now
            
        if ergasies:
            ktima.topikes_ergasies = ergasies
            ktima.teleftaia_enimerosi_ergasion = now
            
        if erotisi:
            ktima.ekkremis_erotisi_ai = erotisi
            
        vasi.session.commit()
    except Exception as e:
        print(f"Σφάλμα AI Συγχρονισμού Κτήματος ({ktima.id}): {e}")
        vasi.session.rollback()

# Αυτοματοποιημένος Έλεγχος (Background Job)
def aytomatizomenos_elegxos():
    with efarmogi.app_context():
        print("🔄 Εκτέλεση αυτοματοποιημένου ελέγχου πρόγνωσης...")
        import requests # Εισαγωγή για τον έλεγχο GDD
        xrhstes = Xrhsths.query.all()
        for xrhsths in xrhstes:
            for ktima in xrhsths.ktimata:
                # Λήψη πρόγνωσης 5 ημερών
                prognosi = pare_prognosi_kairou(ktima.geografiko_platos, ktima.geografiko_mikos)
                
                if prognosi:
                    # ΑΥΤΟΜΑΤΗ ΔΙΟΡΘΩΣΗ GDD ΚΑΘΗΜΕΡΙΝΑ (Re-calc από 1η Ιανουαρίου για ακρίβεια)
                    try:
                        now = datetime.now()
                        start_date = f"{now.year}-01-01"
                        yesterday = (now - timedelta(days=1)).strftime('%Y-%m-%d')
                        
                        # Ανάκτηση ιστορικού καιρού για όλη τη χρονιά μέχρι χθες
                        hist_url = f"https://archive-api.open-meteo.com/v1/archive?latitude={ktima.geografiko_platos}&longitude={ktima.geografiko_mikos}&start_date={start_date}&end_date={yesterday}&daily=temperature_2m_max,temperature_2m_min&timezone=auto"
                        resp = requests.get(hist_url, timeout=10)
                        
                        if resp.status_code == 200:
                            data = resp.json().get('daily', {})
                            t_max = data.get('temperature_2m_max', [])
                            t_min = data.get('temperature_2m_min', [])
                            
                            # Υπολογισμός Accumulation (Base 10C για ελιά)
                            total_gdd = sum([((mx + mn)/2.0 - 10.0) for mx, mn in zip(t_max, t_min) if mx is not None and mn is not None and ((mx + mn)/2.0 > 10.0)])
                            ktima.gdd_accumulated = total_gdd
                            vasi.session.commit()
                    except Exception as e:
                        print(f"Daily GDD Sync Error {ktima.id}: {e}")
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

                # --- ΗΜΕΡΗΣΙΟΣ ΣΥΓΧΡΟΝΙΣΜΟΣ AI ---
                try:
                    syghronismos_ai_ktimatos(ktima)
                    print(f"✅ AI Ενημερώθηκε για το: {ktima.onoma_ktimatos}")
                except Exception as e:
                    print(f"⚠️ Σφάλμα ημερήσιου AI συγχρονισμού: {e}")

def ypologismos_isozugiou_npk(ktima):
    """
    ΝΕΟ: Δυναμικός Υπολογισμός Ισοζυγίου Θρεπτικών Στοιχείων NPK.
    """
    if not ktima.analuseis_edafous:
        return None
    
    sorted_analyses = sorted(ktima.analuseis_edafous, key=lambda x: x.imerominia)
    last_analysi = sorted_analyses[-1]
    
    current_n = float(last_analysi.azwto or 0)
    current_p = float(last_analysi.fwsforos or 0)
    current_k = float(last_analysi.kalio or 0)
    
    if current_n == 0 and current_p == 0 and current_k == 0:
        return None
        
    start_date = last_analysi.imerominia
    end_date = datetime.now() + timedelta(days=30) # Προβολή 1 μήνα στο μέλλον
    
    if start_date.year == end_date.year and start_date.month == end_date.month:
        start_date = start_date - timedelta(days=90) # Τουλάχιστον ένα τρίμηνο ιστορικό
        
    labels = []
    data_n = []
    data_p = []
    data_k = []
    
    current_date = datetime(start_date.year, start_date.month, 1)
    
    while current_date <= end_date:
        month_str = current_date.strftime('%m/%Y')
        m = current_date.month
        
        # --- 1. Φυσική Απόσβεση (Καιρός & Έδαφος) ---
        dep_n = 2.0 if m in [3, 4, 5, 11, 12] else 0.8
        if ktima.typos_edafous == 'Αμμώδες': dep_n *= 1.5
        elif ktima.typos_edafous == 'Αργιλώδες': dep_n *= 0.7
        
        dep_p = 0.3
        
        dep_k = 2.5 if m in [7, 8, 9, 10] else 0.5
        if ktima.ardefsi == 'Αρδευόμενο': dep_k *= 1.2
        
        current_n = max(0, current_n - dep_n)
        current_p = max(0, current_p - dep_p)
        current_k = max(0, current_k - dep_k)
        
        # --- 2. Ενισχύσεις από Εργασίες ---
        for t in ktima.ergasies:
            if t.katastasi == 'Ολοκληρώθηκε' and t.imerominia.year == current_date.year and t.imerominia.month == current_date.month:
                eidos = t.eidos_ergasias.lower()
                farmaka = (t.farmaka_lipasmata or '').lower()
                
                if 'λίπανση' in eidos:
                    current_n += 15.0
                    current_p += 5.0
                    current_k += 10.0
                if 'καταστροφέας' in eidos or 'χόρτα' in eidos:
                    current_n += 3.0
                if 'κλάδεμα' in eidos and 'θρυμματισμός' in farmaka:
                    current_k += 5.0
                    
        # --- 3. AI Εντοπισμός Τροφοπενιών (Από φωτογραφίες) ---
        for d in ktima.diagnoseis:
            if d.imerominia.year == current_date.year and d.imerominia.month == current_date.month:
                res = (d.apotelesma or '').lower()
                if 'έλλειψη αζώτου' in res or 'τροφοπενία αζώτου' in res:
                    current_n *= 0.5 # 50% πτώση της καμπύλης αν εντοπιστεί τροφοπενία
                if 'έλλειψη καλίου' in res or 'τροφοπενία καλίου' in res:
                    current_k *= 0.5
        
        labels.append(month_str)
        data_n.append(round(current_n, 1))
        data_p.append(round(current_p, 1))
        data_k.append(round(current_k, 1))
        
        if current_date.month == 12:
            current_date = datetime(current_date.year + 1, 1, 1)
        else:
            current_date = datetime(current_date.year, current_date.month + 1, 1)
            
    return {
        'labels': labels,
        'datasets': {
            'N': data_n,
            'P': data_p,
            'K': data_k
        }
    }