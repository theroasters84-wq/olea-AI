import os
import requests
import smtplib
import PIL.Image
from datetime import datetime, timedelta
from itsdangerous import URLSafeTimedSerializer
from email.mime.text import MIMEText
from dotenv import load_dotenv
from flask import Flask, redirect, url_for, request, render_template, jsonify, flash, make_response
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin, LoginManager, login_user, login_required, logout_user, current_user
from flask_bcrypt import Bcrypt
import google.generativeai as genai
from apscheduler.schedulers.background import BackgroundScheduler

# Φόρτωση μεταβλητών περιβάλλοντος
# Ορίζουμε ρητά τη διαδρομή για το αρχείο .env στον ίδιο φάκελο με το script
basedir = os.path.abspath(os.path.dirname(__file__))
load_dotenv(os.path.join(basedir, '.env'))

# Αρχικοποίηση εφαρμογής
efarmogi = Flask(__name__, template_folder='.')
efarmogi.config['SECRET_KEY'] = os.getenv('FLASK_SECRET_KEY') or 'mystiko-kleidi-olea-ai'
efarmogi.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(basedir, 'vasi_dedomenwn.db')
efarmogi.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Serializer για tokens επαναφοράς κωδικού
serializer = URLSafeTimedSerializer(efarmogi.config['SECRET_KEY'])

# Ρύθμιση Gemini AI
genai.configure(api_key=os.getenv('AI_API_KEY'))

# Αρχικοποίηση βάσης δεδομένων
vasi = SQLAlchemy(efarmogi)
kryptografhsh = Bcrypt(efarmogi)
diaxeiristh_syndeshs = LoginManager(efarmogi)
diaxeiristh_syndeshs.login_view = 'eisodos'
diaxeiristh_syndeshs.login_message = "Παρακαλώ συνδεθείτε για να δείτε αυτή τη σελίδα."

@diaxeiristh_syndeshs.user_loader
def fortwsh_xrhsth(xrhsths_id):
    return vasi.session.get(Xrhsths, int(xrhsths_id))

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
    is_active = vasi.Column(vasi.Boolean, default=True)
    typos_edafous = vasi.Column(vasi.String(50))
    klisi = vasi.Column(vasi.String(50))
    ardefsi = vasi.Column(vasi.String(50))
    poikilia = vasi.Column(vasi.String(50))
    stremmata = vasi.Column(vasi.Float, default=0.0)
    arithmos_dentron = vasi.Column(vasi.Integer, default=0)
    arxeia_sygkomidis = vasi.relationship('ArxeioSygkomidis', backref='ktima', lazy=True, cascade="all, delete-orphan")
    topikes_ergasies = vasi.Column(vasi.Text)
    teleftaia_enimerosi_ergasion = vasi.Column(vasi.DateTime)
    analysi_dedomena = vasi.Column(vasi.Text)
    diagnoseis = vasi.relationship('Diagnosi', backref='ktima', lazy=True, cascade="all, delete-orphan")
    ergasies = vasi.relationship('Ergasia', backref='ktima', lazy=True, cascade="all, delete-orphan")
    exoda = vasi.relationship('Exodo', backref='ktima', lazy=True, cascade="all, delete-orphan")

    def __repr__(self):
        return f"Ktima('{self.onoma_ktimatos}')"

# Μοντέλο Εργασίας (Task Model)
class Ergasia(vasi.Model):
    __tablename__ = 'ergasies'
    
    id = vasi.Column(vasi.Integer, primary_key=True)
    ktima_id = vasi.Column(vasi.Integer, vasi.ForeignKey('ktimata.id'), nullable=False)
    eidos_ergasias = vasi.Column(vasi.String(100), nullable=False)
    imerominia = vasi.Column(vasi.DateTime, nullable=False)
    katastasi = vasi.Column(vasi.String(50), nullable=False, default='ekkremis')
    farmaka_lipasmata = vasi.Column(vasi.String(255))
    simeiwseis = vasi.Column(vasi.Text)
    archived = vasi.Column(vasi.Boolean, default=False)

    def __repr__(self):
        return f"Ergasia('{self.eidos_ergasias}' on '{self.imerominia}')"

# Μοντέλο Εξόδου (Expense Model)
class Exodo(vasi.Model):
    __tablename__ = 'exoda'
    
    id = vasi.Column(vasi.Integer, primary_key=True)
    ktima_id = vasi.Column(vasi.Integer, vasi.ForeignKey('ktimata.id'), nullable=False)
    perigrafi = vasi.Column(vasi.String(255), nullable=False)
    poso = vasi.Column(vasi.Float, nullable=False)
    imerominia = vasi.Column(vasi.DateTime, nullable=False)
    archived = vasi.Column(vasi.Boolean, default=False)

    def __repr__(self):
        return f"Exodo('{self.perigrafi}', '{self.poso}')"

# Μοντέλο Διάγνωσης (Diagnosis Model)
class Diagnosi(vasi.Model):
    __tablename__ = 'diagnoseis'
    
    id = vasi.Column(vasi.Integer, primary_key=True)
    ktima_id = vasi.Column(vasi.Integer, vasi.ForeignKey('ktimata.id'), nullable=False)
    imerominia = vasi.Column(vasi.DateTime, nullable=False, default=datetime.now)
    apotelesma = vasi.Column(vasi.Text, nullable=False)

    def __repr__(self):
        return f"Diagnosi('{self.imerominia}')"

