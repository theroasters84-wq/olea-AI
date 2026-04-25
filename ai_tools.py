import os
import json
import time
import io
import requests
import PIL.Image
from datetime import datetime, timedelta
from flask import Blueprint, request, jsonify, flash, redirect, url_for
from flask_login import login_required, current_user
from core import vasi, ai_client, api_key_ai
from models import Ktima, Diagnosi, AnalysiEdafous, Ergasia, Syntagh
from geoponika import pare_simvouli_ai
from google import genai
from google.genai import types

ai_bp = Blueprint('ai', __name__)

@ai_bp.route('/rwta_ai/<int:ktima_id>', methods=['POST'])
@login_required
def rwta_ai(ktima_id):
    if not api_key_ai:
        return jsonify({'apantisi': "Σφάλμα Ρύθμισης: Το AI API Key λείπει από τον server."})

    ktima = vasi.session.get(Ktima, ktima_id)
    if not ktima or ktima.idioktitis != current_user:
        return jsonify({'apantisi': "Μη εξουσιοδοτημένη πρόσβαση."}), 403

    data = request.get_json()
    thermokrasia = data.get('thermokrasia')
    ygrasia = data.get('ygrasia')
    perigrafi = data.get('perigrafi')
    
    now = datetime.now()
    if ktima.ai_sumvouli_cache and ktima.ai_sumvouli_date:
        if (now - ktima.ai_sumvouli_date).total_seconds() < 21600:
            return jsonify({'apantisi': ktima.ai_sumvouli_cache + " (Αποθηκευμένη)"})

    # ΟΛΙΚΗ ΕΝΣΩΜΑΤΩΣΗ ΔΕΔΟΜΕΝΩΝ ΓΙΑ ΤΟ CHAT
    from logic import xtise_plires_context
    plires_context = xtise_plires_context(ktima)
    
    full_prompt = f"{plires_context}\n\nΕΡΩΤΗΣΗ/ΣΥΝΘΗΚΕΣ ΑΠΟ ΧΡΗΣΤΗ: Το AI ενημερώνεται για τον καιρό ({thermokrasia}°C, {ygrasia}%). Επιπλέον σχόλιο: {data.get('perigrafi', '')}"
    apantisi = pare_simvouli_ai(thermokrasia, ygrasia, full_prompt)
    
    apantisi += "\n\n⚠️ Σημαντικό: Οι παραπάνω συμβουλές είναι αυτοματοποιημένες και ενδέχεται να μην είναι κατάλληλες για κάθε περίπτωση. Συμβουλευτείτε έναν ειδικό γεωπόνο πριν προβείτε σε οποιαδήποτε ενέργεια."
    
    if not apantisi:
        apantisi = "Το σύστημα AI είναι προσωρινά μη διαθέσιμο. Δοκιμάστε ξανά σε λίγο."
    elif "μη διαθέσιμο" not in apantisi:
        ktima.ai_sumvouli_cache = apantisi
        ktima.ai_sumvouli_date = now
        vasi.session.commit()
        
    return jsonify({'apantisi': apantisi})

@ai_bp.route('/diagnosi_fwtografias/<int:ktima_id>', methods=['POST'])
@login_required
def diagnosi_fwtografias(ktima_id):
    if not api_key_ai:
        flash("Η λειτουργία AI είναι απενεργοποιημένη. Λείπει το API Key από τον server.", "danger")
        return redirect(url_for('core_app.arxikh'))

    ktima = vasi.session.get(Ktima, ktima_id)
    if not ktima or ktima.idioktitis != current_user:
        return "Μη εξουσιοδοτημένη ενέργεια", 403
    
    if 'fwtografia' not in request.files:
        flash('Δεν βρέθηκε αρχείο φωτογραφίας.', 'danger')
        return redirect(url_for('core_app.arxikh'))
    
    file = request.files['fwtografia']
    if file.filename == '':
        flash('Δεν επιλέχθηκε αρχείο.', 'danger')
        return redirect(url_for('core_app.arxikh'))
        
    if file:
        try:
            img = PIL.Image.open(file)
            
            # Δραστική συμπίεση εικόνας
            img.thumbnail((1024, 1024), PIL.Image.Resampling.LANCZOS)
            if img.mode in ('RGBA', 'P'):
                img = img.convert('RGB')
            img_byte_arr = io.BytesIO()
            img.save(img_byte_arr, format='JPEG', quality=75)
            img_part = types.Part.from_bytes(data=img_byte_arr.getvalue(), mime_type='image/jpeg')
            
            from logic import xtise_plires_context
            context = xtise_plires_context(ktima)
            
            prompt = f"Είσαι γεωπόνος. Αυτά είναι τα δεδομένα του κτήματος:\n{context}\n\nΟΔΗΓΙΑ: Ανάλυσε αυτή τη φωτογραφία (φύλλα, καρπός, κορμός Ή ευρεία λήψη). Εντόπισε πιθανές ασθένειες ή τροφοπενίες στα δέντρα ΛΑΜΒΑΝΟΝΤΑΣ ΥΠΟΨΗ τον καιρό και το ιστορικό του κτήματος! ΓΕΩΡΓΙΑ ΑΚΡΙΒΕΙΑΣ: Αν στη φωτογραφία φαίνονται ΠΟΛΛΑ δέντρα, ΔΙΑΧΩΡΙΣΕ ΤΗΝ ΚΑΤΑΣΤΑΣΗ ΤΟΥΣ στην απάντησή σου. ΑΝ η φωτογραφία εστιάζει στο χώμα, αξιολόγησε την κάλυψη χόρτων ΚΑΙ εκτίμησε τον τύπο εδάφους (π.χ. Αργιλώδες, Κοκκινόχωμα). Δώσε σύντομη και ξεκάθαρη διάγνωση."
            
            response = None
            for attempt in range(3):
                try:
                    response = ai_client.models.generate_content(model='gemini-2.5-flash', contents=[prompt, img_part])
                    break
                except Exception:
                    time.sleep(2)
            
            apotelesma_text = response.text if response else "⚠️ Δεν κατάφερα να διακρίνω καθαρά τη φωτογραφία. Δοκιμάστε μια πιο καθαρή λήψη."
            nea_diagnosi = Diagnosi(ktima_id=ktima_id, apotelesma=apotelesma_text, imerominia=datetime.now())
            vasi.session.add(nea_diagnosi)
            ktima.teleftaia_enimerosi_ergasion = None
            ktima.ekkremis_erotisi_ai = None
            ktima.ai_sumvouli_date = None
            vasi.session.commit()
            flash('Η διάγνωση ολοκληρώθηκε επιτυχώς!', 'success')
        except Exception as e:
            error_msg = str(e).lower()
            if '429' in error_msg or 'quota' in error_msg or '413' in error_msg or 'too large' in error_msg:
                flash('⚠️ Η φωτογραφία είναι πολύ μεγάλη ή στείλατε πολλές. Δοκιμάστε με μικρότερο αρχείο.', 'warning')
            else:
                flash('⚠️ Δεν κατάφερα να διακρίνω τη φωτογραφία. Δοκιμάστε ξανά.', 'danger')
            
    return redirect(url_for('core_app.arxikh'))

@ai_bp.route('/analysi_egrafou/<int:ktima_id>', methods=['POST'])
@login_required
def analysi_egrafou(ktima_id):
    if not api_key_ai:
        return jsonify({'success': False, 'message': 'Η λειτουργία AI είναι απενεργοποιημένη.'})

    ktima = vasi.session.get(Ktima, ktima_id)
    if not ktima or ktima.idioktitis != current_user:
        return jsonify({'success': False, 'message': 'Μη εξουσιοδοτημένη πρόσβαση.'}), 403

    files = request.files.getlist('fwtografia_analysis')
    valid_files = [f for f in files if f.filename != '']
    
    if not valid_files:
        return jsonify({'success': False, 'message': 'Δεν επιλέχθηκε αρχείο.'})

    try:
        prompt = "Είσαι γεωπόνος. Διάβασε αυτά τα έγγραφα ανάλυσης εδάφους/φύλλων. Συνδύασε τις πληροφορίες τους και δώσε ένα συνοπτικό συμπέρασμα για την κατάσταση του εδάφους/φυτού."
        contents = [prompt]
        
        for file in valid_files:
            mime_type = file.mimetype
            file_data = file.read()
            
            if 'pdf' in mime_type:
                contents.append(types.Part.from_bytes(data=file_data, mime_type='application/pdf'))
            else:
                img = PIL.Image.open(io.BytesIO(file_data))
                # Δραστική συμπίεση εικόνας (JPEG Bytes)
                img.thumbnail((1024, 1024), PIL.Image.Resampling.LANCZOS)
                if img.mode in ('RGBA', 'P'):
                    img = img.convert('RGB')
                img_byte_arr = io.BytesIO()
                img.save(img_byte_arr, format='JPEG', quality=75)
                contents.append(types.Part.from_bytes(data=img_byte_arr.getvalue(), mime_type='image/jpeg'))
                
        response = None
        for attempt in range(3):
            try:
                response = ai_client.models.generate_content(model='gemini-2.5-flash', contents=contents)
                break
            except Exception as e:
                if attempt == 2: raise e
                time.sleep(3 * (attempt + 1))
        
        analysi_text = response.text if response else "⚠️ Δεν μπόρεσα να διαβάσω το έγγραφο. Ανεβάστε πιο καθαρή φωτογραφία."
        
        extraction_prompt = """Διάβασε την ανάλυση και εξήγαγε τα δεδομένα σε μορφή JSON. Επίστρεψε ΜΟΝΟ το JSON χωρίς άλλο κείμενο (ούτε markdown).
Περίλαβε τα εξής κλειδιά (με αριθμητικές τιμές) αν υπάρχουν: ph, organiki_ousia, azwto, fwsforos, kalio.
Επιπλέον, αν η ανάλυση αναφέρει τη μηχανική σύσταση / τύπο εδάφους (π.χ. Αργιλώδες, Αμμώδες, Πηλώδες, κτλ), πρόσθεσε και το κλειδί "typos_edafous" με την αντίστοιχη λέξη.
ΠΡΟΣΟΧΗ: Αν η εικόνα είναι πολύ θολή/δυσανάγνωστη, ή αν λείπουν βασικές σελίδες (π.χ. βλέπεις μόνο τη σελίδα 1 από 2), πρόσθεσε στο JSON ένα κλειδί "provlima" με ένα σύντομο μήνυμα προς τον χρήστη (π.χ. "Η φωτογραφία είναι πολύ θολή, παρακαλώ ανεβάστε την ξανά." ή "Φαίνεται να λείπει η δεύτερη σελίδα.")."""
        
        ext_response = ai_client.models.generate_content(model='gemini-2.5-flash', contents=[extraction_prompt] + contents[1:])
        
        if ext_response:
            try:
                json_text = ext_response.text.strip().replace('```json', '').replace('```', '').strip()
                start_idx = json_text.find('{')
                end_idx = json_text.rfind('}')
                if start_idx != -1 and end_idx != -1:
                    json_text = json_text[start_idx:end_idx+1]
                
                data = json.loads(json_text, strict=False)
                
                if data.get('provlima'):
                    return jsonify({'success': False, 'message': data.get('provlima')})
                    
                nea_analysi = AnalysiEdafous(ktima_id=ktima_id, **{k: v for k, v in data.items() if k in ['ph', 'organiki_ousia', 'azwto', 'fwsforos', 'kalio']})
                vasi.session.add(nea_analysi)
                
                typos = data.get('typos_edafous')
                if typos:
                    typos_lower = typos.lower()
                    if 'αργιλ' in typos_lower: ktima.typos_edafous = 'Αργιλώδες'
                    elif 'αμμ' in typos_lower: ktima.typos_edafous = 'Αμμώδες'
                    elif 'πηλ' in typos_lower: ktima.typos_edafous = 'Πηλώδες'
                    
                ktima.analysi_dedomena = analysi_text
                nea_diagnosi = Diagnosi(ktima_id=ktima.id, apotelesma=f"📄 Έγγραφο Ανάλυσης ({len(valid_files)} αρχεία): Ολοκληρώθηκε", imerominia=datetime.now())
                vasi.session.add(nea_diagnosi)
            except Exception as e:
                print(f"Σφάλμα JSON: {e}")

        ktima.ekkremis_erotisi_ai = None
        ktima.teleftaia_enimerosi_ergasion = None
        ktima.ai_sumvouli_date = None
        vasi.session.commit()
        return jsonify({'success': True, 'message': 'Η ανάλυση των εγγράφων ολοκληρώθηκε!'})
    except Exception as e:
        error_msg = str(e).lower()
        if '429' in error_msg or 'quota' in error_msg or '413' in error_msg or 'too large' in error_msg:
            return jsonify({'success': False, 'message': '⚠️ Ο όγκος των αρχείων είναι πολύ μεγάλος. Ανεβάστε λιγότερες ή μικρότερες σελίδες.'})
        return jsonify({'success': False, 'message': '⚠️ Δεν κατάφερα να διαβάσω την ανάλυση. Δοκιμάστε ξανά με πιο καθαρή φωτογραφία.'})

