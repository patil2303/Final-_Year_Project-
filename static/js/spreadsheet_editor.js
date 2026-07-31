/**
 * Clean Spreadsheet Editor Controller.
 * Handles rendering editable table grids, tabs, row/col additions.
 */

class SpreadsheetEditorController {
    constructor(tabsBarId, tableHeadId, tableBodyId) {
        this.tabsBar = document.getElementById(tabsBarId);
        this.tableHead = document.getElementById(tableHeadId);
        this.tableBody = document.getElementById(tableBodyId);

        this.sections = [];
        this.activeSectionIdx = 0;
    }

    setSections(sections) {
        this.sections = sections || [];
        this.activeSectionIdx = 0;
        this.render();
    }

    getSections() {
        return this.sections;
    }

    render() {
        this.renderTabs();
        this.renderActiveGrid();
    }

    renderTabs() {
        this.tabsBar.innerHTML = '';
        if (this.sections.length <= 1) return;

        this.sections.forEach((sec, idx) => {
            const tab = document.createElement('div');
            tab.className = `section-tab-item ${idx === this.activeSectionIdx ? 'active' : ''}`;
            tab.innerText = sec.title || `Section ${idx + 1}`;
            tab.addEventListener('click', () => {
                this.activeSectionIdx = idx;
                this.render();
            });
            this.tabsBar.appendChild(tab);
        });
    }

    renderActiveGrid() {
        this.tableHead.innerHTML = '';
        this.tableBody.innerHTML = '';

        const activeSec = this.sections[this.activeSectionIdx];
        if (!activeSec) return;

        // 1. Render Headers
        const headerTr = document.createElement('tr');

        // Row Index column header
        const thIndex = document.createElement('th');
        thIndex.innerText = '#';
        thIndex.style.width = '40px';
        thIndex.style.textAlign = 'center';
        headerTr.appendChild(thIndex);

        activeSec.headers.forEach((hText, cIdx) => {
            const th = document.createElement('th');
            const input = document.createElement('input');
            input.type = 'text';
            input.value = hText;
            input.style.fontWeight = 'bold';
            input.style.color = '#4F46E5';
            input.addEventListener('input', (e) => {
                activeSec.headers[cIdx] = e.target.value;
            });
            th.appendChild(input);
            headerTr.appendChild(th);
        });
        this.tableHead.appendChild(headerTr);

        // 2. Render Data Rows
        activeSec.rows.forEach((row, rIdx) => {
            const tr = document.createElement('tr');

            const tdIndex = document.createElement('td');
            tdIndex.innerText = rIdx + 1;
            tdIndex.style.textAlign = 'center';
            tdIndex.style.color = '#94A3B8';
            tdIndex.style.fontSize = '0.78rem';
            tr.appendChild(tdIndex);

            row.forEach((cell, cIdx) => {
                const td = document.createElement('td');
                if (cell.is_number) {
                    td.classList.add('is-number');
                }

                const input = document.createElement('input');
                input.type = 'text';
                // Display priority: text > value > empty (formatted_text may not exist on all cells)
                const displayVal = cell.text || (cell.value !== undefined && cell.value !== null ? String(cell.value) : '');
                input.value = displayVal;

                input.addEventListener('input', (e) => {
                    const val = e.target.value.trim();
                    cell.text = val;
                    cell.formatted_text = val;
                    
                    if (val !== '' && !isNaN(val)) {
                        cell.value = Number(val);
                        cell.is_number = true;
                        td.classList.add('is-number');
                    } else {
                        cell.value = val;
                        cell.is_number = false;
                        td.classList.remove('is-number');
                    }
                });

                td.appendChild(input);
                tr.appendChild(td);
            });

            this.tableBody.appendChild(tr);
        });
    }

    addRow() {
        const activeSec = this.sections[this.activeSectionIdx];
        if (!activeSec) return;

        const numCols = activeSec.headers.length || 1;
        const newRow = Array.from({ length: numCols }, () => ({
            text: '',
            value: '',
            is_number: false
        }));

        activeSec.rows.push(newRow);
        this.render();
    }

    addColumn() {
        const activeSec = this.sections[this.activeSectionIdx];
        if (!activeSec) return;

        const colNum = activeSec.headers.length + 1;
        activeSec.headers.push(`Column ${colNum}`);

        activeSec.rows.forEach(row => {
            row.push({
                text: '',
                value: '',
                is_number: false
            });
        });

        this.render();
    }

    clearGrid() {
        const activeSec = this.sections[this.activeSectionIdx];
        if (!activeSec) return;

        activeSec.rows = [];
        this.render();
    }
}
