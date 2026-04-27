import os
import json
import requests
import time
from datetime import datetime, timedelta
from flask import Blueprint, request, flash, redirect, url_for, jsonify, render_template
from flask_login import login_required, current_user
from core import vasi
from models import Ktima, Ergasia, Exodo, KatagrafiUgrasias, ArxeioSygkomidis, KtimaPoikilia, Diagnosi, Apothiki, AnalysiEdafous
from geoponika import pare_ypsometro, steile_email

ktima_actions_bp = Blueprint('ktima_actions', __name__)

@ktima_actions_bp.route('/prosthes_ktima', methods=['POST'])
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
    kalliergeia_typos = request.form.get('kalliergeia_typos', 'Συμβατική')
    
    poikilia_onomata = request.form.getlist('poikilia_onoma')
    poikilia_dentra_str = request.form.getlist('poikilia_dentra')
    poikilia_ilikies = request.form.getlist('poikilia_ilikia')
    
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
                now = datetime.now()
                current_year = now.year
                start_date = f"{current_year}-01-01"
                safe_end_date = (now - timedelta(days=5)).strftime('%Y-%m-%d')
                
                if safe_end_date >= start_date:
                    hist_url = f"https://archive-api.open-meteo.com/v1/archive?latitude={float(platos)}&longitude={float(mikos)}&start_date={start_date}&end_date={safe_end_date}&daily=temperature_2m_max,temperature_2m_min&timezone=auto"
                    hist_resp = requests.get(hist_url, timeout=5)
                    
                    if hist_resp.status_code == 200:
                        daily_data = hist_resp.json().get('daily', {})
                        t_max_list = daily_data.get('temperature_2m_max', [])
                        t_min_list = daily_data.get('temperature_2m_min', [])
                        
                        for t_max, t_min in zip(t_max_list, t_min_list):
                            if t_max is not None and t_min is not None:
                                t_mean = (t_max + t_min) / 2.0
                                daily_gdd = t_mean - 10.0
                                if daily_gdd > 0:
                                    initial_gdd += daily_gdd
                    
                    recent_url = f"https://api.open-meteo.com/v1/forecast?latitude={float(platos)}&longitude={float(mikos)}&past_days=4&forecast_days=1&daily=temperature_2m_max,temperature_2m_min&timezone=auto"
                    resp_recent = requests.get(recent_url, timeout=5)
                    if resp_recent.status_code == 200:
                        data_rec = resp_recent.json().get('daily', {})
                        t_max_rec = data_rec.get('temperature_2m_max', [])[:-1]
                        t_min_rec = data_rec.get('temperature_2m_min', [])[:-1]
                        initial_gdd += sum([((mx + mn)/2.0 - 10.0) for mx, mn in zip(t_max_rec, t_min_rec) if mx is not None and mn is not None and ((mx + mn)/2.0 > 10.0)])

            except Exception as e:
                print(f"Historical GDD API Error: {e}")
            # --- END HISTORICAL GDD CALCULATION ---

            # --- SMART GDD TARGETS LOGIC ---
            target_a, target_s = 600, 2500
            gdd_map = {'Κορωνέικη': (550, 2400), 'Αθηνολιά': (500, 2300), 'Καλαμών': (680, 2600), 'Χονδρολιά': (680, 2600), 'Χαλκιδικής': (620, 2500), 'Μεγαρίτικη': (600, 2450), 'Μανάκι': (600, 2500), 'Αρμπεκίνα': (550, 2400)}
            found_known = False
            for k, v in gdd_map.items():
                if k in display_poikilia:
                    target_a, target_s = v
                    found_known = True
                    break
            
            if not found_known and display_poikilia and display_poikilia not in ['Δεν ορίστηκε', 'Ανάμεικτο']:
                try:
                    from core import ai_client
                    prompt = f"What are the approximate Growing Degree Days (GDD) targets for flowering and harvest for the olive variety '{display_poikilia}'? Return ONLY a valid JSON format like this: {{\"anthisi\": 600, \"sygkomidi\": 2500}}. Do not include any other text."
                    response = ai_client.models.generate_content(model='gemini-2.5-flash', contents=prompt)
                    ai_text = response.text.strip().replace('```json', '').replace('```', '')
                    data = json.loads(ai_text)
                    if 'anthisi' in data: target_a = int(data['anthisi'])
                    if 'sygkomidi' in data: target_s = int(data['sygkomidi'])
                except Exception as e:
                    print(f"AI GDD Target Error for {display_poikilia}: {e}")

            neo = Ktima(onoma_ktimatos=onoma, geografiko_mikos=float(mikos), geografiko_platos=float(platos), idioktitis=current_user, typos_edafous=typos, klisi=klisi, ardefsi=ardefsi, stremmata=float(stremmata) if stremmata else 0.0, poikilia=display_poikilia, arithmos_dentron=total_trees, ilikia_dentron=ilikia_dentron, puknotita_dentron=puknotita_dentron, diacheirisi_edafous=diacheirisi_edafous, gdd_accumulated=initial_gdd, gdd_target_anthisi=target_a, gdd_target_sygkomidi=target_s, kalliergeia_typos=kalliergeia_typos)
            
            yps_val = pare_ypsometro(float(platos), float(mikos))
            if yps_val is not None: neo.ypsometro = yps_val
                
            vasi.session.add(neo)
            vasi.session.flush()
            
            for i, onoma_p in enumerate(poikilia_onomata):
                try:
                    d = int(poikilia_dentra_str[i])
                    ilikia_p = poikilia_ilikies[i] if i < len(poikilia_ilikies) else None
                    if d > 0: 
                        vasi.session.add(KtimaPoikilia(ktima_id=neo.id, poikilia_onoma=onoma_p, arithmos_dentron=d, ilikia_dentron=ilikia_p))
                except: pass
            
            poly_json = request.form.get('polygon_geojson')
            if poly_json:
                neo.polygon_geojson = poly_json
                api_key = os.getenv('AGROMONITORING_API_KEY')
                if api_key:
                    try:
                        from google import genai
                        import PIL.Image
                        import io
                        headers = {'Content-Type': 'application/json'}
                        payload = {"name": onoma, "geo_json": json.loads(poly_json)}
                        resp = requests.post(f"http://api.agromonitoring.com/agro/1.0/polygons?appid={api_key}", json=payload, headers=headers)
                        if resp.status_code in [200, 201]:
                            poly_data = resp.json()
                            neo.agromonitoring_poly_id = poly_data.get('id')
                            end_time = int(time.time()) - 60
                            start_time = end_time - (365 * 24 * 60 * 60)
                            img_url = f"http://api.agromonitoring.com/agro/1.0/image/search?start={start_time}&end={end_time}&polyid={neo.agromonitoring_poly_id}&appid={api_key}"
                            img_res = requests.get(img_url)
                            if img_res.status_code == 200 and len(img_res.json()) > 0:
                                images = sorted(img_res.json(), key=lambda x: x['dt'], reverse=True)
                                ndvi_url = next((img.get('image', {}).get('ndvi') for img in images if img.get('image', {}).get('ndvi')), None)
                                if ndvi_url:
                                    img_content = requests.get(ndvi_url).content
                                    image_file = PIL.Image.open(io.BytesIO(img_content))
                                    client_ai = genai.Client(api_key=os.getenv('AI_API_KEY'))
                                    prompt = "Είσαι ειδικός γεωπόνος. Ανάλυσε αυτόν τον δορυφορικό χάρτη NDVI. Δώσε μια σύντομη αναφορά (2-3 γραμμές) για την υγεία της βλάστησης."
                                    response = client_ai.models.generate_content(model='gemini-2.5-flash', contents=[prompt, image_file])
                                    nea_diagnosi = Diagnosi(ktima_id=neo.id, apotelesma=f"🛰️ Δορυφόρος: {response.text}", imerominia=datetime.now())
                                    vasi.session.add(nea_diagnosi)
                    except Exception as e:
                        print(f"Auto-Satellite Error: {e}")
                        
            # --- ΝΕΟ: ONBOARDING AI QUESTION ---
            vasi.session.commit()
            try:
                from logic import syghronismos_ai_ktimatos
                syghronismos_ai_ktimatos(neo)
            except Exception as e: 
                print(f"Onboarding AI Question Error: {e}")
            
            flash('Το κτήμα προστέθηκε!', 'success')
        except Exception as e:
            vasi.session.rollback()
            flash(f'Σφάλμα: {e}', 'danger')
    return redirect(url_for('core_app.arxikh'))

