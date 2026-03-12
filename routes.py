import os
import re
import PIL.Image
import time
from datetime import datetime, timedelta
import requests
from flask import redirect, url_for, request, render_template, jsonify, flash, make_response, Response
from flask_login import login_user, login_required, logout_user, current_user
from sqlalchemy import text

from core import efarmogi, vasi, kryptografhsh, serializer, ai_client, api_key_ai
from models import Xrhsths, Ktima, KatagrafiUgrasias, Ergasia, Exodo, Diagnosi, ArxeioSygkomidis, AnalysiEdafous, Apothiki, KtimaPoikilia
from logic import paragwgi_protasewn, generate_local_tasks_via_ai
from geoponika import pare_kairo, steile_email, pare_simvouli_ai, geoponikos_elegxos

@efarmogi.route('/')
@login_required
def arxikh():
    # Φιλτράρισμα μόνο των ενεργών κτημάτων
    ktimata = [k for k in current_user.ktimata if k.is_active]
    now = datetime.now()

    for ktima in ktimata:
        ktima.kairos = pare_kairo(ktima.geografiko_platos, ktima.geografiko_mikos)
        if ktima.kairos:
            ktima.symvouli = geoponikos_elegxos(ktima.kairos['thermokrasia'], ktima.kairos['ygrasia'])
            ktima.protaseis = paragwgi_protasewn(ktima, ktima.kairos['thermokrasia'], ktima.kairos['ygrasia'], ktima.kairos['perigrafi'])
        else:
            ktima.protaseis = []
        
        # Geospatial AI Task Engine
        ideal_tasks = generate_local_tasks_via_ai(ktima)
        if isinstance(ideal_tasks, list):
             ideal_tasks = [t.strip() for t in ideal_tasks if t.strip()]
        else:
             ideal_tasks = []

        # Ενσωμάτωση Κρίσιμων Ειδοποιήσεων (GDD/Προληπτικός) στις Εργασίες
        for protasi in ktima.protaseis:
            if "Πυρηνοτρήτη" in protasi:
                task_name = "Ψεκασμός για Πυρηνοτρήτη (Κρίσιμο GDD)"
                if task_name not in ideal_tasks:
                    ideal_tasks.insert(0, task_name) # Προσθήκη στην κορυφή της λίστας
            elif "Δάκο" in protasi and "δολωματικό" in protasi:
                ideal_tasks.insert(0, "Δολωματικός Ψεκασμός για Δάκο")
            elif "Επαναληπτικός Ψεκασμός" in protasi:
                task_name = "Προληπτικός Ψεκασμός (Επανάληψη)"
                if task_name not in ideal_tasks:
                    ideal_tasks.insert(0, task_name)

        completed_tasks = [e.eidos_ergasias for e in ktima.ergasies if not e.archived]
        ktima.pending_tasks = [task for task in ideal_tasks if task not in completed_tasks]

        # Υπολογισμός Συνολικού Κόστους για εμφάνιση
        ktima.synoliko_kostos = sum(exodo.poso for exodo in ktima.exoda if not exodo.archived)

        # Calculate days since last spray for PHI checking
        latest_spray = None
        for ergasia in ktima.ergasies:
            if not ergasia.archived and 'Ψεκασμός' in ergasia.eidos_ergasias:
                if latest_spray is None or ergasia.imerominia > latest_spray.imerominia:
                    latest_spray = ergasia
        
        if latest_spray:
            ktima.meres_apo_psekasmo = (now - latest_spray.imerominia).days
        else:
            ktima.meres_apo_psekasmo = None
            
    return render_template('arxiki.html', xrhsths=current_user, ktimata=ktimata)

@efarmogi.route('/ananeosi_ergasion/<int:ktima_id>')
@login_required
def ananeosi_ergasion(ktima_id):
    ktima = vasi.session.get(Ktima, ktima_id)
    if not ktima or ktima.idioktitis != current_user:
        return "Μη εξουσιοδοτημένη ενέργεια", 403
    
    ktima.teleftaia_enimerosi_ergasion = None
    vasi.session.commit()
    generate_local_tasks_via_ai(ktima) # Force regeneration
    
    flash('Η λίστα εργασιών επικαιροποιήθηκε με βάση το μικροκλίμα!', 'success')
    return redirect(url_for('arxikh'))

@efarmogi.route('/arxeio')
@login_required
def arxeio():
    ktimata = current_user.ktimata
    return render_template('arxeio.html', ktimata=ktimata)

@efarmogi.route('/rwta_ai/<int:ktima_id>', methods=['POST'])
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
    
    # Έλεγχος Μνήμης (Cache): Αν έχουμε ρωτήσει τις τελευταίες 6 ώρες, δεν ξαναρωτάμε
    now = datetime.now()
    if ktima.ai_sumvouli_cache and ktima.ai_sumvouli_date:
        # Αν πέρασαν λιγότερο από 6 ώρες (21600 δευτερόλεπτα)
        if (now - ktima.ai_sumvouli_date).total_seconds() < 21600:
            return jsonify({'apantisi': ktima.ai_sumvouli_cache + " (Αποθηκευμένη)"})

    # AI Context Injection
    context_msg = f"Ο ελαιώνας είναι {ktima.stremmata} στρέμματα και έχει {ktima.arithmos_dentron} δέντρα. Χρησιμοποίησε αυτά τα δεδομένα για να υπολογίσεις ακριβείς δόσεις φαρμάκων ή λιπασμάτων αν σου ζητηθεί."
    
    # We wrap the existing function logic here to include context
    full_prompt = f"{context_msg} Θερμοκρασία: {thermokrasia}, Υγρασία: {ygrasia}, Καιρός: {perigrafi}. {data.get('perigrafi', '')}"
    apantisi = pare_simvouli_ai(thermokrasia, ygrasia, full_prompt)
    
    # Αποθήκευση στη βάση αν η απάντηση είναι έγκυρη
    if not apantisi:
        apantisi = "Το σύστημα AI είναι προσωρινά μη διαθέσιμο. Δοκιμάστε ξανά σε λίγο."
    elif "μη διαθέσιμο" not in apantisi:
        ktima.ai_sumvouli_cache = apantisi
        ktima.ai_sumvouli_date = now
        vasi.session.commit()
        
    return jsonify({'apantisi': apantisi})

@efarmogi.route('/diagnosi_fwtografias/<int:ktima_id>', methods=['POST'])
@login_required
def diagnosi_fwtografias(ktima_id):
    if not api_key_ai:
        flash("Η λειτουργία AI είναι απενεργοποιημένη. Λείπει το API Key από τον server.", "danger")
        return redirect(url_for('arxikh'))

    ktima = vasi.session.get(Ktima, ktima_id)
    if not ktima or ktima.idioktitis != current_user:
        return "Μη εξουσιοδοτημένη ενέργεια", 403
    
    if 'fwtografia' not in request.files:
        flash('Δεν βρέθηκε αρχείο φωτογραφίας.', 'danger')
        return redirect(url_for('arxikh'))
    
    file = request.files['fwtografia']
    if file.filename == '':
        flash('Δεν επιλέχθηκε αρχείο.', 'danger')
        return redirect(url_for('arxikh'))
        
    if file:
        try:
            img = PIL.Image.open(file)
            prompt = "Είσαι γεωπόνος. Ανάλυσε αυτή τη φωτογραφία ελαιόδεντρου (φύλλα, καρπός, κορμός). Εντόπισε πιθανές ασθένειες, τροφοπενίες ή προβλήματα. Δώσε σύντομη και ξεκάθαρη διάγνωση 1-2 προτάσεων."
            
            response = None
            for attempt in range(3):
                try:
                    response = ai_client.models.generate_content(model='gemini-2.5-flash', contents=[prompt, img])
                    break
                except Exception:
                    time.sleep(2)
            
            apotelesma_text = response.text if response else "Αδυναμία ανάλυσης εικόνας λόγω φόρτου συστήματος."
            if not response:
                flash('Το AI δεν μπόρεσε να αναλύσει τη φωτογραφία αυτή τη στιγμή.', 'warning')

            nea_diagnosi = Diagnosi(ktima_id=ktima_id, apotelesma=apotelesma_text, imerominia=datetime.now())
            vasi.session.add(nea_diagnosi)
            vasi.session.commit()
            flash('Η διάγνωση ολοκληρώθηκε επιτυχώς!', 'success')
        except Exception as e:
            print(f"Σφάλμα Vision AI: {e}")
            flash('Προέκυψε σφάλμα κατά την ανάλυση της φωτογραφίας.', 'danger')
            
    return redirect(url_for('arxikh'))

