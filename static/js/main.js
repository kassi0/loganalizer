document.addEventListener('DOMContentLoaded', () => {
    const dropzone = document.getElementById('dropzone');
    const fileInput = document.getElementById('logfile');
    const uploadForm = document.getElementById('upload-form');
    const dropzoneText = document.getElementById('dropzone-text');
    const dropzoneSub = document.getElementById('dropzone-sub');
    const submitBtn = document.getElementById('submit-btn');
    const progressContainer = document.getElementById('progress-container');
    const progressBar = document.getElementById('progress-bar');
    const statusMessage = document.getElementById('status-message');

    if (!dropzone || !fileInput) return;

    dropzone.addEventListener('click', () => fileInput.click());

    dropzone.addEventListener('dragover', (e) => {
        e.preventDefault();
        dropzone.classList.add('dragover');
    });

    dropzone.addEventListener('dragleave', () => {
        dropzone.classList.remove('dragover');
    });

    dropzone.addEventListener('drop', (e) => {
        e.preventDefault();
        dropzone.classList.remove('dragover');
        if (e.dataTransfer.files.length > 0) {
            fileInput.files = e.dataTransfer.files;
            updateFileInfo(fileInput.files[0]);
        }
    });

    fileInput.addEventListener('change', () => {
        if (fileInput.files.length > 0) {
            updateFileInfo(fileInput.files[0]);
        }
    });

    function updateFileInfo(file) {
        const sizeMb = (file.size / (1024 * 1024)).toFixed(2);
        dropzoneText.textContent = `Arquivo selecionado: ${file.name}`;
        dropzoneSub.textContent = `Tamanho: ${sizeMb} MB - Pronto para processamento`;
        dropzoneText.style.color = '#38bdf8';
    }

    uploadForm.addEventListener('submit', (e) => {
        e.preventDefault();

        if (!fileInput.files || fileInput.files.length === 0) {
            alert('Por favor, selecione um arquivo de log.');
            return;
        }

        const formData = new FormData(uploadForm);
        submitBtn.disabled = true;
        submitBtn.innerHTML = `
            <svg class="animate-spin" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <circle cx="12" cy="12" r="10" stroke-opacity="0.25"></circle>
                <path d="M12 2a10 10 0 0 1 10 10" stroke-linecap="round"></path>
            </svg>
            Processando Multi-Core...
        `;

        progressContainer.style.display = 'block';
        progressBar.style.width = '35%';
        statusMessage.style.display = 'block';
        statusMessage.style.color = 'var(--text-secondary)';
        statusMessage.innerHTML = 'Enviando arquivo e dividindo fatias de processamento entre as CPUs...';

        const xhr = new XMLHttpRequest();
        xhr.open('POST', '/upload', true);

        xhr.upload.onprogress = (event) => {
            if (event.lengthComputable) {
                const percent = Math.round((event.loaded / event.total) * 60);
                progressBar.style.width = `${percent}%`;
                if (percent >= 60) {
                    statusMessage.innerHTML = '⚡ Arquivo recebido! Os núcleos da CPU estão processando as linhas do log em paralelo...';
                    progressBar.style.width = '85%';
                }
            }
        };

        xhr.onload = () => {
            if (xhr.status === 200) {
                const resp = JSON.parse(xhr.responseText);
                progressBar.style.width = '100%';
                statusMessage.style.color = 'var(--status-2xx)';
                statusMessage.innerHTML = `✅ Concluído! <strong>${resp.stats.total_lines.toLocaleString()}</strong> linhas processadas em <strong>${resp.stats.elapsed_seconds}s</strong> (${resp.stats.cores_used} núcleos). Redirecionando...`;
                
                setTimeout(() => {
                    window.location.href = resp.redirect || '/dashboard';
                }, 1200);
            } else {
                let err = 'Erro ao processar o arquivo de log.';
                try {
                    const resp = JSON.parse(xhr.responseText);
                    if (resp.error) err = resp.error;
                } catch(e) {}
                statusMessage.style.color = 'var(--status-5xx)';
                statusMessage.innerHTML = `❌ ${err}`;
                submitBtn.disabled = false;
                submitBtn.innerHTML = 'Tentar Novamente';
            }
        };

        xhr.onerror = () => {
            statusMessage.style.color = 'var(--status-5xx)';
            statusMessage.innerHTML = '❌ Ocorreu um erro de rede durante o upload.';
            submitBtn.disabled = false;
            submitBtn.innerHTML = 'Tentar Novamente';
        };

        xhr.send(formData);
    });
});
