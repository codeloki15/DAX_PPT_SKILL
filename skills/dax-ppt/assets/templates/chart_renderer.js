// Brand-styled Chart.js rendering for .chart-embed placeholders.
// Shared by the live preview page and the screenshot verifier (verify.py) so
// both show exactly what the exported deck will contain.
// Expects: window.Chart (Chart.js) and window.CHART_SPECS (chart_id -> spec).
(function () {
    if (!window.Chart) return;
    const SPECS = window.CHART_SPECS || {};
    const BRAND = ['00A0DC', '12263F', '6A7C90', '8FD3EE', '3C4456', 'D4D9E0'];
    const GRID = '#E4E8ED', TICK = '#6A7C90', AXIS = '#D4D9E0';

    Chart.defaults.font.family = "'Poppins', Arial, sans-serif";
    Chart.defaults.font.size = 10;
    Chart.defaults.color = '#3C4456';

    function colorFor(spec, i) {
        const c = (spec.colors && spec.colors[i]) ? spec.colors[i] : BRAND[i % BRAND.length];
        return '#' + String(c).replace('#', '');
    }

    function waterfallConfig(spec) {
        const values = spec.series[0].values;
        const totals = new Set(spec.totals || []);
        const data = [], colors = [];
        let running = 0;
        values.forEach((v, i) => {
            // Total bars run from zero: a non-zero value anchors the running
            // total (opening bar); zero renders the computed total (closing bar).
            if (totals.has(i)) { if (v) running = v; data.push([0, running]); colors.push('#12263F'); }
            else if (v >= 0) { data.push([running, running + v]); colors.push('#00A0DC'); running += v; }
            else { data.push([running + v, running]); colors.push('#B3341F'); running += v; }
        });
        return {
            type: 'bar',
            data: { labels: spec.categories, datasets: [{ data, backgroundColor: colors }] },
            options: {
                responsive: true, maintainAspectRatio: false, animation: false,
                plugins: {
                    legend: { display: false },
                    title: { display: !!spec.title, text: spec.title || '' },
                    tooltip: { callbacks: { label: (c) => {
                        const i = c.dataIndex;
                        if (totals.has(i)) return 'Total: ' + data[i][1].toLocaleString();
                        return (values[i] >= 0 ? '+' : '') + values[i].toLocaleString();
                    } } }
                },
                scales: {
                    x: { grid: { display: false }, ticks: { color: TICK }, border: { color: AXIS } },
                    y: { grid: { color: GRID }, ticks: { color: TICK }, border: { color: AXIS } }
                }
            }
        };
    }

    function buildConfig(spec) {
        if (spec.type === 'waterfall') return waterfallConfig(spec);
        const isPie = (spec.type === 'pie' || spec.type === 'doughnut');
        const isHoriz = (spec.type === 'bar' || spec.type === 'bar_stacked');
        const isStacked = spec.type.endsWith('_stacked');
        const isLine = (spec.type === 'line' || spec.type === 'area');
        const datasets = spec.series.map((s, i) => ({
            label: s.name,
            data: s.values,
            backgroundColor: isPie
                ? spec.categories.map((_, j) => colorFor(spec, j))
                : (spec.type === 'area' ? colorFor(spec, i) + '33' : colorFor(spec, i)),
            borderColor: (isPie ? '#FFFFFF' : colorFor(spec, i)),
            borderWidth: isLine ? 2 : (isPie ? 1 : 0),
            fill: spec.type === 'area',
            tension: 0,
            pointRadius: spec.type === 'line' ? 2 : 0
        }));
        return {
            type: isPie ? spec.type : (isLine ? 'line' : 'bar'),
            data: { labels: spec.categories, datasets },
            options: {
                responsive: true, maintainAspectRatio: false, animation: false,
                indexAxis: isHoriz ? 'y' : 'x',
                plugins: {
                    legend: {
                        display: isPie || spec.series.length > 1,
                        position: 'bottom',
                        labels: { boxWidth: 10, boxHeight: 10 }
                    },
                    title: { display: !!spec.title, text: spec.title || '' }
                },
                scales: isPie ? {} : {
                    x: { stacked: isStacked, grid: { display: isHoriz, color: GRID },
                         ticks: { color: TICK }, border: { color: AXIS } },
                    y: { stacked: isStacked, grid: { display: !isHoriz, color: GRID },
                         ticks: { color: TICK }, border: { color: AXIS } }
                }
            }
        };
    }

    function renderAll() {
        document.querySelectorAll('.chart-embed[data-chart-id]').forEach((el) => {
            if (el.dataset.chartRendered) return;
            el.dataset.chartRendered = '1';
            const spec = SPECS[el.dataset.chartId];
            if (!spec) {
                el.textContent = 'Chart spec missing: ' + el.dataset.chartId;
                el.style.cssText += 'display:flex;align-items:center;justify-content:center;color:#B3341F;font-size:12px;border:1px dashed #D4D9E0;';
                return;
            }
            const canvas = document.createElement('canvas');
            if (!el.style.position) el.style.position = 'relative';
            el.appendChild(canvas);
            try {
                new Chart(canvas, buildConfig(spec));
            } catch (e) {
                el.textContent = 'Chart error: ' + e.message;
            }
        });
    }

    // Idempotent re-render hook (used after duplicating a slide in the preview)
    window.__renderCharts = renderAll;
    renderAll();
})();
