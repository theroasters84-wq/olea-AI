~~~~from flask import Blueprint, url_for, redirect, request, jsonify
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