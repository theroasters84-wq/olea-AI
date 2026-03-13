from flask import render_template, request, flash, redirect, url_for
from flask_login import login_required, current_user
from core import efarmogi
from auth import auth_bp
from ai_tools import ai_bp
from core_app import core_bp
from models import Xrhsths

efarmogi.register_blueprint(auth_bp)
efarmogi.register_blueprint(ai_bp)
efarmogi.register_blueprint(core_bp)

@core_bp.route('/dashboard_geoponou', methods=['GET', 'POST'])
@login_required
def dashboard_geoponou():
    # Αποτροπή πρόσβασης σε απλούς αγρότες
    if current_user.rolos != 'geoponos':
        flash('Μη εξουσιοδοτημένη πρόσβαση. Απαιτείται λογαριασμός Γεωπόνου.', 'danger')
        return redirect(url_for('core_app.arxikh'))
    
    pelatis = None
    if request.method == 'POST':
        afm_anazitisis = request.form.get('afm_anazitisis')
        if afm_anazitisis:
            pelatis = Xrhsths.query.filter_by(afm=afm_anazitisis, rolos='agroths').first()
            if not pelatis:
                flash('Δεν βρέθηκε αγρότης με αυτό το ΑΦΜ.', 'warning')
                
    return render_template('geoponos.html', pelatis=pelatis)