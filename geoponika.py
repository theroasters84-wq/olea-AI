import os
import requests
import smtplib
from email.mime.text import MIMEText
from datetime import datetime
import time
from google.genai import types
from core_app import cache

# --- Έξυπνη Μνήμη (Cache) για τις κλήσεις στο Internet ---
_api_cache = {}
def _cached_get(url, ttl_seconds=1800):
    now = time.time()
    if url in _api_cache and (now - _api_cache[url][1]) < ttl_seconds:
        return _api_cache[url][0]
    res = requests.get(url, timeout=5)
    if res.status_code == 200:
        _api_cache[url] = (res.json(), now)
        return res.json()
    return None

# Βοηθητική συνάρτηση για τον καιρό
@cache.memoize(timeout=1800)
def pare_kairo(lat, lng):
    api_key = os.getenv('WEATHER_API_KEY')
    
    if not api_key:
        print("⚠️ ΠΡΟΣΟΧΗ: Δεν βρέθηκε το WEATHER_API_KEY. Ελέγξτε το αρχείο .env")
        return None

    try:
        url = f"https://api.openweathermap.org/data/2.5/weather?lat={lat}&lon={lng}&appid={api_key}&units=metric&lang=el"
        data = _cached_get(url, ttl_seconds=600) # Κρατάει τον καιρό έτοιμο για 10 λεπτά
        if data:
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
            print(f"⚠️ Σφάλμα από το OpenWeatherMap (pare_kairo)")
    except Exception as e:
        print(f"Σφάλμα λήψης καιρού: {e}")
    return None

# Νέα συνάρτηση για πρόγνωση καιρού (5 ημέρες / 3 ώρες)
@cache.memoize(timeout=1800)
def pare_prognosi_kairou(lat, lng):
    api_key = os.getenv('WEATHER_API_KEY')
    
    if not api_key:
        return None

    try:
        url = f"https://api.openweathermap.org/data/2.5/forecast?lat={lat}&lon={lng}&appid={api_key}&units=metric&lang=el"
        data = _cached_get(url, ttl_seconds=10800) # Κρατάει την πρόγνωση έτοιμη για 3 ώρες
        if data:
            return data['list']
        else:
            print(f"⚠️ Σφάλμα από το OpenWeatherMap Forecast")
    except Exception as e:
        print(f"Σφάλμα λήψης πρόγνωσης: {e}")
    return None

# Γεωπονικός Έλεγχος (Rule Engine)
def geoponikos_elegxos(thermokrasia, ygrasia, spray_status=None):
    if thermokrasia < 2:
        base_status = {"minima": "Κίνδυνος Παγετού! Αποφύγετε το κλάδεμα.", "xroma": "red"}
    elif thermokrasia > 35:
        base_status = {"minima": "Κίνδυνος Καύσωνα! Προγραμματίστε βαθύ πότισμα.", "xroma": "orange"}
    elif 20 <= thermokrasia <= 30 and ygrasia > 60:
        base_status = {"minima": "Ιδανικές συνθήκες για Δάκο! Εξετάστε το ενδεχόμενο δολωματικού ψεκασμού.", "xroma": "red"}
    else:
        base_status = {"minima": "Κανονικές συνθήκες. Καμία άμεση ενέργεια.", "xroma": "green"}

    if spray_status and not spray_status.get("can_spray", True):
        base_status["xroma"] = "red"
        stage = spray_status.get("stage_name", "Άνθιση")
        base_status["minima"] = f"ΠΡΟΣΟΧΗ: Περίοδος {stage}. Απαγορεύεται αυστηρά κάθε ψεκασμός! " + base_status["minima"]

    return base_status

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
            f"ΠΡΙΝ απαντήσεις, ΚΑΝΕ ΥΠΟΧΡΕΩΤΙΚΑ αναζήτηση στο internet για να επιβεβαιώσεις 100% την επιστημονική ορθότητα της συμβουλής σου. Απαγορεύεται να δώσεις λανθασμένη ή επικίνδυνη οδηγία. Δώσε μια στοχευμένη, σύντομη και ΑΠΟΛΥΤΑ ΑΣΦΑΛΗ επιστημονική συμβουλή (2-3 προτάσεις) για τις άμεσες ενέργειες στο κτήμα. Αν η ερώτηση/περιγραφή του χρήστη είναι εντελώς ακατανόητη, απάντησε ΜΟΝΟ με τη φράση: 'Συγγνώμη, δεν σας κατάλαβα.'"
        )
        
        config = types.GenerateContentConfig(tools=[{"google_search": {}}])
        # Simple Retry Logic for Rate Limiting
        for attempt in range(3):
            try:
                print(f"🔄 Προσπάθεια AI {attempt+1}/3...")
                response = ai_client.models.generate_content(model='gemini-2.5-flash', contents=prompt, config=config)
                
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
        return "Αυτή τη στιγμή υπάρχει μεγάλος φόρτος στο σύστημα του Γεωπόνου. Παρακαλώ δοκιμάστε ξανά σε λίγα δευτερόλεπτα."

