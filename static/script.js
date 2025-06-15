// Získání prvků z HTML
const recordStopButton = document.getElementById('recordStopButton');
const buttonText = document.getElementById('button-text');
const micIcon = document.getElementById('mic-icon');
const stopIcon = document.getElementById('stop-icon');
const timerElement = document.getElementById('timer');

const loader = document.getElementById('loader');
const resultsDiv = document.getElementById('results');
const originalTextElem = document.getElementById('originalText');
const editedTextElem = document.getElementById('editedText');

// Proměnné pro stav nahrávání
let isRecording = false;
let mediaRecorder;
let audioChunks = [];
let timerInterval;
let seconds = 0;

// Hlavní událost pro kliknutí na tlačítko
recordStopButton.addEventListener('click', () => {
    if (isRecording) {
        stopRecording();
    } else {
        startRecording();
    }
});

// Funkce pro spuštění nahrávání
async function startRecording() {
    try {
        const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
        isRecording = true;
        updateButtonState(true);
        startTimer();

        audioChunks = [];
        mediaRecorder = new MediaRecorder(stream);
        mediaRecorder.start();

        mediaRecorder.addEventListener("dataavailable", event => {
            audioChunks.push(event.data);
        });

        mediaRecorder.addEventListener("stop", () => {
            // Zastavíme stream, aby ikona mikrofonu v prohlížeči zmizela
            stream.getTracks().forEach(track => track.stop());
            const audioBlob = new Blob(audioChunks, { type: 'audio/wav' });
            sendAudioToServer(audioBlob);
        });

    } catch (err) {
        alert("Chyba: Nepodařilo se získat přístup k mikrofonu. Zkontrolujte prosím oprávnění v nastavení prohlížeče.");
        console.error("getUserMedia error:", err);
    }
}

// Funkce pro zastavení nahrávání
function stopRecording() {
    if (mediaRecorder) {
        mediaRecorder.stop();
        isRecording = false;
        updateButtonState(false);
        stopTimer();
    }
}

// Funkce pro aktualizaci vzhledu tlačítka
function updateButtonState(recording) {
    if (recording) {
        recordStopButton.classList.add('is-recording');
        buttonText.textContent = 'Zastavit';
        micIcon.classList.add('hidden');
        stopIcon.classList.remove('hidden');
    } else {
        recordStopButton.classList.remove('is-recording');
        buttonText.textContent = 'Nahrát';
        micIcon.classList.remove('hidden');
        stopIcon.classList.add('hidden');
    }
}

// Funkce pro časovač
function startTimer() {
    timerElement.textContent = '00:00';
    seconds = 0;
    timerInterval = setInterval(() => {
        seconds++;
        const minutes = Math.floor(seconds / 60).toString().padStart(2, '0');
        const secs = (seconds % 60).toString().padStart(2, '0');
        timerElement.textContent = `${minutes}:${secs}`;
    }, 1000);
}

function stopTimer() {
    clearInterval(timerInterval);
}

// Funkce pro odeslání audia na server
async function sendAudioToServer(audioBlob) {
    const formData = new FormData();
    formData.append('audio_file', audioBlob, 'recording.wav');

    loader.classList.remove('hidden');
    resultsDiv.classList.add('hidden');
    recordStopButton.disabled = true; // Zamkneme tlačítko během zpracování

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
        resultsDiv.classList.remove('hidden');
    } catch (error) {
        alert(`Došlo k chybě při zpracování: ${error.message}`);
    } finally {
        loader.classList.add('hidden');
        recordStopButton.disabled = false; // Odemkneme tlačítko
    }
}


// --- Funkce pro další úpravy a sdílení (zůstávají stejné) ---
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
