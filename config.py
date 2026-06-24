import os
import sys
import google.generativeai as genai

# Try to load API key from Kaggle secrets, fallback to local .env
try:
    from kaggle_secrets import UserSecretsClient
    API_KEY = UserSecretsClient().get_secret("GEMINI_API_KEY")
except Exception:
    from dotenv import load_dotenv
    load_dotenv()
    API_KEY = os.getenv("GEMINI_API_KEY")

if API_KEY:
    API_KEY = API_KEY.strip()

# Validate we have a key
if not API_KEY or "your_actual_api_key" in API_KEY:
    print("\n[bold red]Error: GEMINI_API_KEY not configured![/bold red]")
    print("Please configure GEMINI_API_KEY either in your Kaggle Secrets or in the local .env file.")
    print("You can get a free key from Google AI Studio at: https://aistudio.google.com/\n")
    sys.exit(1)

def configure_sdk():
    try:
        genai.configure(api_key=API_KEY)
    except Exception as e:
        print(f"Failed to configure Gemini SDK: {e}")

# Initialize the SDK with the key
configure_sdk()

# Standard models to use for the agents in the legacy/standard SDK.
# gemini-1.5-flash is stable, free, and fast.
MODEL_NAME = "gemini-flash-lite-latest"
# For complex evaluation, gemini-1.5-pro can be used if desired, but we default to flash.