# Μοντέλο Αρχείου Συγκομιδής (Harvest History Model)
class ArxeioSygkomidis(vasi.Model):
    __tablename__ = 'arxeia_sygkomidis'
    
    id = vasi.Column(vasi.Integer, primary_key=True)
    ktima_id = vasi.Column(vasi.Integer, vasi.ForeignKey('ktimata.id'), nullable=False)
    imerominia = vasi.Column(vasi.DateTime, nullable=False, default=datetime.now)
    tonoi = vasi.Column(vasi.Float, nullable=False)
    kila_ana_dentro = vasi.Column(vasi.Float, nullable=False)
    synoliko_kostos = vasi.Column(vasi.Float, nullable=False)

# Βοηθητική συνάρτηση για τον καιρό
def pare_kairo(lat, lng):
    api_key = os.getenv('WEATHER_API_KEY')
    
    if not api_key:
        print("⚠️ ΠΡΟΣΟΧΗ: Δεν βρέθηκε το WEATHER_API_KEY. Ελέγξτε το αρχείο .env")
        return None

    try:
        url = f"https://api.openweathermap.org/data/2.5/weather?lat={lat}&lon={lng}&appid={api_key}&units=metric&lang=el"
        response = requests.get(url)
        data = response.json()
        if response.status_code == 200:
            return {
                'thermokrasia': data['main']['temp'],
                'perigrafi': data['weather'][0]['description'],
                'ygrasia': data['main']['humidity']
            }
        else:
            print(f"⚠️ Σφάλμα από το OpenWeatherMap: {response.status_code} - {data.get('message')}")
    except Exception as e:
        print(f"Σφάλμα λήψης καιρού: {e}")
    return None

# Νέα συνάρτηση για πρόγνωση καιρού (5 ημέρες / 3 ώρες)
def pare_prognosi_kairou(lat, lng):
    api_key = os.getenv('WEATHER_API_KEY')
    
    if not api_key:
        return None

    try:
        url = f"https://api.openweathermap.org/data/2.5/forecast?lat={lat}&lon={lng}&appid={api_key}&units=metric&lang=el"
        response = requests.get(url)
        data = response.json()
        if response.status_code == 200:
            return data['list']
        else:
            print(f"⚠️ Σφάλμα από το OpenWeatherMap Forecast: {response.status_code} - {data.get('message')}")
    except Exception as e:
        print(f"Σφάλμα λήψης πρόγνωσης: {e}")
    return None

# Γεωπονικός Έλεγχος (Rule Engine)
def geoponikos_elegxos(thermokrasia, ygrasia):
    if thermokrasia < 2:
        return {"minima": "Κίνδυνος Παγετού! Αποφύγετε το κλάδεμα.", "xroma": "red"}
    elif thermokrasia > 35:
        return {"minima": "Κίνδυνος Καύσωνα! Προγραμματίστε βαθύ πότισμα.", "xroma": "orange"}
    elif 20 <= thermokrasia <= 30 and ygrasia > 60:
        return {"minima": "Ιδανικές συνθήκες για Δάκο! Εξετάστε το ενδεχόμενο δολωματικού ψεκασμού.", "xroma": "red"}
    else:
        return {"minima": "Κανονικές συνθήκες. Καμία άμεση ενέργεια.", "xroma": "green"}

