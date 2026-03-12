from core import efarmogi
from auth import auth_bp
from ai_tools import ai_bp
from core_app import core_bp

efarmogi.register_blueprint(auth_bp)
efarmogi.register_blueprint(ai_bp)
efarmogi.register_blueprint(core_bp)