@efarmogi.route('/analysi_egrafou/<int:ktima_id>', methods=['POST'])
@login_required
def analysi_egrafou(ktima_id):
    if not api_key_ai:
        flash("Η λειτουργία AI είναι απενεργοποιημένη. Λείπει το API Key από τον server.", "danger")
        return redirect(url_for('arxikh'))

    ktima = vasi.session.get(Ktima, ktima_id)
    if not ktima or ktima.idioktitis != current_user:
        return "Μη εξουσιοδοτημένη ενέργεια", 403

    if 'fwtografia_analysis' not in request.files:
        flash('Δεν βρέθηκε αρχείο φωτογραφίας.', 'danger')
        return redirect(url_for('arxikh'))

    file = request.files['fwtografia_analysis']
    if file.filename == '':
        flash('Δεν επιλέχθηκε αρχείο.', 'danger')
        return redirect(url_for('arxikh'))

    if file:
        try:
            img = PIL.Image.open(file)
            prompt = "Είσαι γεωπόνος. Διάβασε αυτό το έγγραφο ανάλυσης εδάφους/φύλλων. Εντόπισε μόνο τα βασικά προβλήματα ή ελλείψεις (π.χ. έλλειψη καλίου, χαμηλό pH, περίσσεια αζώτου). Γράψε 1-2 προτάσεις με τα ευρήματα."
            
            response = None
            for attempt in range(3):
                try:
                    response = ai_client.models.generate_content(model='gemini-2.5-flash', contents=[prompt, img])
                    break
                except Exception:
                    time.sleep(2)
            
            # Save generic analysis text
            ktima.analysi_dedomena = response.text if response else "Αδυναμία ανάλυσης κειμένου."
            
            # Smart Extraction for Database
            extraction_prompt = """
            Extract the following soil data from the image and return ONLY a JSON object:
            {"ph": float, "organiki_ousia": float, "azwto": float, "fwsforos": float, "kalio": float}
            If a value is not found, use null. Do not use markdown formatting.
            """
            
            extraction_response = None
            for attempt in range(3):
                try:
                    extraction_response = ai_client.models.generate_content(model='gemini-2.5-flash', contents=[extraction_prompt, img])
                    break
                except Exception:
                    time.sleep(2)
            
            if extraction_response:
                try:
                    import json
                    data = json.loads(extraction_response.text.strip().replace('```json', '').replace('```', ''))
                    nea_analysi = AnalysiEdafous(
                        ktima_id=ktima_id,
                        ph=data.get('ph'),
                        organiki_ousia=data.get('organiki_ousia'),
                        azwto=data.get('azwto'),
                        fwsforos=data.get('fwsforos'),
                        kalio=data.get('kalio')
                    )
                    vasi.session.add(nea_analysi)
                except Exception as e:
                    print(f"Extraction Error: {e}")

            vasi.session.commit()
            flash('Η ανάλυση του εγγράφου ολοκληρώθηκε και αποθηκεύτηκε.', 'success')
        except Exception as e:
            print(f"Σφάλμα OCR AI: {e}")
            flash('Προέκυψε σφάλμα κατά την ανάγνωση του εγγράφου.', 'danger')

    return redirect(url_for('arxikh'))

@efarmogi.route('/anagnorisi_stadiou/<int:ktima_id>', methods=['POST'])
@login_required
def anagnorisi_stadiou(ktima_id):
    if not api_key_ai:
        flash("Η λειτουργία AI είναι απενεργοποιημένη. Λείπει το API Key από τον server.", "danger")
        return redirect(url_for('arxikh'))

    ktima = vasi.session.get(Ktima, ktima_id)
    if not ktima or ktima.idioktitis != current_user:
        flash('Μη εξουσιοδοτημένη ενέργεια.', 'danger')
        return redirect(url_for('arxikh'))

    if 'fwtografia_stadiou' not in request.files:
        flash('Δεν βρέθηκε αρχείο φωτογραφίας.', 'danger')
        return redirect(url_for('arxikh'))

    file = request.files['fwtografia_stadiou']
    if file.filename == '':
        flash('Δεν επιλέχθηκε αρχείο.', 'danger')
        return redirect(url_for('arxikh'))

    if file:
        try:
            img = PIL.Image.open(file)
            prompt = "Είσαι κορυφαίος γεωπόνος. Δες αυτή τη φωτογραφία από κλαδί ελιάς. Σε ποιο φαινολογικό στάδιο βρίσκεται; Επίλεξε ΑΥΣΤΗΡΑ ΜΟΝΟ ΜΙΑ από τις παρακάτω φράσεις, χωρίς καμία άλλη λέξη ή τελεία: Λήθαργος, Βλαστική Ανάπτυξη, Σχηματισμός Ταξιανθιών, Άνθιση, Καρπόδεση, Ανάπτυξη Καρπού, Ωρίμανση."
            
            response = None
            for attempt in range(3):
                try:
                    response = ai_client.models.generate_content(model='gemini-2.5-flash', contents=[prompt, img])
                    break
                except Exception:
                    time.sleep(2)
            
            stage_text = response.text.strip().replace('.', '') if response else "Άγνωστο (Σφάλμα AI)"
            
            ktima.fainologiko_stadio = stage_text
            vasi.session.commit()
            flash(f'Το φαινολογικό στάδιο του κτήματος ορίστηκε σε: {stage_text}', 'success')
        except Exception as e:
            print(f"Σφάλμα Stage Vision AI: {e}")
            flash('Προέκυψε σφάλμα κατά την αναγνώριση του σταδίου.', 'danger')
            
    return redirect(url_for('arxikh'))

