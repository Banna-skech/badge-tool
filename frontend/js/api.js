/**
 * API client for the photo processor backend.
 * All calls go to the same origin (FastAPI serves both API and static files).
 */
const API = {
    BASE: '/api',

    /**
     * Upload a batch of photo files.
     * @param {FileList|File[]} files
     * @returns {Promise<Object>} { session_id, file_count, files }
     */
    async uploadPhotos(files) {
        const formData = new FormData();
        for (const f of files) {
            formData.append('files', f);
        }
        const res = await fetch(`${this.BASE}/upload/photos`, {
            method: 'POST',
            body: formData,
        });
        if (!res.ok) {
            const err = await res.json().catch(() => ({}));
            throw new Error(err.detail || `上传失败 (${res.status})`);
        }
        return await res.json();
    },

    /**
     * Upload a name list file (xlsx or txt).
     * @param {string} sessionId
     * @param {File} file
     * @returns {Promise<Object>}
     */
    async uploadNamelist(sessionId, file) {
        const formData = new FormData();
        formData.append('session_id', sessionId);
        formData.append('file', file);
        const res = await fetch(`${this.BASE}/upload/namelist`, {
            method: 'POST',
            body: formData,
        });
        if (!res.ok) {
            const err = await res.json().catch(() => ({}));
            throw new Error(err.detail || `名单上传失败 (${res.status})`);
        }
        return await res.json();
    },

    /**
     * Get available Excel columns and matching preview.
     * @param {string} sessionId
     * @returns {Promise<Object>}
     */
    async getNamelistColumns(sessionId) {
        const res = await fetch(`${this.BASE}/namelist/columns?session_id=${encodeURIComponent(sessionId)}`);
        if (!res.ok) {
            const err = await res.json().catch(() => ({}));
            throw new Error(err.detail || `获取列信息失败 (${res.status})`);
        }
        return await res.json();
    },

    /**
     * Select which Excel column contains names.
     * @param {string} sessionId
     * @param {string} columnName
     * @returns {Promise<Object>}
     */
    async selectNameColumn(sessionId, columnName) {
        const res = await fetch(`${this.BASE}/namelist/select-column`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ session_id: sessionId, column_name: columnName }),
        });
        if (!res.ok) {
            const err = await res.json().catch(() => ({}));
            throw new Error(err.detail || `选择列失败 (${res.status})`);
        }
        return await res.json();
    },

    /**
     * Start the batch processing job.
     * @param {string} sessionId
     * @param {Object} options - { badge_photo, seat_card, namelist_mode }
     * @returns {Promise<Object>} { job_id }
     */
    async startProcess(sessionId, options) {
        const res = await fetch(`${this.BASE}/process`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                session_id: sessionId,
                badge_photo: options.badge_photo,
                seat_card: options.seat_card,
                namelist_mode: options.namelist_mode || 'filename',
            }),
        });
        if (!res.ok) {
            const err = await res.json().catch(() => ({}));
            throw new Error(err.detail || `启动处理失败 (${res.status})`);
        }
        return await res.json();
    },

    /**
     * Subscribe to processing progress via SSE.
     * @param {string} jobId
     * @param {function} onProgress - callback({ progress, total, status, current_file, warning, errors })
     * @param {function} onComplete - callback when done
     * @param {function} onError - callback on connection error
     * @returns {EventSource}
     */
    subscribeProgress(jobId, onProgress, onComplete, onError) {
        const es = new EventSource(`${this.BASE}/process/${jobId}/status`);
        es.onmessage = (event) => {
            const data = JSON.parse(event.data);
            if (data.status === 'completed' || data.status === 'error') {
                onProgress(data);
                es.close();
                onComplete(data);
            } else {
                onProgress(data);
            }
        };
        es.onerror = (err) => {
            es.close();
            if (onError) onError(err);
        };
        return es;
    },

    /**
     * Download the result ZIP with error checking.
     * @param {string} jobId
     */
    async downloadResultWithCheck(jobId) {
        const res = await fetch(`${this.BASE}/process/${jobId}/download`);
        if (!res.ok) {
            const err = await res.json().catch(() => ({ detail: `服务器错误 (${res.status})` }));
            throw new Error(err.detail || `下载失败 (${res.status})`);
        }
        const blob = await res.blob();
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `processed_photos_${jobId}.zip`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
    },

    /**
     * Direct download (legacy — no error check).
     * @param {string} jobId
     */
    downloadResult(jobId) {
        const a = document.createElement('a');
        a.href = `${this.BASE}/process/${jobId}/download`;
        a.download = `processed_photos_${jobId}.zip`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
    },

    /**
     * Download a name list template.
     */
    downloadNamelistTemplate() {
        const a = document.createElement('a');
        a.href = `${this.BASE}/save/namelist`;
        a.download = '名单模板.txt';
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
    },

    // ── Excel employee table processing ────────────────────────────

    /**
     * Upload a raw employee Excel and get parsed preview.
     * @param {File} file
     * @returns {Promise<Object>} { chinese_headers, detected_columns, total_rows, preview }
     */
    async uploadEmployeeExcel(file) {
        const formData = new FormData();
        formData.append('file', file);
        const res = await fetch(`${this.BASE}/excel/upload`, {
            method: 'POST',
            body: formData,
        });
        if (!res.ok) {
            const err = await res.json().catch(() => ({}));
            throw new Error(err.detail || `Excel 上传失败 (${res.status})`);
        }
        return await res.json();
    },

    /**
     * Process a raw employee Excel and download the formatted result.
     * @param {File} file
     */
    async processEmployeeExcel(file) {
        const formData = new FormData();
        formData.append('file', file);
        const res = await fetch(`${this.BASE}/excel/process`, {
            method: 'POST',
            body: formData,
        });
        if (!res.ok) {
            const err = await res.json().catch(() => ({ detail: `服务器错误 (${res.status})` }));
            throw new Error(err.detail || `处理失败 (${res.status})`);
        }
        const blob = await res.blob();
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `工牌座位牌_${Date.now()}.xlsx`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
    },
};
