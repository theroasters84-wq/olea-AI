from flask import Blueprint, render_template, flash, redirect, url_for, request
from flask_login import login_user, logout_user, current_user
from core import vasi, kryptografhsh, serializer
from models import Xrhsths
from geoponika import steile_email

auth_bp = Blueprint('auth', __name__)

@auth_bp.route('/eggrafi', methods=['GET', 'POST'])
def eggrafi():
    if current_user.is_authenticated:
        return redirect(url_for('core_app.arxikh'))
    
    if request.method == 'POST':
        email = request.form.get('email')
        kwdikos = request.form.get('kwdikos')
        epivevaiosi = request.form.get('epivevaiosi_kwdikou')
        rolos = request.form.get('rolos', 'agroths')
        afm = request.form.get('afm')
        ar_tautotitas = request.form.get('ar_tautotitas')
        onoma = request.form.get('onoma')
        
        if not email or not kwdikos or not epivevaiosi:
            flash("Συμπληρώστε τα βασικά πεδία.", "warning")
            return render_template('eggrafi.html')
            
        if kwdikos != epivevaiosi:
            flash("Οι κωδικοί δεν ταιριάζουν.", "danger")
            return render_template('eggrafi.html')
            
        hash_kwdikou = kryptografhsh.generate_password_hash(kwdikos).decode('utf-8')
        neos_xrhsths = Xrhsths(email=email, kwdikos=hash_kwdikou, rolos=rolos, afm=afm, ar_tautotitas=ar_tautotitas, onoma=onoma)
        
        try:
            vasi.session.add(neos_xrhsths)
            vasi.session.commit()
            flash("Η εγγραφή ολοκληρώθηκε! Συνδεθείτε.", "success")
            return redirect(url_for('auth.eisodos'))
        except:
            vasi.session.rollback()
            flash("Το Email, το ΑΦΜ ή η Ταυτότητα υπάρχει ήδη στο σύστημα.", "danger")
            
    return render_template('eggrafi.html')

@auth_bp.route('/xexasa_kodiko', methods=['GET', 'POST'])
def xexasa_kodiko():
    if request.method == 'POST':
        email = request.form.get('email')
        xrhsths = Xrhsths.query.filter_by(email=email).first()
        
        if xrhsths:
            token = serializer.dumps(email, salt='epanafora-kodikou')
            link = url_for('auth.epanafora_kodikou', token=token, _external=True)
            thema = "Επαναφορά Κωδικού - Olea AI"
            keimeno = f"Για να επαναφέρετε τον κωδικό σας, πατήστε στον παρακάτω σύνδεσμο:\n{link}\n\nΟ σύνδεσμος λήγει σε 1 ώρα."
            try:
                steile_email(email, thema, keimeno, raise_exception=True)
                flash('Στάλθηκε email με οδηγίες επαναφοράς.', 'info')
                return redirect(url_for('auth.eisodos'))
            except Exception as e:
                print(f"EMAIL ERROR: {str(e)}", flush=True)
                flash('Σφάλμα κατά την αποστολή του email. Ελέγξτε τα logs.', 'danger')
                return redirect(url_for('auth.xexasa_kodiko'))
        else:
            flash('Δεν βρέθηκε λογαριασμός με αυτό το email.', 'warning')
            return redirect(url_for('auth.xexasa_kodiko'))
    return render_template('xexasa_kodiko.html')

@auth_bp.route('/epanafora_kodikou/<token>', methods=['GET', 'POST'])
def epanafora_kodikou(token):
    try:
        email = serializer.loads(token, salt='epanafora-kodikou', max_age=3600)
    except:
        flash('Ο σύνδεσμος είναι άκυρος ή έχει λήξει.', 'danger')
        return redirect(url_for('auth.xexasa_kodiko'))
    
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
            return redirect(url_for('auth.eisodos'))
            
    return render_template('epanafora_kodikou.html', token=token)

@auth_bp.route('/eisodos', methods=['GET', 'POST'])
def eisodos():
    if current_user.is_authenticated:
        return redirect(url_for('core_app.arxikh'))

    if request.method == 'POST':
        email = request.form.get('email')
        kwdikos = request.form.get('kwdikos')
        
        xrhsths = Xrhsths.query.filter_by(email=email).first()
        
        if xrhsths and kryptografhsh.check_password_hash(xrhsths.kwdikos, kwdikos):
            login_user(xrhsths)
            if xrhsths.rolos == 'geoponos':
                return redirect(url_for('core_app.dashboard_geoponou'))
            else:
                return redirect(url_for('core_app.arxikh'))
        else:
            flash("Λάθος email ή κωδικός", "danger")

    return render_template('eisodos.html')

@auth_bp.route('/eksodos')
def eksodos():
    logout_user()
    return redirect(url_for('auth.eisodos'))