@efarmogi.route('/ektimisi_paragogis/<int:ktima_id>', methods=['POST'])
@login_required
def ektimisi_paragogis(ktima_id):
    if not api_key_ai:
        flash("Η λειτουργία AI είναι απενεργοποιημένη. Λείπει το API Key από τον server.", "danger")
        return redirect(url_for('arxikh'))

    ktima = vasi.session.get(Ktima, ktima_id)
    if not ktima or ktima.idioktitis != current_user:
        return "Μη εξουσιοδοτημένη ενέργεια", 403

    if 'fwtografia_paragogis' not in request.files:
        flash('Δεν βρέθηκε αρχείο φωτογραφίας.', 'danger')
        return redirect(url_for('arxikh'))

    file = request.files['fwtografia_paragogis']
    if file.filename == '':
        flash('Δεν επιλέχθηκε αρχείο.', 'danger')
        return redirect(url_for('arxikh'))

    if file:
        try:
            img = PIL.Image.open(file)
            
            # Κατασκευή πληροφοριών ποικιλίας για το AI
            if ktima.poikilies_details:
                poikilies_str = ", ".join([f"{p.poikilia_onoma} ({p.arithmos_dentron} δέντρα)" for p in ktima.poikilies_details])
            else:
                poikilies_str = ktima.poikilia

            prompt = (f"Είσαι ειδικός γεωπόνος. Ανάλυσε την εικόνα (φορτίο καρπού στο κλαδί) και λάβε υπόψη τα εξής δεδομένα: "
                      f"Σύνολο Δέντρων: {ktima.arithmos_dentron}. Ποικιλία/ες: {poikilies_str}. "
                      f"Χρησιμοποίησε τη βάση γνώσεών σου για τη μέση απόδοση σε καρπό και την ελαιοπεριεκτικότητα (απόδοση σε λάδι) που χαρακτηρίζει αυτές τις ποικιλίες. "
                      f"Συνδύασε την εικόνα (αν το κλαδί είναι φορτωμένο ή όχι) με τα αγρονομικά δεδομένα της ποικιλίας για να κάνεις μια ρεαλιστική εκτίμηση της συνολικής παραγωγής σε κιλά ελαιολάδου. "
                      f"Δώσε το αποτέλεσμα και μια σύντομη αιτιολόγηση.")
            
            response = None
            for attempt in range(3):
                try:
                    response = ai_client.models.generate_content(model='gemini-2.5-flash', contents=[prompt, img])
                    break
                except Exception:
                    time.sleep(2)
            
            apotelesma = response.text if response else "Δεν ήταν δυνατή η εκτίμηση."
            flash(f'Εκτίμηση Παραγωγής: {apotelesma}', 'info')
        except Exception as e:
            print(f"Σφάλμα Yield AI: {e}")
            flash('Προέκυψε σφάλμα κατά την εκτίμηση παραγωγής.', 'danger')
            
    return redirect(url_for('arxikh'))

@efarmogi.route('/ai_input_scan/<int:ktima_id>', methods=['POST'])
@login_required
def ai_input_scan(ktima_id):
    if not api_key_ai:
        flash("Η λειτουργία AI είναι απενεργοποιημένη. Λείπει το API Key από τον server.", "danger")
        return redirect(url_for('arxikh'))

    ktima = vasi.session.get(Ktima, ktima_id)
    if not ktima or ktima.idioktitis != current_user:
        return "Μη εξουσιοδοτημένη ενέργεια", 403

    if 'fwtografia_input' not in request.files:
        flash('Δεν βρέθηκε αρχείο φωτογραφίας.', 'danger')
        return redirect(url_for('arxikh'))

    file = request.files['fwtografia_input']
    if file.filename == '':
        flash('Δεν επιλέχθηκε αρχείο.', 'danger')
        return redirect(url_for('arxikh'))

    if file:
        try:
            img = PIL.Image.open(file)
            prompt = "You are an agronomist. Look at this bottle label or invoice of a farming product. Extract: 1) Product Name, 2) Active Ingredient, 3) Recommended Dosage. Return a very short summary like: 'Applied [Product] ([Ingredient]) at [Dosage]'."
            
            response = None
            for attempt in range(3):
                try:
                    response = ai_client.models.generate_content(model='gemini-2.5-flash', contents=[prompt, img])
                    break
                except Exception:
                    time.sleep(2)
            
            # Check if response exists
            ai_summary = response.text.strip() if response else "Αδυναμία ανάγνωσης ετικέτας."
            
            nea_ergasia = Ergasia(ktima_id=ktima.id, eidos_ergasias='Ψεκασμός/Λίπανση (AI)', katastasi='Ολοκληρώθηκε', farmaka_lipasmata=ai_summary, imerominia=datetime.now())
            vasi.session.add(nea_ergasia)
            
            # STEP 2: Αυτόματη αφαίρεση σχετικών εκκρεμών εργασιών
            if ktima.topikes_ergasies:
                pending_tasks = [t.strip() for t in ktima.topikes_ergasies.split(',') if t.strip()]
                updated_tasks = []
                
                # Έλεγχος αν η καταγραφή AI αφορά εφαρμογή (Ψεκασμό/Λίπανση)
                ai_log_lower = ai_summary.lower()
                is_application = any(kw in ai_log_lower for kw in ['applied', 'dosage', 'product', 'ψεκασμός', 'λίπανση', 'χαλκό', 'σκεύασμα'])
                
                if is_application:
                    for task in pending_tasks:
                        t_lower = task.lower()
                        # Αν η εκκρεμής εργασία είναι σχετική, την αφαιρούμε (θεωρείται ολοκληρωμένη)
                        if 'ψεκασμός' in t_lower or 'λίπανση' in t_lower or 'χαλκ' in t_lower:
                            continue 
                        updated_tasks.append(task)
                    
                    ktima.topikes_ergasies = ",".join(updated_tasks)

            vasi.session.commit()
            flash('Η εργασία καταγράφηκε αυτόματα από την εικόνα!', 'success')
        except Exception as e:
            print(f"Σφάλμα AI Input Scan: {e}")
            flash('Προέκυψε σφάλμα κατά την αυτόματη καταγραφή.', 'danger')
            
    return redirect(url_for('arxikh'))

@efarmogi.route('/steile_anafora', methods=['POST'])
@login_required
def steile_anafora():
    data = request.get_json()
    onoma = data.get('onoma_ktimatos')
    thermokrasia = data.get('thermokrasia')
    ygrasia = data.get('ygrasia')
    ai_sumvouli = data.get('ai_sumvouli', 'Δεν ζητήθηκε συμβουλή AI.')

    thema = f"Αναφορά Olea AI: {onoma}"
    keimeno = f"""Γεια σας,

Ακολουθεί η αναφορά για το κτήμα σας '{onoma}':

Θερμοκρασία: {thermokrasia}°C
Υγρασία: {ygrasia}%

Συμβουλή AI:
{ai_sumvouli}

Με εκτίμηση,
Η ομάδα του Olea AI
"""
    
    if steile_email(current_user.email, thema, keimeno):
        return jsonify({'minima': 'Επιτυχία'})
    else:
        return jsonify({'minima': 'Σφάλμα'}), 500

@efarmogi.route('/prosthes_ergasia/<int:ktima_id>', methods=['POST'])
@login_required
def prosthes_ergasia(ktima_id):
    ktima = vasi.session.get(Ktima, ktima_id)
    if not ktima or ktima.idioktitis != current_user:
        return "Μη εξουσιοδοτημένη ενέργεια", 403
    
    eidos = request.form.get('eidos_ergasias')
    farmaka = request.form.get('farmaka_lipasmata', '').lower()
    katastasi = request.form.get('katastasi')
    
    # Rule 1: Weed Competition Rule
    if eidos == 'Λίπανση':
        thirty_days_ago = datetime.now() - timedelta(days=30)
        recent_tilling = Ergasia.query.filter(
            Ergasia.ktima_id == ktima_id,
            Ergasia.eidos_ergasias == 'Φρεζάρισμα',
            Ergasia.katastasi == 'Ολοκληρώθηκε',
            Ergasia.imerominia >= thirty_days_ago
        ).first()
        if not recent_tilling:
            flash('Προειδοποίηση: Δεν βρέθηκε καταγραφή για καθαρισμό/φρεζάρισμα τις τελευταίες 30 ημέρες. Τα ζιζάνια θα απορροφήσουν το λίπασμα.', 'warning')

    # Rule 2: Dacus Heat Rule
    if eidos == 'Ψεκασμός' and 'δακος' in farmaka:
        kairos = pare_kairo(ktima.geografiko_platos, ktima.geografiko_mikos)
        if kairos and kairos.get('thermokrasia', 0) >= 33:
            flash('Προειδοποίηση: Η θερμοκρασία είναι >33°C. Ο δάκος αδρανοποιείται. Ο ψεκασμός θα είναι σπατάλη χρημάτων!', 'warning')

    nea_ergasia = Ergasia(
        ktima_id=ktima_id,
        eidos_ergasias=eidos,
        farmaka_lipasmata=request.form.get('farmaka_lipasmata'),
        katastasi=katastasi,
        imerominia=datetime.now()
    )
    
    vasi.session.add(nea_ergasia)
    
    # Έλεγχος για κόστος (Smart Workflow)
    kostos_str = request.form.get('kostos')
    if kostos_str and katastasi == 'Ολοκληρώθηκε':
        try:
            kostos = float(kostos_str)
            if kostos > 0:
                neo_exodo = Exodo(
                    ktima_id=ktima_id,
                    perigrafi=f"Έξοδα εργασίας: {eidos}",
                    poso=kostos,
                    imerominia=datetime.now()
                )
                vasi.session.add(neo_exodo)
        except ValueError:
            pass

    vasi.session.commit()
    return redirect(url_for('arxikh'))

