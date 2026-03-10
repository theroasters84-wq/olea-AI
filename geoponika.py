import os
import requests
import smtplib
from email.mime.text import MIMEText
import google.generativeai as genai
from datetime import datetime

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