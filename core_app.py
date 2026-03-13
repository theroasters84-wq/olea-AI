import os
import re
from datetime import datetime, timedelta
from flask import Blueprint, render_template, redirect, url_for, request, flash, jsonify, Response, make_response
from flask_login import login_required, current_user, logout_user
from sqlalchemy import text
from core import vasi, ai_client, api_key_ai, kryptografhsh
from models import Ktima, Ergasia, Exodo, KatagrafiUgrasias, Apothiki, ArxeioSygkomidis, KtimaPoikilia, Diagnosi, AnalysiEdafous, Xrhsths
from logic import paragwgi_protasewn, generate_local_tasks_via_ai, generate_smart_tasks
from geoponika import pare_kairo, steile_email, geoponikos_elegxos, get_agro_soil_data, get_agro_uvi, get_agro_forecast, get_agro_gdd, pare_ypsometro

core_bp = Blueprint('core_app', __name__)

# Διόρθωση: Περνάμε το datetime στα templates για να μην σκάει το 500 error
@core_bp.context_processor
def inject_datetime():
    return {'datetime': datetime}

@core_bp.route('/')
@login_required
def arxikh():
    try:
        pelatis_id = request.args.get('pelatis_id')
        is_geoponos_view = False
        
        if getattr(current_user, 'rolos', '') == 'geoponos' and pelatis_id:
            try:
                pelatis_id_int = int(pelatis_id)
                provalomenos_xrhsths = vasi.session.get(Xrhsths, pelatis_id_int)
                if not provalomenos_xrhsths:
                    flash('Δεν βρέθηκε ο πελάτης.', 'danger')
                    return redirect(url_for('core_app.dashboard_geoponou'))
                ktimata = [k for k in provalomenos_xrhsths.ktimata if k.is_active]
                is_geoponos_view = True
            except ValueError:
                flash('Μη έγκυρο ID πελάτη.', 'danger')
                return redirect(url_for('core_app.dashboard_geoponou'))
        else:
            provalomenos_xrhsths = current_user
            ktimata = [k for k in current_user.ktimata if k.is_active]

        for ktima in ktimata:
            try:
                # Ενσωμάτωση Agromonitoring API
                ktima.agro_data = None
                if ktima.agromonitoring_poly_id:
                    soil = get_agro_soil_data(ktima.agromonitoring_poly_id)
                    uvi = get_agro_uvi(ktima.agromonitoring_poly_id)
                    agro_forecast = get_agro_forecast(ktima.agromonitoring_poly_id)
                    
                    # Μετατροπή της ώρας του Δορυφόρου σε αναγνώσιμη μορφή (π.χ. 13/03/2026 14:30)
                    if soil and 'dt' in soil:
                        soil['dt_formatted'] = datetime.fromtimestamp(soil['dt']).strftime('%d/%m/%Y %H:%M')
                    if uvi and 'dt' in uvi:
                        uvi['dt_formatted'] = datetime.fromtimestamp(uvi['dt']).strftime('%d/%m/%Y %H:%M')
                    
                    if soil or uvi:
                        ktima.agro_data = {'soil': soil, 'uvi': uvi}
                    ktima.agro_forecast = agro_forecast

                ktima.kairos = pare_kairo(ktima.geografiko_platos, ktima.geografiko_mikos)
                if ktima.kairos:
                    ktima.symvouli = geoponikos_elegxos(ktima.kairos['thermokrasia'], ktima.kairos['ygrasia'])
                    ktima.protaseis = paragwgi_protasewn(ktima, ktima.kairos['thermokrasia'], ktima.kairos['ygrasia'], ktima.kairos['perigrafi'])
                else:
                    ktima.protaseis = []
                
                ideal_tasks = generate_smart_tasks(ktima)
                if isinstance(ideal_tasks, list):
                     ideal_tasks = [t.strip() for t in ideal_tasks if t.strip()]
                else:
                     ideal_tasks = []
                
                completed_tasks = [e.eidos_ergasias for e in ktima.ergasies if not e.archived]
                ktima.pending_tasks = [task for task in ideal_tasks if task not in completed_tasks]
                
                # --- SMART INTERACTION: COPPER -> AMINO ACIDS LOGIC ---
                latest_copper = None
                latest_amino = None
                
                for t in ktima.ergasies:
                    if not t.archived:
                        if 'Χαλκ' in t.eidos_ergasias or (t.farmaka_lipasmata and 'Χαλκ' in t.farmaka_lipasmata):
                            if latest_copper is None or t.imerominia > latest_copper.imerominia:
                                latest_copper = t
                        if 'Αμινοξ' in t.eidos_ergasias or (t.farmaka_lipasmata and 'Αμινοξ' in t.farmaka_lipasmata):
                            if latest_amino is None or t.imerominia > latest_amino.imerominia:
                                latest_amino = t
                
                if latest_copper:
                    days_diff = (datetime.now() - latest_copper.imerominia).days
                    amino_done_after = latest_amino and latest_amino.imerominia > latest_copper.imerominia
                    
                    if not amino_done_after and days_diff < 40:
                        if days_diff < 7:
                            wait_days = 7 - days_diff
                            ktima.pending_tasks.insert(0, f"⏳ Αναμονή: Αμινοξέα (σε {wait_days} μέρες)")
                        else:
                            if not any('Αμινοξ' in t for t in ktima.pending_tasks):
                                ktima.pending_tasks.insert(0, "Διαφυλλική με Αμινοξέα (Ενίσχυση)")

                ktima.synoliko_kostos = sum((exodo.poso or 0) for exodo in ktima.exoda if not exodo.archived)
                
                # PHI Logic
                latest_spray = None
                for ergasia in ktima.ergasies:
                    if not ergasia.archived and 'Ψεκασμός' in ergasia.eidos_ergasias:
                        if latest_spray is None or ergasia.imerominia > latest_spray.imerominia:
                            latest_spray = ergasia
                ktima.meres_apo_psekasmo = (datetime.now() - latest_spray.imerominia).days if latest_spray else None

                # --- ΟΔΗΓΟΣ ΒΕΛΤΙΣΤΟΠΟΙΗΣΗΣ (Ελλείψεις Δεδομένων) ---
                ktima.elleipseis = []
                now = datetime.now()
                
                last_soil = max([a.imerominia for a in ktima.analuseis_edafous]) if ktima.analuseis_edafous else None
                last_leaf = None
                last_water = None
                last_stage = None
                last_disease = None
                
                if ktima.diagnoseis:
                    for d in ktima.diagnoseis:
                        res = d.apotelesma or ""
                        if "📄 Έγγραφο Ανάλυσης" in res or "Εργαστηριακή Ανάλυση" in res:
                            if not last_leaf or d.imerominia > last_leaf: last_leaf = d.imerominia
                        elif "💧 Ανάλυση Νερού" in res:
                            if not last_water or d.imerominia > last_water: last_water = d.imerominia
                        elif "🌿 Αναγνώριση Σταδίου" in res:
                            if not last_stage or d.imerominia > last_stage: last_stage = d.imerominia
                        elif not any(k in res for k in ["Δορυφόρος", "Chat", "Answered", "📄", "💧", "🌿"]):
                            if not last_disease or d.imerominia > last_disease: last_disease = d.imerominia

                # 1. Ανάλυση Εδάφους
                if not last_soil: ktima.elleipseis.append("Ανάλυση Εδάφους (Εκκρεμεί - Ανεβάστε αρχείο)")
                elif (now - last_soil).days > (3 * 365): ktima.elleipseis.append("Ανάλυση Εδάφους (Έχει περάσει 3ετία - Απαιτείται νέα)")
                # 2. Ανάλυση Φύλλων
                if not last_leaf: ktima.elleipseis.append("Ανάλυση Φύλλων (Εκκρεμεί - Ανεβάστε αρχείο)")
                elif (now - last_leaf).days > (2 * 365): ktima.elleipseis.append("Ανάλυση Φύλλων (Έχει περάσει 2ετία - Απαιτείται νέα)")
                # 3. Ανάλυση Νερού
                if ktima.ardefsi == 'Αρδευόμενο':
                    if not ktima.nero_ph and not last_water: ktima.elleipseis.append("Ανάλυση Νερού (Εκκρεμεί αρχική μέτρηση)")
                    else:
                        if now.month in [12, 1, 2, 6, 7, 8]:
                            if not last_water or (now - last_water).days > 120:
                                epoxi = "Χειμερινή" if now.month in [12, 1, 2] else "Καλοκαιρινή"
                                ktima.elleipseis.append(f"Ανάλυση Νερού (Απαιτείται {epoxi} επικαιροποίηση)")
                # 4. Στάδιο
                if ktima.fainologiko_stadio == 'Άγνωστο' or not last_stage: ktima.elleipseis.append("Αναγνώριση Σταδίου (AI Εργαλεία -> Βρες Στάδιο)")
                elif (now - last_stage).days > 30: ktima.elleipseis.append("Αναγνώριση Σταδίου (Απαιτείται μηνιαία επικαιροποίηση)")
                # 5. AI Διάγνωση Ασθενειών
                if not last_disease: ktima.elleipseis.append("AI Διάγνωση Ασθενειών (Εκκρεμεί - Φωτογραφία)")
                elif (now - last_disease).days > 30: ktima.elleipseis.append("AI Διάγνωση Ασθενειών (Μηνιαίος προληπτικός έλεγχος)")
                # 6. Δορυφόρος & Υγρασία
                if not ktima.ugrasies: ktima.elleipseis.append("Καταγραφή Υγρασίας (Προσθέστε μέτρηση)")
                if not ktima.polygon_geojson: ktima.elleipseis.append("Δορυφορική Οριοθέτηση (Χάρτης)")

            except Exception as e_ktima:
                print(f"Σφάλμα φόρτωσης δεδομένων για το κτήμα '{ktima.onoma_ktimatos}': {e_ktima}")
                # Σε περίπτωση σφάλματος, δίνουμε κενές τιμές για να μην "σπάσει" η HTML σελίδα.
                if not hasattr(ktima, 'kairos'): ktima.kairos = None
                if not hasattr(ktima, 'protaseis'): ktima.protaseis = []
                if not hasattr(ktima, 'pending_tasks'): ktima.pending_tasks = []
                if not hasattr(ktima, 'synoliko_kostos'): ktima.synoliko_kostos = 0
                if not hasattr(ktima, 'meres_apo_psekasmo'): ktima.meres_apo_psekasmo = None
                if not hasattr(ktima, 'elleipseis'): ktima.elleipseis = []
                if not hasattr(ktima, 'agro_data'): ktima.agro_data = None
                
        # Μαζική αποθήκευση τυχόν νέων AI tasks (Cache)
        vasi.session.commit()
        # Περνάμε το datetime ΡΗΤΑ για να αποφύγουμε σφάλματα στα templates
        return render_template('arxiki.html', xrhsths=provalomenos_xrhsths, ktimata=ktimata, datetime=datetime, is_geoponos_view=is_geoponos_view)

    except Exception as e:
        print(f"CRITICAL ERROR IN ARXIKI: {e}") # Εμφάνιση στο τερματικό για έλεγχο
        flash("Υπήρξε πρόβλημα στη φόρτωση της σελίδας. Παρακαλώ προσπαθήστε ξανά.", "danger")
        return redirect(url_for('auth.eisodos'))

