# Render.com Deployment Guide for Olea AI

Follow these steps to deploy the application on Render's Free Tier.

## 1. Create a Web Service
- Connect your repository to Render.
- Select **Python 3** as the environment.

## 2. Configuration
Use the following settings during creation:
 
- **Build Command:** `pip install -r requirements.txt`
- **Start Command:** `python update_db.py && gunicorn -w 1 -b 0.0.0.0:$PORT efarmogi:efarmogi`
 
> **Note:** We use `python update_db.py` to safely update the database schema (add columns) before the server starts. The `gunicorn` command uses the `$PORT` environment variable provided by Render to make the service accessible online.

## 3. Environment Variables
Go to the **Environment** tab and add the following keys:

- `FLASK_SECRET_KEY`: (Generate a random secure string)
- `DATABASE_URL`: (Copy the "Internal Database URL" from your Render PostgreSQL database)
- `AI_API_KEY`: (Your Gemini AI API Key)
- `WEATHER_API_KEY`: (Your OpenWeatherMap API Key)
- `EMAIL_ADDRESS`: (Gmail address for sending notifications)
- `EMAIL_PASSWORD`: (Gmail App Password)