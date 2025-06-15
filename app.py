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

app = Flask(__name__)


def transcribe_audio_azure(audio_filename):
    logging.info(f"Spouštím přepis souboru: {audio_filename}")
    speech_config = speechsdk.SpeechConfig(
        subscription=os.getenv("AZURE_SPEECH_KEY"), 
        region=os.getenv("AZURE_SPEECH_REGION")
    )
    speech_config.speech_recognition_language = "cs-CZ"
    speech_config.set_property(speechsdk.PropertyId.Speech_SegmentationSilenceTimeoutMs, "5000")
    
    audio_config = speechsdk.audio.AudioConfig(filename=audio_filename)
    speech_recognizer = speechsdk.SpeechRecognizer(speech_config=speech_config, audio_config=audio_config)
    result = speech_recognizer.recognize_once_async().get()
    
    if result.reason == speechsdk.ResultReason.RecognizedSpeech:
        logging.info("Azure: Řeč úspěšně rozpoznána.")
        return result.text
    elif result.reason == speechsdk.ResultReason.NoMatch:
        logging.warning("Azure: Řeč nebyla rozpoznána.")
        return "Řeč nebyla rozpoznána."
    else:
        cancellation_details = result.cancellation_details
        logging.error(f"Azure: Přepis zrušen: {cancellation_details.reason}")
        if cancellation_details.reason == speechsdk.CancellationReason.Error:
            logging.error(f"Azure: Detail chyby: {cancellation_details.error_details}")
        raise Exception(f"Azure chyba: {cancellation_details.reason}")


def convert_audio_with_ffmpeg(input_path, output_path):
    logging.info(f"Spouštím konverzi souboru '{input_path}' na '{output_path}' pomocí ffmpeg.")
    try:
        command = ["ffmpeg", "-i", input_path, "-acodec", "pcm_s16le", "-ac", "1", "-ar", "16000", "-y", output_path]
        subprocess.run(command, check=True, capture_output=True, text=True)
        logging.info("FFmpeg konverze úspěšná.")
    except subprocess.CalledProcessError as e:
        logging.error(f"FFmpeg selhal s chybou: {e.stderr}")
        raise RuntimeError(f"Chyba při konverzi audia: {e.stderr}")

# ====================================================================
# ZMĚNA ZDE: Funkce nyní přijímá 'temperature' jako argument
# ====================================================================
def call_gpt(prompt, temperature=0.5):
    """
    Volá OpenAI API s možností nastavit 'teplotu' (kreativitu).
    Výchozí hodnota je 0.5 pro kreativní úkoly.
    """
    try:
        logging.info(f"Volám OpenAI s teplotou: {temperature}")
        response = openai.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "Jsi expert na stylistiku a gramatiku českého jazyka. Tvé odpovědi jsou stručné a přímo k věci."},
                {"role": "user", "content": prompt}
            ],
            temperature=temperature  # Použije se předaná hodnota
        )
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
        
        if not original_text or original_text == "Řeč nebyla rozpoznána.":
            return jsonify({"edited_text": "Nepodařilo se rozpoznat žádnou řeč. Zkuste to prosím znovu."})

        cleanup_prompt = f"Oprav interpunkci, gramatiku a odstraň slovní vatu (jako 'ehm', 'hmm', 'jako') z následujícího textu, ale zachovej jeho význam a původní formulaci vět: '{original_text}'"
        
        # ====================================================================
        # ZMĚNA ZDE: Pro prvotní čištění voláme funkci s nízkou teplotou 0.2
        # ====================================================================
        edited_text = call_gpt(cleanup_prompt, temperature=0.2)
        
        # Vrátíme pouze 'edited_text', protože 'original_text' už na frontendu nezobrazujeme
        return jsonify({"edited_text": edited_text})

    except Exception as e:
        logging.error(f"Došlo k chybě při zpracování audia: {e}")
        return jsonify({"error": f"Nastala chyba na serveru: {e}"}), 500
    finally:
        if os.path.exists(original_filepath): os.remove(original_filepath)
        if os.path.exists(converted_filepath): os.remove(converted_filepath)

@app.route('/manipulate-text', methods=['POST'])
def manipulate_text():
    data = request.json
    text, action, style = data.get('text'), data.get('action'), data.get('style', '')
    prompts = {"summarize": f"Vytvoř stručné shrnutí tohoto textu: '{text}'", "restyle": f"Přepiš tento text do {style} stylu: '{text}'", "expand": f"Rozšiř následující myšlenky a přidej relevantní detaily: '{text}'"}
    prompt = prompts.get(action)
    if not prompt: return jsonify({"error": "Neznámá akce"}), 400
    
    # Pro kreativní úpravy necháme výchozí, vyšší teplotu (0.5)
    return jsonify({"text": call_gpt(prompt)})

if __name__ == '__main__':
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
