const video = document.getElementById('video');
const canvas = document.getElementById('canvas');
const ctx = canvas.getContext('2d');
let stream = null;
let currentFolder = null;
let captureStream = null;
let capturedBlobs = [];

// Selection State
let selectedImages = new Set();
let currentFolderImages = []; 

function getImageUrl(path) {
    if (!path) return '';
    const cleanPath = path.replace(/\\/g, '/');
    if (cleanPath.startsWith('dataset/')) {
        return '/images/' + cleanPath.substring(8);
    }
    if (cleanPath.startsWith('/')) {
        return cleanPath;
    }
    return '/' + cleanPath;
}

// --- Tabs & Navigation ---
document.querySelectorAll('.nav-tab').forEach(tab => {
    tab.addEventListener('click', () => {
        document.querySelectorAll('.nav-tab').forEach(t => t.classList.remove('active'));
        document.querySelectorAll('.view-container').forEach(v => v.classList.remove('active'));
        tab.classList.add('active');
        const viewId = tab.dataset.view + 'View';
        document.getElementById(viewId).classList.add('active');
        if (tab.dataset.view === 'dataset') {
            loadFolders();
        }
    });
});

// --- Camera Logic (Scanner) ---
document.getElementById('startCamera').addEventListener('click', async () => {
    try {
        stream = await navigator.mediaDevices.getUserMedia({
            video: { facingMode: 'environment', width: { ideal: 1280 }, height: { ideal: 720 } }
        });
        video.srcObject = stream;
        document.getElementById('cameraOverlay').classList.add('hidden');
        document.getElementById('startCamera').disabled = true;
        document.getElementById('stopCamera').disabled = false;
        document.getElementById('captureBtn').disabled = false;
    } catch (err) {
        alert('Erro ao acessar camera: ' + err.message);
    }
});

document.getElementById('stopCamera').addEventListener('click', () => {
    if (stream) {
        stream.getTracks().forEach(track => track.stop());
        stream = null;
    }
    video.srcObject = null;
    document.getElementById('cameraOverlay').classList.remove('hidden');
    document.getElementById('startCamera').disabled = false;
    document.getElementById('stopCamera').disabled = true;
    document.getElementById('captureBtn').disabled = true;
});

document.getElementById('captureBtn').addEventListener('click', async () => {
    canvas.width = video.videoWidth;
    canvas.height = video.videoHeight;
    ctx.drawImage(video, 0, 0);
    
    document.getElementById('loading').classList.add('active');
    document.getElementById('resultSection').classList.remove('active');
    document.getElementById('resultPlaceholder').classList.add('hidden');
    
    canvas.toBlob(async (blob) => {
        document.getElementById('capturedImage').src = URL.createObjectURL(blob);
        
        const formData = new FormData();
        formData.append('image', blob, 'capture.jpg');
        
        try {
            const response = await fetch('/scan', { method: 'POST', body: formData });
            const result = await response.json();
            document.getElementById('loading').classList.remove('active');
            renderScanResult(result);
        } catch (err) {
            document.getElementById('loading').classList.remove('active');
            alert('Erro: ' + err.message);
        }
    }, 'image/jpeg', 0.9);
});