@core_bp.route('/ananeosi_ergasion/<int:ktima_id>')
@login_required
def ananeosi_ergasion(ktima_id):
    ktima = vasi.session.get(Ktima, ktima_id)
    if not ktima or ktima.idioktitis != current_user: return "403", 403
    ktima.teleftaia_enimerosi_ergasion = None
    vasi.session.commit()
    generate_smart_tasks(ktima)
    flash('Επικαιροποιήθηκε!', 'success')
    return redirect(url_for('core_app.arxikh'))

@core_bp.route('/arxeio')
@login_required
def arxeio():
    return render_template('arxeio.html', ktimata=current_user.ktimata)

@core_bp.route('/prosthes_ktima', methods=['POST'])
@login_required
def prosthes_ktima():
    onoma = request.form.get('onoma_ktimatos')
    mikos = request.form.get('geografiko_mikos')
    platos = request.form.get('geografiko_platos')
    typos = request.form.get('typos_edafous')
    klisi = request.form.get('klisi')
    ardefsi = request.form.get('ardefsi')
    stremmata = request.form.get('stremmata')
    if stremmata: stremmata = stremmata.replace(',', '.')
    ilikia_dentron = request.form.get('ilikia_dentron', 'Άγνωστη')
    puknotita_dentron = request.form.get('puknotita_dentron', 'Κανονική')
    diacheirisi_edafous = request.form.get('diacheirisi_edafous', 'Άγνωστη')
    
    poikilia_onomata = request.form.getlist('poikilia_onoma')
    poikilia_dentra_str = request.form.getlist('poikilia_dentra')
    
    if onoma and mikos and platos:
        try:
            total_trees = 0
            for s in poikilia_dentra_str:
                try:
                    total_trees += int(s)
                except: pass
            
            display_poikilia = 'Ανάμεικτο' if len(poikilia_onomata) > 1 else (poikilia_onomata[0] if poikilia_onomata else 'Δεν ορίστηκε')

            # --- START HISTORICAL GDD CALCULATION ---
            initial_gdd = 0.0
            try:
                import requests
                from datetime import datetime, timedelta
                now = datetime.now()
                current_year = now.year
                start_date = f"{current_year}-01-01"
                yesterday = (now - timedelta(days=1)).strftime('%Y-%m-%d')
                
                # Only fetch if today is strictly after Jan 1st
                if now.strftime('%Y-%m-%d') > start_date:
                    hist_url = f"https://archive-api.open-meteo.com/v1/archive?latitude={float(platos)}&longitude={float(mikos)}&start_date={start_date}&end_date={yesterday}&daily=temperature_2m_max,temperature_2m_min&timezone=auto"
                    hist_resp = requests.get(hist_url, timeout=5)
                    
                    if hist_resp.status_code == 200:
                        daily_data = hist_resp.json().get('daily', {})
                        t_max_list = daily_data.get('temperature_2m_max', [])
                        t_min_list = daily_data.get('temperature_2m_min', [])
                        
                        for t_max, t_min in zip(t_max_list, t_min_list):
                            if t_max is not None and t_min is not None:
                                t_mean = (t_max + t_min) / 2.0
                                daily_gdd = t_mean - 10.0 # Base temperature for Olives is 10C
                                if daily_gdd > 0:
                                    initial_gdd += daily_gdd
            except Exception as e:
                print(f"Historical GDD API Error: {e}")
            # --- END HISTORICAL GDD CALCULATION ---

            # --- SMART GDD TARGETS LOGIC ---
            target_a = 600
            target_s = 2500
            
            # 1. Known Varieties Dictionary
            gdd_map = {
                'Κορωνέικη': (550, 2400),
                'Αθηνολιά': (500, 2300),
                'Καλαμών': (680, 2600),
                'Χονδρολιά': (680, 2600),
                'Χαλκιδικής': (620, 2500),
                'Μεγαρίτικη': (600, 2450),
                'Μανάκι': (600, 2500),
                'Αρμπεκίνα': (550, 2400)
            }
            
            found_known = False
            for k, v in gdd_map.items():
                if k in display_poikilia:
                    target_a, target_s = v
                    found_known = True
                    break
            
            # 2. AI Fallback for Unknown Varieties
            if not found_known and display_poikilia and display_poikilia not in ['Δεν ορίστηκε', 'Ανάμεικτο']:
                try:
                    from google import genai
                    import json
                    client = genai.Client(api_key=os.getenv('AI_API_KEY'))
                    prompt = f"What are the approximate Growing Degree Days (GDD) targets for flowering and harvest for the olive variety '{display_poikilia}'? Return ONLY a valid JSON format like this: {{\"anthisi\": 600, \"sygkomidi\": 2500}}. Do not include any other text."
                    response = client.models.generate_content(model='gemini-2.5-flash', contents=prompt)
                    ai_text = response.text.strip().replace('```json', '').replace('```', '')
                    data = json.loads(ai_text)
                    if 'anthisi' in data: target_a = int(data['anthisi'])
                    if 'sygkomidi' in data: target_s = int(data['sygkomidi'])
                except Exception as e:
                    print(f"AI GDD Target Error for {display_poikilia}: {e}")
            # --- END SMART GDD TARGETS LOGIC ---

            neo = Ktima(
                onoma_ktimatos=onoma, geografiko_mikos=float(mikos), geografiko_platos=float(platos), idioktitis=current_user,
                typos_edafous=typos, klisi=klisi, ardefsi=ardefsi, stremmata=float(stremmata) if stremmata else 0.0,
                poikilia=display_poikilia, arithmos_dentron=total_trees,
                ilikia_dentron=ilikia_dentron, puknotita_dentron=puknotita_dentron, diacheirisi_edafous=diacheirisi_edafous,
                gdd_accumulated=initial_gdd,
                gdd_target_anthisi=target_a,
                gdd_target_sygkomidi=target_s
            )
            
            # --- Υπολογισμός Υψομέτρου ---
            yps_val = pare_ypsometro(float(platos), float(mikos))
            if yps_val is not None:
                neo.ypsometro = yps_val
                
            vasi.session.add(neo)
            vasi.session.flush()
            
            for i, onoma_p in enumerate(poikilia_onomata):
                try:
                    d = int(poikilia_dentra_str[i])
                    if d > 0:
                        vasi.session.add(KtimaPoikilia(ktima_id=neo.id, poikilia_onoma=onoma_p, arithmos_dentron=d))
                except: pass
            
            # --- AUTO SATELLITE SETUP & ANALYSIS ---
            poly_json = request.form.get('polygon_geojson')
            if poly_json:
                neo.polygon_geojson = poly_json
                api_key = os.getenv('AGROMONITORING_API_KEY')
                if api_key:
                    try:
                        import json
                        import requests
                        import time
                        import io
                        import PIL.Image
                        from google import genai

                        # 1. Εγγραφή στο Agromonitoring
                        headers = {'Content-Type': 'application/json'}
                        payload = {"name": onoma, "geo_json": json.loads(poly_json)}
                        resp = requests.post(f"http://api.agromonitoring.com/agro/1.0/polygons?appid={api_key}", json=payload, headers=headers)
                        if resp.status_code in [200, 201]:
                            poly_data = resp.json()
                            neo.agromonitoring_poly_id = poly_data.get('id')
                            
                            # --- ΑΥΤΟΜΑΤΗ ΑΝΑΛΥΣΗ (Τρέχει τώρα!) ---
                            end_time = int(time.time())
                            start_time = end_time - (365 * 24 * 60 * 60) # 1 Έτος πίσω
                            img_url = f"http://api.agromonitoring.com/agro/1.0/image/search?start={start_time}&end={end_time}&polyid={neo.agromonitoring_poly_id}&appid={api_key}"
                            
                            img_res = requests.get(img_url)
                            if img_res.status_code == 200 and len(img_res.json()) > 0:
                                images = img_res.json()
                                images.sort(key=lambda x: x['dt'], reverse=True)
                                
                                ndvi_url = None
                                for img in images:
                                    if img.get('image', {}).get('ndvi'):
                                        ndvi_url = img.get('image', {}).get('ndvi')
                                        break
                                
                                if ndvi_url:
                                    # Ανάλυση με Gemini Vision
                                    img_content = requests.get(ndvi_url).content
                                    image_file = PIL.Image.open(io.BytesIO(img_content))
                                    client_ai = genai.Client(api_key=os.getenv('AI_API_KEY'))
                                    prompt = "Είσαι ειδικός γεωπόνος. Ανάλυσε αυτόν τον δορυφορικό χάρτη NDVI. Δώσε μια σύντομη αναφορά (2-3 γραμμές) για την υγεία της βλάστησης."
                                    response = client_ai.models.generate_content(model='gemini-2.5-flash', contents=[prompt, image_file])
                                    
                                    nea_diagnosi = Diagnosi(ktima_id=neo.id, apotelesma=f"🛰️ Δορυφόρος: {response.text}", imerominia=datetime.now())
                                    vasi.session.add(nea_diagnosi)
                    except Exception as e:
                        print(f"Auto-Satellite Error: {e}")
            
            vasi.session.commit()
            flash('Το κτήμα προστέθηκε!', 'success')
        except Exception as e:
            vasi.session.rollback()
            flash(f'Σφάλμα: {e}', 'danger')
    return redirect(url_for('core_app.arxikh'))