# Προληπτικός Σύμβουλος (Εγκυκλοπαίδεια)
def paragwgi_protasewn(ktima, thermokrasia, ygrasia, perigrafi):
    mhnas = datetime.now().month
    protaseis = []

    # Phase 18: Agronomic Profiling Rules
    if ktima.klisi == 'Επικλινές/Πλαγιά' and ('βροχή' in perigrafi.lower() or 'βροχη' in perigrafi.lower()):
        protaseis.append("⚠️ Κλίση & Βροχή: Κίνδυνος έκπλυσης λιπάσματος. Αποφύγετε τη λίπανση πριν τη βροχή.")

    if ktima.typos_edafous == 'Αργιλώδες' and ('βροχή' in perigrafi.lower() or 'βροχη' in perigrafi.lower()):
        protaseis.append("⚠️ Αργιλώδες Έδαφος: Κίνδυνος ασφυξίας ριζών λόγω νεροκρατήματος. Ελέγξτε την αποστράγγιση.")

    if ktima.ardefsi == 'Ξηρικό' and thermokrasia > 30:
        protaseis.append("🔥 Ξηρικό & Ζέστη: Αποφύγετε το βαθύ όργωμα για να μην χαθεί η πολύτιμη υγρασία του εδάφους.")

    if ktima.klisi == 'Ρέμα/Κοιλότητα' and thermokrasia < 5 and mhnas in [12, 1, 2, 3]:
        protaseis.append("❄️ Ρέμα/Κοιλότητα: Αυξημένος κίνδυνος παγετού (frost pocket).")

    # Weather-Aware Fertilization (Months 2, 3, 4)
    if mhnas in [2, 3, 4]:
        if 'βροχή' not in perigrafi.lower() and 'βροχη' not in perigrafi.lower():
            protaseis.append("⚠️ Ανομβρία: Αν προγραμματίζετε επιφανειακή αζωτούχο λίπανση, προτιμήστε υδρολίπανση ή αναμείνατε βροχοπτώσεις για να μην εξατμιστεί το άζωτο.")

    # Άνοιξη (Μάρτιος, Απρίλιος)
    if mhnas in [3, 4]:
        protaseis.append("🌱 Άνοιξη: Ιδανική περίοδος για βασική λίπανση (Άζωτο & Βόριο) και ολοκλήρωση κλαδέματος.")
        protaseis.append("⚠️ Προσοχή στους ψεκασμούς: ΜΗΝ αναμειγνύετε ποτέ χαλκό με αμινοξέα (κίνδυνος φυτοτοξικότητας)!")
        if ygrasia > 60:
            protaseis.append("💧 Υψηλή υγρασία: Συνιστάται προληπτικός ψεκασμός με χαλκούχα για το Κυκλοκόνιο.")
    
    # Άνθιση / Αρχές Καλοκαιριού (Μάιος, Ιούνιος)
    elif mhnas in [5, 6]:
        protaseis.append("🌼 Περίοδος Άνθισης/Μούρου: ΑΠΑΓΟΡΕΥΕΤΑΙ η χρήση χαλκού (καίει το άνθος). Προγραμματίστε καταπολέμηση ζιζανίων.")
    
    # Καλοκαίρι (Ιούλιος, Αύγουστος)
    elif mhnas in [7, 8]:
        protaseis.append("☀️ Καλοκαίρι: Κρίσιμη περίοδος για άρδευση (πήξη πυρήνα).")
        if 20 <= thermokrasia <= 30 and ygrasia > 50:
            protaseis.append("🪰 Ιδανικές συνθήκες Δάκου: Προγραμματίστε δολωματικούς ψεκασμούς.")
        if thermokrasia > 35:
            protaseis.append("🔥 Καύσωνας: Ψεκασμός με Καολίνη για προστασία. Ο δάκος αδρανοποιείται.")
            
    # Φθινόπωρο / Χειμώνας (Σεπτέμβριος - Φεβρουάριος)
    elif mhnas in [9, 10, 11, 12, 1, 2]:
        protaseis.append("🍂 Ελαιογένεση/Συγκομιδή: Έμφαση στο Κάλιο. Μετά τη συγκομιδή ή χαλάζι/παγετό, ψεκάστε άμεσα με χαλκό για απολύμανση πληγών.")

    # Scientific Memory: Boron & Temperature Rule
    if thermokrasia < 12:
        twenty_five_days_ago = datetime.now() - timedelta(days=25)
        # Ελέγχουμε αν υπάρχει εφαρμογή Βορίου τις τελευταίες 25 ημέρες
        recent_boron = Ergasia.query.filter(
            Ergasia.ktima_id == ktima.id,
            Ergasia.farmaka_lipasmata.ilike('%Βόριο%'),
            Ergasia.imerominia >= twenty_five_days_ago
        ).first()
        
        if not recent_boron:
            protaseis.append("📊 Επιστημονική Μνήμη: Η θερμοκρασία είναι < 12°C και έχει περάσει καιρός από την τελευταία εφαρμογή Βορίου. Προτείνεται επανάληψη λόγω μειωμένης απορρόφησης.")

    # Adaptive Memory from Diagnosis
    if ktima.diagnoseis:
        teleytaia_diagnosi = ktima.diagnoseis[-1]
        protaseis.append(f"👁️ Μνήμη Διάγνωσης: Το AI είχε εντοπίσει πρόσφατα: {teleytaia_diagnosi.apotelesma}. Προσαρμόστε τις ενέργειές σας.")

    return protaseis

# AI Γεωπόνος
def pare_simvouli_ai(thermokrasia, ygrasia, perigrafi):
    try:
        model = genai.GenerativeModel('gemini-2.5-flash')
        prompt = (f"Είσαι ένας ειδικός γεωπόνος. Με θερμοκρασία {thermokrasia}°C, "
                  f"υγρασία {ygrasia}% και καιρό {perigrafi}, δώσε μια σύντομη συμβουλή "
                  f"(1-2 προτάσεις) για την καλλιέργεια της ελιάς.")
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        print(f"Σφάλμα AI: {e}")
        return "Δεν μπορώ να δώσω συμβουλή αυτή τη στιγμή."

# Λειτουργία Αποστολής Email
def steile_email(paraliptis, thema, keimeno):
    sender_email = os.getenv('EMAIL_ADDRESS')
    sender_password = os.getenv('EMAIL_PASSWORD')
    
    if not sender_email or not sender_password:
        print("⚠️ Λείπουν τα στοιχεία email από το .env")
        return False

    msg = MIMEText(keimeno, 'plain', 'utf-8')
    msg['Subject'] = thema
    msg['From'] = sender_email
    msg['To'] = paraliptis

    try:
        with smtplib.SMTP('smtp.gmail.com', 587) as server:
            server.starttls()
            server.login(sender_email, sender_password)
            server.send_message(msg)
        return True
    except Exception as e:
        print(f"Σφάλμα αποστολής email: {e}")
        return False