function renderScanResult(result) {
    const resultSuccess = document.getElementById('resultSuccess');
    const resultNoMatch = document.getElementById('resultNoMatch');
    const refImage = document.getElementById('referenceImage');
    const noRef = document.getElementById('noReference');
    
    if (result.status === 'no_match') {
        resultSuccess.classList.add('hidden');
        resultNoMatch.classList.remove('hidden');
        document.getElementById('noMatchScore').textContent = result.similarity_score;
        refImage.classList.add('hidden');
        noRef.classList.remove('hidden');
    } else if (result.has_dataset && result.status === 'match') {
        resultSuccess.classList.remove('hidden');
        resultNoMatch.classList.add('hidden');
        document.getElementById('resultClass').textContent = result.classification || 'Desconhecido';
        document.getElementById('resultScore').textContent = result.similarity_score;
        
        if (result.reference_image && result.reference_image.image_path) {
            refImage.src = getImageUrl(result.reference_image.image_path);
            refImage.classList.remove('hidden');
            noRef.classList.add('hidden');
            document.getElementById('refClass').textContent = result.reference_image.classification;
            document.getElementById('refScore').textContent = result.reference_image.similarity;
        } else {
            refImage.classList.add('hidden');
            noRef.classList.remove('hidden');
        }
    } else {
        resultSuccess.classList.remove('hidden');
        resultNoMatch.classList.add('hidden');
        document.getElementById('resultClass').textContent = 'Dataset vazio';
        document.getElementById('resultScore').textContent = '0';
    }
    
     const topMatchesContainer = document.getElementById('topMatches');
    topMatchesContainer.innerHTML = '';
    if (result.top_matches && result.top_matches.length > 0) {
        result.top_matches.forEach((match, index) => {
            const div = document.createElement('div');
            div.className = 'match-item';
            const imgUrl = getImageUrl(match.image_path);
            const shortPath = match.image_path ? match.image_path.split('/').slice(-2).join('/') : '';
            div.innerHTML = `
                <img class="match-thumbnail" src="${imgUrl}" alt="Match ${index + 1}" onerror="this.style.display='none'">
                <div class="match-info">
                    <span class="match-name">${match.classification}</span>
                    <span class="match-path">${shortPath}</span>
                </div>
                <span class="match-score">${match.similarity}%</span>
            `;
            topMatchesContainer.appendChild(div);
        });
    }
    
    document.getElementById('resultSection').classList.add('active');
}

// --- Dataset Logic ---

async function loadFolders() {
    try {
        const response = await fetch('/dataset/classes');
        const data = await response.json();
        
        const grid = document.getElementById('folderGrid');
        const emptyState = document.getElementById('emptyFolders');
        const select = document.getElementById('uploadClass');
        const captureSelect = document.getElementById('captureClass');
        const statsCards = document.getElementById('statsCards');
        
        grid.innerHTML = '';
        select.innerHTML = '';
        if(captureSelect) captureSelect.innerHTML = '';
        
        let totalImages = 0;
        data.classes.forEach(cls => totalImages += cls.image_count);
        
        statsCards.innerHTML = `
            <div class="stat-card">
                <div class="label">Total de Pastas</div>
                <div class="value">${data.classes.length}</div>
            </div>
            <div class="stat-card">
                <div class="label">Total de Imagens</div>
                <div class="value">${totalImages}</div>
            </div>
        `;
        
        if (data.classes.length === 0) {
            emptyState.classList.remove('hidden');
            grid.classList.add('hidden');
        } else {
            emptyState.classList.add('hidden');
            grid.classList.remove('hidden');
            
            data.classes.forEach(cls => {
                const card = document.createElement('div');
                card.className = 'folder-card';
                card.onclick = (e) => {
                     if(!e.target.closest('.folder-action-btn')) {
                         openFolder(cls.name);
                     }
                };
                
                card.innerHTML = `
                    <div class="folder-icon"><i class="fas fa-folder"></i></div>
                    <div class="folder-name">${cls.name}</div>
                    <div class="folder-count"><span>${cls.image_count}</span> imagens</div>
                    <div class="folder-actions">
                        <button class="folder-action-btn" onclick="openRenameModal('${cls.name}')" title="Renomear">
                            <i class="fas fa-edit"></i> Editar
                        </button>
                        <button class="folder-action-btn delete" onclick="openDeleteFolderModal('${cls.name}')" title="Excluir">
                            <i class="fas fa-trash"></i> Excluir
                        </button>
                    </div>
                `;
                grid.appendChild(card);
                
                const option = document.createElement('option');
                option.value = cls.name;
                option.textContent = cls.name;
                select.appendChild(option.cloneNode(true));
                if(captureSelect) captureSelect.appendChild(option.cloneNode(true));
            });
        }
    } catch (err) {
        console.error('Error loading folders:', err);
    }
}

