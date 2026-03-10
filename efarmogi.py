import os
import requests
import smtplib
import PIL.Image
from datetime import datetime, timedelta
from itsdangerous import URLSafeTimedSerializer
from email.mime.text import MIMEText
from dotenv import load_dotenv
from flask import Flask, redirect, url_for, request, render_template, jsonify, flash, make_response, Response
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin, LoginManager, login_user, login_required, logout_user, current_user
from flask_bcrypt import Bcrypt
import google.generativeai as genai
from flask_migrate import Migrate
from apscheduler.schedulers.background import BackgroundScheduler
from sqlalchemy import text
from geoponika import pare_kairo, pare_prognosi_kairou, geoponikos_elegxos, pare_simvouli_ai, steile_email, get_epoxikes_ergasies
import logging

# Φόρτωση μεταβλητών περιβάλλοντος
# Ορίζουμε ρητά τη διαδρομή για το αρχείο .env στον ίδιο φάκελο με το script
basedir = os.path.abspath(os.path.dirname(__file__))
load_dotenv(os.path.join(basedir, '.env'))

# Αρχικοποίηση εφαρμογής
efarmogi = Flask(__name__, template_folder='.')

# Ρύθμιση Logging
logging.basicConfig(level=logging.DEBUG)

# Ρύθμιση Βάσης Δεδομένων (Production & Development)
database_url = os.getenv('DATABASE_URL')
if database_url and database_url.startswith("postgres://"):
    database_url = database_url.replace("postgres://", "postgresql://", 1)

efarmogi.config['SECRET_KEY'] = os.getenv('FLASK_SECRET_KEY') or 'mystiko-kleidi-olea-ai'
efarmogi.config['SQLALCHEMY_DATABASE_URI'] = database_url or 'sqlite:///' + os.path.join(basedir, 'vasi_dedomenwn.db')
efarmogi.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
efarmogi.config['MAIL_FAIL_SILENTLY'] = False
efarmogi.config['MAIL_DEBUG'] = True

# Serializer για tokens επαναφοράς κωδικού
serializer = URLSafeTimedSerializer(efarmogi.config['SECRET_KEY'])

# Ρύθμιση Gemini AI
genai.configure(api_key=os.getenv('AI_API_KEY'))

# Αρχικοποίηση βάσης δεδομένων
vasi = SQLAlchemy(efarmogi)
migrate = Migrate(efarmogi, vasi)
kryptografhsh = Bcrypt(efarmogi)
diaxeiristh_syndeshs = LoginManager(efarmogi)
diaxeiristh_syndeshs.login_view = 'eisodos'
diaxeiristh_syndeshs.login_message = "Παρακαλώ συνδεθείτε για να δείτε αυτή τη σελίδα."

# Μοντέλο Χρήστη (Database Model)
class Xrhsths(vasi.Model, UserMixin):
    __tablename__ = 'xrhstes'

    id = vasi.Column(vasi.Integer, primary_key=True)
    email = vasi.Column(vasi.String(120), unique=True, nullable=False)
    kwdikos = vasi.Column(vasi.String(60), nullable=False)
    ktimata = vasi.relationship('Ktima', backref='idioktitis', lazy=True)

    def __repr__(self):
        return f"Xrhsths('{self.email}')"

