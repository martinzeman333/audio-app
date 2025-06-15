import os
import openai
import azure.cognitiveservices.speech as speechsdk
from flask import Flask, render_template, request, jsonify
from dotenv import load_dotenv
import logging
import subprocess # Knihovna pro spouštění externích příkazů, jako je ffmpeg
import shutil # Knihovna pro zjištění, zda ffmpeg existuje

# Nastavení logování
logging.basicConfig(level=logging.INFO)

# Kontrola, zda je ffmpeg dostupné hned při startu
if not shutil.which("ffmpeg"):
    logging.error("KRITICKÁ CHYBA: ffmpeg není nainstalován nebo není v systémové cestě (PATH).")
    # V prostředí Renderu by toto nemělo nastat, ale je to dobrá pojistka.

load_dotenv()
openai.api_key = os.getenv("OPENAI_API_KEY")

app = Flask(__name__)

# --- Nová funkce pro konverzi audia ---
def convert_audio_with_ffmpeg(input_path, output_path):
    """
    Převede audio soubor na standardní WAV formát (16kHz, mono, 16-bit PCM) pomocí ffmpeg.
    """
    logging.info(f"Spouštím konverzi souboru '{input_path}' na '{output_path}' pomocí ffmpeg.")
    try:
        # Příkaz pro ffmpeg
        command = [
            "ffmpeg",
            "-i", input_path,      # Vstupní soubor
            "-acodec", "pcm_s16le",# Kodek: standardní 16-bit PCM
            "-ac", "1",            # Počet kanálů: 1 (mono)
            "-ar", "16000",        # Vzorkovací frekvence: 16kHz (ideální pro speech-to-text)
            "-y",                  # Přepsat výstupní soubor, pokud existuje
            output_path
        ]
        
        # Spuštění příkazu
        result = subprocess.run(command, check=True, capture_output=True, text=True)
        logging.info("FFmpeg konverze úspěšná.")
        logging.debug(f"FFmpeg výstup: {result.stdout}")
        
    except subprocess.CalledProcessError as e:
        # Pokud ffmpeg selže, zalogujeme chybu
        logging.error(f"FFmpeg selhal s chybou: {e.stderr}")
        raise RuntimeError(f"Chyba při konverzi audia: {e.stderr}")
    except FileNotFoundError:
        logging.error("Chyba: Příkaz 'ffmpeg' nebyl nalezen.")
        raise RuntimeError("Nástroj ffmpeg není dostupný na serveru.")

# --- Upravená hlavní route ---
@app.route('/process-audio', methods=['POST'])
def process_audio():
    if 'audio_file' not in request.files:
        return jsonify({"error": "Chybí audio soubor"}), 400

    audio_file = request.files['audio_file']
    original_filepath = "temp_recording.original"
    converted_filepath = "temp_recording_converted.wav"
    audio_file.save(original_filepath)

    try:
        # 1. Konverze audia pomocí FFmpeg
        convert_audio_with_ffmpeg(original_filepath, converted_filepath)

        # 2. Přepis pomocí Azure s novým, zkonvertovaným souborem
        logging.info("Spouštím přepis v Azure...")
        original_text = transcribe_audio_azure(converted_filepath)
        
        # ... zbytek funkce zůstává stejný ...
        if not original_text:
            logging.info("Původní text je prázdný, vracím prázdné výsledky.")
            return jsonify({"original_text": "Nebylo nic rozpoznáno.", "edited_text": ""})

        logging.info(f"Text z Azure: '{original_text}'. Spouštím vylepšení v OpenAI...")
        cleanup_prompt = f"Oprav interpunkci, gramatiku a odstraň slovní vatu (jako 'ehm', 'hmm', 'jako') z následujícího textu, ale zachovej jeho význam: '{original_text}'"
        edited_text = call_gpt(cleanup_prompt)
        logging.info("OpenAI dokončilo vylepšení.")
        
        return jsonify({"original_text": original_text, "edited_text": edited_text})

    except Exception as e:
        logging.error(f"Došlo k chybě při zpracování audia: {e}")
        return jsonify({"error": f"Nastala chyba na serveru: {e}"}), 500
    finally:
        if os.path.exists(original_filepath):
            os.remove(original_filepath)
        if os.path.exists(converted_filepath):
            os.remove(converted_filepath)

# --- Zbytek souboru app.py (funkce pro Azure, OpenAI, další routy) zůstává stejný ---
def transcribe_audio_azure(audio_filename):
    try:
        speech_config = speechsdk.SpeechConfig(subscription=os.getenv("AZURE_SPEECH_KEY"), region=os.getenv("AZURE_SPEECH_REGION"))
        speech_config.speech_recognition_language = "cs-CZ"
        audio_config = speechsdk.audio.AudioConfig(filename=audio_filename)
        recognizer = speechsdk.SpeechRecognizer(speech_config=speech_config, audio_config=audio_config)
        result = recognizer.recognize_once_async().get()
        if result.reason == speechsdk.ResultReason.RecognizedSpeech: return result.text
        elif result.reason == speechsdk.ResultReason.NoMatch: return ""
        else:
            cancellation_details = result.cancellation_details
            logging.error(f"Azure chyba: {cancellation_details.reason} - {cancellation_details.error_details}")
            raise Exception(f"Azure chyba: {cancellation_details.reason}")
    except Exception as e:
        logging.error(f"Výjimka v transcribe_audio_azure: {e}")
        raise

def call_gpt(prompt):
    try:
        response = openai.chat.completions.create(model="gpt-4o-mini", messages=[{"role": "system", "content": "Jsi expert na stylistiku a gramatiku českého jazyka. Tvé odpovědi jsou stručné a přímo k věci."}, {"role": "user", "content": prompt}], temperature=0.5)
        return response.choices[0].message.content
    except Exception as e:
        logging.error(f"Výjimka v call_gpt: {e}")
        raise

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/manipulate-text', methods=['POST'])
def manipulate_text():
    data = request.json
    text, action, style = data.get('text'), data.get('action'), data.get('style', '')
    prompts = {"summarize": f"Vytvoř stručné shrnutí tohoto textu: '{text}'", "restyle": f"Přepiš tento text do {style} stylu: '{text}'", "expand": f"Rozšiř následující myšlenky a přidej relevantní detaily: '{text}'"}
    prompt = prompts.get(action)
    if not prompt: return jsonify({"error": "Neznámá akce"}), 400
    return jsonify({"text": call_gpt(prompt)})
