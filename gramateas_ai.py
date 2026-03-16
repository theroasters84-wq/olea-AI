import os
import json
import PIL.Image
from datetime import datetime
from flask import Blueprint, request, jsonify
from flask_login import login_required, current_user
from core import vasi
from models import Ktima, Ergasia, Diagnosi, Exodo, Apothiki, ArxeioSygkomidis, KatagrafiUgrasias
from google import genai
from google.genai import types

gramateas_bp = Blueprint('gramateas', __name__)

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
        
        if ktima:
            from logic import xtise_plires_context
            context_str += f"\nΤο ΕΝΕΡΓΟ κτήμα στη συζήτηση είναι το '{ktima.onoma_ktimatos}' (ID: {ktima.id}). \nΔεδομένα Κτήματος:\n{xtise_plires_context(ktima)}\n"
        elif ktima_id == 'all':
            from logic import xtise_plires_context
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

        prompt = context_str + f"\nΤΩΡΙΝΟ ΜΗΝΥΜΑ ΧΡΗΣΤΗ: '{text}'.\n"
        prompt += """
        ΟΔΗΓΙΕΣ ΓΙΑ ΤΟ JSON ΚΑΙ ΤΗ ΣΥΜΠΕΡΙΦΟΡΑ ΣΟΥ: 
        0. ΟΡΑΣΗ/ΑΡΧΕΙΑ (ΚΡΙΣΙΜΟ): Έχεις πλήρη ικανότητα Vision! Μπορείς να διαβάσεις και να αναλύσεις κανονικά τις φωτογραφίες και τα PDF που σου επισυνάπτονται. ΑΠΑΓΟΡΕΥΕΤΑΙ ΑΥΣΤΗΡΑ να πεις ότι δεν μπορείς να δεις ή να διαβάσεις αρχεία. Αν ο χρήστης έστειλε αρχείο, μελέτησέ το και δώσε του την απάντηση.
        1. Έλεγχος Αποθήκης: Πριν προτείνεις οποιοδήποτε υλικό, φάρμακο ή εργασία, ΕΛΕΓΞΕ ΑΥΣΤΗΡΑ την "ΑΠΟΘΗΚΗ ΥΛΙΚΩΝ" στο προφίλ του κτήματος. Αν το υλικό υπάρχει ήδη διαθέσιμο, πρότεινε να χρησιμοποιήσει αυτό για οικονομία.
        2. Ανάλυση Φωτογραφίας/Εγγράφου & Έξυπνες Ερωτήσεις: Αν ο χρήστης στείλει φωτογραφία (π.χ. ζιζάνιο, έντομο, άρρωστο φύλλο), αναγνώρισέ το αμέσως, πες του τι είναι και πρότεινε λύση. Εκτός από αυτό, παρατήρησε περιφερειακά: α) Το έδαφος (Τι τύπος εδάφους φαίνεται ή αναγράφεται; π.χ. Αργιλώδες, Αμμώδες, Πετρώδες. Υπάρχουν λάστιχα ποτίσματος;), β) Τα χόρτα (είναι κομμένα;), γ) Την πυκνότητα φύτευσης (είναι υπέρπυκνη;). Αν δεις κάτι που διαφέρει από το τρέχον προφίλ του κτήματος, ΜΗΝ ΤΟ ΑΛΛΑΞΕΙΣ ΑΜΕΣΩΣ. Ρώτα πρώτα τον χρήστη στο "reply" (π.χ. "Βλέπω λάστιχα ποτίσματος. Θέλετε να ενημερώσω το κτήμα σε Αρδευόμενο;" ή "Ο τύπος εδάφους φαίνεται αργιλώδης. Να τον καταχωρήσω;"). Θέσε action: "DIAGNOSIS".
        3. Επιβεβαίωση Αλλαγής Προφίλ: Αν ο χρήστης στο κείμενό του ΣΟΥ ΕΠΙΒΕΒΑΙΩΣΕΙ να κάνεις μια αλλαγή στα στοιχεία του κτήματος (π.χ. "Ναι, άλλαξέ το", "Είναι αρδευόμενο", "Άλλαξέ το σε βιολογική", "Κάνε τα στρέμματα 15", "Έχω 150 δέντρα", "Το έδαφος είναι αμμώδες"), βάλε action: "UPDATE_KTIMA" και συμπλήρωσε τις νέες τιμές στο object "updates".
        4. Προσθήκη Εργασιών (Πολλαπλές & Ημερομηνίες): Αν ο χρήστης λέει ότι έκανε μία ή ΠΟΛΛΑΠΛΕΣ εργασίες (π.χ. "ράντισα και μετά από ένα μήνα κλάδεψα"), βάλε action: "ADD_TASKS".
           - Υπολόγισε την ΗΜΕΡΟΜΗΝΙΑ: Αν λέει "τον Νοέμβριο μετά τη συγκομιδή", υπολόγισε και βάλε μια σχετική ημερομηνία στο "date" (π.χ. "2025-11-15"). Αν είναι ασαφές, ρώτα τον στο "reply" (action: "DIAGNOSIS").
           - Για κάθε εργασία, φτιάξε ένα αντικείμενο στη λίστα "tasks".
           - Αν ζητάει καταχώρηση σε ΟΛΑ τα κτήματα, βάλε "target_ktima_id": "ALL" στο task.
           - ΣΗΜΑΝΤΙΚΟ: Αν αναφέρει εμπορικό όνομα, βάλε τη δραστική στο "task_materials".
        5. Διαγραφή Εργασιών: Αν ο χρήστης ζητήσει να διαγράψεις εργασίες, ΡΩΤΑ ΤΟΝ ΠΡΩΤΑ στο "reply" αν είναι σίγουρος (π.χ. "Είστε σίγουροι;") και βάλε action: "DIAGNOSIS" (ώστε να μην διαγραφούν ακόμα). ΜΟΝΟ ΑΝ ο χρήστης επιβεβαιώσει ρητά στην επόμενη απάντησή του (π.χ. "ναι", "διέγραψέ τα"), βάλε action: "DELETE_TASKS". Στο "task_name" γράψε "ΟΛΕΣ" για ολική διαγραφή, ή μια λέξη-κλειδί για συγκεκριμένη. Αν ζητήσει διαγραφή σε ΟΛΑ τα κτήματα, βάλε target_ktima_id: "ALL".
        6. Πληροφορίες Ιστορικού, Εκκρεμοτήτων & Καιρού (ΣΗΜΑΝΤΙΚΟ): ΕΧΕΙΣ ΗΔΗ ΠΡΟΣΒΑΣΗ στο ιστορικό εργασιών, στις "Εκκρεμείς Εργασίες", τον καιρό κλπ (αν υπάρχουν στα 'Δεδομένα Κτήματος' παραπάνω). Αν ο χρήστης σε ρωτήσει "τι εργασίες έχω κάνει;" ή "τι δουλειές πρέπει να γίνουν;", ΑΠΑΝΤΗΣΕ ΑΜΕΣΑ διαβάζοντας αντίστοιχα το ιστορικό ή τις εκκρεμείς εργασίες. ΑΠΑΓΟΡΕΥΕΤΑΙ να πεις "περιμένετε να ψάξω" ή "θα σας πω σε λίγο". Αν βλέπεις δεδομένα πολλών κτημάτων, δώσε συγκεντρωτική αναφορά. Γράψε τα δεδομένα κατευθείαν στο "reply" και βάλε action: "ADVICE".
        7. Οικονομικά (Έξοδα & Έσοδα/Επιδοτήσεις): Αν ο χρήστης ρωτήσει για έξοδα, διάβασέ τα από την ενότητα 'ΟΙΚΟΝΟΜΙΚΑ / ΕΞΟΔΑ'. Αν αναφέρει νέο έξοδο, βάλε action: "ADD_EXPENSE" και συμπλήρωσε "expense_amount" και "expense_desc". Αν αναφέρει ΕΣΟΔΟ (π.χ. "πήρα 500 ευρώ επιδότηση", "αποζημίωση ΕΛΓΑ"), βάλε action: "ADD_INCOME", συμπλήρωσε "income_amount" (θετικός αριθμός) και "income_desc".
        8. Απλή συμβουλή: Αν ο χρήστης ρωτάει μια συμβουλή, δώσε την απάντηση και βάλε action: "ADVICE".
        9. Καταγραφή Συγκομιδής: Αν ο χρήστης αναφέρει δεδομένα συγκομιδής (π.χ. "μάζεψα 5000 κιλά ελιές", "έβγαλα 1 τόνο λάδι", "είχα 2000 ευρώ έσοδα"), βάλε action: "ADD_HARVEST". Στο JSON συμπλήρωσε "tonoi" (κιλά καρπού, 1 τόνος = 1000), "kila_ladi" (κιλά λαδιού) και "esoda" (ευρώ). Αυτόματα θα αρχειοθετηθεί η σεζόν.
        10. Ασαφή/Ελλιπή Δεδομένα: Αν ο χρήστης ρωτήσει κάτι που ΔΕΝ καλύπτεται από τα δεδομένα που σου έχω δώσει (π.χ. ρωτάει για μια εργασία αλλά το ιστορικό είναι κενό, ή κάνει ασαφή ερώτηση/εντολή), ΑΠΑΓΟΡΕΥΕΤΑΙ να επινοήσεις στοιχεία. Ρώτησέ τον άμεσα να σου δώσει τα δεδομένα που λείπουν και βάλε action: "DIAGNOSIS".
        11. Προσθήκη στην Αποθήκη: Αν ο χρήστης λέει ότι αγόρασε κάποιο υλικό/φάρμακο/λίπασμα (π.χ. "αγόρασα 10 λίτρα χαλκό με 50 ευρώ"), βάλε action: "ADD_INVENTORY". Συμπλήρωσε τα πεδία "inv_name", "inv_category" ("Φάρμακο", "Λίπασμα" ή "Εξοπλισμός"), "inv_amount" (αριθμός) και "inv_unit" ("Λίτρα", "Κιλά" ή "Τεμάχια"). Αν αναφέρει κόστος, βάλε και το "expense_amount".
        12. Διαχείριση Υγρασίας & Νερού: Αν ο χρήστης αναφέρει μέτρηση υγρασίας (π.χ. "η υγρασία του εδάφους είναι 20%") ή ανάλυση νερού ("pH 7.2", "αγωγιμότητα 1.5"), βάλε action: "UPDATE_WATER" και συμπλήρωσε τα "moisture_percentage", "nero_ph", "nero_agwgimotita". Αν ρωτάει πόσο να ποτίσει, διάβασε τις 'Ανάγκες Άρδευσης' από τα δεδομένα και απάντησέ του.
        
        Επίστρεψε ΑΥΣΤΗΡΑ ένα JSON με την εξής μορφή (χωρίς markdown, καθαρό JSON):
        {
            "reply": "Η απάντησή σου στον αγρότη. (Σύντομη, φιλική, άμεση)",
            "action": "ADD_TASKS" | "DIAGNOSIS" | "ADVICE" | "UPDATE_KTIMA" | "DELETE_TASKS" | "ADD_EXPENSE" | "ADD_INCOME" | "ADD_HARVEST" | "ADD_INVENTORY" | "UPDATE_WATER",
            "tasks": [
                {
                    "target_ktima_id": "Αριθμός ID κτήματος Ή 'ALL'",
                    "task_name": "Ονομασία Εργασίας...",
                    "task_materials": "Φάρμακα/Λιπάσματα - ΚΕΝΟ αν δεν αναφέρεται",
                    "date": "YYYY-MM-DD",
                    "expense_amount": 100.5,
                    "expense_desc": "Περιγραφή κόστους",
                    "used_material_name": "Όνομα από αποθήκη",
                    "used_material_amount": 2.5
                }
            ],
            "target_ktima_id": "Αριθμός ID Ή 'ALL' (γενική χρήση)",
            "task_name": "ΟΛΕΣ ή λέξη (Μόνο για το DELETE_TASKS)",
            "expense_amount": 50,
            "expense_desc": "Περιγραφή κόστους",
            "income_amount": 500,
            "income_desc": "Περιγραφή εσόδου",
            "tonoi": 5000,
            "kila_ladi": 1000,
            "esoda": 2000,
            "inv_name": "Όνομα προϊόντος",
            "inv_category": "Φάρμακο",
            "inv_amount": 10,
            "inv_unit": "Λίτρα",
            "moisture_percentage": 25.5,
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
                "typos_edafous": "Αμμώδες" ή "Αργιλώδες" ή "Πηλώδες" ή "Πετρώδες" ή null
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
                    contents.append(img)
        
        response = client.models.generate_content(model='gemini-2.5-flash', contents=contents)
        
        # Δικλείδα Ασφαλείας: Αν το AI επιστρέψει κενό (π.χ. λόγω safety filters)
        if not response or not getattr(response, 'text', None):
            return jsonify({'success': True, 'reply': 'Υπήρξε ένα στιγμιαίο πρόβλημα επικοινωνίας ή μπλοκάρισμα από τα φίλτρα ασφαλείας του AI. Μπορείτε να το διατυπώσετε διαφορετικά;', 'action': 'ADVICE'})
            
        json_text = response.text.strip().replace('```json', '').replace('```', '').strip()
        data = json.loads(json_text)
        
        action = data.get('action', 'ADVICE')
        reply_text = data.get('reply', 'Δεν κατάλαβα ακριβώς τι ζητάς.')
        target_ktima_id = data.get('target_ktima_id')
        
        # Αν το AI βρήκε άλλο κτήμα βάσει ονόματος (ή πήρε το επιλεγμένο), το χρησιμοποιούμε
        if target_ktima_id:
            try:
                ktima_id_int = int(target_ktima_id)
                target_ktima = vasi.session.get(Ktima, ktima_id_int)
                if target_ktima and target_ktima.idioktitis == current_user:
                    ktima = target_ktima
            except (ValueError, TypeError):
                pass
        
        if action in ['ADD_TASK', 'ADD_TASKS']:
            tasks_list = data.get('tasks', [])
            # Αν το AI γύρισε παλιά δομή (1 εργασία)
            if not tasks_list and data.get('task_name'):
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
                        
                    nea_ergasia = Ergasia(ktima_id=target_k.id, eidos_ergasias=task_data.get('task_name', 'AI Καταχώρηση'), farmaka_lipasmata=task_data.get('task_materials', ''), katastasi='Ολοκληρώθηκε', imerominia=im, proelevsi='AI Γραμματέας')
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
                
        elif action == 'UPDATE_KTIMA' and ktima:
            updates = data.get('updates', {})
            updated_fields = []
            if updates.get('ardefsi'):
                ktima.ardefsi = updates['ardefsi']
                updated_fields.append('Άρδευση')
            if updates.get('diacheirisi_edafous'):
                ktima.diacheirisi_edafous = updates['diacheirisi_edafous']
                updated_fields.append('Διαχείριση Εδάφους')
            if updates.get('puknotita_dentron'):
                ktima.puknotita_dentron = updates['puknotita_dentron']
                updated_fields.append('Πυκνότητα Δέντρων')
            if updates.get('kalliergeia_typos'):
                ktima.kalliergeia_typos = updates['kalliergeia_typos']
                updated_fields.append('Τύπος Καλλιέργειας')
            if updates.get('ilikia_dentron'):
                ktima.ilikia_dentron = updates['ilikia_dentron']
                updated_fields.append('Ηλικία Δέντρων')
            if updates.get('stremmata') is not None:
                try:
                    ktima.stremmata = float(updates['stremmata'])
                    updated_fields.append('Στρέμματα')
                except (ValueError, TypeError):
                    pass
            if updates.get('arithmos_dentron') is not None:
                try:
                    ktima.arithmos_dentron = int(updates['arithmos_dentron'])
                    updated_fields.append('Αριθμός Δέντρων')
                except (ValueError, TypeError):
                    pass
            if updates.get('typos_edafous'):
                ktima.typos_edafous = updates['typos_edafous']
                updated_fields.append('Τύπος Εδάφους')
            if updated_fields:
                nea_diagnosi = Diagnosi(ktima_id=ktima.id, apotelesma=f"⚙️ Ενημέρωση Προφίλ από AI: {', '.join(updated_fields)}", imerominia=datetime.now())
                vasi.session.add(nea_diagnosi)
        elif action == 'DELETE_TASKS':
            task_name = data.get('task_name', '')
            target_ktimata = []
            
            if str(target_ktima_id).upper() == 'ALL':
                target_ktimata = energa_ktimata
            else:
                if ktima: target_ktimata.append(ktima)
                
            for target_k in target_ktimata:
                if task_name == 'ΟΛΕΣ':
                    Ergasia.query.filter_by(ktima_id=target_k.id).delete()
                    vasi.session.add(Diagnosi(ktima_id=target_k.id, apotelesma="🗑️ AI Γραμματέας: Έγινε διαγραφή όλων των εργασιών.", imerominia=datetime.now()))
                elif task_name:
                    Ergasia.query.filter_by(ktima_id=target_k.id).filter(Ergasia.eidos_ergasias.ilike(f"%{task_name}%")).delete(synchronize_session=False)
                    vasi.session.add(Diagnosi(ktima_id=target_k.id, apotelesma=f"🗑️ AI Γραμματέας: Έγινε διαγραφή εργασιών: {task_name}.", imerominia=datetime.now()))
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
        elif action == 'ADD_HARVEST':
            target_ktimata = []
            if str(target_ktima_id).upper() == 'ALL':
                target_ktimata = energa_ktimata
            else:
                if ktima: target_ktimata.append(ktima)
                
            for target_k in target_ktimata:
                kila_karpou = float(data.get('tonoi', 0) or 0)
                kila_ladi = float(data.get('kila_ladi', 0) or 0)
                esoda = float(data.get('esoda', 0) or 0)
                
                synoliko_kostos = sum([e.poso for e in target_k.exoda if not e.archived])
                kila_ana_dentro = kila_karpou / target_k.arithmos_dentron if target_k.arithmos_dentron and target_k.arithmos_dentron > 0 else 0
                
                nea_sodeia = ArxeioSygkomidis(
                    ktima_id=target_k.id, tonoi=kila_karpou, kila_ladi=kila_ladi, esoda=esoda,
                    kila_ana_dentro=kila_ana_dentro, synoliko_kostos=synoliko_kostos, imerominia=datetime.now()
                )
                vasi.session.add(nea_sodeia)
                
                for e in target_k.ergasies: e.archived = True
                for ex in target_k.exoda: ex.archived = True
                
                vasi.session.add(Diagnosi(ktima_id=target_k.id, apotelesma=f"🫒 AI Γραμματέας: Καταγράφηκε η συγκομιδή ({kila_karpou} κιλά ελιές). Η σεζόν έκλεισε.", imerominia=datetime.now()))
        elif action == 'ADD_INVENTORY':
            inv_name = data.get('inv_name')
            inv_amount = data.get('inv_amount')
            if inv_name and inv_amount is not None:
                try:
                    amount = float(inv_amount)
                    vasi.session.add(Apothiki(
                        xrhsths_id=current_user.id,
                        eidos=data.get('inv_category', 'Άλλο'),
                        onoma_proiontos=inv_name,
                        posotita=amount,
                        monada_metrisis=data.get('inv_unit', 'Τεμάχια')
                    ))
                    
                    poso = data.get('expense_amount')
                    k_id_to_charge = ktima.id if ktima else (energa_ktimata[0].id if energa_ktimata else None)
                    if poso is not None and k_id_to_charge:
                        vasi.session.add(Exodo(ktima_id=k_id_to_charge, perigrafi=data.get('expense_desc') or f"Αγορά: {inv_name}", poso=float(poso), imerominia=datetime.now()))
                        vasi.session.add(Diagnosi(ktima_id=k_id_to_charge, apotelesma=f"📦 AI Αποθήκη: Αγορά {amount} {data.get('inv_unit', '')} '{inv_name}' ({poso}€).", imerominia=datetime.now()))
                except (ValueError, TypeError): pass
        elif action == 'UPDATE_WATER':
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
        elif (action == 'DIAGNOSIS' or any(img.filename != '' for img in image_files)) and ktima:
            nea_diagnosi = Diagnosi(ktima_id=ktima.id, apotelesma=f"📸 AI Γραμματέας: {reply_text}", imerominia=datetime.now())
            vasi.session.add(nea_diagnosi)
            
        vasi.session.commit()
        return jsonify({'success': True, 'reply': reply_text, 'action': action})
    except Exception as e:
        return jsonify({'error': str(e)}), 500