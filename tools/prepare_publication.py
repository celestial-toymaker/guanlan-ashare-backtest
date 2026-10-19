"""按明确文件清单准备 GitHub 发布目录，保存聚合报告和逐文件校验。"""
from hashlib import sha1, sha256
from pathlib import Path
from shutil import copy2, rmtree
from zipfile import ZipFile, ZIP_DEFLATED
import json
import re

from ashare_bt.config import ROOT


SOURCE_DIRECTORIES = (
    'src/ashare_bt', 'tests', 'configs', 'examples', 'tools', 'web/src', 'web/tests',
    'research', 'reports', 'docs', 'validation',
)
ROOT_FILES = (
    'README.md', '验收记录.md', 'THIRD_PARTY_NOTICES.md', 'pyproject.toml', '.gitignore',
    '启动工作台.command', 'web/index.html', 'web/package.json', 'web/package-lock.json',
    'web/tsconfig.json', 'web/vite.config.ts', 'web/playwright.config.ts',
)
DATA_PROOFS = (
    'acceptance.json', 'png-report-check.json', 'actual-exit-check.json', 'full-acceptance.json', '5dr-report-check.json', 'profile.json',
    'audit.json', 'mps_validation.json', 'formal-status-coverage.json', 'status/coverage.json',
)
REPORT_FILES = ('report.md', 'equity-curve.png', 'summary.json', 'config.json', 'manifest.json', 'equity.csv', 'benchmark_equity.csv')
VALIDATION_FILES = (
    'python-tests.xml', 'browser-tests.json', 'full-replay-check.json', 'lifecycle-check.json',
    'lifecycle-browser.json', '5dr-browser-check.json',
    'publication-python-tests.xml', 'publication-staged-tests.xml', 'publication-frontend-build.log',
)


def copy_file(source, destination):
    destination.parent.mkdir(parents=True, exist_ok=True)
    copy2(source, destination)


def approved_file(path):
    relative = path.relative_to(ROOT)
    return (path.is_file() and not path.is_symlink()
            and all(part not in {'__pycache__', '.obsidian', 'node_modules', '.git'} for part in relative.parts)
            and path.name not in {'.DS_Store', 'check_wiki.py', 'apply_wiki_batch.py', 'prepare_wiki.py', 'wiki-approved-integrity.json'}
            and path.suffix not in {'.pyc', '.pyo', '.tsbuildinfo'})


def prepare():
    source = ROOT / 'runs/report-5dr'
    previous_path=ROOT/'reports/5dr/manifest.json'
    if previous_path.exists():
        old_chart=json.loads(previous_path.read_text()).get('report',{}).get('chart')
        if old_chart and old_chart!='equity-curve.png' and Path(old_chart).name==old_chart:
            (previous_path.parent/old_chart).unlink(missing_ok=True)
    for name in REPORT_FILES:
        if (source / name).exists():
            copy_file(source / name, ROOT / 'reports/5dr' / name)
    if (source / 'benchmark_equity.parquet').exists():
        import pandas as pd
        pd.read_parquet(source / 'benchmark_equity.parquet').to_csv(
            ROOT / 'reports/5dr/benchmark_equity.csv', index=False, encoding='utf-8-sig')
    for name in ('5dr-workbench.png', '5dr-report.png'):
        path = ROOT / 'work/screenshots' / name
        if path.exists():
            copy_file(path, ROOT / 'docs/images' / name)
    for name in VALIDATION_FILES:
        path = ROOT / 'work' / name
        if path.exists():
            copy_file(path, ROOT / 'validation' / name)

    summary = json.loads((ROOT / 'reports/5dr/summary.json').read_text())
    assert summary['strategy'] == 'reversal' and summary['config']['parameters']['window'] == 5
    assert summary['trading_days'] == 424
    files = {ROOT / name for name in ROOT_FILES}
    files.update(ROOT / 'data' / name for name in DATA_PROOFS)
    for name in SOURCE_DIRECTORIES:
        files.update(path for path in (ROOT / name).rglob('*') if approved_file(path))
    files = sorted(files)
    assert all(approved_file(path) for path in files)
    assert all('wiki' not in path.relative_to(ROOT).parts for path in files)

    # 对凭据特征逐文件检查，仅报告命中文件名和类别。
    patterns = {
        'github_token': re.compile(rb'\b(?:gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{40,})\b'),
        'private_key': re.compile(rb'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----'),
        'aws_access_key': re.compile(rb'\b(?:AKIA|ASIA)[A-Z0-9]{16}\b'),
    }
    matches = []
    manifest = []
    text_elements, binary_elements = [], []
    directory = ROOT / 'work/publication/repository'
    if directory.exists():
        assert not (directory / '.git').exists()
        rmtree(directory)
    directory.mkdir(parents=True, exist_ok=True)
    for path in files:
        relative = str(path.relative_to(ROOT))
        data = path.read_bytes()
        for kind, pattern in patterns.items():
            if pattern.search(data):
                matches.append({'path': relative, 'kind': kind})
        blob = sha1(f'blob {len(data)}\0'.encode() + data).hexdigest()
        mode = '100755' if path.name == '启动工作台.command' else '100644'
        manifest.append({'path': relative, 'bytes': len(data), 'sha256': sha256(data).hexdigest(),
                         'git_blob_sha': blob, 'mode': mode})
        copy_file(path, directory / relative)
        try:
            content = data.decode('utf-8')
        except UnicodeDecodeError:
            binary_elements.append({'path': relative, 'mode': mode, 'type': 'blob', 'sha': blob})
        else:
            text_elements.append({'path': relative, 'mode': mode, 'type': 'blob', 'content': content})
    assert not matches, matches
    metadata = ROOT / 'work/publication'
    (metadata / 'manifest.json').write_text(json.dumps({'files': manifest, 'bytes': sum(row['bytes'] for row in manifest),
        'credential_scan': 'passed', 'text_files': len(text_elements),
        'binary_files': binary_elements}, ensure_ascii=False, indent=2), encoding='utf-8')
    tree = json.dumps(text_elements, ensure_ascii=False)
    (metadata / 'tree-elements.json').write_text(tree, encoding='utf-8')
    pieces = metadata / 'transfer'
    if pieces.exists():
        rmtree(pieces)
    pieces.mkdir(exist_ok=True)
    part_count = 0
    for offset in range(0, len(tree), 24000):
        (pieces / f'{part_count:03d}.json').write_text(json.dumps(tree[offset:offset+24000], ensure_ascii=False), encoding='utf-8')
        part_count += 1
    with ZipFile(metadata / 'guanlan-ashare-backtest.zip', 'w', ZIP_DEFLATED) as output:
        for path in files:
            output.write(path, str(path.relative_to(ROOT)))
        output.writestr('PUBLICATION-MANIFEST.json', (metadata / 'manifest.json').read_text())
    print(json.dumps({'directory': str(directory), 'files': len(files), 'bytes': sum(row['bytes'] for row in manifest),
        'text_files': len(text_elements), 'binary_files': len(binary_elements), 'transfer_parts': part_count,
        'credential_scan': 'passed'}, ensure_ascii=False))


if __name__ == '__main__':
    prepare()
