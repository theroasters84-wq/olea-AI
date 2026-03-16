import os
import json
import PIL.Image
from datetime import datetime
from flask import Blueprint, request, jsonify
from flask_login import login_required, current_user
from core import vasi
from models import Ktima, Ergasia, Diagnosi, Exodo, Apothiki
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
        context_str += "\nΛίστα Κτημάτων του Αγρότη:\n"
        for k in current_user.ktimata:
            context_str += f"- ID: {k.id}, Όνομα: '{k.onoma_ktimatos}'\n"
        
        if ktima:
            from logic import xtise_plires_context
            context_str += f"\nΤο ΕΝΕΡΓΟ κτήμα στη συζήτηση είναι το '{ktima.onoma_ktimatos}' (ID: {ktima.id}). \nΔεδομένα Κτήματος:\n{xtise_plires_context(ktima)}\n"
        elif ktima_id == 'all':
            from logic import xtise_plires_context
            context_str += "\nΟ αγρότης ΔΕΝ έχει επιλέξει συγκεκριμένο κτήμα (Γενική Προβολή). Σου δίνω ΠΛΗΡΗ ΠΡΟΣΒΑΣΗ στα δεδομένα ΟΛΩΝ των κτημάτων του:\n"
            for k in current_user.ktimata:
                context_str += f"\n--- ΑΡΧΗ ΔΕΔΟΜΕΝΩΝ ΓΙΑ ΚΤΗΜΑ: {k.onoma_ktimatos} (ID: {k.id}) ---\n"
                context_str += xtise_plires_context(k)
                context_str += f"--- ΤΕΛΟΣ ΔΕΔΟΜΕΝΩΝ ΓΙΑ ΚΤΗΜΑ: {k.onoma_ktimatos} ---\n"
        else:
            context_str += "\nΠΡΟΣΟΧΗ: Ο αγρότης κάνει 'Γενική Ερώτηση (Χωρίς Κτήμα)'. Αν ρωτάει για εργασίες ή τον καιρό ενός κτήματος που δεν έχεις τα δεδομένα, ΠΕΣ ΤΟΥ ΕΥΓΕΝΙΚΑ να το επιλέξει από το αναδιπλούμενο μενού πάνω-πάνω, για να μπορέσεις να διαβάσεις τον φάκελό του.\n"

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
        2. Ανάλυση Φωτογραφίας/Εγγράφου & Έξυπνες Ερωτήσεις: Αν ο χρήστης στείλει φωτογραφία ή έγγραφο ανάλυσης, εκτός από τυχόν ασθένειες, παρατήρησε: α) Το έδαφος (Τι τύπος εδάφους φαίνεται ή αναγράφεται; π.χ. Αργιλώδες, Αμμώδες, Πετρώδες. Υπάρχουν λάστιχα ποτίσματος;), β) Τα χόρτα (είναι κομμένα;), γ) Την πυκνότητα φύτευσης (είναι υπέρπυκνη;). Αν δεις κάτι που διαφέρει από το τρέχον προφίλ του κτήματος, ΜΗΝ ΤΟ ΑΛΛΑΞΕΙΣ ΑΜΕΣΩΣ. Ρώτα πρώτα τον χρήστη στο "reply" (π.χ. "Βλέπω λάστιχα ποτίσματος. Θέλετε να ενημερώσω το κτήμα σε Αρδευόμενο;" ή "Ο τύπος εδάφους φαίνεται αργιλώδης. Να τον καταχωρήσω;"). Θέσε action: "DIAGNOSIS".
        3. Επιβεβαίωση Αλλαγής Προφίλ: Αν ο χρήστης στο κείμενό του ΣΟΥ ΕΠΙΒΕΒΑΙΩΣΕΙ να κάνεις μια αλλαγή στα στοιχεία του κτήματος (π.χ. "Ναι, άλλαξέ το", "Είναι αρδευόμενο", "Άλλαξέ το σε βιολογική", "Κάνε τα στρέμματα 15", "Έχω 150 δέντρα", "Το έδαφος είναι αμμώδες"), βάλε action: "UPDATE_KTIMA" και συμπλήρωσε τις νέες τιμές στο object "updates".
        4. Προσθήκη Εργασίας: Αν ο χρήστης λέει ότι έκανε μια εργασία, βάλε action: "ADD_TASK". ΣΗΜΑΝΤΙΚΟ: Αν ο χρήστης αναφέρει εμπορικό όνομα σκευάσματος, βρες τη δραστική του ουσία και γράψε την σε παρένθεση στο "task_materials". Αν αναφέρει ΚΑΙ το κόστος (π.χ. "μου κόστισε 50 ευρώ"), συμπλήρωσε τα "expense_amount" και "expense_desc". ΑΝ αναφέρει ποσότητα υλικού που χρησιμοποίησε (π.χ. "έριξα 2 λίτρα") και το υλικό υπάρχει στην "ΑΠΟΘΗΚΗ ΥΛΙΚΩΝ", συμπλήρωσε το "used_material_name" με το ΑΚΡΙΒΕΣ ΟΝΟΜΑ από την αποθήκη και το "used_material_amount" με τον αριθμό.
        5. Διαγραφή Εργασιών: Αν ο χρήστης ζητήσει να διαγράψεις εργασίες (π.χ. "σβήσε όλες τις εργασίες", "διέγραψε το κλάδεμα"), βάλε action: "DELETE_TASKS". Στο "task_name" γράψε "ΟΛΕΣ" για ολική διαγραφή, ή μια λέξη-κλειδί για συγκεκριμένη (π.χ. "Κλάδεμα").
        6. Πληροφορίες Ιστορικού & Καιρού (ΣΗΜΑΝΤΙΚΟ): ΕΧΕΙΣ ΗΔΗ ΠΡΟΣΒΑΣΗ στο ιστορικό εργασιών, τον καιρό, κλπ (αν υπάρχουν στα 'Δεδομένα Κτήματος' παραπάνω). Αν ο χρήστης σε ρωτήσει "τι εργασίες έχω κάνει;", ΑΠΑΝΤΗΣΕ ΑΜΕΣΑ με τη λίστα. ΑΠΑΓΟΡΕΥΕΤΑΙ να πεις "περιμένετε να ψάξω" ή "θα σας πω σε λίγο". Αν βλέπεις δεδομένα πολλών κτημάτων, δώσε συγκεντρωτική αναφορά. Γράψε τα δεδομένα κατευθείαν στο "reply" και βάλε action: "ADVICE".
        7. Οικονομικά & Έξοδα: Αν ο χρήστης ρωτήσει για τα έξοδά του ή το συνολικό κόστος, διάβασε τα από την ενότητα 'ΟΙΚΟΝΟΜΙΚΑ / ΕΞΟΔΑ' και απάντησε στο "reply". Αν αναφέρει νέο έξοδο (π.χ. "πλήρωσα 100 ευρώ για λιπάσματα"), βάλε action: "ADD_EXPENSE", το ποσό στο "expense_amount" και την περιγραφή στο "expense_desc".
        8. Απλή συμβουλή: Αν ο χρήστης ρωτάει μια συμβουλή, δώσε την απάντηση και βάλε action: "ADVICE".
        
        Επίστρεψε ΑΥΣΤΗΡΑ ένα JSON με την εξής μορφή (χωρίς markdown, καθαρό JSON):
        {
            "reply": "Η απάντησή σου στον αγρότη. (Σύντομη, φιλική, άμεση)",
            "action": "ADD_TASK" | "DIAGNOSIS" | "ADVICE" | "UPDATE_KTIMA" | "DELETE_TASKS" | "ADD_EXPENSE",
            "target_ktima_id": Αριθμός ID του κτήματος (του επιλεγμένου ή αυτού που αναφέρει ο χρήστης. Αν δεν μπορείς να το βρεις, βάλε null),
            "task_name": "Ονομασία Εργασίας (π.χ. 'Ψεκασμός με Χαλκό') ή 'ΟΛΕΣ' - ΚΕΝΟ αν δεν αφορά εργασία",
            "task_materials": "Όνομα φαρμάκου/λιπάσματος - ΚΕΝΟ αν δεν αναφέρεται",
            "expense_amount": Ποσό σε ευρώ (αριθμός, π.χ. 100.5) - null αν δεν αναφέρεται κόστος,
            "expense_desc": "Περιγραφή του εξόδου" - ΚΕΝΟ αν δεν αναφέρεται κόστος,
            "used_material_name": "Ακριβές όνομα υλικού από αποθήκη" - ΚΕΝΟ αν δεν αναφέρεται,
            "used_material_amount": Αριθμός (π.χ. 2.5) - null αν δεν αναφέρεται ποσότητα,
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
        
        if action == 'ADD_TASK' and ktima:
            nea_ergasia = Ergasia(ktima_id=ktima.id, eidos_ergasias=data.get('task_name', 'AI Καταχώρηση'), farmaka_lipasmata=data.get('task_materials', ''), katastasi='Ολοκληρώθηκε', imerominia=datetime.now(), proelevsi='AI Γραμματέας')
            vasi.session.add(nea_ergasia)
            
            # Ανέφερε και κόστος, οπότε καταχωρούμε και την αντίστοιχη δαπάνη
            poso = data.get('expense_amount')
            if poso is not None:
                try:
                    neo_exodo = Exodo(ktima_id=ktima.id, perigrafi=data.get('expense_desc') or f"Κόστος: {data.get('task_name', 'Εργασία')}", poso=float(poso), imerominia=datetime.now())
                    vasi.session.add(neo_exodo)
                except (ValueError, TypeError): pass
                
            # Ανέφερε ποσότητα υλικού από την αποθήκη
            used_material_name = data.get('used_material_name')
            used_material_amount = data.get('used_material_amount')
            if used_material_name and used_material_amount is not None:
                try:
                    amount = float(used_material_amount)
                    item = Apothiki.query.filter_by(xrhsths_id=current_user.id, onoma_proiontos=used_material_name).first()
                    if item and amount > 0:
                        item.posotita = max(0, item.posotita - amount)
                        nea_diagnosi_apothiki = Diagnosi(ktima_id=ktima.id, apotelesma=f"📦 AI Αποθήκη: Αφαιρέθηκαν {amount} {item.monada_metrisis} από '{item.onoma_proiontos}'.", imerominia=datetime.now())
                        vasi.session.add(nea_diagnosi_apothiki)
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
        elif action == 'DELETE_TASKS' and ktima:
            task_name = data.get('task_name', '')
            if task_name == 'ΟΛΕΣ':
                Ergasia.query.filter_by(ktima_id=ktima.id).delete()
                nea_diagnosi = Diagnosi(ktima_id=ktima.id, apotelesma="🗑️ AI Γραμματέας: Έγινε διαγραφή όλων των εργασιών.", imerominia=datetime.now())
                vasi.session.add(nea_diagnosi)
            elif task_name:
                Ergasia.query.filter_by(ktima_id=ktima.id).filter(Ergasia.eidos_ergasias.ilike(f"%{task_name}%")).delete(synchronize_session=False)
                nea_diagnosi = Diagnosi(ktima_id=ktima.id, apotelesma=f"🗑️ AI Γραμματέας: Έγινε διαγραφή εργασιών: {task_name}.", imerominia=datetime.now())
                vasi.session.add(nea_diagnosi)
        elif action == 'ADD_EXPENSE' and ktima:
            poso = data.get('expense_amount')
            perigrafi = data.get('expense_desc', 'Νέο Έξοδο (Από AI)')
            try:
                poso = float(poso)
                neo_exodo = Exodo(ktima_id=ktima.id, perigrafi=perigrafi, poso=poso, imerominia=datetime.now())
                vasi.session.add(neo_exodo)
                nea_diagnosi = Diagnosi(ktima_id=ktima.id, apotelesma=f"💶 AI Γραμματέας: Προστέθηκε έξοδο '{perigrafi}' ({poso}€).", imerominia=datetime.now())
                vasi.session.add(nea_diagnosi)
            except (ValueError, TypeError): pass
        elif (action == 'DIAGNOSIS' or any(img.filename != '' for img in image_files)) and ktima:
            nea_diagnosi = Diagnosi(ktima_id=ktima.id, apotelesma=f"📸 AI Γραμματέας: {reply_text}", imerominia=datetime.now())
            vasi.session.add(nea_diagnosi)
            
        vasi.session.commit()
        return jsonify({'success': True, 'reply': reply_text, 'action': action})
    except Exception as e:
        return jsonify({'error': str(e)}), 500