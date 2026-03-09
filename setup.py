import os

# Ορίζουμε τη βασική διαδρομή
base_dir = "olea_ai"
app_dir = os.path.join(base_dir, "efarmogi")

# 1. Δημιουργία Φακέλων
os.makedirs(app_dir, exist_ok=True)
print(f"✅ Δημιουργήθηκαν οι φάκελοι: {base_dir} και {app_dir}")

# 2. Περιεχόμενα Αρχείων

# requirements.txt
requirements_txt = """Flask
Flask-SQLAlchemy
Flask-Bcrypt
Flask-Login
email_validator
requests
python-dotenv
google-generativeai
apscheduler
Pillow
gunicorn
"""

# run.py
run_py = """from efarmogi import dhmiourgia_efarmogis

efarmogi = dhmiourgia_efarmogis()

if __name__ == '__main__':
    efarmogi.run(debug=True)
"""

# efarmogi/__init__.py
init_py = """from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_bcrypt import Bcrypt
from flask_login import LoginManager

vasi = SQLAlchemy()
kryptografhsh = Bcrypt()
diaxeiristh_syndeshs = LoginManager()

diaxeiristh_syndeshs.login_view = 'kyrio.syndesh'
diaxeiristh_syndeshs.login_message_category = 'info'
diaxeiristh_syndeshs.login_message = "Παρακαλώ συνδεθείτε για να δείτε αυτή τη σελίδα."

def dhmiourgia_efarmogis():
    efarmogi = Flask(__name__)
    efarmogi.config['SECRET_KEY'] = 'mystiko-kleidi-olea-ai'
    efarmogi.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///olea.db'
    efarmogi.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

    vasi.init_app(efarmogi)
    kryptografhsh.init_app(efarmogi)
    diaxeiristh_syndeshs.init_app(efarmogi)

    from efarmogi.dromologia import bp
    efarmogi.register_blueprint(bp)

    with efarmogi.app_context():
        vasi.create_all()

    return efarmogi
"""

# efarmogi/montela.py
montela_py = """from efarmogi import vasi, diaxeiristh_syndeshs
from flask_login import UserMixin

@diaxeiristh_syndeshs.user_loader
def fortwsh_xrhsth(xrhsths_id):
    return Xrhsths.query.get(int(xrhsths_id))

class Xrhsths(vasi.Model, UserMixin):
    __tablename__ = 'xrhstes'
    id = vasi.Column(vasi.Integer, primary_key=True)
    onoma_xrhsth = vasi.Column(vasi.String(20), unique=True, nullable=False)
    email = vasi.Column(vasi.String(120), unique=True, nullable=False)
    kwdikos = vasi.Column(vasi.String(60), nullable=False)

    def __repr__(self):
        return f"Xrhsths('{self.onoma_xrhsth}', '{self.email}')"
"""

# efarmogi/dromologia.py
dromologia_py = """from flask import Blueprint, url_for, redirect, request, jsonify
from efarmogi import vasi, kryptografhsh
from efarmogi.montela import Xrhsths
from flask_login import login_user, current_user, logout_user, login_required

bp = Blueprint('kyrio', __name__)

@bp.route("/")
def arxikh():
    return "<h1>Καλώς ήρθατε στο Olea AI</h1>"

@bp.route("/eggrafh", methods=['POST'])
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

@bp.route("/syndesh", methods=['POST'])
def syndesh():
    dedomena = request.get_json() or request.form
    xrhsths = Xrhsths.query.filter_by(email=dedomena.get('email')).first()
    if xrhsths and kryptografhsh.check_password_hash(xrhsths.kwdikos, dedomena.get('kwdikos')):
        login_user(xrhsths)
        return jsonify({"mhnyma": "Επιτυχής σύνδεση!"})
    return jsonify({"mhnyma": "Λάθος στοιχεία"}), 401

@bp.route("/aposyndesh")
def aposyndesh():
    logout_user()
    return jsonify({"mhnyma": "Αποσυνδεθήκατε."})
"""

# 3. Εγγραφή αρχείων
files = {
    os.path.join(base_dir, "requirements.txt"): requirements_txt,
    os.path.join(base_dir, "run.py"): run_py,
    os.path.join(app_dir, "__init__.py"): init_py,
    os.path.join(app_dir, "montela.py"): montela_py,
    os.path.join(app_dir, "dromologia.py"): dromologia_py,
}

for path, content in files.items():
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"✅ Δημιουργήθηκε το αρχείο: {path}")

print("\n🚀 Η εγκατάσταση ολοκληρώθηκε!")
print(f"Τώρα τρέξε: cd {base_dir} && pip install -r requirements.txt")
