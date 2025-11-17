# check_models_v2.py
import os
import json
import urllib.request
import dotenv

# Load your API Key
dotenv.load_dotenv()
api_key = os.getenv("GOOGLE_API_KEY")

if not api_key:
    print("❌ Error: GOOGLE_API_KEY not found in .env")
else:
    print(f"🔑 Checking models with Key: {api_key[:5]}... (Safe connection)")

    # Direct API Call to Google (Bypassing Python SDK conflicts)
    url = f"https://generativelanguage.googleapis.com/v1beta/models?key={api_key}"

    try:
        with urllib.request.urlopen(url) as response:
            if response.status == 200:
                data = json.loads(response.read().decode())
                print("\n✅ AVAILABLE MODELS:")
                print("-" * 30)
                found_any = False
                for model in data.get('models', []):
                    # Only show models that can generate text
                    if 'generateContent' in model.get('supportedGenerationMethods', []):
                        name = model['name'].replace('models/', '')
                        print(f"• {name}")
                        found_any = True

                if not found_any:
                    print("⚠️ No text-generation models found. Check your API Key permissions.")
            else:
                print(f"⚠️ HTTP Error: {response.status}")

    except Exception as e:
        print(f"\n❌ Connection Error: {e}")
        print("Tip: If this fails, you might need to enable the 'Generative Language API' in Google Cloud Console.")