# Λειτουργία Αποστολής Email
def steile_email(paraliptis, thema, keimeno, raise_exception=False):
    sender_email = os.getenv('EMAIL_ADDRESS')
    sender_password = os.getenv('EMAIL_PASSWORD')
    
    if not sender_email or not sender_password:
        print("⚠️ Λείπουν τα στοιχεία email από το .env")
        if raise_exception:
            raise ValueError("Λείπουν τα στοιχεία EMAIL_ADDRESS ή EMAIL_PASSWORD από τα Environment Variables του server.")
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

@cache.memoize(timeout=1800)
def get_agro_soil_data(poly_id):
    api_key = os.getenv('AGROMONITORING_API_KEY')
    if not api_key or not poly_id: return None
    try:
        return _cached_get(f"http://api.agromonitoring.com/agro/1.0/soil?polyid={poly_id}&appid={api_key}", ttl_seconds=21600) # 6 ώρες cache
    except Exception as e: print(f"Soil Data Error: {e}")
    return None

@cache.memoize(timeout=1800)
def get_agro_uvi(poly_id):
    api_key = os.getenv('AGROMONITORING_API_KEY')
    if not api_key or not poly_id: return None
    try:
        return _cached_get(f"http://api.agromonitoring.com/agro/1.0/uvi?polyid={poly_id}&appid={api_key}", ttl_seconds=7200) # 2 ώρες cache
    except Exception as e: print(f"UVI Error: {e}")
    return None

@cache.memoize(timeout=1800)
def get_agro_ndvi_trend(poly_id):
    api_key = os.getenv('AGROMONITORING_API_KEY')
    if not api_key or not poly_id: return None
    try:
        import time
        end = int(time.time())
        start = end - (60 * 24 * 60 * 60) # Αναζήτηση τελευταίων 60 ημερών
        res = requests.get(f"http://api.agromonitoring.com/agro/1.0/ndvi/history?start={start}&end={end}&polyid={poly_id}&appid={api_key}", timeout=5)
        if res.status_code == 200:
            data = res.json()
            if len(data) > 0:
                data.sort(key=lambda x: x['dt'])
                current_ndvi = data[-1].get('mean')
                dt_ts = data[-1].get('dt')
                
                trend = "stable"
                if len(data) >= 2:
                    previous_ndvi = data[-2].get('mean')
                    if current_ndvi is not None and previous_ndvi is not None:
                        if current_ndvi > previous_ndvi: trend = "up"
                        elif current_ndvi < previous_ndvi: trend = "down"
                
                if current_ndvi is not None:
                    return {'value': current_ndvi, 'trend': trend, 'dt': dt_ts}
    except Exception as e: print(f"Agro NDVI Trend Error: {e}")
    return None

@cache.memoize(timeout=1800)
def get_agro_forecast(poly_id):
    api_key = os.getenv('AGROMONITORING_API_KEY')
    if not api_key or not poly_id: return None
    try:
        return _cached_get(f"http://api.agromonitoring.com/agro/1.0/weather/forecast?polyid={poly_id}&appid={api_key}", ttl_seconds=10800)
    except Exception as e: print(f"Agro Forecast Error: {e}")
    return None

@cache.memoize(timeout=1800)
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

@cache.memoize(timeout=1800)
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

@cache.memoize(timeout=1800)
def pare_istoriko_kairou(lat, lng, past_days=5):
    try:
        # Χρήση του Open-Meteo για δωρεάν δεδομένα παρελθόντος (χωρίς API key)
        url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lng}&daily=precipitation_sum,temperature_2m_max,temperature_2m_min&past_days={past_days}&forecast_days=1&timezone=auto"
        response = requests.get(url, timeout=5)
        if response.status_code == 200:
            data = response.json()
            daily = data.get('daily', {})
            if daily and 'time' in daily:
                history = []
                # Εξαιρούμε τη σημερινή μέρα (κρατάμε μόνο το παρελθόν)
                for i in range(len(daily['time']) - 1):
                    date_str = daily['time'][i]
                    rain = daily.get('precipitation_sum', [])[i]
                    t_max = daily.get('temperature_2m_max', [])[i]
                    t_min = daily.get('temperature_2m_min', [])[i]
                    history.append({
                        'date': date_str,
                        'rain_mm': rain if rain is not None else 0,
                        't_max': t_max if t_max is not None else "-",
                        't_min': t_min if t_min is not None else "-"
                    })
                return history
    except Exception as e:
        print(f"Σφάλμα λήψης ιστορικού καιρού: {e}")
    return None

