import os
import time
import json
from datetime import datetime, timedelta
from core import vasi, efarmogi, ai_client
from models import Ktima, Ergasia, Exodo, Xrhsths, AnalysiEdafous
from geoponika import pare_kairo, pare_prognosi_kairou, geoponikos_elegxos, steile_email, get_epoxikes_ergasies, get_agro_soil_data, get_agro_uvi, ypologismos_anagkon_nerou, pare_istoriko_kairou, evaluate_spraying_window, check_spraying_status
from google.genai import types

# Προληπτικός Σύμβουλος (Εγκυκλοπαίδεια)
def paragwgi_protasewn(ktima, thermokrasia, ygrasia, perigrafi):
    mhnas = datetime.now().month
    protaseis = []
    now = datetime.now()

    # Helper to find days since last specific task
    def get_last_task_info(keyword):
        relevant_tasks = [
            t for t in ktima.ergasies            if not t.archived and t.katastasi == 'Ολοκληρώθηκε' and (keyword in t.eidos_ergasias or (t.farmaka_lipasmata and keyword in t.farmaka_lipasmata))
        ]
        if not relevant_tasks:
            return None, None
        latest_task = max(relevant_tasks, key=lambda x: x.imerominia)
        return (now - latest_task.imerominia).days, latest_task.imerominia

    # Get a list of completed tasks for the current season
    completed_tasks_names = [e.eidos_ergasias for e in ktima.ergasies if not e.archived and e.katastasi == 'Ολοκληρώθηκε']

    # Υπολογισμός μνήμης ποτίσματος (Τελευταίες 7 ημέρες)
    days_since_potisma, _ = get_last_task_info('Πότισμ')
    days_since_ardefsi, _ = get_last_task_info('Άρδευσ')
    water_days_list = [d for d in [days_since_potisma, days_since_ardefsi] if d is not None]
    days_since_water = min(water_days_list) if water_days_list else None
        
    # Υπολογισμός μνήμης ζιζανίων (Τελευταίες 45 ημέρες)
    days_since_horta, _ = get_last_task_info('χόρτ')
    days_since_zizan, _ = get_last_task_info('ζιζάν')
    days_since_katastrof, _ = get_last_task_info('καταστροφ')
    weed_days_list = [d for d in [days_since_horta, days_since_zizan, days_since_katastrof] if d is not None]
    days_since_weed_management = min(weed_days_list) if weed_days_list else None
    recent_weeds_managed = days_since_weed_management is not None and days_since_weed_management <= 45

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
            protaseis.append(f"🛡️ Αντιθερμική Προστασία: Τα δέντρα προστατεύονται από το θερμικό στρες χάρη στην εφαρμογή καολίνης/ζεόλιθου πριν {days_since_protection} ημέρες.")
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
                if days_since_water is not None and days_since_water <= 7:
                    protaseis.append(f"💧 Υγρασία: Η τελευταία μέτρηση ήταν {latest_moisture}%, αλλά καταγράψατε πότισμα πριν {days_since_water} ημέρες. Αναμένουμε τη νέα μέτρηση.")
                else:
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
                protaseis.append("⚠️ Κρίσιμο Στάδιο: Τα δέντρα είναι στο 'μούρο' (Σχηματισμός Ταξιανθιών) - κοντεύουν να ανθίσουν! Αν απαιτείται ψεκασμός, πρέπει να γίνει ΑΜΕΣΑ. Μόλις ανοίξουν τα άνθη, απαγορεύεται ΑΥΣΤΗΡΑ κάθε ψεκασμός (θα τα κάψει).")
        # Fallback to original time/humidity logic if stage is not critical (e.g., 'Άγνωστο', 'Λήθαργος')
        elif ygrasia > 65:
            days_since_copper, _ = get_last_task_info('Χαλκ')
            if days_since_copper is not None:
                if days_since_copper <= 25:
                    protaseis.append(f"🛡️ Ενεργή Προστασία: Υψηλή υγρασία, αλλά ο ελαιώνας προστατεύεται από τον χαλκό που εφαρμόστηκε πριν {days_since_copper} ημέρες.")
                else:
                    protaseis.append(f"⚠️ Λήξη Προστασίας: Έχουν περάσει {days_since_copper} ημέρες από τον τελευταίο ψεκασμό χαλκού. Απαιτείται επαναληπτικός ψεκασμός. ΠΡΟΣΟΧΗ: Λόγω άνοιξης, επιλέξτε αυστηρά ήπιο χαλκό (π.χ. υδροξείδιο) ή μυκητοκτόνο για να μην καεί η νέα βλάστηση.")
            else:
                protaseis.append("💧 Υψηλή υγρασία: Συνιστάται προληπτικός ψεκασμός με μυκητοκτόνα ή ήπια χαλκούχα για το Κυκλοκόνιο (αποφύγετε αυστηρά τον καυστικό βορδιγάλειο πολτό την άνοιξη).")
        
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
             msg = "🌼 Περίοδος Άνθισης/Μούρου: ΑΠΑΓΟΡΕΥΕΤΑΙ η χρήση χαλκού (καίει το άνθος)."
             if not recent_weeds_managed:
                 msg += " Προγραμματίστε καταπολέμηση ζιζανίων."
             protaseis.append(msg)
    
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
                
    # --- ΝΕΟ: Πρόβλεψη Άνθισης μέσω Forecast GDD ---
    gdd = ktima.gdd_accumulated or 0.0
    forecasted_gdd = gdd
    if prognosi_all:
        daily_temps = {}
        for p in prognosi_all:
            d = p['dt_txt'].split(' ')[0]
            if d not in daily_temps: daily_temps[d] = []
            daily_temps[d].append(p['main']['temp'])
        for d, temps in daily_temps.items():
            d_gdd = ((max(temps) + min(temps)) / 2.0) - 10.0
            if d_gdd > 0: forecasted_gdd += d_gdd
            
    target_anth = getattr(ktima, 'gdd_target_anthisi', 600) or 600
    if gdd < target_anth and forecasted_gdd >= target_anth - 15 and ktima.fainologiko_stadio != 'Άνθιση':
        protaseis.append(f"🌺 Πρόβλεψη Άνθισης (GDD): Βάσει της πρόγνωσης θερμοκρασιών, τα δέντρα θα πιάσουν τον στόχο άνθισης στις επόμενες 5 ημέρες! Προγραμματίστε ή σταματήστε ΑΜΕΣΑ τους όποιους ψεκασμούς.")

    # --- ΝΕΟ: Αξιολόγηση Παραθύρου Ψεκασμού βάσει Ποικιλίας & GDD ---
    poikilia_display = ktima.poikilia if ktima.poikilia else 'Άγνωστη'
    spray_status = evaluate_spraying_window(gdd, poikilia_display)
    if not spray_status["can_spray"]:
        protaseis.append(f"🛑 ΑΠΑΓΟΡΕΥΣΗ ΨΕΚΑΣΜΩΝ (GDD): {spray_status['reason']}")

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
                if days_since_water is not None and days_since_water <= 7:
                    protaseis.append(f"💧 Δορυφόρος: Δείχνει χαμηλή υγρασία ({moisture_val*100:.1f}%), αλλά επειδή ποτίσατε πριν {days_since_water} ημέρες, το έδαφος ίσως δεν έχει στραγγίσει/ενημερωθεί. Μην ποτίσετε ξανά άμεσα.")
                else:
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
        if ktima.analysi_dedomena and ktima.analysi_dedomena != 'None':
            clean_dedomena = ktima.analysi_dedomena.replace('\n', ' ')
            analysi_str += f" | Αναλυτικά Συμπεράσματα Εργαστηρίου: {clean_dedomena}"
                
    analysi_fyllon_str = "ΔΕΝ ΥΠΑΡΧΕΙ"
    if hasattr(ktima, 'analuseis_fyllon') and ktima.analuseis_fyllon:
        last_leaf = sorted(ktima.analuseis_fyllon, key=lambda x: x.imerominia)[-1]
        analysi_fyllon_str = f"Υπάρχει (Τελευταία: {last_leaf.imerominia.strftime('%d/%m/%Y')} - N:{last_leaf.azwto_fyllo}, P:{last_leaf.fwsforos_fyllo}, K:{last_leaf.kalio_fyllo}, B:{last_leaf.vorio_fyllo}, Zn:{last_leaf.pseydargyros_fyllo}) (ΟΔΗΓΙΑ: Δώσε έμφαση στα επίπεδα Βορίου και Ψευδαργύρου για τη λίπανση/θρέψη)"

    kalliergeia_str = getattr(ktima, 'kalliergeia_typos', 'Συμβατική')
    if kalliergeia_str == 'Βιολογική':
        kalliergeia_str += " (ΟΔΗΓΙΑ ΑΥΣΤΗΡΗ: Το κτήμα είναι ΒΙΟΛΟΓΙΚΟ. Απαγορεύονται αυστηρά τα χημικά ζιζανιοκτόνα (π.χ. Glyphosate), τα χημικά λιπάσματα και τα χημικά εντομοκτόνα. Πρότεινε ΜΟΝΟ εγκεκριμένα βιολογικά σκευάσματα π.χ. Χαλκό, Βάκιλλο, Φυσικό Πύρεθρο, Ζεόλιθο, Κοπριά κλπ.)"
        
    ardefsi_str = ktima.ardefsi or 'Άγνωστη'
    
    recent_water_tasks = [e for e in ktima.ergasies if not e.archived and e.katastasi == 'Ολοκληρώθηκε' and ('Πότισμ' in e.eidos_ergasias or 'Άρδευσ' in e.eidos_ergasias)]
    if recent_water_tasks:
        last_w = sorted(recent_water_tasks, key=lambda x: x.imerominia)[-1]
        days_w = (now - last_w.imerominia).days
        if days_w <= 7:
            ardefsi_str += f" (ΓΝΩΣΗ AI: Ο αγρότης ΠΟΤΙΣΕ το κτήμα πριν από {days_w} ημέρες. ΑΓΝΟΗΣΕ ΤΕΛΕΙΩΣ τυχόν χαμηλές ενδείξεις υγρασίας δορυφόρου, διότι ο δορυφόρος θέλει μέρες να ενημερωθεί. ΑΠΑΓΟΡΕΥΕΤΑΙ να του προτείνεις νέο πότισμα σήμερα!)"
            
    if 'ΓΝΩΣΗ AI' not in ardefsi_str and ardefsi_str == 'Αρδευόμενο':
        ardefsi_str += " (ΟΔΗΓΙΑ: Το κτήμα είναι ΑΡΔΕΥΟΜΕΝΟ. Δώσε ΠΡΩΤΕΥΟΥΣΑ ΣΗΜΑΣΙΑ στην Υδρολίπανση έναντι της κλασικής κοκκώδους λίπανσης εδάφους, καθώς είναι πιο άμεση, οικονομική και αποδοτική.)"
    elif ardefsi_str == 'Αρδευόμενο':
        ardefsi_str += " (ΟΔΗΓΙΑ: Το κτήμα είναι ΑΡΔΕΥΟΜΕΝΟ. Δώσε ΠΡΩΤΕΥΟΥΣΑ ΣΗΜΑΣΙΑ στην Υδρολίπανση.)"

    # --- ΝΕΟ: ΕΞΥΠΝΕΣ ΟΔΗΓΙΕΣ ΓΙΑ ΖΙΖΑΝΙΑ / ΧΟΡΤΑ ---
    diacheirisi_edafous_str = ktima.diacheirisi_edafous or 'Άγνωστη'
    recent_weed_tasks = [e for e in ktima.ergasies if not e.archived and e.katastasi == 'Ολοκληρώθηκε' and any(keyword in e.eidos_ergasias.lower() for keyword in ['χόρτ', 'ζιζάν', 'καταστροφ'])]
    if recent_weed_tasks:
        last_weed = sorted(recent_weed_tasks, key=lambda x: x.imerominia)[-1]
        days_weed = (now - last_weed.imerominia).days
        if days_weed <= 45:
            diacheirisi_edafous_str += f" (ΓΝΩΣΗ AI: Ο αγρότης ΕΚΟΨΕ Ή ΨΕΚΑΣΕ τα χόρτα πριν από {days_weed} ημέρες. ΑΠΑΓΟΡΕΥΕΤΑΙ ΑΥΣΤΗΡΑ να του προτείνεις ξανά 'Κοπή Χόρτων', 'Καταστροφέα' ή 'Ψεκασμό Ζιζανίων'. Το έδαφος είναι ήδη καθαρό!)"

    # --- ΝΕΟ: ΕΞΥΠΝΕΣ ΟΔΗΓΙΕΣ ΦΑΙΝΟΛΟΓΙΚΟΥ ΣΤΑΔΙΟΥ ---
    stadio = ktima.fainologiko_stadio or 'Άγνωστο'
    stadio_odigia = ""
    if stadio in ['Σχηματισμός Ταξιανθιών', 'Πριν την άνθιση', 'Κρόκιασμα', 'Μούρο']:
        stadio_odigia = " (ΟΔΗΓΙΑ ΣΤΑΔΙΟΥ: Κρίσιμη περίοδος ΠΡΙΝ ανοίξει το άνθος. Αν προτείνεις οποιονδήποτε ψεκασμό, ΤΟΝΙΣΕ ΟΤΙ ΠΡΕΠΕΙ ΝΑ ΓΙΝΕΙ ΑΜΕΣΑ πριν ανοίξουν τα άνθη. Αν τα άνθη είναι έτοιμα να ανοίξουν, ΜΗΝ προτείνεις ψεκασμό, καθώς υπάρχει κίνδυνος να τα κάψει!)"
    elif stadio == 'Άνθιση':
        stadio_odigia = " (ΟΔΗΓΙΑ ΣΤΑΔΙΟΥ: ΚΡΙΣΙΜΟΣ ΣΥΝΑΓΕΡΜΟΣ! Το δέντρο είναι σε πλήρη Άνθιση. ΑΠΑΓΟΡΕΥΕΤΑΙ ΑΥΣΤΗΡΑ ΚΑΙ ΔΙΑ ΡΟΠΑΛΟΥ να προτείνεις οποιονδήποτε ψεκασμό (ειδικά χαλκό ή διαφυλλικά λιπάσματα) γιατί θα κάψει τα άνθη και θα καταστρέψει την παραγωγή. Αν χρειάζεται λίπανση, πρότεινε μόνο από εδάφους ή υδρολίπανση.)"
        #TODO ADVICE
        
    elif stadio in ['Καρπόδεση', 'Ανάπτυξη Καρπού']:
        stadio_odigia = " (ΟΔΗΓΙΑ ΣΤΑΔΙΟΥ: Περίοδος ανάπτυξης. Προτεραιότητα σε Άρδευση και Άζωτο. Προσοχή στην έναρξη γενεών Δάκου και Πυρηνοτρήτη.)"
    elif stadio in ['Σκλήρυνση Πυρήνα', 'Ωρίμανση']:
        stadio_odigia = " (ΟΔΗΓΙΑ ΣΤΑΔΙΟΥ: Έμφαση σε Κάλιο για ελαιογένεση και αυστηρή παρακολούθηση Δάκου/Γλοιοσπορίου.)"
    elif stadio == 'Άγνωστο' and now.month in [3, 4, 5]:
        stadio_odigia = " (ΟΔΗΓΙΑ ΣΤΑΔΙΟΥ: Είναι Άνοιξη και το στάδιο είναι ΑΓΝΩΣΤΟ! Υπάρχει τεράστιος κίνδυνος να βρίσκονται σε άνθιση. ΠΡΙΝ προτείνεις ψεκασμούς, ζήτα ΟΠΩΣΔΗΠΟΤΕ φωτογραφία!)"

    ctx = (
        f"--- ΠΡΟΦΙΛ ΚΤΗΜΑΤΟΣ ---\n"
        f"Κτήμα: {ktima.onoma_ktimatos}, Τύπος: {kalliergeia_str}\n"
        f"Ποικιλίες: {poikilies_analytika}, Υψόμετρο: {ktima.ypsometro if ktima.ypsometro else 'Άγνωστο'}m (Απόσταση από θάλασσα: {ktima.thalassa_apostash if ktima.thalassa_apostash else 'Άγνωστη'} χλμ)\n"
        f"Τοποθεσία (Lat, Lng): {ktima.geografiko_platos}, {ktima.geografiko_mikos} (ΟΔΗΓΙΑ: Αξιολόγησε τον χάρτη. Αν είναι παραθαλάσσιο με χαμηλό υψόμετρο, προειδοποίησε για κίνδυνο αλατονέφωσης/εγκαυμάτων από νοτιάδες αν ο καιρός είναι κακός.)\n"
        f"Έκταση: {ktima.stremmata} στρ., Δέντρα: {ktima.arithmos_dentron}\n"
        f"Ηλικία: {ktima.ilikia_dentron} (ΟΔΗΓΙΑ: Προσάρμοσε ΑΥΣΤΗΡΑ τις ποσότητες φαρμάκων, λιπασμάτων και νερού βάσει αυτής της ηλικίας! Αναζήτησε στο internet τις δοσολογίες. Τα νεαρά δέντρα απαιτούν μικρότερο ψεκαστικό υγρό και προσοχή στην τοξικότητα σε σχέση με τα γηραιά.), Πυκνότητα: {ktima.puknotita_dentron}\n"
        f"Έδαφος: {ktima.typos_edafous}, Κλίση: {klisi_str}\n"
        f"Ανάλυση Εδάφους: {analysi_str}\n"
        f"Ανάλυση Φύλλων: {analysi_fyllon_str}\n"
        f"Διαχείριση: {diacheirisi_edafous_str}, Άρδευση: {ardefsi_str}\n"
        f"Στάδιο: {stadio}{stadio_odigia}, Τρέχοντα GDD: {ktima.gdd_accumulated if ktima.gdd_accumulated else 0:.0f} (Στόχος Άνθισης GDD: ~{ktima.gdd_target_anthisi}, Στόχος Συγκομιδής GDD: ~{ktima.gdd_target_sygkomidi})\n"
        f"ΟΔΗΓΙΑ GDD & ΣΤΑΔΙΟΥ: Διασταύρωσε υποχρεωτικά αν το δηλωμένο 'Στάδιο' συμβαδίζει με τα 'Τρέχοντα GDD'. Αν υπάρχει προφανής αναντιστοιχία (π.χ. τα GDD δείχνουν άνθιση αλλά το στάδιο είναι Λήθαργος), επισήμανέ το ξεκάθαρα.\n\n"
    )

    # --- ΝΕΟ: Ενσωμάτωση δυναμικού GDD Context στο System Prompt των AI Agents ---
    gdd_val = ktima.gdd_accumulated if ktima.gdd_accumulated else 0.0
    poikilia_val = ktima.poikilia if ktima.poikilia else "Κορωνέικη"
    spray_status = check_spraying_status(gdd_val, poikilia_val)
    ctx += (
        f"SYSTEM CONTEXT UPDATE: The current farm has {poikilia_val}. The current GDD is {gdd_val:.1f}. "
        f"Spraying allowed: {spray_status['can_spray']}. Reason: {spray_status['reason']}. "
        f"Advise the user strictly based on this agronomic data if they ask about spraying.\n\n"
    )

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
            if bf > 4 or speed > 6:
                ctx += "ΟΔΗΓΙΑ ΑΝΕΜΟΥ: ΠΡΟΣΟΧΗ, ο άνεμος είναι ισχυρός (>4 Μποφόρ). Αν ο αγρότης ΠΡΕΠΕΙ υποχρεωτικά να ψεκάσει (λόγω στενών χρονικών περιθωρίων π.χ. άνθιση ή επίθεση δάκου), προειδοποίησέ τον έντονα για τον κίνδυνο αερομεταφοράς (drift) και συμβούλεψέ τον να ψεκάσει νωρίς τα ξημερώματα/αργά το σούρουπο ή με μπεκ χοντρής σταγόνας. ΜΗΝ του απαγορεύσεις τον ψεκασμό αν η ασθένεια/εχθρός είναι σε κρίσιμο στάδιο.\n"
            
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
            ctx += "ΟΔΗΓΙΑ ΚΑΥΣΩΝΑ: Ανιχνεύθηκε θερμοκρασία >= 35°C (Τώρα ή στην Πρόγνωση). Πρότεινε 'Ψεκασμός με Καολίνη ή Ζεόλιθο' για ηλιοπροστασία, ΕΚΤΟΣ αν στο Ιστορικό Εργασιών φαίνεται εφαρμογή Καολίνης/Ζεόλιθου τις τελευταίες 20 ημέρες.\n"

        if prognosi:
            daily_forecast = {}
            for p in prognosi:
                d = p['dt_txt'].split(' ')[0]
                if d not in daily_forecast: daily_forecast[d] = {'descs': [], 'temps': []}
                daily_forecast[d]['descs'].append(p['weather'][0]['description'])
                daily_forecast[d]['temps'].append(p['main']['temp'])
                
            forecast_summaries = []
            forecasted_gdd_total = ktima.gdd_accumulated if ktima.gdd_accumulated else 0.0
            for d, data in list(daily_forecast.items())[:5]:
                unique_descs = list(set(data['descs']))
                t_max, t_min = max(data['temps']), min(data['temps'])
                daily_gdd = ((t_max + t_min) / 2.0) - 10.0
                if daily_gdd > 0: forecasted_gdd_total += daily_gdd
                forecast_summaries.append(f"{d[-5:]} ({', '.join(unique_descs)}, T: {t_min:.0f}-{t_max:.0f}°C)")
                
            ctx += "Πρόγνωση (επόμενες 5 ημέρες): " + " | ".join(forecast_summaries) + "\n"
            ctx += f"Πρόβλεψη GDD: Βάσει πρόγνωσης, τα GDD αναμένεται να φτάσουν τα {forecasted_gdd_total:.0f} σε 5 ημέρες. Αν ο αριθμός πλησιάζει τον 'Στόχο Άνθισης' (~{ktima.gdd_target_anthisi}), ΠΡΟΕΙΔΟΠΟΙΗΣΕ τον αγρότη για το πότε περίπου αναμένεται να ανοίξουν τα άνθη!\n\n"
            
        # Προσθήκη Ιστορικού Καιρού (ώστε το AI να θυμάται αν έβρεξε τις τελευταίες 5 μέρες)
        istoriko = pare_istoriko_kairou(ktima.geografiko_platos, ktima.geografiko_mikos)
        if istoriko:
            hist_str = " | ".join([f"{h['date'][-5:]}: {h['rain_mm']}mm βροχή (Max {h['t_max']}°C, Min {h['t_min']}°C)" for h in istoriko])
            ctx += "Ιστορικό Καιρού (Παρελθόν 5 ημερών): " + hist_str + "\n\n"
        
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
        
    if getattr(ktima, 'pagides', None):
        recent_traps = [p for p in ktima.pagides if (now - p.imerominia).days <= 15]
        if recent_traps:
            trap_str = ", ".join([f"{p.eidos_entomou}: {p.arithmos_syllipsewn} άτομα ({p.imerominia.strftime('%d/%m')})" for p in recent_traps])
            ctx += f"--- ΠΑΓΙΔΕΣ ΕΝΤΟΜΩΝ (Τελευταίες 15 ημέρες) ---\nΚαταγραφές: {trap_str}\n(ΟΔΗΓΙΑ: Πρότεινε ψεκασμό βάσει αυτού του πραγματικού πληθυσμού εντόμων, εφόσον υπερβαίνει τα όρια οικονομικής ζημιάς).\n\n"

    if ktima.arxeia_sygkomidis:
        last_harvest = sorted(ktima.arxeia_sygkomidis, key=lambda x: x.imerominia)[-1]
        # Εντοπισμός υπερπαραγωγής (>= 40 κιλά/δέντρο) για να οριστεί η φετινή ως χρονιά ξεκούρασης
        if last_harvest.imerominia.year >= now.year - 1 and last_harvest.kila_ana_dentro and last_harvest.kila_ana_dentro >= 40:
            ctx += "ΟΔΗΓΙΑ ΠΑΡΕΝΙΑΥΤΟΦΟΡΙΑΣ: Πέρυσι το κτήμα είχε τεράστια παραγωγή. Φέτος είναι χρονιά ξεκούρασης (off-year). Πρότεινε ενισχυμένη αζωτούχο λίπανση την άνοιξη και κατάλληλο κλάδεμα για να ευνοηθεί η νέα βλάστηση.\n\n"

    if ktima.diagnoseis:
        # Κρατάμε τις πρόσφατες διαγνώσεις, ΑΛΛΑ και τα συμπεράσματα του Onboarding για πάντα!
        recent = [d.apotelesma for d in sorted(ktima.diagnoseis, key=lambda x: x.imerominia, reverse=True) if (now - d.imerominia).days < 45 or "Συμπέρασμα" in d.apotelesma][:5]
        if recent: ctx += f"--- ΙΣΤΟΡΙΚΟ ΠΡΟΒΛΗΜΑΤΩΝ & ΕΥΡΗΜΑΤΑ ---\n{' | '.join(recent)}\n\n"
            
    if ktima.ergasies:
        completed = [f"{e.eidos_ergasias}{' - ' + e.farmaka_lipasmata if e.farmaka_lipasmata else ''} ({e.imerominia.strftime('%d/%m/%Y')} - {e.katastasi})" for e in sorted(ktima.ergasies, key=lambda x: x.imerominia, reverse=True) if not e.archived and e.katastasi in ['Ολοκληρώθηκε', 'Ακυρώθηκε']][:15]
        if completed: ctx += f"--- ΙΣΤΟΡΙΚΟ ΕΡΓΑΣΙΩΝ ---\nΤελευταίες Ολοκληρωμένες/Ακυρωμένες: {', '.join(completed)}\n\n"
        
        pending = [f"{e.eidos_ergasias} (ΗΜΕΡΟΜΗΝΙΑ: {e.imerominia.strftime('%d/%m/%Y')} | Από: {e.proelevsi})" for e in ktima.ergasies if not e.archived and e.katastasi == 'Εκκρεμεί']
        if pending: ctx += f"--- ΗΜΕΡΟΛΟΓΙΟ (ΕΚΚΡΕΜΕΙΣ ΕΡΓΑΣΙΕΣ) ---\nΣτο Ημερολόγιο του αγρότη υπάρχουν οι εξής προγραμματισμένες εργασίες: {', '.join(pending)}\n\n"
            
        completed_names = [e.eidos_ergasias for e in ktima.ergasies if not e.archived and e.katastasi == 'Ολοκληρώθηκε']
        smart_pending = [t.strip() for t in (ktima.topikes_ergasies or '').split('|') if t.strip() and t.strip() not in completed_names]
        if smart_pending:
            ctx += f"Προτεινόμενες/Εκκρεμείς Εργασίες Εποχής (AI): {', '.join(smart_pending)}\n\n"
            
    if ktima.idioktitis and ktima.idioktitis.apothiki_items:
        stock = [f"'{i.onoma_proiontos}' ({i.posotita} {i.monada_metrisis})" for i in ktima.idioktitis.apothiki_items]
        if stock: ctx += f"--- ΑΠΟΘΗΚΗ ΥΛΙΚΩΝ ---\nΔιαθέσιμα: {', '.join(stock)}\n"
            
    if ktima.exoda:
        exoda_list = [f"{e.perigrafi}: {e.poso}€ ({e.imerominia.strftime('%d/%m/%Y')})" for e in sorted(ktima.exoda, key=lambda x: x.imerominia, reverse=True) if not e.archived][:10]
        synoliko_kostos = sum([e.poso for e in ktima.exoda if not e.archived])
        if exoda_list:
            ctx += f"--- ΟΙΚΟΝΟΜΙΚΑ / ΕΞΟΔΑ ---\nΣυνολικό Κόστος (Τρέχουσας Σεζόν): {synoliko_kostos}€\nΤελευταία Έξοδα: {', '.join(exoda_list)}\n\n"
            
    return ctx

