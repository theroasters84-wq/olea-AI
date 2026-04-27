from flask import render_template, request, flash, redirect, url_for, jsonify, Blueprint
from flask_login import login_required, current_user, login_user, logout_user
from core import efarmogi, vasi, kryptografhsh
from auth import auth_bp
from ai_tools import ai_bp
from core_app import core_bp
from ktima_actions import ktima_actions_bp
from gramateas_ai import gramateas_bp
from models import Xrhsths
from geoponika import check_spraying_status
from core_app import cache

cache.init_app(efarmogi)

@core_bp.route('/dashboard_geoponou', methods=['GET', 'POST'])
@login_required
def dashboard_geoponou():
    # Αποτροπή πρόσβασης σε απλούς αγρότες
    if current_user.rolos != 'geoponos':
        flash('Μη εξουσιοδοτημένη πρόσβαση. Απαιτείται λογαριασμός Γεωπόνου.', 'danger')
        return redirect(url_for('core_app.arxikh'))
    
    pelatis = None
    energa_ktimata = []
    if request.method == 'POST':
        afm_anazitisis = request.form.get('afm_anazitisis')
        if afm_anazitisis:
            pelatis = Xrhsths.query.filter_by(afm=afm_anazitisis, rolos='agroths').first()
            if not pelatis:
                flash('Δεν βρέθηκε αγρότης με αυτό το ΑΦΜ.', 'warning')
            else:
                energa_ktimata = [k for k in pelatis.ktimata if k.is_active]
                
                for k in energa_ktimata:
                    gdd_val = k.gdd_accumulated if k.gdd_accumulated else 0.0
                    poikilia_val = k.poikilia if k.poikilia else "Κορωνέικη"
                    k.spray_status = check_spraying_status(gdd_val, poikilia_val)
                    k.dynamic_stage = k.spray_status.get('stage_name') if k.spray_status else None
                    
                    # Ζωντανός υπολογισμός του τρέχοντος NPK
                    from logic import calculate_dynamic_npk
                    npk_data = calculate_dynamic_npk(k.id)
                    if npk_data:
                        k.current_npk = npk_data.get('current_now')
                        k.npk_is_estimated = npk_data.get('is_estimated')
                    else:
                        k.current_npk = None
                
    return render_template('geoponos.html', pelatis=pelatis, energa_ktimata=energa_ktimata)

# --- CONSOLIDATED ROUTES FROM dromologia.py ---
kyrio_bp = Blueprint('kyrio', __name__)

@kyrio_bp.route("/legacy_welcome")
def kyrio_arxikh():
    return "<h1>Καλώς ήρθατε στο Olea AI</h1>"

@kyrio_bp.route("/eggrafh", methods=['POST'])
def eggrafh():
    dedomena = request.get_json() or request.form
    onoma = dedomena.get('onoma_xrhsth')
    email = dedomena.get('email')
    kwdikos = dedomena.get('kwdikos')

    if not onoma or not email or not kwdikos:
        return jsonify({"mhnyma": "Λείπουν στοιχεία!"}), 400

    hash_kwdikou = kryptografhsh.generate_password_hash(kwdikos).decode('utf-8')
    neos = Xrhsths(onoma_xrhsth=onoma, email=email, kwdikos=hash_kwdikou)
    
    try:
        vasi.session.add(neos)
        vasi.session.commit()
        return jsonify({"mhnyma": "Επιτυχής εγγραφή!"}), 201
    except:
        return jsonify({"mhnyma": "Το Email υπάρχει ήδη."}), 400

@kyrio_bp.route("/syndesh", methods=['POST'])
def syndesh():
    dedomena = request.get_json() or request.form
    xrhsths = Xrhsths.query.filter_by(email=dedomena.get('email')).first()
    if xrhsths and kryptografhsh.check_password_hash(xrhsths.kwdikos, dedomena.get('kwdikos')):
        login_user(xrhsths)
        return jsonify({"mhnyma": "Επιτυχής σύνδεση!"})
    return jsonify({"mhnyma": "Λάθος στοιχεία"}), 401

@kyrio_bp.route("/aposyndesh")
def aposyndesh():
    logout_user()
    return jsonify({"mhnyma": "Αποσυνδεθήκατε."})

efarmogi.register_blueprint(auth_bp)
efarmogi.register_blueprint(ai_bp)
efarmogi.register_blueprint(core_bp)
efarmogi.register_blueprint(ktima_actions_bp)
efarmogi.register_blueprint(gramateas_bp)
efarmogi.register_blueprint(kyrio_bp)