async function openFolder(folderName) {
    currentFolder = folderName;
    document.getElementById('folderListView').classList.add('hidden');
    document.getElementById('folderContentView').classList.remove('hidden');
    document.getElementById('currentFolderName').textContent = folderName;
    document.getElementById('folderTitle').textContent = folderName;
    
    clearSelection();
    
    try {
        const response = await fetch(`/dataset/images/${encodeURIComponent(folderName)}`);
        const data = await response.json();
        
        currentFolderImages = data.images; 
        const grid = document.getElementById('imageGrid');
        const emptyState = document.getElementById('emptyImages');
        
        grid.innerHTML = '';
        
        if (data.images.length === 0) {
            emptyState.classList.remove('hidden');
            grid.classList.add('hidden');
        } else {
            emptyState.classList.add('hidden');
            grid.classList.remove('hidden');
            
            data.images.forEach(img => {
                const card = document.createElement('div');
                card.className = 'image-card';
                card.dataset.id = img.id;
                card.onclick = () => toggleImageSelection(img.id, card);
                
                card.innerHTML = `
                    <div class="image-select-checkbox">
                        <i class="fas fa-check"></i>
                    </div>
                    <img src="${img.path}" alt="${img.filename}" loading="lazy">
                    <div class="image-card-info">
                        <span class="image-card-name">${img.filename}</span>
                    </div>
                `;
                grid.appendChild(card);
            });
        }
    } catch (err) {
        console.error('Error loading folder images:', err);
    }
}

function toggleImageSelection(id, cardElement) {
    if (selectedImages.has(id)) {
        selectedImages.delete(id);
        cardElement.classList.remove('selected');
    } else {
        selectedImages.add(id);
        cardElement.classList.add('selected');
    }
    updateSelectionToolbar();
}

function updateSelectionToolbar() {
    const toolbar = document.getElementById('selectionToolbar');
    const countSpan = document.getElementById('selectionCount');
    const count = selectedImages.size;
    
    if (count > 0) {
        toolbar.classList.add('active');
        countSpan.textContent = `${count} ${count === 1 ? 'item selecionado' : 'itens selecionados'}`;
    } else {
        toolbar.classList.remove('active');
    }
}

function clearSelection() {
    selectedImages.clear();
    document.querySelectorAll('.image-card.selected').forEach(el => el.classList.remove('selected'));
    updateSelectionToolbar();
}

window.toggleSelectAll = function() { 
    const allSelected = selectedImages.size === currentFolderImages.length && currentFolderImages.length > 0;
    
    if (allSelected) {
        clearSelection();
    } else {
        currentFolderImages.forEach(img => selectedImages.add(img.id));
        document.querySelectorAll('.image-card').forEach(el => el.classList.add('selected'));
        updateSelectionToolbar();
    }
};

window.clearSelection = clearSelection;

document.getElementById('deleteSelectedBtn').addEventListener('click', async () => {
    if (selectedImages.size === 0) return;
    
    if (!confirm(`Tem certeza que deseja excluir ${selectedImages.size} imagens?`)) return;
    
    const btn = document.getElementById('deleteSelectedBtn');
    const originalText = btn.innerHTML;
    btn.disabled = true;
    btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Excluindo...';
    
    try {
        const formData = new FormData();
        const idsArray = Array.from(selectedImages);
        formData.append('image_ids', JSON.stringify(idsArray));
        
        const response = await fetch('/dataset/delete-images', { method: 'POST', body: formData });
        
        if (response.ok) {
            openFolder(currentFolder);
        } else {
            const res = await response.json();
            alert('Erro ao excluir: ' + (res.message || res.detail));
        }
    } catch (err) {
        alert('Erro: ' + err.message);
    } finally {
        btn.disabled = false;
        btn.innerHTML = originalText;
    }
});

// --- Rename Folder ---
window.openRenameModal = function(name) {
    document.getElementById('renameOldName').value = name;
    document.getElementById('renameNewName').value = name;
    document.getElementById('renameStatus').textContent = '';
    document.getElementById('renameStatus').className = 'status-message';
    document.getElementById('renameModal').classList.add('active');
};

document.getElementById('closeRenameModal').addEventListener('click', () => {
    document.getElementById('renameModal').classList.remove('active');
});

