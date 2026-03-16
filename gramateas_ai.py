import os
import json
import PIL.Image
from datetime import datetime
from flask import Blueprint, request, jsonify
from flask_login import login_required, current_user
from core import vasi
from models import Ktima, Ergasia, Diagnosi
from google import genai

gramateas_bp = Blueprint('gramateas', __name__)

@gramateas_bp.route('/api/ai_secretary', methods=['POST'])
@login_required
def ai_secretary():
    ktima_id = request.form.get('ktima_id')
    text = request.form.get('text', '')
    history_str = request.form.get('history', '[]')
    image_file = request.files.get('image')

    ktima = vasi.session.get(Ktima, ktima_id) if ktima_id else None
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
        else:
            context_str += "\nΠΡΟΣΟΧΗ: Ο αγρότης ΔΕΝ έχει επιλέξει συγκεκριμένο κτήμα στο μενού. Γι' αυτό ΔΕΝ βλέπεις το ιστορικό εργασιών! Αν ρωτάει για εργασίες ή τον καιρό ενός κτήματος, ΠΕΣ ΤΟΥ ΕΥΓΕΝΙΚΑ να το επιλέξει από το αναδιπλούμενο μενού πάνω-πάνω, για να μπορέσεις να διαβάσεις τον φάκελό του.\n"

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
        1. Έλεγχος Αποθήκης: Πριν προτείνεις οποιοδήποτε υλικό, φάρμακο ή εργασία, ΕΛΕΓΞΕ ΑΥΣΤΗΡΑ την "ΑΠΟΘΗΚΗ ΥΛΙΚΩΝ" στο προφίλ του κτήματος. Αν το υλικό υπάρχει ήδη διαθέσιμο, πρότεινε να χρησιμοποιήσει αυτό για οικονομία.
        2. Ανάλυση Φωτογραφίας & Έξυπνες Ερωτήσεις: Αν ο χρήστης στείλει φωτογραφία, εκτός από τυχόν ασθένειες, παρατήρησε: α) Το έδαφος (υπάρχουν λάστιχα ποτίσματος;), β) Τα χόρτα (είναι κομμένα;), γ) Την πυκνότητα φύτευσης (είναι υπέρπυκνη;). Αν δεις κάτι που διαφέρει από το τρέχον προφίλ του κτήματος, ΜΗΝ ΤΟ ΑΛΛΑΞΕΙΣ ΑΜΕΣΩΣ. Ρώτα πρώτα τον χρήστη στο "reply" (π.χ. "Βλέπω λάστιχα ποτίσματος. Θέλετε να ενημερώσω το κτήμα σε Αρδευόμενο;"). Θέσε action: "DIAGNOSIS".
        3. Επιβεβαίωση Αλλαγής Προφίλ: Αν ο χρήστης στο κείμενό του ΣΟΥ ΕΠΙΒΕΒΑΙΩΣΕΙ να κάνεις μια αλλαγή στα στοιχεία του κτήματος (π.χ. "Ναι, άλλαξέ το", "Είναι αρδευόμενο", "Τα χόρτα είναι κομμένα"), βάλε action: "UPDATE_KTIMA" και συμπλήρωσε τις νέες τιμές στο object "updates".
        4. Προσθήκη Εργασίας: Αν ο χρήστης λέει ότι έκανε μια εργασία (π.χ. "ράντισα", "έριξα λίπασμα", "φρεζάρισα"), βάλε action: "ADD_TASK" και συμπλήρωσε το "task_name" και "task_materials".
        5. Διαγραφή Εργασιών: Αν ο χρήστης ζητήσει να διαγράψεις εργασίες (π.χ. "σβήσε όλες τις εργασίες", "διέγραψε το κλάδεμα"), βάλε action: "DELETE_TASKS". Στο "task_name" γράψε "ΟΛΕΣ" για ολική διαγραφή, ή μια λέξη-κλειδί για συγκεκριμένη (π.χ. "Κλάδεμα").
        6. Πληροφορίες Ιστορικού & Καιρού (ΣΗΜΑΝΤΙΚΟ): ΕΧΕΙΣ ΗΔΗ ΠΛΗΡΗ ΠΡΟΣΒΑΣΗ στο ιστορικό εργασιών, τον καιρό, την πρόγνωση κλπ (είναι όλα γραμμένα στα 'Δεδομένα Κτήματος' παραπάνω). Αν ο χρήστης σε ρωτήσει "τι εργασίες έχω κάνει;", ΑΠΑΝΤΗΣΕ ΑΜΕΣΑ με τη λίστα των εργασιών μέσα στο πεδίο "reply". ΑΠΑΓΟΡΕΥΕΤΑΙ να πεις "περιμένετε να ψάξω" ή "θα σας πω σε λίγο". Γράψε τα δεδομένα κατευθείαν στο "reply" και βάλε action: "ADVICE".
        7. Απλή συμβουλή: Αν ο χρήστης ρωτάει μια συμβουλή, δώσε την απάντηση και βάλε action: "ADVICE".
        
        Επίστρεψε ΑΥΣΤΗΡΑ ένα JSON με την εξής μορφή (χωρίς markdown, καθαρό JSON):
        {
            "reply": "Η απάντησή σου στον αγρότη. (Σύντομη, φιλική, άμεση)",
            "action": "ADD_TASK" | "DIAGNOSIS" | "ADVICE" | "UPDATE_KTIMA" | "DELETE_TASKS",
            "target_ktima_id": Αριθμός ID του κτήματος (του επιλεγμένου ή αυτού που αναφέρει ο χρήστης. Αν δεν μπορείς να το βρεις, βάλε null),
            "task_name": "Ονομασία Εργασίας (π.χ. 'Ψεκασμός με Χαλκό') ή 'ΟΛΕΣ' - ΚΕΝΟ αν δεν αφορά εργασία",
            "task_materials": "Όνομα φαρμάκου/λιπάσματος - ΚΕΝΟ αν δεν αναφέρεται",
            "updates": {
                "ardefsi": "Αρδευόμενο" ή "Ξηρικό" ή null,
                "diacheirisi_edafous": "Καθαρό (Οργωμένο/Ζιζανιοκτονία)" ή "Φυσική Βλάστηση (Άκοπα χόρτα)" ή "Κομμένα Χόρτα" ή null,
                "puknotita_dentron": "Αραιή" ή "Κανονική" ή "Πυκνή/Υπέρπυκνη" ή null
            }
        }
        """
        contents.append(prompt)

        if image_file and image_file.filename != '':
            img = PIL.Image.open(image_file)
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
        elif (action == 'DIAGNOSIS' or (image_file and image_file.filename != '')) and ktima:
            nea_diagnosi = Diagnosi(ktima_id=ktima.id, apotelesma=f"📸 AI Γραμματέας: {reply_text}", imerominia=datetime.now())
            vasi.session.add(nea_diagnosi)
            
        vasi.session.commit()
        return jsonify({'success': True, 'reply': reply_text, 'action': action})
    except Exception as e:
        return jsonify({'error': str(e)}), 500