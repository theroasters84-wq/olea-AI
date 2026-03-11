import os
from core import efarmogi
import routes  # This registers all the routes with the app
from apscheduler.schedulers.background import BackgroundScheduler
from logic import aytomatizomenos_elegxos

# Start Scheduler for Gunicorn (Production)
if not efarmogi.debug or os.environ.get("WERKZEUG_RUN_MAIN") == "true":
    scheduler = BackgroundScheduler()
    scheduler.add_job(func=aytomatizomenos_elegxos, trigger="cron", hour=8, minute=0)
    scheduler.start()
    print("Scheduler has been started for daily forecast checks at 08:00.")

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    efarmogi.run(host='0.0.0.0', port=port, debug=True)