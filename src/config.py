import os
from dotenv import load_dotenv

# Load the .env file
load_dotenv("config/.env")

# Retrieve config variables from environment
SERVICE_ACCOUNT_FILE = os.getenv("GOOGLE_CREDENTIALS_FILE")
SHEET_ID = os.getenv("GOOGLE_SHEET_ID")
SHEET_URL = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/edit"
SHEET_NAME = os.getenv("GOOGLE_SHEET_NAME", "Sheet1")

# OpenRouter stuff
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
MODEL = os.getenv("MODEL", "openai/gpt-4o-mini") # gpt-4o-mini
