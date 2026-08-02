/**
 * Photo & PDF to Excel Converter App.
 * Handles file upload, interactive page crop preview, auto/manual crop,
 * OCR extraction, and spreadsheet grid editor.
 */

document.addEventListener('DOMContentLoaded', () => {
    const spreadsheetEditor = new SpreadsheetEditorController(
        'sectionTabsBar',
        'tableHead',
        'tableBody'
    );

    // Current File State
    let currentUploadedData = null;
    let originalImgWidth = 1204;
    let originalImgHeight = 1600;
    let currentCropRect = null; // { x, y, width, height } in original image pixels
    let isAutoCropped = false;

    // Elements
    const dropZone = document.getElementById('dropZone');
    const fileInput = document.getElementById('fileInput');
    const filePreviewBar = document.getElementById('filePreviewBar');
    const lblFileName = document.getElementById('lblFileName');
    const lblFileMeta = document.getElementById('lblFileMeta');
    const btnChangeFile = document.getElementById('btnChangeFile');

    const cropControlStrip = document.getElementById('cropControlStrip');
    const btnAutoCrop = document.getElementById('btnAutoCrop');
    const btnManualCrop = document.getElementById('btnManualCrop');
    const btnClearCrop = document.getElementById('btnClearCrop');

    const pageCropPreviewCard = document.getElementById('pageCropPreviewCard');
    const cropBadge = document.getElementById('cropBadge');
    const cropStage = document.getElementById('cropStage');
    const previewImage = document.getElementById('previewImage');
    const cropBox = document.getElementById('cropBox');

    const btnConvert = document.getElementById('btnConvert');
    const resultCard = document.getElementById('resultCard');

    const btnExportExcel = document.getElementById('btnExportExcel');
    const btnExportCsv = document.getElementById('btnExportCsv');

    const btnAddRow = document.getElementById('btnAddRow');
    const btnAddCol = document.getElementById('btnAddCol');
    const btnClearGrid = document.getElementById('btnClearGrid');

    const loadingOverlay = document.getElementById('loadingOverlay');
    const loadingTitle = document.getElementById('loadingTitle');
    const loadingMessage = document.getElementById('loadingMessage');

    // ------------------------------------------------------------------
    // 1. File Upload & Setup
    // ------------------------------------------------------------------
    async function uploadFile(file) {
        if (!file) return;

        showLoading('Uploading & Preparing File...', 'Processing document format...');

        const formData = new FormData();
        formData.append('file', file);

        try {
            const res = await fetch('/api/upload', {
                method: 'POST',
                body: formData
            });

            const data = await res.json();
            hideLoading();

            if (data.status === 'success') {
                currentUploadedData = data;
                originalImgWidth = data.width || 1200;
                originalImgHeight = data.height || 1600;

                // Update UI elements
                dropZone.style.display = 'none';
                filePreviewBar.style.display = 'flex';
                cropControlStrip.style.display = 'flex';
                pageCropPreviewCard.style.display = 'block';

                lblFileName.innerText = data.filename;
                const fileExt = data.filename.split('.').pop().toUpperCase();
                lblFileMeta.innerText = `${fileExt} File • ${data.total_pages} Page(s) • (${originalImgWidth}×${originalImgHeight}px)`;

                const setupImageAndCrop = () => {
                    initCropOverlay();
                    triggerAutoCrop();
                };

                previewImage.onload = () => {
                    setTimeout(setupImageAndCrop, 100);
                };

                previewImage.src = data.image_b64;
                btnConvert.disabled = false;

                if (previewImage.complete && previewImage.naturalWidth > 0) {
                    setTimeout(setupImageAndCrop, 100);
                }
            } else {
                alert(`Upload Error: ${data.detail}`);
            }
        } catch (err) {
            hideLoading();
            alert(`Failed to upload file: ${err.message}`);
        }
    }

    fileInput.addEventListener('change', (e) => {
        if (e.target.files.length > 0) {
            uploadFile(e.target.files[0]);
        }
    });

    btnChangeFile.addEventListener('click', () => {
        currentUploadedData = null;
        fileInput.value = '';
        filePreviewBar.style.display = 'none';
        cropControlStrip.style.display = 'none';
        pageCropPreviewCard.style.display = 'none';
        dropZone.style.display = 'block';
        btnConvert.disabled = true;
        resultCard.style.display = 'none';
    });

    ['dragenter', 'dragover'].forEach(name => {
        dropZone.addEventListener(name, (e) => {
            e.preventDefault();
            dropZone.classList.add('drag-over');
        });
    });

    ['dragleave', 'drop'].forEach(name => {
        dropZone.addEventListener(name, (e) => {
            e.preventDefault();
            dropZone.classList.remove('drag-over');
        });
    });

    dropZone.addEventListener('drop', (e) => {
        if (e.dataTransfer.files.length > 0) {
            uploadFile(e.dataTransfer.files[0]);
        }
    });

    // ------------------------------------------------------------------
    // 2. Interactive Crop Overlay Engine
    // ------------------------------------------------------------------
    let stageRect = { width: 1, height: 1 };
    let cropPos = { left: 0, top: 0, width: 0, height: 0 }; // in CSS pixels relative to stage
    let isDragging = false;
    let isResizing = false;
    let currentHandle = null;
    let startMousePos = { x: 0, y: 0 };
    let startCropPos = { left: 0, top: 0, width: 0, height: 0 };

    function initCropOverlay() {
        stageRect = cropStage.getBoundingClientRect();
        
        // Default crop box to middle 75% region or full image
        const defaultW = stageRect.width * 0.85;
        const defaultH = stageRect.height * 0.25;
        const defaultL = (stageRect.width - defaultW) / 2;
        const defaultT = (stageRect.height - defaultH) / 3;

        setCropPosPx(defaultL, defaultT, defaultW, defaultH);
    }

    function setCropPosPx(left, top, width, height) {
        stageRect = cropStage.getBoundingClientRect();
        if (stageRect.width === 0 || stageRect.height === 0) return;

        // Constrain bounds within stage
        left = Math.max(0, Math.min(left, stageRect.width - 20));
        top = Math.max(0, Math.min(top, stageRect.height - 20));
        width = Math.max(20, Math.min(width, stageRect.width - left));
        height = Math.max(20, Math.min(height, stageRect.height - top));

        cropPos = { left, top, width, height };

        cropBox.style.left = `${left}px`;
        cropBox.style.top = `${top}px`;
        cropBox.style.width = `${width}px`;
        cropBox.style.height = `${height}px`;

        // Calculate mapped pixel coordinates on original image
        const scaleX = originalImgWidth / stageRect.width;
        const scaleY = originalImgHeight / stageRect.height;

        const origX = Math.round(left * scaleX);
        const origY = Math.round(top * scaleY);
        const origW = Math.round(width * scaleX);
        const origH = Math.round(height * scaleY);

        currentCropRect = { x: origX, y: origY, width: origW, height: origH };

        const modePrefix = isAutoCropped ? 'Auto crop:' : 'Manual crop:';
        cropBadge.innerText = `${modePrefix} ${origW} × ${origH}`;
    }

    // Drag & Resize Event Listeners
    cropBox.addEventListener('mousedown', (e) => {
        if (e.target.classList.contains('crop-handle')) {
            isResizing = true;
            currentHandle = e.target.getAttribute('data-handle');
        } else {
            isDragging = true;
        }

        isAutoCropped = false;
        setActiveCropButton(btnManualCrop);

        startMousePos = { x: e.clientX, y: e.clientY };
        startCropPos = { ...cropPos };
        e.stopPropagation();
        e.preventDefault();
    });

    document.addEventListener('mousemove', (e) => {
        if (!isDragging && !isResizing) return;

        const dx = e.clientX - startMousePos.x;
        const dy = e.clientY - startMousePos.y;

        if (isDragging) {
            setCropPosPx(
                startCropPos.left + dx,
                startCropPos.top + dy,
                startCropPos.width,
                startCropPos.height
            );
        } else if (isResizing && currentHandle) {
            let nL = startCropPos.left;
            let nT = startCropPos.top;
            let nW = startCropPos.width;
            let nH = startCropPos.height;

            if (currentHandle.includes('e')) nW = startCropPos.width + dx;
            if (currentHandle.includes('s')) nH = startCropPos.height + dy;
            if (currentHandle.includes('w')) {
                nW = startCropPos.width - dx;
                nL = startCropPos.left + dx;
            }
            if (currentHandle.includes('n')) {
                nH = startCropPos.height - dy;
                nT = startCropPos.top + dy;
            }

            setCropPosPx(nL, nT, nW, nH);
        }
    });

    document.addEventListener('mouseup', () => {
        isDragging = false;
        isResizing = false;
        currentHandle = null;
    });

    // Touch Support for mobile / touch devices
    cropBox.addEventListener('touchstart', (e) => {
        if (e.touches.length !== 1) return;
        const touch = e.touches[0];
        if (e.target.classList.contains('crop-handle')) {
            isResizing = true;
            currentHandle = e.target.getAttribute('data-handle');
        } else {
            isDragging = true;
        }

        isAutoCropped = false;
        setActiveCropButton(btnManualCrop);

        startMousePos = { x: touch.clientX, y: touch.clientY };
        startCropPos = { ...cropPos };
        e.stopPropagation();
    });

    document.addEventListener('touchmove', (e) => {
        if (!isDragging && !isResizing) return;
        if (e.touches.length !== 1) return;
        const touch = e.touches[0];

        const dx = touch.clientX - startMousePos.x;
        const dy = touch.clientY - startMousePos.y;

        if (isDragging) {
            setCropPosPx(
                startCropPos.left + dx,
                startCropPos.top + dy,
                startCropPos.width,
                startCropPos.height
            );
        } else if (isResizing && currentHandle) {
            let nL = startCropPos.left;
            let nT = startCropPos.top;
            let nW = startCropPos.width;
            let nH = startCropPos.height;

            if (currentHandle.includes('e')) nW = startCropPos.width + dx;
            if (currentHandle.includes('s')) nH = startCropPos.height + dy;
            if (currentHandle.includes('w')) {
                nW = startCropPos.width - dx;
                nL = startCropPos.left + dx;
            }
            if (currentHandle.includes('n')) {
                nH = startCropPos.height - dy;
                nT = startCropPos.top + dy;
            }

            setCropPosPx(nL, nT, nW, nH);
        }
    });

    document.addEventListener('touchend', () => {
        isDragging = false;
        isResizing = false;
        currentHandle = null;
    });

    window.addEventListener('resize', () => {
        if (currentUploadedData && currentCropRect) {
            stageRect = cropStage.getBoundingClientRect();
            const scaleX = stageRect.width / originalImgWidth;
            const scaleY = stageRect.height / originalImgHeight;
            setCropPosPx(
                currentCropRect.x * scaleX,
                currentCropRect.y * scaleY,
                currentCropRect.width * scaleX,
                currentCropRect.height * scaleY
            );
        }
    });

    // ------------------------------------------------------------------
    // 3. Crop Controls (Auto Crop, Manual Crop, Clear Crop)
    // ------------------------------------------------------------------
    function setActiveCropButton(activeBtn) {
        [btnAutoCrop, btnManualCrop, btnClearCrop].forEach(btn => btn.classList.remove('active'));
        if (activeBtn) activeBtn.classList.add('active');
    }

    async function triggerAutoCrop() {
        if (!currentUploadedData || !currentUploadedData.image_b64) return;

        setActiveCropButton(btnAutoCrop);

        try {
            const res = await fetch('/api/autocrop', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ image_b64: currentUploadedData.image_b64 })
            });

            const data = await res.json();
            if (data.status === 'success' && data.crop) {
                isAutoCropped = true;
                const crop = data.crop;
                stageRect = cropStage.getBoundingClientRect();
                const scaleX = stageRect.width / originalImgWidth;
                const scaleY = stageRect.height / originalImgHeight;

                setCropPosPx(
                    crop.x * scaleX,
                    crop.y * scaleY,
                    crop.width * scaleX,
                    crop.height * scaleY
                );
            }
        } catch (err) {
            console.warn("Auto crop request failed, using manual crop box.", err);
        }
    }

    btnAutoCrop.addEventListener('click', () => {
        triggerAutoCrop();
    });

    btnManualCrop.addEventListener('click', () => {
        isAutoCropped = false;
        setActiveCropButton(btnManualCrop);
        if (currentCropRect) {
            cropBadge.innerText = `Manual crop: ${currentCropRect.width} × ${currentCropRect.height}`;
        }
    });

    btnClearCrop.addEventListener('click', () => {
        isAutoCropped = false;
        setActiveCropButton(btnClearCrop);
        stageRect = cropStage.getBoundingClientRect();
        setCropPosPx(0, 0, stageRect.width, stageRect.height);
        cropBadge.innerText = `Full page: ${originalImgWidth} × ${originalImgHeight}`;
    });

    // Engine Radio Selection Interactivity
    const engineRadioCards = document.querySelectorAll('.engine-radio-card');
    engineRadioCards.forEach(card => {
        card.addEventListener('click', () => {
            engineRadioCards.forEach(c => c.classList.remove('active'));
            card.classList.add('active');
            const radio = card.querySelector('input[type="radio"]');
            if (radio) radio.checked = true;
        });
    });

    function getSelectedEngine() {
        const checkedRadio = document.querySelector('input[name="engineSelect"]:checked');
        return checkedRadio ? checkedRadio.value : 'local';
    }

    function renderBenchmarkMetrics(bench) {
        const benchmarkCard = document.getElementById('benchmarkCard');
        const tableBody = document.getElementById('benchmarkTableBody');
        if (!bench || !benchmarkCard || !tableBody) return;

        const loc = bench.local_engine || {};
        const gem = bench.gemini_engine || {};

        tableBody.innerHTML = `
            <tr>
                <td><strong>Model Architecture</strong></td>
                <td>${loc.name || 'PyTorch CNN (99.55% Acc)'}</td>
                <td>${gem.name || 'Gemini Multimodal Vision API'}</td>
            </tr>
            <tr>
                <td><strong>Inference Latency</strong></td>
                <td><strong style="color:#059669;">${loc.latency_ms || 0} ms</strong> (Fast local CPU)</td>
                <td><strong style="color:#0284C7;">${gem.latency_ms || 0} ms</strong> (Cloud Network)</td>
            </tr>
            <tr>
                <td><strong>Offline Capability</strong></td>
                <td><span style="color:#059669; font-weight:bold;">✔ 100% Offline Capable</span></td>
                <td><span style="color:#EF4444; font-weight:bold;">✖ Requires Internet API</span></td>
            </tr>
            <tr>
                <td><strong>Data Privacy & Security</strong></td>
                <td>${loc.privacy || '100% On-Device'}</td>
                <td>${gem.privacy || 'Sent to Cloud API'}</td>
            </tr>
            <tr>
                <td><strong>Operational Cost</strong></td>
                <td><span style="color:#059669; font-weight:bold;">Free ($0.00)</span></td>
                <td>${gem.cost || 'API Quota/Billing'}</td>
            </tr>
        `;

        benchmarkCard.style.display = 'block';
    }

    // ------------------------------------------------------------------
    // 4. Extraction & Conversion Action
    // ------------------------------------------------------------------
    btnConvert.addEventListener('click', async () => {
        if (!currentUploadedData) {
            alert('Please select a file first.');
            return;
        }

        const selectedEngine = getSelectedEngine();

        showLoading(
            'Extracting Numbers & Tables',
            selectedEngine === 'comparative' 
                ? 'Running side-by-side benchmark: PyTorch Local CNN vs Gemini Cloud AI...'
                : `Executing extraction using [${selectedEngine.toUpperCase()}] Engine...`
        );

        const payload = {
            file_b64_list: currentUploadedData.pages_b64 || [currentUploadedData.image_b64],
            engine: selectedEngine
        };

        // Attach ROI crop coordinates if active
        if (currentCropRect && currentCropRect.width > 20 && currentCropRect.height > 20) {
            payload.roi = currentCropRect;
        }

        try {
            const res = await fetch('/api/extract', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });

            const data = await res.json();
            hideLoading();

            if (data.status === 'success') {
                const sections = data.sections || [];
                spreadsheetEditor.setSections(sections);

                const benchmarkCard = document.getElementById('benchmarkCard');
                if (data.comparative_benchmark) {
                    renderBenchmarkMetrics(data.comparative_benchmark);
                } else if (benchmarkCard) {
                    benchmarkCard.style.display = 'none';
                }

                // Unhide Results Card and scroll to view
                resultCard.style.display = 'block';
                resultCard.scrollIntoView({ behavior: 'smooth' });
            } else {
                alert(`Extraction error: ${data.detail}`);
            }
        } catch (err) {
            hideLoading();
            alert(`Extraction error: ${err.message}`);
        }
    });

    // ------------------------------------------------------------------
    // 5. Grid Editing Toolbar Controls
    // ------------------------------------------------------------------
    btnAddRow.addEventListener('click', () => spreadsheetEditor.addRow());
    btnAddCol.addEventListener('click', () => spreadsheetEditor.addColumn());
    btnClearGrid.addEventListener('click', () => {
        if (confirm('Clear current spreadsheet grid?')) {
            spreadsheetEditor.clearGrid();
        }
    });

    // ------------------------------------------------------------------
    // 6. Export Excel & CSV File Downloads
    // ------------------------------------------------------------------
    btnExportExcel.addEventListener('click', async () => {
        const sections = spreadsheetEditor.getSections();
        if (!sections || sections.length === 0) return;

        showLoading('Generating Excel File', 'Formatting worksheets & auto-fitting columns...');

        try {
            const res = await fetch('/api/export/excel', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ sections: sections })
            });

            if (res.ok) {
                const blob = await res.blob();
                const url = window.URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.href = url;
                a.download = 'extracted_table_numbers.xlsx';
                document.body.appendChild(a);
                a.click();
                a.remove();
                window.URL.revokeObjectURL(url);
            } else {
                alert('Failed to download Excel file.');
            }
        } catch (err) {
            alert(`Export error: ${err.message}`);
        } finally {
            hideLoading();
        }
    });

    btnExportCsv.addEventListener('click', async () => {
        const sections = spreadsheetEditor.getSections();
        if (!sections || sections.length === 0) return;

        showLoading('Generating CSV File', 'Creating clean CSV...');

        try {
            const res = await fetch('/api/export/csv', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ sections: sections })
            });

            if (res.ok) {
                const blob = await res.blob();
                const url = window.URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.href = url;
                a.download = 'extracted_table_numbers.csv';
                document.body.appendChild(a);
                a.click();
                a.remove();
                window.URL.revokeObjectURL(url);
            } else {
                alert('Failed to download CSV file.');
            }
        } catch (err) {
            alert(`Export error: ${err.message}`);
        } finally {
            hideLoading();
        }
    });

    function showLoading(title, msg) {
        loadingTitle.innerText = title;
        loadingMessage.innerText = msg;
        loadingOverlay.style.display = 'flex';
    }

    function hideLoading() {
        loadingOverlay.style.display = 'none';
    }
});