@diaxeiristh_syndeshs.user_loader
def fortwsh_xrhsth(xrhsths_id):
    try:
        return vasi.session.get(Xrhsths, int(xrhsths_id))
    except Exception:
        # This will prevent a crash if the table doesn't exist yet.
        return None

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
    fainologiko_stadio = vasi.Column(vasi.String(50), default='Άγνωστο')
    nero_ph = vasi.Column(vasi.Float, nullable=True)
    nero_agwgimotita = vasi.Column(vasi.Float, nullable=True)
    ugrasies = vasi.relationship('KatagrafiUgrasias', backref='ktima', lazy=True, cascade="all, delete-orphan")
    arxeia_sygkomidis = vasi.relationship('ArxeioSygkomidis', backref='ktima', lazy=True, cascade="all, delete-orphan")
    analuseis_edafous = vasi.relationship('AnalysiEdafous', backref='ktima', lazy=True, cascade="all, delete-orphan")
    topikes_ergasies = vasi.Column(vasi.Text)
    teleftaia_enimerosi_ergasion = vasi.Column(vasi.DateTime)
    analysi_dedomena = vasi.Column(vasi.Text)
    diagnoseis = vasi.relationship('Diagnosi', backref='ktima', lazy=True, cascade="all, delete-orphan")
    ergasies = vasi.relationship('Ergasia', backref='ktima', lazy=True, cascade="all, delete-orphan")
    exoda = vasi.relationship('Exodo', backref='ktima', lazy=True, cascade="all, delete-orphan")

    def __repr__(self):
        return f"Ktima('{self.onoma_ktimatos}')"

# Μοντέλο Καταγραφής Υγρασίας Εδάφους
class KatagrafiUgrasias(vasi.Model):
    __tablename__ = 'katagrafes_ugrasias'
    
    id = vasi.Column(vasi.Integer, primary_key=True)
    ktima_id = vasi.Column(vasi.Integer, vasi.ForeignKey('ktimata.id'), nullable=False)
    pososto = vasi.Column(vasi.Float, nullable=False)
    imerominia = vasi.Column(vasi.DateTime, nullable=False, default=datetime.now)

    def __repr__(self):
        return f"Ugrasia('{self.pososto}%', '{self.imerominia}')"

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

# Μοντέλο Ανάλυσης Εδάφους (Smart Fertilization)
class AnalysiEdafous(vasi.Model):
    __tablename__ = 'analuseis_edafous'
    
    id = vasi.Column(vasi.Integer, primary_key=True)
    ktima_id = vasi.Column(vasi.Integer, vasi.ForeignKey('ktimata.id'), nullable=False)
    ph = vasi.Column(vasi.Float)
    organiki_ousia = vasi.Column(vasi.Float)
    azwto = vasi.Column(vasi.Float)
    fwsforos = vasi.Column(vasi.Float)
    kalio = vasi.Column(vasi.Float)
    imerominia = vasi.Column(vasi.DateTime, nullable=False, default=datetime.now)