@ai_bp.route('/anagnorisi_stadiou/<int:ktima_id>', methods=['POST'])
@login_required
def anagnorisi_stadiou(ktima_id):
    ktima = vasi.session.get(Ktima, ktima_id)
    if not ktima or ktima.idioktitis != current_user:
        return "403", 403
    
    file = request.files.get('fwtografia_stadiou')
    if not file or file.filename == '':
        flash('Δεν επιλέχθηκε αρχείο.', 'danger')
        return redirect(url_for('core_app.arxikh'))

    try:
        img = PIL.Image.open(file)
        prompt = "Είσαι κορυφαίος γεωπόνος. Σε ποιο φαινολογικό στάδιο βρίσκεται η ελιά; Απάντησε ΜΟΝΟ με το όνομα του σταδίου (π.χ. Λήθαργος, Σχηματισμός Ταξιανθιών, Άνθιση, Καρπόδεση)."
        response = ai_client.models.generate_content(model='gemini-2.5-flash', contents=[prompt, img])
        ktima.fainologiko_stadio = response.text.strip().replace('.', '') if response else "Άγνωστο"
        
        if response:
            nea_diagnosi = Diagnosi(ktima_id=ktima.id, apotelesma=f"🌿 Αναγνώριση Σταδίου: {ktima.fainologiko_stadio}", imerominia=datetime.now())
            vasi.session.add(nea_diagnosi)
            
        ktima.ekkremis_erotisi_ai = None
        ktima.teleftaia_enimerosi_ergasion = None
        ktima.ai_sumvouli_date = None
        vasi.session.commit()
        flash(f'Το AI αναγνώρισε το στάδιο: {ktima.fainologiko_stadio}', 'success')
    except Exception as e:
        error_msg = str(e).lower()
        if '429' in error_msg or 'quota' in error_msg or '413' in error_msg or 'too large' in error_msg:
            flash('⚠️ Η φωτογραφία είναι πολύ μεγάλη. Δοκιμάστε με μικρότερο αρχείο.', 'warning')
        else:
            flash('⚠️ Δεν κατάφερα να διακρίνω τη φωτογραφία. Ανεβάστε μια πιο καθαρή.', 'danger')
        
    return redirect(url_for('core_app.arxikh'))

@ai_bp.route('/ektimisi_paragogis/<int:ktima_id>', methods=['POST'])
@login_required
def ektimisi_paragogis(ktima_id):
    ktima = vasi.session.get(Ktima, ktima_id)
    if not ktima or ktima.idioktitis != current_user:
        return "403", 403
        
    file = request.files.get('fwtografia_paragogis')
    if not file or file.filename == '':
        flash('Δεν επιλέχθηκε αρχείο.', 'danger')
        return redirect(url_for('core_app.arxikh'))

    try:
        img = PIL.Image.open(file)
        poikilies = ", ".join([f"{p.poikilia_onoma}" for p in ktima.poikilies_details]) if ktima.poikilies_details else ktima.poikilia
        prompt = f"Είσαι ειδικός γεωπόνος. Εκτίμησε την παραγωγή για {ktima.arithmos_dentron} δέντρα ({poikilies}) βάσει αυτής της εικόνας καρποφορίας. Δώσε 1-2 προτάσεις."
        response = ai_client.models.generate_content(model='gemini-2.5-flash', contents=[prompt, img])
        flash(f'Εκτίμηση: {response.text}', 'info')
    except Exception as e:
        error_msg = str(e).lower()
        if '429' in error_msg or 'quota' in error_msg or '413' in error_msg or 'too large' in error_msg:
            flash('⚠️ Η φωτογραφία είναι πολύ μεγάλη.', 'warning')
        else:
            flash('⚠️ Δεν κατάφερα να διακρίνω τους καρπούς. Δοκιμάστε μια καλύτερη λήψη.', 'danger')
        
    return redirect(url_for('core_app.arxikh'))

@ai_bp.route('/ai_input_scan/<int:ktima_id>', methods=['POST'])
@login_required
def ai_input_scan(ktima_id):
    ktima = vasi.session.get(Ktima, ktima_id)
    if not ktima or ktima.idioktitis != current_user:
        return "403", 403
        
    file = request.files.get('fwtografia_etiketas')
    if not file or file.filename == '':
        flash('Δεν επιλέχθηκε αρχείο.', 'danger')
        return redirect(url_for('core_app.arxikh'))

    try:
        mime_type = file.mimetype
        file_data = file.read()
        prompt = "Είσαι γεωπόνος. Διάβασε την ετικέτα αυτού του φαρμάκου/λιπάσματος. Ποιο είναι το προϊόν, η δραστική ουσία και η δοσολογία;"
        
        if 'pdf' in mime_type:
            content_part = types.Part.from_bytes(data=file_data, mime_type='application/pdf')
        else:
            content_part = PIL.Image.open(io.BytesIO(file_data))
            
        response = ai_client.models.generate_content(model='gemini-2.5-flash', contents=[prompt, content_part])
        ai_summary = response.text.strip() if response else "⚠️ Δεν κατάφερα να διαβάσω την ετικέτα."
        
        nea_ergasia = Ergasia(ktima_id=ktima.id, eidos_ergasias='Ψεκασμός/Λίπανση (AI)', katastasi='Ολοκληρώθηκε', farmaka_lipasmata=ai_summary, imerominia=datetime.now())
        vasi.session.add(nea_ergasia)
        ktima.teleftaia_enimerosi_ergasion = None
        ktima.ekkremis_erotisi_ai = None
        ktima.ai_sumvouli_date = None
        vasi.session.commit()
        flash('Η ετικέτα σαρώθηκε και η εργασία καταγράφηκε!', 'success')
    except Exception as e:
        error_msg = str(e).lower()
        if '429' in error_msg or 'quota' in error_msg or '413' in error_msg or 'too large' in error_msg:
            flash('⚠️ Το αρχείο είναι πολύ μεγάλο.', 'warning')
        else:
            flash('⚠️ Δεν μπόρεσα να διαβάσω την ετικέτα. Βγάλτε πιο καθαρή φωτογραφία.', 'danger')
        
    return redirect(url_for('core_app.arxikh'))

@ai_bp.route('/ai_vision', methods=['POST'])
@login_required
def ai_vision():
    if 'image' not in request.files: return jsonify({'error': 'No image'}), 400
    try:
        img = PIL.Image.open(request.files['image'])
        response = ai_client.models.generate_content(model='gemini-2.5-flash', contents=["Analyze this...", img])
        return jsonify({'result': response.text})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@ai_bp.route('/ndvi_chat/<int:ktima_id>', methods=['POST'])
@login_required
def ndvi_chat(ktima_id):
    ktima = vasi.session.get(Ktima, ktima_id)
    data = request.get_json()
    client = genai.Client(api_key=api_key_ai)
    
    prompt = (
        f"Είσαι επαγγελματίας γεωπόνος (AI) και συνομιλείς με τον αγρότη σχετικά με τον δορυφορικό χάρτη NDVI του κτήματός του.\n"
        f"Προηγούμενη διάγνωση/ερώτησή σου: '{data.get('previous_ai_message')}'\n"
        f"Απάντηση αγρότη (μπορεί να είναι σε greeklish): '{data.get('user_reply')}'\n\n"
        f"ΟΔΗΓΙΕΣ:\n"
        f"1. Κατανόησε τι λέει ο αγρότης (ακόμα και σε greeklish) αλλά ΑΠΑΝΤΗΣΕ ΑΥΣΤΗΡΑ ΣΕ ΣΩΣΤΑ ΕΛΛΗΝΙΚΑ.\n"
        f"2. ΑΠΑΓΟΡΕΥΕΤΑΙ να κάνεις ανάλυση ή μετάφραση των λέξεων. Δώσε ΚΑΤΕΥΘΕΙΑΝ τη γεωπονική σου συμβουλή/συμπέρασμα βάσει της απάντησής του.\n"
        f"3. Να είσαι φιλικός, άμεσος και περιεκτικός."
    )
    response = client.models.generate_content(model='gemini-2.5-flash', contents=prompt)
    
    nea_diagnosi = Diagnosi(ktima_id=ktima.id, apotelesma=f"Chat: {response.text.strip()}", imerominia=datetime.now())
    vasi.session.add(nea_diagnosi)
    vasi.session.commit()
    return jsonify({'refined_message': response.text.strip()})

