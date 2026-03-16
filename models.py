from datetime import datetime
from flask_login import UserMixin
from core import vasi, diaxeiristh_syndeshs

@diaxeiristh_syndeshs.user_loader
def fortwsh_xrhsth(xrhsths_id):
    try:
        return vasi.session.get(Xrhsths, int(xrhsths_id))
    except Exception:
        # This will prevent a crash if the table doesn't exist yet.
        return None

# Μοντέλο Χρήστη (Database Model)
class Xrhsths(vasi.Model, UserMixin):
    __tablename__ = 'xrhstes'
    id = vasi.Column(vasi.Integer, primary_key=True)
    email = vasi.Column(vasi.String(120), unique=True, nullable=False)
    kwdikos = vasi.Column(vasi.String(60), nullable=False)
    rolos = vasi.Column(vasi.String(20), nullable=False, default='agroths') # 'agroths' ή 'geoponos'
    afm = vasi.Column(vasi.String(9), unique=True, nullable=True)
    ar_tautotitas = vasi.Column(vasi.String(20), unique=True, nullable=True)
    onoma = vasi.Column(vasi.String(100), nullable=True)
    is_verified = vasi.Column(vasi.Boolean, default=False)
    ktimata = vasi.relationship('Ktima', backref='idioktitis', lazy=True)
    apothiki_items = vasi.relationship('Apothiki', backref='idioktitis_apothikis', lazy=True, cascade="all, delete-orphan")
    ai_auto_ergasies = vasi.Column(vasi.Boolean, default=True)
    geoponos_auto_ergasies = vasi.Column(vasi.Boolean, default=True)

    def __repr__(self):
        return f"Xrhsths('{self.email}', Ρόλος: '{self.rolos}')"

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
    syntages = vasi.relationship('Syntagh', backref='ktima', lazy=True, cascade="all, delete-orphan")
    gdd_accumulated = vasi.Column(vasi.Float, default=0.0)
    polygon_geojson = vasi.Column(vasi.Text) # Αποθήκευση συντεταγμένων πολυγώνου
    poikilies_details = vasi.relationship('KtimaPoikilia', backref='ktima', lazy=True, cascade="all, delete-orphan")
    ai_sumvouli_cache = vasi.Column(vasi.Text) # Αποθήκευση απάντησης AI
    ai_sumvouli_date = vasi.Column(vasi.DateTime) # Πότε ρωτήσαμε τελευταία φορά
    agromonitoring_poly_id = vasi.Column(vasi.String(100), nullable=True) # ID πολυγώνου στο Agromonitoring
    ilikia_dentron = vasi.Column(vasi.String(50), default='Άγνωστη')
    puknotita_dentron = vasi.Column(vasi.String(50), default='Κανονική')
    diacheirisi_edafous = vasi.Column(vasi.String(50), default='Άγνωστη')
    ekkremis_erotisi_ai = vasi.Column(vasi.Text, nullable=True)
    gdd_target_anthisi = vasi.Column(vasi.Integer, default=600)
    gdd_target_sygkomidi = vasi.Column(vasi.Integer, default=2500)
    ypsometro = vasi.Column(vasi.Float, nullable=True)
    kalliergeia_typos = vasi.Column(vasi.String(50), default='Συμβατική')

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
    proelevsi = vasi.Column(vasi.String(50), default='Αγρότης') # Αγρότης, AI Γεωπόνος, Γεωπόνος

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
    kila_ladi = vasi.Column(vasi.Float, default=0.0)
    esoda = vasi.Column(vasi.Float, default=0.0)
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

# Μοντέλο για Πολλαπλές Ποικιλίες ανά Κτήμα
class KtimaPoikilia(vasi.Model):
    __tablename__ = 'ktima_poikilies'
    id = vasi.Column(vasi.Integer, primary_key=True)
    ktima_id = vasi.Column(vasi.Integer, vasi.ForeignKey('ktimata.id'), nullable=False)
    poikilia_onoma = vasi.Column(vasi.String(100), nullable=False)
    arithmos_dentron = vasi.Column(vasi.Integer, nullable=False)
    ilikia_dentron = vasi.Column(vasi.String(50), nullable=True)

# Μοντέλο Αποθήκης
class Apothiki(vasi.Model):
    __tablename__ = 'apothiki'
    id = vasi.Column(vasi.Integer, primary_key=True)
    xrhsths_id = vasi.Column(vasi.Integer, vasi.ForeignKey('xrhstes.id'), nullable=False)
    eidos = vasi.Column(vasi.String(50), nullable=False)
    onoma_proiontos = vasi.Column(vasi.String(100), nullable=False)
    posotita = vasi.Column(vasi.Float, nullable=False)
    monada_metrisis = vasi.Column(vasi.String(20), nullable=False)

# Μοντέλο Συνταγής (AI ή Γεωπόνου)
class Syntagh(vasi.Model):
    __tablename__ = 'syntages'
    id = vasi.Column(vasi.Integer, primary_key=True)
    ktima_id = vasi.Column(vasi.Integer, vasi.ForeignKey('ktimata.id'), nullable=False)
    geoponos_id = vasi.Column(vasi.Integer, vasi.ForeignKey('xrhstes.id'), nullable=True) # Ποιος γεωπόνος την έδωσε
    imerominia = vasi.Column(vasi.DateTime, nullable=False, default=datetime.now)
    keimeno = vasi.Column(vasi.Text, nullable=False)
    proelevsi = vasi.Column(vasi.String(50), default='AI Γεωπόνος') # AI Γεωπόνος ή Γεωπόνος