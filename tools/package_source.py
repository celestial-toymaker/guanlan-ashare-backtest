"""保存可复核的本地源码交付包，数据矩阵和状态原始缓存分别保留。"""
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED
import json

from ashare_bt.config import ROOT
from ashare_bt.utils import atomic_json, sha256


def package():
    files=set()
    for directory in ('src/ashare_bt','tests','configs','examples','tools','web/src','research','reports','docs','validation'):
        for path in (ROOT/directory).rglob('*'):
            if (path.is_file() and '__pycache__' not in path.parts and path.suffix not in {'.pyc','.pyo'}
                    and path.name not in {'check_wiki.py','apply_wiki_batch.py','prepare_wiki.py','.DS_Store'}):
                files.add(path)
    for name in ('README.md','验收记录.md','THIRD_PARTY_NOTICES.md','pyproject.toml','.gitignore','启动工作台.command',
                 'web/index.html','web/package.json','web/package-lock.json','web/tsconfig.json',
                 'web/vite.config.ts','web/playwright.config.ts','web/tests/workbench.spec.ts',
                 'data/acceptance.json','data/png-report-check.json','data/actual-exit-check.json','data/full-acceptance.json','data/5dr-report-check.json','data/5dr100-ranking-check.json','data/report-refresh-check.json','data/main-strategy-preservation.json','data/profile.json','data/audit.json',
                 'data/mps_validation.json','data/status/coverage.json','data/formal-status-coverage.json'):
        path=ROOT/name
        if path.exists():files.add(path)
    files.update(path for path in (ROOT/'web').glob('tsconfig.*.json'))
    manifest={str(path.relative_to(ROOT)):sha256(path) for path in sorted(files)}
    archive=ROOT/'data/source-delivery.zip'
    with ZipFile(archive,'w',ZIP_DEFLATED,compresslevel=6) as output:
        for path in sorted(files):output.write(path,str(path.relative_to(ROOT)))
        output.writestr('DELIVERY-MANIFEST.json',json.dumps(manifest,ensure_ascii=False,indent=2))
    report={'archive':str(archive),'sha256':sha256(archive),'files':len(files),'source_sha256':manifest,
            'data_requirements':'七个 Feather 矩阵位于 feathers；逐日历史状态原始文件保留在 data/status/daily'}
    atomic_json(ROOT/'data/source-delivery-manifest.json',report)
    print(json.dumps({key:value for key,value in report.items() if key!='source_sha256'},ensure_ascii=False,indent=2))


if __name__=='__main__':package()