@efarmogi.route('/oloklirosi_ergasias/<int:ktima_id>', methods=['POST'])
@login_required
def oloklirosi_ergasias(ktima_id):
    ktima = vasi.session.get(Ktima, ktima_id)
    if not ktima or ktima.idioktitis != current_user:
        return "Μη εξουσιοδοτημένη ενέργεια", 403

    eidos = request.form.get('eidos_ergasias')
    kostos_str = request.form.get('kostos')

    # Δημιουργία Εργασίας
    nea_ergasia = Ergasia(
        ktima_id=ktima_id,
        eidos_ergasias=eidos,
        katastasi='Ολοκληρώθηκε',
        imerominia=datetime.now()
    )
    vasi.session.add(nea_ergasia)

    # Δημιουργία Εξόδου (αν υπάρχει κόστος)
    try:
        kostos = float(kostos_str)
        if kostos > 0:
            neo_exodo = Exodo(ktima_id=ktima_id, perigrafi=f"{eidos} - Έξοδο", poso=kostos, imerominia=datetime.now())
            vasi.session.add(neo_exodo)
    except (ValueError, TypeError):
        pass

    vasi.session.commit()
    return redirect(url_for('arxikh'))

@efarmogi.route('/prosthes_ugrasia/<int:ktima_id>', methods=['POST'])
@login_required
def prosthes_ugrasia(ktima_id):
    ktima = vasi.session.get(Ktima, ktima_id)
    if not ktima or ktima.idioktitis != current_user:
        return "Μη εξουσιοδοτημένη ενέργεια", 403
    
    try:
        pososto = float(request.form.get('pososto'))
        nea_ugrasia = KatagrafiUgrasias(ktima_id=ktima_id, pososto=pososto)
        vasi.session.add(nea_ugrasia)
        vasi.session.commit()
        flash('Η μέτρηση υγρασίας καταγράφηκε.', 'success')
    except ValueError:
        flash('Μη έγκυρη τιμή.', 'danger')
        
    return redirect(url_for('arxikh'))

@efarmogi.route('/enimerosi_nerou/<int:ktima_id>', methods=['POST'])
@login_required
def enimerosi_nerou(ktima_id):
    ktima = vasi.session.get(Ktima, ktima_id)
    if not ktima or ktima.idioktitis != current_user:
        return "Μη εξουσιοδοτημένη ενέργεια", 403
    
    try:
        ph = request.form.get('nero_ph')
        ec = request.form.get('nero_agwgimotita')
        
        if ph: ktima.nero_ph = float(ph)
        if ec: ktima.nero_agwgimotita = float(ec)
        
        vasi.session.commit()
        flash('Τα στοιχεία ποιότητας νερού ενημερώθηκαν.', 'success')
    except ValueError:
        flash('Μη έγκυρες τιμές.', 'danger')
        
    return redirect(url_for('arxikh'))

@efarmogi.route('/prosthes_exodo/<int:ktima_id>', methods=['POST'])
@login_required
def prosthes_exodo(ktima_id):
    ktima = vasi.session.get(Ktima, ktima_id)
    if not ktima or ktima.idioktitis != current_user:
        return "Μη εξουσιοδοτημένη ενέργεια", 403
    
    perigrafi = request.form.get('perigrafi')
    try:
        poso = float(request.form.get('poso'))
    except ValueError:
        poso = 0.0
        
    neo_exodo = Exodo(
        ktima_id=ktima_id,
        perigrafi=perigrafi,
        poso=poso,
        imerominia=datetime.now()
    )
    vasi.session.add(neo_exodo)
    vasi.session.commit()
    return redirect(url_for('arxikh'))

@efarmogi.route('/arxeiothetisi_ktimatos/<int:id>')
@login_required
def arxeiothetisi_ktimatos(id):
    ktima = vasi.session.get(Ktima, id)
    if ktima and ktima.idioktitis == current_user:
        ktima.is_active = False
        vasi.session.commit()
        flash('Το κτήμα αρχειοθετήθηκε επιτυχώς.', 'success')
    return redirect(url_for('arxikh'))

@efarmogi.route('/diagrafi_ktimatos/<int:ktima_id>', methods=['POST'])
@login_required
def diagrafi_ktimatos(ktima_id):
    ktima = vasi.session.get(Ktima, ktima_id)
    if ktima and ktima.idioktitis == current_user:
        # 1. Delete from Agromonitoring Satellite API if it exists
        if ktima.agromonitoring_poly_id:
            api_key = os.getenv('AGROMONITORING_API_KEY')
            if api_key:
                try:
                    del_url = f"http://api.agromonitoring.com/agro/1.0/polygons/{ktima.agromonitoring_poly_id}?appid={api_key}"
                    requests.delete(del_url)
                except Exception as e:
                    print(f"Agromonitoring Delete Error: {e}")
        
        # 2. Delete permanently from local Database
        vasi.session.delete(ktima)
        vasi.session.commit()
        flash('Το κτήμα και τα δορυφορικά του δεδομένα διαγράφηκαν οριστικά.', 'success')
    return redirect(url_for('arxikh'))

@efarmogi.route('/oristiki_diagrafi_ktimatos/<int:id>', methods=['POST'])
@login_required
def oristiki_diagrafi_ktimatos(id):
    ktima = vasi.session.get(Ktima, id)
    if ktima and ktima.idioktitis == current_user:
        # 1. Delete Polygon from Agromonitoring (if exists)
        if ktima.agromonitoring_poly_id:
            api_key = os.getenv('AGROMONITORING_API_KEY')
            if api_key:
                try:
                    del_url = f"http://api.agromonitoring.com/agro/1.0/polygons/{ktima.agromonitoring_poly_id}?appid={api_key}"
                    requests.delete(del_url)
                except Exception as e:
                    print(f"Error deleting polygon from API: {e}")

        # 2. Permanent Delete from DB
        vasi.session.delete(ktima)
        vasi.session.commit()
        flash('Το κτήμα και το συνδεδεμένο πολύγωνο διαγράφηκαν οριστικά.', 'success')
    return redirect(url_for('arxeio'))