# Προληπτικός Σύμβουλος (Εγκυκλοπαίδεια)
def paragwgi_protasewn(ktima, thermokrasia, ygrasia, perigrafi):
    mhnas = datetime.now().month
    protaseis = []
    now = datetime.now()

    # Helper to find days since last specific task
    def get_days_since_task(keyword):
        relevant_tasks = [
            t for t in ktima.ergasies 
            if not t.archived and (keyword in t.eidos_ergasias or (t.farmaka_lipasmata and keyword in t.farmaka_lipasmata))
        ]
        if not relevant_tasks:
            return None
        latest_task = max(relevant_tasks, key=lambda x: x.imerominia)
        return (now - latest_task.imerominia).days

    # Get a list of completed tasks for the current season (for simple existence checks)
    completed_tasks_names = [e.eidos_ergasias for e in ktima.ergasies if not e.archived]

    # Phase 18: Agronomic Profiling Rules
    if ktima.klisi == 'Επικλινές/Πλαγιά' and ('βροχή' in perigrafi.lower() or 'βροχη' in perigrafi.lower()):
        protaseis.append("⚠️ Κλίση & Βροχή: Κίνδυνος έκπλυσης λιπάσματος. Αποφύγετε τη λίπανση πριν τη βροχή.")

    if ktima.typos_edafous == 'Αργιλώδες' and ('βροχή' in perigrafi.lower() or 'βροχη' in perigrafi.lower()):
        protaseis.append("⚠️ Αργιλώδες Έδαφος: Κίνδυνος ασφυξίας ριζών λόγω νεροκρατήματος. Ελέγξτε την αποστράγγιση.")

    if ktima.ardefsi == 'Ξηρικό' and thermokrasia > 30:
        protaseis.append("🔥 Ξηρικό & Ζέστη: Αποφύγετε το βαθύ όργωμα για να μην χαθεί η πολύτιμη υγρασία του εδάφους.")

    if ktima.klisi == 'Ρέμα/Κοιλότητα' and thermokrasia < 5 and mhnas in [12, 1, 2, 3]:
        protaseis.append("❄️ Ρέμα/Κοιλότητα: Αυξημένος κίνδυνος παγετού (frost pocket).")

    # Water Quality Rules
    if ktima.nero_agwgimotita and ktima.nero_agwgimotita > 3.0:
         protaseis.append("⚠️ Τοξικότητα Αλάτων: Η αγωγιμότητα του νερού είναι πολύ υψηλή (>3.0 mS/cm). Κίνδυνος ξηράνσεων στα φύλλα. Συνιστάται έκπλυση εδάφους ή χρήση βελτιωτικών.")

    # Soil Moisture Stress - Safely check for records
    if ktima.ugrasies:
        try:
            # Accessing the relationship triggers the lazy load.
            # If the collection is empty, [-1] will raise an IndexError.
            latest_moisture = ktima.ugrasies[-1].pososto
            if latest_moisture < 20 and mhnas in [6, 7, 8, 9]:
                protaseis.append(f"💧 Έντονο Υδατικό Στρες: Η υγρασία εδάφους είναι στο {latest_moisture}%. Απαιτείται άμεση άρδευση για να μην συρρικνωθεί ο καρπός.")
        except IndexError:
            # This is expected if no moisture records exist yet. Safely ignore.
            pass

    # Weather-Aware Fertilization (Months 2, 3, 4)
    if mhnas in [2, 3, 4]:
        if 'βροχή' not in perigrafi.lower() and 'βροχη' not in perigrafi.lower():
            protaseis.append("⚠️ Ανομβρία: Αν προγραμματίζετε επιφανειακή αζωτούχο λίπανση, προτιμήστε υδρολίπανση ή αναμείνατε βροχοπτώσεις για να μην εξατμιστεί το άζωτο.")

    # Άνοιξη (Μάρτιος, Απρίλιος)
    if mhnas in [3, 4]:
        # Fertilization check (Time-Aware: 60 days)
        days_since_fert = get_days_since_task('Λίπανση')
        if days_since_fert is None:
             days_since_fert = get_days_since_task('Άζωτο')

        if days_since_fert is None or days_since_fert > 60:
            protaseis.append("🌱 Άνοιξη: Ιδανική περίοδος για βασική λίπανση (Άζωτο & Βόριο).")

        # Pruning check
        has_pruned = any('Κλάδεμα' in task for task in completed_tasks_names)
        if not has_pruned:
            protaseis.append("✂️ Άνοιξη: Ολοκληρώστε το κλάδεμα διαμόρφωσης και καρποφορίας.")

        # --- MODIFIED COPPER/SPRAY LOGIC ---
        # Phenological stage takes precedence over simple humidity/time rules.
        if ktima.fainologiko_stadio == 'Άνθιση':
            protaseis.append("🛑 ΑΠΑΓΟΡΕΥΣΗ ΨΕΚΑΣΜΩΝ: Το δέντρο βρίσκεται σε Άνθιση! Σταματήστε ΑΜΕΣΩΣ κάθε ψεκασμό (ειδικά με χαλκό ή διαφυλλικά) για να μην προκαλέσετε κάψιμο των ανθέων και πτώση της παραγωγής.")
        elif ktima.fainologiko_stadio == 'Σχηματισμός Ταξιανθιών':
            days_since_copper = get_days_since_task('Χαλκ')
            if days_since_copper is None or days_since_copper > 25:
                protaseis.append("⚠️ Κρίσιμο Στάδιο: Τα δέντρα είναι στο 'μούρο' (Σχηματισμός Ταξιανθιών) και η προστασία του χαλκού έχει λήξει. Απαιτείται άμεσα ψεκασμός πριν ανοίξουν τα άνθη.")
        # Fallback to original time/humidity logic if stage is not critical (e.g., 'Άγνωστο', 'Λήθαργος')
        elif ygrasia > 65:
            days_since_copper = get_days_since_task('Χαλκ')
            if days_since_copper is not None:
                if days_since_copper <= 25:
                    protaseis.append(f"🛡️ Ενεργή Προστασία: Υψηλή υγρασία, αλλά ο ελαιώνας προστατεύεται από τον χαλκό που εφαρμόστηκε πριν {days_since_copper} μέρες.")
                else:
                    protaseis.append(f"⚠️ Λήξη Προστασίας: Έχουν περάσει {days_since_copper} μέρες από τον τελευταίο ψεκασμό χαλκού. Η δράση του έχει εξασθενήσει. Λόγω υγρασίας, απαιτείται επαναληπτικός ψεκασμός.")
            else:
                protaseis.append("💧 Υψηλή υγρασία: Συνιστάται προληπτικός ψεκασμός με χαλκούχα για το Κυκλοκόνιο.")
        protaseis.append("⚠️ Προσοχή στους ψεκασμούς: ΜΗΝ αναμειγνύετε ποτέ χαλκό με αμινοξέα (κίνδυνος φυτοτοξικότητας)!")
    
    # Άνθιση / Αρχές Καλοκαιριού (Μάιος, Ιούνιος)
    elif mhnas in [5, 6]:
        if ktima.fainologiko_stadio == 'Άνθιση':
             protaseis.append("🌼 Περίοδος Άνθισης/Μούρου: ΑΠΑΓΟΡΕΥΕΤΑΙ η χρήση χαλκού (καίει το άνθος). Προγραμματίστε καταπολέμηση ζιζανίων.")
    
    # Καλοκαίρι (Ιούλιος, Αύγουστος)
    elif mhnas in [7, 8]:
        protaseis.append("☀️ Καλοκαίρι: Κρίσιμη περίοδος για άρδευση (πήξη πυρήνα).")
            
    # Φθινόπωρο / Χειμώνας (Σεπτέμβριος - Φεβρουάριος)
    elif mhnas in [9, 10, 11, 12, 1, 2]:
        protaseis.append("🍂 Ελαιογένεση/Συγκομιδή: Έμφαση στο Κάλιο. Μετά τη συγκομιδή ή χαλάζι/παγετό, ψεκάστε άμεσα με χαλκό για απολύμανση πληγών.")

    # Scientific Memory: Boron & Temperature Rule (Refactored for performance and safety)
    if thermokrasia < 12:
        days_since_boron = get_days_since_task('Βόριο')
        if days_since_boron is None or days_since_boron > 25:
            protaseis.append("📊 Επιστημονική Μνήμη: Η θερμοκρασία είναι < 12°C. Προτείνεται εφαρμογή Βορίου, καθώς η απορρόφησή του είναι μειωμένη σε χαμηλές θερμοκρασίες και μπορεί να χρειαστεί επανάληψη.")

    # Smart Dacus Management (June - October)
    if mhnas in [6, 7, 8, 9, 10]:
        if thermokrasia >= 34:
            protaseis.append("☀️ Καύσωνας & Δάκος: Η θερμοκρασία ξεπερνά τους 34°C. ΑΠΑΓΟΡΕΥΕΤΑΙ ο ψεκασμός. Ο πληθυσμός του δάκου καταρρέει φυσικά από τη ζέστη. Εξοικονομήστε χρήματα και φάρμακα!")
        elif 20 <= thermokrasia <= 30 and ygrasia > 60 and ktima.fainologiko_stadio in ['Ανάπτυξη Καρπού', 'Ωρίμανση']:
            protaseis.append("🪰 Κίνδυνος Δάκου: Οι τρέχουσες συνθήκες (δροσιά και υγρασία) είναι ιδανικές για δακοπροσβολή στον καρπό. Ελέγξτε άμεσα τις παγίδες σας και προγραμματίστε δολωματικό ψεκασμό αν τα επίπεδα είναι υψηλά.")

    # Adaptive Memory from Diagnosis
    if ktima.diagnoseis:
        teleytaia_diagnosi = ktima.diagnoseis[-1]
        protaseis.append(f"👁️ Μνήμη Διάγνωσης: Το AI είχε εντοπίσει πρόσφατα: {teleytaia_diagnosi.apotelesma}. Προσαρμόστε τις ενέργειές σας.")

    # Smart Fertilization Logic
    if ktima.analuseis_edafous:
        teleytaia_analysi = ktima.analuseis_edafous[-1]
        if teleytaia_analysi.ph and teleytaia_analysi.ph > 7.5:
            protaseis.append("⚠️ Υψηλό pH (>7.5): Κίνδυνος έλλειψης Βορίου και Ιχνοστοιχείων. Προτείνεται διαφυλλική εφαρμογή.")

    return protaseis

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
            
            # Save generic analysis text
            ktima.analysi_dedomena = response.text
            
            # Smart Extraction for Database
            extraction_prompt = """
            Extract the following soil data from the image and return ONLY a JSON object:
            {"ph": float, "organiki_ousia": float, "azwto": float, "fwsforos": float, "kalio": float}
            If a value is not found, use null. Do not use markdown formatting.
            """
            extraction_response = model.generate_content([extraction_prompt, img])
            try:
                import json
                data = json.loads(extraction_response.text.strip().replace('```json', '').replace('```', ''))
                nea_analysi = AnalysiEdafous(
                    ktima_id=ktima_id,
                    ph=data.get('ph'),
                    organiki_ousia=data.get('organiki_ousia'),
                    azwto=data.get('azwto'),
                    fwsforos=data.get('fwsforos'),
                    kalio=data.get('kalio')
                )
                vasi.session.add(nea_analysi)
            except Exception as e:
                print(f"Extraction Error: {e}")

            vasi.session.commit()
            flash('Η ανάλυση του εγγράφου ολοκληρώθηκε και αποθηκεύτηκε.', 'success')
        except Exception as e:
            print(f"Σφάλμα OCR AI: {e}")
            flash('Προέκυψε σφάλμα κατά την ανάγνωση του εγγράφου.', 'danger')

    return redirect(url_for('arxikh'))

