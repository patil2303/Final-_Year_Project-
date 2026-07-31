/**
 * Universal Photo & PDF to Excel Converter App.
 * Simple: Upload file -> Convert -> Download Excel/CSV.
 * All OCR modes (digit-only, handwritten) are automatic and built-in.
 */

document.addEventListener('DOMContentLoaded', () => {
    const spreadsheetEditor = new SpreadsheetEditorController(
        'sectionTabsBar',
        'tableHead',
        'tableBody'
    );

    // Current State
    let currentUploadedData = null;

    // Elements
    const dropZone = document.getElementById('dropZone');
    const fileInput = document.getElementById('fileInput');
    const filePreviewBar = document.getElementById('filePreviewBar');
    const lblFileName = document.getElementById('lblFileName');
    const lblFileMeta = document.getElementById('lblFileMeta');
    const btnChangeFile = document.getElementById('btnChangeFile');

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

    // 1. Universal File Upload Handler
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
                
                // Show File Preview Bar
                dropZone.style.display = 'none';
                filePreviewBar.style.display = 'flex';
                lblFileName.innerText = data.filename;

                const fileExt = data.filename.split('.').pop().toUpperCase();
                lblFileMeta.innerText = `${fileExt} File • ${data.total_pages} Page(s) • (${data.width}x${data.height}px)`;

                btnConvert.disabled = false;
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

    // 2. Conversion Action Handler (fully automatic — no mode toggles)
    btnConvert.addEventListener('click', async () => {
        if (!currentUploadedData) {
            alert('Please select a file first.');
            return;
        }

        showLoading(
            'Extracting Numbers & Tables',
            'Running multi-pass OCR with grid detection and gap-filling...'
        );

        try {
            const res = await fetch('/api/extract', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    file_b64_list: currentUploadedData.pages_b64 || [currentUploadedData.image_b64]
                })
            });

            const data = await res.json();
            hideLoading();

            if (data.status === 'success') {
                const sections = data.sections || [];
                spreadsheetEditor.setSections(sections);

                // Unhide Results Card
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

    // 3. Grid Tools
    btnAddRow.addEventListener('click', () => spreadsheetEditor.addRow());
    btnAddCol.addEventListener('click', () => spreadsheetEditor.addColumn());
    btnClearGrid.addEventListener('click', () => {
        if (confirm('Clear current spreadsheet grid?')) {
            spreadsheetEditor.clearGrid();
        }
    });

    // 4. Export Download Actions
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