@efarmogi.route('/eggrafi', methods=['GET', 'POST'])
def eggrafi():
    if current_user.is_authenticated:
        return redirect(url_for('arxikh'))
    
    if request.method == 'POST':
        email = request.form.get('email')
        kwdikos = request.form.get('kwdikos')
        epivevaiosi = request.form.get('epivevaiosi_kwdikou')
        
        if not email or not kwdikos or not epivevaiosi:
            flash("Συμπληρώστε όλα τα πεδία.", "warning")
            return render_template('eggrafi.html')

        if kwdikos != epivevaiosi:
            flash("Οι κωδικοί δεν ταιριάζουν.", "danger")
            return render_template('eggrafi.html')
            
        hash_kwdikou = kryptografhsh.generate_password_hash(kwdikos).decode('utf-8')
        neos_xrhsths = Xrhsths(email=email, kwdikos=hash_kwdikou)
        
        try:
            vasi.session.add(neos_xrhsths)
            vasi.session.commit()
            flash("Η εγγραφή ολοκληρώθηκε! Συνδεθείτε.", "success")
            return redirect(url_for('eisodos'))
        except:
            flash("Το Email υπάρχει ήδη.", "danger")
            
    return render_template('eggrafi.html')

@efarmogi.route('/xexasa_kodiko', methods=['GET', 'POST'])
def xexasa_kodiko():
    if request.method == 'POST':
        email = request.form.get('email')
        xrhsths = Xrhsths.query.filter_by(email=email).first()
        
        if xrhsths:
            token = serializer.dumps(email, salt='epanafora-kodikou')
            link = url_for('epanafora_kodikou', token=token, _external=True)
            
            thema = "Επαναφορά Κωδικού - Olea AI"
            keimeno = f"Για να επαναφέρετε τον κωδικό σας, πατήστε στον παρακάτω σύνδεσμο:\n{link}\n\nΟ σύνδεσμος λήγει σε 1 ώρα."
            
            try:
                steile_email(email, thema, keimeno, raise_exception=True)
                flash('Στάλθηκε email με οδηγίες επαναφοράς.', 'info')
                return redirect(url_for('eisodos'))
            except Exception as e:
                print(f"EMAIL ERROR: {str(e)}", flush=True)
                flash('Σφάλμα κατά την αποστολή του email. Ελέγξτε τα logs.', 'danger')
                return redirect(url_for('xexasa_kodiko'))
        else:
            flash('Δεν βρέθηκε λογαριασμός με αυτό το email.', 'warning')
            return redirect(url_for('xexasa_kodiko'))

    return render_template('xexasa_kodiko.html')

@efarmogi.route('/epanafora_kodikou/<token>', methods=['GET', 'POST'])
def epanafora_kodikou(token):
    try:
        email = serializer.loads(token, salt='epanafora-kodikou', max_age=3600)
    except:
        flash('Ο σύνδεσμος είναι άκυρος ή έχει λήξει.', 'danger')
        return redirect(url_for('xexasa_kodiko'))
    
    if request.method == 'POST':
        kwdikos = request.form.get('kwdikos')
        epivevaiosi = request.form.get('epivevaiosi_kwdikou')
        
        if kwdikos != epivevaiosi:
            flash('Οι κωδικοί δεν ταιριάζουν.', 'danger')
            return render_template('epanafora_kodikou.html', token=token)
            
        xrhsths = Xrhsths.query.filter_by(email=email).first()
        if xrhsths:
            hash_kwdikou = kryptografhsh.generate_password_hash(kwdikos).decode('utf-8')
            xrhsths.kwdikos = hash_kwdikou
            vasi.session.commit()
            flash('Ο κωδικός σας άλλαξε επιτυχώς! Συνδεθείτε.', 'success')
            return redirect(url_for('eisodos'))
            
    return render_template('epanafora_kodikou.html', token=token)

@efarmogi.route('/eisodos', methods=['GET', 'POST'])
def eisodos():
    if current_user.is_authenticated:
        return redirect(url_for('arxikh'))

    if request.method == 'POST':
        email = request.form.get('email')
        kwdikos = request.form.get('kwdikos')
        
        xrhsths = Xrhsths.query.filter_by(email=email).first()
        
        if xrhsths and kryptografhsh.check_password_hash(xrhsths.kwdikos, kwdikos):
            login_user(xrhsths)
            return redirect(url_for('arxikh'))
        else:
            flash("Λάθος email ή κωδικός", "danger")

    return render_template('eisodos.html')

