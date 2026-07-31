/**
 * Image Canvas Controller for Photo to Excel Converter.
 * Handles Canvas rendering, Zoom/Pan, Section Bounding Box Overlays, and ROI Cropping.
 */

class ImageCanvasController {
    constructor(canvasId, wrapperId, viewportId) {
        this.canvas = document.getElementById(canvasId);
        this.ctx = this.canvas.getContext('2d');
        this.wrapper = document.getElementById(wrapperId);
        this.viewport = document.getElementById(viewportId);

        this.image = new Image();
        this.zoomLevel = 1.0;
        this.showBBoxes = true;
        this.sections = [];

        this.highlightedBBox = None = null;
        this.cropMode = false;
        this.cropStart = null;
        this.cropEnd = null;

        // Palette for section bounding box colors
        this.sectionColors = [
            '#06B6D4', // Cyan
            '#6366F1', // Indigo
            '#10B981', // Emerald
            '#F59E0B', // Amber
            '#EC4899', // Pink
            '#8B5CF6'  // Purple
        ];

        this.initEvents();
    }

    initEvents() {
        // Canvas drag / ROI crop events
        this.canvas.addEventListener('mousedown', (e) => this.onMouseDown(e));
        this.canvas.addEventListener('mousemove', (e) => this.onMouseMove(e));
        this.canvas.addEventListener('mouseup', (e) => this.onMouseUp(e));
    }

    loadImageFromSrc(src, callback) {
        this.image.onload = () => {
            this.canvas.width = this.image.width;
            this.canvas.height = this.image.height;
            this.render();
            if (callback) callback(this.image.width, this.image.height);
        };
        this.image.src = src;
    }

    setZoom(level) {
        this.zoomLevel = Math.max(0.2, Math.min(level, 4.0));
        this.viewport.style.transform = `scale(${this.zoomLevel})`;
        this.viewport.style.transformOrigin = 'top left';
        const zoomText = document.getElementById('zoomLevel');
        if (zoomText) zoomText.innerText = `${Math.round(this.zoomLevel * 100)}%`;
    }

    toggleBBoxes() {
        this.showBBoxes = !this.showBBoxes;
        this.render();
        return this.showBBoxes;
    }

    setSections(sections) {
        this.sections = sections || [];
        this.render();
    }

    setHighlightBBox(bbox) {
        this.highlightedBBox = bbox;
        this.render();
    }

    render() {
        if (!this.image.src) return;

        // Clear canvas
        this.ctx.clearRect(0, 0, this.canvas.width, this.canvas.height);

        // Draw Base Image
        this.ctx.drawImage(this.image, 0, 0);

        // Draw Section Bounding Boxes if enabled
        if (this.showBBoxes && this.sections.length > 0) {
            this.sections.forEach((sec, sIdx) => {
                const color = this.sectionColors[sIdx % this.sectionColors.length];
                const [sx, sy, sw, sh] = sec.bbox || [0,0,0,0];

                // Section Box
                this.ctx.lineWidth = 3;
                this.ctx.strokeStyle = color;
                this.ctx.strokeRect(sx, sy, sw, sh);

                // Section Fill
                this.ctx.fillStyle = `${color}1A`; // 10% opacity
                this.ctx.fillRect(sx, sy, sw, sh);

                // Section Label Badge
                this.ctx.fillStyle = color;
                this.ctx.font = 'bold 14px Inter, sans-serif';
                const labelText = ` ${sec.title || 'Section'} `;
                const textWidth = this.ctx.measureText(labelText).width;

                this.ctx.fillRect(sx, Math.max(0, sy - 24), textWidth + 8, 24);
                this.ctx.fillStyle = '#FFFFFF';
                this.ctx.fillText(labelText, sx + 4, Math.max(16, sy - 7));

                // Draw Cell Boxes inside section
                if (sec.rows) {
                    this.ctx.lineWidth = 1;
                    this.ctx.strokeStyle = `${color}80`;
                    sec.rows.forEach(row => {
                        row.forEach(cell => {
                            if (cell.bbox) {
                                const [cx, cy, cw, ch] = cell.bbox;
                                this.ctx.strokeRect(cx, cy, cw, ch);
                            }
                        });
                    });
                }
            });
        }

        // Draw Highlighted Cell Bounding Box if active
        if (this.highlightedBBox) {
            const [hx, hy, hw, hh] = this.highlightedBBox;
            this.ctx.lineWidth = 4;
            this.ctx.strokeStyle = '#EF4444'; // Red highlight
            this.ctx.fillStyle = 'rgba(239, 68, 68, 0.3)';
            this.ctx.strokeRect(hx, hy, hw, hh);
            this.ctx.fillRect(hx, hy, hw, hh);
        }

        // Draw ROI Crop Box if actively drawing
        if (this.cropMode && this.cropStart && this.cropEnd) {
            const rx = Math.min(this.cropStart.x, this.cropEnd.x);
            const ry = Math.min(this.cropStart.y, this.cropEnd.y);
            const rw = Math.abs(this.cropEnd.x - this.cropStart.x);
            const rh = Math.abs(this.cropEnd.y - this.cropStart.y);

            this.ctx.lineWidth = 2;
            this.ctx.strokeStyle = '#F59E0B'; // Amber
            this.ctx.setLineDash([6, 6]);
            this.ctx.strokeRect(rx, ry, rw, rh);
            this.ctx.setLineDash([]);
            this.ctx.fillStyle = 'rgba(245, 158, 11, 0.15)';
            this.ctx.fillRect(rx, ry, rw, rh);
        }
    }

    onMouseDown(e) {
        if (!this.cropMode) return;
        const rect = this.canvas.getBoundingClientRect();
        const scaleX = this.canvas.width / rect.width;
        const scaleY = this.canvas.height / rect.height;

        this.cropStart = {
            x: (e.clientX - rect.left) * scaleX,
            y: (e.clientY - rect.top) * scaleY
        };
        this.cropEnd = { ...this.cropStart };
    }

    onMouseMove(e) {
        if (!this.cropMode || !this.cropStart) return;
        const rect = this.canvas.getBoundingClientRect();
        const scaleX = this.canvas.width / rect.width;
        const scaleY = this.canvas.height / rect.height;

        this.cropEnd = {
            x: (e.clientX - rect.left) * scaleX,
            y: (e.clientY - rect.top) * scaleY
        };
        this.render();
    }

    onMouseUp(e) {
        if (!this.cropMode || !this.cropStart) return;
        this.render();
    }

    getCropROI() {
        if (!this.cropStart || !this.cropEnd) return null;
        const rx = Math.round(Math.min(this.cropStart.x, this.cropEnd.x));
        const ry = Math.round(Math.min(this.cropStart.y, this.cropEnd.y));
        const rw = Math.round(Math.abs(this.cropEnd.x - this.cropStart.x));
        const rh = Math.round(Math.abs(this.cropEnd.y - this.cropStart.y));

        if (rw < 10 || rh < 10) return null;
        return { x: rx, y: ry, width: rw, height: rh };
    }

    clearCrop() {
        this.cropStart = null;
        this.cropEnd = null;
        this.cropMode = false;
        this.render();
    }
}
