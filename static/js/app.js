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

    const previewCard = document.getElementById('previewCard');
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
                if (previewCard) previewCard.style.display = 'block';

                lblFileName.innerText = data.filename;
                const fileExt = data.filename.split('.').pop().toUpperCase();
                lblFileMeta.innerText = `${fileExt} File • ${data.total_pages} Page(s) • (${originalImgWidth}×${originalImgHeight}px)`;

                btnConvert.disabled = false;
            } else {
                alert(`Upload Error: ${data.detail}`);
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
        if (previewCard) previewCard.style.display = 'none';
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
            'Extracting Marksheet & Table Grid',
            'Running Gemini Vision + PyTorch CNN Evaluator with zero cell hallucination...'
        );

        const payload = {
            file_b64_list: currentUploadedData.pages_b64 || [currentUploadedData.image_b64],
            engine: 'hybrid'
        };

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
                alert(`Extraction error: ${data.detail}`);
            }
        } catch (err) {
            hideLoading();
            alert(`Extraction error: ${err.message}`);
        }
    });

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
        const rollNo = meta.roll_no || meta.roll_number || meta.rollno || '';
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

        return {
            student_name: metaStudentName ? metaStudentName.value.trim() : '',
            prn: metaPRN ? metaPRN.value.trim() : '',
            roll_no: metaRollNo ? metaRollNo.value.trim() : '',
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

        showLoading('Submitting to Classroom Database', 'Syncing marksheet with MongoDB Atlas...');

        try {
            const res = await fetch('/api/submissions', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    classroom_id: classroomId,
                    student_metadata: currentMeta,
                    marks_data: questionMarks,
                    raw_image_b64: currentUploadedData ? currentUploadedData.image_b64 : null
                })
            });

            const data = await res.json();
            hideLoading();

            if (data.status === 'success') {
                showToast(
                    'Submitted Successfully! 🎉',
                    `${currentMeta.student_name} (Roll: ${currentMeta.roll_no}) was stored in MongoDB Atlas.`
                );
            } else {
                alert(`Submission error: ${data.detail}`);
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
            const totStr = String(s.total_marks || '').replace(/[^0-9.]/g, '');
            const totNum = parseFloat(totStr);
            if (!isNaN(totNum)) {
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
            return `
                <tr>
                    <td><strong>${idx + 1}</strong></td>
                    <td><span style="font-weight:700; color:#1E40AF;">${s.roll_no || '-'}</span></td>
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
                    <td class="total-col">${s.total_marks || ''}</td>
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