@efarmogi.route('/prosthes_ktima', methods=['POST'])
@login_required
def prosthes_ktima():
    onoma = request.form.get('onoma_ktimatos')
    mikos = request.form.get('geografiko_mikos')
    platos = request.form.get('geografiko_platos')
    typos = request.form.get('typos_edafous')
    klisi = request.form.get('klisi')
    ardefsi = request.form.get('ardefsi')
    ilikia_dentron = request.form.get('ilikia_dentron', 'Άγνωστη')
    puknotita_dentron = request.form.get('puknotita_dentron', 'Κανονική')
    diacheirisi_edafous = request.form.get('diacheirisi_edafous', 'Άγνωστη')
    stremmata = request.form.get('stremmata')
    polygon_geojson = request.form.get('polygon_geojson')
    if stremmata:
        stremmata = stremmata.replace(',', '.')

    # Νέα λογική για πολλαπλές ποικιλίες
    poikilia_onomata = request.form.getlist('poikilia_onoma')
    poikilia_dentra_str = request.form.getlist('poikilia_dentra')
    
    if onoma and mikos and platos:
        try:
            # --- PREPARATION ---
            total_trees = 0
            poikilia_dentra = []
            for s in poikilia_dentra_str:
                try:
                    num_trees = int(s)
                    total_trees += num_trees if num_trees > 0 else 0
                    poikilia_dentra.append(num_trees if num_trees > 0 else 0)
                except (ValueError, TypeError):
                    poikilia_dentra.append(0)

            display_poikilia = 'Ανάμεικτο' if len(poikilia_onomata) > 1 else (poikilia_onomata[0] if len(poikilia_onomata) == 1 else 'Δεν ορίστηκε')

            # --- GDD SMART INIT ---
            initial_gdd = 0.0
            now = datetime.now()
            if now.month > 1:
                try:
                    if api_key_ai:
                        prompt = f"Calculate GDD (Base 9.0°C) for Lat {platos}, Lon {mikos} from Jan 1st to today ({now.strftime('%d/%m')}). Return ONLY the integer value."
                        response = ai_client.models.generate_content(model='gemini-2.5-flash', contents=prompt)
                        if response and response.text:
                            digits = re.findall(r'\d+', response.text)
                            if digits:
                                initial_gdd = float(digits[0])
                except Exception as e:
                    print(f"GDD Auto-Init Failed: {e}")
                    estimations = {1: 0, 2: 15, 3: 60, 4: 150, 5: 320, 6: 600, 7: 950, 8: 1350, 9: 1650}
                    initial_gdd = float(estimations.get(now.month, 0))

            # --- BUILD OBJECTS IN MEMORY ---
            neo = Ktima(
                onoma_ktimatos=onoma, geografiko_mikos=float(mikos), geografiko_platos=float(platos), idioktitis=current_user,
                typos_edafous=typos, klisi=klisi, ardefsi=ardefsi, poikilia=display_poikilia,
                stremmata=float(stremmata) if stremmata else 0.0,
                arithmos_dentron=total_trees, gdd_accumulated=initial_gdd, polygon_geojson=polygon_geojson,
                ilikia_dentron=ilikia_dentron, puknotita_dentron=puknotita_dentron, diacheirisi_edafous=diacheirisi_edafous
            )
            vasi.session.add(neo)
            vasi.session.flush()  # Flush to get neo.id for relations

            for i, onoma_poikilias in enumerate(poikilia_onomata):
                if onoma_poikilias and i < len(poikilia_dentra) and poikilia_dentra[i] > 0:
                    detail = KtimaPoikilia(ktima_id=neo.id, poikilia_onoma=onoma_poikilias, arithmos_dentron=poikilia_dentra[i])
                    vasi.session.add(detail)

            # --- AUTO NDVI ANALYSIS (RUNS BEFORE COMMIT) ---
            if polygon_geojson and polygon_geojson.strip() != "":
                try:
                    import json, requests, io
                    from google import genai

                    geo_data = json.loads(polygon_geojson)
                    api_key = os.getenv('AGROMONITORING_API_KEY')
                    if api_key:
                        poly_url = f"http://api.agromonitoring.com/agro/1.0/polygons?appid={api_key}"
                        poly_data = {"name": f"Ktima_{neo.id}_{int(datetime.now().timestamp())}", "geo_json": geo_data}
                        poly_res = requests.post(poly_url, json=poly_data)
                        
                        poly_id = None
                        if poly_res.status_code in [200, 201]: poly_id = poly_res.json().get('id')
                        elif poly_res.status_code == 422 and 'duplicated' in poly_res.text:
                            match = re.search(r"polygon '([a-f0-9]+)'", poly_res.text)
                            if match: poly_id = match.group(1)
                        
                        if poly_id:
                            neo.agromonitoring_poly_id = poly_id # Update object in session
                            end_time = int(datetime.now().timestamp())
                            start_time = end_time - (365 * 24 * 60 * 60)
                            img_url = f"http://api.agromonitoring.com/agro/1.0/image/search?start={start_time}&end={end_time}&polyid={poly_id}&appid={api_key}"
                            img_res = requests.get(img_url)
                            
                            if img_res.status_code == 200 and img_res.json():
                                for img_data in reversed(img_res.json()):
                                    ndvi_url = img_data.get('image', {}).get('ndvi')
                                    if ndvi_url:
                                        if ndvi_url.startswith('http:'): ndvi_url = ndvi_url.replace('http:', 'https:')
                                        ai_message = "Ο δορυφορικός χάρτης NDVI αναλύθηκε επιτυχώς κατά την δημιουργία του κτήματος."
                                        try:
                                            img_response = requests.get(ndvi_url)
                                            if img_response.status_code == 200:
                                                image_file = PIL.Image.open(io.BytesIO(img_response.content))
                                                client = genai.Client(api_key=api_key_ai)
                                                prompt = f"Είσαι εξειδικευμένος γεωπόνος. Αναλύεις ένα ΝΕΟ κτήμα. Ηλικία δέντρων: {neo.ilikia_dentron}, Πυκνότητα: {neo.puknotita_dentron}, Έδαφος: {neo.diacheirisi_edafous}. Δες τον χάρτη NDVI και γράψε μια πολύ σύντομη, επαγγελματική αρχική εκτίμηση υγείας (1-2 προτάσεις)."
                                                response = client.models.generate_content(model='gemini-2.5-flash', contents=[prompt, image_file])
                                                ai_message = response.text.strip()
                                        except Exception as e:
                                            print(f"Auto NDVI Vision Error: {e}")
                                        
                                        nea_diagnosi = Diagnosi(ktima_id=neo.id, apotelesma=f"🛰️ Αυτόματη Αρχική Διάγνωση (NDVI): {ai_message}", imerominia=datetime.now())
                                        vasi.session.add(nea_diagnosi)
                                        break
                except Exception as e:
                    print(f"Auto NDVI General Error: {e}") # Log error, but don't stop the whole process

            # --- ATOMIC COMMIT ---
            vasi.session.commit()
            flash('Το κτήμα προστέθηκε επιτυχώς!', 'success')
        except Exception as e:
            vasi.session.rollback()
            print(f"DB Error: {e}")
            flash(f'Προέκυψε σφάλμα κατά την αποθήκευση: {e}', 'danger')
    else:
        flash('Συμπληρώστε όλα τα βασικά πεδία.', 'warning')
        
    return redirect(url_for('arxikh'))
@efarmogi.route('/lixi_xronias/<int:ktima_id>', methods=['POST'])
@login_required
def lixi_xronias(ktima_id):sion.get(Ktima, ktima_id)
    if not ktima or ktima.idiok

    try:
        tonoi_paragogis = float(request.form.get('tonoi_paragogis', 0))
    except ValueError:
        flash('Παρακαλώ εισάγετε έγκυρο αριθμό τόνων.', 'danger')
        return redirect(url_for('arxikh'))
    # 1. Calculate Statsuda
        kila_ana_dentro = (tonoi_paragogis * 1000) / ktima.arithmos_dentron

    # 2. Create Archive Record
   arxeio = ArxeioSygkomidi( l
    )
    vasi.session.add(arxeio)

    # 3. Archive Active Items
    for ergasia in ktima.ergasies:
        ergasia.archived = True
    for exodo in ktima.exoda
ima.id, eidos_ergasias='Ψεκασμός (Χαλκός Μετασυλλεκτικά)', katastasi='Εκκρεμεί', farmaka_lipasmata='Χαλκούχα (Απολύμανση πληγών συγκομιδής)', imerominia=datetime.now())
    vasi.session.add(nea_ergasia)

    ktima.gdd_accumulated = 0.0

    vasi.session.commit()
    flash(f'Η χρονιά έκλεισε επιτυχώς! Απόδοση: {kila_ana_dentro:.2f} kg/δέντρο.', 'success')

@efarmogi.route('/ping')
def ping():
    return "Pong", 200

