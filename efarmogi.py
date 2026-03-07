import os
import requests
from dotenv import load_dotenv
from flask import Flask, redirect, url_for, request, render_template
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin, LoginManager, login_user, login_required, logout_user, current_user
from flask_bcrypt import Bcrypt

# Φόρτωση μεταβλητών περιβάλλοντος
load_dotenv()

# Αρχικοποίηση εφαρμογής
efarmogi = Flask(__name__, template_folder='.')
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
    ktimata = vasi.relationship('Ktima', backref='idioktitis', lazy=True)

    def __repr__(self):
        return f"Xrhsths('{self.email}')"

# Μοντέλο Κτήματος (Field Model)
class Ktima(vasi.Model):
    __tablename__ = 'ktimata'
    
    id = vasi.Column(vasi.Integer, primary_key=True)
    onoma_ktimatos = vasi.Column(vasi.String(100), nullable=False)
    geografiko_mikos = vasi.Column(vasi.Float, nullable=False)
    geografiko_platos = vasi.Column(vasi.Float, nullable=False)
    xrhsths_id = vasi.Column(vasi.Integer, vasi.ForeignKey('xrhstes.id'), nullable=False)

    def __repr__(self):
        return f"Ktima('{self.onoma_ktimatos}')"

# Βοηθητική συνάρτηση για τον καιρό
def pare_kairo(lat, lng):
    api_key = os.getenv('WEATHER_API_KEY')
    try:
        url = f"https://api.openweathermap.org/data/2.5/weather?lat={lat}&lon={lng}&appid={api_key}&units=metric&lang=el"
        response = requests.get(url)
        data = response.json()
        if response.status_code == 200:
            return {
                'temp': data['main']['temp'],
                'description': data['weather'][0]['description']
            }
    except Exception as e:
        print(f"Σφάλμα λήψης καιρού: {e}")
    return None

# Routes
@efarmogi.route('/')
@login_required
def arxikh():
    ktimata = current_user.ktimata
    for ktima in ktimata:
        ktima.kairos = pare_kairo(ktima.geografiko_platos, ktima.geografiko_mikos)
    return render_template('arxiki.html', xrhsths=current_user, ktimata=ktimata)

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

@efarmogi.route('/neo_ktima', methods=['GET', 'POST'])
@login_required
def neo_ktima():
    if request.method == 'POST':
        onoma = request.form.get('onoma_ktimatos')
        mikos = request.form.get('geografiko_mikos')
        platos = request.form.get('geografiko_platos')
        
        if onoma and mikos and platos:
            try:
                neo = Ktima(onoma_ktimatos=onoma, geografiko_mikos=float(mikos), geografiko_platos=float(platos), idioktitis=current_user)
                vasi.session.add(neo)
                vasi.session.commit()
                return redirect(url_for('arxikh'))
            except ValueError:
                return "Σφάλμα στις συντεταγμένες."
    return render_template('neo_ktima.html')

@efarmogi.route('/eksodos')
def eksodos():
    logout_user()
    return redirect(url_for('eisodos'))

@efarmogi.route('/favicon.ico')
def favicon():
    return "", 204

# Δημιουργία της βάσης δεδομένων
with efarmogi.app_context():
    vasi.create_all()

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    efarmogi.run(host='0.0.0.0', port=port, debug=True)