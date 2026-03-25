import os
import json
import PIL.Image
from werkzeug.utils import secure_filename
import io
from datetime import datetime
from flask import Blueprint, request, jsonify
from flask_login import login_required, current_user
from core import vasi
from models import Ktima, Ergasia, Diagnosi, Exodo, Apothiki, ArxeioSygkomidis, KatagrafiUgrasias, GenikoExodo
from google import genai
from google.genai import types

gramateas_bp = Blueprint('gramateas', __name__)

@gramateas_bp.route('/api/clear_secretary_history', methods=['POST'])
@login_required
def clear_secretary_history():
    current_user.secretary_history = '[]'
    vasi.session.commit()
    return jsonify({'success': True})

UPLOADS_REL_PATH = os.path.join('uploads', 'ktima_photos')
UPLOADS_ABS_PATH = os.path.join(os.path.dirname(__file__), '..', UPLOADS_REL_PATH)
os.makedirs(UPLOADS_ABS_PATH, exist_ok=True)

@gramateas_bp.route('/api/ai_secretary', methods=['POST'])
@login_required
def ai_secretary():
    ktima_id = request.form.get('ktima_id')
    text = request.form.get('text', '')
    history_str = request.form.get('history', '[]')
    image_files = request.files.getlist('images')

    ktima = None
    if ktima_id and ktima_id not in ['none', 'all']:
        try:
            ktima = vasi.session.get(Ktima, int(ktima_id))
        except (ValueError, TypeError):
            pass
            
    if ktima and ktima.idioktitis != current_user:
        return jsonify({'error': 'Μη εξουσιοδοτημένη πρόσβαση'}), 403

    api_key_to_use = getattr(current_user, 'gemini_api_key', None) or os.getenv('AI_API_KEY')
    if not api_key_to_use:
        return jsonify({'error': 'Δεν έχει ρυθμιστεί κλειδί AI.'}), 500

    client = genai.Client(api_key=api_key_to_use)

    try:
        contents = []
        context_str = f"Είσαι ο 'AI Γραμματέας' του αγρότη. Σκοπός σου είναι να τον διευκολύνεις να καταχωρεί δεδομένα χωρίς να πατάει πολλά κουμπιά, και να του λύνεις απορίες.\n"
        
        # Προσθήκη λίστας κτημάτων ώστε να καταλαβαίνει το AI σε ποιο αναφέρεται ο χρήστης
        energa_ktimata = [k for k in current_user.ktimata if k.is_active]
        context_str += "\nΛίστα Ενεργών Κτημάτων του Αγρότη:\n"
        for k in energa_ktimata:
            context_str += f"- ID: {k.id}, Όνομα: '{k.onoma_ktimatos}'\n"
        
        from logic import xtise_plires_context
        if ktima:
            context_str += f"\nΤο ΕΝΕΡΓΟ κτήμα στη συζήτηση (που βλέπει τώρα ο χρήστης) είναι το '{ktima.onoma_ktimatos}' (ID: {ktima.id}). Οι ενέργειές σου εξ ορισμού αφορούν αυτό.\nΔεδομένα ΕΝΕΡΓΟΥ Κτήματος:\n{xtise_plires_context(ktima)}\n"
            
            alla_ktimata = [k for k in energa_ktimata if k.id != ktima.id]
            if alla_ktimata:
                context_str += "\nΓια δική σου πληροφόρηση (π.χ. αν ζητηθεί σύγκριση ή αλλαγή), ορίστε τα δεδομένα και των ΥΠΟΛΟΙΠΩΝ κτημάτων:\n"
                for k in alla_ktimata:
                    context_str += f"\n--- ΚΤΗΜΑ: {k.onoma_ktimatos} (ID: {k.id}) ---\n{xtise_plires_context(k)}\n"
        elif ktima_id == 'all':
            context_str += "\nΟ αγρότης ΔΕΝ έχει επιλέξει συγκεκριμένο κτήμα (Γενική Προβολή). Επέλεξε 'Όλα τα Κτήματα'. Αν ζητήσει καταχώρηση σε όλα, βάλε target_ktima_id = 'ALL' στο task. Σου δίνω ΠΛΗΡΗ ΠΡΟΣΒΑΣΗ στα δεδομένα ΟΛΩΝ των ενεργών κτημάτων του:\n"
            for k in energa_ktimata:
                context_str += f"\n--- ΑΡΧΗ ΔΕΔΟΜΕΝΩΝ ΓΙΑ ΚΤΗΜΑ: {k.onoma_ktimatos} (ID: {k.id}) ---\n"
                context_str += xtise_plires_context(k)
                context_str += f"--- ΤΕΛΟΣ ΔΕΔΟΜΕΝΩΝ ΓΙΑ ΚΤΗΜΑ: {k.onoma_ktimatos} ---\n"
        else:
            context_str += "\nΠΡΟΣΟΧΗ: Ο αγρότης κάνει 'Γενική Ερώτηση (Χωρίς Κτήμα)'. Αν ρωτάει για εργασίες ή τον καιρό ενός κτήματος που δεν έχεις τα δεδομένα, ΠΕΣ ΤΟΥ ΕΥΓΕΝΙΚΑ να το επιλέξει από το αναδιπλούμενο μενού πάνω-πάνω, για να μπορέσεις να διαβάσεις τον φάκελό του.\n"

            # Προσθήκη της Αποθήκης στη Γενική Προβολή
            if current_user.apothiki_items:
                stock = [f"'{i.onoma_proiontos}' ({i.posotita} {i.monada_metrisis})" for i in current_user.apothiki_items]
                if stock:
                    context_str += f"\n--- ΑΠΟΘΗΚΗ ΥΛΙΚΩΝ ΑΓΡΟΤΗ ---\nΔιαθέσιμα: {', '.join(stock)}\n"

        # --- ΕΙΣΑΓΩΓΗ ΜΝΗΜΗΣ ΣΤΟ AI ---
        try:
            history = json.loads(history_str)
            if history:
                context_str += "\n--- ΠΡΟΣΦΑΤΟ ΙΣΤΟΡΙΚΟ ΣΥΖΗΤΗΣΗΣ (ΜΝΗΜΗ) ---\n"
                for msg in history[-8:]:  # Κρατάμε τα 8 τελευταία μηνύματα
                    role = "Αγρότης" if msg.get('role') == 'user' else "Εσύ (AI Γραμματέας)"
                    context_str += f"{role}: {msg.get('content')}\n"
                context_str += "-------------------------------------------\n"
        except Exception: pass
        
        valid_images = [f for f in image_files if f.filename != '']
        if valid_images:
            text += f"\n[ΣΥΣΤΗΜΙΚΗ ΕΙΔΟΠΟΙΗΣΗ: Ο χρήστης μόλις επισύναψε {len(valid_images)} αρχείο(α)/φωτογραφία(ες).]"

        prompt = context_str + f"\nΤΩΡΙΝΟ ΜΗΝΥΜΑ ΧΡΗΣΤΗ: '{text}'.\n"
        prompt += """
        ΟΔΗΓΙΕΣ ΓΙΑ ΤΟ JSON ΚΑΙ ΤΗ ΣΥΜΠΕΡΙΦΟΡΑ ΣΟΥ: 
        0. ΟΡΑΣΗ/ΑΡΧΕΙΑ (ΚΡΙΣΙΜΟ): Έχεις πλήρη ικανότητα Vision! Μπορείς να διαβάσεις και να αναλύσεις κανονικά τις φωτογραφίες και τα PDF που σου επισυνάπτονται. ΑΠΑΓΟΡΕΥΕΤΑΙ ΑΥΣΤΗΡΑ να πεις ότι δεν μπορείς να δεις ή να διαβάσεις αρχεία.
        1. ΑΝΑΛΥΣΗ ΦΩΤΟΓΡΑΦΙΑΣ (ΝΕΑ ΛΟΓΙΚΗ): Αν ο χρήστης στείλει φωτογραφία κλαδιού/δέντρου, κάνε μια ΠΛΗΡΗ, ΣΦΑΙΡΙΚΗ ΑΞΙΟΛΟΓΗΣΗ. Η απάντησή σου στο 'reply' πρέπει να περιλαμβάνει:
           α) **Διάγνωση Ασθενειών:** Μια πρώτη εκτίμηση για το αν βλέπεις ασθένειες, τροφοπενίες ή εχθρούς.
           β) **Εκτίμηση Σταδίου:** Το φαινολογικό στάδιο που διακρίνεις (π.χ. 'Άνθιση', 'Καρπόδεση'). Αν το αναγνωρίσεις, βάλε το και στο "updates" -> "fainologiko_stadio".
           γ) **Εκτίμηση Παραγωγής:** Μια πρόχειρη εκτίμηση της καρποφορίας (π.χ. 'Χαμηλή', 'Μέτρια', 'Καλή').
           δ) **Ενημέρωση:** Πες του ότι 'Η φωτογραφία καταχωρήθηκε. Μπορείτε τώρα να χρησιμοποιήσετε τα εξειδικευμένα AI Εργαλεία για βαθύτερη ανάλυση σε κάθε τομέα.'.
           δ) **Κατάσταση Εδάφους:** Παρατήρησε ΑΥΣΤΗΡΑ αν στη φωτογραφία φαίνονται ψηλά χόρτα, κομμένα χόρτα ή γυμνό έδαφος και ΑΝΕΦΕΡΕ ΤΟ ξεκάθαρα (π.χ. "Τα χόρτα φαίνονται κομμένα").
           ε) **Ενημέρωση:** Πες του ότι 'Η φωτογραφία καταχωρήθηκε. Μπορείτε τώρα να χρησιμοποιήσετε τα εξειδικευμένα AI Εργαλεία για βαθύτερη ανάλυση σε κάθε τομέα.'.
           Βάλε action: "DIAGNOSIS". Το κείμενο της διάγνωσης θα αποθηκευτεί αυτόματα.
        2. Έλεγχος Αποθήκης: Πριν προτείνεις οποιοδήποτε υλικό, φάρμακο ή εργασία, ΕΛΕΓΞΕ ΑΥΣΤΗΡΑ την "ΑΠΟΘΗΚΗ ΥΛΙΚΩΝ" στο προφίλ του κτήματος. Αν το υλικό υπάρχει ήδη διαθέσιμο, πρότεινε να χρησιμοποιήσει αυτό για οικονομία.
        3. Επιβεβαίωση Αλλαγής Προφίλ: Αν ο χρήστης επιβεβαιώσει αλλαγή (π.χ. "Είναι αρδευόμενο", "Άλλαξέ το σε βιολογική", "Μετονόμασε σε...", "Το στάδιο είναι άνθιση", "Είναι ορεινό") συμπλήρωσε τις νέες τιμές στο object "updates". Αν ο χρήστης αναφέρει ότι φύτεψε, πρόσθεσε ή αφαίρεσε δέντρα (ακόμα και για ΜΙΑ ποικιλία, π.χ. "έβαλα 10 Αθηνοελιές"), ΧΡΗΣΙΜΟΠΟΙΗΣΕ ΠΑΝΤΑ το "poikilies_multi": [ {"onoma": "Αθηνοελιά", "arithmos": 10, "ilikia": "5 ετών"} ] όπου το "arithmos" είναι η ΔΙΑΦΟΡΑ (+10 για προσθήκη ή -5 για αφαίρεση). Το συνολικό "arithmos_dentron" θα υπολογιστεί αυτόματα, ΜΗΝ το στέλνεις. Αν είναι απλή ενημέρωση προφίλ, βάλε action: "UPDATE_KTIMA". Στο "target_ktima_id" γράψε ΑΥΣΤΗΡΑ το ID του κτήματος.
        4. Προσθήκη Εργασιών (Πολλαπλές & Ημερομηνίες): Αν ο χρήστης λέει ότι έκανε μία ή ΠΟΛΛΑΠΛΕΣ εργασίες (π.χ. "ράντισα και μετά από ένα μήνα κλάδεψα"), βάλε action: "ADD_TASKS".
           - Υπολόγισε την ΗΜΕΡΟΜΗΝΙΑ: Αν λέει "τον Νοέμβριο μετά τη συγκομιδή", υπολόγισε και βάλε μια σχετική ημερομηνία στο "date" (π.χ. "2025-11-15"). Αν είναι ασαφές, ρώτα τον στο "reply" (action: "DIAGNOSIS").
           - Κατάσταση (status): Αν η εργασία ΕΧΕΙ ΓΙΝΕΙ, βάλε "status": "Ολοκληρώθηκε". Αν ο χρήστης λέει "πρέπει να ραντίσω", "βάλε σε εκκρεμότητα/αναμονή να...", "πρόσθεσε στο πρόγραμμα", βάλε "status": "Εκκρεμεί".
           - Για κάθε εργασία, φτιάξε ένα αντικείμενο στη λίστα "tasks".
           - Αν ζητάει καταχώρηση σε ΟΛΑ τα κτήματα, βάλε "target_ktima_id": "ALL" στο task.
           - ΣΗΜΑΝΤΙΚΟ: Αν αναφέρει εμπορικό όνομα, βάλε τη δραστική στο "task_materials".
        5. Διαγραφή ή Τροποποίηση Εργασιών (Αλλαγή Ημερομηνίας): Για διαγραφή εργασιών, βάλε action: "DELETE_TASKS" και συμπλήρωσε τη λίστα "tasks_to_delete" με "target_ktima_id" (ή "ALL") και "task_name" ("ΟΛΕΣ" ή το όνομα). ΑΝ ο χρήστης ζητά να σβήσεις μια ΠΑΛΙΑ/ΣΥΓΚΕΚΡΙΜΕΝΗ εργασία (π.χ. 'τον ψεκασμό του Γενάρη'), βρες την στο ιστορικό και συμπλήρωσε ΚΑΙ το "task_date" (π.χ. '2024-01' ή '2024-01-15'). Αν ο χρήστης πει "Έκανα την εκκρεμή εργασία Χ", βάλε action: "UPDATE_TASK" και "new_task_data": {"status": "Ολοκληρώθηκε"}. Αν ζητήσει αλλαγή ΗΜΕΡΟΜΗΝΙΑΣ στο ημερολόγιο, υπολόγισε τη νέα ημερομηνία, βάλε action: "UPDATE_TASK" και συμπλήρωσε "new_task_data": {"date": "YYYY-MM-DD"}.
        6. Πληροφορίες Ημερολογίου, Εκκρεμοτήτων & Καιρού (ΣΗΜΑΝΤΙΚΟ): ΕΧΕΙΣ ΗΔΗ ΠΡΟΣΒΑΣΗ στο 'ΗΜΕΡΟΛΟΓΙΟ (ΕΚΚΡΕΜΕΙΣ ΕΡΓΑΣΙΕΣ)' και στο ιστορικό παραπάνω. Αν ο χρήστης σε ρωτήσει "τι έχω στο ημερολόγιο;" ή "τι δουλειές πρέπει να γίνουν;", διάβασε την ενότητα ΗΜΕΡΟΛΟΓΙΟ και ΑΠΑΝΤΗΣΕ ΑΜΕΣΑ με τις ημερομηνίες! Ταξινόμησέ τες με βάση το τι επείγει. ΑΠΑΓΟΡΕΥΕΤΑΙ να πεις "θα ψάξω", δώσε τα δεδομένα κατευθείαν στο "reply" με action: "ADVICE".
        7. Οικονομικά (Έξοδα/Έσοδα): Αν το έξοδο/έσοδο αφορά ΣΥΓΚΕΚΡΙΜΕΝΟ ΚΤΗΜΑ, βάλε action: "ADD_EXPENSE" ("expense_amount", "expense_desc"). Αν είναι ΓΕΝΙΚΑ έξοδα (ένα ή περισσότερα) βάλε action: "ADD_GENERAL_EXPENSE" και συμπλήρωσε ΥΠΟΧΡΕΩΤΙΚΑ τη λίστα "general_expenses" βάζοντας σε κάθε αντικείμενο: "amount" (αριθμός), "desc" (περιγραφή) και "category" (Επιλογές: "Αναλώσιμα", "Ζημιές", "Γενικά").
           - ΟΔΗΓΙΑ ΚΑΤΗΓΟΡΙΟΠΟΙΗΣΗΣ: Στα "Αναλώσιμα" ανήκουν: Λάδια, πετρέλαιο/καύσιμα, ελαστικά/λάστιχα οχημάτων, λάστιχα/σωλήνες άρδευσης (π.χ. Φ23, σταλάκτες), εργαλεία χειρός, μπαταρίες, πριόνια, ανταλλακτικά συντήρησης. Στις "Ζημιές" ανήκουν αυστηρά: Επισκευές από σπάσιμο (π.χ. έσπασε η αντλία, χάλασε το βυτίο/τρακτέρ), βλάβες και ζημιές από καιρικά φαινόμενα.
           Αν είναι ΓΕΝΙΚΟ έσοδο (π.χ. επιδότηση) βάλε action: "ADD_GENERAL_INCOME" και συμπλήρωσε "income_amount", "income_desc" ΚΑΙ "geniko_katigoria" ("Επιδότηση"). Για διαγραφή εξόδου/εσόδου (π.χ. "λάθος καταχώρηση", "σβήσε τα 50 ευρώ"), βάλε action: "DELETE_EXPENSE" και συμπλήρωσε "expense_desc" (λέξη κλειδί) ή/και "expense_amount" (ποσό).
        8. Διαγραφή Μετρήσεων Υγρασίας: Αν ζητήσει διαγραφή μέτρησης υγρασίας (π.χ. "σβήσε την τελευταία υγρασία", "διέγραψε την υγρασία 25%"), βάλε action: "DELETE_UGRASIA" και συμπλήρωσε το "moisture_percentage" (ποσοστό υγρασίας) ή "ugrasia_desc" (σχόλια στην υγρασία).
        8. Γεωπονική Συμβουλή: Αν ζητάει συμβουλή, ΚΑΝΕ ΥΠΟΧΡΕΩΤΙΚΑ αναζήτηση στο internet για να επιβεβαιώσεις 100% την ορθότητά της πριν απαντήσεις. Δώσε την απάντηση και βάλε action: "ADVICE".
        9. Καταγραφή Συγκομιδής: Αν ο χρήστης αναφέρει δεδομένα συγκομιδής (π.χ. "μάζεψα 5000 κιλά ελιές", "μάζεψα την Κορωνέικη 1000 κιλά"), βάλε action: "ADD_HARVEST". Στο JSON συμπλήρωσε "tonoi" (κιλά καρπού, 1 τόνος = 1000), "kila_ladi" (κιλά λαδιού) και "esoda" (ευρώ). ΣΗΜΑΝΤΙΚΟ: Βάλε "is_final": true ΑΝ ο χρήστης αναφέρει ότι τελείωσε όλη η συγκομιδή για φέτος (για να κλείσει η σεζόν). Αν είναι μερική συγκομιδή (π.χ. μάζεψε μόνο μία ποικιλία και έπεται συνέχεια), βάλε "is_final": false. Προαιρετικά βάλε "poikilia_sygkomidis": "Όνομα ποικιλίας" αν το αναφέρει.
        10. Ασαφή/Ελλιπή Δεδομένα: Αν ο χρήστης ζητήσει ενέργεια (π.χ. διαγραφή, ενημέρωση) για ένα κτήμα που ΔΕΝ υπάρχει στη λίστα, ΑΠΑΓΟΡΕΥΕΤΑΙ να πεις ψέματα ότι το έκανες. Πες του ότι δεν το βρίσκεις και ζήτα διευκρίνιση (action: "DIAGNOSIS"). Το ίδιο ισχύει για ελλιπή δεδομένα (π.χ. ρωτάει για εργασία και το ιστορικό είναι κενό).
        11. Διαχείριση Αποθήκης: Για αγορά/προσθήκη (ένα ή περισσότερα υλικά), βάλε action: "ADD_INVENTORY" και συμπλήρωσε ΥΠΟΧΡΕΩΤΙΚΑ τη λίστα "inventory_items" με αντικείμενα που έχουν "inv_name", "inv_category" (Φάρμακο, Λίπασμα, Εξοπλισμός), "inv_amount", "inv_unit" (Λίτρα, Κιλά, Τεμάχια) και προαιρετικά "expense_amount" (αν αναφέρει κόστος) και "expense_desc". Για διόρθωση υπολοίπου, βάλε action: "UPDATE_INVENTORY" (θέσε το "inv_name" και το "inv_amount" στο νέο νούμερο). Για πέταμα/διαγραφή προϊόντος, βάλε action: "DELETE_INVENTORY" (θέσε το "inv_name").
        12. Διαχείριση Υγρασίας & Νερού: Αν ο χρήστης αναφέρει μέτρηση υγρασίας (π.χ. "η υγρασία του εδάφους είναι 20%") ή ανάλυση νερού ("pH 7.2", "αγωγιμότητα 1.5"), βάλε action: "UPDATE_WATER" και συμπλήρωσε τα "moisture_percentage", "nero_ph", "nero_agwgimotita". Αν ρωτάει πόσο να ποτίσει, διάβασε τις 'Ανάγκες Άρδευσης' από τα δεδομένα και απάντησέ του.
        13. Γενικές / Άσχετες Ερωτήσεις (Internet Access): Είσαι πλέον συνδεδεμένος και στο διαδίκτυο (Google Search). Αν ο χρήστης σε ρωτήσει κάτι εντελώς άσχετο με τα χωράφια (π.χ. συνταγή μαγειρικής, ποιος κέρδισε έναν αγώνα, ειδήσεις, ιστορία), ΑΠΑΝΤΗΣΕ ΤΟΥ ΦΥΣΙΟΛΟΓΙΚΑ, φιλικά και σύντομα. ΜΗΝ προσπαθήσεις να συνδέσεις την ερώτηση με τα κτήματα. Βάλε action: "ADVICE". Αν ο χρήστης γράψει κάτι εντελώς ακατανόητο, γράψε στο reply: "Συγγνώμη, δεν σας κατάλαβα."
        14. Δημιουργία Νέου Κτήματος: Αν ο χρήστης ζητήσει να δημιουργήσεις ένα νέο κτήμα (π.χ. "φτιάξε ένα κτήμα"), βάλε action: "ADD_KTIMA" και συμπλήρωσε το "new_ktima_data". Το "onoma_ktimatos" είναι υποχρεωτικό. Στο "reply" σου πες του ευγενικά: "Το κτήμα δημιουργήθηκε! Σας ανοίγω αυτόματα τον χάρτη για να ορίσετε την ακριβή τοποθεσία.". ΜΗΝ ρωτάς "Σε ποια περιοχή βρίσκεται".
        15. Διαγραφή / Αρχειοθέτηση Κτήματος: Αν θέλει να ΔΙΑΓΡΑΨΕΙ οριστικά ένα κτήμα, βάλε "DELETE_KTIMA" (Ρώτα τον πρώτα για επιβεβαίωση). Αν θέλει να το κρύψει/αρχειοθετήσει, βάλε "ARCHIVE_KTIMA". 
        16. Επιλογή/Αλλαγή/Σύγκριση Κτημάτων: Αν ο χρήστης ζητήσει να μεταβείτε σε ένα συγκεκριμένο κτήμα (π.χ. "Άλλαξε στο...", "Πάμε στο...", "Δες το..."), βρες ΑΥΣΤΗΡΑ τον αριθμό ID του από τη Λίστα Ενεργών Κτημάτων. Βάλε action: "SWITCH_KTIMA" και "target_ktima_id" τον ΑΡΙΘΜΟ ID. 
        ΣΗΜΑΝΤΙΚΟ: Αν ο χρήστης ζητήσει να δει ΠΑΝΩ ΑΠΟ ΕΝΑ κτήματα ταυτόχρονα, ή ζητήσει ΣΥΓΚΡΙΣΗ (π.χ. "σύγκρινε το Α με το Β", "τι διαφορά έχει το Α με το Β"), Ή ζητήσει "όλα τα κτήματα", ΤΟΤΕ βάλε ΑΥΣΤΗΡΑ "target_ktima_id": "ALL" και action: "SWITCH_KTIMA". 
        ΜΗΝ βάλεις ποτέ το όνομα ως target_ktima_id, μόνο το ID ή "ALL"! Στο "reply", εφόσον έχεις πλέον πρόσβαση στα δεδομένα όλων των κτημάτων στο prompt σου, απάντησε απευθείας στο ερώτημά του (π.χ. κάνε τη σύγκριση που ζήτησε ή επιβεβαίωσε την αλλαγή).
        17. Εργαστηριακή Ανάλυση Εδάφους/Φύλλων: Αν ο χρήστης ανεβάσει ανάλυση, ΔΙΑΒΑΣΕ ΤΑ ΔΕΔΟΜΕΝΑ. ΠΡΟΣΟΧΗ: Αν η εικόνα είναι πολύ θολή/δυσανάγνωστη ή λείπει σελίδα (π.χ. έχει μόνο τη σελ. 1 από 2), ΑΠΑΝΤΗΣΕ ΤΟΥ στο "reply" να την ξανανεβάσει σωστά και βάλε action: "ADVICE". ΑΝ ΕΙΝΑΙ ΚΑΘΑΡΗ, βάλε action: "ADD_ANALYSIS". Στο "new_analysis_data" συμπλήρωσε "ph", "organiki_ousia", "azwto" (N), "fwsforos" (P), "kalio" (K) με αριθμούς. Αν αναφέρει τύπο εδάφους (π.χ. Αργιλώδες), βάλτο στο "typos_edafous". Αν ο χρήστης πει πότε έγινε (π.χ. "είναι περσινή", "τον Οκτώβριο του '24"), υπολόγισε την ημερομηνία και βάλτην στο "date" (YYYY-MM-DD).
        18. ΠΟΛΛΑΠΛΕΣ ΕΝΕΡΓΕΙΕΣ ΤΑΥΤΟΧΡΟΝΑ (MULTI-ACTION): Αν ο χρήστης ζητήσει ΠΟΛΛΑΠΛΕΣ ΚΑΙ ΔΙΑΦΟΡΕΤΙΚΕΣ ενέργειες ταυτόχρονα (π.χ. "Διέγραψε όλες τις εργασίες ΚΑΙ πρόσθεσε ράντισμα στο Κτήμα Α" Ή "Ράντισμα στο Κτήμα Α ΚΑΙ έκοψα χόρτα στο Β"), βάλε action: "MULTI_ACTION". Το JSON σου πρέπει να περιέχει ΤΑΥΤΟΧΡΟΝΑ όσες από τις λίστες χρειάζεται: "tasks_to_delete" (για διαγραφές), "tasks" (για νέες εργασίες), "general_expenses" (για γενικά έξοδα) ΚΑΙ "inventory_items" (για την αποθήκη). Το σύστημα θα τα εκτελέσει με τη σωστή σειρά (πρώτα διαγραφές, μετά προσθήκες)!
        
        Επίστρεψε ΑΥΣΤΗΡΑ ένα JSON με την εξής μορφή (χωρίς markdown, καθαρό JSON):
        {
            "reply": "Η απάντησή σου στον αγρότη. (Σύντομη, φιλική, άμεση)",
            "action": "MULTI_ACTION" | "ADD_TASKS" | "DIAGNOSIS" | "ADVICE" | "UPDATE_KTIMA" | "DELETE_TASKS" | "UPDATE_TASK" | "ADD_EXPENSE" | "ADD_INCOME" | "ADD_GENERAL_EXPENSE" | "ADD_GENERAL_INCOME" | "DELETE_EXPENSE" | "DELETE_UGRASIA" | "ADD_HARVEST" | "ADD_INVENTORY" | "UPDATE_INVENTORY" | "DELETE_INVENTORY" | "UPDATE_WATER" | "ADD_KTIMA" | "DELETE_KTIMA" | "ARCHIVE_KTIMA" | "SWITCH_KTIMA" | "ADD_ANALYSIS",
            "tasks": [
                {
                    "target_ktima_id": "Αριθμός ID κτήματος Ή 'ALL'",
                    "task_name": "Ονομασία Εργασίας...",
                    "task_materials": "Φάρμακα/Λιπάσματα - ΚΕΝΟ αν δεν αναφέρεται",
                    "date": "YYYY-MM-DD",
                "status": "Ολοκληρώθηκε ή Εκκρεμεί",
                    "expense_amount": 100.5,
                    "expense_desc": "Περιγραφή κόστους",
                    "used_material_name": "Όνομα από αποθήκη",
                    "used_material_amount": 2.5
                }
            ],
            "tasks_to_delete": [
                {
                    "target_ktima_id": "ALL",
                    "task_name": "ΟΛΕΣ ή όνομα εργασίας",
                    "task_date": "YYYY-MM ή YYYY-MM-DD (Προαιρετικό)"
                }
            ],
            "target_ktima_id": "Αριθμός ID Ή 'ALL' (γενική χρήση)",
            "task_name": "ΟΛΕΣ ή λέξη (Μόνο για DELETE_TASKS ή UPDATE_TASK)",
            "expense_amount": 50,
            "expense_desc": "Περιγραφή κόστους",
            "general_expenses": [
                {
                    "amount": 120,
                    "desc": "Μπαταρία",
                    "category": "Ζημιές"
                }
            ],
            "income_amount": 500,
            "income_desc": "Περιγραφή εσόδου",
            "geniko_katigoria": "Αναλώσιμα",
            "tonoi": 5000,
            "kila_ladi": 1000,
            "esoda": 2000,
            "is_final": true,
            "poikilia_sygkomidis": "Κορωνέικη",
            "inventory_items": [
                {
                    "inv_name": "Όνομα προϊόντος",
                    "inv_category": "Φάρμακο",
                    "inv_amount": 10,
                    "inv_unit": "Λίτρα",
                    "expense_amount": 50,
                    "expense_desc": "Αγορά Φαρμάκου"
                }
            ],
            "inv_name": "Όνομα προϊόντος",
            "inv_category": "Φάρμακο",
            "inv_amount": 10,
            "inv_unit": "Λίτρα",
            "moisture_percentage": 25.5,
            "new_task_data": {
                "date": "YYYY-MM-DD",
                "task_name": "Νέο όνομα αν ζητήθηκε αλλαγή",
            "task_materials": "Νέα υλικά αν ζητήθηκε αλλαγή",
            "status": "Ολοκληρώθηκε ή Εκκρεμεί ή Ακυρώθηκε"
            },
            "new_ktima_data": {
                "onoma_ktimatos": "Όνομα...",
                "arithmos_dentron": 20,
                "poikilia": "Κορωνέικη",
                "ilikia_dentron": "Παραγωγικά (6-40 ετών) ή ότι αναφέρει",
                "poikilies_multi": [{"onoma": "Κορωνέικη", "arithmos": 20}]
            },
            "new_analysis_data": {
                "date": "YYYY-MM-DD",
                "ph": 7.2,
                "organiki_ousia": 2.5,
                "azwto": 15.0,
                "fwsforos": 10.0,
                "kalio": 20.0,
                "typos_edafous": "Αργιλώδες"
            },
            "nero_ph": 7.2,
            "nero_agwgimotita": 1.5,
            "updates": {
                "ardefsi": "Αρδευόμενο" ή "Ξηρικό" ή null,
                "diacheirisi_edafous": "Καθαρό (Οργωμένο/Ζιζανιοκτονία)" ή "Φυσική Βλάστηση (Άκοπα χόρτα)" ή "Κομμένα Χόρτα" ή null,
                "puknotita_dentron": "Αραιή" ή "Κανονική" ή "Πυκνή/Υπέρπυκνη" ή null,
                "kalliergeia_typos": "Βιολογική" ή "Συμβατική" ή null,
                "ilikia_dentron": "Νεαρά (1-5 ετών)" ή "Παραγωγικά (6-40 ετών)" ή "Γηραιά (40+ ετών)" ή null,
                "stremmata": Αριθμός στρεμμάτων (π.χ. 12.5) ή null,
                "arithmos_dentron": Αριθμός δέντρων (ακέραιος, π.χ. 150) ή null,
                "typos_edafous": "Αμμώδες" ή "Αργιλώδες" ή "Πηλώδες" ή "Πετρώδες" ή null,
                "poikilia": "Όνομα ποικιλίας (π.χ. Κορωνέικη) ή null",
                "onoma_ktimatos": "Νέο όνομα κτήματος ή null",
                "klisi": "Πεδινό, Επικλινές/Πλαγιά, Ορεινό, Ρέμα/Κοιλότητα ή null",
                "fainologiko_stadio": "π.χ. Άνθιση, Λήθαργος, Καρπόδεση ή null"
            }
        }
        """
        contents.append(prompt)

        for img_file in image_files:
            if img_file.filename != '':
                mime_type = img_file.mimetype
                if 'pdf' in mime_type:
                    file_data = img_file.read()
                    contents.append(types.Part.from_bytes(data=file_data, mime_type='application/pdf'))
                else:
                    img = PIL.Image.open(img_file)
                    # Δραστική συμπίεση/σμίκρυνση εικόνας για αποφυγή 503/Timeout
                    img.thumbnail((1024, 1024), PIL.Image.Resampling.LANCZOS)
                    if img.mode in ('RGBA', 'P'):
                        img = img.convert('RGB')
                        
                    # Μετατροπή σε JPEG Bytes (Μειώνει το payload από ~5MB σε ~150KB)
                    img_byte_arr = io.BytesIO()
                    img.save(img_byte_arr, format='JPEG', quality=75)
                    img_bytes = img_byte_arr.getvalue()
                    contents.append(types.Part.from_bytes(data=img_bytes, mime_type='image/jpeg'))
                
        # Ενεργοποίηση Google Search (Ζωντανή Πρόσβαση στο Διαδίκτυο)
        config = types.GenerateContentConfig(
            tools=[{"google_search": {}}]
        )
        
        import time
        response = None
        for attempt in range(3):
            try:
                response = client.models.generate_content(model='gemini-2.5-flash', contents=contents, config=config)
                break
            except Exception as e:
                if attempt == 2:
                    raise e
                time.sleep(3 * (attempt + 1)) # Backoff: περιμένει 3s, μετά 6s αν αποτύχει
        
        # Δικλείδα Ασφαλείας: Αν το AI επιστρέψει κενό (π.χ. λόγω safety filters)
        if not response or not getattr(response, 'text', None):
            return jsonify({'success': True, 'reply': '⚠️ Δεν κατάφερα να διακρίνω καθαρά τη φωτογραφία ή το κείμενο. Μπορείτε να ανεβάσετε μια πιο καθαρή λήψη;', 'action': 'ADVICE'})
            
        json_text = response.text.strip().replace('```json', '').replace('```', '').strip()
        data = json.loads(json_text, strict=False)
        
        action = data.get('action', 'ADVICE')
        reply_text = data.get('reply', 'Συγγνώμη, δεν σας κατάλαβα.')
        import re
        reply_text = re.sub(r'\s*\(?ID:\s*\d+\)?', '', reply_text, flags=re.IGNORECASE)
        target_ktima_id = data.get('target_ktima_id')
        
        # Χρήση της επιλογής από το μενού ως προεπιλογή αν το AI δεν έστειλε κάτι
        if not target_ktima_id:
            target_ktima_id = ktima_id
            
        # Αν το AI βρήκε άλλο κτήμα βάσει ονόματος (ή πήρε το επιλεγμένο), το χρησιμοποιούμε
        if target_ktima_id and str(target_ktima_id).upper() not in ['ALL', 'NONE']:
            try:
                ktima_id_int = int(target_ktima_id)
                target_ktima = vasi.session.get(Ktima, ktima_id_int)
                if target_ktima and target_ktima.idioktitis == current_user:
                    ktima = target_ktima
                    target_ktima_id = ktima.id
            except (ValueError, TypeError):
                # Δοκιμή εύρεσης με βάση το όνομα (Σε περίπτωση που το AI έστειλε όνομα αντί για ID)
                for k in energa_ktimata:
                    if str(target_ktima_id).lower().strip() in k.onoma_ktimatos.lower():
                        ktima = k
                        target_ktima_id = ktima.id
                        break
        
        # Backend Safety Check: Αποφυγή AI Hallucinations
        if target_ktima_id and str(target_ktima_id).upper() not in ['ALL', 'NONE'] and not ktima:
            if action not in ['ADVICE', 'DIAGNOSIS', 'ADD_KTIMA', 'ADD_INVENTORY']:
                reply_text = "Συγγνώμη, αλλά δεν βρήκα κάποιο κτήμα με αυτό το όνομα. Παρακαλώ ελέγξτε τη λίστα με τα ενεργά κτήματά σας."
                action = 'DIAGNOSIS'
                target_ktima_id = None

        # --- ΠΡΩΤΑ ΕΚΤΕΛΟΥΝΤΑΙ ΟΙ ΔΙΑΓΡΑΦΕΣ ΕΡΓΑΣΙΩΝ (Για να μην σβηστούν οι νέες αν γίνει MULTI_ACTION) ---
        if action in ['DELETE_TASKS', 'MULTI_ACTION']:
            del_list = data.get('tasks_to_delete', [])
            if not del_list and data.get('task_name') and action != 'MULTI_ACTION':
                del_list = [{'target_ktima_id': target_ktima_id, 'task_name': data.get('task_name')}]
                
            for del_item in del_list:
                t_name = del_item.get('task_name', '')
                t_date = del_item.get('task_date', '')
                t_k_id = del_item.get('target_ktima_id') or target_ktima_id
                
                del_targets = []
                if str(t_k_id).upper() == 'ALL':
                    del_targets = energa_ktimata
                else:
                    try:
                        k_id_int = int(t_k_id)
                        k = vasi.session.get(Ktima, k_id_int)
                        if k and k.idioktitis == current_user: del_targets.append(k)
                    except (ValueError, TypeError):
                        if ktima: del_targets.append(ktima)
                        
                for target_k in del_targets:
                    if t_name == 'ΟΛΕΣ' and not t_date:
                        Ergasia.query.filter_by(ktima_id=target_k.id).delete()
                        vasi.session.add(Diagnosi(ktima_id=target_k.id, apotelesma="🗑️ AI Γραμματέας: Έγινε διαγραφή όλων των εργασιών.", imerominia=datetime.now()))
                    elif t_name or t_date:
                        tasks_to_check = Ergasia.query.filter_by(ktima_id=target_k.id).order_by(Ergasia.imerominia.desc()).all()
                        
                        deleted_count = 0
                        for t in tasks_to_check:
                            match_name = False
                            match_date = False
                            
                            if t_name and t_name != 'ΟΛΕΣ':
                                eidos = (t.eidos_ergasias or "").lower()
                                farmaka = (t.farmaka_lipasmata or "").lower()
                                search_term = t_name.lower()
                                
                                if search_term in eidos or search_term in farmaka:
                                    match_name = True
                                else:
                                    # Ψάχνουμε μεμονωμένες λέξεις > 3 χαρακτήρων αν δεν ταιριάζει ακριβώς
                                    words = [w for w in search_term.split() if len(w) > 3]
                                    for w in words:
                                        if w in eidos or w in farmaka:
                                            match_name = True
                                            break
                            else:
                                match_name = True
                                
                            if t_date:
                                if t.imerominia.strftime('%Y-%m-%d').startswith(t_date):
                                    match_date = True
                            else:
                                match_date = True
                                
                            if match_name and match_date:
                                vasi.session.delete(t)
                                deleted_count += 1
                                # Προστασία: Αν δεν δόθηκε ημερομηνία, σβήνουμε ΜΟΝΟ την πιο πρόσφατη που ταιριάζει
                                if not t_date and t_name != 'ΟΛΕΣ':
                                    break
                                
                        if deleted_count > 0:
                            vasi.session.add(Diagnosi(ktima_id=target_k.id, apotelesma=f"🗑️ AI Γραμματέας: Έγινε διαγραφή {deleted_count} εργασίας ({t_name} {t_date}).", imerominia=datetime.now()))
                    
                    target_k.ekkremis_erotisi_ai = None
        
        if action in ['ADD_TASK', 'ADD_TASKS', 'MULTI_ACTION']:
            tasks_list = data.get('tasks', [])
            # Αν το AI γύρισε παλιά δομή (1 εργασία)
            if not tasks_list and data.get('task_name') and action != 'MULTI_ACTION':
                tasks_list = [data]
                
            for task_data in tasks_list:
                t_ktima_id = task_data.get('target_ktima_id') or target_ktima_id
                target_ktimata = []
                if str(t_ktima_id).upper() == 'ALL':
                    target_ktimata = energa_ktimata
                else:
                    try:
                        k_id = int(t_ktima_id)
                        k = vasi.session.get(Ktima, k_id)
                        if k and k.idioktitis == current_user:
                            target_ktimata.append(k)
                    except (ValueError, TypeError):
                        if ktima: target_ktimata.append(ktima)
                        
                for target_k in target_ktimata:
                    date_str = task_data.get('date')
                    im = datetime.now()
                    if date_str:
                        try: im = datetime.strptime(date_str, '%Y-%m-%d')
                        except: pass
                        
                    status_ergasias = task_data.get('status', 'Ολοκληρώθηκε')
                    nea_ergasia = Ergasia(
                        ktima_id=target_k.id, 
                        eidos_ergasias=task_data.get('task_name', 'Νέα Εργασία'),
                        katastasi=status_ergasias,
                        imerominia=im,
                        farmaka_lipasmata=task_data.get('task_materials', ''),
                        proelevsi='AI Γραμματέας'
                    )
                    vasi.session.add(nea_ergasia)
                    
                    poso = task_data.get('expense_amount')
                    if poso is not None:
                        try: vasi.session.add(Exodo(ktima_id=target_k.id, perigrafi=task_data.get('expense_desc') or f"Κόστος: {task_data.get('task_name', 'Εργασία')}", poso=float(poso), imerominia=im))
                        except (ValueError, TypeError): pass
                        
                    used_material_name = task_data.get('used_material_name')
                    used_material_amount = task_data.get('used_material_amount')
                    if used_material_name and used_material_amount is not None:
                        try:
                            amount = float(used_material_amount)
                            item = Apothiki.query.filter_by(xrhsths_id=current_user.id, onoma_proiontos=used_material_name).first()
                            if item and amount > 0:
                                item.posotita = max(0, item.posotita - amount)
                                vasi.session.add(Diagnosi(ktima_id=target_k.id, apotelesma=f"📦 AI Αποθήκη: Αφαιρέθηκαν {amount} {item.monada_metrisis} από '{item.onoma_proiontos}'.", imerominia=datetime.now()))
                        except (ValueError, TypeError): pass
                    
                    target_k.ekkremis_erotisi_ai = None
                
        # Ενημερώσεις προφίλ ανεξάρτητα από το action (ώστε να δουλεύει ΠΑΡΑΛΛΗΛΑ με το ADD_TASKS)
        updates = data.get('updates')
        if isinstance(updates, dict):
            ktimata_to_update = []
            if str(target_ktima_id).upper() == 'ALL':
                ktimata_to_update = energa_ktimata
            elif ktima:
                ktimata_to_update = [ktima]
                
            for target_k in ktimata_to_update:
                updated_fields = []
                if updates.get('onoma_ktimatos'):
                    target_k.onoma_ktimatos = updates['onoma_ktimatos']
                    updated_fields.append(f"Όνομα (σε {target_k.onoma_ktimatos})")
                if updates.get('klisi'):
                    target_k.klisi = updates['klisi']
                    updated_fields.append('Κλίση')
                if updates.get('fainologiko_stadio'):
                    target_k.fainologiko_stadio = updates['fainologiko_stadio']
                    updated_fields.append(f"Στάδιο ({target_k.fainologiko_stadio})")
                if updates.get('ardefsi'):
                    target_k.ardefsi = updates['ardefsi']
                    updated_fields.append('Άρδευση')
                if updates.get('diacheirisi_edafous'):
                    target_k.diacheirisi_edafous = updates['diacheirisi_edafous']
                    updated_fields.append('Διαχείριση Εδάφους')
                if updates.get('puknotita_dentron'):
                    target_k.puknotita_dentron = updates['puknotita_dentron']
                    updated_fields.append('Πυκνότητα Δέντρων')
                if updates.get('kalliergeia_typos'):
                    target_k.kalliergeia_typos = updates['kalliergeia_typos']
                    updated_fields.append('Τύπος Καλλιέργειας')
                if updates.get('ilikia_dentron'):
                    target_k.ilikia_dentron = updates['ilikia_dentron']
                    updated_fields.append('Ηλικία Δέντρων')
                if updates.get('stremmata') is not None:
                    try: target_k.stremmata = float(updates['stremmata']); updated_fields.append('Στρέμματα')
                    except (ValueError, TypeError): pass
                
                # Smart Tree & Variety Logic
                old_dentra = target_k.arithmos_dentron
                nea_dentra = old_dentra
                tree_count_changed = False
                
                raw_arithmos = updates.get('arithmos_dentron')
                is_zero_trees = False
                if raw_arithmos is not None:
                    try:
                        if int(raw_arithmos) == 0:
                            is_zero_trees = True
                    except: pass

                if is_zero_trees:
                    target_k.arithmos_dentron = 0
                    for p in list(target_k.poikilies_details):
                        vasi.session.delete(p)
                    target_k.poikilia = 'Δεν ορίστηκε'
                    updated_fields.append('Αριθμός Δέντρων (0)')
                    tree_count_changed = True
                elif updates.get('poikilies_multi'):
                    try:
                        import unicodedata
                        def normalize_str(s):
                            if not s: return ""
                            s_norm = unicodedata.normalize('NFD', str(s))
                            return ''.join(c for c in s_norm if unicodedata.category(c) != 'Mn').lower().strip()
                            
                        for item in updates['poikilies_multi']:
                            v_name = item.get('onoma')
                            v_diff = item.get('arithmos', 0)
                            v_age = item.get('ilikia')
                            if v_name and v_diff != 0:
                                req_p_norm = normalize_str(v_name)
                                req_age_norm = normalize_str(v_age)
                                if v_diff > 0:
                                    found = False
                                    for p in target_k.poikilies_details:
                                        if normalize_str(p.poikilia_onoma) == req_p_norm:
                                            if req_age_norm and p.ilikia_dentron and normalize_str(p.ilikia_dentron) != req_age_norm:
                                                continue
                                            p.arithmos_dentron += v_diff
                                            found = True
                                            break
                                    if not found:
                                        from models import KtimaPoikilia
                                        neo_p = KtimaPoikilia(ktima_id=target_k.id, poikilia_onoma=v_name, arithmos_dentron=v_diff, ilikia_dentron=v_age or target_k.ilikia_dentron)
                                        vasi.session.add(neo_p)
                                        target_k.poikilies_details.append(neo_p)
                                else:
                                    ypoloipo = abs(v_diff)
                                    for p in list(target_k.poikilies_details):
                                        if normalize_str(p.poikilia_onoma) == req_p_norm:
                                            if req_age_norm and p.ilikia_dentron and normalize_str(p.ilikia_dentron) != req_age_norm:
                                                continue
                                            if p.arithmos_dentron > ypoloipo:
                                                p.arithmos_dentron -= ypoloipo
                                                ypoloipo = 0
                                                break
                                            else:
                                                ypoloipo -= p.arithmos_dentron
                                                p.arithmos_dentron = 0
                                                vasi.session.delete(p)
                        vasi.session.flush()
                        
                        energes_poikilies = [p for p in target_k.poikilies_details if p.arithmos_dentron > 0]
                        target_k.arithmos_dentron = sum(p.arithmos_dentron for p in energes_poikilies)
                        unique_p = list(set([p.poikilia_onoma for p in energes_poikilies]))
                        target_k.poikilia = 'Ανάμεικτο' if len(unique_p) > 1 else (unique_p[0] if unique_p else 'Δεν ορίστηκε')
                        updated_fields.append('Πολλαπλές Ποικιλίες (Δέντρα)')
                        tree_count_changed = True
                    except Exception as e:
                        print("Σφάλμα multi poikilies AI:", e)
                elif updates.get('arithmos_dentron') is not None:
                    try:
                        nea_dentra = int(updates['arithmos_dentron'])
                        if nea_dentra != old_dentra:
                            target_k.arithmos_dentron = nea_dentra
                            updated_fields.append(f'Αριθμός Δέντρων ({nea_dentra})')
                            tree_count_changed = True
                            
                            diff = nea_dentra - old_dentra
                            requested_poikilia = updates.get('poikilia')
                            
                            if requested_poikilia and target_k.poikilies_details:
                                import unicodedata
                                def normalize_str(s):
                                    if not s: return ""
                                    s_norm = unicodedata.normalize('NFD', str(s))
                                    return ''.join(c for c in s_norm if unicodedata.category(c) != 'Mn').lower().strip()
                                
                                req_p_norm = normalize_str(requested_poikilia)
                                requested_ilikia = updates.get('ilikia_dentron')
                                req_age_norm = normalize_str(requested_ilikia)
                                
                                if diff > 0:
                                    found = False
                                    for p in target_k.poikilies_details:
                                        if normalize_str(p.poikilia_onoma) == req_p_norm:
                                            if req_age_norm and p.ilikia_dentron:
                                                if normalize_str(p.ilikia_dentron) != req_age_norm:
                                                    continue
                                            p.arithmos_dentron += diff
                                            found = True
                                            break
                                    if not found:
                                        from models import KtimaPoikilia
                                        ilikia_to_save = requested_ilikia if requested_ilikia else target_k.ilikia_dentron
                                        neo_p = KtimaPoikilia(ktima_id=target_k.id, poikilia_onoma=requested_poikilia, arithmos_dentron=diff, ilikia_dentron=ilikia_to_save)
                                        vasi.session.add(neo_p)
                                        target_k.poikilies_details.append(neo_p)
                                        target_k.poikilia = 'Ανάμεικτο'
                                else:
                                    ypoloipo = abs(diff)
                                    for p in list(target_k.poikilies_details):
                                        if normalize_str(p.poikilia_onoma) == req_p_norm:
                                            if p.arithmos_dentron > ypoloipo:
                                                p.arithmos_dentron -= ypoloipo
                                                ypoloipo = 0
                                                break
                                            else:
                                                ypoloipo -= p.arithmos_dentron
                                                p.arithmos_dentron = 0
                                                vasi.session.delete(p)
                            elif target_k.poikilies_details:
                                if diff > 0:
                                    target_k.poikilies_details[0].arithmos_dentron += diff
                                else:
                                    ypoloipo = abs(diff)
                                    for p in list(target_k.poikilies_details):
                                        if p.arithmos_dentron > ypoloipo:
                                            p.arithmos_dentron -= ypoloipo
                                            ypoloipo = 0
                                            break
                                        else:
                                            ypoloipo -= p.arithmos_dentron
                                            p.arithmos_dentron = 0
                                            vasi.session.delete(p)
                    except (ValueError, TypeError): pass
                if updates.get('typos_edafous'):
                    target_k.typos_edafous = updates['typos_edafous']
                    updated_fields.append('Τύπος Εδάφους')
                if updates.get('poikilia'):
                    nea_poikilia = updates['poikilia']
                    # Μόνο αν δεν προστέθηκαν δέντρα παραπάνω
                    if not tree_count_changed:
                        target_k.poikilia = nea_poikilia
                        updated_fields.append(f'Ποικιλία ({nea_poikilia})')
                        if target_k.poikilies_details and len(target_k.poikilies_details) == 1:
                            target_k.poikilies_details[0].poikilia_onoma = nea_poikilia
                if updated_fields:
                    vasi.session.add(Diagnosi(ktima_id=target_k.id, apotelesma=f"⚙️ Ενημέρωση Προφίλ από AI: {', '.join(updated_fields)}", imerominia=datetime.now()))
                    target_k.teleftaia_enimerosi_ergasion = None
                    target_k.ai_sumvouli_date = None
                    target_k.ekkremis_erotisi_ai = None

        if action == 'UPDATE_TASK':
            task_name = data.get('task_name', '')
            new_data = data.get('new_task_data') or {}
            target_ktimata = energa_ktimata if str(target_ktima_id).upper() == 'ALL' else ([ktima] if ktima else [])
            
            for target_k in target_ktimata:
                if task_name:
                    # Βρίσκουμε την πιο πρόσφατη εργασία που ταιριάζει με το όνομα
                    task_to_edit = Ergasia.query.filter_by(ktima_id=target_k.id).filter(Ergasia.eidos_ergasias.ilike(f"%{task_name}%")).order_by(Ergasia.imerominia.desc()).first()
                    if task_to_edit:
                        if new_data.get('date'):
                            try: task_to_edit.imerominia = datetime.strptime(new_data['date'], '%Y-%m-%d')
                            except: pass
                        if new_data.get('task_name'):
                            task_to_edit.eidos_ergasias = new_data['task_name']
                        if new_data.get('task_materials'):
                            task_to_edit.farmaka_lipasmata = new_data['task_materials']
                    if new_data.get('status'):
                        task_to_edit.katastasi = new_data['status']
                        vasi.session.add(Diagnosi(ktima_id=target_k.id, apotelesma=f"✏️ AI Γραμματέας: Τροποποιήθηκε η εργασία '{task_name}'.", imerominia=datetime.now()))
                
                target_k.ekkremis_erotisi_ai = None

        elif action == 'ADD_EXPENSE':
            poso = data.get('expense_amount')
            perigrafi = data.get('expense_desc', 'Νέο Έξοδο (Από AI)')
            
            k_id_to_charge = ktima.id if ktima else None
            if not k_id_to_charge and target_ktima_id and str(target_ktima_id).upper() != 'ALL':
                try: k_id_to_charge = int(target_ktima_id)
                except: pass
            if not k_id_to_charge and energa_ktimata:
                k_id_to_charge = energa_ktimata[0].id
                
            if k_id_to_charge and poso is not None:
                try:
                    poso = float(poso)
                    neo_exodo = Exodo(ktima_id=k_id_to_charge, perigrafi=perigrafi, poso=poso, imerominia=datetime.now())
                    vasi.session.add(neo_exodo)
                    vasi.session.add(Diagnosi(ktima_id=k_id_to_charge, apotelesma=f"💶 AI Γραμματέας: Προστέθηκε έξοδο '{perigrafi}' ({poso}€).", imerominia=datetime.now()))
                except (ValueError, TypeError): pass
        elif action == 'ADD_INCOME':
            poso = data.get('income_amount')
            perigrafi = data.get('income_desc', 'Νέο Έσοδο')
            
            k_id_to_charge = ktima.id if ktima else None
            if not k_id_to_charge and target_ktima_id and str(target_ktima_id).upper() != 'ALL':
                try: k_id_to_charge = int(target_ktima_id)
                except: pass
            if not k_id_to_charge and energa_ktimata:
                k_id_to_charge = energa_ktimata[0].id
                
            if k_id_to_charge and poso is not None:
                try:
                    poso = float(poso)
                    # Αποθηκεύουμε το έσοδο ως αρνητικό έξοδο για να μειώσει το συνολικό κόστος
                    neo_exodo = Exodo(ktima_id=k_id_to_charge, perigrafi=f"ΕΣΟΔΟ / ΕΠΙΔΟΤΗΣΗ: {perigrafi}", poso=-poso, imerominia=datetime.now())
                    vasi.session.add(neo_exodo)
                    vasi.session.add(Diagnosi(ktima_id=k_id_to_charge, apotelesma=f"💶 AI Γραμματέας: Προστέθηκε έσοδο '{perigrafi}' (+{poso}€).", imerominia=datetime.now()))
                except (ValueError, TypeError): pass
        
        if action in ['ADD_GENERAL_EXPENSE', 'MULTI_ACTION']:
            g_exps = data.get('general_expenses', [])
            # Εφεδρικός έλεγχος αν το AI χρησιμοποίησε το παλιό, μονό σχήμα
            if not g_exps and data.get('expense_amount') is not None and action != 'MULTI_ACTION':
                g_exps = [{'amount': data.get('expense_amount'), 'desc': data.get('expense_desc', 'Γενικό Έξοδο'), 'category': data.get('geniko_katigoria', 'Γενικά')}]
                
            for ge in g_exps:
                poso = ge.get('amount')
                perigrafi = ge.get('desc', 'Γενικό Έξοδο')
                katigoria = ge.get('category', 'Γενικά')
                if poso is not None:
                    try:
                        poso = float(poso)
                        vasi.session.add(GenikoExodo(xrhsths_id=current_user.id, perigrafi=perigrafi, poso=poso, katigoria=katigoria, imerominia=datetime.now()))
                    except (ValueError, TypeError): pass
        
        if action in ['ADD_GENERAL_INCOME', 'MULTI_ACTION']:
            poso = data.get('income_amount')
            perigrafi = data.get('income_desc', 'Γενικό Έσοδο / Επιδότηση')
            katigoria = data.get('geniko_katigoria', 'Επιδότηση')
            if poso is not None and action != 'MULTI_ACTION':
                try:
                    poso = float(poso)
                    vasi.session.add(GenikoExodo(xrhsths_id=current_user.id, perigrafi=perigrafi, poso=-poso, katigoria=katigoria, imerominia=datetime.now()))
                except (ValueError, TypeError): pass
                
        if action in ['DELETE_EXPENSE', 'MULTI_ACTION']:
            desc = data.get('expense_desc')
            amount = data.get('expense_amount')
            if desc or amount is not None:
                # 1. Πρώτα ψάχνουμε στα Γενικά Έξοδα (καθώς είναι συνήθως πιο γενικά λάθη)
                query_geniko = GenikoExodo.query.filter_by(xrhsths_id=current_user.id)
                if amount is not None:
                    try: query_geniko = query_geniko.filter_by(poso=float(amount))
                    except: pass
                if desc:
                    query_geniko = query_geniko.filter(GenikoExodo.perigrafi.ilike(f"%{desc}%"))
                
                geniko_to_delete = query_geniko.order_by(GenikoExodo.imerominia.desc()).first()
                
                if geniko_to_delete:
                    vasi.session.delete(geniko_to_delete)
                else:
                    # 2. Αν δε βρεθεί, ψάχνουμε στα Έξοδα των Κτημάτων
                    query_exodo = Exodo.query.filter_by(archived=False)
                    k_id_to_check = target_ktima_id if target_ktima_id and str(target_ktima_id).upper() != 'ALL' else (ktima.id if ktima else None)
                    if k_id_to_check:
                        try: query_exodo = query_exodo.filter_by(ktima_id=int(k_id_to_check))
                        except: pass
                    if amount is not None:
                        try: query_exodo = query_exodo.filter_by(poso=float(amount))
                        except: pass
                    if desc:
                        query_exodo = query_exodo.filter(Exodo.perigrafi.ilike(f"%{desc}%"))
                        
                    expense_to_delete = query_exodo.order_by(Exodo.imerominia.desc()).first()
                    if expense_to_delete:
                        vasi.session.delete(expense_to_delete)
                        vasi.session.add(Diagnosi(ktima_id=expense_to_delete.ktima_id, apotelesma=f"🗑️ AI Γραμματέας: Διαγράφηκε το έξοδο/έσοδο '{expense_to_delete.perigrafi}'.", imerominia=datetime.now()))
                
        if action == 'ADD_HARVEST':
            target_ktimata = []
            if str(target_ktima_id).upper() == 'ALL':
                target_ktimata = energa_ktimata
            else:
                if ktima: target_ktimata.append(ktima)
                
            for target_k in target_ktimata:
                kila_karpou = float(data.get('tonoi', 0) or 0)
                kila_ladi = float(data.get('kila_ladi', 0) or 0)
                esoda = float(data.get('esoda', 0) or 0)
                
                is_final = data.get('is_final', True)
                poikilia_sygkomidis = data.get('poikilia_sygkomidis')
                
                synoliko_kostos = sum([e.poso for e in target_k.exoda if not e.archived])
                kostos_eggrafis = synoliko_kostos if is_final else 0.0
                kila_ana_dentro = kila_karpou / target_k.arithmos_dentron if target_k.arithmos_dentron and target_k.arithmos_dentron > 0 else 0
                
                nea_sodeia = ArxeioSygkomidis(
                    ktima_id=target_k.id, tonoi=kila_karpou, kila_ladi=kila_ladi, esoda=esoda,
                    kila_ana_dentro=kila_ana_dentro, synoliko_kostos=kostos_eggrafis, imerominia=datetime.now()
                )
                vasi.session.add(nea_sodeia)
                
                desc_ergasias = "Συγκομιδή"
                if poikilia_sygkomidis: desc_ergasias += f" ({poikilia_sygkomidis})"
                desc_ergasias += f" - {kila_karpou} κιλά"
                vasi.session.add(Ergasia(ktima_id=target_k.id, eidos_ergasias=desc_ergasias, katastasi='Ολοκληρώθηκε', imerominia=datetime.now(), proelevsi='AI Γραμματέας'))
                
                if is_final:
                    for e in target_k.ergasies: e.archived = True
                    for ex in target_k.exoda: ex.archived = True
                    vasi.session.add(Diagnosi(ktima_id=target_k.id, apotelesma=f"🫒 AI Γραμματέας: Καταγράφηκε η τελική συγκομιδή ({kila_karpou} κιλά). Η σεζόν έκλεισε.", imerominia=datetime.now()))
                else:
                    msg = f"🫒 AI Γραμματέας: Καταγράφηκε μερική συγκομιδή ({kila_karpou} κιλά"
                    if poikilia_sygkomidis: msg += f" - {poikilia_sygkomidis}"
                    msg += ")."
                    vasi.session.add(Diagnosi(ktima_id=target_k.id, apotelesma=msg, imerominia=datetime.now()))
                target_k.ekkremis_erotisi_ai = None
                
        if action in ['ADD_INVENTORY', 'MULTI_ACTION']:
            inv_items = data.get('inventory_items', [])
            # Εφεδρικός έλεγχος αν το AI χρησιμοποίησε το παλιό, μονό σχήμα
            if not inv_items and data.get('inv_name') and action != 'MULTI_ACTION':
                inv_items = [{
                    'inv_name': data.get('inv_name'),
                    'inv_category': data.get('inv_category', 'Άλλο'),
                    'inv_amount': data.get('inv_amount'),
                    'inv_unit': data.get('inv_unit', 'Τεμάχια'),
                    'expense_amount': data.get('expense_amount'),
                    'expense_desc': data.get('expense_desc')
                }]
                
            for item in inv_items:
                inv_name = item.get('inv_name')
                inv_amount = item.get('inv_amount')
                if inv_name and inv_amount is not None:
                    try:
                        amount = float(inv_amount)
                        vasi.session.add(Apothiki(
                            xrhsths_id=current_user.id,
                            eidos=item.get('inv_category', 'Άλλο'),
                            onoma_proiontos=inv_name,
                            posotita=amount,
                            monada_metrisis=item.get('inv_unit', 'Τεμάχια')
                        ))
                        
                        poso = item.get('expense_amount')
                        k_id_to_charge = ktima.id if ktima else (energa_ktimata[0].id if energa_ktimata else None)
                        if poso is not None and k_id_to_charge:
                            vasi.session.add(Exodo(ktima_id=k_id_to_charge, perigrafi=item.get('expense_desc') or f"Αγορά: {inv_name}", poso=float(poso), imerominia=datetime.now()))
                            vasi.session.add(Diagnosi(ktima_id=k_id_to_charge, apotelesma=f"📦 AI Αποθήκη: Αγορά {amount} {item.get('inv_unit', '')} '{inv_name}' ({poso}€).", imerominia=datetime.now()))
                    except (ValueError, TypeError): pass
                
        if action == 'UPDATE_INVENTORY':
            inv_name = data.get('inv_name')
            inv_amount = data.get('inv_amount')
            if inv_name and inv_amount is not None:
                items = [i for i in current_user.apothiki_items if str(inv_name).lower() in i.onoma_proiontos.lower()]
                if items:
                    for item in items: item.posotita = float(inv_amount)
                    if ktima: vasi.session.add(Diagnosi(ktima_id=ktima.id, apotelesma=f"📦 AI Αποθήκη: Διορθώθηκε το απόθεμα του '{inv_name}' σε {inv_amount}.", imerominia=datetime.now()))
                    
        if action == 'DELETE_INVENTORY':
            inv_name = data.get('inv_name')
            if inv_name:
                items = [i for i in current_user.apothiki_items if str(inv_name).lower() in i.onoma_proiontos.lower()]
                for item in items:
                    vasi.session.delete(item)
                if ktima: vasi.session.add(Diagnosi(ktima_id=ktima.id, apotelesma=f"📦 AI Αποθήκη: Διαγράφηκε το '{inv_name}'.", imerominia=datetime.now()))
                
        if action == 'UPDATE_WATER':
            moisture = data.get('moisture_percentage')
            ph = data.get('nero_ph')
            ec = data.get('nero_agwgimotita')
            
            target_ktimata = []
            if str(target_ktima_id).upper() == 'ALL':
                target_ktimata = energa_ktimata
            else:
                if ktima: target_ktimata.append(ktima)
                
            for target_k in target_ktimata:
                updates = []
                if moisture is not None:
                    try:
                        pos = float(moisture)
                        vasi.session.add(KatagrafiUgrasias(ktima_id=target_k.id, pososto=pos))
                        updates.append(f"Υγρασία Εδάφους: {pos}%")
                    except (ValueError, TypeError): pass
                if ph is not None:
                    try: target_k.nero_ph = float(ph); updates.append(f"pH Νερού: {ph}")
                    except (ValueError, TypeError): pass
                if ec is not None:
                    try: target_k.nero_agwgimotita = float(ec); updates.append(f"Αγωγιμότητα: {ec}")
                    except (ValueError, TypeError): pass
                if updates:
                    vasi.session.add(Diagnosi(ktima_id=target_k.id, apotelesma=f"💧 AI Γραμματέας: Ενημέρωση ({', '.join(updates)}).", imerominia=datetime.now()))
                    target_k.teleftaia_enimerosi_ergasion = None
                    target_k.ai_sumvouli_date = None
                    target_k.ekkremis_erotisi_ai = None
                    
        if action == 'ADD_KTIMA':
            nk_data = data.get('new_ktima_data')
            if nk_data and nk_data.get('onoma_ktimatos'):
                try:
                    onoma = nk_data.get('onoma_ktimatos')
                    
                    neo_ktima = Ktima(
                        onoma_ktimatos=onoma,
                        geografiko_mikos=23.7275, # Προεπιλογή: Αθήνα
                        geografiko_platos=37.9838, # Προεπιλογή: Αθήνα
                        idioktitis=current_user
                    )
                    vasi.session.add(neo_ktima)
                    vasi.session.flush() # Λήψη του νέου ID
                    
                    poikilies_multi = nk_data.get('poikilies_multi')
                    if not poikilies_multi and isinstance(data.get('updates'), dict):
                        poikilies_multi = data['updates'].get('poikilies_multi')
                    if not poikilies_multi:
                        poikilies_multi = data.get('poikilies_multi')
                        
                    if poikilies_multi and isinstance(poikilies_multi, list) and len(poikilies_multi) > 0:
                        total_trees = 0
                        valid_varieties = []
                        for p in poikilies_multi:
                            p_onoma = p.get('onoma')
                            try: p_arithmos = int(p.get('arithmos') or 0)
                            except: p_arithmos = 0
                            if p_onoma and p_arithmos > 0:
                                from models import KtimaPoikilia
                                neo_p = KtimaPoikilia(ktima_id=neo_ktima.id, poikilia_onoma=p_onoma, arithmos_dentron=p_arithmos, ilikia_dentron=p.get('ilikia') or 'Άγνωστη')
                                vasi.session.add(neo_p)
                                neo_ktima.poikilies_details.append(neo_p)
                                total_trees += p_arithmos
                                valid_varieties.append(p_onoma)
                        neo_ktima.arithmos_dentron = total_trees
                        neo_ktima.poikilia = 'Ανάμεικτο' if len(set(valid_varieties)) > 1 else (valid_varieties[0] if valid_varieties else 'Δεν ορίστηκε')
                    else:
                        neo_ktima.arithmos_dentron = int(nk_data.get('arithmos_dentron') or 0)
                        neo_ktima.poikilia = nk_data.get('poikilia') or 'Δεν ορίστηκε'
                        neo_ktima.ilikia_dentron = nk_data.get('ilikia_dentron') or 'Άγνωστη'
                        if neo_ktima.arithmos_dentron > 0 and neo_ktima.poikilia != 'Δεν ορίστηκε':
                            from models import KtimaPoikilia
                            vasi.session.add(KtimaPoikilia(ktima_id=neo_ktima.id, poikilia_onoma=neo_ktima.poikilia, arithmos_dentron=neo_ktima.arithmos_dentron, ilikia_dentron=neo_ktima.ilikia_dentron))
                            
                    vasi.session.add(Diagnosi(ktima_id=neo_ktima.id, apotelesma="🤖 AI Γραμματέας: Το κτήμα δημιουργήθηκε αυτόματα.", imerominia=datetime.now()))
                    data['new_ktima_id'] = neo_ktima.id
                except Exception as e: print(f"Σφάλμα δημιουργίας κτήματος AI: {e}")
                
        if action == 'DELETE_KTIMA':
            import requests
            target_ktimata = []
            if str(target_ktima_id).upper() == 'ALL':
                target_ktimata = energa_ktimata
            else:
                if ktima: target_ktimata.append(ktima)
                
            for target_k in target_ktimata:
                if target_k.agromonitoring_poly_id and os.getenv('AGROMONITORING_API_KEY'):
                    try: requests.delete(f"http://api.agromonitoring.com/agro/1.0/polygons/{target_k.agromonitoring_poly_id}?appid={os.getenv('AGROMONITORING_API_KEY')}", timeout=5)
                    except: pass
                vasi.session.delete(target_k)
                
        if action == 'ARCHIVE_KTIMA':
            target_ktimata = []
            if str(target_ktima_id).upper() == 'ALL': target_ktimata = energa_ktimata
            else:
                if ktima: target_ktimata.append(ktima)
            for target_k in target_ktimata:
                target_k.is_active = False
                vasi.session.add(Diagnosi(ktima_id=target_k.id, apotelesma=f"🗂️ AI Γραμματέας: Το κτήμα αρχειοθετήθηκε.", imerominia=datetime.now()))
                
        if action == 'ADD_ANALYSIS':
            analysis_data = data.get('new_analysis_data') or {}
            target_ktimata = energa_ktimata if str(target_ktima_id).upper() == 'ALL' else ([ktima] if ktima else [])
            
            for target_k in target_ktimata:
                date_str = analysis_data.get('date')
                im = datetime.now()
                if date_str:
                    try: im = datetime.strptime(date_str, '%Y-%m-%d')
                    except: pass
                    
                def get_float(val):
                    try: return float(val) if val is not None else None
                    except: return None
                    
                n, p, k = get_float(analysis_data.get('azwto')), get_float(analysis_data.get('fwsforos')), get_float(analysis_data.get('kalio'))
                ph_val = get_float(analysis_data.get('ph'))
                org = get_float(analysis_data.get('organiki_ousia'))
                typos = analysis_data.get('typos_edafous')
                
                vasi.session.add(AnalysiEdafous(ktima_id=target_k.id, ph=ph_val, organiki_ousia=org, azwto=n, fwsforos=p, kalio=k, imerominia=im))
                if typos: target_k.typos_edafous = typos
                
                vasi.session.add(Diagnosi(ktima_id=target_k.id, apotelesma=f"📄 AI Γραμματέας: Καταγράφηκε Ανάλυση Εδάφους (N:{n}, P:{p}, K:{k}, pH:{ph_val})", imerominia=datetime.now()))
                target_k.ekkremis_erotisi_ai = None
                
        if (action == 'DIAGNOSIS' or any(img.filename != '' for img in image_files)) and action != 'MULTI_ACTION' and ktima:
            image_path_to_save = None
            if any(f.filename != '' for f in image_files):
                try:
                    first_image = next((f for f in image_files if f.filename != ''), None)
                    if first_image:
                        filename = secure_filename(f"{ktima.id}_{int(datetime.now().timestamp())}_{first_image.filename}")
                        absolute_path = os.path.join(UPLOADS_ABS_PATH, filename)
                        relative_path = os.path.join(UPLOADS_REL_PATH, filename).replace('\\', '/')
                        first_image.seek(0)
                        first_image.save(absolute_path)
                        image_path_to_save = relative_path
                except Exception as e:
                    print(f"Σφάλμα αποθήκευσης εικόνας γραμματέα: {e}")
                    image_path_to_save = None

            nea_diagnosi = Diagnosi(ktima_id=ktima.id, apotelesma=f"📸 AI Γραμματέας: {reply_text}", imerominia=datetime.now(), image_path=image_path_to_save)
            vasi.session.add(nea_diagnosi)
            ktima.teleftaia_enimerosi_ergasion = None
            ktima.ai_sumvouli_date = None
            
        # --- ΕΝΗΜΕΡΩΣΗ ΜΝΗΜΗΣ ΣΤΗ ΒΑΣΗ ΔΕΔΟΜΕΝΩΝ ---
        try:
            history = json.loads(history_str)
            if not isinstance(history, list): history = []
        except:
            history = []
            
        history.append({"role": "model", "content": reply_text})
        if len(history) > 40: # Κρατάμε τα τελευταία 40 μηνύματα για ελαφριά μνήμη
            history = history[-40:]
            
        current_user.secretary_history = json.dumps(history)
        
        vasi.session.commit()
        return jsonify({
            'success': True, 
            'reply': reply_text, 
            'action': action, 
            'new_ktima_data': data.get('new_ktima_data'), 
            'new_ktima_id': data.get('new_ktima_id'),
            'target_ktima_id': target_ktima_id
        })
    except Exception as e:
        error_msg = str(e)
        if '502' in error_msg or '503' in error_msg or 'Bad Gateway' in error_msg:
            return jsonify({'success': True, 'reply': '⚠️ Οι διακομιστές της Google (Gemini AI) αντιμετωπίζουν προσωρινό φόρτο. Παρακαλώ προσπαθήστε ξανά σε λίγο!', 'action': 'ADVICE'})
        elif '429' in error_msg or 'quota' in error_msg.lower() or '413' in error_msg or 'too large' in error_msg.lower():
            return jsonify({'success': True, 'reply': '⚠️ Οι φωτογραφίες είναι πολλές ή πολύ μεγάλες και δεν μπορώ να τις δω όλες μαζί. Δοκιμάστε να στείλετε λιγότερες.', 'action': 'ADVICE'})
        elif 'finish_reason' in error_msg.lower() or 'safety' in error_msg.lower():
            return jsonify({'success': True, 'reply': '⚠️ Δεν μπόρεσα να διακρίνω τη φωτογραφία γιατί είναι θολή ή μπλοκαρίστηκε. Δοκιμάστε με μια πιο καθαρή λήψη.', 'action': 'ADVICE'})
        elif 'expecting' in error_msg.lower() or 'json' in error_msg.lower():
            return jsonify({'success': True, 'reply': '⚠️ Συγγνώμη, μπερδεύτηκα λιγάκι με τη σύνταξη της απάντησής μου! Μπορείτε να μου το επαναλάβετε;', 'action': 'ADVICE'})
            
        return jsonify({'error': "Προέκυψε ένα σφάλμα: " + error_msg[:100] + "..."}), 500