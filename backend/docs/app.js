// HFT & Dispersion Platform Dashboard Controller
let chartInstances = {};

function initTabs() {
    const btns = document.querySelectorAll('.tab-btn');
    btns.forEach(btn => {
        btn.addEventListener('click', function() {
            btns.forEach(b => b.classList.remove('active'));
            document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
            this.classList.add('active');
            const targetId = 'tab-' + this.getAttribute('data-tab');
            const target = document.getElementById(targetId);
            if (target) target.classList.add('active');
        });
    });
}

function initCharts() {
    console.log('[Dashboard] Initializing charts...');
    const dispData = window.DISPERSION_DATA || {};
    const backtestData = window.BACKTEST_DATA || {};

    const ts = dispData.time_series || {};
    const dates = ts.dates || Array.from({length: 60}, (_, i) => 'Day ' + (i + 1));
    const impliedCorr = ts.implied_correlation || [];
    const realizedCorr = ts.realized_correlation || [];
    const cumFiltered = ts.cumulative_pnl_filtered || [];
    const cumUnfiltered = ts.cumulative_pnl_unfiltered || [];

    // 1. Correlation Chart
    const ctxCorr = document.getElementById('corrChart');
    if (ctxCorr && impliedCorr.length > 0) {
        if (chartInstances.corr) chartInstances.corr.destroy();
        chartInstances.corr = new Chart(ctxCorr.getContext('2d'), {
            type: 'line',
            data: {
                labels: dates,
                datasets: [
                    {
                        label: 'Implied Correlation (Market Priced)',
                        data: impliedCorr,
                        borderColor: '#8b5cf6',
                        backgroundColor: 'rgba(139, 92, 246, 0.12)',
                        borderWidth: 2.5,
                        fill: true,
                        tension: 0.25,
                        pointRadius: 2
                    },
                    {
                        label: 'Realized Correlation (Actual Moves)',
                        data: realizedCorr,
                        borderColor: '#3b82f6',
                        backgroundColor: 'rgba(59, 130, 246, 0.08)',
                        borderWidth: 2,
                        fill: true,
                        tension: 0.25,
                        pointRadius: 2
                    }
                ]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { labels: { color: '#9ca3af', font: { family: 'Inter', size: 12 } } },
                    tooltip: { mode: 'index', intersect: false }
                },
                scales: {
                    x: { grid: { color: 'rgba(255,255,255,0.05)' }, ticks: { color: '#9ca3af', maxTicksLimit: 12 } },
                    y: { grid: { color: 'rgba(255,255,255,0.05)' }, ticks: { color: '#9ca3af' } }
                }
            }
        });
        console.log('[Dashboard] Correlation Chart initialized successfully with', impliedCorr.length, 'points');
    }

    // 2. Dispersion Cumulative PnL Chart
    const ctxPnl = document.getElementById('dispPnlChart');
    if (ctxPnl && cumFiltered.length > 0) {
        if (chartInstances.pnl) chartInstances.pnl.destroy();
        chartInstances.pnl = new Chart(ctxPnl.getContext('2d'), {
            type: 'line',
            data: {
                labels: dates,
                datasets: [
                    {
                        label: 'GEX-Filtered Total Dispersion P&L',
                        data: cumFiltered,
                        borderColor: '#10b981',
                        backgroundColor: 'rgba(16, 185, 129, 0.1)',
                        fill: true,
                        borderWidth: 2.5,
                        tension: 0.25,
                        pointRadius: 2
                    },
                    {
                        label: 'Raw Unfiltered Dispersion P&L',
                        data: cumUnfiltered,
                        borderColor: '#3b82f6',
                        borderWidth: 1.5,
                        borderDash: [4, 4],
                        tension: 0.25,
                        pointRadius: 0
                    }
                ]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { labels: { color: '#9ca3af', font: { family: 'Inter', size: 12 } } },
                    tooltip: { mode: 'index', intersect: false }
                },
                scales: {
                    x: { grid: { color: 'rgba(255,255,255,0.05)' }, ticks: { color: '#9ca3af', maxTicksLimit: 12 } },
                    y: { grid: { color: 'rgba(255,255,255,0.05)' }, ticks: { color: '#9ca3af' } }
                }
            }
        });
        console.log('[Dashboard] PnL Chart initialized successfully with', cumFiltered.length, 'points');
    }

    // 3. HFT Equity Chart
    const ctxEq = document.getElementById('hftEquityChart');
    const eq = backtestData.equity_curve || [];
    if (ctxEq && eq.length > 0) {
        if (chartInstances.eq) chartInstances.eq.destroy();
        const eqLabels = eq.map((item, i) => {
            if (Array.isArray(item)) {
                const d = new Date(item[0]);
                return d.getHours() + ':' + String(d.getMinutes()).padStart(2, '0');
            }
            return 'T+' + (i * 15) + 'm';
        });
        const eqVals = eq.map(item => Array.isArray(item) ? item[1] : (item.total_equity || item));

        chartInstances.eq = new Chart(ctxEq.getContext('2d'), {
            type: 'line',
            data: {
                labels: eqLabels,
                datasets: [{
                    label: 'Total Account Equity (Rs.)',
                    data: eqVals,
                    borderColor: '#10b981',
                    backgroundColor: 'rgba(16, 185, 129, 0.08)',
                    fill: true,
                    borderWidth: 2,
                    tension: 0.2,
                    pointRadius: 1
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: { legend: { labels: { color: '#9ca3af' } } },
                scales: {
                    x: { grid: { color: 'rgba(255,255,255,0.05)' }, ticks: { color: '#9ca3af', maxTicksLimit: 10 } },
                    y: { grid: { color: 'rgba(255,255,255,0.05)' }, ticks: { color: '#9ca3af' } }
                }
            }
        });
    }

    // 4. Markout Chart
    const ctxMo = document.getElementById('hftMarkoutChart');
    const markout = backtestData.markout || { '10ms': -73.7, '100ms': -21.9, '1s': -60.1, '5s': 84.7, '30s': -67.2, '60s': -171.1 };
    if (ctxMo) {
        if (chartInstances.mo) chartInstances.mo.destroy();
        const moLabels = Object.keys(markout).map(k => k.endsWith('ms') || k.endsWith('s') ? k : (parseInt(k) >= 1000 ? (parseInt(k)/1000)+'s' : k+'ms'));
        const moVals = Object.values(markout).map(v => typeof v === 'object' ? v.mean_bps : v);

        chartInstances.mo = new Chart(ctxMo.getContext('2d'), {
            type: 'bar',
            data: {
                labels: moLabels,
                datasets: [{
                    label: 'Markout Price Drift / Fill Quality (bps)',
                    data: moVals,
                    backgroundColor: moVals.map(v => v >= 0 ? 'rgba(16, 185, 129, 0.7)' : 'rgba(239, 68, 68, 0.7)'),
                    borderRadius: 6
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: { legend: { labels: { color: '#9ca3af' } } },
                scales: {
                    x: { grid: { color: 'rgba(255,255,255,0.05)' }, ticks: { color: '#9ca3af' } },
                    y: { grid: { color: 'rgba(255,255,255,0.05)' }, ticks: { color: '#9ca3af' } }
                }
            }
        });
    }
}

document.addEventListener('DOMContentLoaded', () => {
    initTabs();
    initCharts();
});
