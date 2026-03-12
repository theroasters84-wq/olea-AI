# Render.com Deployment Guide for Olea AI

Follow these steps to deploy the application on Render's Free Tier.

## 1. Create a Web Service
- Connect your repository to Render.
- Select **Python 3** as the environment.

## 2. Configuration
Use the following settings during creation:
 
- **Build Command:** `pip install -r requirements.txt && flask db upgrade`
- **Start Command:** `gunicorn -b 0.0.0.0:$PORT efarmogi:efarmogi`
 
> **Note:** The `flask db upgrade` command uses the Flask-Migrate library (which is already installed) to apply database updates safely. This is more robust than running a custom script. The `gunicorn` command uses the `$PORT` environment variable provided by Render, which is crucial for the service to be accessible online.

## 3. Environment Variables
Go to the **Environment** tab and add the following keys:

- `FLASK_SECRET_KEY`: (Generate a random secure string)
- `DATABASE_URL`: (Copy the "Internal Database URL" from your Render PostgreSQL database)
- `AI_API_KEY`: (Your Gemini AI API Key)
- `WEATHER_API_KEY`: (Your OpenWeatherMap API Key)
- `EMAIL_ADDRESS`: (Gmail address for sending notifications)
- `EMAIL_PASSWORD`: (Gmail App Password)