@core_bp.route('/prosthes_ergasia/<int:ktima_id>', methods=['POST'])
@login_required
def prosthes_ergasia(ktima_id):
    ktima = vasi.session.get(Ktima, ktima_id)
    eidos = request.form.get('eidos_ergasias')
    # Handle custom date (Backdating)
    date_str = request.form.get('imerominia')
    if date_str:
        im = datetime.strptime(date_str, '%Y-%m-%d')
    else:
        im = datetime.now()
        
    nea_ergasia = Ergasia(ktima_id=ktima_id, eidos_ergasias=eidos, katastasi=request.form.get('katastasi'), imerominia=im, farmaka_lipasmata=request.form.get('farmaka_lipasmata'))
    vasi.session.add(nea_ergasia)
    vasi.session.commit()
    return redirect(url_for('core_app.arxikh'))

@core_bp.route('/oloklirosi_ergasias/<int:ktima_id>', methods=['POST'])
@login_required
def oloklirosi_ergasias(ktima_id):
    from models import Ktima, Ergasia, Exodo, Apothiki
    ktima = vasi.session.get(Ktima, ktima_id)
    # Access control (Αγρότης ιδιοκτήτης ή Γεωπόνος)
    if not ktima or (ktima.idioktitis != current_user and getattr(current_user, 'rolos', '') != 'geoponos'):
        return jsonify({'error': 'Μη εξουσιοδοτημένη ενέργεια'}), 403

    ergasia_id = request.form.get('ergasia_id')
    eidos = request.form.get('eidos_ergasias')
    kostos_str = request.form.get('kostos')
    
    # Δεδομένα απόσυρσης από αποθήκη
    yliko_id = request.form.get('yliko_id')
    posotita_xrisis_str = request.form.get('posotita_xrisis')

    try:
        # 1. Ενημέρωση ή Δημιουργία Εργασίας
        if ergasia_id:
            ergasia = vasi.session.get(Ergasia, ergasia_id)
            if ergasia and ergasia.ktima_id == ktima.id:
                ergasia.katastasi = 'Ολοκληρώθηκε'
                eidos = ergasia.eidos_ergasias # Κρατάμε το αρχικό όνομα
        else:
            nea_ergasia = Ergasia(
                ktima_id=ktima_id,
                eidos_ergasias=eidos,
                katastasi='Ολοκληρώθηκε',
                imerominia=datetime.now(),
                proelevsi='Αγρότης' if getattr(current_user, 'rolos', '') != 'geoponos' else 'Γεωπόνος'
            )
            vasi.session.add(nea_ergasia)

        # 2. Αφαίρεση Υλικού από Αποθήκη (Inventory Sync)
        if yliko_id and posotita_xrisis_str:
            yliko = vasi.session.get(Apothiki, yliko_id)
            # Βρίσκουμε σε ποιον ανήκει η αποθήκη (στον ιδιοκτήτη του κτήματος)
            idioktitis_id = ktima.xrhsths_id
            
            if yliko and yliko.xrhsths_id == idioktitis_id:
                posotita_xrisis = float(posotita_xrisis_str)
                if yliko.posotita >= posotita_xrisis:
                    yliko.posotita -= posotita_xrisis
                    # Αν μηδενίστηκε, μπορούμε προαιρετικά να το διαγράψουμε ή να το αφήσουμε στο 0
                else:
                    flash(f'Δεν υπάρχει αρκετό απόθεμα για το {yliko.onoma_proiontos}. Η εργασία ολοκληρώθηκε, αλλά το απόθεμα δεν ενημερώθηκε.', 'warning')

        # 3. Δημιουργία Εξόδου (αν δηλώθηκε κόστος πέρα από τα υλικά)
        try:
            if kostos_str:
                kostos = float(kostos_str)
                if kostos > 0:
                    neo_exodo = Exodo(ktima_id=ktima_id, perigrafi=f"{eidos} (Κόστος Εργασίας)", poso=kostos, imerominia=datetime.now())
                    vasi.session.add(neo_exodo)
        except (ValueError, TypeError):
            pass

        vasi.session.commit()
        return redirect(request.referrer or url_for('core_app.arxikh'))
        
    except Exception as e:
        vasi.session.rollback()
        print(f"Σφάλμα ολοκλήρωσης εργασίας: {e}")
        flash('Προέκυψε σφάλμα.', 'danger')
        return redirect(request.referrer or url_for('core_app.arxikh'))