# Helper function for Seasonal Tasks
def get_epoxikes_ergasies(minas):
    if minas in [3, 4, 5]: # Spring
        return ['Διαχείριση Ζιζανίων (Χορτοκοπή / Φρέζα)', 'Βασική Λίπανση (Άζωτο / Βόριο)', 'Ολοκλήρωση Κλαδέματος', 'Ψεκασμός (Χαλκούχα για Κυκλοκόνιο)', 'Διαφυλλικός Ψεκασμός (Αμινοξέα & Ιχνοστοιχεία)']
    elif minas in [6, 7, 8]: # Summer
        return ['Άρδευση (Αν είναι ποτιστικό)', 'Ψεκασμός για Δάκο (Αν T < 33°C)', 'Διαφυλλική Λίπανση Καλίου']
    elif minas in [9, 10, 11]: # Autumn
        return ['Προετοιμασία Συγκομιδής', 'Συγκομιδή Ελαιοκάρπου', 'Ψεκασμός (Χαλκός Μετασυλλεκτικά)']
    elif minas in [12, 1, 2]: # Winter
        return ['Χειμερινός Ψεκασμός (Χαλκός)', 'Κλάδεμα Μορφοποίησης', 'Ανάλυση Εδάφους']
    return []

def generate_local_tasks_via_ai(ktima):
    now = datetime.now()
    
    # Check if cache is valid (same month and year)
    if ktima.teleftaia_enimerosi_ergasion and \
       ktima.teleftaia_enimerosi_ergasion.month == now.month and \
       ktima.teleftaia_enimerosi_ergasion.year == now.year and \
       ktima.topikes_ergasies:
        return ktima.topikes_ergasies.split(',')

    # Call AI
    try:
        model = genai.GenerativeModel('gemini-1.5-flash')
        prompt = (f"Είσαι ειδικός γεωπόνος. Το ελαιόκτημα βρίσκεται στις συντεταγμένες {ktima.geografiko_platos}, {ktima.geografiko_mikos} στην Ελλάδα "
                  f"(υπολόγισε το τοπικό μικροκλίμα, π.χ. παραθαλάσσιο vs ορεινό). Ο τρέχων μήνας είναι ο {now.month}. "
                  f"Δώσε μου ΜΟΝΟ μια λίστα με τις 3-5 απολύτως απαραίτητες εργασίες για αυτή την περιοχή αυτόν τον μήνα, "
                  f"χωρισμένες με κόμμα (,). Μην γράψεις καμία άλλη λέξη ή εισαγωγή. "
                  f"Παράδειγμα: Διαχείριση Ζιζανίων,Ψεκασμός με Χαλκό,Βασική Λίπανση")
        
        response = model.generate_content(prompt)
        tasks_str = response.text.strip().replace('\n', '').replace('.', '')
        
        ktima.topikes_ergasies = tasks_str
        ktima.teleftaia_enimerosi_ergasion = now
        vasi.session.commit()
        
        return tasks_str.split(',')
    except Exception as e:
        print(f"AI Task Error: {e}")
        # Fallback to static logic if AI fails
        return get_epoxikes_ergasies(now.month)

# Αυτοματοποιημένος Έλεγχος (Background Job)
def aytomatizomenos_elegxos():
    with efarmogi.app_context():
        print("🔄 Εκτέλεση αυτοματοποιημένου ελέγχου πρόγνωσης...")
        xrhstes = Xrhsths.query.all()
        for xrhsths in xrhstes:
            for ktima in xrhsths.ktimata:
                # Λήψη πρόγνωσης 5 ημερών
                prognosi = pare_prognosi_kairou(ktima.geografiko_platos, ktima.geografiko_mikos)
                
                if prognosi:
                    apeiles = []
                    
                    # Έλεγχος κάθε 3ωρου διαστήματος
                    for stoixeio in prognosi:
                        thermokrasia = stoixeio['main']['temp']
                        ygrasia = stoixeio['main']['humidity']
                        dt_txt = stoixeio['dt_txt'] # Ημερομηνία και ώρα πρόβλεψης
                        
                        elegxos = geoponikos_elegxos(thermokrasia, ygrasia)
                        
                        # Αν υπάρχει κίνδυνος (κόκκινο ή πορτοκαλί), το καταγράφουμε
                        if elegxos['xroma'] in ['red', 'orange']:
                            apeiles.append(f"🕒 {dt_txt}: {thermokrasia}°C, {ygrasia}%. -> {elegxos['minima']}")
                    
                    # Αν βρέθηκαν απειλές, στέλνουμε ΕΝΑ συγκεντρωτικό email
                    if apeiles:
                        thema = f"⚠️ ΠΡΟΕΙΔΟΠΟΙΗΣΗ ΠΡΟΓΝΩΣΗΣ: {ktima.onoma_ktimatos}"
                        keimeno = f"Προσοχή! Εντοπίστηκαν επικίνδυνες συνθήκες για τις επόμενες ημέρες στο κτήμα '{ktima.onoma_ktimatos}':\n\n" + "\n".join(apeiles) + "\n\nΠαρακαλούμε λάβετε τα απαραίτητα μέτρα.\n\nΜε εκτίμηση,\nΗ ομάδα του Olea AI"
                        
                        if steile_email(xrhsths.email, thema, keimeno):
                            print(f"✅ Στάλθηκε email πρόγνωσης στον {xrhsths.email} για το {ktima.onoma_ktimatos}")