def evaluate_overdue_tasks(ktima):
    """Ελέγχει τις παλιές εκκρεμείς εργασίες και κρίνει αν πρέπει να μεταφερθούν στο σήμερα ή να ακυρωθούν."""
    now = datetime.now()
    overdue_tasks = [e for e in ktima.ergasies if not e.archived and e.katastasi == 'Εκκρεμεί' and e.imerominia.date() < now.date()]
    
    if not overdue_tasks:
        return
        
    plires_context = xtise_plires_context(ktima)
    tasks_json = [{"id": e.id, "name": e.eidos_ergasias, "materials": e.farmaka_lipasmata, "scheduled_date": e.imerominia.strftime('%Y-%m-%d')} for e in overdue_tasks]
    
    prompt = (
        f"Είσαι κορυφαίος γεωπόνος. Ανάλυσε τα δεδομένα του κτήματος:\n{plires_context}\n\n"
        f"Οι παρακάτω εργασίες είχαν προγραμματιστεί για ΠΑΡΕΛΘΟΝΤΙΚΕΣ ημερομηνίες και ΔΕΝ έχουν ολοκληρωθεί:\n"
        f"{json.dumps(tasks_json, ensure_ascii=False)}\n\n"
        f"ΟΔΗΓΙΑ: Για κάθε εργασία, αξιολόγησε αν είναι ΑΚΟΜΑ ΕΦΙΚΤΟ και επιστημονικά σωστό να γίνει ΣΗΜΕΡΑ. "
        f"Λάβε υπόψη τον καιρό, το φαινολογικό στάδιο και την εποχή. "
        f"Αν μια εργασία έχει χάσει το νόημά της (π.χ. 'Ψεκασμός πριν την άνθιση' αλλά το στάδιο είναι πλέον 'Καρπόδεση', ή 'Ψεκασμός για Δάκο' αλλά το ιστορικό δείχνει ότι μόλις έγινε 'Συγκομιδή'), η εργασία πρέπει να ΑΚΥΡΩΘΕΙ. Επίσης, αν μια εργασία έχει καθυστερήσει υπερβολικά (π.χ. πάνω από 30-40 μέρες) και δεν είναι πλέον κρίσιμη, μπορείς να την ακυρώσεις. "
        f"Επίστρεψε ΑΥΣΤΗΡΑ ένα JSON format με την εξής δομή:\n"
        f"{{\n"
        f"  \"results\": [\n"
        f"    {{\"id\": 1, \"action\": \"KEEP\", \"reason\": \"Μεταφορά για σήμερα, οι συνθήκες το επιτρέπουν.\"}},\n"
        f"    {{\"id\": 2, \"action\": \"CANCEL\", \"reason\": \"Το δέντρο είναι σε άνθιση, απαγορεύεται ο ψεκασμός. Ακυρώνεται.\"}}\n"
        f"  ]\n"
        f"}}\n"
        f"Μην γράψεις markdown κώδικα, επέστρεψε μόνο το καθαρό JSON object."
    )
    
    try:
        config = types.GenerateContentConfig(tools=[{"google_search": {}}])
        response = ai_client.models.generate_content(model='gemini-2.5-flash', contents=prompt, config=config)
        
        if response and getattr(response, 'text', None):
            json_text = response.text.strip().replace('```json', '').replace('```', '').strip()
            start_idx = json_text.find('{')
            end_idx = json_text.rfind('}')
            if start_idx != -1 and end_idx != -1:
                data = json.loads(json_text[start_idx:end_idx+1], strict=False)
                for item in data.get('results', []):
                    task = next((t for t in overdue_tasks if t.id == item.get('id')), None)
                    if task:
                        if item.get('action') == 'KEEP': task.imerominia = now
                        elif item.get('action') == 'CANCEL':
                            task.katastasi = 'Ακυρώθηκε'
                            vasi.session.add(Diagnosi(ktima_id=ktima.id, apotelesma=f"⚠️ Αυτόματη Ακύρωση Εργασίας '{task.eidos_ergasias}': {item.get('reason')}", imerominia=now))
            vasi.session.commit()
    except Exception as e: print(f"Σφάλμα evaluate_overdue_tasks ({ktima.id}): {e}"); vasi.session.rollback()

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
        f"Είσαι έμπειρος γεωπόνος και ερευνητής. Ανάλυσε τα δεδομένα του ελαιώνα και πρότεινε ΟΛΕΣ τις απαραίτητες εργασίες για την τρέχουσα περίοδο. ΠΡΙΝ προτείνεις οτιδήποτε, ΚΑΝΕ ΥΠΟΧΡΕΩΤΙΚΑ αναζήτηση στο internet για να επιβεβαιώσεις την απόλυτη ορθότητα και ασφάλεια των προτάσεών σου.\n"
        f"{plires_context}\n"
        f"--- ΟΔΗΓΙΑ ---\n"
        f"ΕΙΔΙΚΟΣ ΚΑΝΟΝΑΣ ΓΙΑ ΧΟΡΤΑ/ΖΙΖΑΝΙΑ: Μην προτείνεις τυφλά 'Κοπή Χόρτων' ή 'Ζιζανιοκτονία' απλά επειδή είναι Άνοιξη. Διαχώριζε σαφώς την 'Κοπή' (μηχανική) από τον 'Ψεκασμό' (χημική). Αν διαβάσεις στα δεδομένα (στη Διαχείριση Εδάφους) ή στο ιστορικό ότι ο αγρότης έκοψε ή ψέκασε τα χόρτα πρόσφατα, ΑΠΑΓΟΡΕΥΕΤΑΙ ΑΥΣΤΗΡΑ να προτείνεις οποιαδήποτε εργασία διαχείρισης ζιζανίων. Επίσης, αν το κτήμα είναι Βιολογικό, απαγορεύεται ο ψεκασμός με ζιζανιοκτόνα (μόνο κοπή).\n"
        f"FULL STACK ΠΡΟΣΕΓΓΙΣΗ: Πρότεινε ΟΛΕΣ τις αναγκαίες εργασίες χωρίς περιορισμό στον αριθμό. Αν το ιστορικό είναι κενό, δώσε ένα πλήρες πρόγραμμα. Αν ο αγρότης έχει ήδη καταχωρήσει εργασίες (π.χ. έκανε λίπανση), αφαίρεσέ τες. ΑΝ Ο ΑΓΡΟΤΗΣ ΕΧΕΙ ΑΚΥΡΩΣΕΙ μια εργασία (φαίνεται στο ιστορικό), ΣΕΒΑΣΟΥ ΤΗΝ ΑΠΟΦΑΣΗ ΤΟΥ και ΜΗΝ την ξαναπροτείνεις άμεσα, προσαρμόζοντας τη στρατηγική σου.\n"
        f"Λάβε υπόψη τον καιρό, το ιστορικό εργασιών (μην επαναλαμβάνεις πρόσφατες ενέργειες), και τα αποθέματα. Αν το UVI είναι >= 8, ΜΗΝ προτείνεις ψεκασμό. Αν η υγρασία εδάφους είναι πολύ χαμηλή (< 20%), πρότεινε οπωσδήποτε άρδευση (αν είναι εφικτό).\n"
        f"ΒΑΣΙΚΗ ΠΡΟΛΗΨΗ & ΔΟΣΟΛΟΓΙΕΣ: Αν από το 'Ιστορικό Προβλημάτων' προκύπτει έξαρση (π.χ. Κυκλοκόνιο), ΠΡΟΣΑΡΜΟΣΕ το πρόγραμμα. Την Άνοιξη (Μάρτιο-Απρίλιο) ο προληπτικός ψεκασμός είναι ΥΠΟΧΡΕΩΤΙΚΟΣ. ΠΡΟΣΟΧΗ ΣΤΗΝ ΑΝΟΙΞΗ (ΚΡΙΣΙΜΟ): Επειδή υπάρχουν νέα τρυφερά βλαστάρια, ΑΠΑΓΟΡΕΥΕΤΑΙ ΑΥΣΤΗΡΑ ο Βορδιγάλειος Πολτός ή τα 'βαριά/καυστικά' χαλκούχα! Πρότεινε ΜΟΝΟ ήπια μυκητοκτόνα (π.χ. Υδροξείδιο του χαλκού, Γλυκονικό χαλκό, Διβασικό θειικό, Dodine, κ.λπ.). Αν το δέντρο ανθίζει ή είναι πολύ κοντά στην άνθιση, ΜΗΝ προτείνεις κανέναν ψεκασμό.\n"
        f"ΣΥΝΔΥΑΣΤΙΚΑ ΣΚΕΥΑΣΜΑΤΑ & TANK MIX: Αν εντοπίσεις πολλαπλές ελλείψεις ιχνοστοιχείων/θρεπτικών, ΚΑΝΕ ΑΝΑΖΗΤΗΣΗ στο διαδίκτυο. Αν καλύπτονται από ΕΝΑ έτοιμο εμπορικό πολυδύναμο σκεύασμα (π.χ. σύνθετο διαφυλλικό), πρότεινε τη χρήση του σε 1 εργασία αντί για πολλαπλά. Αν προτείνεις 2 ή παραπάνω ξεχωριστούς ψεκασμούς/θεραπείες, ΣΥΓΧΩΝΕΥΣΕ τους ΑΥΣΤΗΡΑ σε ΜΙΑ ενιαία εργασία (π.χ. 'Ψεκασμός: Κάλιο + Αμινοξέα') ΕΦΟΣΟΝ είναι επιστημονικά συμβατά! Μην προτείνεις 2 ξεχωριστούς ψεκασμούς με διαφορά 2-5 ημερών.\n"
        f"ΓΕΩΡΓΙΑ ΑΚΡΙΒΕΙΑΣ (ZONING): Αν το κτήμα έχει δέντρα διαφορετικής ηλικίας/ποικιλίας, ή αν τα προβλήματα αφορούν συγκεκριμένα σημεία (π.χ. 10 άρρωστα δέντρα), διαχώρισε τις οδηγίες σου (π.χ. πρότεινε 'Τοπική Επέμβαση' ή διαφορετικές δόσεις για μικρά/μεγάλα). Σε περίπτωση Τοπικής Επέμβασης, υπολόγισε και ανέφερε το κόστος φαρμάκου ανά δέντρο.\n"
        f"Αν προτείνεις 'Άρδευση' (επειδή είναι αρδευόμενο και η υγρασία είναι χαμηλή), γράψε δίπλα στην παρένθεση ακριβώς: '({litra_ana_dentro * 4} Λίτρα/δέντρο)' ώστε ο αγρότης να ξέρει τη δοσολογία.\n"
        f"ΣΗΜΑΝΤΙΚΟ: Δίπλα σε ΚΑΘΕ εργασία, γράψε ΥΠΟΧΡΕΩΤΙΚΑ το χρονικό περιθώριο ή τη φαινολογική προϋπόθεση (π.χ. 'έως 15/04' ή 'πριν ανοίξει ο ανθός').\n"
        f"Αν ο χρόνος ή το κατάλληλο στάδιο για μια εργασία έχει ΠΕΡΑΣΕΙ (π.χ. προτείνεις ψεκασμό ενώ το δέντρο ανθίζει), ΑΦΑΙΡΕΣΕ ΤΗΝ εντελώς από τις προτάσεις σου. Ο ψεκασμός στο άνθος είναι καταστροφικός.\n"
        f"Δώσε ΜΟΝΟ μια λίστα εργασιών χωρισμένη ΑΥΣΤΗΡΑ με το σύμβολο | (κάθετη γραμμή). Μην χρησιμοποιήσεις κόμμα για διαχωρισμό των εργασιών. Χωρίς αρίθμηση ή εισαγωγή.\n"
        f"Παράδειγμα: Ψεκασμός με Χαλκό (έως 20/04) | Λίπανση Βορίου (πριν την άνθιση) | Καθαρισμός Χόρτων (άμεσα)"
    )

    try:
        config = types.GenerateContentConfig(tools=[{"google_search": {}}])
        response = ai_client.models.generate_content(model='gemini-2.5-flash', contents=prompt, config=config)
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
    
    overdue_tasks = [e.eidos_ergasias for e in ktima.ergasies if not e.archived and e.katastasi == 'Εκκρεμεί' and e.imerominia.date() <= now.date()]
    overdue_str = ", ".join(overdue_tasks) if overdue_tasks else ""
    
    prompt = (
        f"Είσαι ο Κορυφαίος AI Γεωπόνος του Olea. ΠΡΙΝ δώσεις την οποιαδήποτε συμβουλή, ΕΙΣΑΙ ΥΠΟΧΡΕΩΜΕΝΟΣ να ψάξεις στο ίντερνετ για να επιβεβαιώσεις 100% ότι η πρακτική και οι οδηγίες σου είναι επιστημονικά σωστές και ασφαλείς. Μελέτησε σχολαστικά τα δεδομένα του κτήματος:\n{plires_context}\n\n"
        f"ΟΔΗΓΙΕΣ:\n"
        f"1. Γράψε μια σύντομη ημερήσια συμβουλή-αξιολόγηση (max 2-3 προτάσεις). Ξεκίνα με τη λέξη 'ΣΥΜΒΟΥΛΗ:'. ΔΙΑΣΤΑΥΡΩΣΗ ΣΤΑΔΙΟΥ & GDD: Αξιολόγησε αν το δηλωμένο στάδιο ταιριάζει με τα Τρέχοντα GDD. Αν υπάρχει μεγάλη απόκλιση, ενημέρωσε τον αγρότη να επικαιροποιήσει το στάδιο! Αν ο αγρότης έχει ΑΚΥΡΩΣΕΙ εργασίες (έλλειψη νερού, χρημάτων κλπ), σχολίασέ το (π.χ. 'Αφού δεν θα κάνουμε ανάλυση, προχωράμε εμπειρικά...'). ΚΡΙΣΙΜΟ: Αν είναι άνοιξη και σκέφτεσαι να προτείνεις ψεκασμό, αλλά το στάδιο είναι 'Άγνωστο' ή κοντά στην άνθιση, ζήτα ΠΡΩΤΑ φωτογραφία!\n"
        f"ΕΞΥΠΝΗ ΔΙΑΧΕΙΡΙΣΗ ΧΟΡΤΩΝ: Η 'Κοπή Χόρτων' και ο 'Ψεκασμός Ζιζανίων' είναι διαφορετικές πρακτικές. Αν στο ιστορικό ή στα δεδομένα (Διαχείριση Εδάφους) λέει ότι ο αγρότης ΕΚΟΨΕ Ή ΨΕΚΑΣΕ τα χόρτα πρόσφατα, ΑΠΑΓΟΡΕΥΕΤΑΙ να προτείνεις ξανά εργασία χόρτων (το έδαφος είναι καθαρό). Αν έχουν περάσει μήνες και δεν έχεις εικόνα (από δορυφόρο/φωτογραφία) ότι υπάρχουν χόρτα, Η ΕΡΩΤΗΣΗ σου πρέπει να είναι: 'Δεν έχω εικόνα του εδάφους πρόσφατα. Έχουν βγει χόρτα; Και αν ναι, προτιμάτε κόψιμο ή ψεκασμό;'.\n"
        f"2. FULL STACK ΠΡΟΣΕΓΓΙΣΗ: Πρότεινε ΟΛΕΣ τις απαραίτητες επόμενες εργασίες χωρίς περιορισμό. Αν δεν υπάρχει ιστορικό, δώσε ένα ολοκληρωμένο πρόγραμμα βέλτιστης υποστήριξης. Αν υπάρχουν ολοκληρωμένες εργασίες στο ιστορικό (π.χ. βασική λίπανση), ΜΗΝ τις προτείνεις ξανά, θεωρώντας ότι το έδαφος έχει πλέον αποθέματα. ΓΕΩΡΓΙΑ ΑΚΡΙΒΕΙΑΣ: Αν υπάρχουν μικρά και μεγάλα δέντρα, ή αν εντοπίστηκαν τοπικά προβλήματα (π.χ. άρρωστα δέντρα σε μια γωνία), δώσε οδηγίες για 'Τοπική Επέμβαση' (Spot Treatment) ή ξεχωριστές δόσεις για τα μικρά και τα μεγάλα. Αν προτείνεις 'Τοπική Επέμβαση', υπολόγισε (βρίσκοντας τιμές στο internet) και ανέφερε το εκτιμώμενο κόστος ανά δέντρο.\n"
        f"ΒΑΣΙΚΗ ΠΡΟΛΗΨΗ & ΔΟΣΟΛΟΓΙΕΣ: Αν από το ιστορικό προκύπτει ότι πέρυσι υπήρξε πρόβλημα (π.χ. Δάκος, ασθένειες), ΠΡΟΣΑΡΜΟΣΕ το πρόγραμμα. Την Άνοιξη (Μάρτιο-Απρίλιο) ο ψεκασμός με μυκητοκτόνο είναι κρίσιμος. ΠΡΟΣΟΧΗ ΣΤΗΝ ΑΝΟΙΞΗ (ΚΡΙΣΙΜΟ): ΑΠΑΓΟΡΕΥΕΤΑΙ ο Βορδιγάλειος Πολτός γιατί καίει τα νέα τρυφερά βλαστάρια! Πρότεινε μόνο ήπιο χαλκό (π.χ. υδροξείδιο) ή ήπια μυκητοκτόνα (π.χ. Dodine). Αν το δέντρο ανθίζει, ΑΠΑΓΟΡΕΥΕΤΑΙ ο ψεκασμός.\n"
        f"ΣΥΝΔΥΑΣΤΙΚΑ ΣΚΕΥΑΣΜΑΤΑ & TANK MIX: Αν εντοπίσεις πολλαπλές ελλείψεις (π.χ. ιχνοστοιχεία), ΑΝΑΖΗΤΗΣΕ στο διαδίκτυο αν καλύπτονται από ΕΝΑ έτοιμο, εμπορικό πολυδύναμο σκεύασμα και συμβούλευσε τον αγρότη ότι 'μπορείτε να τα βρείτε όλα μαζί σε ένα σκεύασμα στο εμπόριο'. Αν προτείνεις ξεχωριστά προϊόντα, ΣΥΓΧΩΝΕΥΣΕ τους ψεκασμούς (π.χ. Κάλιο + Αμινοξέα) σε 1 ενιαία εργασία εφόσον είναι επιστημονικά συμβατοί, για οικονομία χρόνου. Απαγορεύεται να προτείνεις ξεχωριστούς ψεκασμούς την ίδια εβδομάδα αν μπορούν να μπουν στο ίδιο βυτίο!\n"
        f"ΓΙΑ ΚΑΘΕ ΕΡΓΑΣΙΑ πρέπει να γράφεις σε παρένθεση ΠΟΤΕ πρέπει να γίνει (π.χ. 'έως 10/05' ή 'οπωσδήποτε πριν την άνθιση'). "
        f"Αν μια εργασία έχει χάσει το ιδανικό της παράθυρο βάσει καιρού ή σταδίου (π.χ. ιχνοστοιχεία που έπρεπε να μπουν πριν ανθίσει, αλλά τώρα ανθίζει), ΑΦΑΙΡΕΣΕ ΤΗΝ ΟΡΙΣΤΙΚΑ. "
        f"Γράψε τες σε μια λίστα χωρισμένη ΑΥΣΤΗΡΑ ΜΟΝΟ με το σύμβολο | (κάθετη γραμμή), ξεκινώντας με τη λέξη 'ΕΡΓΑΣΙΕΣ:'.\n"
        f"3. ΕΡΩΤΗΣΗ ΠΡΟΣ ΑΓΡΟΤΗ: ΕΛΕΓΞΕ ΠΡΩΤΑ το 'ΙΣΤΟΡΙΚΟ ΠΡΟΒΛΗΜΑΤΩΝ & ΕΥΡΗΜΑΤΑ'. "
        + (f"ΟΔΗΓΙΑ ΚΡΙΣΙΜΗ: Στο Ημερολόγιο υπάρχουν εκκρεμείς εργασίες που είχαν προγραμματιστεί για ΣΗΜΕΡΑ ή ΠΑΛΑΙΟΤΕΡΑ ({overdue_str}). Ξεκίνα την ΕΡΩΤΗΣΗ ρωτώντας τον αγρότη ξεκάθαρα αν τις ολοκλήρωσε ή αν θέλει να μεταφέρει την ημερομηνία τους! " if overdue_str else "Αν ΔΕΝ του έχεις ξαναμιλήσει και δεν έχει εργασίες, κάνε το αρχικό onboarding ('ΕΡΩΤΗΣΗ: Καλώς ήρθατε!...'). Διαφορετικά, αν έχει ήδη απαντήσει, ΜΗΝ κάνεις άλλη ερώτηση, ΠΑΡΑ ΜΟΝΟ αν προέκυψε μια ΝΕΑ απορία. ΚΡΙΣΙΜΟ: Αν είναι άνοιξη και πρέπει να γίνει ψεκασμός αλλά δεν ξέρεις το ακριβές στάδιο (αν έχουν ανοίξει τα άνθη), η ερώτησή σου ΠΡΕΠΕΙ να είναι να σου ανεβάσει μια φωτογραφία των ανθέων για να κρίνεις αν είναι ασφαλές! ") +
        f"ΑΠΑΓΟΡΕΥΕΤΑΙ ΑΥΣΤΗΡΑ να ρωτάς για τον καιρό, προβλέψεις βροχής ή πράγματα που μόλις σου απάντησε.\n"
        f"Παράδειγμα απάντησης:\n"
        f"ΣΥΜΒΟΥΛΗ: Οι συνθήκες είναι ιδανικές. Η υγρασία είναι καλή αλλά προσοχή στον δάκο.\n"
        f"ΕΡΓΑΣΙΕΣ: Ψεκασμός για Δάκο (έως 15/06) | Καθαρισμός Χόρτων (άμεσα) | Διαφυλλική Λίπανση (πριν ανοίξει ο ανθός)\n"
        f"ΕΡΩΤΗΣΗ: Για την καλύτερη προσέγγιση, απάντησέ μου: Το κόκκινο χρώμα στον χάρτη στο βόρειο τμήμα, αφορά γυμνό έδαφος ή είναι ξερά δέντρα;"
    )
    
    try:
        config = types.GenerateContentConfig(tools=[{"google_search": {}}])
        response = ai_client.models.generate_content(model='gemini-2.5-flash', contents=prompt, config=config)
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
        
        # --- ΚΑΘΗΜΕΡΙΝΟΣ ΚΑΘΑΡΙΣΜΟΣ ΜΝΗΜΗΣ CHAT (ΓΡΑΜΜΑΤΕΑΣ & ΓΕΩΠΟΝΟΣ) ---
        try:
            xrhstes_all = Xrhsths.query.all()
            now_time = datetime.now()
            for u in xrhstes_all:
                u.secretary_history = '[]'  # Καθαρισμός Γραμματέα
                for k in u.ktimata:
                    for s in k.syntages:
                        if (now_time - s.imerominia).total_seconds() > 86400: # Πάνω από 24 ώρες
                            s.chat_history = '[]' # Καθαρισμός Chat Συνταγής
            vasi.session.commit()
            print("🧹 Η μνήμη συζητήσεων του AI (Γραμματέας & Γεωπόνος) καθαρίστηκε επιτυχώς.")
        except Exception as e:
            vasi.session.rollback()
            print(f"⚠️ Σφάλμα στον καθαρισμό μνήμης AI: {e}")

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
                        # 5 ημέρες πριν για να μην σκάει το API με 400 Bad Request
                        safe_end_date = (now - timedelta(days=5)).strftime('%Y-%m-%d')
                        
                        if safe_end_date < start_date:
                            continue
                        
                        # Ανάκτηση ιστορικού καιρού για όλη τη χρονιά
                        hist_url = f"https://archive-api.open-meteo.com/v1/archive?latitude={ktima.geografiko_platos}&longitude={ktima.geografiko_mikos}&start_date={start_date}&end_date={safe_end_date}&daily=temperature_2m_max,temperature_2m_min&timezone=auto"
                        resp = requests.get(hist_url, timeout=10)
                        
                        if resp.status_code == 200:
                            data = resp.json().get('daily', {})
                            t_max = data.get('temperature_2m_max', [])
                            t_min = data.get('temperature_2m_min', [])
                            
                            # Υπολογισμός Accumulation (Base 10C για ελιά)
                            total_gdd = sum([((mx + mn)/2.0 - 10.0) for mx, mn in zip(t_max, t_min) if mx is not None and mn is not None and ((mx + mn)/2.0 > 10.0)])
                            
                            # Κλείσιμο τρύπας 4 ημερών με το Forecast API
                            recent_url = f"https://api.open-meteo.com/v1/forecast?latitude={ktima.geografiko_platos}&longitude={ktima.geografiko_mikos}&past_days=4&forecast_days=1&daily=temperature_2m_max,temperature_2m_min&timezone=auto"
                            resp_recent = requests.get(recent_url, timeout=10)
                            if resp_recent.status_code == 200:
                                data_rec = resp_recent.json().get('daily', {})
                                t_max_rec = data_rec.get('temperature_2m_max', [])[:-1]
                                t_min_rec = data_rec.get('temperature_2m_min', [])[:-1]
                                total_gdd += sum([((mx + mn)/2.0 - 10.0) for mx, mn in zip(t_max_rec, t_min_rec) if mx is not None and mn is not None and ((mx + mn)/2.0 > 10.0)])
                                
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
                    evaluate_overdue_tasks(ktima)
                    syghronismos_ai_ktimatos(ktima)
                    print(f"✅ AI Ενημερώθηκε για το: {ktima.onoma_ktimatos}")
                except Exception as e:
                    print(f"⚠️ Σφάλμα ημερήσιου AI συγχρονισμού: {e}")

