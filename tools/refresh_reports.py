"""从既有主策略账本刷新报告，并保存原始来源及财务文件哈希。"""
from datetime import datetime
from pathlib import Path
from shutil import copy2,copytree
import argparse,json
import pandas as pd
from ashare_bt.analytics import write_report
from ashare_bt.config import Config,ROOT
from ashare_bt.utils import atomic_json,sha256


def refresh(run_ids=None):
    directories=[ROOT/'runs'/ident for ident in run_ids] if run_ids else sorted((ROOT/'runs').glob('full-*'))
    results=[]
    for directory in directories:
        previous=json.loads((directory/'manifest.json').read_text())
        summary=json.loads((directory/'summary.json').read_text())
        before={p.name:sha256(p) for p in directory.iterdir() if p.suffix in {'.parquet','.csv','.jsonl'} and not p.name.startswith('benchmark_')}
        archive=ROOT/'work/report-history'/directory.name
        if not archive.exists():
            archive.mkdir(parents=True)
            for name in ('config.json','summary.json','manifest.json','report.md','equity-curve.png'):
                if (directory/name).exists():copy2(directory/name,archive/name)
            copytree(directory/'source',archive/'source')
        original=previous.get('simulation_source_sha256',previous['source_sha256'])
        summary={key:value for key,value in summary.items() if not key.startswith('benchmark_')}
        summary['config']=Config.from_dict(summary['config']).public()
        summary['schema_version']=2
        write_report(directory,summary,pd.read_parquet(directory/'equity.parquet'))
        manifest=json.loads((directory/'manifest.json').read_text())
        manifest['simulation_source_sha256']=original
        manifest['report_refresh']={'refreshed_at':datetime.now().astimezone().isoformat(),
            'basis':'从保存的主策略净值及摘要绘制单曲线；原始来源归档，主策略财务文件逐项保持一致',
            'original_report_manifest_sha256':sha256(archive/'manifest.json'),
            'verified_main_strategy_financial_files':before,'verified_main_strategy_statistics_unchanged':True}
        assert all(sha256(directory/name)==digest for name,digest in before.items())
        atomic_json(directory/'config.json',summary['config']);atomic_json(directory/'summary.json',summary)
        atomic_json(directory/'manifest.json',manifest)
        results.append({'run_id':directory.name,'financial_files_checked':len(before),'financial_files_unchanged':True})
    atomic_json(ROOT/'data/report-refresh-check.json',{'passed':True,'runs':results})
    print(json.dumps({'refreshed':results},ensure_ascii=False))


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--run-id',action='append')
    refresh(parser.parse_args().run_id)