# Routes
@efarmogi.route('/')
@login_required
def arxikh():
    # Φιλτράρισμα μόνο των ενεργών κτημάτων
    ktimata = [k for k in current_user.ktimata if k.is_active]
    now = datetime.now()

    for ktima in ktimata:
        ktima.kairos = pare_kairo(ktima.geografiko_platos, ktima.geografiko_mikos)
        if ktima.kairos:
            ktima.symvouli = geoponikos_elegxos(ktima.kairos['thermokrasia'], ktima.kairos['ygrasia'])
            ktima.protaseis = paragwgi_protasewn(ktima, ktima.kairos['thermokrasia'], ktima.kairos['ygrasia'], ktima.kairos['perigrafi'])
        else:
            ktima.protaseis = []
        
        # Geospatial AI Task Engine
        ideal_tasks = generate_local_tasks_via_ai(ktima)
        if isinstance(ideal_tasks, list):
             ideal_tasks = [t.strip() for t in ideal_tasks if t.strip()]
             
        completed_tasks = [e.eidos_ergasias for e in ktima.ergasies if not e.archived]
        ktima.pending_tasks = [task for task in ideal_tasks if task not in completed_tasks]

        # Υπολογισμός Συνολικού Κόστους για εμφάνιση
        ktima.synoliko_kostos = sum(exodo.poso for exodo in ktima.exoda if not exodo.archived)
    return render_template('arxiki.html', xrhsths=current_user, ktimata=ktimata)

@efarmogi.route('/ananeosi_ergasion/<int:ktima_id>')
@login_required
def ananeosi_ergasion(ktima_id):
    ktima = vasi.session.get(Ktima, ktima_id)
    if not ktima or ktima.idioktitis != current_user:
        return "Μη εξουσιοδοτημένη ενέργεια", 403
    
    ktima.teleftaia_enimerosi_ergasion = None
    vasi.session.commit()
    generate_local_tasks_via_ai(ktima) # Force regeneration
    
    flash('Η λίστα εργασιών επικαιροποιήθηκε με βάση το μικροκλίμα!', 'success')
    return redirect(url_for('arxikh'))

@efarmogi.route('/arxeio')
@login_required
def arxeio():
    ktimata = current_user.ktimata
    return render_template('arxeio.html', ktimata=ktimata)

@efarmogi.route('/rwta_ai/<int:ktima_id>', methods=['POST'])
@login_required
def rwta_ai(ktima_id):
    ktima = vasi.session.get(Ktima, ktima_id)
    if not ktima or ktima.idioktitis != current_user:
        return jsonify({'apantisi': "Μη εξουσιοδοτημένη πρόσβαση."}), 403

    data = request.get_json()
    thermokrasia = data.get('thermokrasia')
    ygrasia = data.get('ygrasia')
    perigrafi = data.get('perigrafi')
    
    # AI Context Injection
    context_msg = f"Ο ελαιώνας είναι {ktima.stremmata} στρέμματα και έχει {ktima.arithmos_dentron} δέντρα. Χρησιμοποίησε αυτά τα δεδομένα για να υπολογίσεις ακριβείς δόσεις φαρμάκων ή λιπασμάτων αν σου ζητηθεί."
    
    # We wrap the existing function logic here to include context
    full_prompt = f"{context_msg} Θερμοκρασία: {thermokrasia}, Υγρασία: {ygrasia}, Καιρός: {perigrafi}. {data.get('perigrafi', '')}"
    apantisi = pare_simvouli_ai(thermokrasia, ygrasia, full_prompt)
    return jsonify({'apantisi': apantisi})

@efarmogi.route('/diagnosi_fwtografias/<int:ktima_id>', methods=['POST'])
@login_required
def diagnosi_fwtografias(ktima_id):
    ktima = vasi.session.get(Ktima, ktima_id)
    if not ktima or ktima.idioktitis != current_user:
        return "Μη εξουσιοδοτημένη ενέργεια", 403
    
    if 'fwtografia' not in request.files:
        flash('Δεν βρέθηκε αρχείο φωτογραφίας.', 'danger')
        return redirect(url_for('arxikh'))
    
    file = request.files['fwtografia']
    if file.filename == '':
        flash('Δεν επιλέχθηκε αρχείο.', 'danger')
        return redirect(url_for('arxikh'))
        
    if file:
        try:
            img = PIL.Image.open(file)
            model = genai.GenerativeModel('gemini-1.5-flash')
            prompt = "Είσαι γεωπόνος. Ανάλυσε αυτή τη φωτογραφία ελαιόδεντρου (φύλλα, καρπός, κορμός). Εντόπισε πιθανές ασθένειες, τροφοπενίες ή προβλήματα. Δώσε σύντομη και ξεκάθαρη διάγνωση 1-2 προτάσεων."
            response = model.generate_content([prompt, img])
            
            nea_diagnosi = Diagnosi(ktima_id=ktima_id, apotelesma=response.text, imerominia=datetime.now())
            vasi.session.add(nea_diagnosi)
            vasi.session.commit()
            flash('Η διάγνωση ολοκληρώθηκε επιτυχώς!', 'success')
        except Exception as e:
            print(f"Σφάλμα Vision AI: {e}")
            flash('Προέκυψε σφάλμα κατά την ανάλυση της φωτογραφίας.', 'danger')
            
    return redirect(url_for('arxikh'))

