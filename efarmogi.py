import os
from core import efarmogi, vasi
import core_app # Loads routes and blueprints
from apscheduler.schedulers.background import BackgroundScheduler
from logic import aytomatizomenos_elegxos
from models import Ktima, Diagnosi, Ergasia

def aytomatizomenos_elegxos_ndvi(app_context):
    """Background task that runs weekly to check all registered polygons."""
    with app_context():
        import os
        import requests
        import io
        import PIL.Image
        from datetime import datetime
        from google import genai
        
        api_key = os.getenv('AGROMONITORING_API_KEY')
        ai_key = os.getenv('AI_API_KEY')
        if not api_key or not ai_key: return
        from sqlalchemy import or_

        ktimata = Ktima.query.filter(Ktima.agromonitoring_poly_id.isnot(None)).all()
        client = genai.Client(api_key=ai_key)

        for ktima in ktimata:
            try:
                end_time = int(datetime.now().timestamp()) - 60 # Αφαιρούμε 60 δευτερόλεπτα για να αποφύγουμε σφάλματα συγχρονισμού
                start_time = end_time - (14 * 24 * 60 * 60) # Look back 14 days
                img_url = f"http://api.agromonitoring.com/agro/1.0/image/search?start={start_time}&end={end_time}&polyid={ktima.agromonitoring_poly_id}&appid={api_key}"
                img_res = requests.get(img_url)

                if img_res.status_code == 200 and len(img_res.json()) > 0:
                    latest_img = img_res.json()[-1]
                    ndvi_url = latest_img.get('image', {}).get('ndvi')
                    
                    if ndvi_url:
                        img_response = requests.get(ndvi_url)
                        if img_response.status_code == 200:
                            image_file = PIL.Image.open(io.BytesIO(img_response.content))
                            
                            recent_weeds = ""
                            for d in reversed(ktima.diagnoseis):
                                if "χόρτ" in (d.apotelesma or "").lower() or "ζιζάν" in (d.apotelesma or "").lower() or "έδαφος" in (d.apotelesma or "").lower():
                                    days_ago = (datetime.now() - d.imerominia).days
                                    if days_ago <= 15:
                                        recent_weeds = f"ΓΝΩΣΗ ΑΠΟ ΠΡΟΣΦΑΤΗ ΦΩΤΟΓΡΑΦΙΑ ΕΔΑΦΟΥΣ ({days_ago} ημ. πριν): '{d.apotelesma}'. "
                                    break

                            prompt = (
                                f"Είσαι γεωπόνος. Αυτός είναι ο εβδομαδιαίος δορυφορικός χάρτης NDVI. Κτήμα: Ηλικία={ktima.ilikia_dentron}, Πυκνότητα={ktima.puknotita_dentron}, Έδαφος={ktima.diacheirisi_edafous}. {recent_weeds}"
                                f"ΟΔΗΓΙΕΣ: 1) Αν δεις έντονη πτώση βλάστησης (ξερό χώμα) ρώτα αν έγινε κλάδεμα ή καθαρισμός χόρτων, αλλιώς ζήτα 'Ευρεία Φωτογραφία' εδάφους. "
                                f"2) Αν ο χάρτης είναι ομοιόμορφα σκούρος πράσινος, ρώτα τον αγρότη αν έχουν ψηλώσει τα χόρτα (ή ζήτα 'Ευρεία Φωτογραφία' εδάφους) ΚΑΙ πρόσθεσε ΟΠΩΣΔΗΠΟΤΕ στο τέλος τη λέξη '[ΧΟΡΤΑ_ΥΨΗΛΑ]'. "
                                f"3) Σε κάθε απορία ΞΕΚΙΝΑ την απάντησή σου με 'ΕΡΩΤΗΣΗ:'. 4) Αν όλα είναι φυσιολογικά ΞΕΚΙΝΑ με 'ΕΝΗΜΕΡΩΣΗ:' και δώσε αναφορά."
                            )
                            
                            response = client.models.generate_content(model='gemini-2.5-flash', contents=[prompt, image_file])
                            ai_text = response.text.strip()

                            # Έλεγχος AI Tagging
                            if '[ΧΟΡΤΑ_ΥΨΗΛΑ]' in ai_text:
                                ai_text = ai_text.replace('[ΧΟΡΤΑ_ΥΨΗΛΑ]', '').strip()
                                
                                yparxei_kophi = Ergasia.query.filter_by(ktima_id=ktima.id, katastasi='Εκκρεμεί').filter(
                                    or_(Ergasia.eidos_ergasias.ilike('%Χόρτ%'), Ergasia.eidos_ergasias.ilike('%Ζιζάν%'), Ergasia.eidos_ergasias.ilike('%Καταστροφ%'))
                                ).first()
                                recent_kophi = Ergasia.query.filter_by(ktima_id=ktima.id, katastasi='Ολοκληρώθηκε').filter(
                                    or_(Ergasia.eidos_ergasias.ilike('%Χόρτ%'), Ergasia.eidos_ergasias.ilike('%Ζιζάν%'), Ergasia.eidos_ergasias.ilike('%Καταστροφ%'))
                                ).order_by(Ergasia.imerominia.desc()).first()
                                days_since = (datetime.now() - recent_kophi.imerominia).days if recent_kophi else 999
                                
                                if not yparxei_kophi and days_since > 15:
                                    vasi.session.add(Ergasia(ktima_id=ktima.id, eidos_ergasias='Κοπή Χόρτων / Καταστροφέας', katastasi='Εκκρεμεί', proelevsi='AI Δορυφόρος', imerominia=datetime.now()))

                            if ai_text.startswith("ΕΡΩΤΗΣΗ:"):
                                ktima.ekkremis_erotisi_ai = ai_text.replace("ΕΡΩΤΗΣΗ:", "").strip()
                                vasi.session.commit()
                            elif ai_text.startswith("ΕΝΗΜΕΡΩΣΗ:"):
                                msg = ai_text.replace("ΕΝΗΜΕΡΩΣΗ:", "").strip()
                                nea_diagnosi = Diagnosi(ktima_id=ktima.id, apotelesma=f"🛰️ Εβδομαδιαίος Έλεγχος: {msg}", imerominia=datetime.now())
                                ktima.ekkremis_erotisi_ai = None
                                vasi.session.add(nea_diagnosi)
                                vasi.session.commit()
            except Exception as e:
                print(f"Background NDVI Error for Ktima {ktima.id}: {e}")

# Start Scheduler for Gunicorn (Production)
if (not efarmogi.debug or os.environ.get("WERKZEUG_RUN_MAIN") == "true") and not os.environ.get("SKIP_SCHEDULER"):
    scheduler = BackgroundScheduler()
    scheduler.add_job(func=aytomatizomenos_elegxos, trigger="cron", hour=8, minute=0)
    # Προσθήκη εβδομαδιαίου ελέγχου Δορυφόρου
    scheduler.add_job(func=aytomatizomenos_elegxos_ndvi, trigger='cron', day_of_week='sun', hour=9, minute=0, args=[efarmogi.app_context])
    scheduler.start()
    print("Scheduler has been started for daily forecast checks at 08:00.")

if __name__ == '__main__':
    # Αν τρέξει αυτό το αρχείο κατά λάθος, εκκινούμε τον server όπως στο run.py
    from update_db import update_db
    update_db()
    port = int(os.environ.get("PORT", 5000))
    efarmogi.run(host='0.0.0.0', port=port, debug=True)