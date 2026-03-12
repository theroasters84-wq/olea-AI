import os
from dotenv import load_dotenv
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_bcrypt import Bcrypt
from flask_login import LoginManager
from flask_migrate import Migrate
from itsdangerous import URLSafeTimedSerializer
from google import genai

basedir = os.path.abspath(os.path.dirname(__file__))
load_dotenv(os.path.join(basedir, '.env'))

# Preserving template_folder='.' and setting static_folder to basedir to reliably serve files
efarmogi = Flask(__name__, template_folder='.', static_folder=basedir, static_url_path='/static')
database_url = os.getenv('DATABASE_URL')
if database_url and database_url.startswith("postgres://"):
    database_url = database_url.replace("postgres://", "postgresql://", 1)

efarmogi.config['SECRET_KEY'] = os.getenv('FLASK_SECRET_KEY') or 'mystiko-kleidi-olea-ai'
efarmogi.config['SQLALCHEMY_DATABASE_URI'] = database_url or 'sqlite:///' + os.path.join(basedir, 'vasi_dedomenwn.db')
efarmogi.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
efarmogi.config['MAIL_FAIL_SILENTLY'] = False
efarmogi.config['MAIL_DEBUG'] = True

vasi = SQLAlchemy(efarmogi)
migrate = Migrate(efarmogi, vasi)
kryptografhsh = Bcrypt(efarmogi)
diaxeiristh_syndeshs = LoginManager(efarmogi)
diaxeiristh_syndeshs.login_view = 'auth.eisodos'
diaxeiristh_syndeshs.login_message = "Παρακαλώ συνδεθείτε για να δείτε αυτή τη σελίδα."
serializer = URLSafeTimedSerializer(efarmogi.config['SECRET_KEY'])

# Ρύθμιση Gemini AI
api_key_env = os.getenv('AI_API_KEY')
api_key_ai = api_key_env.strip() if api_key_env else None # Αφαιρούμε τυχόν κενά

print("\n" + "="*50)
if not api_key_ai:
    print("❌ ΚΡΙΣΙΜΟ ΣΦΑΛΜΑ: Η μεταβλητή 'AI_API_KEY' δεν βρέθηκε.")
    print("   Βεβαιωθείτε ότι υπάρχει αρχείο .env και περιέχει τη γραμμή:")
    print("   AI_API_KEY=το-κλειδί-σας")
else:
    print(f"✅ Το AI API Key φορτώθηκε επιτυχώς: {api_key_ai[:5]}...{api_key_ai[-4:]}")
print("="*50 + "\n")

ai_client = genai.Client(api_key=api_key_ai)