@efarmogi.route('/analysi_egrafou/<int:ktima_id>', methods=['POST'])
@login_required
def analysi_egrafou(ktima_id):
    ktima = vasi.session.get(Ktima, ktima_id)
    if not ktima or ktima.idioktitis != current_user:
        return "Μη εξουσιοδοτημένη ενέργεια", 403

    if 'fwtografia_analysis' not in request.files:
        flash('Δεν βρέθηκε αρχείο φωτογραφίας.', 'danger')
        return redirect(url_for('arxikh'))

    file = request.files['fwtografia_analysis']
    if file.filename == '':
        flash('Δεν επιλέχθηκε αρχείο.', 'danger')
        return redirect(url_for('arxikh'))

    if file:
        try:
            img = PIL.Image.open(file)
            model = genai.GenerativeModel('gemini-1.5-flash')
            prompt = "Είσαι γεωπόνος. Διάβασε αυτό το έγγραφο ανάλυσης εδάφους/φύλλων. Εντόπισε μόνο τα βασικά προβλήματα ή ελλείψεις (π.χ. έλλειψη καλίου, χαμηλό pH, περίσσεια αζώτου). Γράψε 1-2 προτάσεις με τα ευρήματα."
            response = model.generate_content([prompt, img])
            ktima.analysi_dedomena = response.text
            vasi.session.commit()
            flash('Η ανάλυση του εγγράφου ολοκληρώθηκε και αποθηκεύτηκε.', 'success')
        except Exception as e:
            print(f"Σφάλμα OCR AI: {e}")
            flash('Προέκυψε σφάλμα κατά την ανάγνωση του εγγράφου.', 'danger')

    return redirect(url_for('arxikh'))

@efarmogi.route('/steile_anafora', methods=['POST'])
@login_required
def steile_anafora():
    data = request.get_json()
    onoma = data.get('onoma_ktimatos')
    thermokrasia = data.get('thermokrasia')
    ygrasia = data.get('ygrasia')
    ai_sumvouli = data.get('ai_sumvouli', 'Δεν ζητήθηκε συμβουλή AI.')

    thema = f"Αναφορά Olea AI: {onoma}"
    keimeno = f"""Γεια σας,

Ακολουθεί η αναφορά για το κτήμα σας '{onoma}':

Θερμοκρασία: {thermokrasia}°C
Υγρασία: {ygrasia}%

Συμβουλή AI:
{ai_sumvouli}

Με εκτίμηση,
Η ομάδα του Olea AI
"""
    
    if steile_email(current_user.email, thema, keimeno):
        return jsonify({'minima': 'Επιτυχία'})
    else:
        return jsonify({'minima': 'Σφάλμα'}), 500

@efarmogi.route('/prosthes_ergasia/<int:ktima_id>', methods=['POST'])
@login_required
def prosthes_ergasia(ktima_id):
    ktima = vasi.session.get(Ktima, ktima_id)
    if not ktima or ktima.idioktitis != current_user:
        return "Μη εξουσιοδοτημένη ενέργεια", 403
    
    eidos = request.form.get('eidos_ergasias')
    farmaka = request.form.get('farmaka_lipasmata', '').lower()
    katastasi = request.form.get('katastasi')
    
    # Rule 1: Weed Competition Rule
    if eidos == 'Λίπανση':
        thirty_days_ago = datetime.now() - timedelta(days=30)
        recent_tilling = Ergasia.query.filter(
            Ergasia.ktima_id == ktima_id,
            Ergasia.eidos_ergasias == 'Φρεζάρισμα',
            Ergasia.katastasi == 'Ολοκληρώθηκε',
            Ergasia.imerominia >= thirty_days_ago
        ).first()
        if not recent_tilling:
            flash('Προειδοποίηση: Δεν βρέθηκε καταγραφή για καθαρισμό/φρεζάρισμα τις τελευταίες 30 ημέρες. Τα ζιζάνια θα απορροφήσουν το λίπασμα.', 'warning')

    # Rule 2: Dacus Heat Rule
    if eidos == 'Ψεκασμός' and 'δακος' in farmaka:
        kairos = pare_kairo(ktima.geografiko_platos, ktima.geografiko_mikos)
        if kairos and kairos.get('thermokrasia', 0) >= 33:
            flash('Προειδοποίηση: Η θερμοκρασία είναι >33°C. Ο δάκος αδρανοποιείται. Ο ψεκασμός θα είναι σπατάλη χρημάτων!', 'warning')

    nea_ergasia = Ergasia(
        ktima_id=ktima_id,
        eidos_ergasias=eidos,
        farmaka_lipasmata=request.form.get('farmaka_lipasmata'),
        katastasi=katastasi,
        imerominia=datetime.now()
    )
    
    vasi.session.add(nea_ergasia)
    
    # Έλεγχος για κόστος (Smart Workflow)
    kostos_str = request.form.get('kostos')
    if kostos_str and katastasi == 'Ολοκληρώθηκε':
        try:
            kostos = float(kostos_str)
            if kostos > 0:
                neo_exodo = Exodo(
                    ktima_id=ktima_id,
                    perigrafi=f"Έξοδα εργασίας: {eidos}",
                    poso=kostos,
                    imerominia=datetime.now()
                )
                vasi.session.add(neo_exodo)
        except ValueError:
            pass

    vasi.session.commit()
    return redirect(url_for('arxikh'))

