// Získání prvků z HTML
const recordStopButton = document.getElementById('recordStopButton');
const statusText = document.getElementById('statusText');
const visualizer = document.getElementById('audioVisualizer');
const canvasCtx = visualizer.getContext('2d');

const loader = document.getElementById('loader');
const resultsDiv = document.getElementById('results');
const originalTextElem = document.getElementById('originalText');
const editedTextElem = document.getElementById('editedText');

// Proměnné pro stav a audio
let isRecording = false;
let mediaRecorder;
let audioChunks = [];
let audioContext;
let analyser;
let source;
let animationFrameId;

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

        audioChunks = [];
        mediaRecorder = new MediaRecorder(stream);
        mediaRecorder.start();

        // --- Logika pro vizualizaci ---
        audioContext = new (window.AudioContext || window.webkitAudioContext)();
        source = audioContext.createMediaStreamSource(stream);
        analyser = audioContext.createAnalyser();
        analyser.fftSize = 2048;
        source.connect(analyser);
        draw(); // Spuštění vizualizace

        mediaRecorder.addEventListener("dataavailable", event => {
            audioChunks.push(event.data);
        });

        mediaRecorder.addEventListener("stop", () => {
            stream.getTracks().forEach(track => track.stop());
            const audioBlob = new Blob(audioChunks, { type: 'audio/wav' });
            sendAudioToServer(audioBlob);
        });

    } catch (err) {
        alert("Chyba: Nepodařilo se získat přístup k mikrofonu.");
        console.error("getUserMedia error:", err);
    }
}

// Funkce pro zastavení nahrávání
function stopRecording() {
    if (mediaRecorder) {
        mediaRecorder.stop();
        isRecording = false;
        updateButtonState(false);
        
        // Zastavení vizualizace
        cancelAnimationFrame(animationFrameId);
        audioContext.close();
        clearCanvas();
    }
}

// Funkce pro vizualizaci zvuku na canvasu
function draw() {
    animationFrameId = requestAnimationFrame(draw);
    const bufferLength = analyser.frequencyBinCount;
    const dataArray = new Uint8Array(bufferLength);
    analyser.getByteTimeDomainData(dataArray);

    canvasCtx.clearRect(0, 0, visualizer.width, visualizer.height);
    
    // Vytvoření gradientu pro čáru
    const gradient = canvasCtx.createLinearGradient(0, 0, visualizer.width, 0);
    gradient.addColorStop(0, '#6e56ff');
    gradient.addColorStop(1, '#ff4aa1');

    canvasCtx.lineWidth = 2;
    canvasCtx.strokeStyle = gradient;
    canvasCtx.beginPath();

    const sliceWidth = visualizer.width * 1.0 / bufferLength;
    let x = 0;

    for (let i = 0; i < bufferLength; i++) {
        const v = dataArray[i] / 128.0;
        const y = v * visualizer.height / 2;
        if (i === 0) {
            canvasCtx.moveTo(x, y);
        } else {
            canvasCtx.lineTo(x, y);
        }
        x += sliceWidth;
    }
    canvasCtx.lineTo(visualizer.width, visualizer.height / 2);
    canvasCtx.stroke();
}

function clearCanvas() {
    canvasCtx.clearRect(0, 0, visualizer.width, visualizer.height);
}

// Funkce pro aktualizaci vzhledu tlačítka
function updateButtonState(recording) {
    recordStopButton.classList.toggle('is-recording', recording);
    statusText.textContent = recording ? 'Nahrávám...' : 'Stiskněte pro nahrávání';
}

// --- Ostatní funkce (odeslání, manipulace) zůstávají stejné ---

async function sendAudioToServer(audioBlob) {
    const formData = new FormData();
    formData.append('audio_file', audioBlob, 'recording.wav');

    loader.classList.remove('hidden');
    resultsDiv.classList.add('hidden');
    recordStopButton.disabled = true;

    try {
        const response = await fetch('/process-audio', {
            method: 'POST',
            body: formData,
        });
        const data = await response.json();
        if (data.error) { throw new Error(data.error); }
        originalTextElem.textContent = data.original_text;
        editedTextElem.value = data.edited_text;
        resultsDiv.classList.remove('hidden');
    } catch (error) {
        alert(`Došlo k chybě při zpracování: ${error.message}`);
    } finally {
        loader.classList.add('hidden');
        recordStopButton.disabled = false;
    }
}

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