@ai_bp.route('/apantisi_sto_ai/<int:ktima_id>', methods=['POST'])
@login_required
def apantisi_sto_ai(ktima_id):
    ktima = vasi.session.get(Ktima, ktima_id)
    user_reply = request.form.get('user_reply')
    client = genai.Client(api_key=api_key_ai)
    prompt = (
        f"Ο γεωπόνος (AI) ρώτησε τον αγρότη: '{ktima.ekkremis_erotisi_ai}'.\nΟ αγρότης απάντησε: '{user_reply}'.\n"
        f"ΟΔΗΓΙΑ 1: Βγάλε ένα ΣΥΝΟΛΙΚΟ συμπέρασμα (2-3 προτάσεις) που να περιέχει ΟΛΕΣ τις πληροφορίες που έδωσε ο χρήστης (π.χ. για περσινές ασθένειες, δάκο, έλλειψη αναλύσεων). Αυτή θα είναι η μόνιμη 'μνήμη' σου. Αν ο αγρότης γράψει κάτι εντελώς ακατανόητο, απάντησε 'Συγγνώμη, δεν σας κατάλαβα.'.\n"
        f"ΟΔΗΓΙΑ 2: Αν ο αγρότης αναφέρει ότι ΕΧΕΙ ΗΔΗ ΚΑΝΕΙ εργασίες (π.χ. 'έριξα χαλκό', 'κλάδεψα'), γράψε στο τέλος τη φράση 'ΟΛΟΚΛΗΡΩΜΕΝΕΣ ΕΡΓΑΣΙΕΣ:' και δίπλα τις εργασίες χωρισμένες με κόμμα.\n"
        f"ΟΔΗΓΙΑ 3: Αν ο αγρότης περιγράφει το φαινολογικό στάδιο (π.χ. 'μούρο', 'μπουμπούκια', 'ανθοταξίες'), γράψε στο τέλος τη φράση 'ΝΕΟ ΣΤΑΔΙΟ:' και δίπλα μια σύντομη ονομασία του σταδίου.\n"
        f"ΟΔΗΓΙΑ 4: Αν ο αγρότης απαντήσει ότι ΔΕΝ έκανε τις εκκρεμείς εργασίες αλλά θα τις κάνει αργότερα (π.χ. 'αύριο', 'avrio', 'μεθαύριο', 'methaurio', 'το Σαββατοκύριακο'), γράψε στο τέλος τη φράση 'ΑΝΑΒΟΛΗ_ΗΜΕΡΕΣ:' και δίπλα ένα νούμερο (π.χ. 1 για αύριο, 2 για μεθαύριο, 4 για γενικά). Αν λέει ότι ΔΕΝ θα τις κάνει καθόλου, γράψε 'ΑΚΥΡΩΣΗ_ΟΛΩΝ:'."
    )
    response = client.models.generate_content(model='gemini-2.5-flash', contents=prompt)
    
    import re
    ai_text = response.text.strip()
    symperasma = ai_text
    
    match_anaboli = re.search(r'ΑΝΑΒΟΛΗ_ΗΜΕΡΕΣ:\s*(\d+)', symperasma)
    anaboli_meres = int(match_anaboli.group(1)) if match_anaboli else None
    if match_anaboli: symperasma = symperasma.replace(match_anaboli.group(0), '')
        
    akyrosi = False
    if 'ΑΚΥΡΩΣΗ_ΟΛΩΝ:' in symperasma:
        akyrosi = True
        symperasma = symperasma.replace('ΑΚΥΡΩΣΗ_ΟΛΩΝ:', '')
        
    match_stadio = re.search(r'ΝΕΟ ΣΤΑΔΙΟ:\s*(.*?)(?=ΟΛΟΚΛΗΡΩΜΕΝΕΣ ΕΡΓΑΣΙΕΣ:|ΑΝΑΒΟΛΗ_ΗΜΕΡΕΣ:|ΑΚΥΡΩΣΗ_ΟΛΩΝ:|$)', symperasma, re.DOTALL)
    neo_stadio = match_stadio.group(1).strip() if match_stadio else None
    if match_stadio: symperasma = symperasma.replace(match_stadio.group(0), '').replace('ΝΕΟ ΣΤΑΔΙΟ:', '')
        
    match_tasks = re.search(r'ΟΛΟΚΛΗΡΩΜΕΝΕΣ ΕΡΓΑΣΙΕΣ:\s*(.*?)(?=ΝΕΟ ΣΤΑΔΙΟ:|ΑΝΑΒΟΛΗ_ΗΜΕΡΕΣ:|ΑΚΥΡΩΣΗ_ΟΛΩΝ:|$)', symperasma, re.DOTALL)
    completed_tasks = [t.strip() for t in match_tasks.group(1).split(',') if t.strip()] if match_tasks else []
    if match_tasks: symperasma = symperasma.replace(match_tasks.group(0), '').replace('ΟΛΟΚΛΗΡΩΜΕΝΕΣ ΕΡΓΑΣΙΕΣ:', '')

    symperasma = symperasma.strip()
        
    nea_diagnosi = Diagnosi(ktima_id=ktima.id, apotelesma=f"Συμπέρασμα AI (Από Chat): {symperasma}", imerominia=datetime.now())
    vasi.session.add(nea_diagnosi)
    
    for task_name in completed_tasks:
        vasi.session.add(Ergasia(ktima_id=ktima.id, eidos_ergasias=task_name + " (Από συζήτηση AI)", katastasi='Ολοκληρώθηκε', imerominia=datetime.now(), proelevsi='AI Ιστορικό'))
        
        # Καθαρισμός εκκρεμών
        pending_tasks = Ergasia.query.filter_by(ktima_id=ktima.id, katastasi='Εκκρεμεί').all()
        new_task_text = task_name.lower()
        
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
        
    if neo_stadio: ktima.fainologiko_stadio = neo_stadio
        
    action_msg = ""
    # Εφαρμογή Αναβολής ή Ακύρωσης σε εκκρεμείς εργασίες
    if anaboli_meres or akyrosi:
        overdue_tasks = [e for e in ktima.ergasies if not e.archived and e.katastasi == 'Εκκρεμεί' and e.imerominia.date() <= datetime.now().date()]
        count_affected = len(overdue_tasks)
        for t in overdue_tasks:
            if akyrosi:
                t.katastasi = 'Ακυρώθηκε'
            else:
                t.imerominia = datetime.now() + timedelta(days=anaboli_meres)
        if count_affected > 0:
            if akyrosi: action_msg += "Έγινε ακύρωση των εκκρεμών εργασιών. "
            else: action_msg += f"Μεταφέρθηκαν {count_affected} εργασίες κατά {anaboli_meres} ημέρες! "
        
    if completed_tasks:
        action_msg += f"Καταγράφηκαν {len(completed_tasks)} εργασίες ως ολοκληρωμένες. "
    if neo_stadio:
        action_msg += f"Το στάδιο ενημερώθηκε σε {neo_stadio}. "
        
    ktima.ekkremis_erotisi_ai = None
    vasi.session.commit()
    
    # Ανανέωση των δεδομένων AI μετά την απάντηση (ώστε να λάβει υπόψη το νέο συμπέρασμα άμεσα)
    try:
        from logic import syghronismos_ai_ktimatos
        syghronismos_ai_ktimatos(ktima)
    except Exception as e:
        print(f"Σφάλμα κατά τον συγχρονισμό μετά την απάντηση: {e}")
        
    flash(f'{action_msg}Η απάντησή σας καταγράφηκε και ο AI Γεωπόνος ενημερώθηκε!', 'success')
    return redirect(url_for('core_app.arxikh'))

def _process_secretary_response(ai_text, ktima):
    """
    Βοηθητική συνάρτηση για την επεξεργασία της απάντησης του AI Γραμματέα.
    Απομονώνει την κοινή λογική από τις apantisi_sto_ai και apantisi_sto_ai_ajax.
    """
    import re
    from models import Diagnosi, Ergasia

    symperasma = ai_text
    
    match_anaboli = re.search(r'ΑΝΑΒΟΛΗ_ΗΜΕΡΕΣ:\s*(\d+)', symperasma)
    anaboli_meres = int(match_anaboli.group(1)) if match_anaboli else None
    if match_anaboli: symperasma = symperasma.replace(match_anaboli.group(0), '')
        
    akyrosi = 'ΑΚΥΡΩΣΗ_ΟΛΩΝ:' in symperasma
    if akyrosi: symperasma = symperasma.replace('ΑΚΥΡΩΣΗ_ΟΛΩΝ:', '')
        
    match_stadio = re.search(r'ΝΕΟ ΣΤΑΔΙΟ:\s*(.*?)(?=ΟΛΟΚΛΗΡΩΜΕΝΕΣ ΕΡΓΑΣΙΕΣ:|ΑΝΑΒΟΛΗ_ΗΜΕΡΕΣ:|ΑΚΥΡΩΣΗ_ΟΛΩΝ:|$)', symperasma, re.DOTALL)
    neo_stadio = match_stadio.group(1).strip() if match_stadio else None
    if match_stadio: symperasma = symperasma.replace(match_stadio.group(0), '').replace('ΝΕΟ ΣΤΑΔΙΟ:', '')
        
    match_tasks = re.search(r'ΟΛΟΚΛΗΡΩΜΕΝΕΣ ΕΡΓΑΣΙΕΣ:\s*(.*?)(?=ΝΕΟ ΣΤΑΔΙΟ:|ΑΝΑΒΟΛΗ_ΗΜΕΡΕΣ:|ΑΚΥΡΩΣΗ_ΟΛΩΝ:|$)', symperasma, re.DOTALL)
    completed_tasks = [t.strip() for t in match_tasks.group(1).split(',') if t.strip()] if match_tasks else []
    if match_tasks: symperasma = symperasma.replace(match_tasks.group(0), '').replace('ΟΛΟΚΛΗΡΩΜΕΝΕΣ ΕΡΓΑΣΙΕΣ:', '')

    symperasma = symperasma.strip()
        
    vasi.session.add(Diagnosi(ktima_id=ktima.id, apotelesma=f"Συμπέρασμα AI (Από Chat): {symperasma}", imerominia=datetime.now()))
    
    # Καθαρισμός εκκρεμών εργασιών με βάση τις ολοκληρωμένες
    synonym_groups = [
        {'πότισμ', 'νερ', 'άρδευσ'}, {'χόρτ', 'ζιζάν', 'καταστροφ'},
        {'λίπανσ', 'θρέψη', 'άζωτ', 'βόρι', 'αμινοξ', 'κάλι', 'φωσφορ'},
        {'κλάδεμ'}, {'χαλκ', 'μυκητοκτόν', 'ψεκασμ'}, {'δάκ', 'εντομοκτόν', 'πυρηνοτρύτ', 'ψεκασμ'}, {'όργωμ', 'φρέζ'}
    ]
    pending_tasks_to_check = Ergasia.query.filter_by(ktima_id=ktima.id, katastasi='Εκκρεμεί').all()

    for task_name in completed_tasks:
        vasi.session.add(Ergasia(ktima_id=ktima.id, eidos_ergasias=task_name + " (Από συζήτηση AI)", katastasi='Ολοκληρώθηκε', imerominia=datetime.now(), proelevsi='AI Ιστορικό'))
        
        new_task_text = task_name.lower()
        new_task_group_idx = next((i for i, group in enumerate(synonym_groups) if any(syn in new_task_text for syn in group)), -1)

        if new_task_group_idx != -1:
            for pt in pending_tasks_to_check:
                pending_task_text = f"{pt.eidos_ergasias.lower()} {(pt.farmaka_lipasmata or '').lower()}"
                if any(syn in pending_task_text for syn in synonym_groups[new_task_group_idx]):
                    vasi.session.delete(pt)
        
    if neo_stadio: ktima.fainologiko_stadio = neo_stadio
        
    # Εφαρμογή Αναβολής ή Ακύρωσης
    if anaboli_meres or akyrosi:
        overdue_tasks = [e for e in ktima.ergasies if not e.archived and e.katastasi == 'Εκκρεμεί' and e.imerominia.date() <= datetime.now().date()]
        for t in overdue_tasks:
            if akyrosi:
                t.katastasi = 'Ακυρώθηκε'
            else:
                t.imerominia = datetime.now() + timedelta(days=anaboli_meres)

    return {
        "anaboli_meres": anaboli_meres, "akyrosi": akyrosi, "neo_stadio": neo_stadio,
        "completed_tasks": completed_tasks, "symperasma": symperasma
    }