@ktima_actions_bp.route('/toggle_kalliergeia/<int:ktima_id>', methods=['POST'])
@login_required
def toggle_kalliergeia(ktima_id):
    ktima = vasi.session.get(Ktima, ktima_id)
    if ktima and (ktima.idioktitis == current_user or getattr(current_user, 'rolos', '') == 'geoponos'):
        current_type = ktima.kalliergeia_typos or 'Συμβατική'
        ktima.kalliergeia_typos = 'Βιολογική' if current_type == 'Συμβατική' else 'Συμβατική'
        ktima.ekkremis_erotisi_ai = None
        vasi.session.commit()
        
        # Επιστροφή JSON αν η κλήση έγινε μέσω AJAX (ώστε να μην ανοίξει web view στο PWA)
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest' or request.is_json:
            return jsonify({'success': True, 'neos_typos': ktima.kalliergeia_typos})
            
        flash(f'Ο τύπος καλλιέργειας άλλαξε σε: {ktima.kalliergeia_typos}', 'success')
    return redirect(request.referrer or url_for('core_app.arxikh'))

@ktima_actions_bp.route('/prosthes_ergasia/<int:ktima_id>', methods=['POST'])
@login_required
def prosthes_ergasia(ktima_id):
    date_str = request.form.get('imerominia')
    im = datetime.strptime(date_str, '%Y-%m-%d') if date_str else datetime.now()
    katastasi = request.form.get('katastasi')
    eidos = request.form.get('eidos_ergasias')
    
    # --- ΣΥΣΤΗΜΑ ΠΡΟΣΤΑΣΙΑΣ GDD ---
    eidos_lower = (eidos or '').lower()
    farmaka_lower = (request.form.get('farmaka_lipasmata') or '').lower()
    if 'ψεκασμ' in eidos_lower or 'ραντισμ' in eidos_lower or 'χαλκ' in eidos_lower or 'ψεκασμ' in farmaka_lower or 'ραντισμ' in farmaka_lower:
        ktima_check = vasi.session.get(Ktima, ktima_id)
        if ktima_check:
            from geoponika import check_spraying_status
            gdd_val = ktima_check.gdd_accumulated if ktima_check.gdd_accumulated else 0.0
            poikilia_val = ktima_check.poikilia if ktima_check.poikilia else "Κορωνέικη"
            spray_status = check_spraying_status(gdd_val, poikilia_val)
            if not spray_status.get('can_spray', True):
                flash(f"Αποτυχία: Το κτήμα βρίσκεται σε στάδιο {spray_status.get('stage_name', 'Άνθισης')}. Ο ψεκασμός απαγορεύεται αυστηρά για την προστασία του ανθού!", "danger")
                return redirect(url_for('core_app.arxikh'))
    # ------------------------------

    nea_ergasia = Ergasia(ktima_id=ktima_id, eidos_ergasias=eidos, katastasi=katastasi, imerominia=im, farmaka_lipasmata=request.form.get('farmaka_lipasmata'))
    vasi.session.add(nea_ergasia)
    ktima = vasi.session.get(Ktima, ktima_id)
    if ktima: 
        if katastasi == 'Ολοκληρώθηκε':
            # Καθαρισμός εκκρεμών
            pending_tasks = Ergasia.query.filter_by(ktima_id=ktima.id, katastasi='Εκκρεμεί').all()
            t_name = eidos.lower()
            strong_keywords = ['χόρτ', 'ζιζάν', 'χαλκ', 'κλάδεμ', 'δάκ', 'άζωτ', 'βόρι', 'αμινοξ', 'καταστροφ', 'λίπανσ', 'φρέζ', 'όργωμ', 'μυκητοκτόν', 'εντομοκτόν', 'πότισμ', 'νερ']
            found_keywords = [k for k in strong_keywords if k in t_name]
            for pt in pending_tasks:
                pt_name = pt.eidos_ergasias.lower()
                if any(k in pt_name for k in found_keywords) or (t_name in pt_name):
                    vasi.session.delete(pt)
        ktima.ekkremis_erotisi_ai = None
        ktima.teleftaia_enimerosi_ergasion = None
        ktima.ai_sumvouli_date = None
    vasi.session.commit()
    return redirect(url_for('core_app.arxikh'))