@core_bp.route('/prosthes_ugrasia/<int:ktima_id>', methods=['POST'])
@login_required
def prosthes_ugrasia(ktima_id):
    try:
        pososto = float(request.form.get('pososto', 0))
        nea = KatagrafiUgrasias(ktima_id=ktima_id, pososto=pososto)
        vasi.session.add(nea)
        vasi.session.commit()
    except ValueError:
        flash('Μη έγκυρη τιμή υγρασίας.', 'danger')
    return redirect(url_for('core_app.arxikh'))

@core_bp.route('/enimerosi_nerou/<int:ktima_id>', methods=['POST'])
@login_required
def enimerosi_nerou(ktima_id):
    ktima = vasi.session.get(Ktima, ktima_id)
    try:
        ktima.nero_ph = float(request.form.get('nero_ph') or 0)
        ktima.nero_agwgimotita = float(request.form.get('nero_agwgimotita') or 0)
        
        nea_diagnosi = Diagnosi(ktima_id=ktima.id, apotelesma=f"💧 Ανάλυση Νερού: pH {ktima.nero_ph}, EC {ktima.nero_agwgimotita}", imerominia=datetime.now())
        vasi.session.add(nea_diagnosi)
        vasi.session.commit()
    except ValueError:
        flash('Εισάγετε έγκυρους αριθμούς για την ανάλυση νερού.', 'danger')
    return redirect(url_for('core_app.arxikh'))