@ai_bp.route('/apantisi_sto_ai_ajax/<int:ktima_id>', methods=['POST'])
@login_required
def apantisi_sto_ai_ajax(ktima_id):
    ktima = vasi.session.get(Ktima, ktima_id)
    if not ktima or (ktima.idioktitis != current_user and getattr(current_user, 'rolos', '') != 'geoponos'):
        return jsonify({'error': 'Μη εξουσιοδοτημένη πρόσβαση'}), 403
        
    req_data = request.get_json()
    user_reply = req_data.get('user_reply', '')
    current_question = req_data.get('current_question', ktima.ekkremis_erotisi_ai)
    
    client = genai.Client(api_key=api_key_ai)
    prompt = (
        f"Ο γεωπόνος (AI) ρώτησε τον αγρότη: '{current_question}'.\nΟ αγρότης απάντησε: '{user_reply}'.\n"
        f"ΟΔΗΓΙΑ 1: Βγάλε ένα ΣΥΝΟΛΙΚΟ συμπέρασμα (2-3 προτάσεις) που να περιέχει ΟΛΕΣ τις πληροφορίες που έδωσε ο χρήστης (π.χ. για περσινές ασθένειες, δάκο, έλλειψη αναλύσεων). Αυτή θα είναι η μόνιμη 'μνήμη' σου. Αν ο αγρότης γράψει κάτι εντελώς ακατανόητο, απάντησε 'Συγγνώμη, δεν σας κατάλαβα.'.\n"
        f"ΟΔΗΓΙΑ 2: Αν ο αγρότης αναφέρει ότι ΕΧΕΙ ΗΔΗ ΚΑΝΕΙ εργασίες (π.χ. 'έριξα χαλκό', 'κλάδεψα'), γράψε στο τέλος τη φράση 'ΟΛΟΚΛΗΡΩΜΕΝΕΣ ΕΡΓΑΣΙΕΣ:' και δίπλα τις εργασίες χωρισμένες με κόμμα.\n"
        f"ΟΔΗΓΙΑ 3: Αν ο αγρότης περιγράφει το φαινολογικό στάδιο (π.χ. 'μούρο', 'μπουμπούκια', 'ανθοταξίες'), γράψε στο τέλος τη φράση 'ΝΕΟ ΣΤΑΔΙΟ:' και δίπλα μια σύντομη ονομασία του σταδίου.\n"
        f"ΟΔΗΓΙΑ 4: Αν ο αγρότης απαντήσει ότι ΔΕΝ έκανε τις εκκρεμείς εργασίες αλλά θα τις κάνει αργότερα (π.χ. 'αύριο', 'avrio', 'μεθαύριο', 'methaurio', 'το Σαββατοκύριακο'), γράψε στο τέλος τη φράση 'ΑΝΑΒΟΛΗ_ΗΜΕΡΕΣ:' και δίπλα ένα νούμερο (π.χ. 1 για αύριο, 2 για μεθαύριο, 4 για γενικά). Αν λέει ότι ΔΕΝ θα τις κάνει καθόλου, γράψε 'ΑΚΥΡΩΣΗ_ΟΛΩΝ:'."
    )
    
    response = client.models.generate_content(model='gemini-2.5-flash', contents=prompt)
    import re
    ai_text = response.text.strip()
    
    symperasma = ai_text
    
    match_anaboli = re.search(r'ΑΝΑΒΟΛΗ_ΗΜΕΡΕΣ:\s*(\d+)', symperasma)
    anaboli_meres = int(match_anaboli.group(1)) if match_anaboli else None
    if match_anaboli: symperasma = symperasma.replace(match_anaboli.group(0), '')
        
    akyrosi = False
    if 'ΑΚΥΡΩΣΗ_ΟΛΩΝ:' in symperasma:
        akyrosi = True
        symperasma = symperasma.replace('ΑΚΥΡΩΣΗ_ΟΛΩΝ:', '')
        
    match_stadio = re.search(r'ΝΕΟ ΣΤΑΔΙΟ:\s*(.*?)(?=ΟΛΟΚΛΗΡΩΜΕΝΕΣ ΕΡΓΑΣΙΕΣ:|ΑΝΑΒΟΛΗ_ΗΜΕΡΕΣ:|ΑΚΥΡΩΣΗ_ΟΛΩΝ:|$)', symperasma, re.DOTALL)
    neo_stadio = match_stadio.group(1).strip() if match_stadio else None
    if match_stadio: symperasma = symperasma.replace(match_stadio.group(0), '').replace('ΝΕΟ ΣΤΑΔΙΟ:', '')
        
    match_tasks = re.search(r'ΟΛΟΚΛΗΡΩΜΕΝΕΣ ΕΡΓΑΣΙΕΣ:\s*(.*?)(?=ΝΕΟ ΣΤΑΔΙΟ:|ΑΝΑΒΟΛΗ_ΗΜΕΡΕΣ:|ΑΚΥΡΩΣΗ_ΟΛΩΝ:|$)', symperasma, re.DOTALL)
    completed_tasks = [t.strip() for t in match_tasks.group(1).split(',') if t.strip()] if match_tasks else []
    if match_tasks: symperasma = symperasma.replace(match_tasks.group(0), '').replace('ΟΛΟΚΛΗΡΩΜΕΝΕΣ ΕΡΓΑΣΙΕΣ:', '')

    symperasma = symperasma.strip()
        
    nea_diagnosi = Diagnosi(ktima_id=ktima.id, apotelesma=f"Συμπέρασμα AI (Από Chat): {symperasma}", imerominia=datetime.now())
    vasi.session.add(nea_diagnosi)
    
    for task_name in completed_tasks:
        vasi.session.add(Ergasia(ktima_id=ktima.id, eidos_ergasias=task_name + " (Από συζήτηση AI)", katastasi='Ολοκληρώθηκε', imerominia=datetime.now(), proelevsi='AI Ιστορικό'))
        
        # Καθαρισμός εκκρεμών
        pending_tasks = Ergasia.query.filter_by(ktima_id=ktima.id, katastasi='Εκκρεμεί').all()
        new_task_text = task_name.lower()

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
        
    if neo_stadio: ktima.fainologiko_stadio = neo_stadio
        
    action_msg = ""
    # Εφαρμογή Αναβολής ή Ακύρωσης σε εκκρεμείς εργασίες
    if anaboli_meres or akyrosi:
        overdue_tasks = [e for e in ktima.ergasies if not e.archived and e.katastasi == 'Εκκρεμεί' and e.imerominia.date() <= datetime.now().date()]
        count_affected = len(overdue_tasks)
        for t in overdue_tasks:
            if akyrosi:
                t.katastasi = 'Ακυρώθηκε'
            else:
                t.imerominia = datetime.now() + timedelta(days=anaboli_meres)
        if count_affected > 0:
            if akyrosi: action_msg += "✅ Έγινε ακύρωση των εκκρεμών εργασιών.\n"
            else: action_msg += f"✅ Μετέφερα {count_affected} εργασίες κατά {anaboli_meres} ημέρες στο Ημερολόγιό σας!\n"
        
    if completed_tasks:
        action_msg += f"✅ Καταγράφηκαν {len(completed_tasks)} εργασίες ως ολοκληρωμένες.\n"
    if neo_stadio:
        action_msg += f"✅ Το στάδιο ενημερώθηκε σε: {neo_stadio}.\n"
        
    # Αφαιρούμε την τρέχουσα ερώτηση για να δούμε αν ο συγχρονισμός θα βγάλει καινούργια
    ktima.ekkremis_erotisi_ai = None
    vasi.session.commit()
    
    try:
        from logic import syghronismos_ai_ktimatos
        syghronismos_ai_ktimatos(ktima) # Ο "εγκέφαλος" διαβάζει τα νέα δεδομένα επιτόπου
        vasi.session.refresh(ktima)
        
        return jsonify({
            'success': True, 
            'action_msg': action_msg,
            'next_question': ktima.ekkremis_erotisi_ai
        })
    except Exception as e:
        vasi.session.rollback()
        return jsonify({'error': str(e)}), 500