def ypologismos_isozugiou_npk(ktima):
    """
    ΝΕΟ: Δυναμικός Υπολογισμός Ισοζυγίου Θρεπτικών Στοιχείων NPK.
    """
    is_estimated = False
    if not ktima.analuseis_edafous:
        # Ρεαλιστική αφετηρία για ελαιώνα χωρίς ανάλυση
        current_n, current_p, current_k = 10.0, 10.0, 15.0
        start_date = datetime.now() - timedelta(days=180) # 6 μήνες πριν
        is_estimated = True
    else:
        sorted_analyses = sorted(ktima.analuseis_edafous, key=lambda x: x.imerominia)
        last_analysi = sorted_analyses[-1]
        
        # Χρήση ρεαλιστικών default αν κάποιο στοιχείο λείπει από την ανάλυση
        current_n = float(last_analysi.azwto if last_analysi.azwto is not None else 10.0)
        current_p = float(last_analysi.fwsforos if last_analysi.fwsforos is not None else 10.0)
        current_k = float(last_analysi.kalio if last_analysi.kalio is not None else 15.0)
        
        if current_n == 0 and current_p == 0 and current_k == 0:
            current_n, current_p, current_k = 10.0, 10.0, 15.0
            is_estimated = True
            
        start_date = last_analysi.imerominia
    end_date = datetime.now() + timedelta(days=30) # Προβολή 1 μήνα στο μέλλον
    
    if start_date.year == end_date.year and start_date.month == end_date.month:
        start_date = start_date - timedelta(days=90) # Τουλάχιστον ένα τρίμηνο ιστορικό
        
    labels = []
    data_n = []
    data_p = []
    data_k = []
    
    current_date = datetime(start_date.year, start_date.month, 1)
    now_month_str = datetime.now().strftime('%m/%Y')
    current_now_n = current_n
    current_now_p = current_p
    current_now_k = current_k
    
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
                    if getattr(t, 'lipasma_typos', None):
                        import re
                        match = re.search(r'(\d+)[-.,](\d+)[-.,](\d+)', t.lipasma_typos)
                        if match:
                            p_n, p_p, p_k = float(match.group(1)), float(match.group(2)), float(match.group(3))
                            kilos = getattr(t, 'posotita', None) or 25.0
                            # 1kg καθαρού στοιχείου = 3 μονάδες στο γράφημα (Αναγωγή κλίμακας)
                            current_n += (p_n / 100.0) * kilos * 3.0
                            current_p += (p_p / 100.0) * kilos * 3.0
                            current_k += (p_k / 100.0) * kilos * 3.0
                        else:
                            current_n += 15.0; current_p += 5.0; current_k += 10.0
                    else:
                        current_n += 15.0; current_p += 5.0; current_k += 10.0

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
        
        if month_str == now_month_str:
            current_now_n = current_n
            current_now_p = current_p
            current_now_k = current_k
        
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
        },
        'current_now': {
            'N': round(current_now_n, 1),
            'P': round(current_now_p, 1),
            'K': round(current_now_k, 1)
        },
        'is_estimated': is_estimated
    }