@efarmogi.route('/oloklirosi_ergasias/<int:ktima_id>', methods=['POST'])
@login_required
def oloklirosi_ergasias(ktima_id):
    ktima = vasi.session.get(Ktima, ktima_id)
    if not ktima or ktima.idioktitis != current_user:
        return "Μη εξουσιοδοτημένη ενέργεια", 403

    eidos = request.form.get('eidos_ergasias')
    kostos_str = request.form.get('kostos')

    # Δημιουργία Εργασίας
    nea_ergasia = Ergasia(
        ktima_id=ktima_id,
        eidos_ergasias=eidos,
        katastasi='Ολοκληρώθηκε',
        imerominia=datetime.now()
    )
    vasi.session.add(nea_ergasia)

    # Δημιουργία Εξόδου (αν υπάρχει κόστος)
    try:
        kostos = float(kostos_str)
        if kostos > 0:
            neo_exodo = Exodo(ktima_id=ktima_id, perigrafi=f"{eidos} - Έξοδο", poso=kostos, imerominia=datetime.now())
            vasi.session.add(neo_exodo)
    except (ValueError, TypeError):
        pass

    vasi.session.commit()
    return redirect(url_for('arxikh'))

@efarmogi.route('/prosthes_exodo/<int:ktima_id>', methods=['POST'])
@login_required
def prosthes_exodo(ktima_id):
    ktima = vasi.session.get(Ktima, ktima_id)
    if not ktima or ktima.idioktitis != current_user:
        return "Μη εξουσιοδοτημένη ενέργεια", 403
    
    perigrafi = request.form.get('perigrafi')
    try:
        poso = float(request.form.get('poso'))
    except ValueError:
        poso = 0.0
        
    neo_exodo = Exodo(
        ktima_id=ktima_id,
        perigrafi=perigrafi,
        poso=poso,
        imerominia=datetime.now()
    )
    vasi.session.add(neo_exodo)
    vasi.session.commit()
    return redirect(url_for('arxikh'))

@efarmogi.route('/arxeiothetisi_ktimatos/<int:id>')
@login_required
def arxeiothetisi_ktimatos(id):
    ktima = vasi.session.get(Ktima, id)
    if ktima and ktima.idioktitis == current_user:
        ktima.is_active = False
        vasi.session.commit()
        flash('Το κτήμα αρχειοθετήθηκε επιτυχώς.', 'success')
    return redirect(url_for('arxikh'))

@efarmogi.route('/eggrafi', methods=['GET', 'POST'])
def eggrafi():
    if current_user.is_authenticated:
        return redirect(url_for('arxikh'))
    
    if request.method == 'POST':
        email = request.form.get('email')
        kwdikos = request.form.get('kwdikos')
        epivevaiosi = request.form.get('epivevaiosi_kwdikou')
        
        if not email or not kwdikos or not epivevaiosi:
            flash("Συμπληρώστε όλα τα πεδία.", "warning")
            return render_template('eggrafi.html')

        if kwdikos != epivevaiosi:
            flash("Οι κωδικοί δεν ταιριάζουν.", "danger")
            return render_template('eggrafi.html')
            
        hash_kwdikou = kryptografhsh.generate_password_hash(kwdikos).decode('utf-8')
        neos_xrhsths = Xrhsths(email=email, kwdikos=hash_kwdikou)
        
        try:
            vasi.session.add(neos_xrhsths)
            vasi.session.commit()
            flash("Η εγγραφή ολοκληρώθηκε! Συνδεθείτε.", "success")
            return redirect(url_for('eisodos'))
        except:
            flash("Το Email υπάρχει ήδη.", "danger")
            
    return render_template('eggrafi.html')

@efarmogi.route('/xexasa_kodiko', methods=['GET', 'POST'])
def xexasa_kodiko():
    if request.method == 'POST':
        email = request.form.get('email')
        xrhsths = Xrhsths.query.filter_by(email=email).first()
        
        if xrhsths:
            token = serializer.dumps(email, salt='epanafora-kodikou')
            link = url_for('epanafora_kodikou', token=token, _external=True)
            
            thema = "Επαναφορά Κωδικού - Olea AI"
            keimeno = f"Για να επαναφέρετε τον κωδικό σας, πατήστε στον παρακάτω σύνδεσμο:\n{link}\n\nΟ σύνδεσμος λήγει σε 1 ώρα."
            
            if steile_email(email, thema, keimeno):
                flash('Στάλθηκε email με οδηγίες επαναφοράς.', 'info')
            else:
                flash('Υπήρξε πρόβλημα κατά την αποστολή του email.', 'danger')
        else:
            flash('Δεν βρέθηκε λογαριασμός με αυτό το email.', 'warning')
            
        return redirect(url_for('eisodos'))

    return render_template('xexasa_kodiko.html')