@ai_bp.route('/paragogi_syntaghs/<int:ktima_id>', methods=['POST'])
@login_required
def paragogi_syntaghs(ktima_id):
    from models import Ktima, Syntagh, Ergasia # Local imports to avoid circular dependencies
    ktima = vasi.session.get(Ktima, ktima_id)
    
    # Access control: Must be owner or a geoponos
    if not ktima or (ktima.idioktitis != current_user and getattr(current_user, 'rolos', 'agroths') != 'geoponos'):
        return jsonify({'error': 'Μη εξουσιοδοτημένη πρόσβαση'}), 403

    try:
        # Συλλογή δεδομένων κτήματος για το AI
        from logic import xtise_plires_context
        dedomena = xtise_plires_context(ktima)
            
        # Το μαγικό Prompt που αναγκάζει το AI να απαντήσει με JSON
        prompt = (
            f"Είσαι Επαγγελματίας Γεωπόνος. Μελέτησε σχολαστικά τα δεδομένα του κτήματος:\n{dedomena}\n\n"
            f"ΟΔΗΓΙΕΣ ΓΙΑ ΤΗ ΣΥΝΤΑΓΗ:\n"
            f"1. FULL STACK ΠΡΟΣΕΓΓΙΣΗ: Πρότεινε ΟΛΕΣ τις αναγκαίες εργασίες χωρίς περιορισμό. Αν το ιστορικό του κτήματος είναι κενό, φτιάξε ένα πλήρες, ολοκληρωμένο πρόγραμμα για τη βέλτιστη υποστήριξη της καλλιέργειας. Αν ο αγρότης έχει καταχωρήσει εργασίες (π.χ. έγινε βασική λίπανση), αφαίρεσέ τες θεωρώντας ότι το φυτό έχει καλυφθεί στις αντίστοιχες ανάγκες του.\n"
            f"1α. ΒΑΣΙΚΗ ΠΡΟΛΗΨΗ: Την Άνοιξη (Μάρτιο/Απρίλιο) και το Φθινόπωρο, ο προληπτικός ψεκασμός με Χαλκό ή Μυκητοκτόνα είναι απαραίτητος. ΠΡΟΣΟΧΗ ΓΙΑ ΤΗΝ ΑΝΟΙΞΗ (ΚΡΙΣΙΜΟ): Απαγορεύεται αυστηρά η πρόταση για 'Βορδιγάλειο Πολτό' ή 'βαριά' καυστικά χαλκούχα σκευάσματα, καθώς καίνε τη νέα τρυφερή βλάστηση! Πρότεινε αποκλειστικά ήπιες μορφές (π.χ. Υδροξείδιο χαλκού, Γλυκονικό χαλκό, Dodine κ.λπ.) ή μη καυστικά μυκητοκτόνα. Επίσης, αν το δέντρο βρίσκεται στο στάδιο της πλήρους άνθισης ή πολύ κοντά σε αυτήν, ΑΠΑΓΟΡΕΥΕΤΑΙ ΑΥΣΤΗΡΑ ΚΑΘΕ ΨΕΚΑΣΜΟΣ. Αν το στάδιο είναι 'Άγνωστο' ή αμφίβολο, στο 'apantisi_chat' ζήτα ΠΡΩΤΑ από τον αγρότη να ανεβάσει μια φωτογραφία για να κρίνεις αν είναι ασφαλές να γίνει η εφαρμογή της συνταγής.\n"
            f"1β. Στο 'keimeno_syntaghs', ΕΝΗΜΕΡΩΣΕ ΞΕΚΑΘΑΡΑ τον αγρότη για τα χρονικά περιθώρια! Εξήγησέ του ΠΟΤΕ ακριβώς πρέπει να έχει γίνει η κάθε εργασία και γιατί (π.χ. 'Αυτός ο ψεκασμός πρέπει να γίνει το αργότερο έως τις 15/04 για να προλάβουμε το άνοιγμα του άνθους').\n"
            f"1γ. ΕΤΟΙΜΑ ΣΥΝΔΥΑΣΤΙΚΑ ΣΚΕΥΑΣΜΑΤΑ & TANK MIX (ΚΡΙΣΙΜΟ ΓΙΑ ΟΙΚΟΝΟΜΙΑ): Όταν το δέντρο έχει πολλαπλές ελλείψεις ιχνοστοιχείων/θρεπτικών (π.χ. Βόριο, Ψευδάργυρος, Μαγνήσιο, Άζωτο κλπ.), ΠΡΙΝ προτείνεις ξεχωριστά σκευάσματα, ΚΑΝΕ ΑΝΑΖΗΤΗΣΗ ΣΤΟ ΔΙΑΔΙΚΤΥΟ για να δεις αν υπάρχουν έτοιμα, εμπορικά 'πολυδύναμα' σκευάσματα που τα περιέχουν ΟΛΑ ΜΑΖΙ σε μία συσκευασία (π.χ. σύνθετα διαφυλλικά λιπάσματα ιχνοστοιχείων). Αν υπάρχουν, ενημέρωσε τον αγρότη στο κείμενο: 'Αυτά τα στοιχεία θα τα βρείτε συνδυασμένα σε ένα έτοιμο σκεύασμα του εμπορίου'. Αν δεν υπάρχει έτοιμο και πρέπει να γίνουν μίξεις (tank mix) διαφορετικών σκευασμάτων, ΣΥΓΧΩΝΕΥΣΕ τα ΑΥΣΤΗΡΑ σε ΕΝΑΝ κοινό ψεκασμό ΜΟΝΟ ΕΦΟΣΟΝ είναι επιστημονικά συμβατά. Αν είναι ασύμβατα, σπάσε τα σε ξεχωριστές εργασίες.\n"
            f"1δ. ΥΔΡΟΛΙΠΑΝΣΗ: Αν στα δεδομένα αναφέρεται ότι το κτήμα είναι 'Αρδευόμενο', ΠΡΟΤΙΜΗΣΕ ΞΕΚΑΘΑΡΑ την Υδρολίπανση ως μέθοδο θρέψης έναντι της κοκκώδους λίπανσης στο έδαφος, διότι είναι πιο άμεση, οικονομική και αποδοτική.\n"
            f"1ε. ΓΕΩΡΓΙΑ ΑΚΡΙΒΕΙΑΣ (ΜΙΚΤΑ ΚΤΗΜΑΤΑ & ΤΟΠΙΚΑ ΠΡΟΒΛΗΜΑΤΑ): Αν το κτήμα έχει δέντρα διαφορετικών ηλικιών ή ποικιλιών (π.χ. και νεαρά και γηραιά), ΥΠΟΛΟΓΙΣΕ ΚΑΙ ΔΩΣΕ ΞΕΧΩΡΙΣΤΕΣ ΔΟΣΟΛΟΓΙΕΣ στο κείμενο (π.χ. 'Για τα νεαρά δέντρα X λίτρα, για τα γηραιά Y λίτρα'). Αν από τις διαγνώσεις προκύπτει ότι ΜΟΝΟ κάποια δέντρα έχουν πρόβλημα (ή ο δορυφόρος δείχνει τοπικό στρες), πρότεινε 'Τοπική Επέμβαση' (Spot Treatment) ΜΟΝΟ στα άρρωστα δέντρα για οικονομία φαρμάκων και άσε τα υγιή χωρίς φάρμακο. ΣΕ ΑΥΤΗ ΤΗΝ ΠΕΡΙΠΤΩΣΗ, ψάξε στο ίντερνετ την τιμή του φαρμάκου, υπολόγισε και ανέφερε το ΕΚΤΙΜΩΜΕΝΟ ΚΟΣΤΟΣ ΑΝΑ ΔΕΝΤΡΟ, ώστε ο αγρότης να δει το οικονομικό όφελος!\n"
            f"1στ. ΥΠΟΛΟΓΙΣΜΟΣ ΔΟΣΟΛΟΓΙΑΣ ΒΑΣΕΙ ΗΛΙΚΙΑΣ & ΔΕΝΤΡΩΝ (ΚΡΙΣΙΜΟ): Προσάρμοσε τις προτεινόμενες δόσεις φαρμάκων/λιπασμάτων και τον όγκο του ψεκαστικού υγρού ΑΥΣΤΗΡΑ με βάση την ΗΛΙΚΙΑ των δέντρων και τον αριθμό τους! Χρησιμοποίησε το internet για να βρεις τις σωστές επιστημονικές αναλογίες φαρμάκου/νερού ανάλογα με την ηλικία της ελιάς (π.χ. τα νεαρά δέντρα 1-5 ετών θέλουν πολύ μικρότερο όγκο νερού και πιο προσεκτικές συγκεντρώσεις για αποφυγή τοξικότητας). Παρουσίασε αναλυτικά τους υπολογισμούς της συνολικής δοσολογίας στο κείμενο.\n"
            f"1ζ. ΙΣΤΟΡΙΚΟ ΑΣΘΕΝΕΙΩΝ: ΑΝ από το 'ΙΣΤΟΡΙΚΟ ΠΡΟΒΛΗΜΑΤΩΝ, ΦΩΤΟΓΡΑΦΙΩΝ & ΕΥΡΗΜΑΤΩΝ ΓΡΑΜΜΑΤΕΑ' προκύπτει πρόσφατη αναγνώριση ασθένειας (π.χ. Κυκλοκόνιο, μύκητες) ή συγκεκριμένο στάδιο, ΛΑΒΕ ΤΟ ΣΟΒΑΡΑ ΥΠΟΨΗ για τη συνταγή σου, προσαρμόζοντας τα φάρμακα ή τις δόσεις.\n"
            f"1η. ΜΕΣΟ ΨΕΚΑΣΜΟΥ: Αν προτείνεις ψεκασμό, ΡΩΤΑ ΞΕΚΑΘΑΡΑ με ποιο μέσο θα γίνει η εφαρμογή (τουρμπίνα, μπεκ/λάστιχο, ψεκαστήρας πλάτης, drone) ώστε στην επόμενη συνομιλία σας να προσαρμόσεις με ακρίβεια τον όγκο του ψεκαστικού υγρού.\n"
            f"1θ. ΣΕΙΡΑ ΑΝΑΜΕΙΞΗΣ: Αν προτείνεις ψεκασμό με μίγμα 2 ή παραπάνω σκευασμάτων (π.χ. χαλκός + ιχνοστοιχεία + κολλητικό), ΠΕΡΙΓΡΑΨΕ ΞΕΚΑΘΑΡΑ μέσα στο 'keimeno_syntaghs' την επιστημονικά σωστή σειρά προσθήκης τους στο βυτίο (π.χ. νερό ως τη μέση, μετά σκόνες WP/WG, μετά υγρά SC/EC, τέλος διαβρέκτες/κολλητικά) για να μην κόψει το φάρμακο.\n"
            f"1ι. ΑΣΥΜΒΑΤΟΤΗΤΕΣ & ΤΟΞΙΚΟΤΗΤΑ: Αν προτείνεις μίγμα (tank mix), έλεγξε ΑΥΣΤΗΡΑ την επιστημονική συμβατότητα των ουσιών (π.χ. Απαγορεύεται αυστηρά η ανάμειξη Χαλκού με Αμινοξέα). Αν εντοπίσεις πρόβλημα συμβατότητας στα υλικά που έχει η αποθήκη, ΜΗΝ τα βάλεις στο ίδιο βυτίο. Προειδοποίησε τον αγρότη και σπάσε τις εργασίες σε ξεχωριστούς ψεκασμούς με διαφορά ημερών.\n"
            f"1κ. ΑΝΑΜΟΝΗ & ΧΡΟΝΟΜΕΤΡΑ: Αν δεις στις 'Εκκρεμείς Εργασίες' ότι υπάρχει 'Χρονόμετρο', ΣΕΒΑΣΟΥ ΤΟ. Επίσης, αν εσύ προτείνεις μια εργασία που πρέπει να καθυστερήσει (π.χ. PHI, αναμονή σταδίου, ασυμβατότητα), πρόσθεσε στην αρχή του πεδίου 'farmaka' το tag '[ΧΡΟΝΟΜΕΤΡΟ:YYYY-MM-DD]' με την ημερομηνία που θα είναι ασφαλές να γίνει. Το σύστημα θα ανάψει πράσινο όταν έρθει η ώρα.\n"
            f"1λ. ΑΠΑΓΟΡΕΥΕΤΑΙ ΑΥΣΤΗΡΑ να ζητάς από τον αγρότη πληροφορίες για τον καιρό ή προβλέψεις (λαμβάνεις ήδη την Πρόγνωση 4 ημερών από τα δεδομένα σου).\n"
            f"1μ. ΕΛΛΕΙΨΗ ΑΝΑΛΥΣΗΣ: Αν στα δεδομένα δεις ότι ΔΕΝ ΥΠΑΡΧΕΙ ανάλυση εδάφους, δώσε κανονικά μια 'τυπική/στάνταρ' πρόταση λίπανσης για την εποχή, ΑΛΛΑ τόνισε στο 'keimeno_syntaghs' ότι: 'Λόγω έλλειψης ανάλυσης, η πρόταση είναι τυπική. Για μέγιστη ακρίβεια και οικονομία συνιστάται εδαφολογική ανάλυση'. Επίσης πρόσθεσε στο 'eidos' της συγκεκριμένης εργασίας το tag '[⚠️ Τυπική Πρόταση]'.\n"
            f"1ν. ΒΙΟΛΟΓΙΚΗ ΓΕΩΡΓΙΑ: Αν στο προφίλ αναφέρεται 'Βιολογική', ΑΠΑΓΟΡΕΥΕΤΑΙ ΑΥΣΤΗΡΑ η χρήση χημικών ζιζανιοκτόνων ή φαρμάκων.\n"
            f"1ξ. ΟΙΚΟΝΟΜΙΚΗ & ΧΡΟΝΙΚΗ ΚΑΤΑΝΟΜΗ ΕΡΓΑΣΙΩΝ (ΚΡΙΣΙΜΟ): ΜΗΝ φορτώνεις τον αγρότη με όλα τα έξοδα και όλες τις δουλειές ταυτόχρονα! Αν η ανάλυση εδάφους/φύλλων ή το στάδιο δείχνουν πολλαπλές ελλείψεις, ΙΕΡΑΡΧΗΣΕ ΤΕΣ. Πρότεινε για ΑΜΕΣΗ εφαρμογή ΜΟΝΟ τα απολύτως απαραίτητα για την επιβίωση/καρπόδεση του δέντρου. Για τα υπόλοιπα (π.χ. δευτερεύοντα ιχνοστοιχεία ή μελλοντικές ανάγκες), μετάθεσέ τα χρονικά. Στο πεδίο 'farmaka' αυτών των μελλοντικών εργασιών, βάλε υποχρεωτικά στην αρχή το tag '[ΧΡΟΝΟΜΕΤΡΟ:YYYY-MM-DD]' (υπολόγισε μια ημερομηνία σε 20, 30 ή 40 μέρες από σήμερα). Έτσι το κόστος αγοράς και ο κόπος θα σπάσει σε δόσεις.\n"
            f"1ο. ΔΙΑΧΕΙΡΙΣΗ ΖΙΖΑΝΙΩΝ: Αν διαβάσεις στα δεδομένα ότι ο αγρότης έχει ήδη ΚΟΨΕΙ Ή ΨΕΚΑΣΕΙ τα χόρτα πρόσφατα, ΑΠΑΓΟΡΕΥΕΤΑΙ ΑΥΣΤΗΡΑ να του ξαναπροτείνεις ενέργεια καταπολέμησης (το έδαφος είναι καθαρό). Επίσης, ξεχώριζε ρητά την 'Κοπή' (μηχανική) από τον 'Ψεκασμό' (χημική) όταν κάνεις προτάσεις.\n"
            f"2. ΔΙΑΧΕΙΡΙΣΗ ΥΓΡΑΣΙΑΣ & ΨΕΚΑΣΜΩΝ: Αν βλέπεις χαμηλή υγρασία (<20%) ΜΟΝΟ από τον 'Δορυφόρο', ΜΗΝ είσαι απόλυτος και ΜΗΝ απαγορεύεις τις εργασίες. Πρότεινε κανονικά τις επόμενες αναγκαίες ενέργειες (π.χ. τον επόμενο ψεκασμό βάσει σταδίου), αλλά δώσε την ενέργεια ως *πρόταση*, υπενθυμίζοντας στον αγρότη να επιβεβαιώσει πρώτα την υγρασία στο χωράφι και να ποτίσει αν χρειάζεται πριν ψεκάσει, για να μην κάψει τα δέντρα.\n"
            f"3. ΜΟΝΟ αν η 'Χειροκίνητη Μέτρηση Υγρασίας' είναι <20% ή το UVI είναι επικίνδυνα υψηλό (>8), εφάρμοσε αυστηρούς περιορισμούς στους ψεκασμούς.\n"
            f"4. Δώσε ΠΡΟΤΕΡΑΙΟΤΗΤΑ στα υλικά της Αποθήκης.\n"
            f"5. Στο πεδίο 'eidos' κάθε εργασίας, ΠΡΟΣΘΕΣΕ ΥΠΟΧΡΕΩΤΙΚΑ το χρονικό περιθώριο ή την προϋπόθεση (π.χ. 'Ψεκασμός - Έως 20/04' ή 'Λίπανση - Πριν την άνθιση'). Αν το ιδανικό στάδιο/εποχή έχει περάσει, μην περιλάβεις την εργασία καθόλου.\n"
            f"6. ΑΠΟΛΥΤΗ ΕΠΙΣΤΗΜΟΝΙΚΗ ΟΡΘΟΤΗΤΑ (ΚΡΙΣΙΜΟ): Έχεις ζωντανή πρόσβαση στο διαδίκτυο. ΠΡΙΝ γράψεις την οποιαδήποτε συμβουλή, δοσολογία ή προτείνεις φάρμακο, ΕΙΣΑΙ ΥΠΟΧΡΕΩΜΕΝΟΣ να ψάξεις στο internet για να επιβεβαιώσεις 100% ότι η πρακτική είναι σωστή και ασφαλής. Απαγορεύεται αυστηρά να κάνεις λάθος που μπορεί να καταστρέψει την παραγωγή.\n"
            f"--- ΔΙΑΧΩΡΙΣΜΟΣ ΑΠΑΝΤΗΣΗΣ ΣΕ 2 ΚΟΥΤΙΑ (ΚΡΙΣΙΜΟ) ---\n"
            f"ΠΡΕΠΕΙ να μοιράσεις το κείμενο σε 2 μέρη για να εμφανιστεί σωστά στην οθόνη του χρήστη:\n"
            f"ΑΠΑΓΟΡΕΥΕΤΑΙ ΑΥΣΤΗΡΑ η χρήση διπλών εισαγωγικών (\") μέσα στα κείμενα ή τις απαντήσεις σου. Χρησιμοποίησε ΜΟΝΟ μονά εισαγωγικά ('). Απαγορεύεται να χρησιμοποιήσεις αλλαγές γραμμής (Enter/Newlines) μέσα στα string values.\n"
            f"Επίστρεψε ΑΥΣΤΗΡΑ ΚΑΙ ΜΟΝΟ ένα έγκυρο JSON με αυτή την ακριβή δομή:\n"
            f"{{\n"
            f"  \"apantisi_chat\": \"ΚΟΥΤΙ 1: Εδώ θα μπει η φιλική συζήτηση (Χαιρετισμός, ανάλυση καιρού/εδάφους και γενικές εξηγήσεις).\",\n"
            f"  \"keimeno_syntaghs\": \"ΚΟΥΤΙ 2: Εδώ θα μπει ΑΥΣΤΗΡΑ ΜΟΝΟ η λίστα με τις πρακτικές εργασίες (π.χ. 1. Ψεκασμός με...). ΜΗΝ βάλεις χαιρετισμούς ή αναλύσεις εδώ!\",\n"
            f"  \"ergasies\": [\n"
            f"    {{\"eidos\": \"Ψεκασμός/Λίπανση...\", \"farmaka\": \"...\"}}\n"
            f"  ]\n"
            f"}}\n"
            f"Μην γράψεις markdown κώδικα (όπως ```json), επέστρεψε απευθείας το καθαρό JSON object."
        )
        
        # Ενεργοποίηση Google Search (Σημείωση: Το response_mime_type δεν υποστηρίζεται ταυτόχρονα με tools)
        config = types.GenerateContentConfig(
            tools=[{"google_search": {}}]
        )
        response = ai_client.models.generate_content(model='gemini-2.5-flash', contents=prompt, config=config)
        
        if not response or not getattr(response, 'text', None):
            return jsonify({'error': 'Το AI δεν επέστρεψε δεδομένα. Δοκιμάστε ξανά.'}), 500

        # Καθαρισμός του JSON
        json_text = response.text.strip().replace('```json', '').replace('```', '').strip()
        
        # Απομόνωση του JSON block σε περίπτωση που το AI προσθέσει τυχαίο κείμενο
        start_idx = json_text.find('{')
        end_idx = json_text.rfind('}')
        if start_idx != -1 and end_idx != -1:
            json_text = json_text[start_idx:end_idx+1]
            
        # Καθαρισμός προβληματικών χαρακτήρων που σπάνε το JSON
        import re
        # Αφαιρούμε τις εσωτερικές αλλαγές γραμμής που καταστρέφουν τα JSON strings
        json_text = json_text.replace('\n', ' ').replace('\r', '')
        # Fix για διπλά εισαγωγικά που ίσως ξέφυγαν (Προαιρετικό, το strict=False βοηθάει)
            
        try:
            import json
            data = json.loads(json_text, strict=False)
        except json.JSONDecodeError as je:
            print(f"JSON Parse Error: {je}\nRaw: {json_text}")
            return jsonify({'error': 'Το AI χρησιμοποίησε μη επιτρεπτούς χαρακτήρες. Παρακαλώ πατήστε ξανά "Έκδοση Νέας Συνταγής"!'}), 500
        
        apantisi_chat = data.get('apantisi_chat', 'Γεια σας! Έχω αναλύσει τα δεδομένα και σας ετοίμασα το παρακάτω πρόγραμμα.')
        keimeno = data.get('keimeno_syntaghs', 'Προτεινόμενη Συνταγή από το AI')
        
        chat_arr = [{"role": "model", "content": apantisi_chat}]
        
        # 1. Αποθήκευση της Συνταγής
        nea_syntagh = Syntagh(
            ktima_id=ktima.id, 
            keimeno=keimeno, 
            chat_history=json.dumps(chat_arr, ensure_ascii=False),
            proelevsi='AI Γεωπόνος' if getattr(current_user, 'rolos', 'agroths') != 'geoponos' else 'Γεωπόνος',
            geoponos_id=current_user.id if getattr(current_user, 'rolos', '') == 'geoponos' else None
        )
        vasi.session.add(nea_syntagh)
        vasi.session.commit()
        
        # Επιστρέφουμε τις εργασίες στο frontend για να ζητήσουμε επιβεβαίωση
        # αντί να τις αποθηκεύσουμε κατευθείαν, ώστε να μην διαγράψουμε τυχόν χειροκίνητες εργασίες.
        return jsonify({
            'success': True, 
            'apantisi_chat': apantisi_chat,
            'syntagh': keimeno, 
            'syntagh_id': nea_syntagh.id,
            'ergasies': data.get('ergasies', [])
        })

    except Exception as e:
        vasi.session.rollback()
        print(f"Σφάλμα AI Συνταγής: {e}")
        return jsonify({'error': str(e)}), 500