document.getElementById('renameFolderForm').addEventListener('submit', async (e) => {
    e.preventDefault();
    const oldName = document.getElementById('renameOldName').value;
    const newName = document.getElementById('renameNewName').value.trim();
    const status = document.getElementById('renameStatus');
    
    if (oldName === newName) {
        document.getElementById('renameModal').classList.remove('active');
        return;
    }
    
    try {
        const formData = new FormData();
        formData.append('old_name', oldName);
        formData.append('new_name', newName);
        
        const response = await fetch('/dataset/rename', { method: 'POST', body: formData });
        const result = await response.json();
        
        if (response.ok) {
            status.className = 'status-message success';
            status.textContent = 'Renomeado com sucesso!';
            setTimeout(() => {
                document.getElementById('renameModal').classList.remove('active');
                loadFolders();
            }, 1000);
        } else {
            status.className = 'status-message error';
            status.textContent = result.message || 'Erro ao renomear';
        }
    } catch (err) {
        status.className = 'status-message error';
        status.textContent = 'Erro: ' + err.message;
    }
});

// --- Delete Folder ---
window.openDeleteFolderModal = function(name) {
     document.getElementById('deleteFolderNameDisplay').textContent = name;
     document.getElementById('confirmDeleteFolderBtn').dataset.folder = name;
     document.getElementById('deleteFolderModal').classList.add('active');
};

document.getElementById('closeDeleteFolderModal').addEventListener('click', () => {
     document.getElementById('deleteFolderModal').classList.remove('active');
});

document.getElementById('cancelDeleteFolder').addEventListener('click', () => {
     document.getElementById('deleteFolderModal').classList.remove('active');
});

document.getElementById('confirmDeleteFolderBtn').addEventListener('click', async (e) => {
     const name = e.target.closest('button').dataset.folder;
     const btn = e.target.closest('button');
     
     btn.disabled = true;
     btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Excluindo...';
     
     try {
        const formData = new FormData();
        formData.append('name', name);
        
        const response = await fetch('/dataset/delete', { method: 'POST', body: formData });
        
        if (response.ok) {
            document.getElementById('deleteFolderModal').classList.remove('active');
            loadFolders();
        } else {
            alert('Erro ao excluir pasta');
        }
     } catch (err) {
         alert('Erro: ' + err.message);
     } finally {
         btn.disabled = false;
         btn.innerHTML = '<i class="fas fa-trash"></i> Excluir';
     }
});

document.getElementById('backToFolders').addEventListener('click', () => {
    document.getElementById('folderContentView').classList.add('hidden');
    document.getElementById('folderListView').classList.remove('hidden');
    currentFolder = null;
    loadFolders();
});

document.getElementById('createFolderBtn').addEventListener('click', () => {
    document.getElementById('createFolderModal').classList.add('active');
    document.getElementById('createStatus').className = 'status-message';
});

document.getElementById('closeCreateModal').addEventListener('click', () => {
    document.getElementById('createFolderModal').classList.remove('active');
});

document.getElementById('createFolderForm').addEventListener('submit', async (e) => {
    e.preventDefault();
    const name = document.getElementById('folderName').value.trim();
    const status = document.getElementById('createStatus');
    const submitBtn = e.target.querySelector('button[type="submit"]');
    
    const originalBtnText = submitBtn.innerHTML;
    submitBtn.disabled = true;
    submitBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Criando...';
    
    try {
        const formData = new FormData();
        formData.append('name', name);
        
        const response = await fetch('/dataset/create', { method: 'POST', body: formData });
        const result = await response.json();
        
        if (response.ok) {
            status.className = 'status-message success';
            status.textContent = 'Pasta criada com sucesso!';
            document.getElementById('folderName').value = '';
            loadFolders();
            setTimeout(() => {
                document.getElementById('createFolderModal').classList.remove('active');
                status.className = 'status-message';
                status.textContent = '';
            }, 1500);
        } else {
            status.className = 'status-message error';
            status.textContent = result.detail || 'Erro ao criar pasta';
        }
    } catch (err) {
        status.className = 'status-message error';
        status.textContent = 'Erro: ' + err.message;
    } finally {
        submitBtn.disabled = false;
        submitBtn.innerHTML = originalBtnText;
    }
});

document.getElementById('uploadImagesBtn').addEventListener('click', () => {
    document.getElementById('uploadModal').classList.add('active');
    document.getElementById('uploadStatus').className = 'status-message';
});

