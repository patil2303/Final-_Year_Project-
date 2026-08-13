/**
 * Academic Exam Marksheet & Grade Portal App.
 * Handles Dual Portal (Student Upload & Faculty Dashboard),
 * MongoDB Classroom Management, AI Number Extraction, and Master Grade Sheet Export.
 */

document.addEventListener('DOMContentLoaded', () => {
    const spreadsheetEditor = new SpreadsheetEditorController(
        'sectionTabsBar',
        'tableHead',
        'tableBody'
    );

    // Current File & State
    let currentUploadedData = null;
    let originalImgWidth = 1204;
    let originalImgHeight = 1600;
    let currentCropRect = null;
    let isAutoCropped = false;
    let activeClassroomsList = [];
    let currentRosterData = [];

    // Navigation Tabs
    const tabStudentPortal = document.getElementById('tabStudentPortal');
    const tabFacultyPortal = document.getElementById('tabFacultyPortal');
    const studentPortalView = document.getElementById('studentPortalView');
    const facultyPortalView = document.getElementById('facultyPortalView');

    // Student View Elements
    const studentClassroomSelect = document.getElementById('studentClassroomSelect');
    const dropZone = document.getElementById('dropZone');
    const fileInput = document.getElementById('fileInput');
    const cameraInput = document.getElementById('cameraInput');
    const btnSnapCamera = document.getElementById('btnSnapCamera');
    const btnChooseFile = document.getElementById('btnChooseFile');
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

    const btnSubmitToDb = document.getElementById('btnSubmitToDb');
    const btnExportExcel = document.getElementById('btnExportExcel');
    const btnExportCsv = document.getElementById('btnExportCsv');

    const btnAddRow = document.getElementById('btnAddRow');
    const btnAddCol = document.getElementById('btnAddCol');
    const btnClearGrid = document.getElementById('btnClearGrid');

    // Faculty View Elements
    const facultyClassroomSelect = document.getElementById('facultyClassroomSelect');
    const btnOpenCreateClassModal = document.getElementById('btnOpenCreateClassModal');
    const btnRefreshFacultyRoster = document.getElementById('btnRefreshFacultyRoster');
    const btnFacultyExportExcel = document.getElementById('btnFacultyExportExcel');
    const btnFacultyExportCsv = document.getElementById('btnFacultyExportCsv');

    const statTotalSubmissions = document.getElementById('statTotalSubmissions');
    const statClassAverage = document.getElementById('statClassAverage');
    const statHighestScore = document.getElementById('statHighestScore');
    const statTopStudent = document.getElementById('statTopStudent');
    const statLatestTime = document.getElementById('statLatestTime');
    const statLatestStudent = document.getElementById('statLatestStudent');

    const facultyRosterSearch = document.getElementById('facultyRosterSearch');
    const facultyRosterTableBody = document.getElementById('facultyRosterTableBody');
    const rosterEmptyState = document.getElementById('rosterEmptyState');

    // Modal & Toast Elements
    const createClassModal = document.getElementById('createClassModal');
    const btnCloseCreateClassModal = document.getElementById('btnCloseCreateClassModal');
    const btnCancelCreateClass = document.getElementById('btnCancelCreateClass');
    const createClassForm = document.getElementById('createClassForm');
    const toastNotification = document.getElementById('toastNotification');
    const toastTitle = document.getElementById('toastTitle');
    const toastMessage = document.getElementById('toastMessage');

    const loadingOverlay = document.getElementById('loadingOverlay');
    const loadingTitle = document.getElementById('loadingTitle');
    const loadingMessage = document.getElementById('loadingMessage');

    // ------------------------------------------------------------------
    // 1. Dual Portal Mode Switcher
    // ------------------------------------------------------------------
    function switchPortal(portal) {
        if (portal === 'student') {
            tabStudentPortal.classList.add('active');
            tabFacultyPortal.classList.remove('active');
            studentPortalView.style.display = 'block';
            facultyPortalView.style.display = 'none';
        } else {
            tabFacultyPortal.classList.add('active');
            tabStudentPortal.classList.remove('active');
            studentPortalView.style.display = 'none';
            facultyPortalView.style.display = 'block';
            loadFacultyRoster();
        }
    }

    tabStudentPortal.addEventListener('click', () => switchPortal('student'));
    tabFacultyPortal.addEventListener('click', () => switchPortal('faculty'));

    // ------------------------------------------------------------------
    // 2. Classroom Management (MongoDB Synced)
    // ------------------------------------------------------------------
    async function loadClassrooms(selectedIdToSet = null) {
        try {
            const res = await fetch('/api/classrooms');
            const data = await res.json();

            if (data.status === 'success' && data.classrooms) {
                activeClassroomsList = data.classrooms;
            } else {
                activeClassroomsList = [];
            }

            populateClassroomDropdowns(selectedIdToSet);
        } catch (err) {
            console.error('Failed to load classrooms from MongoDB:', err);
        }
    }

    function populateClassroomDropdowns(selectedId = null) {
        if (!activeClassroomsList || activeClassroomsList.length === 0) {
            const studentEmptyOpt = '<option value="">-- No Active Classes (Please wait for faculty) --</option>';
            const facultyEmptyOpt = '<option value="">-- No Classes Created Yet (Click "+ Create New Class / Exam" above) --</option>';
            if (studentClassroomSelect) studentClassroomSelect.innerHTML = studentEmptyOpt;
            if (facultyClassroomSelect) facultyClassroomSelect.innerHTML = facultyEmptyOpt;
            return;
        }

        const studentOpts = [];
        const facultyOpts = [];

        activeClassroomsList.forEach(cls => {
            const label = `${cls.year} ${cls.branch} (Div ${cls.division}) • ${cls.subject} (Sem ${cls.semester}) • ${cls.exam_name || 'IA-1'}`;
            studentOpts.push(`<option value="${cls.classroom_id}">${label}</option>`);
            facultyOpts.push(`<option value="${cls.classroom_id}">${label}</option>`);
        });

        if (studentClassroomSelect) studentClassroomSelect.innerHTML = studentOpts.join('');
        if (facultyClassroomSelect) facultyClassroomSelect.innerHTML = facultyOpts.join('');

        if (selectedId) {
            if (studentClassroomSelect) studentClassroomSelect.value = selectedId;
            if (facultyClassroomSelect) facultyClassroomSelect.value = selectedId;
        }
    }

    // Modal Open/Close Controls (Faculty Only)
    function openCreateClassModal() {
        createClassModal.style.display = 'flex';
    }

    function closeCreateClassModal() {
        createClassModal.style.display = 'none';
        createClassForm.reset();
    }

    if (btnOpenCreateClassModal) btnOpenCreateClassModal.addEventListener('click', openCreateClassModal);
    if (btnCloseCreateClassModal) btnCloseCreateClassModal.addEventListener('click', closeCreateClassModal);
    if (btnCancelCreateClass) btnCancelCreateClass.addEventListener('click', closeCreateClassModal);

    createClassForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        const year = document.getElementById('newClassYear').value.trim();
        const branch = document.getElementById('newClassBranch').value.trim();
        const division = document.getElementById('newClassDivision').value.trim();
        const semester = document.getElementById('newClassSemester').value.trim();
        const subject = document.getElementById('newClassSubject').value.trim();
        const examName = document.getElementById('newClassExam').value.trim();

        showLoading('Registering Classroom...', 'Saving new batch to MongoDB Atlas...');

        try {
            const res = await fetch('/api/classrooms', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    year: year,
                    branch: branch,
                    division: division,
                    semester: semester,
                    subject: subject,
                    exam_name: examName
                })
            });

            const data = await res.json();
            hideLoading();

            if (data.status === 'success') {
                closeCreateClassModal();
                showToast('Classroom Created!', `${year} ${branch} (${subject}) registered in MongoDB.`);
                await loadClassrooms(data.classroom.classroom_id);
                if (facultyPortalView.style.display !== 'none') {
                    loadFacultyRoster();
                }
            } else {
                alert(`Error creating classroom: ${data.detail}`);
            }
        } catch (err) {
            hideLoading();
            alert(`Failed to create classroom: ${err.message}`);
        }
    });

    // ------------------------------------------------------------------
    // 3. File Upload & Setup (Mobile Camera & Desktop)
    // ------------------------------------------------------------------
    let stageRect = { width: 1, height: 1 };
    let cropPos = { left: 0, top: 0, width: 0, height: 0 };
    let isDragging = false;
    let isResizing = false;
    let currentHandle = null;
    let startMousePos = { x: 0, y: 0 };
    let startCropPos = { left: 0, top: 0, width: 0, height: 0 };

    function initCropOverlay() {
        if (!cropStage) return;
        stageRect = cropStage.getBoundingClientRect();
        const defaultW = stageRect.width * 0.85;
        const defaultH = stageRect.height * 0.25;
        const defaultL = (stageRect.width - defaultW) / 2;
        const defaultT = (stageRect.height - defaultH) / 3;
        setCropPosPx(defaultL, defaultT, defaultW, defaultH);
    }

    function setCropPosPx(left, top, width, height) {
        if (!cropStage || !cropBox) return;
        stageRect = cropStage.getBoundingClientRect();
        if (stageRect.width === 0 || stageRect.height === 0) return;

        left = Math.max(0, Math.min(left, stageRect.width - 20));
        top = Math.max(0, Math.min(top, stageRect.height - 20));
        width = Math.max(20, Math.min(width, stageRect.width - left));
        height = Math.max(20, Math.min(height, stageRect.height - top));

        cropPos = { left, top, width, height };

        cropBox.style.left = `${left}px`;
        cropBox.style.top = `${top}px`;
        cropBox.style.width = `${width}px`;
        cropBox.style.height = `${height}px`;

        const scaleX = originalImgWidth / stageRect.width;
        const scaleY = originalImgHeight / stageRect.height;

        const origX = Math.round(left * scaleX);
        const origY = Math.round(top * scaleY);
        const origW = Math.round(width * scaleX);
        const origH = Math.round(height * scaleY);

        currentCropRect = { x: origX, y: origY, width: origW, height: origH };

        if (cropBadge) {
            const modePrefix = isAutoCropped ? 'Auto crop:' : 'Manual crop:';
            cropBadge.innerText = `${modePrefix} ${origW} × ${origH}`;
        }
    }

    function setActiveCropButton(activeBtn) {
        [btnAutoCrop, btnManualCrop, btnClearCrop].forEach(btn => {
            if (btn) btn.classList.remove('active');
        });
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

    if (btnAutoCrop) {
        btnAutoCrop.addEventListener('click', () => triggerAutoCrop());
    }

    if (btnManualCrop) {
        btnManualCrop.addEventListener('click', () => {
            isAutoCropped = false;
            setActiveCropButton(btnManualCrop);
            if (currentCropRect && cropBadge) {
                cropBadge.innerText = `Manual crop: ${currentCropRect.width} × ${currentCropRect.height}`;
            }
        });
    }

    if (btnClearCrop) {
        btnClearCrop.addEventListener('click', () => {
            isAutoCropped = false;
            setActiveCropButton(btnClearCrop);
            if (cropStage) {
                stageRect = cropStage.getBoundingClientRect();
                setCropPosPx(0, 0, stageRect.width, stageRect.height);
                if (cropBadge) cropBadge.innerText = `Full page: ${originalImgWidth} × ${originalImgHeight}`;
            }
        });
    }

    // Crop box mouse drag & resize listeners
    if (cropBox) {
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

        // Touch support
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
    }

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
        if (currentUploadedData && currentCropRect && cropStage) {
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

    function compressImageForUpload(file, maxDimension = 1600, quality = 0.85) {
        return new Promise((resolve) => {
            if (!file || !file.type || !file.type.startsWith('image/')) {
                return resolve(file); // PDFs or other non-image files are passed directly
            }

            const img = new Image();
            const url = URL.createObjectURL(file);
            img.onload = () => {
                URL.revokeObjectURL(url);
                let w = img.width;
                let h = img.height;

                if (w <= maxDimension && h <= maxDimension && file.size < 800 * 1024) {
                    return resolve(file);
                }

                if (w > maxDimension || h > maxDimension) {
                    if (w > h) {
                        h = Math.round((h * maxDimension) / w);
                        w = maxDimension;
                    } else {
                        w = Math.round((w * maxDimension) / h);
                        h = maxDimension;
                    }
                }

                const canvas = document.createElement('canvas');
                canvas.width = w;
                canvas.height = h;
                const ctx = canvas.getContext('2d');
                ctx.drawImage(img, 0, 0, w, h);

                canvas.toBlob(
                    (blob) => {
                        if (blob) {
                            const newName = (file.name || 'photo').replace(/\.[^/.]+$/, '') + '.jpg';
                            const compressed = new File([blob], newName, {
                                type: 'image/jpeg',
                                lastModified: Date.now()
                            });
                            resolve(compressed);
                        } else {
                            resolve(file);
                        }
                    },
                    'image/jpeg',
                    quality
                );
            };
            img.onerror = () => resolve(file);
            img.src = url;
        });
    }

    async function safeFetchJson(url, options = {}) {
        let res;
        try {
            res = await fetch(url, options);
        } catch (netErr) {
            throw new Error('Network request failed. If the Render instance is spinning up, please wait 5 seconds and retry.');
        }

        const contentType = res.headers.get('content-type') || '';
        if (!contentType.includes('application/json')) {
            const rawText = await res.text();
            if (res.status === 502 || res.status === 503 || res.status === 504) {
                throw new Error('Cloud server is waking up from idle. Please wait 5-10 seconds and try again.');
            }
            if (res.status === 413) {
                throw new Error('Uploaded file is too large. Please select a smaller photo or PDF.');
            }
            throw new Error(`Server returned HTTP ${res.status}: ${rawText.substring(0, 100)}`);
        }

        const data = await res.json();
        if (!res.ok) {
            throw new Error(data.detail || `Request failed with status ${res.status}`);
        }
        return data;
    }

    async function uploadFile(file) {
        if (!file) return;

        showLoading('Uploading & Preparing File...', 'Optimizing document for instant extraction...');

        try {
            const optimizedFile = await compressImageForUpload(file);
            const formData = new FormData();
            formData.append('file', optimizedFile);

            const data = await safeFetchJson('/api/upload', {
                method: 'POST',
                body: formData
            });

            hideLoading();

            if (data.status === 'success') {
                currentUploadedData = data;
                originalImgWidth = data.width || 1200;
                originalImgHeight = data.height || 1600;

                // Update UI elements
                dropZone.style.display = 'none';
                filePreviewBar.style.display = 'flex';
                cropControlStrip.style.display = 'flex';
                if (pageCropPreviewCard) pageCropPreviewCard.style.display = 'block';

                lblFileName.innerText = data.filename;
                const fileExt = data.filename.split('.').pop().toUpperCase();
                lblFileMeta.innerText = `${fileExt} File • ${data.total_pages} Page(s) • (${originalImgWidth}×${originalImgHeight}px)`;

                const setupImageAndCrop = () => {
                    initCropOverlay();
                    if (cropStage) {
                        stageRect = cropStage.getBoundingClientRect();
                        setCropPosPx(0, 0, stageRect.width, stageRect.height);
                        if (cropBadge) cropBadge.innerText = `Full page: ${originalImgWidth} × ${originalImgHeight}`;
                        setActiveCropButton(btnClearCrop);
                    }
                };

                if (previewImage) {
                    previewImage.onload = () => {
                        setTimeout(setupImageAndCrop, 100);
                    };
                    previewImage.src = data.image_b64;

                    if (previewImage.complete && previewImage.naturalWidth > 0) {
                        setTimeout(setupImageAndCrop, 100);
                    }
                }

                btnConvert.disabled = false;
            } else {
                alert(`Upload Error: ${data.detail || 'Could not process file'}`);
            }
        } catch (err) {
            hideLoading();
            alert(`Failed to upload file: ${err.message}`);
        }
    }

    if (btnSnapCamera && cameraInput) {
        btnSnapCamera.addEventListener('click', () => cameraInput.click());
    }

    if (btnChooseFile && fileInput) {
        btnChooseFile.addEventListener('click', () => fileInput.click());
    }

    fileInput.addEventListener('change', (e) => {
        if (e.target.files.length > 0) {
            uploadFile(e.target.files[0]);
        }
    });

    if (cameraInput) {
        cameraInput.addEventListener('change', (e) => {
            if (e.target.files.length > 0) {
                uploadFile(e.target.files[0]);
            }
        });
    }

    btnChangeFile.addEventListener('click', () => {
        currentUploadedData = null;
        fileInput.value = '';
        if (cameraInput) cameraInput.value = '';
        filePreviewBar.style.display = 'none';
        cropControlStrip.style.display = 'none';
        if (pageCropPreviewCard) pageCropPreviewCard.style.display = 'none';
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
    // 4. Extraction & AI Recognition Action
    // ------------------------------------------------------------------
    let lastExtractedMetadata = null;

    btnConvert.addEventListener('click', async () => {
        if (!currentUploadedData) {
            alert('Please select a file first.');
            return;
        }

        showLoading(
            'Extracting Marksheet Data',
            'Processing marksheet table and student details...'
        );

        const payload = {
            file_b64_list: currentUploadedData.pages_b64 || [currentUploadedData.image_b64],
            engine: 'hybrid'
        };

        try {
            const data = await safeFetchJson('/api/extract', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });

            hideLoading();

            if (data.status === 'success') {
                const sections = data.sections || [];
                spreadsheetEditor.setSections(sections);

                // Update Student & Document Metadata Banner dynamically (editable inputs)
                lastExtractedMetadata = data.metadata || (sections.length > 0 ? sections[0].metadata : null);
                renderStudentMetadata(lastExtractedMetadata);

                const benchmarkCard = document.getElementById('benchmarkCard');
                if (data.comparative_benchmark && benchmarkCard) {
                    benchmarkCard.style.display = 'block';
                } else if (benchmarkCard) {
                    benchmarkCard.style.display = 'none';
                }

                // Unhide Results Card and scroll to view
                resultCard.style.display = 'block';
                resultCard.scrollIntoView({ behavior: 'smooth' });
            } else {
                alert(`Extraction error: ${data.detail || 'Failed to extract'}`);
            }
        } catch (err) {
            hideLoading();
            alert(`Extraction error: ${err.message}`);
        }
    });

    function cleanNumericRollNo(val) {
        if (!val) return '';
        const s = String(val).trim();
        // E.g. "44 / SE", "44/SE", "44-SE" -> "44"
        const m1 = s.match(/^\s*(\d+)\s*[/_-]/);
        if (m1) return m1[1];
        // E.g. "SE-46", "SE/46", "B-63" -> "46", "63"
        const m2 = s.match(/^[A-Za-z\s/_-]+(\d+)\s*$/);
        if (m2) return m2[1];
        // Standalone number
        const m3 = s.match(/\b\d+\b/);
        if (m3) return m3[0];
        return s;
    }

    function renderStudentMetadata(meta) {
        const metaStudentName = document.getElementById('metaStudentName');
        const metaPRN = document.getElementById('metaPRN');
        const metaRollNo = document.getElementById('metaRollNo');
        const metaBranch = document.getElementById('metaBranch');
        const metaDivision = document.getElementById('metaDivision');
        const metaSemester = document.getElementById('metaSemester');
        const metaSubject = document.getElementById('metaSubject');

        if (!meta) {
            if (metaStudentName) metaStudentName.value = '';
            if (metaPRN) metaPRN.value = '';
            if (metaRollNo) metaRollNo.value = '';
            if (metaBranch) metaBranch.value = '';
            if (metaDivision) metaDivision.value = '';
            if (metaSemester) metaSemester.value = '';
            if (metaSubject) metaSubject.value = '';
            return;
        }

        const name = meta.student_name || meta.name || '';
        const prn = meta.prn || '';
        const rawRoll = meta.roll_no || meta.roll_number || meta.rollno || '';
        const rollNo = cleanNumericRollNo(rawRoll) || rawRoll;
        const branch = meta.branch || '';
        const div = meta.division || '';
        const sem = meta.semester || '';
        const subj = meta.subject || '';

        if (metaStudentName) metaStudentName.value = name ? name.toUpperCase() : '';
        if (metaPRN) metaPRN.value = prn ? prn : '';
        if (metaRollNo) metaRollNo.value = rollNo ? rollNo.toUpperCase() : '';
        if (metaBranch) metaBranch.value = branch ? branch : '';
        if (metaDivision) metaDivision.value = div ? div : '';
        if (metaSemester) metaSemester.value = sem ? sem : '';
        if (metaSubject) metaSubject.value = subj ? subj : '';
    }

    function getEditedMetadata() {
        const metaStudentName = document.getElementById('metaStudentName');
        const metaPRN = document.getElementById('metaPRN');
        const metaRollNo = document.getElementById('metaRollNo');
        const metaBranch = document.getElementById('metaBranch');
        const metaDivision = document.getElementById('metaDivision');
        const metaSemester = document.getElementById('metaSemester');
        const metaSubject = document.getElementById('metaSubject');

        const rawRoll = metaRollNo ? metaRollNo.value.trim() : '';
        const cleanRoll = cleanNumericRollNo(rawRoll) || rawRoll;

        return {
            student_name: metaStudentName ? metaStudentName.value.trim() : '',
            prn: metaPRN ? metaPRN.value.trim() : '',
            roll_no: cleanRoll,
            branch: metaBranch ? metaBranch.value.trim() : '',
            division: metaDivision ? metaDivision.value.trim() : '',
            semester: metaSemester ? metaSemester.value.trim() : '',
            subject: metaSubject ? metaSubject.value.trim() : ''
        };
    }

    function extractQuestionMarksFromGrid() {
        const sections = spreadsheetEditor.getSections();
        if (!sections || sections.length === 0) return {};

        const sec = sections[0];
        const headers = sec.headers || [];
        const rows = sec.rows || [];

        const marksMap = {};
        if (rows.length >= 2) {
            // Row 1 is Mark Awarded row
            const awardRow = rows[1];
            headers.forEach((h, idx) => {
                const normH = String(h).trim().toLowerCase();
                if (normH.startsWith('1') || normH.startsWith('2') || normH.startsWith('3') || normH === 'total') {
                    const cellVal = idx < awardRow.length ? (awardRow[idx].value || awardRow[idx].text || '') : '';
                    marksMap[normH] = String(cellVal).trim();
                }
            });
        }
        return marksMap;
    }

    // ------------------------------------------------------------------
    // 5. Student Submit to MongoDB Database
    // ------------------------------------------------------------------
    btnSubmitToDb.addEventListener('click', async () => {
        const classroomId = studentClassroomSelect ? studentClassroomSelect.value : '';
        
        if (!classroomId) {
            alert('No active classroom session selected. Please select a classroom created by your faculty before submitting.');
            return;
        }

        const currentMeta = getEditedMetadata();
        const questionMarks = extractQuestionMarksFromGrid();

        if (!currentMeta.student_name && !currentMeta.prn && !currentMeta.roll_no) {
            alert('Please verify student metadata (Name / Roll No / PRN) before submitting.');
            return;
        }

        showLoading('Submitting Marksheet', 'Saving student marksheet to classroom database...');

        try {
            const data = await safeFetchJson('/api/submissions', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    classroom_id: classroomId,
                    student_metadata: currentMeta,
                    marks_data: questionMarks,
                    raw_image_b64: currentUploadedData ? currentUploadedData.image_b64 : null
                })
            });

            hideLoading();

            if (data.status === 'success') {
                showToast(
                    'Submitted Successfully! 🎉',
                    `${currentMeta.student_name} (Roll: ${currentMeta.roll_no}) was stored in MongoDB Atlas.`
                );
            } else {
                alert(`Submission error: ${data.detail || 'Could not save marksheet'}`);
            }
        } catch (err) {
            hideLoading();
            alert(`Failed to submit to database: ${err.message}`);
        }
    });

    // ------------------------------------------------------------------
    // 6. Individual Student Excel / CSV Exports
    // ------------------------------------------------------------------
    btnExportExcel.addEventListener('click', async () => {
        const sections = spreadsheetEditor.getSections();
        if (!sections || sections.length === 0) return;

        showLoading('Generating Excel File', 'Formatting worksheets & auto-fitting columns...');
        const currentMeta = getEditedMetadata();

        try {
            const res = await fetch('/api/export/excel', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ sections: sections, metadata: currentMeta })
            });

            if (res.ok) {
                const blob = await res.blob();
                const url = window.URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.href = url;
                a.download = `marksheet_${currentMeta.roll_no || 'student'}.xlsx`;
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
        const currentMeta = getEditedMetadata();

        try {
            const res = await fetch('/api/export/csv', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ sections: sections, metadata: currentMeta })
            });

            if (res.ok) {
                const blob = await res.blob();
                const url = window.URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.href = url;
                a.download = `marksheet_${currentMeta.roll_no || 'student'}.csv`;
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

    // ------------------------------------------------------------------
    // 7. Faculty Dashboard & Live Class Roster
    // ------------------------------------------------------------------
    async function loadFacultyRoster() {
        const classroomId = facultyClassroomSelect ? facultyClassroomSelect.value : (activeClassroomsList[0]?.classroom_id || 'SE_IT_B_IV_CNND_IA1');
        if (!classroomId) return;

        try {
            const res = await fetch(`/api/submissions/${classroomId}`);
            const data = await res.json();

            if (data.status === 'success') {
                currentRosterData = data.submissions || [];
                renderFacultyMetrics(currentRosterData);
                renderFacultyRosterTable(currentRosterData);
            }
        } catch (err) {
            console.error('Failed to fetch faculty roster from MongoDB:', err);
        }
    }

    function parseScoreValue(scoreStr, marksMap) {
        const s = String(scoreStr || '').trim();
        if (s) {
            if (s.includes('1/2')) {
                const base = s.replace('1/2', '').trim();
                const baseNum = parseFloat(base) || 0;
                return baseNum + 0.5;
            }
            if (s.includes('/')) {
                const parts = s.split('/');
                const num = parseFloat(parts[0].trim().replace(/[^0-9.]/g, ''));
                if (!isNaN(num)) return num;
            }
            const cleaned = s.replace(/[^0-9.]/g, '');
            const num = parseFloat(cleaned);
            if (!isNaN(num)) return num;
        }

        // Fallback: calculate sum from individual awarded question marks
        if (marksMap) {
            let calcSum = 0;
            let hasAny = false;
            Object.values(marksMap).forEach(v => {
                const sv = String(v || '').trim();
                if (sv) {
                    if (sv.includes('1/2')) {
                        const base = sv.replace('1/2', '').trim();
                        const bNum = parseFloat(base) || 0;
                        calcSum += (bNum + 0.5);
                        hasAny = true;
                    } else {
                        const cn = parseFloat(sv.replace(/[^0-9.]/g, ''));
                        if (!isNaN(cn)) {
                            calcSum += cn;
                            hasAny = true;
                        }
                    }
                }
            });
            if (hasAny) return calcSum;
        }

        return NaN;
    }

    function renderFacultyMetrics(submissions) {
        if (!submissions || submissions.length === 0) {
            if (statTotalSubmissions) statTotalSubmissions.innerText = '0';
            if (statClassAverage) statClassAverage.innerText = '0.0 / 20';
            if (statHighestScore) statHighestScore.innerText = '0 / 20';
            if (statTopStudent) statTopStudent.innerText = 'No submissions';
            if (statLatestTime) statLatestTime.innerText = '-';
            if (statLatestStudent) statLatestStudent.innerText = 'No submissions';
            return;
        }

        const count = submissions.length;
        if (statTotalSubmissions) statTotalSubmissions.innerText = String(count);

        let totalSum = 0;
        let validScoresCount = 0;
        let highest = -1;
        let topStudentName = '';

        submissions.forEach(s => {
            const totNum = parseScoreValue(s.total_marks, s.marks_awarded);
            if (!isNaN(totNum) && totNum >= 0) {
                totalSum += totNum;
                validScoresCount++;
                if (totNum > highest) {
                    highest = totNum;
                    topStudentName = s.student_name || s.roll_no;
                }
            }
        });

        const avg = validScoresCount > 0 ? (totalSum / validScoresCount).toFixed(1) : '0.0';
        if (statClassAverage) statClassAverage.innerText = `${avg} / 20`;
        if (statHighestScore) statHighestScore.innerText = highest >= 0 ? `${highest} / 20` : '0 / 20';
        if (statTopStudent) statTopStudent.innerText = topStudentName || 'N/A';

        // Latest submission info
        const latest = submissions[submissions.length - 1];
        if (statLatestTime) statLatestTime.innerText = 'Just now (Synced)';
        if (statLatestStudent) statLatestStudent.innerText = latest ? `${latest.student_name} (${latest.roll_no})` : '-';
    }

    function renderFacultyRosterTable(submissions) {
        if (!facultyRosterTableBody) return;

        if (!submissions || submissions.length === 0) {
            facultyRosterTableBody.innerHTML = '';
            if (rosterEmptyState) rosterEmptyState.style.display = 'block';
            return;
        }

        if (rosterEmptyState) rosterEmptyState.style.display = 'none';

        const rowsHtml = submissions.map((s, idx) => {
            const marks = s.marks_awarded || {};
            const cleanTot = parseScoreValue(s.total_marks, marks);
            const displayTotal = !isNaN(cleanTot) ? cleanTot : (s.total_marks || '-');

            return `
                <tr>
                    <td><strong>${idx + 1}</strong></td>
                    <td><span style="font-weight:700; color:#1E40AF;">${cleanNumericRollNo(s.roll_no) || s.roll_no || '-'}</span></td>
                    <td><span style="font-family:var(--font-code); font-size:0.82rem;">${s.prn || '-'}</span></td>
                    <td><strong>${s.student_name || '-'}</strong></td>
                    <td>${marks['1a'] || ''}</td>
                    <td>${marks['1b'] || ''}</td>
                    <td>${marks['1c'] || ''}</td>
                    <td>${marks['1d'] || ''}</td>
                    <td>${marks['1e'] || ''}</td>
                    <td>${marks['1f'] || ''}</td>
                    <td>${marks['2a'] || ''}</td>
                    <td>${marks['2b'] || ''}</td>
                    <td>${marks['3a'] || ''}</td>
                    <td>${marks['3b'] || ''}</td>
                    <td class="total-col" style="font-weight:700; color:#15803D;">${displayTotal}</td>
                    <td><span class="roster-badge-status"><i class="fa-solid fa-check"></i> ${s.status || 'Verified'}</span></td>
                </tr>
            `;
        }).join('');

        facultyRosterTableBody.innerHTML = rowsHtml;
    }

    // Live search filter in faculty roster
    if (facultyRosterSearch) {
        facultyRosterSearch.addEventListener('input', (e) => {
            const query = e.target.value.toLowerCase().trim();
            if (!query) {
                renderFacultyRosterTable(currentRosterData);
                return;
            }

            const filtered = currentRosterData.filter(s => {
                const name = (s.student_name || '').toLowerCase();
                const roll = (s.roll_no || '').toLowerCase();
                const prn = (s.prn || '').toLowerCase();
                return name.includes(query) || roll.includes(query) || prn.includes(query);
            });

            renderFacultyRosterTable(filtered);
        });
    }

    if (facultyClassroomSelect) {
        facultyClassroomSelect.addEventListener('change', () => loadFacultyRoster());
    }

    if (btnRefreshFacultyRoster) {
        btnRefreshFacultyRoster.addEventListener('click', async () => {
            showToast('Refreshing Roster...', 'Fetching latest submissions from MongoDB Atlas.');
            await loadFacultyRoster();
        });
    }

    // Master Class Excel Export
    if (btnFacultyExportExcel) {
        btnFacultyExportExcel.addEventListener('click', async () => {
            const classroomId = facultyClassroomSelect ? facultyClassroomSelect.value : 'SE_IT_B_IV_CNND_IA1';
            showLoading('Exporting Master Class Excel', 'Compiling all student grades into one Excel workbook...');

            try {
                const res = await fetch(`/api/export/master-excel/${classroomId}`);
                if (res.ok) {
                    const blob = await res.blob();
                    const url = window.URL.createObjectURL(blob);
                    const a = document.createElement('a');
                    a.href = url;
                    a.download = `master_grade_sheet_${classroomId}.xlsx`;
                    document.body.appendChild(a);
                    a.click();
                    a.remove();
                    window.URL.revokeObjectURL(url);
                } else {
                    alert('Failed to export Master Excel sheet.');
                }
            } catch (err) {
                alert(`Export error: ${err.message}`);
            } finally {
                hideLoading();
            }
        });
    }

    // Master Class CSV Export
    if (btnFacultyExportCsv) {
        btnFacultyExportCsv.addEventListener('click', async () => {
            const classroomId = facultyClassroomSelect ? facultyClassroomSelect.value : 'SE_IT_B_IV_CNND_IA1';
            showLoading('Exporting Master CSV', 'Generating clean CSV for all students...');

            try {
                const res = await fetch(`/api/export/master-csv/${classroomId}`);
                if (res.ok) {
                    const blob = await res.blob();
                    const url = window.URL.createObjectURL(blob);
                    const a = document.createElement('a');
                    a.href = url;
                    a.download = `master_grade_sheet_${classroomId}.csv`;
                    document.body.appendChild(a);
                    a.click();
                    a.remove();
                    window.URL.revokeObjectURL(url);
                } else {
                    alert('Failed to export Master CSV file.');
                }
            } catch (err) {
                alert(`Export error: ${err.message}`);
            } finally {
                hideLoading();
            }
        });
    }

    // ------------------------------------------------------------------
    // 8. Grid Tools & Utilities
    // ------------------------------------------------------------------
    if (btnAddRow) btnAddRow.addEventListener('click', () => spreadsheetEditor.addRow());
    if (btnAddCol) btnAddCol.addEventListener('click', () => spreadsheetEditor.addColumn());
    if (btnClearGrid) {
        btnClearGrid.addEventListener('click', () => {
            if (confirm('Clear current spreadsheet grid?')) {
                spreadsheetEditor.clearGrid();
            }
        });
    }

    function showToast(title, msg) {
        if (!toastNotification) return;
        toastTitle.innerText = title;
        toastMessage.innerText = msg;
        toastNotification.style.display = 'flex';
        setTimeout(() => {
            toastNotification.style.display = 'none';
        }, 4000);
    }

    function showLoading(title, msg) {
        loadingTitle.innerText = title;
        loadingMessage.innerText = msg;
        loadingOverlay.style.display = 'flex';
    }

    function hideLoading() {
        loadingOverlay.style.display = 'none';
    }

    // Initial Load
    loadClassrooms();
});