@efarmogi.route('/epanafora_kodikou/<token>', methods=['GET', 'POST'])
def epanafora_kodikou(token):
    try:
        email = serializer.loads(token, salt='epanafora-kodikou', max_age=3600)
    except:
        flash('Ο σύνδεσμος είναι άκυρος ή έχει λήξει.', 'danger')
        return redirect(url_for('xexasa_kodiko'))
    
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
            return redirect(url_for('eisodos'))
            
    return render_template('epanafora_kodikou.html', token=token)

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
            flash("Λάθος email ή κωδικός", "danger")

    return render_template('eisodos.html')

@efarmogi.route('/prosthes_ktima', methods=['POST'])
@login_required
def prosthes_ktima():
    onoma = request.form.get('onoma_ktimatos')
    mikos = request.form.get('geografiko_mikos')
    platos = request.form.get('geografiko_platos')
    typos = request.form.get('typos_edafous')
    klisi = request.form.get('klisi')
    ardefsi = request.form.get('ardefsi')
    poikilia = request.form.get('poikilia')
    stremmata = request.form.get('stremmata')
    arithmos_dentron = request.form.get('arithmos_dentron')
    
    if onoma and mikos and platos:
        try:
            neo = Ktima(
                onoma_ktimatos=onoma, 
                geografiko_mikos=float(mikos), 
                geografiko_platos=float(platos), 
                idioktitis=current_user,
                typos_edafous=typos,
                klisi=klisi,
                ardefsi=ardefsi,
                poikilia=poikilia,
                stremmata=float(stremmata) if stremmata else 0.0,
                arithmos_dentron=int(arithmos_dentron) if arithmos_dentron else 0
            )
            vasi.session.add(neo)
            vasi.session.commit()
            flash('Το κτήμα προστέθηκε επιτυχώς!', 'success')
        except ValueError:
            flash('Σφάλμα στις συντεταγμένες.', 'danger')
    else:
        flash('Συμπληρώστε όλα τα πεδία.', 'warning')
        
    return redirect(url_for('arxikh'))

@efarmogi.route('/lixi_xronias/<int:ktima_id>', methods=['POST'])
@login_required
def lixi_xronias(ktima_id):
    ktima = vasi.session.get(Ktima, ktima_id)
    if not ktima or ktima.idioktitis != current_user:
        return "Μη εξουσιοδοτημένη ενέργεια", 403

    try:
        tonoi_paragogis = float(request.form.get('tonoi_paragogis', 0))
    except ValueError:
        flash('Παρακαλώ εισάγετε έγκυρο αριθμό τόνων.', 'danger')
        return redirect(url_for('arxikh'))

    # 1. Calculate Stats
    synoliko_kostos = sum(exodo.poso for exodo in ktima.exoda if not exodo.archived)
    
    kila_ana_dentro = 0
    if ktima.arithmos_dentron > 0:
        kila_ana_dentro = (tonoi_paragogis * 1000) / ktima.arithmos_dentron

    # 2. Create Archive Record
    arxeio = ArxeioSygkomidis(
        ktima_id=ktima.id,
        tonoi=tonoi_paragogis,
        kila_ana_dentro=kila_ana_dentro,
        synoliko_kostos=synoliko_kostos,
        imerominia=datetime.now()
    )
    vasi.session.add(arxeio)

    # 3. Archive Active Items
    for ergasia in ktima.ergasies:
        ergasia.archived = True
    for exodo in ktima.exoda:
        exodo.archived = True

    # 4. Create New Post-Harvest Task
    nea_ergasia = Ergasia(ktima_id=ktima.id, eidos_ergasias='Ψεκασμός (Χαλκός Μετασυλλεκτικά)', katastasi='Εκκρεμεί', farmaka_lipasmata='Χαλκούχα (Απολύμανση πληγών συγκομιδής)', imerominia=datetime.now())
    vasi.session.add(nea_ergasia)

    vasi.session.commit()
    flash(f'Η χρονιά έκλεισε επιτυχώς! Απόδοση: {kila_ana_dentro:.2f} kg/δέντρο.', 'success')
    return redirect(url_for('arxikh'))

@efarmogi.route('/manifest.json')
def manifest():
    return jsonify({
        "name": "Olea AI",
        "short_name": "Olea",
        "start_url": "/",
        "display": "standalone",
        "background_color": "#f4f7f6",
        "theme_color": "#386641",
        "icons": [
            {
                "src": "https://cdn-icons-png.flaticon.com/512/628/628283.png",
                "sizes": "512x512",
                "type": "image/png"
            }
        ]
    })

@efarmogi.route('/sw.js')
def service_worker():
    response = make_response("""
        self.addEventListener('install', (event) => {
            console.log('Service Worker installing.');
        });
        self.addEventListener('fetch', (event) => {
            event.respondWith(fetch(event.request));
        });
    """)
    response.headers['Content-Type'] = 'application/javascript'
    return response

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
    # This check prevents the scheduler from starting twice when debug=True, fixing the email spam bug.
    if not efarmogi.debug or os.environ.get("WERKZEUG_RUN_MAIN") == "true":
        scheduler = BackgroundScheduler()
        scheduler.add_job(func=aytomatizomenos_elegxos, trigger="cron", hour=8, minute=0)
        scheduler.start()
        print("Scheduler has been started for daily forecast checks at 08:00.")
    port = int(os.environ.get("PORT", 5000))
    efarmogi.run(host='0.0.0.0', port=port, debug=True)