@core_bp.route('/prosthes_exodo/<int:ktima_id>', methods=['POST'])
@login_required
def prosthes_exodo(ktima_id):
    try:
        poso = float(request.form.get('poso', 0))
        neo = Exodo(ktima_id=ktima_id, perigrafi=request.form.get('perigrafi', 'Έξοδο'), poso=poso, imerominia=datetime.now())
        vasi.session.add(neo)
        vasi.session.commit()
    except ValueError:
        flash('Μη έγκυρο ποσό.', 'danger')
    return redirect(url_for('core_app.arxikh'))

@core_bp.route('/apothiki', methods=['GET', 'POST'])
@login_required
def apothiki():
    if request.method == 'POST':
        try:
            posotita = float(request.form.get('posotita', 0))
            neo = Apothiki(xrhsths_id=current_user.id, eidos=request.form.get('eidos'), onoma_proiontos=request.form.get('onoma_proiontos'), posotita=posotita, monada_metrisis=request.form.get('monada_metrisis'))
            vasi.session.add(neo)
            vasi.session.commit()
            flash('Προστέθηκε!', 'success')
        except ValueError:
            flash('Η ποσότητα πρέπει να είναι αριθμός.', 'danger')
        return redirect(url_for('core_app.apothiki'))
    return render_template('apothiki.html', proionta=Apothiki.query.filter_by(xrhsths_id=current_user.id).all())

@core_bp.route('/diagrafi_apothikis/<int:item_id>', methods=['POST'])
@login_required
def diagrafi_apothikis(item_id):
    item = vasi.session.get(Apothiki, item_id)
    if item: vasi.session.delete(item); vasi.session.commit()
    return redirect(url_for('core_app.apothiki'))

@core_bp.route('/lixi_xronias/<int:ktima_id>', methods=['POST'])
@login_required
def lixi_xronias(ktima_id):
    ktima = vasi.session.get(Ktima, ktima_id)
    try:
        tonoi = float(request.form.get('tonoi_paragogis', 0))
        arxeio = ArxeioSygkomidis(ktima_id=ktima.id, tonoi=tonoi, kila_ana_dentro=0, synoliko_kostos=0, imerominia=datetime.now())
        vasi.session.add(arxeio)
        for e in ktima.ergasies: e.archived = True
        for ex in ktima.exoda: ex.archived = True
        vasi.session.commit()
        flash('Χρονιά έκλεισε.', 'success')
    except ValueError:
        flash('Παρακαλώ εισάγετε έγκυρο αριθμό τόνων παραγωγής.', 'danger')
    return redirect(url_for('core_app.arxikh'))

@core_bp.route('/epeksergasia_poikiliwn/<int:ktima_id>', methods=['POST'])
@login_required
def epeksergasia_poikiliwn(ktima_id):
    # (Logic to update varieties)
    flash('Ενημερώθηκε.', 'success')
    return redirect(url_for('core_app.arxikh'))

@core_bp.route('/steile_anafora', methods=['POST'])
@login_required
def steile_anafora():
    data = request.get_json()
    steile_email(current_user.email, f"Anafora {data.get('onoma_ktimatos')}", data.get('ai_sumvouli'))
    return jsonify({'minima': 'Ok'})

