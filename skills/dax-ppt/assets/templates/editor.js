// Editing layer for the live preview: real persistence, undo/redo, a rich-text
// toolbar, chart data editing, and slide insertion.
//
// Everything here talks to the local edit server (edit_server.py). When the
// page is opened over file:// there is no server, so the UI degrades to
// read-only and says so rather than pretending edits are saved.
(function () {
    const API_BASE = location.origin;
    // Set early in the page so init code running before this script agrees.
    const HAS_SERVER = window.__editorHasServer === true;

    // ---------------------------------------------------------------- utils
    function toast(msg, type) { if (window.showToast) window.showToast(msg, type || 'success'); }

    async function api(path, options) {
        const res = await fetch(API_BASE + path, Object.assign({
            headers: { 'Content-Type': 'application/json' }
        }, options));
        let data = {};
        try { data = await res.json(); } catch (e) {}
        if (!res.ok || data.error) throw new Error(data.error || ('HTTP ' + res.status));
        return data;
    }

    function slideNumberOf(card) {
        return parseInt(card.dataset.slideNumber ||
            (card.querySelector('.slide-content') || {}).dataset?.slideNumber || '0', 10);
    }

    // Serialise a card's slide body back to storable HTML: the scoped <style>
    // is preview-only chrome, and editing attributes must never be persisted.
    function bodyHtmlOf(card) {
        const content = card.querySelector('.slide-content');
        if (!content) return null;
        const clone = content.cloneNode(true);
        clone.querySelectorAll('style').forEach(s => s.remove());
        clone.querySelectorAll('[contenteditable]').forEach(el => el.removeAttribute('contenteditable'));
        clone.querySelectorAll('.chart-embed[data-chart-id]').forEach(el => {
            el.removeAttribute('data-chart-rendered');
            el.querySelectorAll('canvas').forEach(c => c.remove());
        });
        clone.querySelectorAll('[data-editor-ui]').forEach(el => el.remove());
        return clone.innerHTML.trim();
    }

    // ---------------------------------------------------------------- state
    const dirtySlides = new Set();
    let saving = false;
    let statusEl = null;

    function setStatus(text, tone) {
        if (!statusEl) return;
        statusEl.textContent = text;
        statusEl.dataset.tone = tone || '';
    }

    function markSlideDirty(card) {
        if (!card) return;
        dirtySlides.add(card);
        card.classList.add('has-unsaved');
        setStatus('Unsaved changes', 'warn');
        scheduleAutosave();
    }

    let autosaveTimer = null;
    function scheduleAutosave() {
        if (!HAS_SERVER) return;
        clearTimeout(autosaveTimer);
        autosaveTimer = setTimeout(() => { saveAll(true); }, 2500);
    }

    async function saveAll(isAuto) {
        if (!HAS_SERVER) {
            toast('Opened without the edit server - changes cannot be saved', 'error');
            return false;
        }
        if (saving || dirtySlides.size === 0) return true;
        saving = true;
        setStatus('Saving...', '');
        const cards = Array.from(dirtySlides);
        let ok = 0, failed = 0;

        for (const card of cards) {
            const n = slideNumberOf(card);
            const body = bodyHtmlOf(card);
            if (!n || body === null) { failed++; continue; }
            try {
                await api('/api/slide/' + n, { method: 'POST', body: JSON.stringify({ body_html: body }) });
                dirtySlides.delete(card);
                card.classList.remove('has-unsaved');
                ok++;
            } catch (e) {
                failed++;
                console.error('Save failed for slide', n, e);
            }
        }

        saving = false;
        if (failed) {
            setStatus(failed + ' slide(s) failed to save', 'error');
            toast('Could not save ' + failed + ' slide(s)', 'error');
            return false;
        }
        setStatus('All changes saved', 'ok');
        if (!isAuto && ok) toast('Saved ' + ok + ' slide(s) to disk', 'success');
        if (ok) verifyDirty(cards);
        return true;
    }

    // Post-save overflow check: a hand-typed longer title can silently overflow.
    async function verifyDirty(cards) {
        for (const card of cards) {
            const n = slideNumberOf(card);
            if (!n) continue;
            try {
                const r = await api('/api/verify/' + n, { method: 'POST', body: '{}' });
                const badge = card.querySelector('.overflow-badge');
                if (r.overflow_detected) {
                    if (badge) badge.remove();
                    const el = document.createElement('span');
                    el.className = 'overflow-badge';
                    el.textContent = 'Overflows 720px';
                    el.title = (r.issues || []).join('\n');
                    card.querySelector('.slide-card-header').appendChild(el);
                } else if (badge) {
                    badge.remove();
                }
            } catch (e) { /* verification is advisory */ }
        }
    }

    // ---------------------------------------------------------------- undo
    // Snapshot-based: each entry restores one card's innerHTML, or replays a
    // structural deck operation. Structural ops are saved immediately, so undo
    // for those re-issues the inverse against the server.
    const undoStack = [];
    const redoStack = [];
    const MAX_UNDO = 60;

    function pushUndo(entry) {
        undoStack.push(entry);
        if (undoStack.length > MAX_UNDO) undoStack.shift();
        redoStack.length = 0;
        updateUndoButtons();
    }

    function snapshotCard(card) {
        const content = card.querySelector('.slide-content');
        return { type: 'content', card, html: content ? content.innerHTML : '' };
    }

    function applyContentSnapshot(entry) {
        const content = entry.card.querySelector('.slide-content');
        if (!content) return null;
        const current = content.innerHTML;
        content.innerHTML = entry.html;
        if (window.__renderCharts) window.__renderCharts();
        markSlideDirty(entry.card);
        return { type: 'content', card: entry.card, html: current };
    }

    async function undo() {
        const entry = undoStack.pop();
        if (!entry) { toast('Nothing to undo', 'error'); return; }
        if (entry.type === 'content') {
            const inverse = applyContentSnapshot(entry);
            if (inverse) redoStack.push(inverse);
        } else if (entry.type === 'deck') {
            try {
                await entry.undo();
                redoStack.push(entry);
                toast('Undid ' + entry.label, 'success');
            } catch (e) {
                toast('Could not undo: ' + e.message, 'error');
            }
        }
        updateUndoButtons();
    }

    async function redo() {
        const entry = redoStack.pop();
        if (!entry) { toast('Nothing to redo', 'error'); return; }
        if (entry.type === 'content') {
            const inverse = applyContentSnapshot(entry);
            if (inverse) undoStack.push(inverse);
        } else if (entry.type === 'deck') {
            try {
                await entry.redo();
                undoStack.push(entry);
                toast('Redid ' + entry.label, 'success');
            } catch (e) {
                toast('Could not redo: ' + e.message, 'error');
            }
        }
        updateUndoButtons();
    }

    function updateUndoButtons() {
        const u = document.getElementById('undo-btn');
        const r = document.getElementById('redo-btn');
        if (u) u.disabled = undoStack.length === 0;
        if (r) r.disabled = redoStack.length === 0;
    }

    // Capture a snapshot before the first keystroke of an editing burst.
    let burstCard = null;
    let burstTimer = null;
    function noteEditBurst(card) {
        if (burstCard !== card) {
            pushUndo(snapshotCard(card));
            burstCard = card;
        }
        clearTimeout(burstTimer);
        burstTimer = setTimeout(() => { burstCard = null; }, 900);
    }

    // ---------------------------------------------------------------- format
    const FORMAT_BAR_ID = 'format-bar';

    function ensureFormatBar() {
        let bar = document.getElementById(FORMAT_BAR_ID);
        if (bar) return bar;
        bar = document.createElement('div');
        bar.id = FORMAT_BAR_ID;
        bar.className = 'format-bar';
        bar.innerHTML = `
            <button data-cmd="bold" title="Bold (Ctrl/Cmd+B)"><b>B</b></button>
            <button data-cmd="italic" title="Italic (Ctrl/Cmd+I)"><i>I</i></button>
            <button data-cmd="underline" title="Underline (Ctrl/Cmd+U)"><u>U</u></button>
            <span class="format-sep"></span>
            <button data-size="-" title="Decrease font size">A&minus;</button>
            <button data-size="+" title="Increase font size">A+</button>
            <span class="format-sep"></span>
            <button data-color="#12263F" title="Navy"><span class="swatch" style="background:#12263F"></span></button>
            <button data-color="#00A0DC" title="Brand blue"><span class="swatch" style="background:#00A0DC"></span></button>
            <button data-color="#1F7A5C" title="Positive"><span class="swatch" style="background:#1F7A5C"></span></button>
            <button data-color="#B3341F" title="Negative"><span class="swatch" style="background:#B3341F"></span></button>
            <button data-color="#3C4456" title="Body"><span class="swatch" style="background:#3C4456"></span></button>
            <span class="format-sep"></span>
            <button data-align="left" title="Align left">&#8676;</button>
            <button data-align="center" title="Align center">&#8596;</button>
            <button data-align="right" title="Align right">&#8677;</button>
            <span class="format-sep"></span>
            <button data-clear="1" title="Clear formatting">&#10005;</button>`;
        document.body.appendChild(bar);

        // mousedown (not click) so the selection isn't lost before we act
        bar.addEventListener('mousedown', (e) => {
            const btn = e.target.closest('button');
            if (!btn) return;
            e.preventDefault();
            applyFormat(btn);
        });
        return bar;
    }

    function activeEditableCard() {
        const sel = window.getSelection();
        if (!sel || sel.rangeCount === 0) return null;
        let node = sel.getRangeAt(0).commonAncestorContainer;
        if (node.nodeType === Node.TEXT_NODE) node = node.parentElement;
        if (!node || !node.closest) return null;
        const editable = node.closest('[contenteditable="true"]');
        return editable ? editable.closest('.slide-card') : null;
    }

    function applyFormat(btn) {
        const card = activeEditableCard();
        if (!card) return;
        noteEditBurst(card);

        if (btn.dataset.cmd) {
            document.execCommand(btn.dataset.cmd, false, null);
        } else if (btn.dataset.color) {
            document.execCommand('foreColor', false, btn.dataset.color);
        } else if (btn.dataset.align) {
            const map = { left: 'justifyLeft', center: 'justifyCenter', right: 'justifyRight' };
            document.execCommand(map[btn.dataset.align], false, null);
        } else if (btn.dataset.clear) {
            document.execCommand('removeFormat', false, null);
        } else if (btn.dataset.size) {
            adjustFontSize(btn.dataset.size === '+' ? 1 : -1);
        }
        markSlideDirty(card);
        positionFormatBar();
    }

    // execCommand has no relative sizing, so scale the containing block's
    // computed px size - that matches how the design system sizes text.
    function adjustFontSize(direction) {
        const sel = window.getSelection();
        if (!sel || sel.rangeCount === 0) return;
        let node = sel.getRangeAt(0).commonAncestorContainer;
        if (node.nodeType === Node.TEXT_NODE) node = node.parentElement;
        const target = node && node.closest ? node.closest('[contenteditable="true"]') : null;
        if (!target) return;
        const current = parseFloat(window.getComputedStyle(target).fontSize) || 14;
        const next = Math.max(7, Math.min(72, current + direction));
        target.style.fontSize = next.toFixed(1) + 'px';
    }

    function positionFormatBar() {
        const bar = document.getElementById(FORMAT_BAR_ID);
        if (!bar) return;
        const sel = window.getSelection();
        if (!sel || sel.rangeCount === 0 || sel.isCollapsed || !activeEditableCard()) {
            bar.classList.remove('visible');
            return;
        }
        const rect = sel.getRangeAt(0).getBoundingClientRect();
        if (!rect.width && !rect.height) { bar.classList.remove('visible'); return; }
        bar.classList.add('visible');
        const barRect = bar.getBoundingClientRect();
        let left = rect.left + rect.width / 2 - barRect.width / 2;
        left = Math.max(8, Math.min(window.innerWidth - barRect.width - 8, left));
        let top = rect.top - barRect.height - 10;
        if (top < 70) top = rect.bottom + 10;
        bar.style.left = left + 'px';
        bar.style.top = top + 'px';
    }

    document.addEventListener('selectionchange', () => {
        if (window.isEditModeActive && window.isEditModeActive()) positionFormatBar();
    });

    // ---------------------------------------------------------------- charts
    async function openChartEditor(chartId, card) {
        let spec;
        try {
            spec = (await api('/api/chart/' + chartId)).spec;
        } catch (e) {
            toast('Could not load chart: ' + e.message, 'error');
            return;
        }

        const overlay = document.createElement('div');
        overlay.className = 'chart-editor-overlay visible';
        const rows = spec.categories.map((cat, i) => {
            const cells = spec.series.map((s, si) =>
                `<td><input class="chart-cell" data-series="${si}" data-row="${i}" type="number" step="any" value="${s.values[i]}"></td>`
            ).join('');
            return `<tr><td><input class="chart-cat" data-row="${i}" value="${String(cat).replace(/"/g, '&quot;')}"></td>${cells}</tr>`;
        }).join('');
        const heads = spec.series.map((s, si) =>
            `<th><input class="chart-series-name" data-series="${si}" value="${String(s.name).replace(/"/g, '&quot;')}"></th>`
        ).join('');

        overlay.innerHTML = `
            <div class="chart-editor-panel">
                <div class="chart-editor-header">
                    <h3>Edit chart data &mdash; ${chartId}</h3>
                    <button class="chart-editor-close" title="Close">&#10005;</button>
                </div>
                <div class="chart-editor-body">
                    <label class="chart-editor-field">
                        Chart type
                        <select class="chart-type">
                            ${['column','bar','line','area','pie','doughnut','column_stacked','bar_stacked','waterfall']
                                .map(t => `<option value="${t}"${t === spec.type ? ' selected' : ''}>${t}</option>`).join('')}
                        </select>
                    </label>
                    <div class="chart-table-wrap">
                        <table class="chart-table">
                            <thead><tr><th>Category</th>${heads}</tr></thead>
                            <tbody>${rows}</tbody>
                        </table>
                    </div>
                    <p class="chart-editor-hint">Saving updates the stored chart spec, so the preview and the
                    native PowerPoint chart in the export both use the new numbers.</p>
                </div>
                <div class="chart-editor-footer">
                    <button class="chart-editor-cancel">Cancel</button>
                    <button class="chart-editor-save">Save chart</button>
                </div>
            </div>`;
        document.body.appendChild(overlay);

        const close = () => overlay.remove();
        overlay.querySelector('.chart-editor-close').addEventListener('click', close);
        overlay.querySelector('.chart-editor-cancel').addEventListener('click', close);
        overlay.addEventListener('click', (e) => { if (e.target === overlay) close(); });

        overlay.querySelector('.chart-editor-save').addEventListener('click', async () => {
            const categories = Array.from(overlay.querySelectorAll('.chart-cat')).map(i => i.value);
            const series = spec.series.map((s, si) => ({
                name: overlay.querySelector(`.chart-series-name[data-series="${si}"]`).value,
                values: categories.map((_, ri) => {
                    const cell = overlay.querySelector(`.chart-cell[data-series="${si}"][data-row="${ri}"]`);
                    return parseFloat(cell.value) || 0;
                })
            }));
            const payload = { categories, series, type: overlay.querySelector('.chart-type').value };
            try {
                await api('/api/chart/' + chartId, { method: 'POST', body: JSON.stringify(payload) });
                close();
                toast('Chart updated - reloading preview', 'success');
                setTimeout(() => location.reload(), 600);
            } catch (e) {
                toast('Could not save chart: ' + e.message, 'error');
            }
        });
    }

    function attachChartEditButtons() {
        document.querySelectorAll('.chart-embed[data-chart-id]').forEach((el) => {
            if (el.querySelector('.chart-edit-btn')) return;
            const card = el.closest('.slide-card');
            const btn = document.createElement('button');
            btn.className = 'chart-edit-btn';
            btn.type = 'button';
            btn.dataset.editorUi = '1';
            btn.textContent = 'Edit data';
            btn.title = 'Edit this chart’s data';
            btn.addEventListener('click', (e) => {
                e.stopPropagation();
                if (!HAS_SERVER) { toast('Chart editing needs the edit server', 'error'); return; }
                openChartEditor(el.dataset.chartId, card);
            });
            if (!el.style.position) el.style.position = 'relative';
            el.appendChild(btn);
        });
    }

    // ---------------------------------------------------------------- deck ops
    // Structural ops rewrite slide files and then reload the page. Guard against
    // a second op firing during that window (double-click, or a click landing
    // while the reload is still in flight) - it would insert/delete twice.
    let deckOpInFlight = false;

    async function deckOp(label, doFn, undoFn, redoFn) {
        if (deckOpInFlight) return;
        deckOpInFlight = true;
        try {
            await doFn();
            pushUndo({ type: 'deck', label, undo: undoFn, redo: redoFn });
            toast(label + ' saved', 'success');
            setTimeout(() => location.reload(), 500);
        } catch (e) {
            deckOpInFlight = false;
            toast('Could not ' + label.toLowerCase() + ': ' + e.message, 'error');
        }
    }

    window.__deckOpBusy = () => deckOpInFlight;
    window.__beginDeckOp = () => {
        if (deckOpInFlight) return false;
        deckOpInFlight = true;
        return true;
    };
    window.__endDeckOp = () => { deckOpInFlight = false; };

    function currentOrder() {
        return Array.from(document.querySelectorAll('.slide-card')).map(slideNumberOf).filter(Boolean);
    }

    async function persistOrder(order) {
        return api('/api/deck/reorder', { method: 'POST', body: JSON.stringify({ order }) });
    }

    // ---------------------------------------------------------------- clipboard
    // PowerPoint-style slide clipboard: copy/cut/paste whole slides.
    let slideClipboard = null;   // {html, sourceNumber, cut}

    async function copySlide(cut) {
        if (!HAS_SERVER) { toast('Copying slides needs the edit server', 'error'); return; }
        const card = currentCard();
        if (!card) return;
        const n = slideNumberOf(card);
        try {
            const r = await api('/api/slide/' + n + '/html');
            slideClipboard = { html: r.html, sourceNumber: n, cut: !!cut };
            try { sessionStorage.setItem('pptmk-clipboard', JSON.stringify(slideClipboard)); } catch (e) {}
            toast(cut ? 'Slide cut' : 'Slide copied', 'success');
            updateClipboardButtons();
        } catch (e) {
            toast('Could not copy slide: ' + e.message, 'error');
        }
    }

    async function pasteSlide() {
        if (!HAS_SERVER) { toast('Pasting slides needs the edit server', 'error'); return; }
        if (!slideClipboard) { toast('Clipboard is empty', 'error'); return; }
        const card = currentCard();
        const after = card ? slideNumberOf(card) : 0;
        const clip = slideClipboard;

        if (!window.__beginDeckOp()) return;
        try {
            await api('/api/deck/paste', {
                method: 'POST',
                body: JSON.stringify({ after, html: clip.html })
            });
            // A cut is paste-then-remove-original; the original shifts if it
            // sat after the insertion point.
            if (clip.cut) {
                const removed = clip.sourceNumber > after ? clip.sourceNumber + 1 : clip.sourceNumber;
                const order = [];
                const total = document.querySelectorAll('.slide-card').length + 1;
                for (let i = 1; i <= total; i++) if (i !== removed) order.push(i);
                await api('/api/deck/reorder', {
                    method: 'POST',
                    body: JSON.stringify({ order, label: 'before cut-paste' })
                });
                slideClipboard = null;
                try { sessionStorage.removeItem('pptmk-clipboard'); } catch (e) {}
            }
            toast('Slide pasted', 'success');
            setTimeout(() => location.reload(), 400);
        } catch (e) {
            window.__endDeckOp();
            toast('Could not paste: ' + e.message, 'error');
        }
    }

    function updateClipboardButtons() {
        const b = document.getElementById('paste-slide-btn');
        if (b) b.disabled = !slideClipboard;
    }

    function currentCard() {
        const cards = Array.from(document.querySelectorAll('.slide-card'));
        const idx = window.currentSlideIndexValue ? window.currentSlideIndexValue() : 0;
        return cards[idx] || cards[0] || null;
    }

    // ---------------------------------------------------------------- layouts
    async function openLayoutGallery(after) {
        let layouts = [];
        try {
            layouts = (await api('/api/layouts')).layouts;
        } catch (e) {
            toast('Could not load layouts: ' + e.message, 'error');
            return;
        }

        const overlay = document.createElement('div');
        overlay.className = 'layout-overlay visible';
        overlay.innerHTML = `
            <div class="layout-panel">
                <div class="layout-header">
                    <h3>New slide</h3>
                    <button class="layout-close" title="Close">&#10005;</button>
                </div>
                <div class="layout-grid">
                    ${layouts.map(l => `
                        <button class="layout-card" data-layout="${l.id}">
                            <span class="layout-thumb layout-thumb-${l.id}"></span>
                            <span class="layout-name">${l.label}</span>
                        </button>`).join('')}
                </div>
            </div>`;
        document.body.appendChild(overlay);

        const close = () => overlay.remove();
        overlay.querySelector('.layout-close').addEventListener('click', close);
        overlay.addEventListener('click', (e) => { if (e.target === overlay) close(); });

        overlay.querySelectorAll('.layout-card').forEach(btn => {
            btn.addEventListener('click', () => {
                const layout = btn.dataset.layout;
                close();
                deckOp('Add slide',
                    () => api('/api/deck/insert', {
                        method: 'POST', body: JSON.stringify({ after, layout })
                    }),
                    async () => {
                        const order = [];
                        const total = document.querySelectorAll('.slide-card').length + 1;
                        for (let i = 1; i <= total; i++) if (i !== after + 1) order.push(i);
                        await persistOrder(order);
                    },
                    () => api('/api/deck/insert', {
                        method: 'POST', body: JSON.stringify({ after, layout })
                    }));
            });
        });
    }

    // ---------------------------------------------------------------- history
    async function openHistory() {
        let versions = [];
        try {
            versions = (await api('/api/history')).versions;
        } catch (e) {
            toast('Could not load history: ' + e.message, 'error');
            return;
        }

        const overlay = document.createElement('div');
        overlay.className = 'layout-overlay visible';
        overlay.innerHTML = `
            <div class="layout-panel" style="max-width:520px;">
                <div class="layout-header">
                    <h3>Version history</h3>
                    <button class="layout-close" title="Close">&#10005;</button>
                </div>
                <div class="history-list">
                    ${versions.length ? versions.map(v => `
                        <div class="history-row">
                            <div>
                                <div class="history-label">${v.label || 'Snapshot'}</div>
                                <div class="history-meta">${formatStamp(v.id)} &middot; ${v.slides} slide(s)</div>
                            </div>
                            <button class="history-restore" data-id="${v.id}">Restore</button>
                        </div>`).join('')
                        : '<p class="chart-editor-hint">No snapshots yet. One is taken automatically before each add, delete, reorder or paste.</p>'}
                </div>
            </div>`;
        document.body.appendChild(overlay);

        const close = () => overlay.remove();
        overlay.querySelector('.layout-close').addEventListener('click', close);
        overlay.addEventListener('click', (e) => { if (e.target === overlay) close(); });

        overlay.querySelectorAll('.history-restore').forEach(btn => {
            btn.addEventListener('click', async () => {
                if (!confirm('Restore this version? The current deck is snapshotted first.')) return;
                try {
                    await api('/api/history/restore', {
                        method: 'POST', body: JSON.stringify({ snapshot_id: btn.dataset.id })
                    });
                    close();
                    toast('Version restored', 'success');
                    setTimeout(() => location.reload(), 500);
                } catch (e) {
                    toast('Could not restore: ' + e.message, 'error');
                }
            });
        });
    }

    function formatStamp(id) {
        const m = /^(\d{4})(\d{2})(\d{2})-(\d{2})(\d{2})(\d{2})/.exec(id);
        if (!m) return id;
        return `${m[3]}/${m[2]} ${m[4]}:${m[5]}:${m[6]}`;
    }

    // ---------------------------------------------------------------- context menu
    function buildContextMenu() {
        const menu = document.createElement('div');
        menu.className = 'ctx-menu';
        menu.id = 'ctx-menu';
        menu.innerHTML = `
            <button data-act="new">New slide<span>&#8862;</span></button>
            <button data-act="duplicate">Duplicate slide<span>&#8984;D</span></button>
            <div class="ctx-sep"></div>
            <button data-act="cut">Cut slide<span>&#8984;X</span></button>
            <button data-act="copy">Copy slide<span>&#8984;C</span></button>
            <button data-act="paste">Paste slide<span>&#8984;V</span></button>
            <div class="ctx-sep"></div>
            <button data-act="up">Move up</button>
            <button data-act="down">Move down</button>
            <div class="ctx-sep"></div>
            <button data-act="notes">Edit speaker notes</button>
            <button data-act="present">Present from here<span>&#8679;F5</span></button>
            <div class="ctx-sep"></div>
            <button data-act="delete" class="danger">Delete slide</button>`;
        document.body.appendChild(menu);

        document.addEventListener('contextmenu', (e) => {
            const card = e.target.closest('.slide-card');
            const thumb = e.target.closest('.thumb');
            if (!card && !thumb) return;
            e.preventDefault();

            // Select whatever was right-clicked first, like PowerPoint does
            const cards = Array.from(document.querySelectorAll('.slide-card'));
            let index = card ? cards.indexOf(card)
                             : Array.from(document.querySelectorAll('.thumb')).indexOf(thumb);
            if (index >= 0 && window.selectSlideAt) window.selectSlideAt(index);

            menu.querySelector('[data-act="paste"]').disabled = !slideClipboard;
            menu.classList.add('visible');
            const w = menu.offsetWidth, h = menu.offsetHeight;
            menu.style.left = Math.min(e.clientX, window.innerWidth - w - 8) + 'px';
            menu.style.top = Math.min(e.clientY, window.innerHeight - h - 8) + 'px';
        });

        document.addEventListener('click', () => menu.classList.remove('visible'));
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape') menu.classList.remove('visible');
        });

        menu.addEventListener('click', (e) => {
            const btn = e.target.closest('button');
            if (!btn || btn.disabled) return;
            menu.classList.remove('visible');
            const act = btn.dataset.act;
            const card = currentCard();
            if (act === 'new') openLayoutGallery(card ? slideNumberOf(card) : 0);
            else if (act === 'duplicate') document.getElementById('duplicate-slide-btn').click();
            else if (act === 'cut') copySlide(true);
            else if (act === 'copy') copySlide(false);
            else if (act === 'paste') pasteSlide();
            else if (act === 'up') document.getElementById('move-up-btn').click();
            else if (act === 'down') document.getElementById('move-down-btn').click();
            else if (act === 'delete') document.getElementById('delete-slide-btn').click();
            else if (act === 'present') {
                if (window.startPresenting) window.startPresenting(true);
            } else if (act === 'notes' && card) {
                const wrap = card.querySelector('.notes-wrap');
                if (wrap) {
                    wrap.classList.add('open');
                    const input = wrap.querySelector('.notes-input');
                    if (input) { input.scrollIntoView({ block: 'center' }); input.focus(); }
                }
            }
        });
    }

    // ---------------------------------------------------------------- drag reorder
    function enableThumbDragReorder() {
        const rail = document.getElementById('thumb-rail');
        if (!rail || rail.dataset.dragReady) return;
        rail.dataset.dragReady = '1';

        let dragIndex = null;

        rail.addEventListener('dragstart', (e) => {
            const thumb = e.target.closest('.thumb');
            if (!thumb) return;
            dragIndex = Array.from(rail.querySelectorAll('.thumb')).indexOf(thumb);
            thumb.classList.add('dragging');
            e.dataTransfer.effectAllowed = 'move';
            try { e.dataTransfer.setData('text/plain', String(dragIndex)); } catch (err) {}
        });

        rail.addEventListener('dragover', (e) => {
            if (dragIndex === null) return;
            e.preventDefault();
            e.dataTransfer.dropEffect = 'move';
            const over = e.target.closest('.thumb');
            rail.querySelectorAll('.thumb').forEach(t => t.classList.remove('drop-before', 'drop-after'));
            if (!over) return;
            const r = over.getBoundingClientRect();
            over.classList.add(e.clientY < r.top + r.height / 2 ? 'drop-before' : 'drop-after');
        });

        rail.addEventListener('drop', async (e) => {
            e.preventDefault();
            const thumbs = Array.from(rail.querySelectorAll('.thumb'));
            const over = e.target.closest('.thumb');
            rail.querySelectorAll('.thumb').forEach(t => t.classList.remove('drop-before', 'drop-after', 'dragging'));
            if (dragIndex === null || !over) { dragIndex = null; return; }

            let target = thumbs.indexOf(over);
            const r = over.getBoundingClientRect();
            if (e.clientY >= r.top + r.height / 2) target += 1;
            if (target > dragIndex) target -= 1;
            const from = dragIndex;
            dragIndex = null;
            if (target === from) return;

            // Slide numbers are 1..N in display order
            const order = [];
            for (let i = 1; i <= thumbs.length; i++) order.push(i);
            const [moved] = order.splice(from, 1);
            order.splice(target, 0, moved);

            if (!window.__beginDeckOp()) return;
            try {
                await api('/api/deck/reorder', {
                    method: 'POST', body: JSON.stringify({ order, label: 'before drag reorder' })
                });
                toast('Slide moved', 'success');
                setTimeout(() => location.reload(), 350);
            } catch (err) {
                window.__endDeckOp();
                toast('Could not reorder: ' + err.message, 'error');
            }
        });

        rail.addEventListener('dragend', () => {
            dragIndex = null;
            rail.querySelectorAll('.thumb').forEach(t =>
                t.classList.remove('dragging', 'drop-before', 'drop-after'));
        });
    }

    // ---------------------------------------------------------------- init
    function buildToolbarButtons() {
        const section = document.querySelector('.edit-bar .edit-actions');
        if (!section) return;

        const mk = (id, title, label, svg) => {
            const b = document.createElement('button');
            b.className = 'edit-bar-btn action-btn';
            b.id = id;
            b.title = title;
            b.innerHTML = svg + `<span>${label}</span>`;
            return b;
        };

        const saveBtn = mk('save-btn', 'Save to disk (Ctrl/Cmd+S)', 'Save',
            '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M19 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11l5 5v11a2 2 0 0 1-2 2z"/><polyline points="17 21 17 13 7 13 7 21"/><polyline points="7 3 7 8 15 8"/></svg>');
        const undoBtn = mk('undo-btn', 'Undo (Ctrl/Cmd+Z)', 'Undo',
            '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 7v6h6"/><path d="M21 17a9 9 0 0 0-9-9 9 9 0 0 0-6 2.3L3 13"/></svg>');
        const redoBtn = mk('redo-btn', 'Redo (Ctrl/Cmd+Shift+Z)', 'Redo',
            '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 7v6h-6"/><path d="M3 17a9 9 0 0 1 9-9 9 9 0 0 1 6 2.3L21 13"/></svg>');

        section.prepend(redoBtn);
        section.prepend(undoBtn);
        section.prepend(saveBtn);

        saveBtn.addEventListener('click', () => saveAll(false));
        undoBtn.addEventListener('click', undo);
        redoBtn.addEventListener('click', redo);
        updateUndoButtons();

        // History lives next to undo/redo - it's durable undo
        const historyBtn = mk('history-btn', 'Version history', 'History',
            '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 3v5h5"/><path d="M3.05 13A9 9 0 1 0 6 5.3L3 8"/><path d="M12 7v5l4 2"/></svg>');
        section.insertBefore(historyBtn, redoBtn.nextSibling);
        historyBtn.addEventListener('click', () => {
            if (!HAS_SERVER) { toast('History needs the edit server', 'error'); return; }
            openHistory();
        });

        // Structural actions: new slide (layout gallery), copy/paste
        const reorder = document.querySelector('.edit-bar .reorder-actions');
        if (reorder) {
            const addBtn = mk('add-slide-btn', 'New slide from a layout (Ctrl/Cmd+M)', 'New',
                '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="4" width="18" height="14" rx="2"/><line x1="12" y1="8" x2="12" y2="14"/><line x1="9" y1="11" x2="15" y2="11"/></svg>');
            const copyBtn = mk('copy-slide-btn', 'Copy slide (Ctrl/Cmd+C)', 'Copy',
                '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="9" y="9" width="13" height="13" rx="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/></svg>');
            const pasteBtn = mk('paste-slide-btn', 'Paste slide (Ctrl/Cmd+V)', 'Paste',
                '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M16 4h2a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2h2"/><rect x="8" y="2" width="8" height="4" rx="1"/></svg>');

            reorder.prepend(pasteBtn);
            reorder.prepend(copyBtn);
            reorder.prepend(addBtn);

            addBtn.addEventListener('click', () => {
                if (!HAS_SERVER) { toast('Adding slides needs the edit server', 'error'); return; }
                const card = currentCard();
                openLayoutGallery(card ? slideNumberOf(card) : 0);
            });
            copyBtn.addEventListener('click', () => copySlide(false));
            pasteBtn.addEventListener('click', pasteSlide);
            updateClipboardButtons();
        }

        // Save status readout
        statusEl = document.createElement('span');
        statusEl.className = 'save-status';
        statusEl.id = 'save-status';
        section.appendChild(statusEl);
        setStatus(HAS_SERVER ? 'All changes saved' : 'Read-only (no edit server)',
                  HAS_SERVER ? 'ok' : 'warn');
    }

    function initNotesFromDisk() {
        document.querySelectorAll('.slide-card').forEach((card) => {
            const dataEl = card.querySelector('.slide-notes-data');
            const input = card.querySelector('.notes-input');
            if (!dataEl || !input) return;
            let text = '';
            try { text = JSON.parse(dataEl.textContent || '""'); } catch (e) {}
            if (text) {
                input.value = text;
                const wrap = card.querySelector('.notes-wrap');
                if (wrap) wrap.classList.add('has-notes');
            }
            // Persist notes to the slide file rather than localStorage.
            let notesTimer = null;
            input.addEventListener('input', () => {
                if (!HAS_SERVER) return;
                clearTimeout(notesTimer);
                notesTimer = setTimeout(async () => {
                    try {
                        await api('/api/slide/' + slideNumberOf(card) + '/notes',
                                  { method: 'POST', body: JSON.stringify({ notes: input.value }) });
                        setStatus('All changes saved', 'ok');
                    } catch (e) {
                        setStatus('Notes failed to save', 'error');
                    }
                }, 900);
            });
        });
    }

    function initEditor() {
        ensureFormatBar();
        buildToolbarButtons();
        initNotesFromDisk();
        attachChartEditButtons();
        buildContextMenu();
        enableThumbDragReorder();

        // Slide clipboard survives the reloads that follow deck operations
        try {
            const stored = sessionStorage.getItem('pptmk-clipboard');
            if (stored) { slideClipboard = JSON.parse(stored); updateClipboardButtons(); }
        } catch (e) {}

        if (!HAS_SERVER) {
            document.body.classList.add('no-edit-server');
        }

        // Snapshot BEFORE the keystroke lands, so undo can restore the text as
        // it was (an 'input' listener alone captures the already-mutated DOM).
        document.addEventListener('keydown', (e) => {
            if (!e.target.isContentEditable) return;
            if (e.metaKey || e.ctrlKey || e.altKey) return;   // shortcuts aren't edits
            const card = e.target.closest('.slide-card');
            if (card) noteEditBurst(card);
        }, true);

        // Track text edits for dirty state (and cover paste / IME input)
        document.addEventListener('input', (e) => {
            if (!e.target.isContentEditable) return;
            const card = e.target.closest('.slide-card');
            if (!card) return;
            noteEditBurst(card);
            markSlideDirty(card);
        });

        // Keyboard: save / undo / redo / slide clipboard / new slide
        document.addEventListener('keydown', (e) => {
            if (window.__presenting) return;
            const mod = e.metaKey || e.ctrlKey;
            if (!mod) return;
            const k = e.key.toLowerCase();

            // Text selection inside a slide keeps the browser's own copy/paste
            const inText = e.target.isContentEditable ||
                           e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA';
            const hasTextSelection = !(window.getSelection() || {}).isCollapsed;

            if (k === 's') { e.preventDefault(); saveAll(false); }
            else if (k === 'z' && !e.shiftKey) { e.preventDefault(); undo(); }
            else if ((k === 'z' && e.shiftKey) || k === 'y') { e.preventDefault(); redo(); }
            else if (k === 'm') { e.preventDefault();
                const card = currentCard();
                openLayoutGallery(card ? slideNumberOf(card) : 0);
            }
            else if (k === 'c' && !inText && !hasTextSelection) { e.preventDefault(); copySlide(false); }
            else if (k === 'x' && !inText && !hasTextSelection) { e.preventDefault(); copySlide(true); }
            else if (k === 'v' && !inText) { e.preventDefault(); pasteSlide(); }
        });

        // Never lose work on close
        window.addEventListener('beforeunload', (e) => {
            if (dirtySlides.size > 0) {
                e.preventDefault();
                e.returnValue = '';
            }
        });

        window.__markDirtyCard = markSlideDirty;
        window.__saveAll = saveAll;
        window.__pushDeckUndo = pushUndo;
        window.__persistOrder = persistOrder;
        window.__currentOrder = currentOrder;
        window.__attachChartEditButtons = attachChartEditButtons;
    }

    if (document.readyState !== 'loading') initEditor();
    else document.addEventListener('DOMContentLoaded', initEditor);
})();
