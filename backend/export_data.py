import json
with open('results/dispersion_report.json', 'r', encoding='utf-8') as f1:
    d = json.load(f1)
with open('results/backtest_report.json', 'r', encoding='utf-8') as f2:
    b = json.load(f2)
with open('docs/data.js', 'w', encoding='utf-8') as out:
    out.write('window.DISPERSION_DATA = ' + json.dumps(d) + ';\nwindow.BACKTEST_DATA = ' + json.dumps(b) + ';\n')
with open('dashboard/data.js', 'w', encoding='utf-8') as out:
    out.write('window.DISPERSION_DATA = ' + json.dumps(d) + ';\nwindow.BACKTEST_DATA = ' + json.dumps(b) + ';\n')
print('[OK] data.js exported successfully!')