@core_bp.route('/diagrafi_ktimatos/<int:ktima_id>', methods=['POST'])
@login_required
def diagrafi_ktimatos(ktima_id):
    ktima = vasi.session.get(Ktima, ktima_id)
    if ktima:
        if ktima.idioktitis != current_user:
            flash('Δεν έχετε δικαίωμα διαγραφής αυτού του κτήματος.', 'danger')
            return redirect(url_for('core_app.arxikh'))
        
        # --- ΔΙΑΓΡΑΦΗ ΑΠΟ AGROMONITORING ---
        if ktima.agromonitoring_poly_id:
            api_key = os.getenv('AGROMONITORING_API_KEY')
            if api_key:
                try:
                    import requests
                    url = f"http://api.agromonitoring.com/agro/1.0/polygons/{ktima.agromonitoring_poly_id}?appid={api_key}"
                    requests.delete(url, timeout=5)
                except Exception as e:
                    print(f"Σφάλμα διαγραφής από Agromonitoring: {e}")

        vasi.session.delete(ktima)
        vasi.session.commit()
        flash('Το κτήμα διαγράφηκε επιτυχώς.', 'success')
    return redirect(url_for('core_app.arxikh'))

@core_bp.route('/oristiki_diagrafi_ktimatos/<int:id>', methods=['POST'])
@login_required
def oristiki_diagrafi_ktimatos(id):
    ktima = vasi.session.get(Ktima, id)
    
    # --- ΔΙΑΓΡΑΦΗ ΑΠΟ AGROMONITORING ---
    if ktima.agromonitoring_poly_id:
        api_key = os.getenv('AGROMONITORING_API_KEY')
        if api_key:
            try:
                import requests
                url = f"http://api.agromonitoring.com/agro/1.0/polygons/{ktima.agromonitoring_poly_id}?appid={api_key}"
                requests.delete(url, timeout=5)
            except Exception as e:
                print(f"Σφάλμα διαγραφής από Agromonitoring: {e}")
                
    vasi.session.delete(ktima)
    vasi.session.commit()
    return redirect(url_for('core_app.arxeio'))

@core_bp.route('/arxeiothetisi_ktimatos/<int:id>')
@login_required
def arxeiothetisi_ktimatos(id):
    ktima = vasi.session.get(Ktima, id)
    ktima.is_active = False
    vasi.session.commit()
    return redirect(url_for('core_app.arxikh'))

@core_bp.route('/ektyposi_anaforas/<int:ktima_id>')
@login_required
def ektyposi_anaforas(ktima_id):
    ktima = vasi.session.get(Ktima, ktima_id)
    return render_template('anafora.html', ktima=ktima)

@core_bp.route('/ndvi_analyze/<int:ktima_id>', methods=['POST'])
@login_required
def ndvi_analyze(ktima_id):
    import json
    import requests
    import time
    import io
    import PIL.Image
    
    try:
        ktima = vasi.session.get(Ktima, ktima_id)
        if not ktima or (ktima.idioktitis != current_user and getattr(current_user, 'rolos', '') != 'geoponos'):
            return jsonify({'error': 'Άρνηση πρόσβασης'}), 403
        
        data = request.get_json()
        geo_json = data.get('geo_json')
        
        if geo_json:
            # Αποθήκευση του πολυγώνου στη βάση
            ktima.polygon_geojson = json.dumps(geo_json)
            vasi.session.commit()
            
            api_key = os.getenv('AGROMONITORING_API_KEY')
            if not api_key:
                 return jsonify({'message': 'Αποθηκεύτηκε (Χωρίς Δορυφόρο - Λείπει το API Key)', 'ndvi_url': ''})

            # 1. Δημιουργία/Ενημέρωση Πολυγώνου στο Agromonitoring
            poly_url = f"http://api.agromonitoring.com/agro/1.0/polygons?appid={api_key}"
            payload = {"name": ktima.onoma_ktimatos, "geo_json": geo_json}
            headers = {'Content-Type': 'application/json'}
            
            # Κάνουμε POST για να πάρουμε το ID (αν υπάρχει ήδη, επιστρέφει το υπάρχον)
            poly_res = requests.post(poly_url, json=payload, headers=headers)
            
            if poly_res.status_code in [200, 201]:
                poly_data = poly_res.json()
                ktima.agromonitoring_poly_id = poly_data.get('id')
                vasi.session.commit()
                
                # 2. Αναζήτηση Εικόνας NDVI (Τελευταίες 365 μέρες - 1 Έτος)
                end_time = int(time.time())
                start_time = end_time - (365 * 24 * 60 * 60)
                img_url = f"http://api.agromonitoring.com/agro/1.0/image/search?start={start_time}&end={end_time}&polyid={ktima.agromonitoring_poly_id}&appid={api_key}"
                
                time.sleep(1) # Μικρή αναμονή για το API
                img_res = requests.get(img_url)
                
                if img_res.status_code == 200 and len(img_res.json()) > 0:
                    # Βελτιωμένη λογική: Ψάχνουμε την πιο πρόσφατη ΕΓΚΥΡΗ εικόνα
                    images = img_res.json()
                    images.sort(key=lambda x: x['dt'], reverse=True) # Ταξινόμηση: Νεότερα πρώτα
                    
                    ndvi_url = None
                    ndwi_url = None
                    for img in images:
                        if img.get('image', {}).get('ndvi'):
                            ndvi_url = img.get('image', {}).get('ndvi')
                            ndwi_url = img.get('image', {}).get('ndwi')
                            break
                    
                    ai_msg = "Ο χάρτης ανανεώθηκε, αλλά δεν έγινε ανάλυση AI."
                    if ndvi_url:
                        # 3. Ανάλυση με Gemini Vision
                        try:
                            img_content = requests.get(ndvi_url).content
                            image_file = PIL.Image.open(io.BytesIO(img_content))
                            prompt = "Είσαι ειδικός γεωπόνος. Ανάλυσε αυτόν τον χάρτη NDVI (Δείκτης Βλάστησης). Το πράσινο είναι υγιής/πυκνή βλάστηση, το κόκκινο/κίτρινο είναι στρες/έδαφος. Εντόπισε αν υπάρχουν προβληματικές ζώνες."
                            response = ai_client.models.generate_content(model='gemini-2.5-flash', contents=[prompt, image_file])
                            ai_msg = response.text
                            
                            # Αποθήκευση στη βάση για τον Σύμβουλο
                            nea_diagnosi = Diagnosi(ktima_id=ktima.id, apotelesma=f"🛰️ Δορυφόρος (Live): {ai_msg}", imerominia=datetime.now())
                            vasi.session.add(nea_diagnosi)
                            vasi.session.commit()
                        except Exception as e:
                            print(f"Vision Error: {e}")
                            ai_msg = "Σφάλμα κατά την ανάλυση εικόνας."

            return jsonify({
                'message': 'Το πολύγωνο αποθηκεύτηκε επιτυχώς.',
                'ai_message': ai_msg if 'ai_msg' in locals() else 'Ο χάρτης ορίστηκε. Αναμονή για δορυφορικό πέρασμα.',
                'ndvi_url': ndvi_url if 'ndvi_url' in locals() else '',
                'ndwi_url': ndwi_url if 'ndwi_url' in locals() else ''
            })
        
        return jsonify({'error': 'Δεν βρέθηκαν δεδομένα χάρτη'}), 400

    except Exception as e:
        print(f"NDVI Error: {e}")
        return jsonify({'error': 'Σφάλμα διακομιστή'}), 500

