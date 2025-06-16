import os
import openai
import azure.cognitiveservices.speech as speechsdk
from flask import Flask, render_template, request, jsonify
from dotenv import load_dotenv
import logging
import subprocess
import shutil
import time
import uuid
import threading

# --- Základní nastavení ---
logging.basicConfig(level=logging.INFO)
load_dotenv()

# --- Kontrola a inicializace ---
if not shutil.which("ffmpeg"):
    logging.error("KRITICKÁ CHYBA: ffmpeg není nainstalován.")
openai.api_key = os.getenv("OPENAI_API_KEY")
app = Flask(__name__)

# --- Jednoduché in-memory úložiště pro stav úloh ---
jobs = {}

# --- Pomocné funkce ---

def transcribe_audio_azure(audio_filename):
    """
    Přepíše DLOUHÝ audio soubor pomocí Azure Speech SDK v kontinuálním režimu.
    Toto je robustní metoda pro zpracování nahrávek delších než 60 sekund.
    """
    logging.info(f"Spouštím KONTINUÁLNÍ přepis souboru: {audio_filename}")
    speech_config = speechsdk.SpeechConfig(subscription=os.getenv("AZURE_SPEECH_KEY"), region=os.getenv("AZURE_SPEECH_REGION"))
    speech_config.speech_recognition_language = "cs-CZ"
    audio_config = speechsdk.audio.AudioConfig(filename=audio_filename)
    
    speech_recognizer = speechsdk.SpeechRecognizer(speech_config=speech_config, audio_config=audio_config)
    
    done = threading.Event()
    all_results = []

    def recognized_cb(evt):
        # Tato funkce se zavolá pokaždé, když je úspěšně rozpoznána část řeči
        if evt.result.reason == speechsdk.ResultReason.RecognizedSpeech:
            logging.info(f"ROZPOZNÁNO: {evt.result.text}")
            all_results.append(evt.result.text)

    def stop_cb(evt):
        # Tato funkce se zavolá, jakmile je celý soubor zpracován
        logging.info(f'UKONČUJI SEZENÍ: {evt}')
        done.set() # Signalizuje hlavnímu vláknu, že je hotovo

    # Připojení našich funkcí k událostem z Azure SDK
    speech_recognizer.recognized.connect(recognized_cb)
    speech_recognizer.session_started.connect(lambda evt: logging.info(f'SEZENÍ SPUŠTĚNO: {evt}'))
    speech_recognizer.session_stopped.connect(stop_cb)
    speech_recognizer.canceled.connect(stop_cb)

    # Spuštění kontinuálního rozpoznávání. Bude běžet, dokud neskončí audio soubor.
    speech_recognizer.start_continuous_recognition()
    
    # Bezpečné čekání na dokončení s časovým limitem (např. 15 minut)
    finished_in_time = done.wait(timeout=900.0) 
    if not finished_in_time:
        logging.error("Přepis překročil časový limit 15 minut.")

    speech_recognizer.stop_continuous_recognition()
    
    final_text = " ".join(all_results)
    
    if not final_text:
        return "Řeč nebyla rozpoznána."
        
    return final_text

def convert_audio_with_ffmpeg(input_path, output_path):
    try:
        command = ["ffmpeg", "-i", input_path, "-acodec", "pcm_s16le", "-ac", "1", "-ar", "16000", "-y", output_path]
        subprocess.run(command, check=True, capture_output=True, text=True)
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"Chyba při konverzi audia: {e.stderr}")

def call_gpt(prompt, temperature=0.5):
    try:
        response = openai.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "system", "content": "Jsi expert na stylistiku a gramatiku."}, {"role": "user", "content": prompt}],
            temperature=temperature
        )
        return response.choices[0].message.content
    except Exception as e:
        raise RuntimeError(f"Chyba při volání OpenAI: {e}")

def process_audio_in_background(job_id, original_filepath):
    converted_filepath = f"temp_{job_id}_converted.wav"
    try:
        jobs[job_id]['message'] = 'Konvertuji audio...'
        convert_audio_with_ffmpeg(original_filepath, converted_filepath)

        jobs[job_id]['message'] = 'Přepisuji řeč na text...'
        original_text = transcribe_audio_azure(converted_filepath)
        if not original_text or original_text == "Řeč nebyla rozpoznána.":
            raise ValueError("Nepodařilo se rozpoznat žádnou řeč.")

        jobs[job_id]['message'] = 'Vylepšuji text pomocí AI...'
        cleanup_prompt = f"Proveď pouze základní korekturu následujícího textu. Odstraň slovní vatu a doplň interpunkci. Zachovej původní slova a formulaci vět. Výsledný text neobaluj do vnějších uvozovek. Text k úpravě: '{original_text}'"
        edited_text = call_gpt(cleanup_prompt, temperature=0.2)

        jobs[job_id]['message'] = 'Generuji název...'
        title_prompt = f"Vytvoř velmi krátký a výstižný název (maximálně 5 slov) pro tento text. Odpověz POUZE samotným názvem, bez uvozovek. Text: '{edited_text[:500]}'"
        title = call_gpt(title_prompt, temperature=0.7).strip().replace('"', '')

        jobs[job_id].update({
            'status': 'completed',
            'result': {
                "id": int(time.time() * 1000),
                "title": title,
                "edited_text": edited_text
            }
        })

    except Exception as e:
        logging.error(f"Chyba v úloze na pozadí (job {job_id}): {e}")
        jobs[job_id].update({'status': 'failed', 'error': str(e)})
    finally:
        if os.path.exists(original_filepath): os.remove(original_filepath)
        if os.path.exists(converted_filepath): os.remove(converted_filepath)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/upload-audio', methods=['POST'])
def upload_audio():
    if 'audio_file' not in request.files:
        return jsonify({"error": "Chybí audio soubor"}), 400

    audio_file = request.files['audio_file']
    job_id = str(uuid.uuid4())
    filepath = f"temp_{job_id}.original"
    audio_file.save(filepath)

    if os.path.getsize(filepath) < 2048:
        return jsonify({"error": "Nahrávka byla příliš krátká."}), 400

    jobs[job_id] = {'status': 'queued', 'message': 'Úloha zařazena...'}
    
    thread = threading.Thread(target=process_audio_in_background, args=(job_id, filepath))
    thread.start()
    
    return jsonify({"job_id": job_id})

@app.route('/status/<job_id>')
def get_status(job_id):
    job = jobs.get(job_id, {})
    return jsonify(job)

@app.route('/manipulate-text', methods=['POST'])
def manipulate_text():
    data = request.json
    text, action = data.get('text'), data.get('action')
    style = data.get('style', 'profesionálním')
    
    prompts = {
        "summarize": f"Vytvoř stručné shrnutí: '{text}'",
        "restyle": f"Přepiš text do {style} stylu: '{text}'",
        "expand": f"Rozšiř myšlenky: '{text}'",
        "translate_en": f"Přelož do angličtiny: '{text}'",
        "twitter_post": f"Přeformuluj jako příspěvek na Twitter (max 280 znaků, s hashtagy): '{text}'"
    }
    prompt = prompts.get(action)
    if not prompt: return jsonify({"error": "Neznámá akce"}), 400
    
    return jsonify({"text": call_gpt(prompt, temperature=0.7)})

if __name__ == '__main__':
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
