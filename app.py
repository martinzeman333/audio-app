import os
import openai
import azure.cognitiveservices.speech as speechsdk
from flask import Flask, render_template, request, jsonify
from dotenv import load_dotenv
import logging
import subprocess
import shutil

logging.basicConfig(level=logging.INFO)

if not shutil.which("ffmpeg"):
    logging.error("KRITICKÁ CHYBA: ffmpeg není nainstalován nebo není v systémové cestě (PATH).")

load_dotenv()
openai.api_key = os.getenv("OPENAI_API_KEY")

# ====================================================================
# TENTO ŘÁDEK S NEJVĚTŠÍ PRAVDĚPODOBNOSTÍ CHYBĚL NEBO BYL SMAZÁN
app = Flask(__name__)
# ====================================================================


def convert_audio_with_ffmpeg(input_path, output_path):
    logging.info(f"Spouštím konverzi souboru '{input_path}' na '{output_path}' pomocí ffmpeg.")
    try:
        command = ["ffmpeg", "-i", input_path, "-acodec", "pcm_s16le", "-ac", "1", "-ar", "16000", "-y", output_path]
        result = subprocess.run(command, check=True, capture_output=True, text=True)
        logging.info("FFmpeg konverze úspěšná.")
    except subprocess.CalledProcessError as e:
        logging.error(f"FFmpeg selhal s chybou: {e.stderr}")
        raise RuntimeError(f"Chyba při konverzi audia: {e.stderr}")
    except FileNotFoundError:
        logging.error("Chyba: Příkaz 'ffmpeg' nebyl nalezen.")
        raise RuntimeError("Nástroj ffmpeg není dostupný na serveru.")

def transcribe_audio_azure(audio_filename):
    logging.info(f"Spouštím kontinuální přepis souboru: {audio_filename}")
    speech_config = speechsdk.SpeechConfig(subscription=os.getenv("AZURE_SPEECH_KEY"), region=os.getenv("AZURE_SPEECH_REGION"))
    speech_config.speech_recognition_language = "cs-CZ"
    audio_config = speechsdk.audio.AudioConfig(filename=audio_filename)
    speech_recognizer = speechsdk.SpeechRecognizer(speech_config=speech_config, audio_config=audio_config)
    
    all_results = []
    def handle_recognized(evt):
        all_results.append(evt.result.text)
        logging.info(f'ROZPOZNÁNO: {evt.result.text}')

    speech_recognizer.recognized.connect(handle_recognized)

    done = False
    def stop_cb(evt):
        logging.info('KONEC SEZENÍ: {}'.format(evt))
        nonlocal done
        done = True

    speech_recognizer.session_stopped.connect(stop_cb)
    speech_recognizer.canceled.connect(stop_cb)
    speech_recognizer.start_continuous_recognition()
    
    while not done:
        pass

    speech_recognizer.stop_continuous_recognition()
    final_text = " ".join(all_results)
    logging.info(f"Finální přepsaný text: {final_text}")
    return final_text

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

@app.route('/process-audio', methods=['POST'])
def process_audio():
    if 'audio_file' not in request.files:
        return jsonify({"error": "Chybí audio soubor"}), 400

    audio_file = request.files['audio_file']
    original_filepath = "temp_recording.original"
    converted_filepath = "temp_recording_converted.wav"
    audio_file.save(original_filepath)

    try:
        convert_audio_with_ffmpeg(original_filepath, converted_filepath)
        original_text = transcribe_audio_azure(converted_filepath)
        
        if not original_text:
            return jsonify({"original_text": "Nebylo nic rozpoznáno.", "edited_text": ""})

        cleanup_prompt = f"Oprav interpunkci, gramatiku a odstraň slovní vatu (jako 'ehm', 'hmm', 'jako') z následujícího textu, ale zachovej jeho význam: '{original_text}'"
        edited_text = call_gpt(cleanup_prompt)
        
        return jsonify({"original_text": original_text, "edited_text": edited_text})

    except Exception as e:
        logging.error(f"Došlo k chybě při zpracování audia: {e}")
        return jsonify({"error": f"Nastala chyba na serveru: {e}"}), 500
    finally:
        if os.path.exists(original_filepath):
            os.remove(original_filepath)
        if os.path.exists(converted_filepath):
            os.remove(converted_filepath)

@app.route('/manipulate-text', methods=['POST'])
def manipulate_text():
    data = request.json
    text, action, style = data.get('text'), data.get('action'), data.get('style', '')
    prompts = {"summarize": f"Vytvoř stručné shrnutí tohoto textu: '{text}'", "restyle": f"Přepiš tento text do {style} stylu: '{text}'", "expand": f"Rozšiř následující myšlenky a přidej relevantní detaily: '{text}'"}
    prompt = prompts.get(action)
    if not prompt: return jsonify({"error": "Neznámá akce"}), 400
    return jsonify({"text": call_gpt(prompt)})


# ====================================================================
# TENTO BLOK JE TAKÉ DŮLEŽITÝ PRO SPRÁVNOU FUNKCI
if __name__ == '__main__':
    # Tato část se používá pro lokální testování, Gunicorn ji ignoruje,
    # ale je dobrým zvykem ji v souboru mít.
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
# ====================================================================
