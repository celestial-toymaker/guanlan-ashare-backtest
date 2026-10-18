"""保存固定提交的上游源码与许可证，供事件覆盖审计。"""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import json
import urllib.request

from ashare_bt.utils import atomic_json, sha256

ROOT = Path(__file__).resolve().parents[1]
SOURCES = {
    "rqalpha": ("ricequant/rqalpha", "284b78a1975bd2d6c4bee8fde35586e6846bfd96", [
        "rqalpha/core/events.py", "rqalpha/portfolio/account.py", "rqalpha/model/order.py",
        "rqalpha/portfolio/position.py", "rqalpha/mod/rqalpha_mod_sys_accounts/position_model.py",
        "rqalpha/mod/rqalpha_mod_sys_transaction_cost/deciders.py", "LICENSE"]),
    "lean": ("QuantConnect/Lean", "a54e9cc6cee9030e865d4f401c03c0e2373ba199", [
        "Common/Interfaces/IAlgorithm.cs", "Common/Global.cs", "Common/Orders/OrderTypes.cs", "Common/Data/Market/Dividend.cs",
        "Common/Data/Market/Split.cs", "Common/Data/Market/Delisting.cs", "Common/Data/Market/SymbolChangedEvent.cs",
        "Common/Securities/SecurityPortfolioManager.cs", "Common/Interfaces/IBrokerage.cs", "Engine/AlgorithmManager.cs", "LICENSE"]),
    "zipline": ("quantopian/zipline", "014f1fc339dc8b7671d29be2d85ce57d3daec343", [
        "zipline/protocol.py", "zipline/gens/sim_engine.pyx", "zipline/finance/order.py",
        "zipline/finance/ledger.py", "zipline/algorithm.py", "LICENSE"]),
    "backtrader": ("mementum/backtrader", "b853d7c90b6721476eb5a5ea3135224e33db1f14", [
        "backtrader/strategy.py", "backtrader/order.py", "backtrader/feed.py", "backtrader/trade.py", "backtrader/lineiterator.py", "LICENSE"]),
    "qlib": ("microsoft/qlib", "54355232463878d2eebb91fe0ee5fa7fa1f5976c", [
        "qlib/backtest/exchange.py", "qlib/backtest/position.py", "LICENSE"]),
}


def fetch(item):
    name, repo, commit, source_path = item
    url = f"https://raw.githubusercontent.com/{repo}/{commit}/{source_path}"
    path = ROOT / "research" / "sources" / name / source_path
    try:
        data = urllib.request.urlopen(url, timeout=45).read()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return {"framework": name,"repo": repo,"commit": commit,"path": source_path,"url":url,
                "local":str(path.relative_to(ROOT)),"sha256":sha256(path),"bytes":len(data)}
    except Exception as exc:
        return {"framework":name,"path":source_path,"url":url,"error":str(exc)}


if __name__ == "__main__":
    items = [(name,repo,commit,path) for name,(repo,commit,paths) in SOURCES.items() for path in paths]
    with ThreadPoolExecutor(max_workers=6) as pool:
        records = list(pool.map(fetch, items))
    atomic_json(ROOT / "research" / "sources" / "manifest.json", records)
    print(json.dumps(records,ensure_ascii=False,indent=2))