# --- GDD Thresholds for Spraying Windows per Variety ---
GDD_THRESHOLDS = {
    "Κορωνέικη": {"stop_spray": 550, "start_spray": 850},
    "Καλαμών": {"stop_spray": 680, "start_spray": 950},
    "Χαλκιδικής": {"stop_spray": 620, "start_spray": 920},
    "Μανάκι": {"stop_spray": 600, "start_spray": 900},
    "Αθηνολιά": {"stop_spray": 500, "start_spray": 800},
    "Μεγαρίτικη": {"stop_spray": 600, "start_spray": 900},
    "Χονδρολιά": {"stop_spray": 680, "start_spray": 950},
    "Αρμπεκίνα": {"stop_spray": 550, "start_spray": 850}
}

def evaluate_spraying_window(current_gdd, poikilia):
    """
    Αξιολογεί αν επιτρέπεται ο ψεκασμός βάσει των GDD και της ποικιλίας.
    """
    if current_gdd is None:
        return {"can_spray": True, "reason": "Δεν υπάρχουν επαρκή δεδομένα GDD."}
        
    thresholds = GDD_THRESHOLDS.get(poikilia, {"stop_spray": 600, "start_spray": 900})
    stop_spray = thresholds["stop_spray"]
    start_spray = thresholds["start_spray"]
    
    if stop_spray <= current_gdd < start_spray:
        return {
            "can_spray": False, 
            "reason": f"Βρίσκεστε σε περίοδο άνθισης (GDD: {current_gdd:.1f}). ΑΠΑΓΟΡΕΥΕΤΑΙ ο ψεκασμός για την ποικιλία {poikilia}."
        }
    elif current_gdd >= start_spray:
        return {
            "can_spray": True, 
            "reason": f"Έχει ολοκληρωθεί η καρπόδεση (GDD: {current_gdd:.1f}). Επιτρέπονται οι ψεκασμοί για την ποικιλία {poikilia}."
        }
    else:
        return {
            "can_spray": True, 
            "reason": f"Βρίσκεστε πριν την άνθιση (GDD: {current_gdd:.1f}). Επιτρέπονται οι προληπτικοί ψεκασμοί για την ποικιλία {poikilia}."
        }

OLIVE_GDD_THRESHOLDS = {
    'Αθηνοελιά': {'stop_spray': 430, 'start_spray': 830},
    'Κορωνέικη': {'stop_spray': 480, 'start_spray': 880},
    'Καλαμών': {'stop_spray': 530, 'start_spray': 930}
}

def check_spraying_status(current_gdd, poikilia):
    if current_gdd is None:
        return {"can_spray": True, "reason": "Δεν υπάρχουν επαρκή δεδομένα GDD.", "stage_name": "Άγνωστο"}
        
    varieties = [v.strip() for v in poikilia.split(',')] if poikilia else ['Κορωνέικη']
    valid_varieties = [v for v in varieties if v in OLIVE_GDD_THRESHOLDS]
    
    if not valid_varieties:
        valid_varieties = ['Κορωνέικη']
        
    avg_stop = sum(OLIVE_GDD_THRESHOLDS[v]['stop_spray'] for v in valid_varieties) / len(valid_varieties)
    avg_start = sum(OLIVE_GDD_THRESHOLDS[v]['start_spray'] for v in valid_varieties) / len(valid_varieties)
    
    if current_gdd < avg_stop - 50:
        stage_name = "Βλαστική Ανάπτυξη"
    elif avg_stop - 50 <= current_gdd <= avg_stop:
        stage_name = "Κρόκιασμα (Προ-Άνθιση)"
    elif avg_stop < current_gdd < avg_start:
        stage_name = "Άνθιση"
    else:
        stage_name = "Καρπόδεση"

    if current_gdd < avg_stop:
        can_spray, reason = True, "Βρίσκεστε πριν την άνθιση. Επιτρέπονται οι ψεκασμοί."
    elif avg_stop <= current_gdd < avg_start:
        can_spray, reason = False, "Περίοδος άνθισης. Απαγορεύονται οι ψεκασμοί."
    else:
        can_spray, reason = True, "Ολοκληρώθηκε η καρπόδεση. Επιτρέπονται οι ψεκασμοί."
        
    if len(valid_varieties) > 1:
        reason += " Προσοχή: Εντοπίστηκαν πολλαπλές ποικιλίες στο κτήμα. Τα όρια ψεκασμού υπολογίστηκαν με βάση τον μέσο όρο τους για την προστασία όλων των δέντρων."
        
    return {"can_spray": can_spray, "reason": reason, "stage_name": stage_name}