@efarmogi.route('/icon.svg')
svg = '''<svg xmlns="http://www.w3.og0gw00">
      <rect width="100" height="100" rx="22" fill="#4A7C59"/>
      <text x="50%" y="50%" font-size="55" text-anchor="middle" dominant-baseline="central">🫒</text>
    return Response(svg, mime/svg+xml')

@efarmogi.route('/manifest.json')a()
        "short_name": "Olea",
        "start_url": "/",
        "display": "standalone",
        "background_color": "#f4f7f6",
        "theme_color": "#386641",
        "icons"     s": "any",
                "type": "image/svg+xml"
            }
    })

@efarmogi.route('/sw.js')
def service_worker():
    response = make_response("""
        self.addEventListener('install', (event) => {
            console.log('Service Worker installing.');
        });
    """)
    response.headers['Content-Type'] = 'application/javascript'
    return response

@efarmogi.route('/eksodos')
def eksodos():
    logout_user()
    return redirect(url_for('eisodos'))

@efarmogi.route('/favicon.ico')
def favicon():
    return "", 204

@efarmogi.route('/updb')
def update_db_schema():
    try:
        # Δημιουργία όλων των πινάκων αν δεν υπάρχουν (για περιπτώσεις όπως το Render)
        vasi.create_all()
        
        with vasi.engine.connect() as conn:
            # Προσθήκη fainologiko_stadio
            try:
                conn.execute(text("ALTER TABLE ktimata ADD COLUMN fainologiko_stadio VARCHAR(50) DEFAULT 'Άγνωστο'"))
            except Exception as e:
                print(f"Column fainologiko_stadio exists or error: {e}")
                conn.rollback()

            # Προσθήκη topikes_ergasies
            try:
                conn.execute(text("ALTER TABLE ktimata ADD COLUMN topikes_ergasies TEXT"))
            except Exception as e:
                print(f"Column topikes_ergasies exists or error: {e}")
                conn.rollback()

            # Προσθήκη teleftaia_enimerosi_ergasion
            try:
                conn.execute(text("ALTER TABLE ktimata ADD COLUMN teleftaia_enimerosi_ergasion TIMESTAMP"))
            except Exception as e:
                print(f"Column teleftaia_enimerosi_ergasion exists or error: {e}")
                conn.rollback()
                
            # Προσθήκη nero_ph
            try:
                conn.execute(text("ALTER TABLE ktimata ADD COLUMN nero_ph FLOAT"))
            except Exception as e:
                print(f"Column nero_ph exists or error: {e}")
                conn.rollback()

            # Προσθήκη nero_agwgimotita
            try:
                conn.execute(text("ALTER TABLE ktimata ADD COLUMN nero_agwgimotita FLOAT"))
            except Exception as e:
                print(f"Column nero_agwgimotita exists or error: {e}")
                conn.rollback()
            
            # Προσθήκη gdd_accumulated
            try:
                conn.execute(text("ALTER TABLE ktimata ADD COLUMN gdd_accumulated FLOAT DEFAULT 0.0"))
            except Exception as e:
                print(f"Column gdd_accumulated exists or error: {e}")
                conn.rollback()

            # Προσθήκη polygon_geojson
            try:
                conn.execute(text("ALTER TABLE ktimata ADD COLUMN polygon_geojson TEXT"))
            except Exception as e:
                print(f"Column polygon_geojson exists or error: {e}")
                conn.rollback()
            
            # Προσθήκη agromonitoring_poly_id
            try:
                conn.execute(text("ALTER TABLE ktimata ADD COLUMN agromonitoring_poly_id VARCHAR(100)"))
            except Exception as e:
                print(f"Column agromonitoring_poly_id exists or error: {e}")
                conn.rollback()

            try:
                conn.execute(text("ALTER TABLE ktimata ADD COLUMN ilikia_dentron VARCHAR(50) DEFAULT 'Άγνωστη'"))
                conn.execute(text("ALTER TABLE ktimata ADD COLUMN puknotita_dentron VARCHAR(50) DEFAULT 'Κανονική'"))
                conn.execute(text("ALTER TABLE ktimata ADD COLUMN diacheirisi_edafous VARCHAR(50) DEFAULT 'Άγνωστη'"))
            except Exception as e:
                print(f"New agronomic columns exist or error: {e}")
                conn.rollback()

            try:
                conn.execute(text("ALTER TABLE ktimata ADD COLUMN ekkremis_erotisi_ai TEXT"))
            except Exception as e:
                print(f"ekkremis_erotisi_ai column exists or error: {e}")
                conn.rollback()
            
            # Create table analuseis_edafous if not exists
            vasi.create_all()
            
            conn.commit()
        return "Η βάση δεδομένων ενημερώθηκε επιτυχώς! Τώρα μπορείτε να πάτε στην <a href='/'>Αρχική</a>."
    except Exception as e:
        return f"Σφάλμα κατά την ενημέρωση: {e}", 500

@efarmogi.route('/ping')
def ping_keep_alive():
    return "OK", 200

@efarmogi.route('/ai_vision', methods=['POST'])
@login_required
def ai_vision():
    if not api_key_ai:
        return jsonify({'error': 'Σφάλμα Ρύθμισης: Το AI API Key λείπει από τον server.'}), 503

    if 'image' not in request.files:
        return jsonify({'error': 'Δεν βρέθηκε αρχείο εικόνας'}), 400

    file = request.files['image']
    if file.filename == '':
        return jsonify({'error': 'Δεν επιλέχθηκε αρχείο'}), 400

    try:
        img = PIL.Image.open(file)
        prompt = "Λειτούργησε ως έμπειρος γεωπόνος. Ανάλυσε αυτή την εικόνα και εντόπισε το φαινολογικό στάδιο της ελιάς ή πιθανές ασθένειες."
        
        response = None
        for attempt in range(3):
            try:
                response = ai_client.models.generate_content(model='gemini-2.5-flash', contents=[prompt, img])
                break
            except Exception:
                time.sleep(2)
        
        result_text = response.text if response else "Αδυναμία ανάλυσης."
        return jsonify({'result': result_text})
    except Exception as e:
        return jsonify({'error': f"Σφάλμα AI: {str(e)}"}), 500

@efarmogi.route('/ektyposi_anaforas/<int:ktima_id>')
@login_required
def ektyposi_anaforas(ktima_id):
    ktima = vasi.session.get(Ktima, ktima_id)
    if not ktima or ktima.idioktitis != current_user:
        return "Μη εξουσιοδοτημένη ενέργεια", 403
    return render_template('anafora.html', ktima=ktima)

@efarmogi.route('/apothiki', methods=['GET', 'POST'])
@login_required
def apothiki():
    if request.method == 'POST':
        eidos = request.form.get('eidos')
        onoma_proiontos = request.form.get('onoma_proiontos')
        try:
            posotita = float(request.form.get('posotita'))
        except (ValueError, TypeError):
            flash('Μη έγκυρη ποσότητα.', 'danger')
            return redirect(url_for('apothiki'))
        monada_metrisis = request.form.get('monada_metrisis')
        neo_proion = Apothiki(xrhsths_id=current_user.id, eidos=eidos, onoma_proiontos=onoma_proiontos, posotita=posotita, monada_metrisis=monada_metrisis)
        vasi.session.add(neo_proion)
        vasi.session.commit()
        flash('Το προϊόν προστέθηκε στην αποθήκη!', 'success')
        return redirect(url_for('apothiki'))
    proionta = Apothiki.query.filter_by(xrhsths_id=current_user.id).all()
    return render_template('apothiki.html', proionta=proionta)

@efarmogi.route('/diagrafi_apothikis/<int:item_id>', methods=['POST'])
@login_required
def diagrafi_apothikis(item_id):
    item = vasi.session.get(Apothiki, item_id)
    if item and item.xrhsths_id == current_user.id:
        vasi.session.delete(item)
        vasi.session.commit()
        flash('Το προϊόν διαγράφηκε από την αποθήκη.', 'success')
    return redirect(url_for('apothiki'))

@efarmogi.route('/ndvi_analyze/<int:ktima_id>', methods=['POST'])
@login_required
def ndvi_analyze(ktima_id):
    ktima = vasi.session.get(Ktima, ktima_id)
    if not ktima or ktima.idioktitis != current_user:
        return jsonify({'error': 'Μη εξουσιοδοτημένη ενέργεια'}), 403

    data = request.get_json()
    geo_json = data.get('geo_json')

    api_key = os.getenv('AGROMONITORING_API_KEY')
    if not api_key:
        return jsonify({'error': 'Δεν βρέθηκε το AGROMONITORING_API_KEY στο σύστημα.'}), 500

    try:
        import requests
        import re
        import json
        
        # 1. Register Polygon in Agromonitoring
        poly_url = f"http://api.agromonitoring.com/agro/1.0/polygons?appid={api_key}"
        poly_data = {
            "name": f"Ktima_{ktima.id}_{int(datetime.now().timestamp())}",
            "geo_json": geo_json
        }
        
        # DEBUG PRINT: Print the payload being sent to the terminal
        print(f"--- SENDING TO AGROMONITORING: {poly_data} ---")
        
        poly_res = requests.post(poly_url, json=poly_data)
        
        poly_id = None
        if poly_res.status_code in [200, 201]:
            poly_id = poly_res.json().get('id')
        elif poly_res.status_code == 422 and 'duplicated' in poly_res.text:
            match = re.search(r"polygon '([a-f0-9]+)'", poly_res.text)
            if match:
                poly_id = match.group(1)
            else:
                poly_res = requests.post(poly_url + "&duplicated=true", json=poly_data)
                poly_id = poly_res.json().get('id')
        else:
            # THIS IS THE FIX: Return the EXACT error text from the satellite API
            error_msg = f"Σφάλμα Δορυφόρου ({poly_res.status_code}): {poly_res.text}"
            print(error_msg)
            return jsonify({'error': error_msg}), 400
                
        if not poly_id:
            return jsonify({'error': 'Αποτυχία δημιουργίας πολυγώνου. Ελέγξτε τις συντεταγμένες.'}), 400

        # Save poly_id to database to remember it for future deletion
        if ktima.agromonitoring_poly_id != poly_id:
            ktima.agromonitoring_poly_id = poly_id
            vasi.session.commit()

        # 2. Get NDVI Image for the registered polygon (Look back 365 days)
        # Αφαιρούμε 1 ώρα (3600 sec) για να αποφύγουμε το σφάλμα "end can not be after now" λόγω μικροδιαφορών ώρας
        end_time = int(datetime.now().timestamp()) - 3600
        start_time = end_time - (365 * 24 * 60 * 60) 
        img_url = f"http://api.agromonitoring.com/agro/1.0/image/search?start={start_time}&end={end_time}&polyid={poly_id}&appid={api_key}"
        
        img_res = requests.get(img_url)
        if img_res.status_code == 200:
            images = img_res.json()
            if len(images) > 0:
                for img_data in reversed(images):
                    ndvi_url = img_data.get('image', {}).get('ndvi')
                    if ndvi_url:
                        # HTTPS Fix
                        if ndvi_url.startswith('http:'):
                            ndvi_url = ndvi_url.replace('http:', 'https:')
                
                        ai_message = "Ο δορυφορικός χάρτης NDVI φορτώθηκε επιτυχώς."
                        try:
                            import io
                            import requests
                            import PIL.Image
                            from google import genai
                            
                            img_response = requests.get(ndvi_url)
                            if img_response.status_code == 200:
                                image_file = PIL.Image.open(io.BytesIO(img_response.content))
                                
                                # Use the new google-genai SDK
                                client = genai.Client(api_key=os.getenv('AI_API_KEY'))
                                prompt = f"""Είσαι εξειδικευμένος γεωπόνος Γεωργίας Ακριβείας. Αυτός είναι ένας δορυφορικός χάρτης NDVI ελαιώνα. 
Δεδομένα κτήματος: 
- Ηλικία δέντρων: {ktima.ilikia_dentron}
- Πυκνότητα φύτευσης: {ktima.puknotita_dentron}
- Κάλυψη/Διαχείριση εδάφους: {ktima.diacheirisi_edafous}

Το έντονο πράσινο σημαίνει υψηλή φωτοσύνθεση. Λάβε υπόψη σου τα χαρακτηριστικά (π.χ. νεαρά δέντρα ή αραιή φύτευση αφήνουν ορατό γυμνό έδαφος ρίχνοντας τον μέσο όρο NDVI, ενώ αν υπάρχει φυσική βλάστηση/ζιζάνια μπορεί να δώσουν ψευδές έντονο πράσινο). Γράψε μια επαγγελματική, στοχευμένη εκτίμηση (2-3 προτάσεις) για την υγεία του κτήματος και τι πρέπει να προσέξει ο παραγωγός."""
                                
                                response = client.models.generate_content(
                                    model='gemini-2.5-flash',
                                    contents=[prompt, image_file]
                                )
                                ai_message = response.text.strip()
                        except Exception as e:
                            print(f"Gemini NDVI Vision Error: {e}")

                        # Save the diagnosis to the database
                        nea_diagnosi = Diagnosi(ktima_id=ktima.id, apotelesma=f"🛰️ Δορυφόρος (NDVI): {ai_message}", imerominia=datetime.now())
                        vasi.session.add(nea_diagnosi)
                        vasi.session.commit()

                        return jsonify({'ndvi_url': ndvi_url, 'ai_message': ai_message})
                
                return jsonify({'error': 'Βρέθηκαν λήψεις, αλλά καμία δεν είχε έτοιμο χάρτη NDVI.'}), 404
            else:
                return jsonify({'error': 'Ο δορυφόρος δεν έχει περάσει ακόμα πάνω από αυτό το σημείο.'}), 404
        else:
            return jsonify({'error': f'Σφάλμα αναζήτησης εικόνων. Κωδικός: {img_res.status_code}'}), 500
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@efarmogi.route('/ndvi_chat/<int:ktima_id>', methods=['POST'])
@login_required
def ndvi_chat(ktima_id):
    ktima = vasi.session.get(Ktima, ktima_id)
    if not ktima or ktima.idioktitis != current_user:
        return jsonify({'error': 'Μη εξουσιοδοτημένη ενέργεια'}), 403

    data = request.get_json()
    user_reply = data.get('user_reply')
    previous_ai_message = data.get('previous_ai_message')

    try:
        from google import genai
        import os
        from datetime import datetime
        client = genai.Client(api_key=os.getenv('AI_API_KEY'))
        
        prompt = f"Είσαι ο γεωπόνος του Olea AI. Νωρίτερα έδωσες αυτή την εκτίμηση από δορυφόρο για έναν ελαιώνα: '{previous_ai_message}'. Ο παραγωγός μόλις σου διευκρίνισε το εξής: '{user_reply}'. Με βάση αυτή τη νέα πληροφορία, δώσε μια τελική, επαγγελματική και σύντομη συμβουλή (1-2 προτάσεις) για το τι πρέπει να κάνει."

        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt
        )
        refined_message = response.text.strip()
        
        # Save the refined diagnosis
        nea_diagnosi = Diagnosi(ktima_id=ktima.id, apotelesma=f"🗣️ Διευκρίνιση: {user_reply} | 🤖 Τελική Συμβουλή AI: {refined_message}", imerominia=datetime.now())
        vasi.session.add(nea_diagnosi)
        vasi.session.commit()

        return jsonify({'refined_message': refined_message})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@efarmogi.route('/apantisi_sto_ai/<int:ktima_id>', methods=['POST'])
@login_required
def apantisi_sto_ai(ktima_id):
    ktima = vasi.session.get(Ktima, ktima_id)
    if not ktima or ktima.idioktitis != current_user: 
        return redirect(url_for('arxikh'))

    user_reply = request.form.get('user_reply')
    erotisi = ktima.ekkremis_erotisi_ai

    try:
        from google import genai
        import os
        from datetime import datetime
        client = genai.Client(api_key=os.getenv('AI_API_KEY'))
        prompt = f"Είσαι γεωπόνος. Ρώτησες τον αγρότη: '{erotisi}'. Ο αγρότης σου απάντησε: '{user_reply}'. Βγάλε ένα τελικό, καθησυχαστικό ή συμβουλευτικό πόρισμα (1-2 προτάσεις)."
        response = client.models.generate_content(model='gemini-2.5-flash', contents=prompt)

        nea_diagnosi = Diagnosi(ktima_id=ktima.id, apotelesma=f"🤖 Απάντηση Αγρότη: {user_reply} | 🛰️ Τελικό Πόρισμα: {response.text.strip()}", imerominia=datetime.now())
        vasi.session.add(nea_diagnosi)
        ktima.ekkremis_erotisi_ai = None
        vasi.session.commit()
        flash('Η απάντησή σας δόθηκε στο AI και το πόρισμα αποθηκεύτηκε!', 'success')
    except Exception as e:
        flash(f'Σφάλμα επικοινωνίας με το AI: {e}', 'danger')

    return redirect(url_for('arxikh'))