@ai_bp.route('/refine_syntagh/<int:ktima_id>', methods=['POST'])
@login_required
def refine_syntagh(ktima_id):
    from models import Ktima, Syntagh, Ergasia
    ktima = vasi.session.get(Ktima, ktima_id)
    
    if not ktima or (ktima.idioktitis != current_user and getattr(current_user, 'rolos', 'agroths') != 'geoponos'):
        return jsonify({'error': 'Μη εξουσιοδοτημένη πρόσβαση'}), 403

    req_data = request.get_json()
    previous_recipe = req_data.get('previous_recipe', '')
    user_reply = req_data.get('user_reply', '')
    secret_brands = req_data.get('secret_brands', False)
    syntagh_id_apo_js = req_data.get('syntagh_id')
    
    old_syntagh = vasi.session.get(Syntagh, int(syntagh_id_apo_js)) if syntagh_id_apo_js else None
    try:
        # Άδειασμα μνήμης συζήτησης αν έχουν περάσει 24 ώρες
        if old_syntagh and (datetime.now() - old_syntagh.imerominia).total_seconds() > 86400:
            history = []
            old_syntagh.chat_history = '[]'
            vasi.session.commit()
        else:
            history = json.loads(old_syntagh.chat_history) if old_syntagh and old_syntagh.chat_history else []
    except:
        history = []

    try:
        from logic import xtise_plires_context
        dedomena = xtise_plires_context(ktima)
            
        secret_prompt = ""
        if secret_brands:
            secret_prompt = f"ΜΥΣΤΙΚΗ ΛΕΙΤΟΥΡΓΙΑ ΕΜΠΟΡΙΚΩΝ ΣΚΕΥΑΣΜΑΤΩΝ (ΚΡΙΣΙΜΟ): Ψάξε στο διαδίκτυο και πρότεινε ΣΥΓΚΕΚΡΙΜΕΝΕΣ ΥΠΑΡΚΤΕΣ ΜΑΡΚΕΣ της αγοράς (brands) για τα φάρμακα/λιπάσματα που θα προτείνεις. Αν είναι βιολογική, πρότεινε εγκεκριμένα βιολογικά προϊόντα. Βάλε τα εμπορικά ονόματα ΞΕΚΑΘΑΡΑ στο κείμενο και στο πεδίο 'farmaka' της κάθε εργασίας. "
            
        prompt = (
            f"Είσαι Κορυφαίος Επαγγελματίας Γεωπόνος & Ερευνητής. Μελέτησε σχολαστικά τα δεδομένα του κτήματος:\n{dedomena}\n\n"
            f"--- ΠΡΟΗΓΟΥΜΕΝΗ ΣΥΝΤΑΓΗ ΣΟΥ ---\n{previous_recipe}\n\n"
            f"--- ΣΧΟΛΙΟ / ΕΡΩΤΗΣΗ ΑΓΡΟΤΗ ---\n{user_reply}\n\n"
            f"--- ΟΔΗΓΙΑ (ΑΥΣΤΗΡΟΣ ΔΙΑΧΩΡΙΣΜΟΣ CHAT & ΣΥΝΤΑΓΗΣ) ---\n"
            f"Στην οθόνη υπάρχουν 2 ξεχωριστά 'Κουτιά': Ένα για το Chat (συζήτηση) και ένα για τη Συνταγή (το επίσημο πρόγραμμα).\n"
            f"ΠΡΕΠΕΙ ΝΑ ΤΑ ΔΙΑΧΩΡΙΣΕΙΣ ΣΩΣΤΑ:\n"
            f"1. Πεδίο 'apantisi_chat': ΕΔΩ ΘΑ ΓΡΑΦΕΙΣ ΠΑΝΤΑ! Γράψε τη φιλική σου απάντηση, λύσε την απορία του. ΑΝ Ο ΧΡΗΣΤΗΣ ΓΡΑΦΕΙ ΑΣΧΕΤΑ ΠΡΑΓΜΑΤΑ ή σε τεστάρει, απάντησέ του φιλικά. Αν γράψει κάτι εντελώς ακατανόητο, γράψε 'Συγγνώμη, δεν σας κατάλαβα.'.\n"
            f"2. Πεδίο 'keimeno_syntaghs': ΕΔΩ ΜΠΑΙΝΕΙ ΜΟΝΟ ΤΟ ΚΑΘΑΡΟ ΠΡΟΓΡΑΜΜΑ (Δοσολογίες/Φάρμακα).\n"
            f"   - ΚΡΙΣΙΜΟΣ ΚΑΝΟΝΑΣ: ΑΝ Ο ΧΡΗΣΤΗΣ ΑΠΛΩΣ ΣΕ ΡΩΤΑΕΙ ΚΑΤΙ (π.χ. 'Τι είναι το Βόριο;', 'Είσαι εδώ;'), ΑΠΑΓΟΡΕΥΕΤΑΙ ΝΑ ΑΛΛΑΞΕΙΣ ΤΗ ΣΥΝΤΑΓΗ! Βάλε την τιμή false (χωρίς εισαγωγικά) στο \"allakse_h_suntagh\" και άσε το \"keimeno_syntaghs\" κενό.\n"
            f"   - Θα θέσεις την τιμή true στο \"allakse_h_suntagh\" ΜΟΝΟ ΑΝ ΣΟΥ ΖΗΤΗΣΕΙ ΞΕΚΑΘΑΡΑ ΝΑ ΑΛΛΑΞΕΙΣ ΤΙΣ ΕΡΓΑΣΙΕΣ Ή ΤΙΣ ΔΟΣΟΛΟΓΙΕΣ.\n\n"
            f"ΕΙΔΙΚΟΙ ΚΑΝΟΝΕΣ: Είσαι στο διαδίκτυο. Ψάξε ΠΡΩΤΑ στο ίντερνετ. {secret_prompt}Λάβε υπόψη τις ΠΟΙΚΙΛΙΕΣ και την ΗΛΙΚΙΑ. ΓΕΩΡΓΙΑ ΑΚΡΙΒΕΙΑΣ: Αν υπάρχουν διαφορετικές ηλικίες/ποικιλίες ή τοπικά προβλήματα, δώσε ΞΕΧΩΡΙΣΤΕΣ δόσεις ή πρότεινε 'Τοπική Επέμβαση'. Αν προτείνεις Τοπική Επέμβαση, ΥΠΟΛΟΓΙΣΕ ΚΑΙ ΑΝΕΦΕΡΕ το κόστος φαρμάκου ανά δέντρο (βρες τιμές στο internet). ΑΝ ΕΙΝΑΙ ΑΝΟΙΞΗ, απαγορεύεται ο βορδιγάλειος πολτός. ΕΤΟΙΜΑ ΣΥΝΔΥΑΣΤΙΚΑ: Ψάξε στο διαδίκτυο αν οι ελλείψεις καλύπτονται από ΕΝΑ πολυδύναμο εμπορικό σκεύασμα και πρότεινέ το. Συγχώνευσε σε 1 εργασία (tank mix) ΜΟΝΟ όσα είναι συμβατά. ΒΙΟΛΟΓΙΚΗ ΓΕΩΡΓΙΑ: Απαγορεύονται τα χημικά.\n"
            f"ΒΙΟΛΟΓΙΚΗ ΓΕΩΡΓΙΑ: Αν στο προφίλ αναφέρεται 'Βιολογική', ΑΠΑΓΟΡΕΥΕΤΑΙ ΑΥΣΤΗΡΑ η χρήση χημικών ζιζανιοκτόνων ή φαρμάκων.\n"
            f"ΟΙΚΟΝΟΜΙΚΗ & ΧΡΟΝΙΚΗ ΚΑΤΑΝΟΜΗ: Σπάσε τις εργασίες χρονικά για να μην επιβαρυνθεί οικονομικά μονομιάς ο παραγωγός. Βάλε άμεσα ΜΟΝΟ τα επείγοντα για τη σεζόν και προγραμμάτισε τα υπόλοιπα για αργότερα με το tag '[ΧΡΟΝΟΜΕΤΡΟ:YYYY-MM-DD]' μέσα στο 'farmaka'.\n"
            f"ΑΠΟΛΥΤΗ ΕΠΙΣΤΗΜΟΝΙΚΗ ΟΡΘΟΤΗΤΑ (ΚΡΙΣΙΜΟ): ΠΡΙΝ απαντήσεις, ΕΙΣΑΙ ΥΠΟΧΡΕΩΜΕΝΟΣ να ψάξεις στο internet για να επιβεβαιώσεις 100% τις δοσολογίες και τα φάρμακα. Απαγορεύεται αυστηρά να κάνεις λάθος που μπορεί να προκαλέσει ζημιά στην καλλιέργεια.\n"
            f"ΑΠΑΓΟΡΕΥΕΤΑΙ ΑΥΣΤΗΡΑ η χρήση διπλών εισαγωγικών (\") μέσα στα κείμενα ή τις απαντήσεις σου. Χρησιμοποίησε ΜΟΝΟ μονά εισαγωγικά ('). Απαγορεύεται να χρησιμοποιήσεις αλλαγές γραμμής (Enter/Newlines) μέσα στα string values.\n"
            f"Επίστρεψε ΑΥΣΤΗΡΑ ΚΑΙ ΜΟΝΟ ένα έγκυρο JSON με αυτή την ακριβή δομή:\n"
            f"{{\n"
            f"  \"apantisi_chat\": \"Η φιλική απάντηση-συζήτηση.\",\n"
            f"  \"allakse_h_suntagh\": false,\n"
            f"  \"keimeno_syntaghs\": \"Το καθαρό νέο πρόγραμμα (ΜΟΝΟ αν allakse_h_suntagh=true).\",\n"
            f"  \"ergasies\": []\n"
            f"}}\n"
            f"Μην γράψεις markdown κώδικα, επέστρεψε απευθείας το καθαρό JSON object."
        )
        
        config = types.GenerateContentConfig(
            tools=[{"google_search": {}}]
        )
        response = ai_client.models.generate_content(model='gemini-2.5-flash', contents=prompt, config=config)
        
        if not response or not getattr(response, 'text', None):
            return jsonify({'error': 'Το AI δεν επέστρεψε δεδομένα.'}), 500
            
        json_text = response.text.strip().replace('```json', '').replace('```', '').strip()
        
        start_idx = json_text.find('{')
        end_idx = json_text.rfind('}')
        if start_idx != -1 and end_idx != -1:
            json_text = json_text[start_idx:end_idx+1]
            
        # Καθαρισμός προβληματικών χαρακτήρων που σπάνε το JSON
        import re
        # Αφαιρούμε τις εσωτερικές αλλαγές γραμμής που καταστρέφουν τα JSON strings
        json_text = json_text.replace('\n', ' ').replace('\r', '')
        # Fix για διπλά εισαγωγικά που ίσως ξέφυγαν (Προαιρετικό, το strict=False βοηθάει)
            
        try:
            import json
            data = json.loads(json_text, strict=False)
        except json.JSONDecodeError as je:
            print(f"JSON Parse Error (refine): {je}\nRaw: {json_text}")
            return jsonify({'error': 'Το AI μπερδεύτηκε με τη σύνταξη του κειμένου. Μπορείτε να διατυπώσετε διαφορετικά το σχόλιό σας;'}), 500
            
        apantisi_chat = data.get('apantisi_chat', 'Συγγνώμη, δεν σας κατάλαβα.')
        allakse_raw = data.get('allakse_h_suntagh', False)
        allakse = True if str(allakse_raw).lower() == 'true' or allakse_raw is True else False
        keimeno = data.get('keimeno_syntaghs', '')
        
        history.append({"role": "user", "content": user_reply})
        history.append({"role": "model", "content": apantisi_chat})
        
        if allakse and keimeno:
            raw_ergasies = data.get('ergasies', [])
            unique_ergasies = []
            seen = set()
            for erg in raw_ergasies:
                ident = (str(erg.get('eidos', '')).strip(), str(erg.get('farmaka', '')).strip())
                if ident not in seen:
                    seen.add(ident)
                    unique_ergasies.append(erg)

            if old_syntagh:
                old_syntagh.keimeno = keimeno
                old_syntagh.chat_history = json.dumps(history, ensure_ascii=False)
                old_syntagh.imerominia = datetime.now()
                vasi.session.commit()
                teliko_syntagh_id = old_syntagh.id
            else:
                nea_syntagh = Syntagh(
                    ktima_id=ktima.id, 
                    keimeno=keimeno, 
                    chat_history=json.dumps(history, ensure_ascii=False),
                    proelevsi='AI Γεωπόνος (Αναθεωρημένη)' if getattr(current_user, 'rolos', 'agroths') != 'geoponos' else 'Γεωπόνος',
                    geoponos_id=current_user.id if getattr(current_user, 'rolos', '') == 'geoponos' else None
                )
                vasi.session.add(nea_syntagh)
                vasi.session.commit()
                teliko_syntagh_id = nea_syntagh.id
        else:
            if old_syntagh:
                old_syntagh.chat_history = json.dumps(history, ensure_ascii=False)
                vasi.session.commit()
            teliko_syntagh_id = syntagh_id_apo_js
            keimeno = previous_recipe
            unique_ergasies = []
        
        return jsonify({
            'success': True, 
            'apantisi_chat': apantisi_chat,
            'allakse': allakse,
            'syntagh': keimeno, 
            'syntagh_id': teliko_syntagh_id,
            'ergasies': unique_ergasies
        })

    except Exception as e:
        vasi.session.rollback()
        print(f"Σφάλμα κατά την αναθεώρηση: {e}")
        return jsonify({'error': str(e)}), 500

