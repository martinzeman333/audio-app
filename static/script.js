// Získání prvků z HTML
const recordButton = document.getElementById('recordButton');
const stopButton = document.getElementById('stopButton');
const loader = document.getElementById('loader');
const resultsDiv = document.getElementById('results');
const originalTextElem = document.getElementById('originalText');
const editedTextElem = document.getElementById('editedText');

let mediaRecorder;
let audioChunks = [];

// Spuštění nahrávání
recordButton.addEventListener('click', async () => {
    try {
        const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
        mediaRecorder = new MediaRecorder(stream);
        mediaRecorder.start();
        audioChunks = [];
        recordButton.disabled = true;
        stopButton.disabled = false;
        resultsDiv.classList.add('hidden');
    } catch (err) {
        alert("Chyba: Nepodařilo se získat přístup k mikrofonu.");
    }
});

// Zastavení nahrávání
stopButton.addEventListener('click', () => {
    mediaRecorder.stop();
    recordButton.disabled = false;
    stopButton.disabled = true;
});

// Co se stane, když je nahrávání dokončeno
mediaRecorder.addEventListener("stop", () => {
    const audioBlob = new Blob(audioChunks, { type: 'audio/wav' });
    sendAudioToServer(audioBlob);
});

mediaRecorder.addEventListener("dataavailable", event => {
    audioChunks.push(event.data);
});

// Funkce pro odeslání audio souboru na server
async function sendAudioToServer(audioBlob) {
    const formData = new FormData();
    formData.append('audio_file', audioBlob, 'recording.wav');

    loader.classList.remove('hidden');
    resultsDiv.classList.add('hidden');

    try {
        const response = await fetch('/process-audio', {
            method: 'POST',
            body: formData,
        });
        const data = await response.json();
        if (data.error) {
            throw new Error(data.error);
        }
        originalTextElem.textContent = data.original_text;
        editedTextElem.value = data.edited_text;
        loader.classList.add('hidden');
        resultsDiv.classList.remove('hidden');
    } catch (error) {
        loader.classList.add('hidden');
        alert(`Došlo k chybě: ${error.message}`);
    }
}

// Funkce pro další manipulaci s textem
async function manipulateText(action, style = '') {
    const text = editedTextElem.value;
    loader.classList.remove('hidden');
    try {
        const response = await fetch('/manipulate-text', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ text, action, style })
        });
        const data = await response.json();
        editedTextElem.value = data.text;
    } catch (error) {
        alert('Došlo k chybě při úpravě textu.');
    } finally {
        loader.classList.add('hidden');
    }
}

// Funkce pro sdílení emailem
async function share(method) {
    const text = editedTextElem.value;
    const recipient = document.getElementById('emailInput').value;
    
    if (method === 'email' && !recipient) {
        alert('Prosím, zadejte e-mailovou adresu.');
        return;
    }

    try {
        const response = await fetch('/share', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ text, recipient, method })
        });
        const data = await response.json();
        alert(data.message);
    } catch (error) {
        alert('Došlo k chybě při sdílení.');
    }
}