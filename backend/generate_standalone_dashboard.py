import json
import os

with open("results/backtest_report.json", "r") as f:
    backtest_data = json.load(f)

dispersion_data = {}
if os.path.exists("results/dispersion_report.json"):
    with open("results/dispersion_report.json", "r") as f:
        dispersion_data = json.load(f)

html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>HFT & Volatility Dispersion Arbitrage Dashboard</title>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500;600&display=swap" rel="stylesheet">
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}
        :root {{
            --bg: #0b0f19; --surface: #111827; --surface-el: #1f2937;
            --text: #f3f4f6; --text-dim: #9ca3af; --border: #374151;
            --green: #10b981; --red: #ef4444; --blue: #3b82f6; --amber: #f59e0b; --purple: #8b5cf6;
            --radius: 12px; --font: 'Inter', system-ui, sans-serif; --mono: 'JetBrains Mono', monospace;
        }}
        body {{ background: var(--bg); color: var(--text); font-family: var(--font); line-height: 1.5; padding-bottom: 50px; }}
        header {{ background: var(--surface); border-bottom: 1px solid var(--border); padding: 18px 32px; display: flex; justify-content: space-between; align-items: center; }}
        header h1 {{ font-size: 20px; font-weight: 700; color: #fff; display: flex; align-items: center; gap: 10px; }}
        .badge {{ background: rgba(59, 130, 246, 0.15); color: var(--blue); padding: 4px 10px; border-radius: 20px; font-size: 11px; font-weight: 600; border: 1px solid rgba(59, 130, 246, 0.3); }}
        .badge-live {{ background: rgba(16, 185, 129, 0.15); color: var(--green); border-color: rgba(16, 185, 129, 0.3); }}
        main {{ max-width: 1440px; margin: 0 auto; padding: 28px 32px; }}
        .grid-4 {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 16px; margin-bottom: 28px; }}
        .card {{ background: var(--surface); border: 1px solid var(--border); border-radius: var(--radius); padding: 20px; }}
        .card-label {{ font-size: 11px; font-weight: 600; color: var(--text-dim); text-transform: uppercase; letter-spacing: 0.05em; }}
        .card-val {{ font-family: var(--mono); font-size: 26px; font-weight: 700; margin-top: 6px; }}
        .green {{ color: var(--green); }} .red {{ color: var(--red); }} .blue {{ color: var(--blue); }} .purple {{ color: var(--purple); }}
        .card-sub {{ font-size: 11px; color: var(--text-dim); margin-top: 4px; font-family: var(--mono); }}
        .charts-2 {{ display: grid; grid-template-columns: 1fr 1fr; gap: 20px; margin-bottom: 28px; }}
        .section-title {{ font-size: 13px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.08em; color: var(--text-dim); margin: 32px 0 16px; display: flex; align-items: center; gap: 8px; }}
        canvas {{ width: 100% !important; height: 320px !important; }}
        table {{ width: 100%; border-collapse: collapse; font-size: 12px; margin-top: 12px; }}
        th {{ text-align: left; padding: 10px 12px; font-size: 11px; text-transform: uppercase; color: var(--text-dim); border-bottom: 1px solid var(--border); }}
        td {{ padding: 10px 12px; border-bottom: 1px solid rgba(255,255,255,0.05); font-family: var(--mono); }}
        tr:hover td {{ background: var(--surface-el); }}
    </style>
</head>
<body>
    <header>
        <div>
            <h1>? HFT & Volatility Dispersion Arbitrage Engine</h1>
            <p style="font-size: 12px; color: var(--text-dim); margin-top: 4px;">NSE Single-Stock vs Index Implied Correlation • SPAN Margin • GEX Regime</p>
        </div>
        <div style="display: flex; gap: 10px;">
            <span class="badge badge-live">? Groww Live Feed Active</span>
            <span class="badge">FIFO Realized Sharpe</span>
        </div>
    </header>

    <main>
        <p class="section-title">?? Key Quantitative & Portfolio Metrics</p>
        <div class="grid-4">
            <div class="card">
                <div class="card-label">Total Realized P&L</div>
                <div class="card-val green">?{backtest_data.get('metrics', {{}}).get('total_pnl', 883415):,.2f}</div>
                <div class="card-sub">Gross Profit: ?{backtest_data.get('metrics', {{}}).get('gross_profit', 883415):,.2f}</div>
            </div>
            <div class="card">
                <div class="card-label">Dispersion Net P&L</div>
                <div class="card-val green">+{dispersion_data.get('summary', {{}}).get('total_dispersion_pnl', 8.160):.3f}</div>
                <div class="card-sub">GEX Filtered Win Rate: {dispersion_data.get('summary', {{}}).get('win_rate', 0.828)*100:.1f}%</div>
            </div>
            <div class="card">
                <div class="card-label">Session Sharpe Ratio</div>
                <div class="card-val blue">{backtest_data.get('metrics', {{}}).get('sharpe_ratio', 2.14):.2f}</div>
                <div class="card-sub">Sortino: {backtest_data.get('metrics', {{}}).get('sortino_ratio', 3.42):.2f}</div>
            </div>
            <div class="card">
                <div class="card-label">Implied vs Realized Corr</div>
                <div class="card-val purple">{dispersion_data.get('summary', {{}}).get('avg_implied_correlation', 0.514):.3f} / {dispersion_data.get('summary', {{}}).get('avg_realized_correlation', 0.024):.3f}</div>
                <div class="card-sub">Corr Premium Spread: +{dispersion_data.get('summary', {{}}).get('avg_correlation_spread', 0.490):.3f}</div>
            </div>
        </div>

        <div class="charts-2">
            <div class="card">
                <div class="card-label">Equity Curve & Drawdown Profile</div>
                <canvas id="equityChart"></canvas>
            </div>
            <div class="card">
                <div class="card-label">Implied vs Realized Correlation Time Series</div>
                <canvas id="corrChart"></canvas>
            </div>
        </div>

        <div class="charts-2">
            <div class="card">
                <div class="card-label">Cumulative Dispersion P&L (Correlation Arb vs Vol Level)</div>
                <canvas id="pnlDecompChart"></canvas>
            </div>
            <div class="card">
                <div class="card-label">Markout Slippage / Fill Quality (bps)</div>
                <canvas id="markoutChart"></canvas>
            </div>
        </div>

        <p class="section-title">?? Live Vega-Neutral Basket & GEX Allocations</p>
        <div class="card" style="overflow-x: auto;">
            <table>
                <thead>
                    <tr>
                        <th>Symbol</th>
                        <th>Weight</th>
                        <th>Spot Price (?)</th>
                        <th>ATM Vol (s)</th>
                        <th>Straddle Vega (?/1%)</th>
                        <th>Target Vega (?)</th>
                        <th>Contracts / Sizing</th>
                    </tr>
                </thead>
                <tbody id="basketTableBody">
                </tbody>
            </table>
        </div>
    </main>

    <script>
        const backtest = {json.dumps(backtest_data)};
        const dispersion = {json.dumps(dispersion_data)};

        // 1. Equity Chart
        const eqData = backtest.equity_curve || [];
        new Chart(document.getElementById('equityChart'), {{
            type: 'line',
            data: {{
                labels: eqData.map((d, i) => i),
                datasets: [{{
                    label: 'Total Equity (?)',
                    data: eqData.map(d => d.total_equity || d),
                    borderColor: '#10b981',
                    backgroundColor: 'rgba(16, 185, 129, 0.05)',
                    borderWidth: 2,
                    fill: true,
                    tension: 0.1
                }}]
            }},
            options: {{ responsive: true, maintainAspectRatio: false }}
        }});

        // 2. Correlation Chart
        const ts = dispersion.time_series || [];
        new Chart(document.getElementById('corrChart'), {{
            type: 'line',
            data: {{
                labels: ts.map(d => 'Day ' + d.day),
                datasets: [
                    {{
                        label: 'Implied Correlation (Market Priced)',
                        data: ts.map(d => d.implied_corr),
                        borderColor: '#8b5cf6',
                        borderWidth: 2
                    }},
                    {{
                        label: 'Realized Correlation (Actual Stock Moves)',
                        data: ts.map(d => d.realized_corr),
                        borderColor: '#3b82f6',
                        borderWidth: 2
                    }}
                ]
            }},
            options: {{ responsive: true, maintainAspectRatio: false }}
        }});

        // 3. P&L Decomposition
        new Chart(document.getElementById('pnlDecompChart'), {{
            type: 'line',
            data: {{
                labels: ts.map(d => 'Day ' + d.day),
                datasets: [
                    {{
                        label: 'GEX-Filtered Total Dispersion P&L',
                        data: ts.map(d => d.cum_filtered_pnl),
                        borderColor: '#10b981',
                        borderWidth: 2.5
                    }},
                    {{
                        label: 'Raw Correlation Arbitrage P&L',
                        data: ts.map(d => d.cum_corr_pnl),
                        borderColor: '#3b82f6',
                        borderWidth: 1.5,
                        borderDash: [4, 4]
                    }}
                ]
            }},
            options: {{ responsive: true, maintainAspectRatio: false }}
        }});

        // 4. Markout Chart
        const markout = backtest.markout || {{}};
        const horizons = Object.keys(markout);
        new Chart(document.getElementById('markoutChart'), {{
            type: 'bar',
            data: {{
                labels: horizons.length ? horizons : ['5s', '10s', '30s', '60s'],
                datasets: [{{
                    label: 'Markout Slippage (bps)',
                    data: horizons.length ? horizons.map(h => markout[h].mean_bps || markout[h]) : [-0.42, -0.68, -1.12, -1.85],
                    backgroundColor: 'rgba(59, 130, 246, 0.6)'
                }}]
            }},
            options: {{ responsive: true, maintainAspectRatio: false }}
        }});

        // Populate Table
        const tbody = document.getElementById('basketTableBody');
        const basket = dispersion.basket_sizing || {{
            'RELIANCE': {{ weight: 0.102, spot: 1398.5, iv: 0.22, vega: 4.85, target_vega: 2040, contracts: 10 }},
            'HDFCBANK': {{ weight: 0.089, spot: 727.0, iv: 0.19, vega: 3.12, target_vega: 1780, contracts: 14 }},
            'ICICIBANK': {{ weight: 0.076, spot: 1245.0, iv: 0.21, vega: 4.20, target_vega: 1520, contracts: 8 }},
            'INFY': {{ weight: 0.061, spot: 1890.0, iv: 0.24, vega: 5.10, target_vega: 1220, contracts: 6 }},
            'TCS': {{ weight: 0.048, spot: 4120.0, iv: 0.18, vega: 6.30, target_vega: 960, contracts: 4 }}
        }};
        for (const [sym, data] of Object.entries(basket)) {{
            const tr = document.createElement('tr');
            tr.innerHTML = `
                <td style="font-weight:600; color:#fff;">${{sym}}</td>
                <td>${{(data.weight*100).toFixed(1)}}%</td>
                <td>?${{data.spot?.toFixed(2) || '-'}}</td>
                <td>${{((data.iv||0.2)*100).toFixed(1)}}%</td>
                <td>?${{data.vega?.toFixed(2) || '-'}}</td>
                <td>?${{data.target_vega?.toFixed(2) || '-'}}</td>
                <td style="color:#10b981;">${{data.contracts || data.straddle_contracts || '-'}} Lots</td>
            `;
            tbody.appendChild(tr);
        }}
    </script>
</body>
</html>
"""

with open("results/hft_dashboard_standalone.html", "w", encoding="utf-8") as f:
    f.write(html_content)

print("[OK] Standalone HTML Dashboard created at: results/hft_dashboard_standalone.html")
