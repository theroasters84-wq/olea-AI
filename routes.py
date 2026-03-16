from flask import render_template, request, flash, redirect, url_for
from flask_login import login_required, current_user
from core import efarmogi
from auth import auth_bp
from ai_tools import ai_bp
from core_app import core_bp
from ktima_actions import ktima_actions_bp
from gramateas_ai import gramateas_bp
from models import Xrhsths

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
                
    return render_template('geoponos.html', pelatis=pelatis, energa_ktimata=energa_ktimata)

efarmogi.register_blueprint(auth_bp)
efarmogi.register_blueprint(ai_bp)
efarmogi.register_blueprint(core_bp)
efarmogi.register_blueprint(ktima_actions_bp)
efarmogi.register_blueprint(gramateas_bp)