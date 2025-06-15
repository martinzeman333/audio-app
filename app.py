import os
import openai
import azure.cognitiveservices.speech as speechsdk
from flask import Flask, render_template, request, jsonify
from dotenv import load_dotenv

# Načtení API klíčů ze souboru .env
load_dotenv()
openai.api_key = os.getenv("OPENAI_API_KEY")

# Inicializace Flask aplikace
app = Flask(__name__)

# Funkce pro přepis audia pomocí Azure
def transcribe_audio_azure(audio_filename):
    speech_config = speechsdk.SpeechConfig(
        subscription=os.getenv("AZURE_SPEECH_KEY"), 
        region=os.getenv("AZURE_SPEECH_REGION")
    )
    speech_config.speech_recognition_language = "cs-CZ"
    audio_config = speechsdk.audio.AudioConfig(filename=audio_filename)
    recognizer = speechsdk.SpeechRecognizer(speech_config=speech_config, audio_config=audio_config)
    
    result = recognizer.recognize_once_async().get()
    
    if result.reason == speechsdk.ResultReason.RecognizedSpeech:
        return result.text
    elif result.reason == speechsdk.ResultReason.NoMatch:
        return "Řeč nebyla rozpoznána."
    else:
        return f"Chyba při přepisu: {result.cancellation_details.reason}"

# Funkce pro volání OpenAI API (používáme novější Chat modely)
def call_gpt(prompt):
    try:
        response = openai.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "Jsi užitečný asistent, který pracuje s textem."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"Chyba při volání OpenAI: {e}"

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/process-audio', methods=['POST'])
def process_audio():
    if 'audio_file' not in request.files:
        return jsonify({"error": "Chybí audio soubor"}), 400

    audio_file = request.files['audio_file']
    filepath = "temp_recording.wav"
    audio_file.save(filepath)

    # 1. Přepis pomocí Azure
    original_text = transcribe_audio_azure(filepath)
    os.remove(filepath) # Smazání dočasného souboru

    if "Chyba" in original_text or "nebyla rozpoznána" in original_text:
        return jsonify({"error": original_text})

    # 2. Vylepšení textu pomocí ChatGPT
    cleanup_prompt = f"Oprav interpunkci, gramatiku a odstraň slovní vatu (jako 'ehm', 'hmm', 'jako') z následujícího textu, ale zachovej jeho význam: '{original_text}'"
    edited_text = call_gpt(cleanup_prompt)
    
    return jsonify({
        "original_text": original_text,
        "edited_text": edited_text
    })

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
    if not prompt:
        return jsonify({"error": "Neznámá akce"}), 400
        
    result_text = call_gpt(prompt)
    return jsonify({"text": result_text})

@app.route('/share', methods=['POST'])
def share():
    data = request.json
    text = data.get('text')
    recipient = data.get('recipient')
    method = data.get('method')

    # Zde by byla integrace reálné služby (SendGrid, Twilio atd.)
    # Prozatím jen simulujeme odeslání
    print(f"POŽADAVEK NA SDÍLENÍ: Metoda='{method}', Příjemce='{recipient}', Text='{text[:50]}...'")
    
    return jsonify({"message": f"Text byl úspěšně 'odeslán' na {recipient}."})

if __name__ == '__main__':
    # Port se nastavuje pro lokální běh, Render si ho nastaví sám
    app.run(host="0.0.0.0", port=int(os.environ.get('PORT', 5000)))