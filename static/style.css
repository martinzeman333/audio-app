document.addEventListener('DOMContentLoaded', () => {
    // Získání prvků z HTML
    const recordStopButton = document.getElementById('recordStopButton');
    const processButton = document.getElementById('processButton');
    const micIcon = document.getElementById('mic-icon');
    const pauseIcon = document.getElementById('pause-icon');
    const statusText = document.getElementById('statusText');
    const visualizer = document.getElementById('audioVisualizer');
    const canvasCtx = visualizer.getContext('2d');
    const copyButton = document.getElementById('copyButton');
    const nativeShareButton = document.getElementById('nativeShareButton');
    const emailLink = document.getElementById('emailLink');
    const loader = document.getElementById('loader');
    const loaderText = document.getElementById('loader-text');
    const resultsDiv = document.getElementById('results');
    const editedTextElem = document.getElementById('editedText');
    const aiActionSelect = document.getElementById('aiActionSelect');
    const historyContainer = document.getElementById('history-container');
    const historyList = document.getElementById('history-list');

    // Globální proměnná pro ukládání historie
    let history = [];
    
    // Proměnné pro stav nahrávání
    let recordingState = 'inactive';
    let mediaRecorder, audioChunks = [], audioContext, analyser, source, animationFrameId;

    // --- FUNKCE PRO PRÁCI S HISTORIÍ ---
    
    function saveHistory() {
        localStorage.setItem('audioHistory', JSON.stringify(history));
    }

    function loadHistory() {
        const savedHistory = localStorage.getItem('audioHistory');
        if (savedHistory) {
            history = JSON.parse(savedHistory);
            renderHistory();
        }
    }

    function renderHistory() {
        historyList.innerHTML = '';
        if (history.length > 0) {
            historyContainer.classList.remove('hidden');
        } else {
            historyContainer.classList.add('hidden');
        }

        history.forEach(item => {
            const li = document.createElement('li');
            li.className = 'history-item';
            li.dataset.id = item.id;

            const titleSpan = document.createElement('span');
            titleSpan.className = 'history-title';
            titleSpan.textContent = item.title;
            titleSpan.addEventListener('click', () => {
                editedTextElem.value = item.text;
                resultsDiv.classList.remove('hidden');
                updateEmailLink();
                window.scrollTo({ top: 0, behavior: 'smooth' });
            });

            const deleteBtn = document.createElement('button');
            deleteBtn.className = 'delete-history-btn';
            deleteBtn.innerHTML = `<svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="3 6 5 6 21 6"></polyline><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path><line x1="10" y1="11" x2="10" y2="17"></line><line x1="14" y1="11" x2="14" y2="17"></line></svg>`;
            deleteBtn.ariaLabel = 'Smazat položku';
            deleteBtn.addEventListener('click', () => {
                if (confirm(`Opravdu chcete smazat záznam "${item.title}"?`)) {
                    history = history.filter(h => h.id !== item.id);
                    saveHistory();
                    renderHistory();
                }
            });

            li.appendChild(titleSpan);
            li.appendChild(deleteBtn);
            historyList.appendChild(li);
        });
    }

    function addToHistory(newItem) {
        history.unshift(newItem);
        if (history.length > 50) {
            history.pop();
        }
        saveHistory();
        renderHistory();
    }
    
    // --- PŘIPOJENÍ EVENT LISTENERŮ ---
    if (!navigator.share) { nativeShareButton.classList.add('hidden'); }
    recordStopButton.addEventListener('click', handleRecordClick);
    processButton.addEventListener('click', finishRecording);
    nativeShareButton.addEventListener('click', nativeShare);
    copyButton.addEventListener('click', copyTextToClipboard);
    editedTextElem.addEventListener('input', updateEmailLink);
    aiActionSelect.addEventListener('change', handleAiAction);

    loadHistory();

    function handleRecordClick() {
        if (recordingState === 'inactive') startRecording();
        else if (recordingState === 'recording') pauseRecording();
        else if (recordingState === 'paused') resumeRecording();
    }

    async function startRecording() {
        try {
            resultsDiv.classList.add('hidden');
            const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
            recordingState = 'recording';
            updateButtonState(); 
            audioChunks = [];
            mediaRecorder = new MediaRecorder(stream);
            
            mediaRecorder.addEventListener("dataavailable", event => { 
                audioChunks.push(event.data); 
            });

            mediaRecorder.addEventListener("stop", () => {
                const audioBlob = new Blob(audioChunks, { type: 'audio/wav' });
                
                if (audioBlob.size < 4096) { // Zvýšena kontrola pro jistotu
                    alert("Nahrávka byla příliš krátká nebo prázdná. Zkuste to prosím znovu.");
                    recordingState = 'inactive';
                    updateButtonState();
                    return;
                }

                uploadAndProcessAudio(audioBlob);
                stream.getTracks().forEach(track => track.stop());
                if (animationFrameId) cancelAnimationFrame(animationFrameId);
                if (audioContext) audioContext.close();
                clearCanvas();
            });

            mediaRecorder.start();
            audioContext = new (window.AudioContext || window.webkitAudioContext)();
            source = audioContext.createMediaStreamSource(stream);
            analyser = audioContext.createAnalyser();
            analyser.fftSize = 2048; 
            source.connect(analyser);
            draw();
        } catch (err) { 
            alert("Chyba: Nepodařilo se získat přístup k mikrofonu.");
            recordingState = 'inactive';
            updateButtonState();
        }
    }

    function pauseRecording() {
        if (mediaRecorder && mediaRecorder.state === 'recording') {
            mediaRecorder.pause();
            recordingState = 'paused';
            updateButtonState();
        }
    }

    function resumeRecording() {
        if (mediaRecorder && mediaRecorder.state === 'paused') {
            mediaRecorder.resume();
            recordingState = 'recording';
            updateButtonState();
        }
    }

    function finishRecording() {
        if (mediaRecorder && mediaRecorder.state !== 'inactive') {
            mediaRecorder.stop();
            recordingState = 'inactive';
            updateButtonState();
        }
    }

    function updateButtonState() {
        if (recordingState === 'inactive') {
            recordStopButton.classList.remove('is-recording'); micIcon.classList.remove('hidden'); pauseIcon.classList.add('hidden');
            statusText.textContent = 'Stiskněte pro nahrávání';
            processButton.classList.add('hidden');
        } else if (recordingState === 'recording') {
            recordStopButton.classList.add('is-recording'); micIcon.classList.add('hidden'); pauseIcon.classList.remove('hidden');
            statusText.textContent = 'Nahrávám... (klikněte pro pauzu)';
            processButton.classList.remove('hidden');
        } else if (recordingState === 'paused') {
            recordStopButton.classList.remove('is-recording'); micIcon.classList.remove('hidden'); pauseIcon.classList.add('hidden');
            statusText.textContent = 'Pozastaveno (klikněte pro pokračování)';
            processButton.classList.remove('hidden');
        }
    }
    
    async function uploadAndProcessAudio(audioBlob, retries = 3, delay = 5000) {
        loader.classList.remove('hidden');
        resultsDiv.classList.add('hidden');
        recordStopButton.disabled = true;
        processButton.disabled = true;

        try {
            const formData = new FormData();
            formData.append('audio_file', audioBlob, 'recording.wav');

            if (retries < 3) {
                 loaderText.textContent = `Server se probouzí, zkouším znovu...`;
            } else {
                loaderText.textContent = 'Nahrávám soubor na server...';
            }
            
            const uploadResponse = await fetch('/upload-audio', { method: 'POST', body: formData });
            
            if (!uploadResponse.ok) {
                let errorMessage = `Chyba při nahrávání: ${uploadResponse.status} ${uploadResponse.statusText}`;
                try {
                    const errData = await uploadResponse.json();
                    errorMessage = errData.error || errorMessage;
                } catch (e) {
                    console.error("Chybová odpověď serveru nebyla ve formátu JSON.", e);
                }
                throw new Error(errorMessage);
            }

            const { job_id } = await uploadResponse.json();
            pollStatus(job_id);

        } catch (error) {
            if (error instanceof TypeError && retries > 0) {
                console.warn(`Síťová chyba, pravděpodobně se server probouzí. Zkouším znovu za ${delay / 1000}s...`);
                setTimeout(() => uploadAndProcessAudio(audioBlob, retries - 1, delay), delay);
            } else {
                console.error("Kompletní chyba při nahrávání:", error);
                let userMessage = `Došlo k chybě: ${error.message}`;
                if (error instanceof TypeError) {
                    userMessage = 'Chyba sítě: Nelze se připojit k serveru. Zkuste to prosím znovu.';
                }
                alert(userMessage);
                loader.classList.add('hidden');
                recordStopButton.disabled = false;
                processButton.disabled = false;
            }
        }
    }

    function pollStatus(jobId) {
        const intervalId = setInterval(async () => {
            try {
                const statusResponse = await fetch(`/status/${jobId}`);
                if (!statusResponse.ok) {
                    clearInterval(intervalId);
                    throw new Error(`Chyba při zjišťování stavu: ${statusResponse.status} ${statusResponse.statusText}`);
                }
                const job = await statusResponse.json();

                if (job.message) {
                    loaderText.textContent = job.message;
                }

                if (job.status === 'completed') {
                    clearInterval(intervalId);
                    const data = job.result;
                    editedTextElem.value = data.edited_text; 
                    resultsDiv.classList.remove('hidden');
                    updateEmailLink();
                    addToHistory({ id: data.id, title: data.title, text: data.edited_text });
                    loader.classList.add('hidden');
                    recordStopButton.disabled = false;
                    processButton.disabled = false;
                } else if (job.status === 'failed') {
                    clearInterval(intervalId);
                    throw new Error(job.error || 'Neznámá chyba při zpracování na serveru.');
                }
            } catch (error) {
                console.error("Kompletní chyba při dotazování na stav:", error);
                clearInterval(intervalId);
                alert(`Došlo k chybě při zpracování: ${error.message}`);
                loader.classList.add('hidden');
                recordStopButton.disabled = false;
                processButton.disabled = false;
            }
        }, 3000);
    }
    
    function handleAiAction(event) {
        const selectedAction = event.target.value;
        if (selectedAction) {
            manipulateText(selectedAction);
            event.target.selectedIndex = 0;
        }
    }

    async function manipulateText(action, style = '') {
        const text = editedTextElem.value;
        loaderText.textContent = 'Komunikuji s AI...';
        loader.classList.remove('hidden');
        try {
            const response = await fetch('/manipulate-text', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ text, action, style }) });
            if (!response.ok) {
                 throw new Error(`Chyba serveru při AI úpravě: ${response.status} ${response.statusText}`);
            }
            const data = await response.json();
            editedTextElem.value = data.text;
            updateEmailLink();
        } catch (error) {
            alert(`Došlo k chybě při úpravě textu: ${error.message}`);
        } finally {
            loader.classList.add('hidden');
        }
    }

    function updateEmailLink() {
        const text = editedTextElem.value;
        const subject = "Přepsaný text z Audio Asistenta";
        emailLink.href = `mailto:?subject=${encodeURIComponent(subject)}&body=${encodeURIComponent(text)}`;
    }

    function nativeShare() {
        if (navigator.share) {
            navigator.share({ title: 'Přepsaný text', text: editedTextElem.value })
            .catch((error) => console.log('Chyba při sdílení:', error));
        }
    }

    function copyTextToClipboard() {
        navigator.clipboard.writeText(editedTextElem.value).then(() => {
            const originalIcon = copyButton.innerHTML;
            copyButton.innerHTML = `<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="#28a745" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M20 6 9 17l-5-5"/></svg>`;
            setTimeout(() => { copyButton.innerHTML = originalIcon; }, 2000);
        });
    }

    function draw() {
        animationFrameId = requestAnimationFrame(draw);
        if (!analyser) return;
        const bufferLength = analyser.frequencyBinCount;
        const dataArray = new Uint8Array(bufferLength);
        analyser.getByteTimeDomainData(dataArray);
        canvasCtx.clearRect(0, 0, visualizer.width, visualizer.height);
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
            if (i === 0) { canvasCtx.moveTo(x, y); } else { canvasCtx.lineTo(x, y); }
            x += sliceWidth;
        }
        canvasCtx.lineTo(visualizer.width, visualizer.height / 2); 
        canvasCtx.stroke();
    }
    
    function clearCanvas() { canvasCtx.clearRect(0, 0, visualizer.width, visualizer.height); }
});
