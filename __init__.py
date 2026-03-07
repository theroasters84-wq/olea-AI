from flask import Flask
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
    efarmogi.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///vasi_dedomenwn.db'
    efarmogi.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

    vasi.init_app(efarmogi)
    kryptografhsh.init_app(efarmogi)
    diaxeiristh_syndeshs.init_app(efarmogi)

    from efarmogi.dromologia import bp
    efarmogi.register_blueprint(bp)

    with efarmogi.app_context():
        vasi.create_all()

    return efarmogi