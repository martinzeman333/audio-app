import os
import openai
import azure.cognitiveservices.speech as speechsdk
from flask import Flask, render_template, request, jsonify
from dotenv import load_dotenv
import logging

# Nastavení logování, aby se chyby zobrazovaly v konzoli (a v logu na Renderu)
logging.basicConfig(level=logging.INFO)

load_dotenv()
openai.api_key = os.getenv("OPENAI_API_KEY")

app = Flask(__name__)

def transcribe_audio_azure(audio_filename):
    # Přidán blok try-except pro odchycení chyb přímo v Azure funkci
    try:
        speech_config = speechsdk.SpeechConfig(
            subscription=os.getenv("AZURE_SPEECH_KEY"), 
            region=os.getenv("AZURE_SPEECH_REGION")
        )
        speech_config.speech_recognition_language = "cs-CZ"
        audio_config = speechsdk.audio.AudioConfig(filename=audio_filename)
        recognizer = speechsdk.SpeechRecognizer(speech_config=speech_config, audio_config=audio_config)
        
        result = recognizer.recognize_once_async().get()
        
        if result.reason == speechsdk.ResultReason.RecognizedSpeech:
            logging.info("Azure: Řeč úspěšně rozpoznána.")
            return result.text
        elif result.reason == speechsdk.ResultReason.NoMatch:
            logging.warning("Azure: Řeč nebyla rozpoznána.")
            return "" # Vracíme prázdný string místo chybové hlášky
        else:
            cancellation_details = result.cancellation_details
            logging.error(f"Azure: Přepis zrušen: {cancellation_details.reason}")
            logging.error(f"Azure: Detail chyby: {cancellation_details.error_details}")
            raise Exception(f"Azure chyba: {cancellation_details.reason}")
    except Exception as e:
        logging.error(f"Výjimka v transcribe_audio_azure: {e}")
        # Propagujeme výjimku dále, aby ji hlavní funkce mohla chytit
        raise

def call_gpt(prompt):
    # Přidán blok try-except a použití nejnovějšího modelu gpt-4o-mini
    try:
        # Používáme nový, rychlý a levný model gpt-4o-mini
        response = openai.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "Jsi expert na stylistiku a gramatiku českého jazyka. Tvé odpovědi jsou stručné a přímo k věci."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.5
        )
        return response.choices[0].message.content
    except Exception as e:
        logging.error(f"Výjimka v call_gpt: {e}")
        # Propagujeme výjimku, aby ji hlavní funkce mohla chytit
        raise

@app.route('/process-audio', methods=['POST'])
def process_audio():
    if 'audio_file' not in request.files:
        return jsonify({"error": "Chybí audio soubor"}), 400

    audio_file = request.files['audio_file']
    filepath = "temp_recording.wav"
    audio_file.save(filepath)

    try:
        # 1. Přepis pomocí Azure
        logging.info("Spouštím přepis v Azure...")
        original_text = transcribe_audio_azure(filepath)
        
        # Pokud Azure nic nerozeznal, nemá smysl pokračovat k OpenAI
        if not original_text:
            logging.info("Původní text je prázdný, vracím prázdné výsledky.")
            return jsonify({
                "original_text": "Nebylo nic rozpoznáno.",
                "edited_text": ""
            })

        # 2. Vylepšení textu pomocí ChatGPT
        logging.info(f"Text z Azure: '{original_text}'. Spouštím vylepšení v OpenAI...")
        cleanup_prompt = f"Oprav interpunkci, gramatiku a odstraň slovní vatu (jako 'ehm', 'hmm', 'jako') z následujícího textu, ale zachovej jeho význam: '{original_text}'"
        edited_text = call_gpt(cleanup_prompt)
        logging.info("OpenAI dokončilo vylepšení.")
        
        return jsonify({
            "original_text": original_text,
            "edited_text": edited_text
        })

    except Exception as e:
        # Toto je hlavní záchranný blok. Pokud cokoliv selže, vrátíme srozumitelnou chybu.
        logging.error(f"Došlo k chybě při zpracování audia: {e}")
        return jsonify({"error": f"Nastala chyba na serveru: {e}"}), 500
    finally:
        # Zajistíme, že se dočasný soubor vždy smaže
        if os.path.exists(filepath):
            os.remove(filepath)

# Ostatní routy (manipulate-text, share, index) zůstávají beze změny...
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/manipulate-text', methods=['POST'])
def manipulate_text():
    data = request.json
    text = data.get('text')
    action = data.get('action')
    style = data.get('style', '')
    prompts = {
        "summarize": f"Vytvoř stručné shrnutí tohoto textu: '{text}'",
        "restyle": f"Přepiš tento text do {style} stylu: '{text}'",
        "expand": f"Rozšiř následující myšlenky a přidej relevantní detaily: '{text}'"
    }
    prompt = prompts.get(action)
    if not prompt: return jsonify({"error": "Neznámá akce"}), 400
    result_text = call_gpt(prompt)
    return jsonify({"text": result_text})

@app.route('/share', methods=['POST'])
def share():
    data = request.json
    text = data.get('text')
    recipient = data.get('recipient')
    method = data.get('method')
    print(f"POŽADAVEK NA SDÍLENÍ: Metoda='{method}', Příjemce='{recipient}', Text='{text[:50]}...'")
    return jsonify({"message": f"Text byl úspěšně 'odeslán' na {recipient}."})
