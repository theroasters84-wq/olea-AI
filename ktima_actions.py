import os
import json
import requests
import time
from datetime import datetime, timedelta
from flask import Blueprint, request, flash, redirect, url_for, jsonify, render_template
from flask_login import login_required, current_user
from core import vasi
from models import Ktima, Ergasia, Exodo, KatagrafiUgrasias, ArxeioSygkomidis, KtimaPoikilia, Diagnosi, Apothiki
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
                yesterday = (now - timedelta(days=1)).strftime('%Y-%m-%d')
                
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
                                daily_gdd = t_mean - 10.0
                                if daily_gdd > 0:
                                    initial_gdd += daily_gdd
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

            neo = Ktima(onoma_ktimatos=onoma, geografiko_mikos=float(mikos), geografiko_platos=float(platos), idioktitis=current_user, typos_edafous=typos, klisi=klisi, ardefsi=ardefsi, stremmata=float(stremmata) if stremmata else 0.0, poikilia=display_poikilia, arithmos_dentron=total_trees, ilikia_dentron=ilikia_dentron, puknotita_dentron=puknotita_dentron, diacheirisi_edafous=diacheirisi_edafous, gdd_accumulated=initial_gdd, gdd_target_anthisi=target_a, gdd_target_sygkomidi=target_s)
            
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
            
            vasi.session.commit()
            flash('Το κτήμα προστέθηκε!', 'success')
        except Exception as e:
            vasi.session.rollback()
            flash(f'Σφάλμα: {e}', 'danger')
    return redirect(url_for('core_app.arxikh'))

@ktima_actions_bp.route('/prosthes_ergasia/<int:ktima_id>', methods=['POST'])
@login_required
def prosthes_ergasia(ktima_id):
    date_str = request.form.get('imerominia')
    im = datetime.strptime(date_str, '%Y-%m-%d') if date_str else datetime.now()
    nea_ergasia = Ergasia(ktima_id=ktima_id, eidos_ergasias=request.form.get('eidos_ergasias'), katastasi=request.form.get('katastasi'), imerominia=im, farmaka_lipasmata=request.form.get('farmaka_lipasmata'))
    vasi.session.add(nea_ergasia)
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
        vasi.session.add(Diagnosi(ktima_id=ktima.id, apotelesma=f"💧 Ανάλυση Νερού: pH {ktima.nero_ph}, EC {ktima.nero_agwgimotita}", imerominia=datetime.now()))
        vasi.session.commit()
    except ValueError: flash('Εισάγετε έγκυρους αριθμούς.', 'danger')
    return redirect(url_for('core_app.arxikh'))

@ktima_actions_bp.route('/prosthes_exodo/<int:ktima_id>', methods=['POST'])
@login_required
def prosthes_exodo(ktima_id):
    try:
        vasi.session.add(Exodo(ktima_id=ktima_id, perigrafi=request.form.get('perigrafi', 'Έξοδο'), poso=float(request.form.get('poso', 0)), imerominia=datetime.now()))
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
    flash('Ενημερώθηκε.', 'success')
    return redirect(url_for('core_app.arxikh'))

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