@efarmogi.route('/anagnorisi_stadiou/<int:ktima_id>', methods=['POST'])
@login_required
def anagnorisi_stadiou(ktima_id):
    ktima = vasi.session.get(Ktima, ktima_id)
    if not ktima or ktima.idioktitis != current_user:
        flash('Μη εξουσιοδοτημένη ενέργεια.', 'danger')
        return redirect(url_for('arxikh'))

    if 'fwtografia_stadiou' not in request.files:
        flash('Δεν βρέθηκε αρχείο φωτογραφίας.', 'danger')
        return redirect(url_for('arxikh'))

    file = request.files['fwtografia_stadiou']
    if file.filename == '':
        flash('Δεν επιλέχθηκε αρχείο.', 'danger')
        return redirect(url_for('arxikh'))

    if file:
        try:
            img = PIL.Image.open(file)
            model = genai.GenerativeModel('gemini-1.5-flash')
            prompt = "Είσαι κορυφαίος γεωπόνος. Δες αυτή τη φωτογραφία από κλαδί ελιάς. Σε ποιο φαινολογικό στάδιο βρίσκεται; Επίλεξε ΑΥΣΤΗΡΑ ΜΟΝΟ ΜΙΑ από τις παρακάτω φράσεις, χωρίς καμία άλλη λέξη ή τελεία: Λήθαργος, Βλαστική Ανάπτυξη, Σχηματισμός Ταξιανθιών, Άνθιση, Καρπόδεση, Ανάπτυξη Καρπού, Ωρίμανση."
            response = model.generate_content([prompt, img])
            
            stage_text = response.text.strip().replace('.', '')
            ktima.fainologiko_stadio = stage_text
            vasi.session.commit()
            flash(f'Το φαινολογικό στάδιο του κτήματος ορίστηκε σε: {stage_text}', 'success')
        except Exception as e:
            print(f"Σφάλμα Stage Vision AI: {e}")
            flash('Προέκυψε σφάλμα κατά την αναγνώριση του σταδίου.', 'danger')
            
    return redirect(url_for('arxikh'))

