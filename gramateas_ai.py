import os
import json
import unicodedata
import re
import PIL.Image
from werkzeug.utils import secure_filename
import io
from datetime import datetime
from flask import Blueprint, request, jsonify
from flask_login import login_required, current_user
from core import vasi
from models import Ktima, Ergasia, Diagnosi, Exodo, Apothiki, ArxeioSygkomidis, KatagrafiUgrasias, GenikoExodo, AnalysiEdafous
from google import genai
from google.genai import types

gramateas_bp = Blueprint('gramateas', __name__)

def _norm_gr(s):
    if not s:
        return ""
    s_norm = unicodedata.normalize('NFD', str(s))
    s_clean = ''.join(c for c in s_norm if unicodedata.category(c) != 'Mn').lower().strip()
    return s_clean

def _stem_gr_word(w):
    w = re.sub(r'[^\w]', '', w)
    for suf in ('ους', 'ων', 'ες', 'ος', 'οσ', 'ου', 'ον', 'ας', 'ασ', 'ης', 'ησ', 'ις', 'ισ', 'ο', 'α', 'η', 'ι', 'ω', 'ε'):
        if len(w) - len(suf) >= 3 and w.endswith(suf):
            return w[:-len(suf)]
    return w

_GR_STOPWORDS = {'στον', 'στου', 'στην', 'στη', 'στο', 'στους', 'στις', 'στα', 'του', 'της', 'των', 'τον', 'την', 'το', 'τα', 'ο', 'η', 'οι', 'ενα', 'εναν', 'μια', 'κατω', 'πανω', 'κοντα', 'μεσα', 'εξω', 'απο', 'για', 'με', 'σε', 'κτημα', 'χωραφι', 'ελαιωνας', 'ελαιωνα', 'χωραφια', 'κτηματα'}

def _extract_gr_stems(text_val):
    norm = _norm_gr(text_val)
    words = re.findall(r'[α-ωa-z0-9]+', norm)
    stems = []
    for w in words:
        if w in _GR_STOPWORDS:
            continue
        st = _stem_gr_word(w)
        if len(st) >= 2:
            stems.append(st)
    return stems