document.getElementById('uploadToFolderBtn').addEventListener('click', () => {
    document.getElementById('uploadClass').value = currentFolder;
    document.getElementById('uploadModal').classList.add('active');
    document.getElementById('uploadStatus').className = 'status-message';
});

document.getElementById('closeUploadModal').addEventListener('click', () => {
    document.getElementById('uploadModal').classList.remove('active');
});

document.getElementById('uploadForm').addEventListener('submit', async (e) => {
    e.preventDefault();
    const classification = document.getElementById('uploadClass').value;
    const fileInput = document.getElementById('uploadImages');
    const files = fileInput.files;
    const status = document.getElementById('uploadStatus');
    const submitBtn = e.target.querySelector('button[type="submit"]');
    
    if (files.length === 0) {
        status.className = 'status-message error';
        status.textContent = 'Selecione pelo menos uma imagem';
        return;
    }
    
    const BATCH_SIZE = 10;
    const totalFiles = files.length;
    const totalBatches = Math.ceil(totalFiles / BATCH_SIZE);
    
    const originalBtnText = submitBtn.innerHTML;
    submitBtn.disabled = true;
    
    let successCount = 0;
    
    try {
        for (let i = 0; i < totalBatches; i++) {
            const start = i * BATCH_SIZE;
            const end = Math.min(start + BATCH_SIZE, totalFiles);
            const batchFiles = Array.from(files).slice(start, end);
            
            const formData = new FormData();
            formData.append('classification', classification);
            batchFiles.forEach(file => formData.append('images', file));
            
            submitBtn.innerHTML = `<i class="fas fa-spinner fa-spin"></i> Enviando lote ${i+1}/${totalBatches}...`;
            
            const response = await fetch('/dataset/upload-multiple', { method: 'POST', body: formData });
            
            if (!response.ok) throw new Error(`Falha no lote ${i+1}`);
            successCount += batchFiles.length;
        }
        
        status.className = 'status-message success';
        status.textContent = `${successCount} imagens enviadas com sucesso!`;
        
        setTimeout(() => {
            document.getElementById('uploadModal').classList.remove('active');
            status.className = 'status-message';
            status.textContent = '';
            fileInput.value = '';
            if (currentFolder === classification) {
                 openFolder(currentFolder);
            } else if (!currentFolder) {
                loadFolders();
            }
        }, 1500);
        
    } catch (err) {
        status.className = 'status-message error';
        status.textContent = 'Erro no envio: ' + err.message;
    } finally {
        submitBtn.disabled = false;
        submitBtn.innerHTML = originalBtnText;
    }
});

document.getElementById('captureMultipleBtn').addEventListener('click', () => {
     document.getElementById('captureModal').classList.add('active');
     startCaptureCamera();
});

document.getElementById('closeCaptureModal').addEventListener('click', () => {
     document.getElementById('captureModal').classList.remove('active');
     stopCaptureCamera();
     capturedBlobs = [];
     document.getElementById('captureGrid').innerHTML = '';
     updateCaptureCount();
});

async function startCaptureCamera() {
     const v = document.getElementById('captureVideo');
     try {
        captureStream = await navigator.mediaDevices.getUserMedia({
            video: { facingMode: 'environment' }
        });
        v.srcObject = captureStream;
        document.getElementById('startCaptureCamera').disabled = true;
        document.getElementById('stopCaptureCamera').disabled = false;
        document.getElementById('takeCapturePhoto').disabled = false;
     } catch (err) {
         alert("Erro camera: " + err);
     }
}

function stopCaptureCamera() {
     if (captureStream) {
         captureStream.getTracks().forEach(t => t.stop());
         captureStream = null;
     }
     document.getElementById('captureVideo').srcObject = null;
     document.getElementById('startCaptureCamera').disabled = false;
     document.getElementById('stopCaptureCamera').disabled = true;
     document.getElementById('takeCapturePhoto').disabled = true;
}

document.getElementById('startCaptureCamera').addEventListener('click', startCaptureCamera);
document.getElementById('stopCaptureCamera').addEventListener('click', stopCaptureCamera);