@efarmogi.route('/ektimisi_paragogis/<int:ktima_id>', methods=['POST'])
@login_required
def ektimisi_paragogis(ktima_id):
    ktima = vasi.session.get(Ktima, ktima_id)
    if not ktima or ktima.idioktitis != current_user:
        return "Μη εξουσιοδοτημένη ενέργεια", 403

    if 'fwtografia_paragogis' not in request.files:
        flash('Δεν βρέθηκε αρχείο φωτογραφίας.', 'danger')
        return redirect(url_for('arxikh'))

    file = request.files['fwtografia_paragogis']
    if file.filename == '':
        flash('Δεν επιλέχθηκε αρχείο.', 'danger')
        return redirect(url_for('arxikh'))

    if file:
        try:
            img = PIL.Image.open(file)
            model = genai.GenerativeModel('gemini-1.5-flash')
            prompt = f"Είσαι ειδικός γεωπόνος. Μετρα οσες ελιες βλεπεις στο κλαδι. Το κτημα εχει {ktima.arithmos_dentron} δεντρα. Κανε μια εκτιμηση για την συνολικη παραγωγη σε κιλα λαδιου. Δωσε μονο τον αριθμο και μια συντομη αιτιολογηση."
            response = model.generate_content([prompt, img])
            flash(f'Εκτίμηση Παραγωγής: {response.text}', 'info')
        except Exception as e:
            print(f"Σφάλμα Yield AI: {e}")
            flash('Προέκυψε σφάλμα κατά την εκτίμηση παραγωγής.', 'danger')
            
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