@ai_bp.route('/epivevaiosi_ergasion_ai/<int:ktima_id>', methods=['POST'])
@login_required
def epivevaiosi_ergasion_ai(ktima_id):
    from models import Ktima, Ergasia
    ktima = vasi.session.get(Ktima, ktima_id)
    if not ktima or (ktima.idioktitis != current_user and getattr(current_user, 'rolos', 'agroths') != 'geoponos'):
        return jsonify({'error': 'Μη εξουσιοδοτημένη πρόσβαση'}), 403

    data = request.get_json()
    ergasies_list = data.get('ergasies', [])

    try:
        # Διαγραφή παλιών εκκρεμών (Προστέθηκε και ο "AI Γραμματέας" για 100% καθαρισμό)
        Ergasia.query.filter_by(ktima_id=ktima.id, katastasi='Εκκρεμεί').filter(
            Ergasia.proelevsi.in_(['AI Γεωπόνος', 'Γεωπόνος', 'AI Σύστημα Ασφαλείας', 'AI Δορυφόρος', 'AI Ιστορικό', 'AI Γραμματέας'])
        ).delete(synchronize_session=False)

        seen = set()
        for erg in ergasies_list:
            eidos = str(erg.get('eidos', 'Άλλη Εργασία'))[:100].strip()
            farmaka = str(erg.get('farmaka', ''))[:255].strip()
            
            if (eidos, farmaka) in seen:
                continue
            seen.add((eidos, farmaka))

            nea_ergasia = Ergasia(
                ktima_id=ktima.id,
                eidos_ergasias=eidos,
                farmaka_lipasmata=farmaka,
                katastasi='Εκκρεμεί',
                proelevsi='AI Γεωπόνος' if getattr(current_user, 'rolos', 'agroths') != 'geoponos' else 'Γεωπόνος',
                imerominia=datetime.now()
            )
            vasi.session.add(nea_ergasia)
        
        vasi.session.commit()
        return jsonify({'success': True})
    except Exception as e:
        vasi.session.rollback()
        return jsonify({'error': str(e)}), 500