document.getElementById('takeCapturePhoto').addEventListener('click', () => {
     const v = document.getElementById('captureVideo');
     const c = document.createElement('canvas');
     c.width = v.videoWidth;
     c.height = v.videoHeight;
     c.getContext('2d').drawImage(v, 0, 0);
     
     c.toBlob(blob => {
         capturedBlobs.push(blob);
         addCaptureToGrid(blob, capturedBlobs.length - 1);
         updateCaptureCount();
     }, 'image/jpeg');
});

function addCaptureToGrid(blob, index) {
     const url = URL.createObjectURL(blob);
     const div = document.createElement('div');
     div.className = 'capture-thumbnail';
     div.dataset.index = index;
     div.innerHTML = `
        <img src="${url}">
        <button class="remove-btn" onclick="removeCapture(${index})">&times;</button>
     `;
     document.getElementById('captureGrid').appendChild(div);
}

window.removeCapture = function(index) {
     capturedBlobs.splice(index, 1);
     const grid = document.getElementById('captureGrid');
     grid.innerHTML = '';
     capturedBlobs.forEach((b, i) => addCaptureToGrid(b, i));
     updateCaptureCount();
}

function updateCaptureCount() {
     const count = capturedBlobs.length;
     document.getElementById('captureCount').textContent = `${count} fotos capturadas`;
     document.getElementById('sendAllCaptures').disabled = count === 0;
}

document.getElementById('sendAllCaptures').addEventListener('click', async () => {
     const cls = document.getElementById('captureClass').value;
     if (!cls) { alert("Selecione uma pasta"); return; }
     
     const btn = document.getElementById('sendAllCaptures');
     btn.disabled = true;
     btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Enviando...';
     
     try {
         const formData = new FormData();
         formData.append('classification', cls);
         capturedBlobs.forEach(b => formData.append('images', b, 'capture.jpg'));
         
         const res = await fetch('/dataset/capture-multiple', { method: 'POST', body: formData });
         
         if (res.ok) {
             alert("Enviado com sucesso!");
             document.getElementById('captureModal').classList.remove('active');
             stopCaptureCamera();
             capturedBlobs = [];
             loadFolders();
         } else {
             alert("Erro ao enviar");
         }
     } catch (e) {
         alert("Erro: " + e);
     } finally {
         btn.disabled = false;
         btn.innerHTML = '<i class="fas fa-upload"></i> Enviar Todas as Fotos';
     }
});

document.getElementById('retrainBtn').addEventListener('click', async () => {
    const btn = document.getElementById('retrainBtn');
    btn.disabled = true;
    btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Retreinando...';
    
    try {
        const response = await fetch('/dataset/retrain', { method: 'POST' });
        const result = await response.json();
        alert(result.message || 'Embeddings atualizados!');
    } catch (err) {
        alert('Erro: ' + err.message);
    } finally {
        btn.disabled = false;
        btn.innerHTML = '<i class="fas fa-sync-alt"></i> Retreinar';
    }
});

document.querySelectorAll('.modal-overlay').forEach(modal => {
    modal.addEventListener('click', (e) => {
        if (e.target === modal) {
            modal.classList.remove('active');
        }
    });
});
document.querySelectorAll('.modal').forEach(modal => {
    modal.addEventListener('click', e => e.stopPropagation());
});

document.getElementById('createCategoryBtn').addEventListener('click', () => {
    document.querySelectorAll('.nav-tab').forEach(t => t.classList.remove('active'));
    document.querySelectorAll('.view-container').forEach(v => v.classList.remove('active'));
    document.querySelector('[data-view="dataset"]').classList.add('active');
    document.getElementById('datasetView').classList.add('active');
    loadFolders();
    document.getElementById('createFolderModal').classList.add('active');
});

document.getElementById('addPhotosBtn').addEventListener('click', () => {
    document.querySelectorAll('.nav-tab').forEach(t => t.classList.remove('active'));
    document.querySelectorAll('.view-container').forEach(v => v.classList.remove('active'));
    document.querySelector('[data-view="dataset"]').classList.add('active');
    document.getElementById('datasetView').classList.add('active');
    loadFolders();
    setTimeout(() => {
        document.getElementById('uploadModal').classList.add('active');
    }, 300);
});

// Initial load
loadFolders();
