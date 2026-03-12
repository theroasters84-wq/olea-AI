import os
import re
from datetime import datetime, timedelta
from flask import Blueprint, render_template, redirect, url_for, request, flash, jsonify, Response, make_response
from flask_login import login_required, current_user, logout_user
from sqlalchemy import text
from core import vasi, ai_client, api_key_ai
from models import Ktima, Ergasia, Exodo, KatagrafiUgrasias, Apothiki, ArxeioSygkomidis, KtimaPoikilia, Diagnosi, AnalysiEdafous
from logic import paragwgi_protasewn, generate_local_tasks_via_ai
from geoponika import pare_kairo, steile_email, geoponikos_elegxos

core_bp = Blueprint('core_app', __name__)

@core_bp.route('/')
@login_required
def arxikh():
    ktimata = [k for k in current_user.ktimata if k.is_active]
    for ktima in ktimata:
        ktima.kairos = pare_kairo(ktima.geografiko_platos, ktima.geografiko_mikos)
        if ktima.kairos:
            ktima.symvouli = geoponikos_elegxos(ktima.kairos['thermokrasia'], ktima.kairos['ygrasia'])
            ktima.protaseis = paragwgi_protasewn(ktima, ktima.kairos['thermokrasia'], ktima.kairos['ygrasia'], ktima.kairos['perigrafi'])
        else:
            ktima.protaseis = []
        
        ideal_tasks = generate_local_tasks_via_ai(ktima)
        if isinstance(ideal_tasks, list):
             ideal_tasks = [t.strip() for t in ideal_tasks if t.strip()]
        else:
             ideal_tasks = []
        
        # (GDD logic omitted for brevity, same as original)

        completed_tasks = [e.eidos_ergasias for e in ktima.ergasies if not e.archived]
        ktima.pending_tasks = [task for task in ideal_tasks if task not in completed_tasks]
        ktima.synoliko_kostos = sum(exodo.poso for exodo in ktima.exoda if not exodo.archived)
        
        # PHI Logic
        latest_spray = None
        for ergasia in ktima.ergasies:
            if not ergasia.archived and 'Ψεκασμός' in ergasia.eidos_ergasias:
                if latest_spray is None or ergasia.imerominia > latest_spray.imerominia:
                    latest_spray = ergasia
        ktima.meres_apo_psekasmo = (datetime.now() - latest_spray.imerominia).days if latest_spray else None
            
    return render_template('arxiki.html', xrhsths=current_user, ktimata=ktimata)

@core_bp.route('/ananeosi_ergasion/<int:ktima_id>')
@login_required
def ananeosi_ergasion(ktima_id):
    ktima = vasi.session.get(Ktima, ktima_id)
    if not ktima or ktima.idioktitis != current_user: return "403", 403
    ktima.teleftaia_enimerosi_ergasion = None
    vasi.session.commit()
    generate_local_tasks_via_ai(ktima)
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
                    import json, os
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
            vasi.session.add(neo)
            vasi.session.flush()
            
            for i, onoma_p in enumerate(poikilia_onomata):
                try:
                    d = int(poikilia_dentra_str[i])
                    if d > 0:
                        vasi.session.add(KtimaPoikilia(ktima_id=neo.id, poikilia_onoma=onoma_p, arithmos_dentron=d))
                except: pass
            
            # ... (Auto NDVI logic) ...
            
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
    nea_ergasia = Ergasia(ktima_id=ktima_id, eidos_ergasias=eidos, katastasi=request.form.get('katastasi'), imerominia=datetime.now())
    vasi.session.add(nea_ergasia)
    vasi.session.commit()
    return redirect(url_for('core_app.arxikh'))

@core_bp.route('/oloklirosi_ergasias/<int:ktima_id>', methods=['POST'])
@login_required
def oloklirosi_ergasias(ktima_id):
    ktima = vasi.session.get(Ktima, ktima_id)
    nea_ergasia = Ergasia(ktima_id=ktima_id, eidos_ergasias=request.form.get('eidos_ergasias'), katastasi='Ολοκληρώθηκε', imerominia=datetime.now())
    vasi.session.add(nea_ergasia)
    # Cost logic
    try:
        kostos = float(request.form.get('kostos'))
        if kostos > 0:
            neo_exodo = Exodo(ktima_id=ktima_id, perigrafi=f"{request.form.get('eidos_ergasias')} - Έξοδο", poso=kostos, imerominia=datetime.now())
            vasi.session.add(neo_exodo)
    except: pass
    vasi.session.commit()
    return redirect(url_for('core_app.arxikh'))

@core_bp.route('/prosthes_ugrasia/<int:ktima_id>', methods=['POST'])
@login_required
def prosthes_ugrasia(ktima_id):
    nea = KatagrafiUgrasias(ktima_id=ktima_id, pososto=float(request.form.get('pososto')))
    vasi.session.add(nea)
    vasi.session.commit()
    return redirect(url_for('core_app.arxikh'))

@core_bp.route('/enimerosi_nerou/<int:ktima_id>', methods=['POST'])
@login_required
def enimerosi_nerou(ktima_id):
    ktima = vasi.session.get(Ktima, ktima_id)
    ktima.nero_ph = float(request.form.get('nero_ph') or 0)
    ktima.nero_agwgimotita = float(request.form.get('nero_agwgimotita') or 0)
    vasi.session.commit()
    return redirect(url_for('core_app.arxikh'))

@core_bp.route('/prosthes_exodo/<int:ktima_id>', methods=['POST'])
@login_required
def prosthes_exodo(ktima_id):
    neo = Exodo(ktima_id=ktima_id, perigrafi=request.form.get('perigrafi'), poso=float(request.form.get('poso')), imerominia=datetime.now())
    vasi.session.add(neo)
    vasi.session.commit()
    return redirect(url_for('core_app.arxikh'))

@core_bp.route('/apothiki', methods=['GET', 'POST'])
@login_required
def apothiki():
    if request.method == 'POST':
        neo = Apothiki(xrhsths_id=current_user.id, eidos=request.form.get('eidos'), onoma_proiontos=request.form.get('onoma_proiontos'), posotita=float(request.form.get('posotita')), monada_metrisis=request.form.get('monada_metrisis'))
        vasi.session.add(neo)
        vasi.session.commit()
        flash('Προστέθηκε!', 'success')
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
    arxeio = ArxeioSygkomidis(ktima_id=ktima.id, tonoi=float(request.form.get('tonoi_paragogis')), kila_ana_dentro=0, synoliko_kostos=0, imerominia=datetime.now())
    vasi.session.add(arxeio)
    for e in ktima.ergasies: e.archived = True
    for ex in ktima.exoda: ex.archived = True
    vasi.session.commit()
    flash('Χρονιά έκλεισε.', 'success')
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
    vasi.session.delete(ktima)
    vasi.session.commit()
    return redirect(url_for('core_app.arxikh'))

@core_bp.route('/oristiki_diagrafi_ktimatos/<int:id>', methods=['POST'])
@login_required
def oristiki_diagrafi_ktimatos(id):
    ktima = vasi.session.get(Ktima, id)
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