@efarmogi.route('/prosthes_ugrasia/<int:ktima_id>', methods=['POST'])
@login_required
def prosthes_ugrasia(ktima_id):
    ktima = vasi.session.get(Ktima, ktima_id)
    if not ktima or ktima.idioktitis != current_user:
        return "Μη εξουσιοδοτημένη ενέργεια", 403
    
    try:
        pososto = float(request.form.get('pososto'))
        nea_ugrasia = KatagrafiUgrasias(ktima_id=ktima_id, pososto=pososto)
        vasi.session.add(nea_ugrasia)
        vasi.session.commit()
        flash('Η μέτρηση υγρασίας καταγράφηκε.', 'success')
    except ValueError:
        flash('Μη έγκυρη τιμή.', 'danger')
        
    return redirect(url_for('arxikh'))

@efarmogi.route('/enimerosi_nerou/<int:ktima_id>', methods=['POST'])
@login_required
def enimerosi_nerou(ktima_id):
    ktima = vasi.session.get(Ktima, ktima_id)
    if not ktima or ktima.idioktitis != current_user:
        return "Μη εξουσιοδοτημένη ενέργεια", 403
    
    try:
        ph = request.form.get('nero_ph')
        ec = request.form.get('nero_agwgimotita')
        
        if ph: ktima.nero_ph = float(ph)
        if ec: ktima.nero_agwgimotita = float(ec)
        
        vasi.session.commit()
        flash('Τα στοιχεία ποιότητας νερού ενημερώθηκαν.', 'success')
    except ValueError:
        flash('Μη έγκυρες τιμές.', 'danger')
        
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
            
            try:
                steile_email(email, thema, keimeno, raise_exception=True)
                flash('Στάλθηκε email με οδηγίες επαναφοράς.', 'info')
                return redirect(url_for('eisodos'))
            except Exception as e:
                print(f"EMAIL ERROR: {str(e)}", flush=True)
                flash('Σφάλμα κατά την αποστολή του email. Ελέγξτε τα logs.', 'danger')
                return redirect(url_for('xexasa_kodiko'))
        else:
            flash('Δεν βρέθηκε λογαριασμός με αυτό το email.', 'warning')
            return redirect(url_for('xexasa_kodiko'))

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

@efarmogi.route('/ping')
def ping():
    return "Pong", 200