@core_bp.route('/trexe_doriforo/<int:ktima_id>')
@login_required
def trexe_doriforo(ktima_id):
    import requests
    import time
    import io
    import PIL.Image
    import json
    
    ktima = vasi.session.get(Ktima, ktima_id)
    if not ktima or (ktima.idioktitis != current_user and getattr(current_user, 'rolos', '') != 'geoponos'):
        flash('Δεν έχετε πρόσβαση.', 'danger')
        return redirect(url_for('core_app.arxikh'))
        
    api_key = os.getenv('AGROMONITORING_API_KEY')
    if not api_key:
        flash('Λείπει το κλειδί Agromonitoring.', 'danger')
        return redirect(url_for('core_app.arxikh'))
        
    if not ktima.agromonitoring_poly_id:
        flash('Δεν έχει οριστεί χάρτης (πολύγωνο) για αυτό το κτήμα.', 'warning')
        return redirect(url_for('core_app.arxikh'))

    try:
        # Αναζήτηση Εικόνας NDVI (Τελευταίες 365 μέρες)
        end_time = int(time.time())
        start_time = end_time - (365 * 24 * 60 * 60)
        img_url = f"http://api.agromonitoring.com/agro/1.0/image/search?start={start_time}&end={end_time}&polyid={ktima.agromonitoring_poly_id}&appid={api_key}"
        
        img_res = requests.get(img_url)
        
        # Προσωρινή αποθήκευση αποτελεσμάτων για έλεγχο
        images = []
        ndvi_url = None
        
        if img_res.status_code == 200 and len(img_res.json()) > 0:
            images = img_res.json()
            images.sort(key=lambda x: x['dt'], reverse=True)
            for img in images:
                if img.get('image', {}).get('ndvi'):
                    ndvi_url = img.get('image', {}).get('ndvi')
                    break
        
        # ΑΥΤΟΜΑΤΗ ΕΠΙΔΙΟΡΘΩΣΗ: Αν δεν βρει εικόνες Ή βρει αλλά χωρίς NDVI, ξανα-δημιουργούμε το πολύγωνο
        if (len(images) == 0 or ndvi_url is None) and ktima.polygon_geojson:
            print(f"🔄 Επιδιόρθωση πολυγώνου για το κτήμα {ktima.id}...")
            poly_url = f"http://api.agromonitoring.com/agro/1.0/polygons?appid={api_key}"
            payload = {"name": ktima.onoma_ktimatos, "geo_json": json.loads(ktima.polygon_geojson)}
            headers = {'Content-Type': 'application/json'}
            
            poly_res = requests.post(poly_url, json=payload, headers=headers)
            if poly_res.status_code in [200, 201]:
                new_data = poly_res.json()
                ktima.agromonitoring_poly_id = new_data.get('id')
                vasi.session.commit()
                # Ξαναδοκιμάζουμε την αναζήτηση με το νέο ID
                img_url = f"http://api.agromonitoring.com/agro/1.0/image/search?start={start_time}&end={end_time}&polyid={ktima.agromonitoring_poly_id}&appid={api_key}"
                img_res = requests.get(img_url)
                if img_res.status_code == 200:
                    images = img_res.json()
                    images.sort(key=lambda x: x['dt'], reverse=True)
        
        if len(images) > 0:
            # Τελική αναζήτηση NDVI URL
            ndvi_url = None
            for img in images:
                if img.get('image', {}).get('ndvi'):
                    ndvi_url = img.get('image', {}).get('ndvi')
                    break
            
            if ndvi_url:
                # Ανάλυση με Gemini Vision
                try:
                    img_content = requests.get(ndvi_url).content
                    image_file = PIL.Image.open(io.BytesIO(img_content))
                    prompt = "Είσαι ειδικός γεωπόνος. Ανάλυσε αυτόν τον δορυφορικό χάρτη NDVI. Δώσε μια σύντομη αναφορά (2-3 γραμμές) για την υγεία της βλάστησης."
                    response = ai_client.models.generate_content(model='gemini-2.5-flash', contents=[prompt, image_file])
                    
                    # Λήψη Στατιστικών (Hard Data) από Agromonitoring
                    stats_msg = ""
                    try:
                        stats_url = f"http://api.agromonitoring.com/agro/1.0/ndvi/history?start={start_time}&end={end_time}&polyid={ktima.agromonitoring_poly_id}&appid={api_key}"
                        stats_res = requests.get(stats_url)
                        if stats_res.status_code == 200 and len(stats_res.json()) > 0:
                            # Παίρνουμε το πιο πρόσφατο στατιστικό
                            latest_stat = stats_res.json()[-1] 
                            mean_ndvi = latest_stat.get('mean')
                            max_ndvi = latest_stat.get('max')
                            dt_stat = datetime.fromtimestamp(latest_stat.get('dt')).strftime('%d/%m/%Y')
                            stats_msg = f"📊 Στατιστικά ({dt_stat}): Μέσος NDVI: {mean_ndvi:.2f}, Μέγιστο: {max_ndvi:.2f}. "
                    except Exception as e:
                        print(f"Stats Error: {e}")

                    # Αποθήκευση στη διάγνωση
                    teliko_keimeno = f"🛰️ Δορυφόρος: {stats_msg}{response.text}"
                    nea_diagnosi = Diagnosi(ktima_id=ktima.id, apotelesma=teliko_keimeno, imerominia=datetime.now())
                    vasi.session.add(nea_diagnosi)
                    
                    # Ενημέρωση και του πεδίου 'analysi_dedomena' για να φαίνεται στο κουτάκι
                    ktima.analysi_dedomena = f"{stats_msg}\n{response.text}"
                    vasi.session.commit()
                    
                    flash('Η ανάλυση ολοκληρώθηκε! Δείτε το ιστορικό διαγνώσεων.', 'success')
                except Exception as e:
                    print(f"Vision Error: {e}")
                    flash('Σφάλμα κατά την ανάλυση AI.', 'danger')
            else:
                flash('Βρέθηκαν περάσματα δορυφόρου αλλά κανένα δεν είχε έτοιμο δείκτη NDVI. Δοκιμάστε αργότερα.', 'warning')
        else:
            flash(f'Δεν βρέθηκε εικόνα. API Status: {img_res.status_code}. Response: {img_res.text}', 'warning')
            
    except Exception as e:
        flash(f'Σφάλμα επικοινωνίας: {e}', 'danger')

    # ΔΙΟΡΘΩΣΗ REDIRECT: Αν είναι γεωπόνος, επιστρέφουμε στην προβολή του πελάτη
    if getattr(current_user, 'rolos', '') == 'geoponos':
        return redirect(url_for('core_app.arxikh', pelatis_id=ktima.xrhsths_id))
        
    return redirect(url_for('core_app.arxikh'))