@ktima_actions_bp.route('/oloklirosi_ergasias/<int:ktima_id>', methods=['POST'])
@login_required
def oloklirosi_ergasias(ktima_id):
    ktima = vasi.session.get(Ktima, ktima_id)
    if not ktima or (ktima.idioktitis != current_user and getattr(current_user, 'rolos', '') != 'geoponos'):
        return jsonify({'error': 'Μη εξουσιοδοτημένη ενέργεια'}), 403
    try:
        ergasia_id = request.form.get('ergasia_id')
        eidos = request.form.get('eidos_ergasias')
        if ergasia_id:
            ergasia = vasi.session.get(Ergasia, ergasia_id)
            if ergasia and ergasia.ktima_id == ktima.id:
                ergasia.katastasi = 'Ολοκληρώθηκε'
                eidos = ergasia.eidos_ergasias
        else:
            vasi.session.add(Ergasia(ktima_id=ktima_id, eidos_ergasias=eidos, katastasi='Ολοκληρώθηκε', imerominia=datetime.now(), proelevsi='Αγρότης' if getattr(current_user, 'rolos', '') != 'geoponos' else 'Γεωπόνος'))
            
            # Καθαρισμός εκκρεμών
            pending_tasks = Ergasia.query.filter_by(ktima_id=ktima.id, katastasi='Εκκρεμεί').all()
            new_task_text = eidos.lower()
            synonym_groups = [
                {'πότισμ', 'νερ', 'άρδευσ'},
                {'χόρτ', 'ζιζάν', 'καταστροφ'},
                {'λίπανσ', 'θρέψη', 'άζωτ', 'βόρι', 'αμινοξ', 'κάλι', 'φωσφορ'},
                {'κλάδεμ'},
                {'χαλκ', 'μυκητοκτόν'},
                {'δάκ', 'εντομοκτόν', 'πυρηνοτρύτ'},
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
        
        yliko_id = request.form.get('yliko_id')
        posotita_xrisis_str = request.form.get('posotita_xrisis')
        if yliko_id and posotita_xrisis_str:
            yliko = vasi.session.get(Apothiki, yliko_id)
            if yliko and yliko.xrhsths_id == ktima.xrhsths_id:
                posotita_xrisis = float(posotita_xrisis_str)
                if yliko.posotita >= posotita_xrisis: yliko.posotita -= posotita_xrisis
                else: flash(f'Δεν υπάρχει αρκετό απόθεμα για το {yliko.onoma_proiontos}.', 'warning')
        
        kostos_str = request.form.get('kostos')
        if kostos_str and float(kostos_str) > 0:
            vasi.session.add(Exodo(ktima_id=ktima_id, perigrafi=f"{eidos} (Κόστος Εργασίας)", poso=float(kostos_str), imerominia=datetime.now()))
        
        # --- ΑΥΤΟΜΑΤΟ ΧΡΟΝΟΜΕΤΡΟ ΑΜΙΝΟΞΕΩΝ (7 ΗΜΕΡΩΝ) ΜΕΤΑ ΑΠΟ ΧΑΛΚΟ ---
        farmaka = request.form.get('farmaka_lipasmata', '')
        if 'χαλκ' in eidos.lower() or 'χαλκ' in farmaka.lower() or 'kocide' in farmaka.lower():
            # Ελέγχουμε αν υπάρχει ήδη εκκρεμής εργασία για αμινοξέα
            yparxei_amino = Ergasia.query.filter_by(ktima_id=ktima.id, katastasi='Εκκρεμεί').filter(Ergasia.eidos_ergasias.ilike('%αμινοξ%')).first()
            if not yparxei_amino:
                nea_imerominia = datetime.now() + timedelta(days=7)
                date_str = nea_imerominia.strftime('%Y-%m-%d')
                nea_ergasia_amino = Ergasia(
                    ktima_id=ktima_id,
                    eidos_ergasias='Διαφυλλική με Αμινοξέα',
                    farmaka_lipasmata=f'[ΧΡΟΝΟΜΕΤΡΟ:{date_str}] Εφαρμογή αυστηρά μετά από 7 ημέρες από τον Χαλκό για αποφυγή τοξικότητας.',
                    katastasi='Εκκρεμεί',
                    imerominia=nea_imerominia,
                    proelevsi='AI Σύστημα Ασφαλείας'
                )
                vasi.session.add(nea_ergasia_amino)
                flash('Το σύστημα πρόσθεσε αυτόματα χρονόμετρο αναμονής 7 ημερών για τα Αμινοξέα, ώστε να μην καούν τα δέντρα από τον Χαλκό!', 'info')

        vasi.session.commit()
        return redirect(request.referrer or url_for('core_app.arxikh'))
    except Exception as e:
        vasi.session.rollback()
        flash('Προέκυψε σφάλμα.', 'danger')
        return redirect(request.referrer or url_for('core_app.arxikh'))

@ktima_actions_bp.route('/prosthes_ugrasia/<int:ktima_id>', methods=['POST'])
@login_required
def prosthes_ugrasia(ktima_id):
    try:
        vasi.session.add(KatagrafiUgrasias(ktima_id=ktima_id, pososto=float(request.form.get('pososto', 0))))
        ktima = vasi.session.get(Ktima, ktima_id)
        if ktima: 
            ktima.ekkremis_erotisi_ai = None
            ktima.teleftaia_enimerosi_ergasion = None
            ktima.ai_sumvouli_date = None
        vasi.session.commit()
    except ValueError: flash('Μη έγκυρη τιμή υγρασίας.', 'danger')
    return redirect(url_for('core_app.arxikh'))

@ktima_actions_bp.route('/enimerosi_nerou/<int:ktima_id>', methods=['POST'])
@login_required
def enimerosi_nerou(ktima_id):
    ktima = vasi.session.get(Ktima, ktima_id)
    try:
        ktima.nero_ph = float(request.form.get('nero_ph') or 0)
        ktima.nero_agwgimotita = float(request.form.get('nero_agwgimotita') or 0)
        ktima.ekkremis_erotisi_ai = None
        ktima.teleftaia_enimerosi_ergasion = None
        ktima.ai_sumvouli_date = None
        vasi.session.add(Diagnosi(ktima_id=ktima.id, apotelesma=f"💧 Ανάλυση Νερού: pH {ktima.nero_ph}, EC {ktima.nero_agwgimotita}", imerominia=datetime.now()))
        vasi.session.commit()
    except ValueError: flash('Εισάγετε έγκυρους αριθμούς.', 'danger')
    return redirect(url_for('core_app.arxikh'))

@ktima_actions_bp.route('/prosthes_exodo/<int:ktima_id>', methods=['POST'])
@login_required
def prosthes_exodo(ktima_id):
    try:
        katigoria = request.form.get('katigoria', 'Εργασίες/Γενικά')
        vasi.session.add(Exodo(ktima_id=ktima_id, perigrafi=request.form.get('perigrafi', 'Έξοδο'), poso=float(request.form.get('poso', 0)), katigoria=katigoria, imerominia=datetime.now()))
        vasi.session.commit()
    except ValueError: flash('Μη έγκυρο ποσό.', 'danger')
    return redirect(url_for('core_app.arxikh'))

@ktima_actions_bp.route('/lixi_xronias/<int:ktima_id>', methods=['POST'])
@login_required
def lixi_xronias(ktima_id):
    ktima = vasi.session.get(Ktima, ktima_id)
    try:
        vasi.session.add(ArxeioSygkomidis(ktima_id=ktima.id, tonoi=float(request.form.get('tonoi_paragogis', 0)), kila_ana_dentro=0, synoliko_kostos=0, imerominia=datetime.now()))
        for e in ktima.ergasies: e.archived = True
        for ex in ktima.exoda: ex.archived = True
        vasi.session.commit()
        flash('Χρονιά έκλεισε.', 'success')
    except ValueError: flash('Παρακαλώ εισάγετε έγκυρο αριθμό τόνων.', 'danger')
    return redirect(url_for('core_app.arxikh'))

@ktima_actions_bp.route('/epeksergasia_poikiliwn/<int:ktima_id>', methods=['POST'])
@login_required
def epeksergasia_poikiliwn(ktima_id):
    ktima = vasi.session.get(Ktima, ktima_id)
    if not ktima or ktima.idioktitis != current_user:
        flash('Μη εξουσιοδοτημένη ενέργεια.', 'danger')
        return redirect(url_for('core_app.arxikh'))

    try:
        # Λήψη δεδομένων από τη φόρμα
        poikilia_onomata = request.form.getlist('poikilia_onoma')
        poikilia_dentra_str = request.form.getlist('poikilia_dentra')
        poikilia_ilikies = request.form.getlist('poikilia_ilikia')

        # Καθαρισμός παλιών εγγραφών
        KtimaPoikilia.query.filter_by(ktima_id=ktima.id).delete()

        total_trees = 0
        valid_varieties = []

        for i, onoma_p in enumerate(poikilia_onomata):
            try:
                d = int(poikilia_dentra_str[i])
                ilikia_p = poikilia_ilikies[i] if i < len(poikilia_ilikies) else None
                if d > 0:
                    vasi.session.add(KtimaPoikilia(ktima_id=ktima.id, poikilia_onoma=onoma_p, arithmos_dentron=d, ilikia_dentron=ilikia_p))
                    total_trees += d
                    valid_varieties.append(onoma_p)
            except ValueError:
                pass

        # Ενημέρωση κεντρικών πεδίων του κτήματος
        ktima.arithmos_dentron = total_trees
        ktima.poikilia = 'Ανάμεικτο' if len(valid_varieties) > 1 else (valid_varieties[0] if valid_varieties else 'Δεν ορίστηκε')
        if len(poikilia_ilikies) > 0 and poikilia_ilikies[0]: ktima.ilikia_dentron = poikilia_ilikies[0]

        ktima.ekkremis_erotisi_ai = None
        ktima.teleftaia_enimerosi_ergasion = None
        ktima.ai_sumvouli_date = None
        vasi.session.commit()
        flash('Τα δέντρα και οι ποικιλίες ενημερώθηκαν επιτυχώς!', 'success')
    except Exception as e:
        vasi.session.rollback()
        flash(f'Σφάλμα κατά την ενημέρωση: {e}', 'danger')
        
    return redirect(request.referrer or url_for('core_app.arxikh'))

@ktima_actions_bp.route('/steile_anafora', methods=['POST'])
@login_required
def steile_anafora():
    data = request.get_json()
    steile_email(current_user.email, f"Anafora {data.get('onoma_ktimatos')}", data.get('ai_sumvouli'))
    return jsonify({'minima': 'Ok'})

@ktima_actions_bp.route('/diagrafi_ktimatos/<int:ktima_id>', methods=['POST'])
@login_required
def diagrafi_ktimatos(ktima_id):
    ktima = vasi.session.get(Ktima, ktima_id)
    if ktima and ktima.idioktitis == current_user:
        if ktima.agromonitoring_poly_id and os.getenv('AGROMONITORING_API_KEY'):
            try: requests.delete(f"http://api.agromonitoring.com/agro/1.0/polygons/{ktima.agromonitoring_poly_id}?appid={os.getenv('AGROMONITORING_API_KEY')}", timeout=5)
            except Exception as e: print(f"Σφάλμα διαγραφής από Agromonitoring: {e}")
        vasi.session.delete(ktima)
        vasi.session.commit()
        flash('Το κτήμα διαγράφηκε επιτυχώς.', 'success')
    return redirect(url_for('core_app.arxikh'))

@ktima_actions_bp.route('/oristiki_diagrafi_ktimatos/<int:id>', methods=['POST'])
@login_required
def oristiki_diagrafi_ktimatos(id):
    ktima = vasi.session.get(Ktima, id)
    if ktima.agromonitoring_poly_id and os.getenv('AGROMONITORING_API_KEY'):
        try: requests.delete(f"http://api.agromonitoring.com/agro/1.0/polygons/{ktima.agromonitoring_poly_id}?appid={os.getenv('AGROMONITORING_API_KEY')}", timeout=5)
        except Exception as e: print(f"Σφάλμα διαγραφής από Agromonitoring: {e}")
    vasi.session.delete(ktima)
    vasi.session.commit()
    return redirect(url_for('core_app.arxeio'))

@ktima_actions_bp.route('/arxeiothetisi_ktimatos/<int:id>')
@login_required
def arxeiothetisi_ktimatos(id):
    ktima = vasi.session.get(Ktima, id)
    ktima.is_active = False
    vasi.session.commit()
    return redirect(url_for('core_app.arxikh'))

@ktima_actions_bp.route('/ektyposi_anaforas/<int:ktima_id>')
@login_required
def ektyposi_anaforas(ktima_id):
    ktima = vasi.session.get(Ktima, ktima_id)
    return render_template('anafora.html', ktima=ktima)

@ktima_actions_bp.route('/xeirokiniti_analysi/<int:ktima_id>', methods=['POST'])
@login_required
def xeirokiniti_analysi(ktima_id):
    ktima = vasi.session.get(Ktima, ktima_id)
    if not ktima or (ktima.idioktitis != current_user and getattr(current_user, 'rolos', '') != 'geoponos'):
        return "Μη εξουσιοδοτημένη πρόσβαση", 403
        
    try:
        ph = request.form.get('ph')
        org = request.form.get('organiki_ousia')
        n = request.form.get('azwto')
        p = request.form.get('fwsforos')
        k = request.form.get('kalio')
        typos = request.form.get('typos_edafous')
        
        nea_analysi = AnalysiEdafous(
            ktima_id=ktima_id,
            ph=float(ph) if ph else None,
            organiki_ousia=float(org) if org else None,
            azwto=float(n) if n else None,
            fwsforos=float(p) if p else None,
            kalio=float(k) if k else None,
            imerominia=datetime.now()
        )
        vasi.session.add(nea_analysi)
        
        if typos:
            ktima.typos_edafous = typos
            
        ktima.ekkremis_erotisi_ai = None
        ktima.teleftaia_enimerosi_ergasion = None
        ktima.ai_sumvouli_date = None
        vasi.session.add(Diagnosi(
            ktima_id=ktima_id, 
            apotelesma=f"📄 Χειροκίνητη Ανάλυση Εδάφους: Ολοκληρώθηκε", 
            imerominia=datetime.now()
        ))
        
        vasi.session.commit()
        flash('Η χειροκίνητη ανάλυση καταχωρήθηκε επιτυχώς!', 'success')
    except ValueError:
        flash('Παρακαλώ εισάγετε έγκυρους αριθμητικούς χαρακτήρες.', 'danger')
        
    return redirect(url_for('core_app.arxikh'))

@ktima_actions_bp.route('/nea_sodeia', methods=['POST'])
@login_required
def nea_sodeia():
    ktima_id = request.form.get('ktima_id')
    ktima = vasi.session.get(Ktima, ktima_id)
    if not ktima or ktima.idioktitis != current_user:
        flash("Άρνηση πρόσβασης", "danger")
        return redirect(url_for('core_app.arxeio'))
        
    try:
        kila_karpou = float(request.form.get('kila_karpou', 0))
        kila_ladi = float(request.form.get('kila_ladi', 0))
        esoda = float(request.form.get('esoda', 0))
        
        # Υπολογισμός Συνολικών Εξόδων της σεζόν πριν αρχειοθετηθούν
        synoliko_kostos = sum([e.poso for e in ktima.exoda if not e.archived])
        kila_ana_dentro = kila_karpou / ktima.arithmos_dentron if ktima.arithmos_dentron and ktima.arithmos_dentron > 0 else 0
        
        vasi.session.add(ArxeioSygkomidis(
            ktima_id=ktima.id, 
            tonoi=kila_karpou, # Χρησιμοποιούμε τη στήλη tonoi για τα Κιλά Καρπού
            kila_ladi=kila_ladi,
            esoda=esoda,
            kila_ana_dentro=kila_ana_dentro, 
            synoliko_kostos=synoliko_kostos, 
            imerominia=datetime.now()
        ))
        
        for e in ktima.ergasies: e.archived = True
        for ex in ktima.exoda: ex.archived = True
        
        vasi.session.commit()
        flash(f'Η σοδειά καταγράφηκε! Όλες οι τρέχουσες εργασίες και έξοδα του κτήματος "{ktima.onoma_ktimatos}" αρχειοθετήθηκαν επιτυχώς.', 'success')
    except ValueError: 
        flash('Παρακαλώ εισάγετε έγκυρους αριθμούς.', 'danger')
        
    return redirect(url_for('core_app.arxeio'))

@ktima_actions_bp.route('/diagrafi_sodeias/<int:sodeia_id>', methods=['POST'])
@login_required
def diagrafi_sodeias(sodeia_id):
    sodeia = vasi.session.get(ArxeioSygkomidis, sodeia_id)
    if not sodeia or sodeia.ktima.idioktitis != current_user:
        flash('Μη εξουσιοδοτημένη ενέργεια.', 'danger')
        return redirect(url_for('core_app.arxeio'))
    
    vasi.session.delete(sodeia)
    vasi.session.commit()
    flash('Η καταχώρηση της σοδειάς διαγράφηκε επιτυχώς.', 'success')
    return redirect(url_for('core_app.arxeio'))

@ktima_actions_bp.route('/epeksergasia_topothesias/<int:ktima_id>', methods=['POST'])
@login_required
def epeksergasia_topothesias(ktima_id):
    ktima = vasi.session.get(Ktima, ktima_id)
    if not ktima or ktima.idioktitis != current_user:
        return redirect(url_for('core_app.arxikh'))
        
    mikos = request.form.get('geografiko_mikos')
    platos = request.form.get('geografiko_platos')
    stremmata = request.form.get('stremmata')
    poly_json = request.form.get('polygon_geojson')
    
    if mikos and platos:
        ktima.geografiko_mikos = float(mikos)
        ktima.geografiko_platos = float(platos)
        if stremmata: 
            ktima.stremmata = float(stremmata.replace(',', '.'))
        if poly_json: 
            ktima.polygon_geojson = poly_json
            api_key = os.getenv('AGROMONITORING_API_KEY')
            if api_key:
                try:
                    headers = {'Content-Type': 'application/json'}
                    payload = {"name": ktima.onoma_ktimatos, "geo_json": json.loads(poly_json)}
                    resp = requests.post(f"http://api.agromonitoring.com/agro/1.0/polygons?appid={api_key}", json=payload, headers=headers)
                    if resp.status_code in [200, 201]: ktima.agromonitoring_poly_id = resp.json().get('id')
                except Exception as e: print(f"Σφάλμα ενημέρωσης δορυφόρου: {e}")
        ktima.ekkremis_erotisi_ai = None
        ktima.teleftaia_enimerosi_ergasion = None
        ktima.ai_sumvouli_date = None
        vasi.session.commit()
        flash('Η τοποθεσία ενημερώθηκε επιτυχώς!', 'success')
    return redirect(url_for('core_app.arxikh'))

@ktima_actions_bp.route('/allagi_katastasis_ergasias/<int:ergasia_id>', methods=['POST'])
@login_required
def allagi_katastasis_ergasias(ergasia_id):
    ergasia = vasi.session.get(Ergasia, ergasia_id)
    if not ergasia or ergasia.ktima.idioktitis != current_user:
        return jsonify({'error': 'Μη εξουσιοδοτημένη ενέργεια'}), 403

    try:
        if ergasia.katastasi == 'Εκκρεμεί':
            ergasia.katastasi = 'Ολοκληρώθηκε'
        else:
            ergasia.katastasi = 'Εκκρεμεί'
        vasi.session.commit()
        return jsonify({'success': True, 'nea_katastasi': ergasia.katastasi})
    except Exception as e:
        vasi.session.rollback()
        return jsonify({'error': str(e)}), 500