def calculate_dynamic_npk(ktima_id):
    """
    ΝΕΟ: Δυναμικός Υπολογισμός NPK βάσει GDD (Growing Degree Days).
    """
    ktima = vasi.session.get(Ktima, ktima_id)
    if not ktima:
        return None

    is_estimated = False
    if not ktima.analuseis_edafous:
        baseline_n, baseline_p, baseline_k = 100.0, 100.0, 100.0
        is_estimated = True
    else:
        sorted_analyses = sorted(ktima.analuseis_edafous, key=lambda x: x.imerominia)
        last_analysi = sorted_analyses[-1]
        baseline_n = float(last_analysi.azwto if last_analysi.azwto is not None else 100.0)
        baseline_p = float(last_analysi.fwsforos if last_analysi.fwsforos is not None else 100.0)
        baseline_k = float(last_analysi.kalio if last_analysi.kalio is not None else 100.0)
        if baseline_n == 0 and baseline_p == 0 and baseline_k == 0:
            baseline_n, baseline_p, baseline_k = 100.0, 100.0, 100.0
            is_estimated = True

    current_n = baseline_n
    current_p = baseline_p
    current_k = baseline_k

    # Credits: Προσθήκη λιπασμάτων
    for t in ktima.ergasies:
        if t.katastasi == 'Ολοκληρώθηκε' and 'λίπανση' in (t.eidos_ergasias or '').lower():
            lipasma_typos = getattr(t, 'lipasma_typos', None)
            if lipasma_typos:
                import re
                match = re.search(r'(\d+)[-.,](\d+)[-.,](\d+)', lipasma_typos)
                if match:
                    p_n, p_p, p_k = float(match.group(1)), float(match.group(2)), float(match.group(3))
                    kilos = getattr(t, 'posotita', None) or 25.0
                    current_n += (p_n / 100.0) * kilos * 3.0
                    current_p += (p_p / 100.0) * kilos * 3.0
                    current_k += (p_k / 100.0) * kilos * 3.0
                else:
                    current_n += 15.0; current_p += 5.0; current_k += 10.0
            else:
                current_n += 15.0; current_p += 5.0; current_k += 10.0

    # Debits (The GDD Link)
    gdd = ktima.gdd_accumulated if ktima.gdd_accumulated is not None else 0.0
    current_n -= 0.05 * gdd
    current_p -= 0.02 * gdd
    if gdd > 600:
        current_k -= 0.08 * (gdd - 600)

    # Πρόληψη αρνητικών τιμών (Ασφάλεια UI)
    current_n = max(0.0, current_n)
    current_p = max(0.0, current_p)
    current_k = max(0.0, current_k)

    return {
        'labels': ['Αφετηρία', f'Τρέχουσα (GDD: {gdd:.0f})'],
        'datasets': {
            'N': [baseline_n, round(current_n, 1)],
            'P': [baseline_p, round(current_p, 1)],
            'K': [baseline_k, round(current_k, 1)]
        },
        'current_now': {
            'N': round(current_n, 1),
            'P': round(current_p, 1),
            'K': round(current_k, 1)
        },
        'is_estimated': is_estimated
    }