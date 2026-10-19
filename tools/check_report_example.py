"""核对 5DR 中文报告样例与已验收的 5 日反转账本。"""
import json
import re

import pandas as pd

from ashare_bt.config import Config, ROOT
from ashare_bt.utils import atomic_json, sha256


def check():
    directory = ROOT / 'runs/report-5dr'
    baseline = ROOT / 'runs/full-reversal'
    summary = json.loads((directory / 'summary.json').read_text())
    config = Config.load(ROOT / 'configs/5dr.toml')
    actual = summary['config']
    assert summary['name'] == config.name and '5DR' in summary['name']
    assert actual['strategy'] == 'reversal' and actual['parameters']['window'] == 5
    assert actual['parameters']['allocation'] == 'equal'
    assert summary['compute']['device'] == 'mps'
    assert (summary['start'], summary['end'], summary['trading_days']) == ('2025-01-02', '2026-09-30', 424)
    assert summary['warmup']['last_decision'] == '2024-12-31'
    assert summary['first_trade_date'] == '2025-01-02'
    assert actual['initial_cash'] == '1000000000.00'
    assert actual['commission_rate'] == '0.0001' and actual['stamp_tax_rate'] == '0.0005'
    assert summary['status_coverage']['unknown_stock_days'] == 0
    assert summary['exit_planning']['basis'] == 'actual_path' and summary['exit_planning']['completed']
    assert summary['ending_positions'] == 0 and float(summary['ending_market_value']) == 0
    assert float(summary['ending_receivables']) == float(summary['ending_pending_equity']) == 0
    assert not summary['terminal_assumptions']
    comparisons = []
    for name in ('orders', 'trades', 'journal', 'equity', 'positions', 'fees', 'exits', 'universe', 'selection', 'benchmark_equity'):
        frame = pd.read_parquet(directory / f'{name}.parquet')
        original = pd.read_parquet(baseline / f'{name}.parquet')
        pd.testing.assert_frame_equal(frame, original, check_exact=True)
        comparisons.append({'table': name, 'rows': len(frame), 'identical': True})
        del frame, original
    manifest = json.loads((directory / 'manifest.json').read_text())
    application_changes = {}
    for name, digest in manifest['source_sha256'].items():
        assert sha256(directory / 'source' / name) == digest
        current = sha256(ROOT / 'src/ashare_bt' / name)
        if name == 'server.py':
            if current != digest:
                application_changes[name] = {'run_sha256': digest, 'publication_sha256': current}
        else:
            assert current == digest
    markdown = (directory / 'report.md').read_text()
    assert '退出方式与后续行情使用范围' in markdown and '事后规划' in markdown and '新增买入' in markdown
    assert markdown.startswith('# 5DR') and '5 日反转' in markdown
    assert '![策略与参考组合的累计收益曲线](equity-curve.png)' in markdown
    from PIL import Image
    with Image.open(directory/'equity-curve.png') as image:
        assert image.format=='PNG' and image.size==(1880,580)
        image.verify()
    assert manifest['report']['chart_sha256']==sha256(directory/'equity-curve.png')
    assert f'{summary["return"]:.2%}' in markdown
    assert f'{summary["max_drawdown"]:.2%}' in markdown
    assert f'{float(summary["net_profit"]):,.2f}' in markdown
    report = {'passed': True, 'run_id': summary['run_id'], 'strategy': '5DR（5 日反转）',
              'ranking': '5 日复权收益从低到高，同分按证券代码', 'baseline': str(baseline.relative_to(ROOT)),
              'device': summary['compute']['device'], 'trading_days': summary['trading_days'],
              'tables': comparisons, 'config_sha256': sha256(ROOT / 'configs/5dr.toml'),
              'report_sha256': sha256(directory / 'report.md'), 'source_sha256': manifest['source_sha256'],
              'application_publication_changes': application_changes, 'financial_source_matches': True}
    atomic_json(ROOT / 'data/5dr-report-check.json', report)
    print(json.dumps({key: report[key] for key in ('passed', 'run_id', 'strategy', 'device', 'trading_days')}, ensure_ascii=False))


if __name__ == '__main__':
    check()
