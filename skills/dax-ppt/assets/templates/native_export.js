// Native PowerPoint chart + table export, entirely in the browser.
//
// dom-to-pptx flattens anything it can't map to a PowerPoint shape into a
// picture - so Chart.js canvases and HTML tables arrive as flat images. This
// module builds those as REAL OOXML chart and table parts with PptxGenJS
// (window.PptxGenJS, loaded separately) and merges them into the deck
// dom-to-pptx produces, so the recipient can right-click > Edit Data.
//
// dom-to-pptx bundles its own copy of PptxGenJS in a closure, so its instance
// cannot be intercepted; the merge below is done on the output files instead.
(function () {
    'use strict';

    const BRAND = ['00A0DC', '12263F', '6A7C90', '8FD3EE', '3C4456', 'D4D9E0'];
    const AXIS = '6A7C90';
    const WATERFALL_UP = '00A0DC', WATERFALL_DOWN = 'B3341F', WATERFALL_TOTAL = '12263F';

    // Slide geometry in inches (13.333 x 7.5 = 16:9 at 96dpi)
    const SLIDE_W = 13.333, SLIDE_H = 7.5;

    function seriesColor(spec, i) {
        const c = (spec.colors && spec.colors[i]) ? spec.colors[i] : BRAND[i % BRAND.length];
        return String(c).replace('#', '').toUpperCase();
    }

    // ---------------------------------------------------------------- charts
    function chartTypeFor(pptx, spec) {
        const T = pptx.ChartType;
        switch (spec.type) {
            case 'bar':            return T.bar;   // horizontal (barDir 'bar')
            case 'bar_stacked':    return T.bar;
            case 'column':         return T.bar;   // vertical  (barDir 'col')
            case 'column_stacked': return T.bar;
            case 'waterfall':      return T.bar;
            case 'line':           return T.line;
            case 'area':           return T.area;
            case 'pie':            return T.pie;
            case 'doughnut':       return T.doughnut;
            default:               return T.bar;
        }
    }

    // Waterfall has no native PowerPoint type in PptxGenJS; the standard
    // consulting build is a stacked column with an invisible base series.
    function waterfallSeries(spec) {
        const values = spec.series[0].values;
        const totals = new Set(spec.totals || []);
        const base = [], delta = [], colors = [];
        let running = 0;
        values.forEach((v, i) => {
            if (totals.has(i)) {
                if (v) running = v;
                base.push(0); delta.push(running); colors.push(WATERFALL_TOTAL);
            } else if (v >= 0) {
                base.push(running); delta.push(v); colors.push(WATERFALL_UP);
                running += v;
            } else {
                base.push(running + v); delta.push(-v); colors.push(WATERFALL_DOWN);
                running += v;
            }
        });
        return { base, delta, colors };
    }

    function addChartToSlide(pptx, slide, spec, pos) {
        const opts = {
            x: pos.x, y: pos.y, w: pos.w, h: pos.h,
            chartColors: spec.series.map((_, i) => seriesColor(spec, i)),
            showLegend: spec.series.length > 1 || spec.type === 'pie' || spec.type === 'doughnut',
            legendPos: 'b',
            legendFontSize: 9,
            catAxisLabelFontSize: 9,
            valAxisLabelFontSize: 9,
            catAxisLabelColor: AXIS,
            valAxisLabelColor: AXIS,
            valGridLine: { color: 'E4E8ED', size: 1 },
            catGridLine: { style: 'none' },
            dataLabelFontSize: 9,
            dataLabelColor: '221F20',
        };
        if (spec.title) {
            opts.showTitle = true;
            opts.title = spec.title;
            opts.titleFontSize = 11;
            opts.titleColor = '12263F';
        }
        if (spec.number_format) {
            opts.valAxisLabelFormatCode = spec.number_format;
            opts.dataLabelFormatCode = spec.number_format;
        }

        if (spec.type === 'waterfall') {
            const { base, delta, colors } = waterfallSeries(spec);
            const data = [
                { name: '_base', labels: spec.categories, values: base },
                { name: spec.series[0].name, labels: spec.categories, values: delta },
            ];
            slide.addChart(pptx.ChartType.bar, data, Object.assign({}, opts, {
                barDir: 'col', barGrouping: 'stacked',
                showLegend: false,
                // Base is invisible; the visible series carries per-point colors
                chartColors: ['FFFFFF'].concat(colors),
                chartColorsOpacity: 100,
                barGapWidthPct: 60,
            }));
            return;
        }

        const data = spec.series.map(s => ({
            name: s.name, labels: spec.categories, values: s.values,
        }));

        if (spec.type === 'pie' || spec.type === 'doughnut') {
            slide.addChart(chartTypeFor(pptx, spec), data, Object.assign({}, opts, {
                chartColors: spec.categories.map((_, i) => seriesColor(spec, i)),
                showPercent: false,
                holeSize: spec.type === 'doughnut' ? 50 : undefined,
            }));
            return;
        }

        if (spec.type === 'line' || spec.type === 'area') {
            slide.addChart(chartTypeFor(pptx, spec), data, Object.assign({}, opts, {
                lineSize: 2, lineSmooth: false,
            }));
            return;
        }

        const horizontal = (spec.type === 'bar' || spec.type === 'bar_stacked');
        const stacked = spec.type.endsWith('_stacked');
        slide.addChart(pptx.ChartType.bar, data, Object.assign({}, opts, {
            barDir: horizontal ? 'bar' : 'col',
            barGrouping: stacked ? 'stacked' : 'clustered',
            // Value labels read well on a single-series bar, like a consulting exhibit
            showValue: (!stacked && spec.series.length === 1),
        }));
    }

    // ---------------------------------------------------------------- tables
    function addTableToSlide(slide, tbl, pos) {
        const head = tbl.headers.map(h => ({
            text: h,
            options: { bold: true, color: AXIS, fontSize: 9, fill: 'FFFFFF' },
        }));
        const body = tbl.rows.map(r => r.map((cell, ci) => ({
            text: cell,
            options: {
                fontSize: 10, color: '3C4456',
                align: (tbl.aligns && tbl.aligns[ci] === 'r') ? 'right' : 'left',
            },
        })));

        slide.addTable([head].concat(body), {
            x: pos.x, y: pos.y, w: pos.w, h: pos.h,
            fontFace: 'Poppins',
            border: { type: 'solid', pt: 0.5, color: 'D4D9E0' },
            autoPage: false,
        });
    }

    // ---------------------------------------------------------------- extract
    // Pull chart/table geometry + data out of the DOM, then remove those nodes
    // so dom-to-pptx has nothing chart-shaped left to rasterise.
    function extractAndStrip(slideContents) {
        const perSlide = [];

        slideContents.forEach((sc) => {
            const scRect = sc.getBoundingClientRect();
            const entry = { charts: [], tables: [] };
            if (!scRect.width || !scRect.height) { perSlide.push(entry); return; }

            const frac = (r) => ({
                x: ((r.left - scRect.left) / scRect.width) * SLIDE_W,
                y: ((r.top - scRect.top) / scRect.height) * SLIDE_H,
                w: (r.width / scRect.width) * SLIDE_W,
                h: (r.height / scRect.height) * SLIDE_H,
            });

            // Strip the exhibit panel's chrome too - its border/background would
            // otherwise rasterise into a frame sitting over the native shape.
            const clearPanel = (node) => {
                const panel = node.closest('.exh');
                if (panel) {
                    panel.style.border = 'none';
                    panel.style.background = 'none';
                    panel.style.boxShadow = 'none';
                }
            };
            const replaceWithSpacer = (node, r) => {
                const spacer = document.createElement('div');
                spacer.style.width = r.width + 'px';
                spacer.style.height = r.height + 'px';
                node.replaceWith(spacer);
            };

            sc.querySelectorAll('.chart-embed[data-chart-id]').forEach((el) => {
                const spec = (window.CHART_SPECS || {})[el.dataset.chartId];
                const r = el.getBoundingClientRect();
                if (!spec || !r.width || !r.height) return;
                entry.charts.push({ spec, pos: frac(r) });
                clearPanel(el);
                replaceWithSpacer(el, r);
            });

            sc.querySelectorAll('table').forEach((tbl) => {
                const r = tbl.getBoundingClientRect();
                if (!r.width || !r.height) return;
                const headEls = tbl.querySelectorAll('thead th, thead td');
                const headers = Array.from(headEls).map(e => e.innerText.trim());
                if (!headers.length) return;
                const aligns = Array.from(headEls).map(e =>
                    getComputedStyle(e).textAlign === 'right' ? 'r' : 'l');
                const rows = Array.from(tbl.querySelectorAll('tbody tr')).map(tr =>
                    Array.from(tr.querySelectorAll('td, th')).map(td => td.innerText.trim()));
                if (!rows.length) return;

                entry.tables.push({ headers, rows, aligns, pos: frac(r) });
                clearPanel(tbl);
                replaceWithSpacer(tbl, r);
            });

            perSlide.push(entry);
        });

        return perSlide;
    }

    // ---------------------------------------------------------------- merge
    // dom-to-pptx and PptxGenJS both emit standard PPTX zips. Building the
    // native shapes as an overlay deck and merging its chart/table parts in is
    // far more robust than trying to synthesise OOXML by hand.
    async function buildOverlayDeck(perSlide) {
        if (typeof window.PptxGenJS !== 'function') return null;
        const pptx = new window.PptxGenJS();
        pptx.defineLayout({ name: 'DA_16x9', width: SLIDE_W, height: SLIDE_H });
        pptx.layout = 'DA_16x9';

        let any = false;
        perSlide.forEach((entry) => {
            const slide = pptx.addSlide();
            entry.charts.forEach(c => { addChartToSlide(pptx, slide, c.spec, c.pos); any = true; });
            entry.tables.forEach(t => { addTableToSlide(slide, t, t.pos); any = true; });
        });

        if (!any) return null;
        return pptx.write({ outputType: 'blob' });
    }

    // Copy the chart/table shapes from the overlay deck into the base deck,
    // slide by slide, carrying their relationship targets (chart XML, embedded
    // workbooks, table styles) so the result is a valid single PPTX.
    // Resolve an OOXML relationship Target to a path inside the zip.
    function normalizeTarget(target) {
        if (!target) return '';
        if (target.charAt(0) === '/') return target.slice(1);      // "/ppt/charts/x.xml"
        if (target.indexOf('../') === 0) return 'ppt/' + target.slice(3); // "../charts/x.xml"
        return 'ppt/slides/' + target;                              // sibling of the slide
    }

    async function mergeDecks(baseBlob, overlayBlob) {
        const JSZipCtor = window.JSZip;
        if (!JSZipCtor) throw new Error('JSZip not available for merge');

        const base = await JSZipCtor.loadAsync(baseBlob);
        const over = await JSZipCtor.loadAsync(overlayBlob);

        const slideName = (n) => `ppt/slides/slide${n}.xml`;
        const relsName = (n) => `ppt/slides/_rels/slide${n}.xml.rels`;

        // How many chart parts the base deck already has, so ids never collide
        let chartSeq = Object.keys(base.files).filter(f => /^ppt\/charts\/chart\d+\.xml$/.test(f)).length;
        let embedSeq = Object.keys(base.files)
            .filter(f => /^ppt\/embeddings\//.test(f)).length;

        const parser = new DOMParser();
        const serializer = new XMLSerializer();

        let slideIdx = 1;
        while (base.file(slideName(slideIdx)) && over.file(slideName(slideIdx))) {
            const overXml = await over.file(slideName(slideIdx)).async('string');
            const overDoc = parser.parseFromString(overXml, 'application/xml');
            const spTree = overDoc.getElementsByTagName('p:spTree')[0];
            if (!spTree) { slideIdx++; continue; }

            // graphicFrame holds both charts and tables
            const frames = Array.from(spTree.getElementsByTagName('p:graphicFrame'));
            if (!frames.length) { slideIdx++; continue; }

            const baseXml = await base.file(slideName(slideIdx)).async('string');
            const baseDoc = parser.parseFromString(baseXml, 'application/xml');
            const baseTree = baseDoc.getElementsByTagName('p:spTree')[0];

            const overRelsFile = over.file(relsName(slideIdx));
            const overRels = overRelsFile
                ? parser.parseFromString(await overRelsFile.async('string'), 'application/xml')
                : null;
            const baseRelsFile = base.file(relsName(slideIdx));
            const baseRels = baseRelsFile
                ? parser.parseFromString(await baseRelsFile.async('string'), 'application/xml')
                : parser.parseFromString(
                    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>' +
                    '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"/>',
                    'application/xml');
            const baseRelsRoot = baseRels.documentElement;

            let maxRid = 0;
            Array.from(baseRelsRoot.getElementsByTagName('Relationship')).forEach(r => {
                const m = /^rId(\d+)$/.exec(r.getAttribute('Id') || '');
                if (m) maxRid = Math.max(maxRid, parseInt(m[1], 10));
            });

            for (const frame of frames) {
                // Re-point any r:id this frame carries at a copied part
                const refs = Array.from(frame.getElementsByTagName('c:chart'))
                    .concat(Array.from(frame.getElementsByTagName('a:blip')));

                for (const ref of refs) {
                    const rid = ref.getAttribute('r:id') || ref.getAttribute('r:embed');
                    if (!rid || !overRels) continue;

                    const rel = Array.from(overRels.getElementsByTagName('Relationship'))
                        .find(r => r.getAttribute('Id') === rid);
                    if (!rel) continue;

                    // PptxGenJS writes absolute targets ("/ppt/charts/chart1.xml");
                    // other writers use relative ("../charts/chart1.xml"). Normalise
                    // both to a zip path, or the part lookup silently fails and the
                    // chart keeps pointing at whatever rId already existed.
                    const target = normalizeTarget(rel.getAttribute('Target'));
                    const partFile = over.file(target);
                    if (!partFile) continue;

                    chartSeq += 1;
                    const newPart = `ppt/charts/chart${chartSeq}.xml`;
                    base.file(newPart, await partFile.async('uint8array'));

                    // Chart parts carry their own rels (embedded workbook, colors, style)
                    const partRelsPath = target.replace(/([^/]+)$/, '_rels/$1.rels');
                    const partRels = over.file(partRelsPath);
                    if (partRels) {
                        let prXml = await partRels.async('string');
                        const prDoc = parser.parseFromString(prXml, 'application/xml');
                        for (const r of Array.from(prDoc.getElementsByTagName('Relationship'))) {
                            const abs = normalizeTarget(r.getAttribute('Target'));
                            const sub = over.file(abs);
                            if (!sub) continue;
                            let newSub;
                            if (/embeddings\//.test(abs)) {
                                embedSeq += 1;
                                newSub = `ppt/embeddings/Microsoft_Excel_Sheet${embedSeq}.xlsx`;
                                r.setAttribute('Target', `../embeddings/${newSub.split('/').pop()}`);
                            } else {
                                newSub = abs.replace(/(\d+)(\.\w+)$/, `${chartSeq}$2`);
                                r.setAttribute('Target', '../' + newSub.replace(/^ppt\//, ''));
                            }
                            base.file(newSub, await sub.async('uint8array'));
                        }
                        base.file(`ppt/charts/_rels/chart${chartSeq}.xml.rels`,
                                  serializer.serializeToString(prDoc));
                    }

                    maxRid += 1;
                    const newRid = 'rId' + maxRid;
                    // createElementNS: the rels document has a default namespace,
                    // and an element created without it is silently ignored by
                    // PowerPoint - which leaves the chart pointing at whatever
                    // rId already existed (an image).
                    const REL_NS = 'http://schemas.openxmlformats.org/package/2006/relationships';
                    const newRel = baseRels.createElementNS(REL_NS, 'Relationship');
                    newRel.setAttribute('Id', newRid);
                    newRel.setAttribute('Type',
                        'http://schemas.openxmlformats.org/officeDocument/2006/relationships/chart');
                    newRel.setAttribute('Target', `../charts/chart${chartSeq}.xml`);
                    baseRelsRoot.appendChild(newRel);

                    if (ref.hasAttribute('r:id')) ref.setAttribute('r:id', newRid);
                    else ref.setAttribute('r:embed', newRid);
                }

                baseTree.appendChild(baseDoc.importNode(frame, true));
            }

            base.file(slideName(slideIdx), serializer.serializeToString(baseDoc));
            base.file(relsName(slideIdx), serializer.serializeToString(baseRels));
            slideIdx++;
        }

        // Register the copied chart parts in [Content_Types].xml
        const ctFile = base.file('[Content_Types].xml');
        if (ctFile) {
            const ctDoc = parser.parseFromString(await ctFile.async('string'), 'application/xml');
            const root = ctDoc.documentElement;
            const existing = new Set(Array.from(ctDoc.getElementsByTagName('Override'))
                .map(o => o.getAttribute('PartName')));
            const CT_NS = 'http://schemas.openxmlformats.org/package/2006/content-types';
            Object.keys(base.files)
                .filter(f => /^ppt\/charts\/chart\d+\.xml$/.test(f))
                .forEach(f => {
                    const part = '/' + f;
                    if (existing.has(part)) return;
                    const o = ctDoc.createElementNS(CT_NS, 'Override');
                    o.setAttribute('PartName', part);
                    o.setAttribute('ContentType',
                        'application/vnd.openxmlformats-officedocument.drawingml.chart+xml');
                    root.appendChild(o);
                });
            // Embedded chart workbooks need a declared extension too
            const hasXlsx = Array.from(ctDoc.getElementsByTagName('Default'))
                .some(d => (d.getAttribute('Extension') || '').toLowerCase() === 'xlsx');
            if (!hasXlsx && Object.keys(base.files).some(f => /^ppt\/embeddings\/.*\.xlsx$/.test(f))) {
                const d = ctDoc.createElementNS(CT_NS, 'Default');
                d.setAttribute('Extension', 'xlsx');
                d.setAttribute('ContentType',
                    'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet');
                root.appendChild(d);
            }
            base.file('[Content_Types].xml', serializer.serializeToString(ctDoc));
        }

        return base.generateAsync({ type: 'blob', mimeType:
            'application/vnd.openxmlformats-officedocument.presentationml.presentation' });
    }

    window.NativeExport = {
        extractAndStrip,
        buildOverlayDeck,
        mergeDecks,
        SLIDE_W, SLIDE_H,
    };
})();
