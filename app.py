# app.py

# Na začátek souboru přidejte tento import
from pydub import AudioSegment
import os
import openai
# ... zbytek vašich importů ...

# ... zbytek vašeho kódu ...

# NAHRAĎTE TUTO FUNKCI
@app.route('/process-audio', methods=['POST'])
def process_audio():
    if 'audio_file' not in request.files:
        return jsonify({"error": "Chybí audio soubor"}), 400

    audio_file = request.files['audio_file']
    # Uložíme soubory s dočasnými, ale jasnými názvy
    original_filepath = "temp_recording.original"
    fixed_filepath = "temp_recording_fixed.wav"
    audio_file.save(original_filepath)

    try:
        # --- NOVÝ KROK: Konverze audia pomocí Pydub ---
        logging.info("Spouštím konverzi audia pomocí pydub...")
        # Načteme nahraný soubor (pydub si poradí s různými formáty)
        sound = AudioSegment.from_file(original_filepath)
        # Exportujeme ho do zaručeně správného formátu WAV
        sound.export(fixed_filepath, format="wav")
        logging.info("Audio úspěšně převedeno do standardního formátu WAV.")
        # ---------------------------------------------

        # 1. Přepis pomocí Azure - nyní použijeme opravený soubor
        logging.info("Spouštím přepis v Azure...")
        original_text = transcribe_audio_azure(fixed_filepath) # <-- ZMĚNA ZDE
        
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
        logging.error(f"Došlo k chybě při zpracování audia: {e}")
        return jsonify({"error": f"Nastala chyba na serveru: {e}"}), 500
    finally:
        # Zajistíme, že se oba dočasné soubory vždy smažou
        if os.path.exists(original_filepath):
            os.remove(original_filepath)
        if os.path.exists(fixed_filepath):
            os.remove(fixed_filepath)
