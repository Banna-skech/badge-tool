/**
 * Main application UI — photo batch processor.
 * State machine: upload → name-list → process → download
 */
(function () {
    'use strict';

    // ---- State ----
    const state = {
        activeTab: 'photo',       // 'photo' | 'excel'
        sessionId: null,
        files: [],
        names: [],
        namelistMode: 'filename', // 'filename' | 'namelist'
        columns: [],
        suggestedColumn: null,
        selectedColumn: null,
        jobId: null,
        eventSource: null,
        badgePhoto: true,
        seatCard: true,
        // Excel tab state
        excelFile: null,
        excelParsed: null,
        excelProcessing: false,
    };

    // ---- Refs ----
    const $ = (sel) => document.querySelector(sel);
    const $$ = (sel) => document.querySelectorAll(sel);

    // ---- Init ----
    function init() {
        render();
    }

    // ---- Render ----
    function render() {
        // Update tab bar styles
        const tabPhoto = $('#tab-photo');
        const tabExcel = $('#tab-excel');
        if (tabPhoto && tabExcel) {
            if (state.activeTab === 'photo') {
                tabPhoto.className = 'px-6 py-2.5 rounded-lg font-medium text-sm transition-all bg-white shadow text-gray-800';
                tabExcel.className = 'px-6 py-2.5 rounded-lg font-medium text-sm transition-all text-gray-500 hover:text-gray-700';
            } else {
                tabExcel.className = 'px-6 py-2.5 rounded-lg font-medium text-sm transition-all bg-white shadow text-gray-800';
                tabPhoto.className = 'px-6 py-2.5 rounded-lg font-medium text-sm transition-all text-gray-500 hover:text-gray-700';
            }
        }

        const app = $('#app');
        if (!app) return;

        if (state.activeTab === 'excel') {
            app.innerHTML = renderExcelTab();
            bindExcelEvents();
        } else {
            app.innerHTML = `
                <!-- Step 1: Upload Photos -->
                <div class="mb-8" id="step-upload">
                    ${renderStepUpload()}
                </div>

                <!-- Step 2: Name List -->
                <div class="mb-8" id="step-names" style="${state.sessionId ? '' : 'opacity: 0.4; pointer-events: none;'}">
                    ${renderStepNames()}
                </div>

                <!-- Step 3: Output Options -->
                <div class="mb-8" id="step-options" style="${state.sessionId ? '' : 'opacity: 0.4; pointer-events: none;'}">
                    ${renderStepOptions()}
                </div>

                <!-- Step 4: Process & Download -->
                <div id="step-process" style="${state.sessionId ? '' : 'opacity: 0.4; pointer-events: none;'}">
                    ${renderStepProcess()}
                </div>
            `;
            bindEvents();
        }
    }

    function renderStepUpload() {
        const count = state.files.length;
        return `
            <div class="flex items-center gap-3 mb-3">
                <span class="flex items-center justify-center w-8 h-8 rounded-full bg-blue-600 text-white font-bold text-sm">1</span>
                <h2 class="text-lg font-semibold text-gray-800">上传照片</h2>
            </div>
            <div class="border-2 border-dashed border-gray-300 rounded-xl p-8 text-center hover:border-blue-400 transition-colors cursor-pointer bg-gray-50"
                 id="drop-zone">
                <svg class="mx-auto h-12 w-12 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5"
                          d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z"/>
                </svg>
                <p class="mt-2 text-sm text-gray-600">
                    <span class="font-medium text-blue-600">点击上传</span>、拖拽照片 或 <span class="font-medium text-blue-600">Ctrl+V 粘贴</span>
                </p>
                <p class="text-xs text-gray-400 mt-1">支持 JPG、PNG 格式，可一次多选 · 从文件夹复制文件后在此页面粘贴即可</p>
                <input type="file" id="file-input" multiple accept=".jpg,.jpeg,.png" class="hidden">
            </div>
            ${count > 0 ? `
                <div class="mt-3 flex items-center gap-2 text-sm text-green-700 bg-green-50 px-3 py-2 rounded-lg">
                    <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"/>
                    </svg>
                    已上传 <strong>${count}</strong> 张照片（按文件名排序）
                </div>` : ''}
            ${count > 0 ? `
                <div class="mt-3 text-xs text-gray-500">
                    排序预览：${state.files.slice(0, 5).map(f => f.filename).join('、')}${count > 5 ? '...' : ''}
                </div>` : ''}
        `;
    }

    function renderStepNames() {
        const mode = state.namelistMode;
        const nameCount = state.names.length;
        return `
            <div class="flex items-center gap-3 mb-3">
                <span class="flex items-center justify-center w-8 h-8 rounded-full bg-blue-600 text-white font-bold text-sm">2</span>
                <h2 class="text-lg font-semibold text-gray-800">命名方式</h2>
            </div>
            <div class="space-y-3">
                <label class="flex items-center gap-2 cursor-pointer">
                    <input type="radio" name="name-mode" value="filename" ${mode === 'filename' ? 'checked' : ''}
                           class="w-4 h-4 text-blue-600">
                    <span class="text-sm text-gray-700">使用原文件名（去掉扩展名）</span>
                </label>
                <label class="flex items-center gap-2 cursor-pointer">
                    <input type="radio" name="name-mode" value="namelist" ${mode === 'namelist' ? 'checked' : ''}
                           class="w-4 h-4 text-blue-600">
                    <span class="text-sm text-gray-700">匹配名单文件</span>
                </label>
                <div id="namelist-area" style="${mode === 'namelist' ? '' : 'display: none;'}">
                    <div class="flex gap-2 mt-2">
                        <button id="upload-xlsx-btn" class="px-4 py-2 bg-white border border-gray-300 rounded-lg text-sm hover:bg-gray-50 transition">
                            📊 上传 Excel (.xlsx)
                        </button>
                        <button id="upload-txt-btn" class="px-4 py-2 bg-white border border-gray-300 rounded-lg text-sm hover:bg-gray-50 transition">
                            📄 上传文本 (.txt)
                        </button>
                        <button id="download-template-btn" class="px-3 py-2 text-sm text-blue-600 hover:underline">
                            下载模板
                        </button>
                        <input type="file" id="namelist-file-input" accept=".xlsx,.xls,.txt,.csv" class="hidden">
                    </div>
                    ${state.columns.length > 0 ? `
                        <div class="mt-3">
                            <label class="text-sm text-gray-600">姓名列：</label>
                            <select id="column-select" class="ml-2 px-3 py-1.5 border border-gray-300 rounded-lg text-sm">
                                ${state.columns.map(c => `<option value="${c}" ${c === state.selectedColumn ? 'selected' : ''}>${c}</option>`).join('')}
                            </select>
                        </div>` : ''}
                    ${nameCount > 0 ? `
                        <div class="mt-3 flex items-center gap-2 text-sm text-green-700 bg-green-50 px-3 py-2 rounded-lg">
                            <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"/>
                            </svg>
                            名单已加载：<strong>${nameCount}</strong> 个名字${nameCount !== state.files.length ? `（照片 ${state.files.length} 张）` : ''}
                            ${nameCount !== state.files.length ? `<span class="text-amber-600 ml-1">⚠数量不匹配</span>` : ''}
                        </div>` : ''}
                    ${nameCount > 0 && state.files.length > 0 ? `
                        <div class="mt-2 p-3 bg-gray-50 rounded-lg text-xs text-gray-600 max-h-32 overflow-y-auto" id="match-preview">
                            ${state.files.slice(0, 10).map((f, i) => {
                                const name = i < state.names.length ? state.names[i] : '?';
                                return `<div class="py-0.5">${i + 1}. <span class="font-mono">${f.filename}</span> → <span class="font-medium">${name}</span></div>`;
                            }).join('')}
                            ${state.files.length > 10 ? `<div class="text-gray-400 mt-1">...共 ${state.files.length} 张</div>` : ''}
                        </div>` : ''}
                </div>
            </div>
        `;
    }

    function renderStepOptions() {
        return `
            <div class="flex items-center gap-3 mb-3">
                <span class="flex items-center justify-center w-8 h-8 rounded-full bg-blue-600 text-white font-bold text-sm">3</span>
                <h2 class="text-lg font-semibold text-gray-800">输出选项</h2>
            </div>
            <div class="flex gap-6">
                <label class="flex items-center gap-2 cursor-pointer">
                    <input type="checkbox" id="opt-badge" ${state.badgePhoto ? 'checked' : ''}
                           class="w-4 h-4 text-blue-600 rounded">
                    <span class="text-sm text-gray-700">📷 工牌照（头像+肩部 · 3:4 · 1080×1440 · JPG）</span>
                </label>
                <label class="flex items-center gap-2 cursor-pointer">
                    <input type="checkbox" id="opt-seat" ${state.seatCard ? 'checked' : ''}
                           class="w-4 h-4 text-blue-600 rounded">
                    <span class="text-sm text-gray-700">🪑 座位牌（头顶到腰部 · 3:4 · 1080×1440 · JPG）</span>
                </label>
            </div>
        `;
    }

    function renderStepProcess() {
        const canStart = state.sessionId && (state.badgePhoto || state.seatCard);
        return `
            <div class="flex items-center gap-3 mb-3">
                <span class="flex items-center justify-center w-8 h-8 rounded-full bg-blue-600 text-white font-bold text-sm">4</span>
                <h2 class="text-lg font-semibold text-gray-800">处理 & 下载</h2>
            </div>
            <button id="start-btn" ${canStart ? '' : 'disabled'}
                    class="px-6 py-3 ${canStart ? 'bg-blue-600 hover:bg-blue-700 cursor-pointer' : 'bg-gray-300 cursor-not-allowed'}
                           text-white font-medium rounded-lg transition text-lg shadow-sm">
                🚀 开始处理
            </button>
            <div id="progress-area" class="mt-4" style="display: none;"></div>
            <div id="download-area" class="mt-4" style="display: none;"></div>
        `;
    }

    // ---- Events ----
    function bindEvents() {
        // Tab switching
        const tabPhoto = $('#tab-photo');
        const tabExcel = $('#tab-excel');
        tabPhoto?.addEventListener('click', () => {
            if (state.activeTab !== 'photo') {
                // Clean up SSE connection when switching away
                if (state.eventSource) {
                    state.eventSource.close();
                    state.eventSource = null;
                }
                state.activeTab = 'photo';
                render();
            }
        });
        tabExcel?.addEventListener('click', () => {
            if (state.activeTab !== 'excel') {
                // Clean up SSE connection when switching away
                if (state.eventSource) {
                    state.eventSource.close();
                    state.eventSource = null;
                }
                state.activeTab = 'excel';
                render();
            }
        });

        // Drop zone
        const dropZone = $('#drop-zone');
        const fileInput = $('#file-input');

        if (dropZone) {
            dropZone.addEventListener('click', () => fileInput?.click());

            dropZone.addEventListener('dragover', (e) => {
                e.preventDefault();
                dropZone.classList.add('border-blue-400', 'bg-blue-50');
            });
            dropZone.addEventListener('dragleave', () => {
                dropZone.classList.remove('border-blue-400', 'bg-blue-50');
            });
            dropZone.addEventListener('drop', (e) => {
                e.preventDefault();
                dropZone.classList.remove('border-blue-400', 'bg-blue-50');
                const files = e.dataTransfer?.files;
                if (files && files.length) handlePhotoUpload(files);
            });
        }

        if (fileInput) {
            fileInput.addEventListener('change', () => {
                if (fileInput.files && fileInput.files.length) handlePhotoUpload(fileInput.files);
            });
        }

        // ── Global paste-to-upload (photo tab only) ──
        document.addEventListener('paste', (e) => {
            // Only handle paste when photo tab is active and not in an input field
            if (state.activeTab !== 'photo') return;
            const target = e.target;
            if (target && (target.tagName === 'INPUT' || target.tagName === 'TEXTAREA' || target.isContentEditable)) return;
            const items = e.clipboardData?.items;
            if (!items) return;
            const files = [];
            for (const item of items) {
                if (item.kind === 'file') {
                    files.push(item.getAsFile());
                }
            }
            if (files.length > 0) {
                e.preventDefault();
                handlePhotoUpload(files);
            }
        });

        // Name mode radio
        $$('input[name="name-mode"]').forEach(r => {
            r.addEventListener('change', (e) => {
                state.namelistMode = e.target.value;
                render();
            });
        });

        // Upload name list buttons
        const xlsxBtn = $('#upload-xlsx-btn');
        const txtBtn = $('#upload-txt-btn');
        const templateBtn = $('#download-template-btn');
        const namelistInput = $('#namelist-file-input');

        xlsxBtn?.addEventListener('click', () => {
            if (namelistInput) {
                namelistInput.accept = '.xlsx,.xls';
                namelistInput.click();
            }
        });
        txtBtn?.addEventListener('click', () => {
            if (namelistInput) {
                namelistInput.accept = '.txt,.csv';
                namelistInput.click();
            }
        });
        namelistInput?.addEventListener('change', () => {
            if (namelistInput.files && namelistInput.files.length) {
                handleNamelistUpload(namelistInput.files[0]);
            }
        });
        templateBtn?.addEventListener('click', (e) => {
            e.preventDefault();
            API.downloadNamelistTemplate();
        });

        // Column select
        const colSelect = $('#column-select');
        colSelect?.addEventListener('change', async (e) => {
            await handleColumnSelect(e.target.value);
        });

        // Output options
        const optBadge = $('#opt-badge');
        const optSeat = $('#opt-seat');
        optBadge?.addEventListener('change', () => {
            state.badgePhoto = optBadge.checked;
            render();
        });
        optSeat?.addEventListener('change', () => {
            state.seatCard = optSeat.checked;
            render();
        });

        // Start button
        const startBtn = $('#start-btn');
        startBtn?.addEventListener('click', handleStartProcess);
    }

    // ---- Handlers ----
    async function handlePhotoUpload(files) {
        const arrFiles = Array.from(files).filter(f => {
            const ext = f.name.split('.').pop()?.toLowerCase();
            return ext === 'jpg' || ext === 'jpeg' || ext === 'png';
        });

        if (arrFiles.length === 0) {
            alert('请选择 JPG 或 PNG 格式的照片');
            return;
        }

        // Show loading state in the upload area
        const dropZone = $('#drop-zone');
        if (dropZone) {
            dropZone.innerHTML = `<div class="loading-spinner mx-auto"></div><p class="text-sm text-gray-500 mt-3">正在上传 ${arrFiles.length} 张照片...</p>`;
        }

        try {
            const result = await API.uploadPhotos(arrFiles);
            state.sessionId = result.session_id;
            state.files = result.files;
            state.jobId = null;
            state.names = [];
            state.namelistMode = 'filename';
            state.columns = [];
            state.selectedColumn = null;
            render();
        } catch (err) {
            alert('上传失败：' + err.message);
            render();
        }
    }

    async function handleNamelistUpload(file) {
        if (!state.sessionId) {
            alert('请先上传照片');
            return;
        }
        try {
            const result = await API.uploadNamelist(state.sessionId, file);
            if (result.columns.length > 0) {
                state.columns = result.columns;
                state.selectedColumn = result.suggested_name_column || result.columns[0];
                state.suggestedColumn = result.suggested_name_column;
            }
            state.names = result.names_preview || [];
            // Reload full column info to get complete preview
            if (state.columns.length > 0) {
                await loadColumnInfo();
            }
            state.namelistMode = 'namelist';
            render();
        } catch (err) {
            alert('名单上传失败：' + err.message);
        }
    }

    async function handleColumnSelect(columnName) {
        if (!state.sessionId) return;
        try {
            const result = await API.selectNameColumn(state.sessionId, columnName);
            state.selectedColumn = columnName;
            state.names = [];
            // Rebuild names from preview
            for (const item of result.preview) {
                state.names.push(item.name);
            }
            // Need to reload for full list
            await loadColumnInfo();
            render();
        } catch (err) {
            alert('列选择失败：' + err.message);
        }
    }

    async function loadColumnInfo() {
        try {
            const info = await API.getNamelistColumns(state.sessionId);
            state.names = [];
            for (const item of info.preview) {
                state.names.push(item.name);
            }
            // If there are more names, get them
            if (info.name_count > info.preview.length) {
                state.names = [];
                for (let i = 0; i < info.name_count; i++) {
                    state.names.push(info.preview[i]?.name || `第${i+1}个`);
                }
            }
            state.columns = info.columns;
            state.selectedColumn = info.current || info.suggested;
        } catch (err) {
            console.error('Failed to load column info:', err);
        }
    }

    async function handleStartProcess() {
        if (!state.sessionId) return;
        if (!state.badgePhoto && !state.seatCard) {
            alert('请至少选择一种输出类型（工牌照 或 座位牌）');
            return;
        }

        try {
            const result = await API.startProcess(state.sessionId, {
                badge_photo: state.badgePhoto,
                seat_card: state.seatCard,
                namelist_mode: state.namelistMode,
            });

            state.jobId = result.job_id;

            // Show progress area
            const progressArea = $('#progress-area');
            const startBtn = $('#start-btn');
            if (startBtn) startBtn.disabled = true;
            if (progressArea) {
                progressArea.style.display = 'block';
                progressArea.innerHTML = `
                    <div class="p-4 bg-blue-50 rounded-xl">
                        <p class="text-sm text-blue-700 font-medium mb-2">正在处理中...</p>
                        <div class="w-full bg-gray-200 rounded-full h-4 mb-2">
                            <div id="progress-bar" class="bg-blue-600 h-4 rounded-full transition-all duration-300" style="width: 0%"></div>
                        </div>
                        <p class="text-xs text-gray-500" id="progress-text">准备中...</p>
                    </div>`;
            }

            // Subscribe to progress
            state.eventSource = API.subscribeProgress(
                state.jobId,
                // onProgress
                (data) => {
                    const pct = data.total > 0 ? Math.round((data.progress / data.total) * 100) : 0;
                    const bar = $('#progress-bar');
                    const text = $('#progress-text');
                    if (bar) bar.style.width = pct + '%';
                    if (text) {
                        let msg = `处理中: ${data.progress}/${data.total}`;
                        if (data.current_file) msg += ` — ${data.current_file}`;
                        text.textContent = msg;
                    }
                    if (data.warning) {
                        const area = $('#progress-area');
                        if (area && !area.querySelector('.warning-msg')) {
                            const warn = document.createElement('p');
                            warn.className = 'text-sm text-amber-600 mt-2 warning-msg';
                            warn.textContent = '⚠ ' + data.warning;
                            area.appendChild(warn);
                        }
                    }
                },
                // onComplete
                (data) => {
                    const downloadArea = $('#download-area');
                    const bar = $('#progress-bar');
                    const text = $('#progress-text');

                    if (bar) bar.style.width = '100%';

                    // Check for server-side error
                    if (data.status === 'error') {
                        if (text) text.textContent = '❌ 处理失败';
                        if (downloadArea) {
                            downloadArea.style.display = 'block';
                            downloadArea.innerHTML = `
                                <div class="p-4 bg-red-50 rounded-xl">
                                    <p class="text-sm text-red-700 font-medium mb-2">❌ 处理过程中发生错误</p>
                                    <p class="text-xs text-red-600 mb-3">${data.error_message || '未知错误'}</p>
                                    <button id="restart-btn" class="px-6 py-2.5 bg-gray-200 hover:bg-gray-300 text-gray-700 font-medium rounded-lg transition">
                                        🔄 重新处理
                                    </button>
                                </div>`;
                            $('#restart-btn')?.addEventListener('click', () => {
                                state.jobId = null;
                                render();
                            });
                        }
                        return;
                    }

                    if (text) text.textContent = '✅ 全部完成！';
                    if (downloadArea) {
                        downloadArea.style.display = 'block';
                        downloadArea.innerHTML = `
                            <div class="p-4 bg-green-50 rounded-xl">
                                <p class="text-sm text-green-700 font-medium mb-3">✅ 处理完成！共 ${data.total} 张照片</p>
                                ${(data.errors || []).length > 0 ? `
                                    <div class="text-xs text-red-600 mb-2">
                                        ${data.errors.map(e => `⚠ ${e.filename}: ${e.error}`).join('<br>')}
                                    </div>` : ''}
                                <button id="download-btn" class="px-6 py-2.5 bg-green-600 hover:bg-green-700 text-white font-medium rounded-lg transition">
                                    📥 下载 ZIP 文件
                                </button>
                                <button id="restart-btn" class="ml-3 px-6 py-2.5 bg-gray-200 hover:bg-gray-300 text-gray-700 font-medium rounded-lg transition">
                                    🔄 重新处理
                                </button>
                            </div>`;
                        // Bind download — use fetch-based download for better error handling
                        $('#download-btn')?.addEventListener('click', () => downloadWithErrorCheck(state.jobId));
                        $('#restart-btn')?.addEventListener('click', () => {
                            state.sessionId = null;
                            state.files = [];
                            state.names = [];
                            state.namelistMode = 'filename';
                            state.columns = [];
                            state.selectedColumn = null;
                            state.jobId = null;
                            render();
                        });
                    }
                },
                // onError
                (err) => {
                    console.error('SSE error:', err);
                }
            );

        } catch (err) {
            alert('启动处理失败：' + err.message);
        }
    }

    /**
     * Download with error handling — shows alert on failure instead of
     * silently downloading an error JSON as a file.
     */
    async function downloadWithErrorCheck(jobId) {
        const btn = $('#download-btn');
        if (btn) {
            btn.disabled = true;
            btn.textContent = '下载中...';
        }
        try {
            await API.downloadResultWithCheck(jobId);
        } catch (err) {
            alert('下载失败：' + err.message);
            if (btn) {
                btn.disabled = false;
                btn.textContent = '📥 重新下载';
            }
        }
    }

    // ---- Excel Tab ──────────────────────────────────────────────────

    function renderExcelTab() {
        const parsed = state.excelParsed;
        return `
            <div class="mb-6">
                <div class="flex items-center gap-3 mb-3">
                    <span class="flex items-center justify-center w-8 h-8 rounded-full bg-green-600 text-white font-bold text-sm">1</span>
                    <h2 class="text-lg font-semibold text-gray-800">上传在职员工 Excel 原始表</h2>
                </div>
                <div class="border-2 border-dashed border-gray-300 rounded-xl p-8 text-center hover:border-green-400 transition-colors cursor-pointer bg-gray-50"
                     id="excel-drop-zone">
                    <svg class="mx-auto h-12 w-12 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5"
                              d="M9 17v-2m3 2v-4m3 4v-6m2 10H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"/>
                    </svg>
                    <p class="mt-2 text-sm text-gray-600">
                        <span class="font-medium text-green-600">点击上传</span>、拖拽文件 或 <span class="font-medium text-green-600">Ctrl+V 粘贴</span>
                    </p>
                    <p class="text-xs text-gray-400 mt-1">支持从系统导出的在职员工 .xlsx 文件 · 复制文件后在此页面粘贴即可</p>
                    <input type="file" id="excel-file-input" accept=".xlsx,.xls" class="hidden">
                </div>
                ${state.excelFile ? `
                    <div class="mt-3 flex items-center gap-2 text-sm text-green-700 bg-green-50 px-3 py-2 rounded-lg">
                        <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"/>
                        </svg>
                        已上传：<strong>${state.excelFile.name}</strong>（${parsed ? parsed.total_rows + ' 条记录' : '解析中...'}）
                    </div>
                ` : ''}
            </div>

            ${parsed ? `
            <!-- Step 2: Preview & Confirm -->
            <div class="mb-6">
                <div class="flex items-center gap-3 mb-3">
                    <span class="flex items-center justify-center w-8 h-8 rounded-full bg-green-600 text-white font-bold text-sm">2</span>
                    <h2 class="text-lg font-semibold text-gray-800">列映射预览</h2>
                </div>
                <div class="overflow-x-auto">
                    <table class="w-full text-sm border border-gray-200 rounded-lg">
                        <thead>
                            <tr class="bg-blue-50">
                                <th class="px-3 py-2 text-left text-gray-600 border-b">目标字段</th>
                                <th class="px-3 py-2 text-left text-gray-600 border-b">源数据列</th>
                                <th class="px-3 py-2 text-center text-gray-600 border-b">状态</th>
                            </tr>
                        </thead>
                        <tbody>
                            ${renderMappingRow('姓名', parsed)}
                            ${renderMappingRow('英文名/姓名拼音', parsed, '英文名')}
                            ${renderMappingRow('工号', parsed)}
                            ${renderMappingRow('二级部门', parsed)}
                            ${renderMappingRow('三级部门', parsed)}
                            ${renderMappingRow('详细职位名称', parsed, '职位')}
                        </tbody>
                    </table>
                </div>

                <!-- Data preview -->
                <div class="mt-4">
                    <h3 class="text-sm font-medium text-gray-700 mb-2">数据预览（前 5 行）</h3>
                    <div class="overflow-x-auto border border-gray-200 rounded-lg">
                        <table class="w-full text-xs">
                            <thead>
                                <tr class="bg-gray-50">
                                    ${parsed.chinese_headers.map(h => `<th class="px-2 py-1.5 text-left text-gray-500 font-medium border-b">${h}</th>`).join('')}
                                </tr>
                            </thead>
                            <tbody>
                                ${(parsed.preview || []).map(row => `
                                    <tr class="hover:bg-gray-50">
                                        ${Object.values(row).map(v => `<td class="px-2 py-1 border-b text-gray-700">${v}</td>`).join('')}
                                    </tr>
                                `).join('')}
                            </tbody>
                        </table>
                    </div>
                </div>
            </div>

            <!-- Step 3: Generate -->
            <div class="mb-6">
                <div class="flex items-center gap-3 mb-3">
                    <span class="flex items-center justify-center w-8 h-8 rounded-full bg-green-600 text-white font-bold text-sm">3</span>
                    <h2 class="text-lg font-semibold text-gray-800">生成工牌 & 座位牌</h2>
                </div>
                <p class="text-sm text-gray-500 mb-3">
                    将生成包含两个 Sheet 的 Excel 文件：<br>
                    <strong>「工牌」</strong>— 姓名、英文名、工号（按工号排序）<br>
                    <strong>「座位牌」</strong>— 姓名、英文名、工号、二级部门、职位（按部门排序）
                </p>
                <button id="excel-process-btn" ${state.excelProcessing ? 'disabled' : ''}
                        class="px-6 py-3 ${state.excelProcessing ? 'bg-gray-300 cursor-not-allowed' : 'bg-green-600 hover:bg-green-700 cursor-pointer'}
                               text-white font-medium rounded-lg transition text-lg shadow-sm">
                    ${state.excelProcessing ? '⏳ 处理中...' : '📥 生成并下载 Excel'}
                </button>
                ${state.excelProcessing ? '<div class="loading-spinner mt-3"></div>' : ''}
            </div>
            ` : ''}
        `;
    }

    function renderMappingRow(targetField, parsed, fieldKey) {
        const key = fieldKey || targetField;
        const detected = parsed.detected_columns[key];
        if (detected) {
            return `
                <tr>
                    <td class="px-3 py-2 border-b font-medium text-gray-800">${targetField}</td>
                    <td class="px-3 py-2 border-b text-gray-600">${detected.source_column}</td>
                    <td class="px-3 py-2 border-b text-center"><span class="text-green-600">✅ 已匹配</span></td>
                </tr>`;
        } else {
            return `
                <tr>
                    <td class="px-3 py-2 border-b font-medium text-gray-800">${targetField}</td>
                    <td class="px-3 py-2 border-b text-gray-400">—</td>
                    <td class="px-3 py-2 border-b text-center"><span class="text-amber-500">⚠ 未找到</span></td>
                </tr>`;
        }
    }

    function bindExcelEvents() {
        // Drop zone
        const dropZone = $('#excel-drop-zone');
        const fileInput = $('#excel-file-input');

        if (dropZone && fileInput) {
            dropZone.addEventListener('click', () => fileInput.click());
            dropZone.addEventListener('dragover', (e) => {
                e.preventDefault();
                dropZone.classList.add('border-green-400', 'bg-green-50');
            });
            dropZone.addEventListener('dragleave', () => {
                dropZone.classList.remove('border-green-400', 'bg-green-50');
            });
            dropZone.addEventListener('drop', (e) => {
                e.preventDefault();
                dropZone.classList.remove('border-green-400', 'bg-green-50');
                const files = e.dataTransfer?.files;
                if (files && files.length) handleExcelFile(files[0]);
            });
            fileInput.addEventListener('change', () => {
                if (fileInput.files && fileInput.files.length) handleExcelFile(fileInput.files[0]);
            });
        }

        // ── Paste-to-upload for Excel tab ──
        document.addEventListener('paste', (e) => {
            // Only handle paste when Excel tab is active and not in an input field
            if (state.activeTab !== 'excel') return;
            const target = e.target;
            if (target && (target.tagName === 'INPUT' || target.tagName === 'TEXTAREA' || target.isContentEditable)) return;
            const items = e.clipboardData?.items;
            if (!items) return;
            for (const item of items) {
                if (item.kind === 'file') {
                    e.preventDefault();
                    handleExcelFile(item.getAsFile());
                    break;  // Only take the first file for Excel
                }
            }
        });

        // Process button
        const processBtn = $('#excel-process-btn');
        processBtn?.addEventListener('click', handleExcelProcess);
    }

    async function handleExcelFile(file) {
        const ext = file.name.split('.').pop()?.toLowerCase();
        if (ext !== 'xlsx' && ext !== 'xls') {
            alert('请选择 .xlsx 格式的 Excel 文件');
            return;
        }

        // Show loading
        const dropZone = $('#excel-drop-zone');
        if (dropZone) {
            dropZone.innerHTML = `<div class="loading-spinner mx-auto"></div><p class="text-sm text-gray-500 mt-3">正在解析...</p>`;
        }

        try {
            const result = await API.uploadEmployeeExcel(file);
            state.excelFile = file;
            state.excelParsed = result;
            state.excelProcessing = false;
            render();
        } catch (err) {
            alert('解析失败：' + err.message);
            render();
        }
    }

    async function handleExcelProcess() {
        if (!state.excelFile) {
            alert('请先上传 Excel 文件');
            return;
        }

        state.excelProcessing = true;
        render();

        try {
            await API.processEmployeeExcel(state.excelFile);
            state.excelProcessing = false;
            render();
        } catch (err) {
            alert('处理失败：' + err.message);
            state.excelProcessing = false;
            render();
        }
    }

    // ---- Boot ----
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();