def _match_ktimata_by_text(candidate_val, energa_ktimata, is_full_sentence=False):
    if not candidate_val or not energa_ktimata:
        return []
    cand_norm = _norm_gr(candidate_val)
    if cand_norm in ('all', 'none', 'ολα', 'όλα', ''):
        return []
    cand_words = [w for w in re.findall(r'[α-ωa-z0-9]+', cand_norm) if w not in _GR_STOPWORDS]
    cand_clean = ' '.join(cand_words)
    cand_stems = _extract_gr_stems(candidate_val)
    if not cand_clean and not cand_stems:
        return []

    exact_matches = []
    stem_matches = []
    for k in energa_ktimata:
        k_norm = _norm_gr(k.onoma_ktimatos)
        k_words = [w for w in re.findall(r'[α-ωa-z0-9]+', k_norm) if w not in _GR_STOPWORDS]
        k_clean = ' '.join(k_words)
        k_stems = _extract_gr_stems(k.onoma_ktimatos)
        if not k_clean:
            continue

        if not is_full_sentence:
            if cand_clean == k_clean or (len(cand_clean) >= 3 and (cand_clean in k_clean or k_clean in cand_clean)):
                exact_matches.append(k)
                continue
        else:
            if len(k_clean) >= 3 and re.search(r'\b' + re.escape(k_clean) + r'\b', cand_norm):
                exact_matches.append(k)
                continue

        if k_stems and cand_stems:
            if not is_full_sentence:
                if all(any(cs == ks or (len(cs) >= 3 and len(ks) >= 3 and (cs.startswith(ks) or ks.startswith(cs))) for cs in cand_stems) for ks in k_stems) or \
                   all(any(cs == ks or (len(cs) >= 3 and len(ks) >= 3 and (cs.startswith(ks) or ks.startswith(cs))) for ks in k_stems) for cs in cand_stems):
                    stem_matches.append(k)
            else:
                if all(any(cs == ks or (len(cs) >= 3 and len(ks) >= 3 and (cs.startswith(ks) or ks.startswith(cs))) for cs in cand_stems) for ks in k_stems):
                    stem_matches.append(k)

    return exact_matches if exact_matches else stem_matches

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

    api_key_raw = getattr(current_user, 'gemini_api_key', None) or os.getenv('AI_API_KEY')
    api_key_to_use = api_key_raw.strip() if api_key_raw else None
    if not api_key_to_use:
        return jsonify({'error': 'Δεν έχει ρυθμιστεί κλειδί AI.'}), 500

    client = genai.Client(api_key=api_key_to_use, http_options=types.HttpOptions(api_version='v1beta'))

    try:
        # --- ΕΞΥΠΝΟΣ ΕΛΕΓΚΤΗΣ ΓΡΗΓΟΡΩΝ ΑΠΑΝΤΗΣΕΩΝ (Pre-filter) ---
        text_lower = text.lower().strip()
        aples_lexeis = ['γεια', 'καλημέρα', 'καλησπέρα', 'τι κάνεις', 'πως εισαι', 'ευχαριστώ', 'ok', 'ναι', 'όχι', 'τελεια', 'μια χαρα']
        
        try:
            parsed_history_pre = json.loads(history_str)
            if not isinstance(parsed_history_pre, list):
                parsed_history_pre = []
        except Exception:
            parsed_history_pre = []
        if not parsed_history_pre and getattr(current_user, 'secretary_history', None):
            try:
                db_hist = json.loads(current_user.secretary_history)
                if isinstance(db_hist, list):
                    parsed_history_pre = db_hist
            except Exception:
                pass

        last_assistant_msg = ""
        for h_msg in reversed(parsed_history_pre):
            if isinstance(h_msg, dict) and h_msg.get('role') in ('model', 'assistant'):
                last_assistant_msg = str(h_msg.get('content') or '')
                break
        last_assistant_asked_question = ('?' in last_assistant_msg or ';' in last_assistant_msg or ';' in last_assistant_msg)
        
        is_very_simple = (
            not last_assistant_asked_question
            and len(text_lower.split()) <= 4
            and any(text_lower.startswith(lexi) or text_lower == lexi for lexi in aples_lexeis)
        )
        valid_images = [f for f in image_files if f.filename != '']
        
        # Αν είναι πολύ απλή κουβέντα ΚΑΙ δεν έχει επισυνάψει εικόνες/αρχεία
        if is_very_simple and (not valid_images):
            # Κάνουμε μια πολύ γρήγορη, ελαφριά κλήση στο AI χωρίς κανένα context
            quick_prompt = f"Είσαι ο φιλικός AI Γραμματέας της Olea. Απάντα σύντομα και φιλικά στο εξής: '{text}'. ΠΡΟΣΟΧΗ: Σεβάσου απόλυτα την ταυτότητα που δηλώνει ο χρήστης στο ιστορικό (π.χ. αν είπε 'δεν είμαι αγρότης'). Ιστορικό: {history_str[-500:]}. Επίστρεψε ΑΥΣΤΗΡΑ JSON: {{\"reply\": \"...\", \"action\": \"ADVICE\"}}"
            
            try:
                quick_response = client.models.generate_content(
                    model='gemini-2.5-flash', 
                    contents=quick_prompt,
                    config=types.GenerateContentConfig() # Χωρίς internet, χωρίς τίποτα
                )
            except Exception as e:
                print(f"AI API Error: {e}")
                return jsonify({
                    'success': True, 
                    'reply': 'Αυτή τη στιγμή υπάρχει μεγάλος φόρτος στο σύστημα του Γεωπόνου. Παρακαλώ δοκιμάστε ξανά σε λίγα δευτερόλεπτα.', 
                    'action': 'ADVICE', 
                    'target_ktima_id': ktima_id
                })
            
            try:
                # Καθαρισμός του JSON (όπως κάνουμε και παρακάτω)
                import json, re
                raw_response = quick_response.text.strip()
                
                json_text = re.sub(r'^```json\s*', '', raw_response, flags=re.IGNORECASE)
                json_text = re.sub(r'^```\s*', '', json_text)
                json_text = re.sub(r'\s*```$', '', json_text)
                
                start_idx = json_text.find('{')
                end_idx = json_text.rfind('}')
                if start_idx != -1 and end_idx != -1:
                    json_text = json_text[start_idx:end_idx+1]
                
                json_text = json_text.replace('\n', ' ').replace('\r', '')
                
                data = json.loads(json_text, strict=False)
                reply_text = data.get('reply', 'Γεια σας! Πώς μπορώ να βοηθήσω με τα κτήματα;')
                
                # Αποθήκευση στο ιστορικό
                try:
                    history = json.loads(history_str)
                    if not isinstance(history, list): history = []
                except: history = []
                
                history.append({"role": "user", "content": text})
                history.append({"role": "model", "content": reply_text})
                if len(history) > 25: history = history[-25:] # Κράτα 25 μηνύματα για πλήρες context
                current_user.secretary_history = json.dumps(history)
                vasi.session.commit()
                
                return jsonify({
                    'success': True, 
                    'reply': reply_text, 
                    'action': 'ADVICE', 
                    'target_ktima_id': ktima_id
                })
            except Exception as quick_e:
                vasi.session.rollback()
                print(f"Σφάλμα στο quick response: {quick_e}")
                # Αν αποτύχει, συνεχίζει κανονικά παρακάτω
                pass
        
        # --- ΤΕΛΟΣ ΕΞΥΠΝΟΥ ΕΛΕΓΚΤΗ ---

        contents = []
        from logic import xtise_plires_context
        energa_ktimata = [k for k in current_user.ktimata if k.is_active]
        
        # Μάζεψε τα δεδομένα όλων των ενεργών κτημάτων
        ktimata_info = ""
        for k in energa_ktimata:
            context_ktimatos = xtise_plires_context(k)
            ktimata_info += f"\n=== ΚΤΗΜΑ: {k.onoma_ktimatos} (ID: {k.id}) ===\n{context_ktimatos}\n"
            
        context_str = (
            f"Είσαι ο προσωπικός 'AI Γραμματέας' στην Olea. Είσαι ένας έξυπνος συνομιλητής που προσαρμόζεται στον χρήστη. \n"
            f"ΚΑΝΟΝΑΣ: Μην χρησιμοποιείς τυποποιημένες προσφωνήσεις όπως 'αγρότη' αν ο χρήστης έχει δηλώσει ότι δεν του ταιριάζουν. Ακολούθησε το ύφος της συζήτησης.\n"
            f"Έχεις μπροστά σου τον παρακάτω φάκελο με τα δεδομένα των κτημάτων του (αναλύσεις, εκκρεμείς εργασίες, ελλείψεις εγγράφων, καιρός):\n"
            f"{ktimata_info}\n"
            f"ΟΔΗΓΙΕΣ: Αν ο χρήστης σε ρωτήσει 'Τι ανάλυση πρέπει να κάνω στο κτήμα Τάδε;' ή 'Γιατί μου έβαλες αυτή την εργασία;', ΨΑΞΕ στα δεδομένα (ειδικά στις ενότητες των Ελλείψεων ή του Ιστορικού) και ΕΞΗΓΗΣΕ του με απλά λόγια. Μην απαντάς γενικά. Να είσαι πρακτικός, φιλικός και να μιλάς άμεσα.\n"
        )

        if ktima:
            context_str += f"\nΤο ΕΝΕΡΓΟ κτήμα στη συζήτηση είναι το '{ktima.onoma_ktimatos}' (ID: {ktima.id}). Οι ενέργειές σου εξ ορισμού αφορούν αυτό, εκτός αν ο χρήστης ονομάσει διαφορετικό κτήμα.\n"
        elif ktima_id == 'all':
            context_str += "\nΟ αγρότης επέλεξε 'Όλα τα Κτήματα'. Αν ζητήσει καταχώρηση σε όλα, βάλε target_ktima_id = 'ALL' στο task.\n"
        else:
            context_str += (
                "\nΕΛΕΥΘΕΡΗ ΛΕΙΤΟΥΡΓΙΑ ΧΩΡΙΣ ΠΡΟΕΠΙΛΕΓΜΕΝΟ ΚΤΗΜΑ: Ο χρήστης σου γράφει ελεύθερα χωρίς να έχει επιλέξει κτήμα από μενού. "
                "Εντόπισε σε ποιο κτήμα αναφέρεται από το μήνυμά του ή από τα αμέσως προηγούμενα μηνύματα του ιστορικού συζήτησης. "
                "ΚΡΙΣΙΜΟ: Αν ο χρήστης έχει ΠΑΝΩ ΑΠΟ ΕΝΑ ενεργά κτήματα και ΔΕΝ αναφέρει ποιο κτήμα αφορά η ενέργεια ή η ερώτησή του (ούτε προκύπτει ξεκάθαρα από την τρέχουσα πρόταση/συζήτηση), "
                "ΜΗΝ μαντέψεις κτήμα! Ρώτησέ τον ευγενικά και ξεκάθαρα για ποιο από τα κτήματά του πρόκειται (αναφέροντας τα ονόματά τους) και βάλε action: 'ADVICE'.\n"
            )

            # Προσθήκη της Αποθήκης στη Γενική Προβολή
            if current_user.apothiki_items:
                stock = [f"'{i.onoma_proiontos}' ({i.posotita} {i.monada_metrisis})" for i in current_user.apothiki_items if i.posotita > 0]
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
        3. Επιβεβαίωση Αλλαγής Προφίλ: Αν ο χρήστης επιβεβαιώσει αλλαγή (π.χ. "Είναι αρδευόμενο", "Άλλαξέ το σε βιολογική", "Μετονόμασε σε...", "Το στάδιο είναι άνθιση", "Είναι ορεινό") συμπλήρωσε τις νέες τιμές στο object "updates". Αν ο χρήστης αναφέρει ότι φύτεψε, πρόσθεσε ή αφαίρεσε δέντρα (ακόμα και για ΜΙΑ ποικιλία, π.χ. "έβαλα 10 Αθηνοελιές", "έχω και 50 Αθηνοελιές"), ΧΡΗΣΙΜΟΠΟΙΗΣΕ ΠΑΝΤΑ το "poikilies_multi": [ {"onoma": "Αθηνοελιά", "arithmos": 10, "ilikia": "5 ετών"} ] όπου το "arithmos" είναι η ΔΙΑΦΟΡΑ (+10 για προσθήκη ή -5 για αφαίρεση), χωρίς να μηδενίζεις τις υπάρχουσες ποικιλίες. Το συνολικό "arithmos_dentron" θα υπολογιστεί αυτόματα, ΜΗΝ το στέλνεις. ΠΡΟΣΟΧΗ (ΑΝΤΙΚΑΤΑΣΤΑΣΗ / ΔΙΟΡΘΩΣΗ ΠΟΙΚΙΛΙΑΣ vs ΠΡΟΣΘΗΚΗ): Ξεχώρισε αυστηρά την προσθήκη δέντρων από την αντικατάσταση ή διόρθωση ποικιλίας (π.χ. "όλες είναι Αθηνοελιές", "άλλαξε τις Κορωνέικες σε Αθηνοελιές", "δεν είναι Κορωνέικες, είναι Αθηνοελιές"). Όταν πρόκειται για αντικατάσταση όλων των δέντρων μιας παλιάς ποικιλίας (ή όλων των δέντρων του κτήματος) με νέα ποικιλία: στείλε στην "poikilies_multi" τη νέα ποικιλία με τον συνολικό αριθμό δέντρων (διατηρώντας την υπάρχουσα ηλικία δέντρων αν δεν δόθηκε νέα) ΚΑΙ την παλιά ποικιλία με "arithmos": 0 (ή βάλε "replace_all_varieties": true μέσα στο "updates"), ώστε να μην διπλασιάζεται το σύνολο των δέντρων! Αν είναι απλή ενημέρωση προφίλ, βάλε action: "UPDATE_KTIMA". Στο "target_ktima_id" γράψε ΑΥΣΤΗΡΑ το ID του κτήματος.
        4. Προσθήκη Εργασιών (Πολλαπλές & Ημερομηνίες): Αν ο χρήστης λέει ότι έκανε μία ή ΠΟΛΛΑΠΛΕΣ εργασίες (π.χ. "ράντισα και μετά από ένα μήνα κλάδεψα"), βάλε action: "ADD_TASKS".
           - Υπολόγισε την ΗΜΕΡΟΜΗΝΙΑ: Αν λέει "τον Νοέμβριο μετά τη συγκομιδή", υπολόγισε και βάλε μια σχετική ημερομηνία στο "date" (π.χ. "2025-11-15"). Αν είναι ασαφές, ρώτα τον στο "reply" (action: "DIAGNOSIS").
           - Κατάσταση (status): Αν η εργασία ΕΧΕΙ ΓΙΝΕΙ, βάλε "status": "Ολοκληρώθηκε". Αν ο χρήστης λέει "πρέπει να ραντίσω", "βάλε σε εκκρεμότητα/αναμονή να...", "πρόσθεσε στο πρόγραμμα", βάλε "status": "Εκκρεμεί". ΠΡΟΣΟΧΗ: Αν ο χρήστης αρνείται να κάνει μια εκκρεμή εργασία, ΒΑΛΕ status: "Ακυρώθηκε"!
           - Για κάθε εργασία, φτιάξε ένα αντικείμενο στη λίστα "tasks".
           - Αν ζητάει καταχώρηση σε ΟΛΑ τα κτήματα, βάλε "target_ktima_id": "ALL" στο task. Αν αφορά ΕΝΑ συγκεκριμένο κτήμα (π.χ. "στη Μεγάλη Σπηλιά"), βάλε το ID του στο κεντρικό "target_ktima_id" της ρίζας του JSON (Οδηγία 16).
           - ΣΗΜΑΝΤΙΚΟ: Αν αναφέρει εμπορικό όνομα, βάλε τη δραστική στο "task_materials". Αν η εργασία είναι λίπανση ή αναφέρεται τύπος λιπάσματος (π.χ. NPK, 20-10-10, 21-0-0) ή ποσότητα σε κιλά, συμπλήρωσε και τα "lipasma_typos" (π.χ. "20-10-10") και "posotita" (αριθμός κιλών, π.χ. 50) στο task (ή στο "new_task_data" για UPDATE_TASKS).
        5. Διαχείριση, Ολοκλήρωση & Ακύρωση Εργασιών: Για ολοκλήρωση ή αναβολή, βάλε action: "UPDATE_TASKS" με "status": "Ολοκληρώθηκε" ή "date": "YYYY-MM-DD". ΑΝ Ο ΧΡΗΣΤΗΣ ΑΡΝΗΘΕΙ ΜΙΑ ΕΡΓΑΣΙΑ Ή ΠΕΙ ΟΤΙ ΔΕΝ ΜΠΟΡΕΙ (π.χ. 'δεν θα κάνω ανάλυση', 'δεν έχω νερό να ποτίσω', 'δεν θα κλαδέψω', 'άστο δεν χρειάζεται'), κάνε "UPDATE_TASKS" και βάλε "status": "Ακυρώθηκε". Με αυτόν τον τρόπο η εργασία φεύγει από το πρόγραμμα, αλλά παραμένει στο ιστορικό για να το θυμάσαι στις επόμενες συμβουλές σου! Αν ο χρήστης ζητήσει ρητά 'διαγραφή' επειδή έκανε λάθος καταχώρηση, κάνε "DELETE_TASKS".
        6. Πληροφορίες Ημερολογίου, Εκκρεμοτήτων & Καιρού (ΣΗΜΑΝΤΙΚΟ): ΕΧΕΙΣ ΗΔΗ ΠΡΟΣΒΑΣΗ στο 'ΗΜΕΡΟΛΟΓΙΟ (ΕΚΚΡΕΜΕΙΣ ΕΡΓΑΣΙΕΣ)' και στο ιστορικό παραπάνω. Αν ο χρήστης σε ρωτήσει "τι έχω στο ημερολόγιο;" ή "τι δουλειές πρέπει να γίνουν;", διάβασε την ενότητα ΗΜΕΡΟΛΟΓΙΟ και ΑΠΑΝΤΗΣΕ ΑΜΕΣΑ με τις ημερομηνίες! Ταξινόμησέ τες με βάση το τι επείγει. ΑΠΑΓΟΡΕΥΕΤΑΙ να πεις "θα ψάξω", δώσε τα δεδομένα κατευθείαν στο "reply" με action: "ADVICE".
        7. Οικονομικά (Έξοδα/Έσοδα): Αν το έξοδο/έσοδο αφορά ΣΥΓΚΕΚΡΙΜΕΝΟ ΚΤΗΜΑ, βάλε action: "ADD_EXPENSE" ("expense_amount", "expense_desc"). Αν είναι ΓΕΝΙΚΑ έξοδα (ένα ή περισσότερα) βάλε action: "ADD_GENERAL_EXPENSE" και συμπλήρωσε ΥΠΟΧΡΕΩΤΙΚΑ τη λίστα "general_expenses" βάζοντας σε κάθε αντικείμενο: "amount" (αριθμός), "desc" (περιγραφή) και "category" (Επιλογές: "Αναλώσιμα", "Ζημιές", "Γενικά").
           - ΟΔΗΓΙΑ ΚΑΤΗΓΟΡΙΟΠΟΙΗΣΗΣ: Στα "Αναλώσιμα" ανήκουν: Λάδια, πετρέλαιο/καύσιμα, ελαστικά/λάστιχα οχημάτων, λάστιχα/σωλήνες άρδευσης (π.χ. Φ23, σταλάκτες), εργαλεία χειρός, μπαταρίες, πριόνια, ανταλλακτικά συντήρησης. Στις "Ζημιές" ανήκουν αυστηρά: Επισκευές από σπάσιμο (π.χ. έσπασε η αντλία, χάλασε το βυτίο/τρακτέρ), βλάβες και ζημιές από καιρικά φαινόμενα. ΩΣΤΟΣΟ, αν ο χρήστης διαφωνήσει ρητά με την κατηγορία (π.χ. "το λάστιχο δεν είναι αναλώσιμο, είναι ζημιά"), κάνε UPDATE_EXPENSE και ικανοποίησε το αίτημά του!
          - Για διαγραφή εξόδου/εσόδου (π.χ. "λάθος καταχώρηση", "σβήσε τα 50 ευρώ"), βάλε action: "DELETE_EXPENSE" και συμπλήρωσε "expense_desc" (λέξη κλειδί) ή/και "expense_amount" (ποσό). Αν ο χρήστης ζητήσει να διαγραφούν ΟΛΑ τα έξοδα γενικά, βάλε action: "DELETE_EXPENSE", "expense_desc": "ΟΛΑ" και "target_ktima_id": "ALL".
          - Για ΔΙΟΡΘΩΣΗ/ΑΛΛΑΓΗ εξόδου (π.χ. "το λάστιχο είναι ζημιά, όχι αναλώσιμο", "διόρθωσε το ποσό σε 60"), βάλε action: "UPDATE_EXPENSE". Στο JSON βάλε "expense_desc" (Λέξη κλειδί του ΠΑΛΙΟΥ εξόδου) και συμπλήρωσε τα "new_expense_amount", "new_expense_desc" Ή "geniko_katigoria" με τα νέα δεδομένα.
        8. Έξυπνη Διαχείριση Χόρτων / Ζιζανίων: Η "Κοπή Χόρτων" ΤΙΚΑ αναζήτηση στο internet για να επιβεβαιώσεις 100% την ορθότητά της πριν απαντήσεις. Δώσε την απάντηση και βάλε action: "ADVICE".
        11. Καταγραφή Συγκομιδής: Αν ο χρήστης αναφέρει δεδομένα συγκομιδής (π.χ. "μάζεψα 5000 κιλά ελιές", "μάζεψα την Κορωνέικη 1000 κιλά"), βάλε action: "ADD_HARVEST". Στο JSON συμπλήρωσε "tonoi" (κιλά καρπού, 1 τόνος = 1000), "kila_ladi" (κιλά λαδιού) και "esoda" (ευρώ). ΣΗΜΑΝΤΙΚΟ: Βάλε "is_final": true ΑΝ ο χρήστης αναφέρει ότι τελείωσε όλη η συγκομιδή για φέτος (για να κλείσει η σεζόν). Αν είναι μερική συγκομιδή (π.χ. μάζεψε μόνο μία ποικιλία και έπεται συνέχεια), βάλε "is_final": false. Προαιρετικά βάλε "poikilia_sygkomidis": "Όνομα ποικιλίας" αν το αναφέρει.
        12. Ασαφή/Ελλιπή Δεδομένα: Αν ο χρήστης ζητήσει ενέργεια (π.χ. διαγραφή, ενημέρωση) για ένα κτήμα που ΔΕΝ υπάρχει στη λίστα, ΑΠΑΓΟΡΕΥΕΤΑΙ να πεις ψέματα ότι το έκανες. Πες του ότι δεν το βρίσκεις και ζήτα διευκρίνιση (action: "DIAGNOSIS"). Το ίδιο ισχύει για ελλιπή δεδομένα (π.χ. ρωτάει για εργασία και το ιστορικό είναι κενό).
        13. Διαχείριση Αποθήκης: Για αγορά/προσθήκη (ένα ή περισσότερα υλικά), βάλε action: "ADD_INVENTORY" και συμπλήρωσε ΥΠΟΧΡΕΩΤΙΚΑ τη λίστα "inventory_items" με αντικείμενα που έχουν "inv_name", "inv_category" (Φάρμακο, Λίπασμα, Εξοπλισμός), "inv_amount", "inv_unit" (Λίτρα, Κιλά, Τεμάχια) και προαιρετικά "expense_amount" (αν αναφέρει κόστος) και "expense_desc". Για διόρθωση υπολοίπου, βάλε action: "UPDATE_INVENTORY" (θέσε το "inv_name" και το "inv_amount" στο νέο νούμερο). Για πέταμα/διαγραφή προϊόντος, βάλε action: "DELETE_INVENTORY" (θέσε το "inv_name").
        14. Διαχείριση Υγρασίας & Νερού: Αν ο χρήστης αναφέρει μέτρηση υγρασίας (π.χ. "η υγρασία του εδάφους είναι 20%") ή ανάλυση νερού ("pH 7.2", "αγωγιμότητα 1.5"), βάλε action: "UPDATE_WATER" και συμπλήρωσε τα "moisture_percentage", "nero_ph", "nero_agwgimotita". Αν ο χρήστης ζητήσει διαγραφή μέτρησης υγρασίας (π.χ. "σβήσε την τελευταία μέτρηση υγρασίας", "λάθος υγρασία"), βάλε action: "DELETE_UGRASIA" (προαιρετικά συμπλήρωσε "moisture_percentage" αν αναφέρει συγκεκριμένο ποσοστό). Αν ρωτάει πόσο να ποτίσει, διάβασε τις 'Ανάγκες Άρδευσης' από τα δεδομένα και απάντησέ του.
        15. Γενικές / Άσχετες Ερωτήσεις (Internet Access): Είσαι πλέον συνδεδεμένος και στο διαδίκτυο (Google Search). Αν ο χρήστης σε ρωτήσει κάτι εντελώς άσχετο με τα χωράφια (π.χ. συνταγή μαγειρικής, ποιος κέρδισε έναν αγώνα, ειδήσεις, ιστορία), ΑΠΑΝΤΗΣΕ ΤΟΥ ΦΥΣΙΟΛΟΓΙΚΑ, φιλικά και σύντομα. ΜΗΝ προσπαθήσεις να συνδέσεις την ερώτηση με τα κτήματα. Βάλε action: "ADVICE". Αν ο χρήστης γράψει κάτι εντελώς ακατανόητο, γράψε στο reply: "Συγγνώμη, δεν σας κατάλαβα."
        16. Δημιουργία Νέου Κτήματος: Αν ο χρήστης ζητήσει να δημιουργήσεις ένα νέο κτήμα (π.χ. "φτιάξε ένα κτήμα") ή αν σε προηγούμενο μήνυμα τον ρώτησες πώς θέλει να ονομάσει το νέο κτήμα και σου απάντησε με το όνομα (ακόμα και μονολεκτικά, π.χ. "katageika", ΚΑΙ ΑΚΟΜΑ ΚΙ ΑΝ δεν έχει δώσει ακόμα αριθμό δέντρων, ποικιλία ή στρέμματα), ΕΚΤΕΛΕΣΕ ΑΜΕΣΩΣ action: "ADD_KTIMA" και συμπλήρωσε το "new_ktima_data" με το "onoma_ktimatos" (συμπεριλαμβάνοντας όσα επιπλέον στοιχεία τυχόν ανέφερε, όπως "stremmata", "typos_edafous", "klisi", "ardefsi", "kalliergeia_typos", "puknotita_dentron", "diacheirisi_edafous"). ΜΗΝ καθυστερείς τη δημιουργία ρωτώντας πρώτα πόσα δέντρα ή τι ποικιλία έχει! Αν ο χρήστης είπε απλώς "φτιάξε ένα νέο κτήμα" ΧΩΡΙΣ να δώσει όνομα, ρώτησέ τον μόνο "Πώς θέλετε να ονομάσουμε το νέο κτήμα;" (action: "ADVICE") και μόλις σου πει το όνομα, κάνε αμέσως action: "ADD_KTIMA". Στο "reply" σου όταν κάνεις "ADD_KTIMA", δώσε του ξεκάθαρες οδηγίες βασισμένες στα πραγματικά κουμπιά του παραθύρου χάρτη τοποθεσίας που του ανοίγει αυτόματα: πες του ότι "Το κτήμα δημιουργήθηκε! Σας ανοίγω αυτόματα τον χάρτη τοποθεσίας: πατήστε το κουμπί GPS (στόχαστρο) πάνω αριστερά για να βρείτε την περιοχή σας, επιλέξτε το εργαλείο πολυγώνου (⬟) αριστερά στον χάρτη για να σχεδιάσετε τα όρια του κτήματος (τα στρέμματα θα υπολογιστούν αυτόματα) και πατήστε 'Αποθήκευση Τοποθεσίας'. Στη συνέχεια μπορείτε να μου πείτε εδώ πόσα δέντρα, τι ποικιλία ή όποιο άλλο στοιχείο θέλετε να καταχωρήσω!". ΜΗΝ ρωτάς "Σε ποια περιοχή βρίσκεται".
        17. Διαγραφή / Αρχειοθέτηση Κτήματος: Αν θέλει να ΔΙΑΓΡΑΨΕΙ οριστικά ένα κτήμα, βάλε "DELETE_KTIMA" (Ρώτα τον πρώτα για επιβεβαίωση). Αν θέλει να το κρύψει/αρχειοθετήσει, βάλε "ARCHIVE_KTIMA". 
        18. Αυτόματη Επιλογή Κτήματος (ΚΡΙΣΙΜΟ): Αν ο χρήστης αναφέρει ΟΝΟΜΑΣΤΙΚΑ ένα κτήμα (π.χ. "Κάνε το τάδε στην Μεγάλη Σπηλιά", "Βάλε έξοδο στο...", "Πάμε στο...") βρες ΑΥΣΤΗΡΑ τον αριθμό ID του από τη Λίστα Ενεργών Κτημάτων. Βάλε ΥΠΟΧΡΕΩΤΙΚΑ το "target_ktima_id" ίσο με τον ΑΡΙΘΜΟ ID στη ρίζα του JSON, ΑΝΕΞΑΡΤΗΤΑ από το ποιο είναι το action (ακόμα και αν είναι ADD_TASKS, ADD_EXPENSE, κλπ). Αυτό είναι απολύτως απαραίτητο για να γυρίσει η οθόνη του χρήστη στο σωστό κτήμα! 
        ΣΗΜΑΝΤΙΚΟ: Αν ο χρήστης ζητήσει να δει ΠΑΝΩ ΑΠΟ ΕΝΑ κτήματα ταυτόχρονα, Ή ζητήσει ΣΥΓΚΡΙΣΗ, Ή "όλα τα κτήματα", ΤΟΤΕ βάλε "target_ktima_id": "ALL" και action: "SWITCH_KTIMA". ΜΗΝ βάλεις ποτέ το όνομα, μόνο το ID ή "ALL"! Στο "reply", εφόσον έχεις πρόσβαση σε όλα, απάντησε απευθείας.
        19. Εργαστηριακή Ανάλυση Εδάφους/Φύλλων: Αν ο χρήστης ανεβάσει ανάλυση, ΔΙΑΒΑΣΕ ΤΑ ΔΕΔΟΜΕΝΑ. ΠΡΟΣΟΧΗ: Αν η εικόνα είναι πολύ θολή/δυσανάγνωστη ή λείπει σελίδα (π.χ. έχει μόνο τη σελ. 1 από 2), ΑΠΑΝΤΗΣΕ ΤΟΥ στο "reply" να την ξανανεβάσει σωστά και βάλε action: "ADVICE". ΑΝ ΕΙΝΑΙ ΚΑΘΑΡΗ, βάλε action: "ADD_ANALYSIS". Στο "new_analysis_data" συμπλήρωσε "ph", "organiki_ousia", "azwto" (N), "fwsforos" (P), "kalio" (K) με αριθμούς. Αν αναφέρει τύπο εδάφους (π.χ. Αργιλώδες), βάλτο στο "typos_edafous". Αν ο χρήστης πει πότε έγινε (π.χ. "είναι περσινή", "τον Οκτώβριο του '24"), υπολόγισε την ημερομηνία και βάλτην στο "date" (YYYY-MM-DD).
        20. ΠΟΛΛΑΠΛΕΣ ΕΝΕΡΓΕΙΕΣ ΤΑΥΤΟΧΡΟΝΑ (MULTI-ACTION): Αν ο χρήστης ζητήσει ΠΟΛΛΑΠΛΕΣ ΚΑΙ ΔΙΑΦΟΡΕΤΙΚΕΣ ενέργειες ταυτόχρονα, βάλε action: "MULTI_ACTION". Το JSON σου πρέπει να περιέχει ΤΑΥΤΟΧΡΟΝΑ όσες από τις λίστες/ενέργειες χρειάζεται: "tasks_to_delete" (για διαγραφές), "tasks" (για νέες εργασίες), "general_expenses" (για γενικά έξοδα), "inventory_items" (για την αποθήκη) ΚΑΙ "new_ktima_data" (για δημιουργία νέου κτήματος). Το σύστημα θα τα εκτελέσει όλα με τη σωστή σειρά!
        21. ΜΕΛΛΟΝΤΙΚΕΣ ΥΠΕΝΘΥΜΙΣΕΙΣ (ΓΙΑ ΑΡΓΟΤΕΡΑ Ή ΤΟΥ ΧΡΟΝΟΥ): Αν ο χρήστης σου ζητήσει να του θυμίσεις κάτι για το μέλλον (π.χ. "σε ένα μήνα θύμισέ μου να δω τα μπόλια", "σε 2 εβδομάδες", "του χρόνου"), βάλε action: "ADD_TASKS". Υπολόγισε την ακριβή ημερομηνία (π.χ. αν λέει 'σε 1 μήνα', βάλε ημερομηνία +30 μέρες από σήμερα). Στο "task_name" γράψε ΑΚΡΙΒΩΣ με αυτό το πρόθεμα: "[AI ΥΠΕΝΘΥΜΙΣΗ] [Η δουλειά/έλεγχος]" (π.χ. "[AI ΥΠΕΝΘΥΜΙΣΗ] Έλεγχος στα μπολιάδια") και βάλε "status": "Εκκρεμεί". Όταν έρθει η ώρα, το σύστημα θα του το θυμίσει αυτόματα το πρωί!
        
        ΑΠΑΓΟΡΕΥΕΤΑΙ ΑΥΣΤΗΡΑ η χρήση διπλών εισαγωγικών (") μέσα στα κείμενα ή τις απαντήσεις σου. Χρησιμοποίησε ΜΟΝΟ μονά εισαγωγικά ('). Απαγορεύεται να χρησιμοποιήσεις αλλαγές γραμμής (Enter/Newlines) μέσα στα string values.
        
        Επίστρεψε ΑΥΣΤΗΡΑ ένα JSON με την εξής μορφή (χωρίς markdown, καθαρό JSON):
        {
            "reply": "Η απάντησή σου. Πρέπει να είναι ΣΥΝΤΟΜΗ, ΦΙΛΙΚΗ, ΦΥΣΙΚΗ και πολύ πρακτική.",
            "action": "MULTI_ACTION" | "ADD_TASKS" | "DIAGNOSIS" | "ADVICE" | "UPDATE_KTIMA" | "DELETE_TASKS" | "UPDATE_TASKS" | "ADD_EXPENSE" | "ADD_INCOME" | "ADD_GENERAL_EXPENSE" | "ADD_GENERAL_INCOME" | "DELETE_EXPENSE" | "UPDATE_EXPENSE" | "DELETE_UGRASIA" | "ADD_HARVEST" | "ADD_INVENTORY" | "UPDATE_INVENTORY" | "DELETE_INVENTORY" | "UPDATE_WATER" | "ADD_KTIMA" | "DELETE_KTIMA" | "ARCHIVE_KTIMA" | "SWITCH_KTIMA" | "ADD_ANALYSIS",
            "tasks": [
                {
                    "target_ktima_id": "Αριθμός ID κτήματος Ή 'ALL'",
                    "task_name": "Ονομασία Εργασίας...",
                    "task_materials": "Φάρμακα/Λιπάσματα - ΚΕΝΟ αν δεν αναφέρεται",
                    "lipasma_typos": "Τύπος λιπάσματος N-P-K (π.χ. 20-10-10 ή 21-0-0) ή null",
                    "posotita": 50.0,
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
            "tasks_to_update": [
                {
                    "target_ktima_id": "ALL",
                    "task_name": "ΟΛΕΣ ή όνομα εργασίας",
                    "new_task_data": {
                        "date": "YYYY-MM-DD",
                        "task_name": "Νέο όνομα (αν χρειάζεται)",
                        "task_materials": "Νέα υλικά (αν χρειάζεται)",
                        "lipasma_typos": "Νέος τύπος λιπάσματος (π.χ. 20-10-10) ή null",
                        "posotita": 50.0,
                        "status": "Ολοκληρώθηκε ή Εκκρεμεί ή Ακυρώθηκε"
                    }
                }
            ],
            "target_ktima_id": "Αριθμός ID Ή 'ALL' (γενική χρήση)",
            "task_name": "ΟΛΕΣ ή λέξη (Μόνο για DELETE_TASKS ή UPDATE_TASK)",
            "expense_amount": 50,
            "expense_desc": "Περιγραφή κόστους",
            "new_expense_amount": 60,
            "new_expense_desc": "Νέα περιγραφή",
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
            "lipasma_typos": "Τύπος λιπάσματος (π.χ. 20-10-10) ή null",
            "posotita": 50.0,
            "status": "Ολοκληρώθηκε ή Εκκρεμεί ή Ακυρώθηκε"
            },
            "new_ktima_data": {
                "onoma_ktimatos": "Όνομα...",
                "arithmos_dentron": 20,
                "poikilia": "Κορωνέικη",
                "ilikia_dentron": "Παραγωγικά (6-40 ετών) ή ότι αναφέρει",
                "poikilies_multi": [{"onoma": "Κορωνέικη", "arithmos": 20}],
                "stremmata": 10.5,
                "typos_edafous": "Αμμώδες ή Αργιλώδες ή Πηλώδες ή Πετρώδες ή null",
                "klisi": "Πεδινό ή Επικλινές/Πλαγιά ή Ορεινό ή Ρέμα/Κοιλότητα ή null",
                "ardefsi": "Αρδευόμενο ή Ξηρικό ή null",
                "kalliergeia_typos": "Βιολογική ή Συμβατική ή null",
                "puknotita_dentron": "Αραιή ή Κανονική ή Πυκνή/Υπέρπυκνη ή null",
                "diacheirisi_edafous": "Καθαρό (Οργωμένο/Ζιζανιοκτονία) ή Φυσική Βλάστηση (Άκοπα χόρτα) ή Κομμένα Χόρτα ή null"
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
                "poikilies_multi": [{"onoma": "Αθηνοελιά", "arithmos": 50, "ilikia": "Παραγωγικά (6-40 ετών)"}],
                "replace_all_varieties": false,
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
                
        # Έξυπνη Ενεργοποίηση Internet και ΥΠΟΧΡΕΩΤΙΚΟ JSON MODE
        text_lower = text.lower()
        text_norm = _norm_gr(text)
        agrotikes_lexeis = ['κτήμα', 'χωράφι', 'έξοδα', 'δουλειές', 'έσοδα', 'αποθήκη', 'ραντίσω', 'κλάδεψα', 'λιπασμα', 'συνολο', 'σβήσε', 'όλα']
        agrotika_stems = [
            'κτημ', 'χωραφ', 'ελαιων', 'εξοδ', 'εσοδ', 'επιδοτ', 'δουλει', 'εργασι', 'αποθηκ',
            'ραντισ', 'ψεκασ', 'κλαδε', 'λιπασμ', 'λιπανσ', 'ποτισ', 'αρδευσ', 'χορτ', 'ζιζαν',
            'μαζεψ', 'μαζεμ', 'συγκομιδ', 'ελι', 'λαδ', 'δεντρ', 'ποικιλ', 'σβησ', 'διαγραψ',
            'ολοκληρωσ', 'ακυρωσ', 'εκκρεμ', 'υπενθυμισ', 'θυμισ', 'αναλυσ', 'υγρασι', 'νερ',
            'αγορασ', 'πετρελαι', 'χαλκ', 'βορι', 'δακ', 'οργωσ', 'οργωμ', 'φρεζ', 'συνολ', 'ολα'
        ]
        search_intent_patterns = [
            'ψαξε στο ιντερνετ', 'ψαξε στο διαδικτυο', 'αναζητησε', 'ειδησεις', 'νεα για', 'τιμη λαδιου σημερα', 'καιρος αυριο'
        ]
        wants_web_search = any(p in text_norm for p in search_intent_patterns)
        is_simple_query = (
            any(lexi in text_lower for lexi in agrotikes_lexeis)
            or any(st in text_norm for st in agrotika_stems)
            or bool(_match_ktimata_by_text(text, energa_ktimata, is_full_sentence=True))
            or last_assistant_asked_question
        ) and not wants_web_search
        
        if is_simple_query or not text or valid_images:
            config = types.GenerateContentConfig(
                response_mime_type="application/json"
            )
        else:
            # Το response_mime_type="application/json" ΔΕΝ υποστηρίζεται ταυτόχρονα με το Google Search
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
                print(f"AI API Error: {e}")
                if attempt == 2:
                    return jsonify({'success': True, 'reply': 'Αυτή τη στιγμή υπάρχει μεγάλος φόρτος στο σύστημα του Γεωπόνου. Παρακαλώ δοκιμάστε ξανά σε λίγα δευτερόλεπτα.', 'action': 'ADVICE'})
                time.sleep(3 * (attempt + 1)) # Backoff: περιμένει 3s, μετά 6s αν αποτύχει
        
        # Δικλείδα Ασφαλείας: Αν το AI επιστρέψει κενό (π.χ. λόγω safety filters)
        if not response or not getattr(response, 'text', None):
            return jsonify({'success': True, 'reply': '⚠️ Δεν κατάφερα να διακρίνω καθαρά τη φωτογραφία ή το κείμενο. Μπορείτε να ανεβάσετε μια πιο καθαρή λήψη;', 'action': 'ADVICE'})
            
        import json, re
        raw_response = response.text.strip()
        
        # 1. Καθαρισμός Markdown Fences
        json_text = re.sub(r'^```json\s*', '', raw_response, flags=re.IGNORECASE)
        json_text = re.sub(r'^```\s*', '', json_text)
        json_text = re.sub(r'\s*```$', '', json_text)
        
        # 2. Απομόνωση του JSON block
        start_idx = json_text.find('{')
        end_idx = json_text.rfind('}')
        if start_idx != -1 and end_idx != -1:
            json_text = json_text[start_idx:end_idx+1]
            
        # 3. Ασφαλής αφαίρεση αλλαγών γραμμής μέσα στα strings του JSON
        json_text = json_text.replace('\n', ' ').replace('\r', '')
            
        try:
            data = json.loads(json_text, strict=False)
        except Exception as e:
            print(f"Σφάλμα JSON Parsing: {e}\nΚείμενο: {json_text}")
            # Fallback μηχανισμός
            fallback_reply = "Η απάντησή μου ήταν πολύ μεγάλη και μπερδεύτηκα. Μπορείτε να επαναλάβετε;"
            reply_match = re.search(r'"reply"\s*:\s*"([^"]+)"', json_text)
            if reply_match:
                fallback_reply = reply_match.group(1)
            data = {"action": "ADVICE", "reply": fallback_reply}
        
        action = data.get('action', 'ADVICE')
        reply_text = data.get('reply', 'Συγγνώμη, δεν σας κατάλαβα.')
        import re
        reply_text = re.sub(r'\s*\(?ID:\s*\d+\)?', '', reply_text, flags=re.IGNORECASE)
        target_ktima_id = data.get('target_ktima_id')
        ambiguous_ktimata = []

        def _resolve_single_ktima(raw_id_or_name, fallback_ktima=None):
            if raw_id_or_name and str(raw_id_or_name).strip().upper() not in ['ALL', 'NONE', '']:
                try:
                    k_int = int(raw_id_or_name)
                    k_obj = vasi.session.get(Ktima, k_int)
                    if k_obj and k_obj.idioktitis == current_user:
                        return k_obj, []
                except (ValueError, TypeError):
                    pass
                matched = _match_ktimata_by_text(raw_id_or_name, energa_ktimata, is_full_sentence=False)
                if len(matched) == 1:
                    return matched[0], []
                elif len(matched) > 1:
                    return None, matched
            return fallback_ktima, []

        # Αν λείπει ή είναι 'ALL'/'NONE' στη ρίζα, ελέγχουμε αν υπάρχει συγκεκριμένο κτήμα μέσα στα tasks/tasks_to_update/tasks_to_delete
        if not target_ktima_id or str(target_ktima_id).strip().upper() in ['ALL', 'NONE', '']:
            sub_ids = []
            for list_key in ('tasks', 'tasks_to_update', 'tasks_to_delete'):
                items_list = data.get(list_key)
                if isinstance(items_list, list):
                    for it in items_list:
                        if isinstance(it, dict) and it.get('target_ktima_id') and str(it.get('target_ktima_id')).strip().upper() not in ['ALL', 'NONE', '']:
                            sub_ids.append(it.get('target_ktima_id'))
            if len(set(str(x) for x in sub_ids)) == 1:
                target_ktima_id = sub_ids[0]

        # Επίλυση target_ktima_id αν δόθηκε από το AI (ID ή όνομα)
        if target_ktima_id and str(target_ktima_id).strip().upper() not in ['ALL', 'NONE', '']:
            resolved_k, amb_list = _resolve_single_ktima(target_ktima_id, fallback_ktima=None)
            if resolved_k:
                ktima = resolved_k
                target_ktima_id = ktima.id
            elif amb_list:
                ambiguous_ktimata = amb_list
                ktima = None
            else:
                ktima = None

        # Αν ακόμα δεν έχουμε συγκεκριμένο κτήμα (π.χ. ο χρήστης είναι σε 'all' ή 'none'), ψάχνουμε στο κείμενο του χρήστη
        if not ktima and not ambiguous_ktimata:
            text_matches = _match_ktimata_by_text(text, energa_ktimata, is_full_sentence=True)
            if len(text_matches) == 1:
                ktima = text_matches[0]
                if not target_ktima_id or str(target_ktima_id).strip().upper() in ['ALL', 'NONE', '']:
                    # Αν ο χρήστης δεν ζήτησε ρητά "όλα τα κτήματα" στο κείμενο, θέτουμε το κτήμα που βρέθηκε
                    if not any(w in _norm_gr(text) for w in ('ολα τα κτηματα', 'σε ολα', 'ολα μου τα κτηματα')):
                        target_ktima_id = ktima.id
            elif len(text_matches) > 1:
                ambiguous_ktimata = text_matches

        # Χρήση της επιλογής από το μενού ως προεπιλογή αν το AI δεν έστειλε κάτι και δεν βρέθηκε άλλο
        if not target_ktima_id:
            target_ktima_id = ktima_id
        if ktima and (not target_ktima_id or str(target_ktima_id).strip().upper() in ['NONE', '']):
            target_ktima_id = ktima.id

        # Έλεγχος αν ο χρήστης ζήτησε ρητά "όλα τα κτήματα"
        explicit_all_requested = (
            str(data.get('target_ktima_id') or '').strip().upper() == 'ALL'
            and any(w in _norm_gr(text) for w in ('ολα', 'όλα', 'παντου', 'καθε κτημα'))
        )

        # 1. Αν βρέθηκαν 2+ κτήματα με παρόμοιο όνομα (διφορούμενο κτήμα)
        if ambiguous_ktimata and action not in ['ADVICE', 'ADD_KTIMA', 'ADD_INVENTORY', 'UPDATE_INVENTORY', 'DELETE_INVENTORY', 'ADD_GENERAL_EXPENSE', 'ADD_GENERAL_INCOME']:
            names_str = ', '.join(f"'{k.onoma_ktimatos}'" for k in ambiguous_ktimata)
            reply_text = f"Βρήκα περισσότερα από ένα κτήματα που ταιριάζουν ({names_str}). Μπορείτε να μου διευκρινίσετε σε ποιο κτήμα αναφέρεστε;"
            action = 'ADVICE'
            target_ktima_id = None

        # 2. Backend Safety Check: Αν δόθηκε όνομα/ID κτήματος που δεν βρέθηκε καθόλου
        elif target_ktima_id and str(target_ktima_id).upper() not in ['ALL', 'NONE'] and not ktima:
            if action not in ['ADVICE', 'DIAGNOSIS', 'ADD_KTIMA', 'ADD_INVENTORY', 'UPDATE_INVENTORY', 'DELETE_INVENTORY', 'ADD_GENERAL_EXPENSE', 'ADD_GENERAL_INCOME']:
                reply_text = "Συγγνώμη, αλλά δεν βρήκα κάποιο κτήμα με αυτό το όνομα. Παρακαλώ ελέγξτε τη λίστα με τα ενεργά κτήματά σας."
                action = 'ADVICE'
                target_ktima_id = None

        # 3. Έλεγχος ενεργειών που απαιτούν συγκεκριμένο κτήμα (αποφυγή σιωπηλής αποτυχίας ή λάθος χρέωσης στο energa_ktimata[0])
        elif not ktima and not explicit_all_requested:
            single_ktima_actions = {
                'UPDATE_KTIMA', 'ADD_HARVEST', 'UPDATE_WATER', 'DELETE_UGRASIA', 'DELETE_KTIMA', 'ARCHIVE_KTIMA',
                'ADD_EXPENSE', 'ADD_INCOME', 'ADD_ANALYSIS', 'UPDATE_TASKS', 'UPDATE_TASK', 'DELETE_TASKS'
            }
            needs_ktima_for_diag = (action == 'DIAGNOSIS' and bool(valid_images))
            needs_ktima_for_updates = (isinstance(data.get('updates'), dict) and any(v is not None for v in data.get('updates', {}).values()) and action not in ['ADD_KTIMA'])
            if action in single_ktima_actions or needs_ktima_for_diag or needs_ktima_for_updates:
                if len(energa_ktimata) == 1:
                    ktima = energa_ktimata[0]
                    target_ktima_id = ktima.id
                else:
                    available_names = ', '.join(f"'{k.onoma_ktimatos}'" for k in energa_ktimata)
                    if available_names:
                        reply_text = f"Για να προχωρήσω στην καταχώρηση, παρακαλώ διευκρινίστε μου για ποιο κτήμα πρόκειται ({available_names})."
                    else:
                        reply_text = "Δεν βρέθηκε ενεργό κτήμα για αυτή την καταχώρηση. Παρακαλώ δημιουργήστε πρώτα ένα κτήμα."
                    action = 'ADVICE'
                    target_ktima_id = None

        executed_ktima_names = []
        all_ktimata_targeted = False
        def _track_target_ktima(k_obj=None, is_all=False):
            nonlocal all_ktimata_targeted
            if is_all:
                all_ktimata_targeted = True
            elif k_obj and getattr(k_obj, 'onoma_ktimatos', None):
                if k_obj.onoma_ktimatos not in executed_ktima_names:
                    executed_ktima_names.append(k_obj.onoma_ktimatos)

        # --- ΠΡΩΤΑ ΕΚΤΕΛΟΥΝΤΑΙ ΟΙ ΔΙΑΓΡΑΦΕΣ ΕΡΓΑΣΙΩΝ (Για να μην σβηστούν οι νέες αν γίνει MULTI_ACTION) ---
        if action in ['DELETE_TASKS', 'MULTI_ACTION']:
            del_list = data.get('tasks_to_delete', [])
            if not del_list and data.get('task_name') and action != 'MULTI_ACTION':
                del_list = [{'target_ktima_id': target_ktima_id, 'task_name': data.get('task_name'), 'task_date': data.get('task_date') or data.get('date', '')}]
                
            total_deleted_tasks = 0
            had_delete_attempt = bool(del_list)
            for del_item in del_list:
                t_name = del_item.get('task_name', '')
                t_date = del_item.get('task_date') or del_item.get('date', '')
                t_k_id = del_item.get('target_ktima_id') or target_ktima_id
                
                del_targets = []
                if str(t_k_id).upper() == 'ALL' and explicit_all_requested:
                    del_targets = energa_ktimata
                else:
                    resolved_t_k, _ = _resolve_single_ktima(t_k_id, fallback_ktima=ktima)
                    if resolved_t_k:
                        del_targets.append(resolved_t_k)
                        if not ktima:
                            ktima = resolved_t_k
                            target_ktima_id = resolved_t_k.id
                        
                for target_k in del_targets:
                    if t_name == 'ΟΛΕΣ' and not t_date:
                        existing_count = Ergasia.query.filter_by(ktima_id=target_k.id).count()
                        if existing_count > 0:
                            Ergasia.query.filter_by(ktima_id=target_k.id).delete()
                            total_deleted_tasks += existing_count
                            _track_target_ktima(target_k, is_all=(str(t_k_id).upper() == 'ALL' and explicit_all_requested))
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
                                eidos_norm = _norm_gr(eidos)
                                farmaka_norm = _norm_gr(farmaka)
                                search_norm = _norm_gr(search_term)
                                
                                if search_term in eidos or search_term in farmaka or (search_norm and (search_norm in eidos_norm or search_norm in farmaka_norm)):
                                    match_name = True
                                else:
                                    # Ψάχνουμε μεμονωμένες λέξεις > 3 χαρακτήρων αν δεν ταιριάζει ακριβώς
                                    words = [w for w in search_term.split() if len(w) > 3]
                                    for w in words:
                                        w_norm = _norm_gr(w)
                                        if w in eidos or w in farmaka or (w_norm and (w_norm in eidos_norm or w_norm in farmaka_norm)):
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
                                total_deleted_tasks += 1
                                # Προστασία: Αν δεν δόθηκε ημερομηνία, σβήνουμε ΜΟΝΟ την πιο πρόσφατη που ταιριάζει
                                if not t_date and t_name != 'ΟΛΕΣ':
                                    break
                                
                        if deleted_count > 0:
                            _track_target_ktima(target_k, is_all=(str(t_k_id).upper() == 'ALL' and explicit_all_requested))
                            vasi.session.add(Diagnosi(ktima_id=target_k.id, apotelesma=f"🗑️ AI Γραμματέας: Έγινε διαγραφή {deleted_count} εργασίας ({t_name} {t_date}).", imerominia=datetime.now()))
                    
                    target_k.ekkremis_erotisi_ai = None

            if action == 'DELETE_TASKS' and (not had_delete_attempt or total_deleted_tasks == 0):
                reply_text = "Δεν βρέθηκε αντίστοιχη εργασία για διαγραφή."
        
        if action in ['ADD_TASK', 'ADD_TASKS', 'MULTI_ACTION']:
            tasks_list = data.get('tasks', [])
            # Αν το AI γύρισε παλιά δομή (1 εργασία)
            if not tasks_list and data.get('task_name') and action != 'MULTI_ACTION':
                tasks_list = [data]

            def _extract_fertilizer_info(t_dict, fallback_dict=None):
                f_dict = fallback_dict if isinstance(fallback_dict, dict) else {}
                eidos_str = str(t_dict.get('task_name') or f_dict.get('task_name') or '')
                mat_str = str(t_dict.get('task_materials') or f_dict.get('task_materials') or '')
                combined_text = f"{eidos_str} {mat_str}"

                raw_typos = t_dict.get('lipasma_typos') or f_dict.get('lipasma_typos')
                lip_typos = str(raw_typos).strip()[:50] if raw_typos and str(raw_typos).strip().lower() not in ['null', 'none', ''] else None
                if not lip_typos:
                    npk_m = re.search(r'\b(\d{1,2}\s*[-.,]\s*\d{1,2}\s*[-.,]\s*\d{1,2}(?:\s*\+\s*[\w\d.,]+)?)\b', combined_text)
                    if npk_m:
                        lip_typos = re.sub(r'\s+', '', npk_m.group(1)).replace(',', '.')[:50]

                raw_pos = t_dict.get('posotita') if t_dict.get('posotita') is not None else f_dict.get('posotita')
                pos_val = None
                if raw_pos is not None and str(raw_pos).strip().lower() not in ['null', 'none', '']:
                    try:
                        pos_val = float(str(raw_pos).replace(',', '.'))
                    except (ValueError, TypeError):
                        pos_val = None
                if pos_val is None:
                    is_fert_context = bool(lip_typos) or any(k in _norm_gr(combined_text) for k in ('λιπανσ', 'λιπασμ', 'npk', 'αζωτ', 'καλι', 'φωσφορ', 'βορι', 'ουρι', 'αμμωνι'))
                    if is_fert_context:
                        kg_m = re.search(r'(\d+(?:[.,]\d+)?)\s*(?:κιλ[αάώω]?|kg|kgr)\b', combined_text, flags=re.IGNORECASE)
                        if kg_m:
                            try:
                                pos_val = float(kg_m.group(1).replace(',', '.'))
                            except (ValueError, TypeError):
                                pos_val = None
                        elif t_dict.get('used_material_amount') is not None:
                            try:
                                pos_val = float(t_dict.get('used_material_amount'))
                            except (ValueError, TypeError):
                                pos_val = None

                if lip_typos and not mat_str.strip():
                    mat_str = f"Λίπασμα {lip_typos}" + (f" ({pos_val:g} κιλά)" if pos_val else "")
                elif lip_typos and lip_typos not in mat_str:
                    mat_str = f"{mat_str} ({lip_typos})".strip()
                if pos_val and f"{pos_val:g}" not in mat_str and 'κιλ' not in mat_str.lower() and 'kg' not in mat_str.lower():
                    mat_str = f"{mat_str} ({pos_val:g} κιλά)".strip() if mat_str else f"{pos_val:g} κιλά"

                return lip_typos, pos_val, mat_str[:255]
                
            for task_data in tasks_list:
                t_ktima_id = task_data.get('target_ktima_id') or target_ktima_id
                target_ktimata = []
                if str(t_ktima_id).upper() == 'ALL' and explicit_all_requested:
                    target_ktimata = energa_ktimata
                else:
                    resolved_t_k, _ = _resolve_single_ktima(t_ktima_id, fallback_ktima=ktima)
                    if resolved_t_k:
                        target_ktimata.append(resolved_t_k)
                        if not ktima:
                            ktima = resolved_t_k
                            target_ktima_id = resolved_t_k.id
                    elif len(energa_ktimata) == 1:
                        target_ktimata.append(energa_ktimata[0])
                        ktima = energa_ktimata[0]
                        target_ktima_id = ktima.id
                    else:
                        available_names = ', '.join(f"'{k.onoma_ktimatos}'" for k in energa_ktimata)
                        reply_text = f"Για να καταχωρήσω την εργασία, παρακαλώ διευκρινίστε μου σε ποιο κτήμα αναφέρεστε ({available_names})."
                        action = 'ADVICE'
                        target_ktima_id = None
                        break
                        
                for target_k in target_ktimata:
                    date_str = task_data.get('date')
                    im = datetime.now()
                    if date_str:
                        try: im = datetime.strptime(date_str, '%Y-%m-%d')
                        except: pass
                        
                    status_ergasias = task_data.get('status', 'Ολοκληρώθηκε')
                    lip_typos_val, posotita_val, materials_val = _extract_fertilizer_info(task_data, fallback_dict=data)
                    nea_ergasia = Ergasia(
                        ktima_id=target_k.id, 
                        eidos_ergasias=task_data.get('task_name', 'Νέα Εργασία'),
                        katastasi=status_ergasias,
                        imerominia=im,
                        farmaka_lipasmata=materials_val,
                        lipasma_typos=lip_typos_val,
                        posotita=posotita_val,
                        proelevsi='AI Γραμματέας'
                    )
                    vasi.session.add(nea_ergasia)
                    _track_target_ktima(target_k, is_all=(str(t_ktima_id).upper() == 'ALL' and explicit_all_requested))
                    
                    # ΕΞΥΠΝΟΣ ΚΑΘΑΡΙΣΜΟΣ ΕΚΚΡΕΜΟΤΗΤΩΝ: Αν είναι "Ολοκληρωμένη", σβήνει την ίδια "Εκκρεμή"
                    if status_ergasias == 'Ολοκληρώθηκε':
                        pending_tasks = Ergasia.query.filter_by(ktima_id=target_k.id, katastasi='Εκκρεμεί').all()
                        new_task_text = f"{task_data.get('task_name', '').lower()} {task_data.get('task_materials', '').lower()}"
                        
                        synonym_groups = [
                            {'πότισμ', 'νερ', 'άρδευσ'},
                            {'χόρτ', 'ζιζάν', 'καταστροφ'},
                            {'λίπανσ', 'θρέψη', 'άζωτ', 'βόρι', 'αμινοξ', 'κάλι', 'φωσφορ'},
                            {'κλάδεμ'},
                            {'χαλκ', 'μυκητοκτόν', 'ψεκασμ'},
                            {'δάκ', 'εντομοκτόν', 'πυρηνοτρύτ', 'ψεκασμ'},
                            {'όργωμ', 'φρέζ'},
                        ]
                        new_task_group_idx = -1
                        for i, group in enumerate(synonym_groups):
                            if any(syn in new_task_text for syn in group):
                                new_task_group_idx = i
                                break

                        if new_task_group_idx != -1:
                            for pt in pending_tasks:
                                pending_task_text = f"{pt.eidos_ergasias.lower()} {(pt.farmaka_lipasmata or '').lower()}"
                                if any(syn in pending_task_text for syn in synonym_groups[new_task_group_idx]):
                                    vasi.session.delete(pt)
                    
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
                    vasi.session.add(Diagnosi(ktima_id=target_k.id, apotelesma=f"🌿 Αναγνώριση Σταδίου: {target_k.fainologiko_stadio}", imerominia=datetime.now()))
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

                        def _is_known_age(age_val):
                            if not age_val:
                                return False
                            a_norm = normalize_str(age_val)
                            return a_norm not in ('', 'αγνωστη', 'αγνωστο', 'δεν οριστηκε', 'null', 'none')

                        # Αποθήκευση γνωστών ηλικιών και συνολικών δέντρων πριν από πιθανή αντικατάσταση/μηδενισμό
                        prev_total_trees = target_k.arithmos_dentron or sum((p.arithmos_dentron or 0) for p in target_k.poikilies_details)
                        inherited_age = None
                        age_by_variety = {}
                        for p in target_k.poikilies_details:
                            if _is_known_age(p.ilikia_dentron):
                                age_by_variety[normalize_str(p.poikilia_onoma)] = p.ilikia_dentron
                                if not inherited_age:
                                    inherited_age = p.ilikia_dentron
                        if not inherited_age and _is_known_age(target_k.ilikia_dentron):
                            inherited_age = target_k.ilikia_dentron

                        replace_all_flag = bool(updates.get('replace_all_varieties'))
                        zeroed_age = None

                        # Αν δόθηκε replace_all_varieties: true, καθαρίζουμε τις προηγούμενες ποικιλίες ώστε να γίνει καθαρή αντικατάσταση
                        if replace_all_flag:
                            for p in list(target_k.poikilies_details):
                                if _is_known_age(p.ilikia_dentron) and not zeroed_age:
                                    zeroed_age = p.ilikia_dentron
                                p.arithmos_dentron = 0
                                vasi.session.delete(p)
                            target_k.poikilies_details.clear()
                        else:
                            # Πρώτο πέρασμα: αν υπάρχουν στοιχεία με arithmos == 0 (ρητός μηδενισμός παλιάς ποικιλίας για αντικατάσταση)
                            for item in updates['poikilies_multi']:
                                v_name = item.get('onoma')
                                v_diff = item.get('arithmos', 0)
                                if v_name and v_diff == 0:
                                    req_p_norm = normalize_str(v_name)
                                    for p in list(target_k.poikilies_details):
                                        if normalize_str(p.poikilia_onoma) == req_p_norm:
                                            if _is_known_age(p.ilikia_dentron) and not zeroed_age:
                                                zeroed_age = p.ilikia_dentron
                                            p.arithmos_dentron = 0
                                            vasi.session.delete(p)
                                            if p in target_k.poikilies_details:
                                                target_k.poikilies_details.remove(p)

                        fallback_known_age = zeroed_age or inherited_age

                        for item in updates['poikilies_multi']:
                            v_name = item.get('onoma')
                            v_diff = item.get('arithmos', 0)
                            v_age = item.get('ilikia')
                            if replace_all_flag and (v_diff is None or v_diff == 0) and len(updates['poikilies_multi']) == 1 and prev_total_trees > 0:
                                v_diff = prev_total_trees
                            if v_name and v_diff != 0:
                                req_p_norm = normalize_str(v_name)
                                effective_age = v_age if _is_known_age(v_age) else (age_by_variety.get(req_p_norm) or fallback_known_age or v_age or target_k.ilikia_dentron)
                                req_age_norm = normalize_str(v_age) if _is_known_age(v_age) else ""
                                if v_diff > 0:
                                    found = False
                                    for p in target_k.poikilies_details:
                                        if p.arithmos_dentron <= 0:
                                            continue
                                        if normalize_str(p.poikilia_onoma) == req_p_norm:
                                            if req_age_norm and _is_known_age(p.ilikia_dentron) and normalize_str(p.ilikia_dentron) != req_age_norm:
                                                continue
                                            p.arithmos_dentron += v_diff
                                            if not _is_known_age(p.ilikia_dentron) and _is_known_age(effective_age):
                                                p.ilikia_dentron = effective_age
                                            found = True
                                            break
                                    if not found:
                                        from models import KtimaPoikilia
                                        neo_p = KtimaPoikilia(ktima_id=target_k.id, poikilia_onoma=v_name, arithmos_dentron=v_diff, ilikia_dentron=effective_age)
                                        vasi.session.add(neo_p)
                                        target_k.poikilies_details.append(neo_p)
                                else:
                                    ypoloipo = abs(v_diff)
                                    for p in list(target_k.poikilies_details):
                                        if normalize_str(p.poikilia_onoma) == req_p_norm:
                                            if req_age_norm and _is_known_age(p.ilikia_dentron) and normalize_str(p.ilikia_dentron) != req_age_norm:
                                                continue
                                            if p.arithmos_dentron > ypoloipo:
                                                p.arithmos_dentron -= ypoloipo
                                                ypoloipo = 0
                                                break
                                            else:
                                                if _is_known_age(p.ilikia_dentron) and not zeroed_age:
                                                    zeroed_age = p.ilikia_dentron
                                                    fallback_known_age = zeroed_age or inherited_age
                                                ypoloipo -= p.arithmos_dentron
                                                p.arithmos_dentron = 0
                                                vasi.session.delete(p)
                        vasi.session.flush()
                        
                        energes_poikilies = [p for p in target_k.poikilies_details if p.arithmos_dentron > 0]
                        for p in energes_poikilies:
                            if not _is_known_age(p.ilikia_dentron) and _is_known_age(fallback_known_age):
                                p.ilikia_dentron = fallback_known_age
                        if not _is_known_age(target_k.ilikia_dentron) and _is_known_age(fallback_known_age):
                            target_k.ilikia_dentron = fallback_known_age
                        elif len(energes_poikilies) == 1 and _is_known_age(energes_poikilies[0].ilikia_dentron) and not updates.get('ilikia_dentron'):
                            target_k.ilikia_dentron = energes_poikilies[0].ilikia_dentron
                        target_k.arithmos_dentron = sum(p.arithmos_dentron for p in energes_poikilies)
                        unique_p = list(set([p.poikilia_onoma for p in energes_poikilies]))
                        target_k.poikilia = 'Ανάμεικτο' if len(unique_p) > 1 else (unique_p[0] if unique_p else 'Δεν ορίστηκε')
                        updated_fields.append('Πολλαπλές Ποικιλίες (Δέντρα)')
                        tree_count_changed = True
                    except Exception as e:
                        vasi.session.rollback()
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
                    _track_target_ktima(target_k, is_all=(str(target_ktima_id).upper() == 'ALL'))
                    vasi.session.add(Diagnosi(ktima_id=target_k.id, apotelesma=f"⚙️ Ενημέρωση Προφίλ από AI: {', '.join(updated_fields)}", imerominia=datetime.now()))
                    target_k.teleftaia_enimerosi_ergasion = None
                    target_k.ai_sumvouli_date = None
                    target_k.ekkremis_erotisi_ai = None

        if action in ['UPDATE_TASKS', 'UPDATE_TASK', 'MULTI_ACTION']:
            upd_list = data.get('tasks_to_update', [])
            if not upd_list and action != 'MULTI_ACTION':
                root_new_data = dict(data.get('new_task_data')) if isinstance(data.get('new_task_data'), dict) else {}
                if not root_new_data.get('status') and data.get('status'):
                    root_new_data['status'] = data.get('status')
                if not root_new_data.get('date') and (data.get('date') or data.get('task_date')):
                    root_new_data['date'] = data.get('date') or data.get('task_date')
                if not root_new_data.get('task_materials') and data.get('task_materials'):
                    root_new_data['task_materials'] = data.get('task_materials')
                if not root_new_data.get('lipasma_typos') and data.get('lipasma_typos'):
                    root_new_data['lipasma_typos'] = data.get('lipasma_typos')
                if root_new_data.get('posotita') is None and data.get('posotita') is not None:
                    root_new_data['posotita'] = data.get('posotita')
                if not root_new_data.get('task_name') and data.get('new_task_name'):
                    root_new_data['task_name'] = data.get('new_task_name')

                if data.get('task_name') and root_new_data:
                    upd_list = [{'target_ktima_id': target_ktima_id, 'task_name': data.get('task_name'), 'new_task_data': root_new_data}]
                elif isinstance(data.get('tasks'), list) and data.get('tasks'):
                    upd_list = []
                    for t_item in data.get('tasks'):
                        if isinstance(t_item, dict) and t_item.get('task_name'):
                            upd_list.append({
                                'target_ktima_id': t_item.get('target_ktima_id') or target_ktima_id,
                                'task_name': t_item.get('task_name'),
                                'new_task_data': {
                                    'status': t_item.get('status') or root_new_data.get('status'),
                                    'date': t_item.get('date') or t_item.get('task_date') or root_new_data.get('date'),
                                    'task_materials': t_item.get('task_materials') or root_new_data.get('task_materials'),
                                    'lipasma_typos': t_item.get('lipasma_typos') or root_new_data.get('lipasma_typos'),
                                    'posotita': t_item.get('posotita') if t_item.get('posotita') is not None else root_new_data.get('posotita')
                                }
                            })
                
            total_updated_tasks = 0
            had_update_attempt = bool(upd_list)
            for upd_item in upd_list:
                t_name = upd_item.get('task_name', '')
                t_k_id = upd_item.get('target_ktima_id') or target_ktima_id
                raw_new_data = upd_item.get('new_task_data')
                new_data = dict(raw_new_data) if isinstance(raw_new_data, dict) else {}
                if not new_data.get('status') and (upd_item.get('status') or data.get('status')):
                    new_data['status'] = upd_item.get('status') or data.get('status')
                if not new_data.get('date') and (upd_item.get('date') or upd_item.get('task_date') or data.get('date') or data.get('task_date')):
                    new_data['date'] = upd_item.get('date') or upd_item.get('task_date') or data.get('date') or data.get('task_date')
                if not new_data.get('task_materials') and (upd_item.get('task_materials') or data.get('task_materials')):
                    new_data['task_materials'] = upd_item.get('task_materials') or data.get('task_materials')
                if not new_data.get('lipasma_typos') and (upd_item.get('lipasma_typos') or data.get('lipasma_typos')):
                    new_data['lipasma_typos'] = upd_item.get('lipasma_typos') or data.get('lipasma_typos')
                if new_data.get('posotita') is None and (upd_item.get('posotita') is not None or data.get('posotita') is not None):
                    new_data['posotita'] = upd_item.get('posotita') if upd_item.get('posotita') is not None else data.get('posotita')
                if not new_data.get('task_name') and (upd_item.get('new_task_name') or data.get('new_task_name')):
                    new_data['task_name'] = upd_item.get('new_task_name') or data.get('new_task_name')
                
                upd_targets = []
                if str(t_k_id).upper() == 'ALL' and explicit_all_requested:
                    upd_targets = energa_ktimata
                else:
                    resolved_t_k, _ = _resolve_single_ktima(t_k_id, fallback_ktima=ktima)
                    if resolved_t_k:
                        upd_targets.append(resolved_t_k)
                        if not ktima:
                            ktima = resolved_t_k
                            target_ktima_id = resolved_t_k.id
                        
                for target_k in upd_targets:
                    if t_name == 'ΟΛΕΣ':
                        tasks_to_update = Ergasia.query.filter_by(ktima_id=target_k.id, katastasi='Εκκρεμεί').all()
                        for t in tasks_to_update:
                            if new_data.get('status'): t.katastasi = new_data['status']
                            if new_data.get('date'):
                                try: t.imerominia = datetime.strptime(new_data['date'], '%Y-%m-%d')
                                except: pass
                        if tasks_to_update:
                            total_updated_tasks += len(tasks_to_update)
                            _track_target_ktima(target_k, is_all=(str(t_k_id).upper() == 'ALL' and explicit_all_requested))
                            vasi.session.add(Diagnosi(ktima_id=target_k.id, apotelesma="✏️ AI Γραμματέας: Μαζική ενημέρωση εκκρεμών εργασιών.", imerominia=datetime.now()))
                    elif t_name:
                        tasks_to_check = Ergasia.query.filter_by(ktima_id=target_k.id).order_by(Ergasia.imerominia.desc()).all()
                        task_to_edit = None
                        
                        search_term = t_name.lower()
                        search_norm = _norm_gr(search_term)
                        for t in tasks_to_check:
                            eidos = (t.eidos_ergasias or "").lower()
                            farmaka = (t.farmaka_lipasmata or "").lower()
                            eidos_norm = _norm_gr(eidos)
                            farmaka_norm = _norm_gr(farmaka)
                            if search_term in eidos or search_term in farmaka or (search_norm and (search_norm in eidos_norm or search_norm in farmaka_norm)):
                                task_to_edit = t
                                break
                            else:
                                words = [w for w in search_term.split() if len(w) > 3]
                                match_found = False
                                for w in words:
                                    w_norm = _norm_gr(w)
                                    if w in eidos or w in farmaka or (w_norm and (w_norm in eidos_norm or w_norm in farmaka_norm)):
                                        task_to_edit = t
                                        match_found = True
                                        break
                                if match_found: break
                                
                        if task_to_edit:
                            updated_fields = []
                            if new_data.get('date'):
                                try: 
                                    task_to_edit.imerominia = datetime.strptime(new_data['date'], '%Y-%m-%d')
                                    updated_fields.append("Ημερομηνία")
                                except: pass
                            if new_data.get('task_name'):
                                task_to_edit.eidos_ergasias = new_data['task_name']
                                updated_fields.append("Όνομα")
                            if new_data.get('task_materials'):
                                task_to_edit.farmaka_lipasmata = new_data['task_materials']
                                updated_fields.append("Υλικά")

                            upd_combined_text = f"{new_data.get('task_name') or task_to_edit.eidos_ergasias or ''} {new_data.get('task_materials') or ''}"
                            raw_upd_lip = new_data.get('lipasma_typos')
                            upd_lip_val = str(raw_upd_lip).strip()[:50] if raw_upd_lip and str(raw_upd_lip).strip().lower() not in ['null', 'none', ''] else None
                            if not upd_lip_val and new_data.get('task_materials'):
                                npk_m = re.search(r'\b(\d{1,2}\s*[-.,]\s*\d{1,2}\s*[-.,]\s*\d{1,2}(?:\s*\+\s*[\w\d.,]+)?)\b', upd_combined_text)
                                if npk_m:
                                    upd_lip_val = re.sub(r'\s+', '', npk_m.group(1)).replace(',', '.')[:50]
                            if upd_lip_val:
                                task_to_edit.lipasma_typos = upd_lip_val
                                if not task_to_edit.farmaka_lipasmata:
                                    task_to_edit.farmaka_lipasmata = f"Λίπασμα {upd_lip_val}"
                                elif upd_lip_val not in task_to_edit.farmaka_lipasmata:
                                    task_to_edit.farmaka_lipasmata = f"{task_to_edit.farmaka_lipasmata} ({upd_lip_val})".strip()[:255]
                                updated_fields.append(f"Λίπασμα ({upd_lip_val})")

                            raw_upd_pos = new_data.get('posotita')
                            upd_pos_val = None
                            if raw_upd_pos is not None and str(raw_upd_pos).strip().lower() not in ['null', 'none', '']:
                                try:
                                    upd_pos_val = float(str(raw_upd_pos).replace(',', '.'))
                                except (ValueError, TypeError):
                                    upd_pos_val = None
                            if upd_pos_val is None and new_data.get('task_materials'):
                                is_fert_ctx = bool(upd_lip_val or task_to_edit.lipasma_typos) or any(k in _norm_gr(upd_combined_text) for k in ('λιπανσ', 'λιπασμ', 'npk', 'αζωτ', 'καλι', 'φωσφορ', 'βορι', 'ουρι', 'αμμωνι'))
                                if is_fert_ctx:
                                    kg_m = re.search(r'(\d+(?:[.,]\d+)?)\s*(?:κιλ[αάώω]?|kg|kgr)\b', upd_combined_text, flags=re.IGNORECASE)
                                    if kg_m:
                                        try:
                                            upd_pos_val = float(kg_m.group(1).replace(',', '.'))
                                        except (ValueError, TypeError):
                                            upd_pos_val = None
                            if upd_pos_val is not None:
                                task_to_edit.posotita = upd_pos_val
                                if not task_to_edit.farmaka_lipasmata:
                                    task_to_edit.farmaka_lipasmata = f"{upd_pos_val:g} κιλά"
                                elif f"{upd_pos_val:g}" not in task_to_edit.farmaka_lipasmata and 'κιλ' not in task_to_edit.farmaka_lipasmata.lower() and 'kg' not in task_to_edit.farmaka_lipasmata.lower():
                                    task_to_edit.farmaka_lipasmata = f"{task_to_edit.farmaka_lipasmata} ({upd_pos_val:g} κιλά)".strip()[:255]
                                updated_fields.append(f"Ποσότητα ({upd_pos_val:g} kg)")

                            if new_data.get('status'):
                                task_to_edit.katastasi = new_data['status']
                                updated_fields.append(f"Κατάσταση ({new_data['status']})")
                                
                            if updated_fields:
                                total_updated_tasks += 1
                                _track_target_ktima(target_k, is_all=(str(t_k_id).upper() == 'ALL' and explicit_all_requested))
                                vasi.session.add(Diagnosi(ktima_id=target_k.id, apotelesma=f"✏️ AI Γραμματέας: Ενημέρωση '{task_to_edit.eidos_ergasias}' ({', '.join(updated_fields)}).", imerominia=datetime.now()))
                    
                    target_k.ekkremis_erotisi_ai = None

            if action in ['UPDATE_TASKS', 'UPDATE_TASK'] and (not had_update_attempt or total_updated_tasks == 0):
                reply_text = "Δεν βρέθηκε αντίστοιχη εργασία για ενημέρωση."

        elif action == 'ADD_EXPENSE':
            poso = data.get('expense_amount')
            perigrafi = data.get('expense_desc', 'Νέο Έξοδο (Από AI)')
            
            resolved_exp_k, _ = _resolve_single_ktima(target_ktima_id, fallback_ktima=ktima)
            target_exp_obj = resolved_exp_k if resolved_exp_k else (energa_ktimata[0] if len(energa_ktimata) == 1 else None)
            k_id_to_charge = target_exp_obj.id if target_exp_obj else None
                
            if k_id_to_charge and poso is not None:
                try:
                    poso = float(poso)
                    neo_exodo = Exodo(ktima_id=k_id_to_charge, perigrafi=perigrafi, poso=poso, imerominia=datetime.now())
                    vasi.session.add(neo_exodo)
                    _track_target_ktima(target_exp_obj)
                    vasi.session.add(Diagnosi(ktima_id=k_id_to_charge, apotelesma=f"💶 AI Γραμματέας: Προστέθηκε έξοδο '{perigrafi}' ({poso}€).", imerominia=datetime.now()))
                except (ValueError, TypeError): pass
        elif action == 'ADD_INCOME':
            poso = data.get('income_amount')
            perigrafi = data.get('income_desc', 'Νέο Έσοδο')
            
            resolved_inc_k, _ = _resolve_single_ktima(target_ktima_id, fallback_ktima=ktima)
            target_inc_obj = resolved_inc_k if resolved_inc_k else (energa_ktimata[0] if len(energa_ktimata) == 1 else None)
            k_id_to_charge = target_inc_obj.id if target_inc_obj else None
                
            if k_id_to_charge and poso is not None:
                try:
                    poso = float(poso)
                    # Αποθηκεύουμε το έσοδο ως αρνητικό έξοδο για να μειώσει το συνολικό κόστος
                    neo_exodo = Exodo(ktima_id=k_id_to_charge, perigrafi=f"ΕΣΟΔΟ / ΕΠΙΔΟΤΗΣΗ: {perigrafi}", poso=-poso, imerominia=datetime.now())
                    vasi.session.add(neo_exodo)
                    _track_target_ktima(target_inc_obj)
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
            deleted_any_expense = False
            
            # Διορθώθηκε για να πιάνει και φράσεις όπως "σβήσε όλα τα έξοδα"
            if desc and ('ΟΛΑ' in str(desc).strip().upper() or 'ALL' in str(desc).strip().upper()):
                # Αλλαγή από bulk delete σε iterative delete για μεγαλύτερη ασφάλεια και συμβατότητα
                genika_exoda_list = GenikoExodo.query.filter_by(xrhsths_id=current_user.id).all()
                deleted_gen = len(genika_exoda_list)
                for ge in genika_exoda_list:
                    vasi.session.delete(ge)
                
                deleted_ex = 0
                target_ktimata = []
                if str(target_ktima_id).upper() == 'ALL':
                    target_ktimata = energa_ktimata
                else:
                    # Αν δεν έχει οριστεί target, αλλά υπάρχει ενεργό κτήμα, το βάζουμε
                    if ktima: 
                        target_ktimata.append(ktima)
                    
                for target_k in target_ktimata:
                    exoda_ktimatos_list = Exodo.query.filter_by(ktima_id=target_k.id, archived=False).all()
                    if exoda_ktimatos_list:
                        _track_target_ktima(target_k, is_all=(str(target_ktima_id).upper() == 'ALL'))
                    deleted_ex += len(exoda_ktimatos_list)
                    for ex in exoda_ktimatos_list:
                        vasi.session.delete(ex)
                
                if deleted_gen > 0 or deleted_ex > 0:
                    deleted_any_expense = True
                    k_id_diag = target_ktimata[0].id if target_ktimata else (energa_ktimata[0].id if energa_ktimata else None)
                    if k_id_diag:
                        vasi.session.add(Diagnosi(ktima_id=k_id_diag, apotelesma=f"🗑️ AI Γραμματέας: Μαζική διαγραφή εξόδων ({deleted_gen} γενικά, {deleted_ex} κτημάτων).", imerominia=datetime.now()))
                    
            elif desc or amount is not None:
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
                    deleted_any_expense = True
                else:
                    # 2. Αν δε βρεθεί, ψάχνουμε στα Έξοδα των Κτημάτων
                    user_ktima_ids = [k.id for k in energa_ktimata]
                    query_exodo = Exodo.query.filter(Exodo.archived == False, Exodo.ktima_id.in_(user_ktima_ids))
                    k_id_to_check = target_ktima_id if target_ktima_id and str(target_ktima_id).upper() != 'ALL' else (ktima.id if ktima else None)
                    if k_id_to_check:
                        try:
                            k_id_int = int(k_id_to_check)
                            if k_id_int in user_ktima_ids:
                                query_exodo = query_exodo.filter_by(ktima_id=k_id_int)
                            else:
                                query_exodo = query_exodo.filter(False)
                        except: pass
                    if amount is not None:
                        try: query_exodo = query_exodo.filter_by(poso=float(amount))
                        except: pass
                    if desc:
                        query_exodo = query_exodo.filter(Exodo.perigrafi.ilike(f"%{desc}%"))
                        
                    expense_to_delete = query_exodo.order_by(Exodo.imerominia.desc()).first()
                    if expense_to_delete:
                        exp_ktima_obj = next((k for k in energa_ktimata if k.id == expense_to_delete.ktima_id), None)
                        _track_target_ktima(exp_ktima_obj)
                        vasi.session.delete(expense_to_delete)
                        deleted_any_expense = True
                        vasi.session.add(Diagnosi(ktima_id=expense_to_delete.ktima_id, apotelesma=f"🗑️ AI Γραμματέας: Διαγράφηκε το έξοδο/έσοδο '{expense_to_delete.perigrafi}'.", imerominia=datetime.now()))

            if action == 'DELETE_EXPENSE' and not deleted_any_expense:
                reply_text = "Δεν βρέθηκε αντίστοιχο έξοδο ή έσοδο για διαγραφή."
                
        if action == 'UPDATE_EXPENSE':
            old_desc = data.get('expense_desc')
            old_amount = data.get('expense_amount')
            
            new_amount = data.get('new_expense_amount')
            new_desc = data.get('new_expense_desc')
            new_cat = data.get('geniko_katigoria')
            
            updated = False
            
            query_geniko = GenikoExodo.query.filter_by(xrhsths_id=current_user.id)
            if old_desc:
                query_geniko = query_geniko.filter(GenikoExodo.perigrafi.ilike(f"%{old_desc}%"))
            if old_amount is not None:
                try: query_geniko = query_geniko.filter_by(poso=float(old_amount))
                except: pass
                
            geniko_to_update = query_geniko.order_by(GenikoExodo.imerominia.desc()).first()
            if geniko_to_update:
                if new_amount is not None: geniko_to_update.poso = float(new_amount)
                if new_desc: geniko_to_update.perigrafi = new_desc
                if new_cat: geniko_to_update.katigoria = new_cat
                updated = True
                k_id_diag = target_ktima_id if target_ktima_id and str(target_ktima_id).upper() != 'ALL' else (ktima.id if ktima else (energa_ktimata[0].id if energa_ktimata else None))
                if k_id_diag:
                    vasi.session.add(Diagnosi(ktima_id=k_id_diag, apotelesma=f"✏️ AI Γραμματέας: Ενημερώθηκε το γενικό έξοδο/έσοδο.", imerominia=datetime.now()))
            else:
                user_ktima_ids = [k.id for k in energa_ktimata]
                query_exodo = Exodo.query.filter(Exodo.archived == False, Exodo.ktima_id.in_(user_ktima_ids))
                k_id_to_check = target_ktima_id if target_ktima_id and str(target_ktima_id).upper() != 'ALL' else (ktima.id if ktima else None)
                if k_id_to_check:
                    try:
                        k_id_int = int(k_id_to_check)
                        if k_id_int in user_ktima_ids:
                            query_exodo = query_exodo.filter_by(ktima_id=k_id_int)
                        else:
                            query_exodo = query_exodo.filter(False)
                    except: pass
                if old_desc:
                    query_exodo = query_exodo.filter(Exodo.perigrafi.ilike(f"%{old_desc}%"))
                if old_amount is not None:
                    try: query_exodo = query_exodo.filter_by(poso=float(old_amount))
                    except: pass
                    
                expense_to_update = query_exodo.order_by(Exodo.imerominia.desc()).first()
                if expense_to_update:
                    if new_amount is not None: expense_to_update.poso = float(new_amount)
                    if new_desc: expense_to_update.perigrafi = new_desc
                    if new_cat: expense_to_update.katigoria = new_cat
                    updated = True
                    exp_ktima_obj = next((k for k in energa_ktimata if k.id == expense_to_update.ktima_id), None)
                    _track_target_ktima(exp_ktima_obj)
                    vasi.session.add(Diagnosi(ktima_id=expense_to_update.ktima_id, apotelesma=f"✏️ AI Γραμματέας: Ενημερώθηκε το έξοδο/έσοδο κτήματος.", imerominia=datetime.now()))
            
            if not updated:
                reply_text = "Δεν μπόρεσα να βρω το έξοδο με αυτά τα στοιχεία για να το διορθώσω."

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
                _track_target_ktima(target_k, is_all=(str(target_ktima_id).upper() == 'ALL'))
                
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
            updated_inv = False
            if inv_name and inv_amount is not None:
                items = [i for i in current_user.apothiki_items if str(inv_name).lower() in i.onoma_proiontos.lower() or _norm_gr(inv_name) in _norm_gr(i.onoma_proiontos)]
                if items:
                    for item in items: item.posotita = float(inv_amount)
                    updated_inv = True
                    if ktima: vasi.session.add(Diagnosi(ktima_id=ktima.id, apotelesma=f"📦 AI Αποθήκη: Διορθώθηκε το απόθεμα του '{inv_name}' σε {inv_amount}.", imerominia=datetime.now()))
            if not updated_inv:
                reply_text = "Δεν βρέθηκε αντίστοιχο προϊόν στην αποθήκη για ενημέρωση."
                    
        if action == 'DELETE_INVENTORY':
            inv_name = data.get('inv_name')
            deleted_inv = False
            if inv_name:
                items = [i for i in current_user.apothiki_items if str(inv_name).lower() in i.onoma_proiontos.lower() or _norm_gr(inv_name) in _norm_gr(i.onoma_proiontos)]
                if items:
                    for item in items:
                        vasi.session.delete(item)
                    deleted_inv = True
                    if ktima: vasi.session.add(Diagnosi(ktima_id=ktima.id, apotelesma=f"📦 AI Αποθήκη: Διαγράφηκε το '{inv_name}'.", imerominia=datetime.now()))
            if not deleted_inv:
                reply_text = "Δεν βρέθηκε αντίστοιχο προϊόν στην αποθήκη για διαγραφή."
                
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
                    _track_target_ktima(target_k, is_all=(str(target_ktima_id).upper() == 'ALL'))
                    water_prefix = "💧 Ανάλυση Νερού" if (ph is not None or ec is not None) else "💧 AI Γραμματέας: Ενημέρωση"
                    vasi.session.add(Diagnosi(ktima_id=target_k.id, apotelesma=f"{water_prefix} ({', '.join(updates)}).", imerominia=datetime.now()))
                    target_k.teleftaia_enimerosi_ergasion = None
                    target_k.ai_sumvouli_date = None
                    target_k.ekkremis_erotisi_ai = None

        if action == 'DELETE_UGRASIA':
            moisture_val = data.get('moisture_percentage')
            target_ktimata = []
            if str(target_ktima_id).upper() == 'ALL' and explicit_all_requested:
                target_ktimata = [k for k in energa_ktimata if k.idioktitis == current_user]
            else:
                resolved_u_k, _ = _resolve_single_ktima(target_ktima_id, fallback_ktima=ktima)
                if resolved_u_k and resolved_u_k.idioktitis == current_user:
                    target_ktimata.append(resolved_u_k)
                    if not ktima:
                        ktima = resolved_u_k
                        target_ktima_id = resolved_u_k.id

            deleted_ugrasia_count = 0
            for target_k in target_ktimata:
                if target_k.idioktitis != current_user:
                    continue
                query_u = KatagrafiUgrasias.query.filter_by(ktima_id=target_k.id).order_by(KatagrafiUgrasias.imerominia.desc())
                record_to_del = None
                if moisture_val is not None and str(moisture_val).strip().lower() not in ['null', 'none', '']:
                    try:
                        m_float = float(str(moisture_val).replace(',', '.'))
                        for u_rec in query_u.all():
                            if abs((u_rec.pososto or 0.0) - m_float) < 0.01:
                                record_to_del = u_rec
                                break
                    except (ValueError, TypeError):
                        pass
                else:
                    record_to_del = query_u.first()

                if record_to_del:
                    del_pososto = record_to_del.pososto
                    vasi.session.delete(record_to_del)
                    deleted_ugrasia_count += 1
                    _track_target_ktima(target_k, is_all=(str(target_ktima_id).upper() == 'ALL' and explicit_all_requested))
                    vasi.session.add(Diagnosi(ktima_id=target_k.id, apotelesma=f"🗑️ AI Γραμματέας: Διαγράφηκε η καταγραφή υγρασίας ({del_pososto}%).", imerominia=datetime.now()))
                    target_k.teleftaia_enimerosi_ergasion = None
                    target_k.ai_sumvouli_date = None
                    target_k.ekkremis_erotisi_ai = None

            if deleted_ugrasia_count == 0:
                reply_text = "Δεν βρέθηκε αντίστοιχη καταγραφή υγρασίας για διαγραφή."

        if action in ['ADD_KTIMA', 'MULTI_ACTION']:
            nk_data = data.get('new_ktima_data')
            if nk_data and nk_data.get('onoma_ktimatos'):
                try:
                    onoma = nk_data.get('onoma_ktimatos')
                    upd_fallback = data.get('updates') if isinstance(data.get('updates'), dict) else {}

                    def _pick_ktima_field(field_name, default_val=None):
                        val = nk_data.get(field_name)
                        if val is None or str(val).strip().lower() in ['null', 'none', '']:
                            val = upd_fallback.get(field_name)
                        if val is None or str(val).strip().lower() in ['null', 'none', '']:
                            return default_val
                        return val

                    lat_val = 37.9838 # Προεπιλογή: Αθήνα
                    lng_val = 23.7275 # Προεπιλογή: Αθήνα
                    raw_lat = _pick_ktima_field('geografiko_platos')
                    raw_lng = _pick_ktima_field('geografiko_mikos')
                    has_custom_coords = False
                    if raw_lat is not None and raw_lng is not None:
                        try:
                            lat_val = float(str(raw_lat).replace(',', '.'))
                            lng_val = float(str(raw_lng).replace(',', '.'))
                            if abs(lat_val - 37.9838) > 1e-4 or abs(lng_val - 23.7275) > 1e-4:
                                has_custom_coords = True
                        except (ValueError, TypeError):
                            lat_val, lng_val = 37.9838, 23.7275

                    stremmata_val = 0.0
                    raw_str = _pick_ktima_field('stremmata')
                    if raw_str is not None:
                        try:
                            stremmata_val = float(str(raw_str).replace(',', '.'))
                        except (ValueError, TypeError):
                            stremmata_val = 0.0

                    typos_edafous_val = _pick_ktima_field('typos_edafous')
                    klisi_val = _pick_ktima_field('klisi')
                    ardefsi_val = _pick_ktima_field('ardefsi')
                    kalliergeia_val = _pick_ktima_field('kalliergeia_typos', 'Συμβατική')
                    puknotita_val = _pick_ktima_field('puknotita_dentron', 'Κανονική')
                    diacheirisi_val = _pick_ktima_field('diacheirisi_edafous', 'Άγνωστη')
                    ilikia_val = _pick_ktima_field('ilikia_dentron', 'Άγνωστη')
                    stadio_val = _pick_ktima_field('fainologiko_stadio', 'Άγνωστο')

                    neo_ktima = Ktima(
                        onoma_ktimatos=onoma,
                        geografiko_mikos=lng_val,
                        geografiko_platos=lat_val,
                        idioktitis=current_user,
                        stremmata=stremmata_val,
                        typos_edafous=typos_edafous_val,
                        klisi=klisi_val,
                        ardefsi=ardefsi_val,
                        kalliergeia_typos=kalliergeia_val,
                        puknotita_dentron=puknotita_val,
                        diacheirisi_edafous=diacheirisi_val,
                        ilikia_dentron=ilikia_val,
                        fainologiko_stadio=stadio_val
                    )

                    # Ασφαλής υπολογισμός υψομέτρου και αρχικού GDD με βάση τις συντεταγμένες
                    try:
                        from geoponika import pare_ypsometro, gdd_ytd
                        yps_val = pare_ypsometro(lat_val, lng_val)
                        if yps_val is not None:
                            neo_ktima.ypsometro = yps_val
                        if has_custom_coords:
                            init_gdd = gdd_ytd(lat_val, lng_val, timeout=5)
                            if init_gdd is not None:
                                neo_ktima.gdd_accumulated = init_gdd
                    except Exception as geo_e:
                        print(f"Σφάλμα υπολογισμού υψομέτρου/GDD στο ADD_KTIMA: {geo_e}")

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
                                neo_p = KtimaPoikilia(ktima_id=neo_ktima.id, poikilia_onoma=p_onoma, arithmos_dentron=p_arithmos, ilikia_dentron=p.get('ilikia') or ilikia_val or 'Άγνωστη')
                                vasi.session.add(neo_p)
                                neo_ktima.poikilies_details.append(neo_p)
                                total_trees += p_arithmos
                                valid_varieties.append(p_onoma)
                        neo_ktima.arithmos_dentron = total_trees
                        neo_ktima.poikilia = 'Ανάμεικτο' if len(set(valid_varieties)) > 1 else (valid_varieties[0] if valid_varieties else 'Δεν ορίστηκε')
                    else:
                        raw_trees = _pick_ktima_field('arithmos_dentron', 0)
                        try:
                            neo_ktima.arithmos_dentron = int(raw_trees or 0)
                        except (ValueError, TypeError):
                            neo_ktima.arithmos_dentron = 0
                        neo_ktima.poikilia = _pick_ktima_field('poikilia', 'Δεν ορίστηκε')
                        neo_ktima.ilikia_dentron = ilikia_val or 'Άγνωστη'
                        if neo_ktima.arithmos_dentron > 0 and neo_ktima.poikilia != 'Δεν ορίστηκε':
                            from models import KtimaPoikilia
                            vasi.session.add(KtimaPoikilia(ktima_id=neo_ktima.id, poikilia_onoma=neo_ktima.poikilia, arithmos_dentron=neo_ktima.arithmos_dentron, ilikia_dentron=neo_ktima.ilikia_dentron))

                    # Ρύθμιση στόχων GDD βάσει ποικιλίας (όπως και στη φόρμα προσθήκης κτήματος)
                    gdd_map = {
                        'Κορωνέικη': (550, 2400), 'Αθηνολιά': (500, 2300), 'Αθηνοελιά': (500, 2300),
                        'Καλαμών': (680, 2600), 'Χονδρολιά': (680, 2600), 'Χαλκιδικής': (620, 2500),
                        'Μεγαρίτικη': (600, 2450), 'Μανάκι': (600, 2500), 'Αρμπεκίνα': (550, 2400)
                    }
                    for var_k, (t_a, t_s) in gdd_map.items():
                        if neo_ktima.poikilia and var_k in neo_ktima.poikilia:
                            neo_ktima.gdd_target_anthisi = t_a
                            neo_ktima.gdd_target_sygkomidi = t_s
                            break
                            
                    vasi.session.add(Diagnosi(ktima_id=neo_ktima.id, apotelesma="🤖 AI Γραμματέας: Το κτήμα δημιουργήθηκε αυτόματα.", imerominia=datetime.now()))
                    data['new_ktima_id'] = neo_ktima.id
                except Exception as e:
                    vasi.session.rollback()
                    print(f"Σφάλμα δημιουργίας κτήματος AI: {e}")
                
        if action == 'DELETE_KTIMA':
            import requests
            target_ktimata = []
            if str(target_ktima_id).upper() == 'ALL':
                target_ktimata = energa_ktimata
            else:
                if ktima: target_ktimata.append(ktima)
                
            for target_k in target_ktimata:
                _track_target_ktima(target_k, is_all=(str(target_ktima_id).upper() == 'ALL'))
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
                _track_target_ktima(target_k, is_all=(str(target_ktima_id).upper() == 'ALL'))
                target_k.is_active = False
                vasi.session.add(Diagnosi(ktima_id=target_k.id, apotelesma=f"🗂️ AI Γραμματέας: Το κτήμα αρχειοθετήθηκε.", imerominia=datetime.now()))
                
        if action == 'ADD_ANALYSIS':
            analysis_data = data.get('new_analysis_data') or {}
            target_ktimata = energa_ktimata if str(target_ktima_id).upper() == 'ALL' else ([ktima] if ktima else [])
            
            for target_k in target_ktimata:
                _track_target_ktima(target_k, is_all=(str(target_ktima_id).upper() == 'ALL'))
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

        # --- ΡΗΤΗ ΕΝΔΕΙΞΗ ΚΤΗΜΑΤΟΣ ΣΤΟ ΜΗΝΥΜΑ ΑΠΑΝΤΗΣΗΣ ---
        ktima_scoped_actions = {
            'ADD_TASK', 'ADD_TASKS', 'UPDATE_TASKS', 'UPDATE_TASK', 'DELETE_TASKS',
            'UPDATE_KTIMA', 'ADD_EXPENSE', 'ADD_INCOME', 'DELETE_EXPENSE', 'UPDATE_EXPENSE',
            'ADD_HARVEST', 'UPDATE_WATER', 'DELETE_UGRASIA', 'ADD_ANALYSIS', 'ARCHIVE_KTIMA', 'DELETE_KTIMA', 'MULTI_ACTION'
        }
        if action in ktima_scoped_actions and (all_ktimata_targeted or executed_ktima_names):
            if all_ktimata_targeted:
                if not any(w in _norm_gr(reply_text) for w in ('ολα τα κτηματα', 'σε ολα')):
                    reply_text = f"📍 [Όλα τα κτήματα] {reply_text}"
            else:
                missing_names = [n for n in executed_ktima_names if _norm_gr(n) not in _norm_gr(reply_text)]
                if missing_names:
                    label = ', '.join(executed_ktima_names)
                    reply_text = f"📍 [Κτήμα: {label}] {reply_text}"
            
        # --- ΕΝΗΜΕΡΩΣΗ ΜΝΗΜΗΣ ΣΤΗ ΒΑΣΗ ΔΕΔΟΜΕΝΩΝ ---
        try:
            history = json.loads(history_str)
            if not isinstance(history, list): history = []
        except:
            history = []
            
        history.append({"role": "model", "content": reply_text})
        if len(history) > 25: # Κρατάμε τα τελευταία 25 μηνύματα για πλήρες context
            history = history[-25:]
            
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
        vasi.session.rollback()
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