@ai_bp.route('/xeirokiniti_syntagh/<int:ktima_id>', methods=['POST'])
@login_required
def xeirokiniti_syntagh(ktima_id):
    from models import Ktima, Syntagh, Ergasia
    ktima = vasi.session.get(Ktima, ktima_id)
    
    # Πρόσβαση μόνο σε Γεωπόνους (ή τον ιδιοκτήτη αν θέλουμε)
    if not ktima or getattr(current_user, 'rolos', '') != 'geoponos':
        return jsonify({'error': 'Μη εξουσιοδοτημένη πρόσβαση. Μόνο οι Γεωπόνοι μπορούν να εκδώσουν χειροκίνητη συνταγή.'}), 403

    data = request.get_json()
    keimeno_geoponou = data.get('keimeno', '').strip()
    
    if not keimeno_geoponou:
        return jsonify({'error': 'Το κείμενο της συνταγής δεν μπορεί να είναι κενό.'}), 400

    try:
        # 1. Αποθήκευση της Πρωτότυπης Συνταγής του Γεωπόνου
        nea_syntagh = Syntagh(ktima_id=ktima.id, keimeno=keimeno_geoponou, proelevsi='Γεωπόνος', geoponos_id=current_user.id)
        vasi.session.add(nea_syntagh)
        vasi.session.commit()

        # 2. Το AI διαβάζει τη συνταγή του Γεωπόνου και βγάζει τις Εργασίες
        epitrepetai_auto = ktima.idioktitis.geoponos_auto_ergasies
        
        if epitrepetai_auto:
            prompt = (
                f"Ένας επαγγελματίας γεωπόνος μόλις έγραψε την παρακάτω συνταγή/οδηγία για το κτήμα του αγρότη:\n"
                f"\"{keimeno_geoponou}\"\n\n"
                f"ΟΔΗΓΙΑ: Διάβασε το κείμενο και εξήγαγε ΜΟΝΟ τις εργασίες/ψεκασμούς/λιπάνσεις που ζητάει ο γεωπόνος να γίνουν. "
                f"Φρόντισε να βάλεις στο 'eidos' το χρονικό περιθώριο αν αναφέρεται (π.χ. 'Ψεκασμός - Έως 20/04').\n"
                f"Αν εντοπίσεις κάποιο επιστημονικό λάθος στη δοσολογία Ή λάθος στη συμβατότητα του μίγματος (π.χ. προτείνει ανάμειξη χαλκού με αμινοξέα ή ασύμβατων ουσιών), πρόσθεσε μια ευγενική πρόταση διόρθωσης μέσα στο πεδίο 'farmaka' (π.χ. '... [Σημείωση AI: Προσοχή, η ανάμειξη αυτών των σκευασμάτων ίσως προκαλέσει τοξικότητα / αχρήστευση]').\n"
                f"Επίστρεψε ΑΥΣΤΗΡΑ ΚΑΙ ΜΟΝΟ ένα έγκυρο JSON με αυτή την ακριβή δομή: "
                f"{{\"ergasies\": [{{\"eidos\": \"Είδος Εργασίας\", \"farmaka\": \"Φάρμακα/Λιπάσματα που αναφέρονται\"}}]}}\n"
                f"Μην γράψεις markdown κώδικα, επέστρεψε απευθείας το καθαρό JSON object."
            )
            
            config = types.GenerateContentConfig(response_mime_type="application/json")
            response = ai_client.models.generate_content(model='gemini-2.5-flash', contents=prompt, config=config)
            
            if not response or not getattr(response, 'text', None):
                return jsonify({'success': True}) # Προστασία να μην σκάσει η διαδικασία
                
            json_text = response.text.strip().replace('```json', '').replace('```', '').strip()
            start_idx = json_text.find('{')
            end_idx = json_text.rfind('}')
            if start_idx != -1 and end_idx != -1:
                json_text = json_text[start_idx:end_idx+1]
                
            ai_data = json.loads(json_text, strict=False)
            
            # Διαγραφή ΟΛΩΝ των παλιών εκκρεμών εργασιών (για να μην υπάρχουν διπλότυπα με παλιές συνταγές)
            Ergasia.query.filter_by(ktima_id=ktima.id, katastasi='Εκκρεμεί').filter(
                Ergasia.proelevsi.in_(['AI Γεωπόνος', 'Γεωπόνος', 'AI Σύστημα Ασφαλείας', 'AI Δορυφόρος', 'AI Ιστορικό', 'AI Γραμματέας'])
            ).delete(synchronize_session=False)

            seen = set()
            for erg in ai_data.get('ergasies', []):
                eidos = str(erg.get('eidos', 'Άλλη Εργασία'))[:100].strip()
                farmaka = str(erg.get('farmaka', ''))[:255].strip()
                
                if (eidos, farmaka) in seen:
                    continue
                seen.add((eidos, farmaka))
                
                vasi.session.add(Ergasia(ktima_id=ktima.id, eidos_ergasias=eidos, farmaka_lipasmata=farmaka, katastasi='Εκκρεμεί', proelevsi='Γεωπόνος', imerominia=datetime.now()))
            
            vasi.session.commit()

        return jsonify({'success': True})

    except Exception as e:
        vasi.session.rollback()
        print(f"Σφάλμα Χειροκίνητης Συνταγής: {e}")
        return jsonify({'error': str(e)}), 500

@ai_bp.route('/akyrosi_erotisis_ai/<int:ktima_id>', methods=['POST'])
@login_required
def akyrosi_erotisis_ai(ktima_id):
    from models import Ktima, Ergasia
    ktima = vasi.session.get(Ktima, ktima_id)
    
    if not ktima or (ktima.idioktitis != current_user and getattr(current_user, 'rolos', '') != 'geoponos'):
        return jsonify({'error': 'Μη εξουσιοδοτημένη πρόσβαση'}), 403
        
    completed_tasks = sum(1 for e in ktima.ergasies if e.katastasi == 'Ολοκληρώθηκε')
    if completed_tasks == 0 or (ktima.ekkremis_erotisi_ai and ('Καλώς' in ktima.ekkremis_erotisi_ai or 'καλώς' in ktima.ekkremis_erotisi_ai.lower())):
        # Αν ακυρώσει το onboarding, προσθέτουμε μια εικονική εργασία για να μην τον ξαναρωτήσει
        vasi.session.add(Ergasia(ktima_id=ktima.id, eidos_ergasias='Έναρξη Χρήσης (Χωρίς προηγούμενο ιστορικό)', katastasi='Ολοκληρώθηκε', imerominia=datetime.now(), proelevsi='Αγρότης'))
        
    ktima.ekkremis_erotisi_ai = None
    vasi.session.commit()
    return jsonify({'success': True})

@ai_bp.route('/delete_diagnosi/<int:diagnosi_id>', methods=['POST'])
@login_required
def delete_diagnosi(diagnosi_id):
    diagnosi = vasi.session.get(Diagnosi, diagnosi_id)
    if not diagnosi:
        flash('Η διάγνωση δεν βρέθηκε.', 'danger')
        return redirect(request.referrer or url_for('core_app.arxikh'))
    
    # Έλεγχος ιδιοκτησίας
    if diagnosi.ktima.idioktitis != current_user:
        flash('Δεν έχετε δικαίωμα να διαγράψετε αυτή τη διάγνωση.', 'danger')
        return redirect(request.referrer or url_for('core_app.arxikh'))
        
    vasi.session.delete(diagnosi)
    vasi.session.commit()
    flash('Η διάγνωση διαγράφηκε επιτυχώς.', 'success')
    return redirect(request.referrer or url_for('core_app.arxikh'))

@ai_bp.route('/delete_analysi_edafous/<int:analysi_id>', methods=['POST'])
@login_required
def delete_analysi_edafous(analysi_id):
    analysi = vasi.session.get(AnalysiEdafous, analysi_id)
    if not analysi or analysi.ktima.idioktitis != current_user:
        flash('Δεν βρέθηκε η ανάλυση ή δεν έχετε δικαίωμα διαγραφής.', 'danger')
        return redirect(request.referrer or url_for('core_app.arxikh'))
    
    vasi.session.delete(analysi)
    vasi.session.commit()
    flash('Η ανάλυση εδάφους διαγράφηκε επιτυχώς.', 'success')
    return redirect(request.referrer or url_for('core_app.arxikh'))
