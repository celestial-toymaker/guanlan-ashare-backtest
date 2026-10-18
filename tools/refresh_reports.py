"""从已保存账本生成 Markdown 报告，并保留报表刷新前的来源哈希。"""
from datetime import datetime
import json

import pandas as pd

from ashare_bt.analytics import write_report
from ashare_bt.config import ROOT
from ashare_bt.utils import atomic_json, sha256


def refresh():
    current=ROOT/'src/ashare_bt'
    results=[]
    for directory in sorted((ROOT/'runs').iterdir()):
        if not (directory.name.startswith('full-') or directory.name=='report-5dr'):
            continue
        manifest_path=directory/'manifest.json'
        if not manifest_path.exists():
            continue
        previous=json.loads(manifest_path.read_text())
        verified=[]
        for name,digest in previous['source_sha256'].items():
            snapshot=directory/'source'/name
            assert sha256(snapshot)==digest,(directory.name,name,'来源快照')
            if name=='analytics.py':
                prefix=lambda text:text[:text.index('def chart_svg')].replace('from html import escape\n','')
                assert prefix(snapshot.read_text())==prefix((current/name).read_text())
            elif name not in {'cli.py','server.py'}:
                assert sha256(current/name)==digest,(directory.name,name,'财务模块')
                verified.append(name)
        summary=json.loads((directory/'summary.json').read_text())
        reference_path=directory/'benchmark_equity.parquet'
        reference=pd.read_parquet(reference_path) if reference_path.exists() else None
        write_report(directory,summary,pd.read_parquet(directory/'equity.parquet'),reference)
        refreshed=json.loads(manifest_path.read_text())
        refreshed['simulation_source_sha256']=previous.get('simulation_source_sha256',previous['source_sha256'])
        refreshed['report_refresh']={'format':'markdown','refreshed_at':datetime.now().astimezone().isoformat(),
            'verified_unchanged_financial_modules':verified,
            'basis':'从原始净值、费用及摘要生成报表；财务模块与统计口径逐项核对；CLI 与服务同步 Markdown 文件入口'}
        atomic_json(manifest_path,refreshed)
        (directory/'report.html').unlink(missing_ok=True)
        results.append(directory.name)
    (ROOT/'reports/5dr/report.html').unlink(missing_ok=True)
    print(json.dumps({'refreshed':results,'format':'markdown'},ensure_ascii=False))


if __name__=='__main__':refresh()
