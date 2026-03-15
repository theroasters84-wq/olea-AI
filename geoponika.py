import os
import requests
import smtplib
from email.mime.text import MIMEText
from datetime import datetime
import time

# Βοηθητική συνάρτηση για τον καιρό
def pare_kairo(lat, lng):
    api_key = os.getenv('WEATHER_API_KEY')
    
    if not api_key:
        print("⚠️ ΠΡΟΣΟΧΗ: Δεν βρέθηκε το WEATHER_API_KEY. Ελέγξτε το αρχείο .env")
        return None

    try:
        url = f"https://api.openweathermap.org/data/2.5/weather?lat={lat}&lon={lng}&appid={api_key}&units=metric&lang=el"
        response = requests.get(url, timeout=5)
        data = response.json()
        if response.status_code == 200:
            wind_speed = data.get('wind', {}).get('speed', 0)
            wind_deg = data.get('wind', {}).get('deg', 0)
            
            # Μετατροπή m/s σε Μποφόρ (Beaufort scale)
            bf = 0
            if wind_speed >= 32.7: bf = 12
            elif wind_speed >= 28.5: bf = 11
            elif wind_speed >= 24.5: bf = 10
            elif wind_speed >= 20.8: bf = 9
            elif wind_speed >= 17.2: bf = 8
            elif wind_speed >= 13.9: bf = 7
            elif wind_speed >= 10.8: bf = 6
            elif wind_speed >= 8.0: bf = 5
            elif wind_speed >= 5.5: bf = 4
            elif wind_speed >= 3.4: bf = 3
            elif wind_speed >= 1.6: bf = 2
            elif wind_speed >= 0.3: bf = 1
            
            return {
                'thermokrasia': data['main']['temp'],
                'perigrafi': data['weather'][0]['description'],
                'ygrasia': data['main']['humidity'],
                'anemos_taxytita': wind_speed,
                'anemos_dieythinsi': wind_deg,
                'anemos_mpofor': bf
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
        response = requests.get(url, timeout=5)
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

# AI Γεωπόνος
def pare_simvouli_ai(thermokrasia, ygrasia, perigrafi):
    from core import ai_client, api_key_ai
    
    if not api_key_ai:
        print("⚠️ AI API Key missing in geoponika.py call")
        return "Το σύστημα AI δεν είναι ενεργοποιημένο (λείπει το κλειδί)."

    try:
        prompt = (
            f"Είσαι ένας ειδικός γεωπόνος. Λάβε υπόψη τα εξής δεδομένα:\n"
            f"{perigrafi}\n\n"
            f"Δώσε μια στοχευμένη, σύντομη συμβουλή (2-3 προτάσεις) για τις άμεσες ενέργειες στο κτήμα."
        )
        
        # Simple Retry Logic for Rate Limiting
        for attempt in range(3):
            try:
                print(f"🔄 Προσπάθεια AI {attempt+1}/3...")
                response = ai_client.models.generate_content(model='gemini-2.5-flash', contents=prompt)
                
                if response and response.text:
                    print("✅ Το AI απάντησε επιτυχώς!")
                    return response.text
                else:
                    print(f"⚠️ Το AI επέστρεψε κενή απάντηση (Προσπάθεια {attempt+1})")

            except Exception as e:
                if "429" in str(e) or "quota" in str(e).lower():
                    print(f"⏳ Rate Limit (429) - Αναμονή... ({e})")
                    time.sleep(3 * (attempt + 1)) # Backoff: 3s, 6s, 9s
                    continue
                print(f"❌ Σφάλμα στη προσπάθεια {attempt+1}: {e}")
                raise e
    except Exception as e:
        print("\n" + "!"*50)
        print(f"🔴 ΚΡΙΣΙΜΟ ΣΦΑΛΜΑ AI: {e}")
        print("!"*50 + "\n")
        # Επιστροφή φιλικού μηνύματος αντί για None/null
        return "Το σύστημα AI είναι προσωρινά μη διαθέσιμο λόγω μεγάλου φόρτου. Δοκιμάστε ξανά σε λίγο."

# Λειτουργία Αποστολής Email
def steile_email(paraliptis, thema, keimeno, raise_exception=False):
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
        # Προσθήκη timeout 10 δευτερολέπτων για να μην κολλάει η εφαρμογή
        with smtplib.SMTP('smtp.gmail.com', 587, timeout=10) as server:
            server.starttls()
            server.login(sender_email, sender_password)
            server.send_message(msg)
        return True
    except Exception as e:
        print(f"Σφάλμα αποστολής email: {e}")
        if raise_exception:
            raise e
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

# --- ΝΕΕΣ ΣΥΝΑΡΤΗΣΕΙΣ AGROMONITORING API ---

def get_agro_soil_data(poly_id):
    api_key = os.getenv('AGROMONITORING_API_KEY')
    if not api_key or not poly_id: return None
    try:
        res = requests.get(f"http://api.agromonitoring.com/agro/1.0/soil?polyid={poly_id}&appid={api_key}", timeout=5)
        if res.status_code == 200: return res.json()
    except Exception as e: print(f"Soil Data Error: {e}")
    return None

def get_agro_uvi(poly_id):
    api_key = os.getenv('AGROMONITORING_API_KEY')
    if not api_key or not poly_id: return None
    try:
        res = requests.get(f"http://api.agromonitoring.com/agro/1.0/uvi?polyid={poly_id}&appid={api_key}", timeout=5)
        if res.status_code == 200: return res.json()
    except Exception as e: print(f"UVI Error: {e}")
    return None

def get_agro_forecast(poly_id):
    api_key = os.getenv('AGROMONITORING_API_KEY')
    if not api_key or not poly_id: return None
    try:
        res = requests.get(f"http://api.agromonitoring.com/agro/1.0/weather/forecast?polyid={poly_id}&appid={api_key}", timeout=5)
        if res.status_code == 200: return res.json()
    except Exception as e: print(f"Agro Forecast Error: {e}")
    return None

def get_agro_gdd(poly_id):
    api_key = os.getenv('AGROMONITORING_API_KEY')
    if not api_key or not poly_id: return None
    try:
        end = int(time.time())
        start = int(datetime(datetime.now().year, 1, 1).timestamp())
        res = requests.get(f"http://api.agromonitoring.com/agro/1.0/weather/history/accumulated_temperature?polyid={poly_id}&threshold=10&start={start}&end={end}&appid={api_key}", timeout=5)
        if res.status_code == 200: return res.json()
    except Exception as e: print(f"Agro GDD Error: {e}")
    return None

def ypologismos_anagkon_nerou(thermokrasia, mhnas, arithmos_dentron, stremmata):
    if not arithmos_dentron or not stremmata or arithmos_dentron <= 0 or stremmata <= 0:
        return 0
        
    # Συντελεστής Καλλιέργειας Ελιάς (Kc)
    if mhnas in [6, 7, 8]:
        kc = 0.65
    elif mhnas in [4, 5, 9, 10]:
        kc = 0.55
    else:
        kc = 0.40
        
    # Προσεγγιστική Ημερήσια Εξατμισοδιαπνοή (ETo) σε mm
    if thermokrasia > 33: eto = 6.5
    elif thermokrasia > 28: eto = 5.5
    elif thermokrasia > 22: eto = 4.0
    else: eto = 2.5
        
    tetragonika_ana_dentro = (stremmata * 1000) / arithmos_dentron
    litra_ana_dentro_imera = eto * kc * tetragonika_ana_dentro * 0.5
    return int(litra_ana_dentro_imera)

def pare_ypsometro(lat, lng):
    try:
        url = f"https://api.open-meteo.com/v1/elevation?latitude={lat}&longitude={lng}"
        response = requests.get(url, timeout=5)
        if response.status_code == 200:
            data = response.json()
            if 'elevation' in data and data['elevation']:
                return float(data['elevation'][0])
    except Exception as e:
        print(f"Σφάλμα λήψης υψομέτρου: {e}")
    return None