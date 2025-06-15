document.addEventListener('DOMContentLoaded', () => {
    // Získání prvků z HTML až po načtení stránky
    const recordStopButton = document.getElementById('recordStopButton');
    const statusText = document.getElementById('statusText');
    const visualizer = document.getElementById('audioVisualizer');
    const canvasCtx = visualizer.getContext('2d');
    const copyButton = document.getElementById('copyButton');
    const nativeShareButton = document.getElementById('nativeShareButton');
    const emailLink = document.getElementById('emailLink');
    const loader = document.getElementById('loader');
    const resultsDiv = document.getElementById('results');
    const editedTextElem = document.getElementById('editedText');
    const aiActionSelect = document.getElementById('aiActionSelect');

    // Proměnné pro stav a audio
    let isRecording = false;
    let mediaRecorder;
    let audioChunks = [];
    let audioContext;
    let analyser;
    let source;
    let animationFrameId;

    // Skryjeme nativní sdílení, pokud není podporováno
    if (!navigator.share) {
        nativeShareButton.classList.add('hidden');
    }

    // Připojení událostí k prvkům
    recordStopButton.addEventListener('click', () => { if (isRecording) { stopRecording(); } else { startRecording(); } });
    nativeShareButton.addEventListener('click', nativeShare);
    copyButton.addEventListener('click', copyTextToClipboard);
    editedTextElem.addEventListener('input', updateEmailLink);
    aiActionSelect.addEventListener('change', handleAiAction);

    // --- Definice funkcí ---

    function handleAiAction(event) {
        const selectedAction = event.target.value;
        if (selectedAction) {
            manipulateText(selectedAction);
            event.target.selectedIndex = 0; // Resetuje menu zpět na výchozí text
        }
    }

    function updateEmailLink() {
        const text = editedTextElem.value;
        const subject = "Přepsaný text z Audio Asistenta";
        emailLink.href = `mailto:?subject=${encodeURIComponent(subject)}&body=${encodeURIComponent(text)}`;
    }

    function nativeShare() {
        if (navigator.share) {
            navigator.share({
                title: 'Přepsaný text',
                text: editedTextElem.value,
            }).catch((error) => console.log('Chyba při sdílení:', error));
        }
    }

    function copyTextToClipboard() {
        navigator.clipboard.writeText(editedTextElem.value).then(() => {
            const originalIcon = copyButton.innerHTML;
            copyButton.innerHTML = `<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="#28a745" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M20 6 9 17l-5-5"/></svg>`;
            setTimeout(() => { copyButton.innerHTML = originalIcon; }, 2000);
        }, (err) => { alert('Chyba při kopírování textu: ', err); });
    }

    async function manipulateText(action, style = '') {
        const text = editedTextElem.value;
        loader.classList.remove('hidden');
        try {
            const response = await fetch('/manipulate-text', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ text, action, style }) });
            const data = await response.json();
            editedTextElem.value = data.text;
            updateEmailLink();
        } catch (error) {
            alert('Došlo k chybě při úpravě textu.');
        } finally {
            loader.classList.add('hidden');
        }
    }

    async function sendAudioToServer(audioBlob) {
        const formData = new FormData();
        formData.append('audio_file', audioBlob, 'recording.wav');
        loader.classList.remove('hidden');
        resultsDiv.classList.add('hidden');
        recordStopButton.disabled = true;
        try {
            const response = await fetch('/process-audio', { method: 'POST', body: formData });
            const data = await response.json();
            if (data.error) { throw new Error(data.error); }
            
            editedTextElem.value = data.edited_text; 
            
            resultsDiv.classList.remove('hidden');
            updateEmailLink();
        } catch (error) {
            alert(`Došlo k chybě při zpracování: ${error.message}`);
        } finally {
            loader.classList.add('hidden');
            recordStopButton.disabled = false;
        }
    }

    async function startRecording() {
        try {
            const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
            isRecording = true;
            updateButtonState(true); audioChunks = [];
            mediaRecorder = new MediaRecorder(stream);
            mediaRecorder.start();
            audioContext = new (window.AudioContext || window.webkitAudioContext)();
            source = audioContext.createMediaStreamSource(stream);
            analyser = audioContext.createAnalyser();
            analyser.fftSize = 2048; source.connect(analyser);
            draw();
            mediaRecorder.addEventListener("dataavailable", event => { audioChunks.push(event.data); });
            mediaRecorder.addEventListener("stop", () => {
                stream.getTracks().forEach(track => track.stop());
                const audioBlob = new Blob(audioChunks, { type: 'audio/wav' });
                sendAudioToServer(audioBlob);
            });
        } catch (err) { alert("Chyba: Nepodařilo se získat přístup k mikrofonu."); console.error("getUserMedia error:", err); }
    }

    function stopRecording() {
        if (mediaRecorder) {
            mediaRecorder.stop(); isRecording = false;
            updateButtonState(false);
            if (animationFrameId) cancelAnimationFrame(animationFrameId);
            if (audioContext) audioContext.close();
            clearCanvas();
        }
    }

    function draw() {
        animationFrameId = requestAnimationFrame(draw);
        if (!analyser) return; // Pojistka pro případ, že se funkce zavolá po zastavení
        const bufferLength = analyser.frequencyBinCount;
        const dataArray = new Uint8Array(bufferLength);
        analyser.getByteTimeDomainData(dataArray);
        canvasCtx.clearRect(0, 0, visualizer.width, visualizer.height);
        const gradient = canvasCtx.createLinearGradient(0, 0, visualizer.width, 0);
        gradient.addColorStop(0, '#6e56ff'); gradient.addColorStop(1, '#ff4aa1');
        canvasCtx.lineWidth = 2; canvasCtx.strokeStyle = gradient;
        canvasCtx.beginPath();
        const sliceWidth = visualizer.width * 1.0 / bufferLength;
        let x = 0;
        for (let i = 0; i < bufferLength; i++) {
            const v = dataArray[i] / 128.0; const y = v * visualizer.height / 2;
            if (i === 0) { canvasCtx.moveTo(x, y); } else { canvasCtx.lineTo(x, y); }
            x += sliceWidth;
        }
        canvasCtx.lineTo(visualizer.width, visualizer.height / 2); canvasCtx.stroke();
    }

    function clearCanvas() { canvasCtx.clearRect(0, 0, visualizer.width, visualizer.height); }

    function updateButtonState(recording) {
        recordStopButton.classList.toggle('is-recording', recording);
        statusText.textContent = recording ? 'Nahrávám...' : 'Stiskněte pro nahrávání';
    }
});