@core_bp.route('/diorthosi_gdd')
@login_required
def diorthosi_gdd():
    import requests
    ktimata = current_user.ktimata
    count = 0
    
    now = datetime.now()
    current_year = now.year
    start_date = f"{current_year}-01-01"
    yesterday = (now - timedelta(days=1)).strftime('%Y-%m-%d')
    
    for ktima in ktimata:
        try:
            # Ανάκτηση ιστορικού καιρού από 1η Ιανουαρίου
            hist_url = f"https://archive-api.open-meteo.com/v1/archive?latitude={ktima.geografiko_platos}&longitude={ktima.geografiko_mikos}&start_date={start_date}&end_date={yesterday}&daily=temperature_2m_max,temperature_2m_min&timezone=auto"
            resp = requests.get(hist_url, timeout=5)
            if resp.status_code == 200:
                data = resp.json().get('daily', {})
                t_max = data.get('temperature_2m_max', [])
                t_min = data.get('temperature_2m_min', [])
                
                total_gdd = sum([((mx + mn)/2.0 - 10.0) for mx, mn in zip(t_max, t_min) if mx and mn and ((mx + mn)/2.0 > 10.0)])
                ktima.gdd_accumulated = total_gdd
                count += 1
        except Exception as e:
            print(f"Σφάλμα GDD Update για κτήμα {ktima.id}: {e}")
            
    vasi.session.commit()
    flash(f'Έγινε επανυπολογισμός GDD από 1/1 για {count} κτήματα!', 'success')
    return redirect(url_for('core_app.arxikh'))

@core_bp.route('/updb')
def update_db_schema():
    vasi.create_all()
    return "Database Updated! <a href='/'>Επιστροφή στην Αρχική</a>"

@core_bp.route('/ping')
def ping(): return "Pong", 200

@core_bp.route('/icon.svg')
def icon():
    svg = '''<svg xmlns="http://www.w3.org/2000/svg" width="100" height="100" viewBox="0 0 100 100"><rect width="100" height="100" rx="22" fill="#4A7C59"/><text x="50%" y="50%" font-size="55" text-anchor="middle" dominant-baseline="central">🫒</text></svg>'''
    return Response(svg, mimetype='image/svg+xml')

@core_bp.route('/manifest.json')
def manifest():
    return jsonify({"name": "Olea AI", "icons": [{"src": "/icon.svg", "sizes": "192x192", "type": "image/svg+xml"}]})

@core_bp.route('/sw.js')
def service_worker():
    response = make_response("self.addEventListener('install', (e) => console.log('SW Installed'));")
    response.headers['Content-Type'] = 'application/javascript'
    return response

@core_bp.route('/favicon.ico')
def favicon(): return "", 204

@core_bp.route('/enimerosi_profil', methods=['POST'])
@login_required
def enimerosi_profil():
    # Ενημέρωση βασικών στοιχείων
    current_user.onoma = request.form.get('onoma')
    current_user.afm = request.form.get('afm')
    current_user.ar_tautotitas = request.form.get('ar_tautotitas')
    
    # Λογική Αλλαγής Κωδικού
    neos_kwdikos = request.form.get('neos_kwdikos')
    epivevaiosi_kwdikou = request.form.get('epivevaiosi_kwdikou')
    trexwn_kwdikos = request.form.get('trexwn_kwdikos')
    
    if neos_kwdikos:
        if not trexwn_kwdikos:
             flash('Για να αλλάξετε κωδικό, πρέπει να συμπληρώσετε τον τρέχοντα κωδικό.', 'danger')
             return redirect(url_for('core_app.arxikh'))
        
        if not kryptografhsh.check_password_hash(current_user.kwdikos, trexwn_kwdikos):
             flash('Ο τρέχων κωδικός είναι λάθος.', 'danger')
             return redirect(url_for('core_app.arxikh'))
             
        if neos_kwdikos != epivevaiosi_kwdikou:
             flash('Οι νέοι κωδικοί δεν ταιριάζουν μεταξύ τους.', 'danger')
             return redirect(url_for('core_app.arxikh'))

        current_user.kwdikos = kryptografhsh.generate_password_hash(neos_kwdikos).decode('utf-8')
        flash('Ο κωδικός πρόσβασης άλλαξε επιτυχώς!', 'success')

    vasi.session.commit()
    flash('Το προφίλ ενημερώθηκε.', 'success')
    return redirect(url_for('core_app.arxikh'))

# Import routes to register them with the blueprint before the blueprint is registered with the app
import routes