@efarmogi.route('/icon.svg')
def serve_icon():
    svg = '''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100">
      <rect width="100" height="100" rx="22" fill="#4A7C59"/>
      <text x="50%" y="50%" font-size="55" text-anchor="middle" dominant-baseline="central">🫒</text>
    </svg>'''
    return Response(svg, mimetype='image/svg+xml')

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
                "src": "/icon.svg",
                "sizes": "any",
                "type": "image/svg+xml"
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
            // For now, just let the browser handle the fetch request normally.
            // This avoids errors with special requests (e.g., cross-origin, only-if-cached).
            return;
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

@efarmogi.route('/updb')
def update_db_schema():
    try:
        # Δημιουργία όλων των πινάκων αν δεν υπάρχουν (για περιπτώσεις όπως το Render)
        vasi.create_all()
        
        with vasi.engine.connect() as conn:
            # Προσθήκη fainologiko_stadio
            try:
                conn.execute(text("ALTER TABLE ktimata ADD COLUMN fainologiko_stadio VARCHAR(50) DEFAULT 'Άγνωστο'"))
            except Exception as e:
                print(f"Column fainologiko_stadio exists or error: {e}")

            # Προσθήκη topikes_ergasies
            try:
                conn.execute(text("ALTER TABLE ktimata ADD COLUMN topikes_ergasies TEXT"))
            except Exception as e:
                print(f"Column topikes_ergasies exists or error: {e}")

            # Προσθήκη teleftaia_enimerosi_ergasion
            try:
                conn.execute(text("ALTER TABLE ktimata ADD COLUMN teleftaia_enimerosi_ergasion TIMESTAMP"))
            except Exception as e:
                print(f"Column teleftaia_enimerosi_ergasion exists or error: {e}")
                
            # Προσθήκη nero_ph
            try:
                conn.execute(text("ALTER TABLE ktimata ADD COLUMN nero_ph FLOAT"))
            except Exception as e:
                print(f"Column nero_ph exists or error: {e}")

            # Προσθήκη nero_agwgimotita
            try:
                conn.execute(text("ALTER TABLE ktimata ADD COLUMN nero_agwgimotita FLOAT"))
            except Exception as e:
                print(f"Column nero_agwgimotita exists or error: {e}")
            
            # Create table analuseis_edafous if not exists
            vasi.create_all()
            
            conn.commit()
        return "Η βάση δεδομένων ενημερώθηκε επιτυχώς! Τώρα μπορείτε να πάτε στην <a href='/'>Αρχική</a>."
    except Exception as e:
        return f"Σφάλμα κατά την ενημέρωση: {e}", 500

@efarmogi.route('/ping')
def ping_keep_alive():
    return "OK", 200

@efarmogi.route('/ai_vision', methods=['POST'])
@login_required
def ai_vision():
    if 'image' not in request.files:
        return jsonify({'error': 'Δεν βρέθηκε αρχείο εικόνας'}), 400

    file = request.files['image']
    if file.filename == '':
        return jsonify({'error': 'Δεν επιλέχθηκε αρχείο'}), 400

    try:
        img = PIL.Image.open(file)
        model = genai.GenerativeModel('gemini-1.5-flash')
        prompt = "Λειτούργησε ως έμπειρος γεωπόνος. Ανάλυσε αυτή την εικόνα και εντόπισε το φαινολογικό στάδιο της ελιάς ή πιθανές ασθένειες."
        response = model.generate_content([prompt, img])
        return jsonify({'result': response.text})
    except Exception as e:
        return jsonify({'error': f"Σφάλμα AI: {str(e)}"}), 500

# Start Scheduler for Gunicorn (Production)
if not efarmogi.debug or os.environ.get("WERKZEUG_RUN_MAIN") == "true":
    scheduler = BackgroundScheduler()
    scheduler.add_job(func=aytomatizomenos_elegxos, trigger="cron", hour=8, minute=0)
    scheduler.start()
    print("Scheduler has been started for daily forecast checks at 08:00.")

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    efarmogi.run(host='0.0.0.0', port=port, debug=True)