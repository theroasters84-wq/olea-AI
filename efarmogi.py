import os
from flask import Flask, redirect, url_for, request, render_template
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin, LoginManager, login_user, login_required, logout_user, current_user
from flask_bcrypt import Bcrypt

# Αρχικοποίηση εφαρμογής
efarmogi = Flask(__name__, template_folder='selides')
efarmogi.config['SECRET_KEY'] = 'mystiko-kleidi-olea-ai'
efarmogi.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///vasi_dedomenwn.db'
efarmogi.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Αρχικοποίηση βάσης δεδομένων
vasi = SQLAlchemy(efarmogi)
kryptografhsh = Bcrypt(efarmogi)
diaxeiristh_syndeshs = LoginManager(efarmogi)
diaxeiristh_syndeshs.login_view = 'eisodos'
diaxeiristh_syndeshs.login_message = "Παρακαλώ συνδεθείτε για να δείτε αυτή τη σελίδα."

@diaxeiristh_syndeshs.user_loader
def fortwsh_xrhsth(xrhsths_id):
    return Xrhsths.query.get(int(xrhsths_id))

# Μοντέλο Χρήστη (Database Model)
class Xrhsths(vasi.Model, UserMixin):
    __tablename__ = 'xrhstes'
    
    id = vasi.Column(vasi.Integer, primary_key=True)
    email = vasi.Column(vasi.String(120), unique=True, nullable=False)
    kwdikos = vasi.Column(vasi.String(60), nullable=False)

    def __repr__(self):
        return f"Xrhsths('{self.email}')"

# Routes
@efarmogi.route('/')
@login_required
def arxikh():
    return render_template('arxiki.html', xrhsths=current_user)

@efarmogi.route('/eggrafi', methods=['GET', 'POST'])
def eggrafi():
    if current_user.is_authenticated:
        return redirect(url_for('arxikh'))
    
    if request.method == 'POST':
        email = request.form.get('email')
        kwdikos = request.form.get('kwdikos')
        
        if not email or not kwdikos:
            return "Συμπληρώστε όλα τα πεδία"
            
        hash_kwdikou = kryptografhsh.generate_password_hash(kwdikos).decode('utf-8')
        neos_xrhsths = Xrhsths(email=email, kwdikos=hash_kwdikou)
        
        try:
            vasi.session.add(neos_xrhsths)
            vasi.session.commit()
            return redirect(url_for('eisodos'))
        except:
            return "Το Email υπάρχει ήδη."
            
    return render_template('eggrafi.html')

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
            return "Λάθος email ή κωδικός"

    return render_template('eisodos.html')

@efarmogi.route('/eksodos')
def eksodos():
    logout_user()
    return redirect(url_for('eisodos'))

# Δημιουργία της βάσης δεδομένων
with efarmogi.app_context():
    vasi.create_all()

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    efarmogi.run(host='0.0.0.0', port=port, debug=True)