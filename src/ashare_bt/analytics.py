from __future__ import annotations

from datetime import datetime
from html import escape
from importlib.metadata import version
import platform
import sys

import numpy as np

from .config import EXIT_MODES
from .utils import atomic_json, dec, dumps, sha256


def summarize(config, tables, coverage, device, reference, extra):
    equity, trades, orders = tables["equity"], tables["trades"], tables["orders"]
    units = equity.unit_nav.to_numpy(float)
    curve = np.r_[1., units]
    changes = curve[1:] / curve[:-1] - 1
    drawdown = curve / np.maximum.accumulate(curve) - 1
    cost_by_type = {}
    if len(tables["fees"]):
        for kind, frame in tables["fees"].groupby("type"):
            cost_by_type[kind] = str(sum((dec(v) for v in frame.amount), dec(0)))
    last = equity.iloc[-1]
    ledger = extra["ledger"]
    profit = dec(last.nav) - dec(config.initial_cash) - dec(last.net_external_flows)
    total_costs = sum((dec(v) for v in cost_by_type.values()), dec(0))
    summary = {
        "name": config.name, "strategy": config.strategy, "start": config.start, "end": config.end,
        "trading_days": len(equity), "initial_cash": config.initial_cash, "ending_nav": last.nav,
        "net_profit": str(profit), "return": float(units[-1] - 1),
        "annual_return": float(units[-1] ** (252 / len(units)) - 1) if units[-1] > 0 else -1.,
        "max_drawdown": float(-drawdown.min()),
        "sharpe": float(changes.mean() / changes.std(ddof=1) * np.sqrt(252)) if len(changes) > 1 and changes.std(ddof=1) > 0 else 0.,
        "average_exposure": float(equity.exposure.mean()), "ending_exposure": float(last.exposure),
        "target_exposure": float(config.target_exposure), "ending_cash": last.cash,
        "ending_market_value": last.market_value, "ending_positions": int(last.positions),
        "ending_receivables": last.receivables, "ending_pending_equity": last.pending_equity,
        "ending_liabilities": last.liabilities, "stale_value": last.stale_value,
        "first_trade_date": str(trades.date.min()) if len(trades) else None,
        "trade_count": len(trades), "order_count": len(orders),
        "total_costs": str(total_costs), "costs": cost_by_type,
        "turnover_notional": str(sum((dec(v) for v in trades.notional), dec(0))) if len(trades) else "0",
        "expired_orders": int((orders.status == "expired").sum()) if len(orders) else 0,
        "capacity_constrained_orders": int(extra["order_events"].reason.str.contains("容量").sum()) if len(extra["order_events"]) else 0,
        "capacity_constrained_notional": str(sum((dec(value) for value in orders.capacity_unfilled_notional),dec(0))) if len(orders) else "0",
        "exit_mode": config.exit_mode, "exit_label": EXIT_MODES[config.exit_mode],
        "terminal_assumptions": extra["terminal_settlements"].to_dict("records"),
        "pending_rights": ledger.pending, "receivables": ledger.receivables, "liabilities": ledger.liabilities,
        "accounting_mode": config.accounting_mode, "status_coverage": coverage,
        "compute": device, "created_at": datetime.now().astimezone().isoformat(),
        "warmup": {"first": config.warmup_start, "last_decision": str(extra["universe"].date.iloc[0])},
        "research_assumptions": [
            "当日累计复权因子推定为开盘前生效，使用总收益等价单位；原始价格用于成交和费用。" if config.accounting_mode == "total_return" else "显式公司行动以原始股数、现金、应收款及待上市权益逐项处理。",
            "完整日线的当日成交额用于开盘记录有效性核验；高低收价格用于收盘诊断。",
            "BaoStock 逐日 ST 状态推定在当日开盘前可知；带明确可获知时间的覆盖事件按其时间执行。",
            "价格边界为历史规则与复权参考价推算的候选，首次观测与业务上市事实分别记录。",
            "容量仅使用决策日已知成交额；日频开盘成交采用方向性封板规则，盘口排队由更细数据扩展。",
        ],
        "metric_definitions": {"return": "按基金份额法剔除入出金影响的区间收益", "annual_return": "以每年 252 个交易日折算",
                               "max_drawdown": "从此前最高单位净值到随后低点的最大跌幅", "sharpe": "日收益均值除以日收益标准差后年化；无风险利率取零",
                               "net_profit": "终点净资产减初始资金和净入金", "exposure": "股票市值除以净资产；待结算权益单列",
                               "capacity_constrained_notional": "因共享容量到期的委托余量按该次开盘价折算，跨日累计并包含重复尝试，买卖双向合计"},
    }
    if reference is not None:
        summary["benchmark_return"] = float(reference.unit_nav.iloc[-1] - 1)
        summary["benchmark_ending_nav"] = str(reference.nav.iloc[-1])
    return summary


def chart_svg(equity, reference=None):
    values = equity.unit_nav.to_numpy(float)
    series = [values] + ([reference.unit_nav.to_numpy(float)] if reference is not None else [])
    lower = min(float(np.min(s)) for s in series + [np.array([1.])])
    upper = max(float(np.max(s)) for s in series + [np.array([1.])])
    span = max(upper - lower, .01)
    y = lambda value: 240 - (value - lower) / span * 210
    points = lambda s: " ".join(f"{50 + i * 850 / max(1, len(s)-1):.2f},{y(v):.2f}" for i,v in enumerate(s))
    grid = "".join(f'<line x1="50" x2="900" y1="{y(v):.2f}" y2="{y(v):.2f}" stroke="#e8edf5"/><text x="5" y="{y(v)+4:.2f}" font-size="12" fill="#77849c">{(v-1)*100:.1f}%</text>' for v in np.linspace(lower, upper, 5))
    lines = ""
    for i, (series_values, color) in enumerate(zip(series, ["#315ee8", "#98a6c0"])):
        dash = 'stroke-dasharray="5,5"' if i else ""
        lines += f'<polyline points="{points(series_values)}" fill="none" stroke="{color}" stroke-width="{3 if i == 0 else 1.8}" {dash}/>'
    return f'<svg viewBox="0 0 940 290" role="img" aria-label="策略与参考组合累计收益曲线">{grid}{lines}<text x="50" y="278" font-size="12" fill="#77849c">{equity.date.iloc[0]}</text><text x="820" y="278" font-size="12" fill="#77849c">{equity.date.iloc[-1]}</text></svg>'


def write_report(directory, summary, equity, reference=None):
    s = summary
    yuan = lambda value: f"¥ {float(value):,.2f}"
    metrics = [("投资赚亏", yuan(s["net_profit"])), ("区间收益", f'{s["return"]:.2%}'),
               ("最大回撤", f'{s["max_drawdown"]:.2%}'), ("平均实际仓位", f'{s["average_exposure"]:.2%}')]
    cards = "".join(f'<div class="metric"><span>{label}</span><strong>{value}</strong></div>' for label,value in metrics)
    costs = "".join(f'<tr><td>{label}</td><td>{yuan(s["costs"].get(key,0))}</td><td>{description}</td></tr>' for key,label,description in
                    [("commission","佣金",f'单边万分之 {float(s["config"]["commission_rate"])*10000:g}，每单至少 {s["config"]["min_commission"]} 元'),
                     ("stamp_tax","印花税",f'卖出金额的万分之 {float(s["config"]["stamp_tax_rate"])*10000:g}'),
                     ("transfer","过户费","按历史生效费率"),("slippage","滑点成本",f'成交金额的万分之 {float(s["config"]["slippage_rate"])*10000:g}，独立计费'),("tax","显式税款","依注入金额应计，支付与负债分别记账"),("fee","显式费用","依注入的实际金额事件")])
    assumptions = "".join(f'<li>{escape(line)}</li>' for line in s["research_assumptions"])
    sources = "".join(f'<li><a href="{escape(item["url"],quote=True)}">{escape(item["subject"])}</a></li>' for item in s["rule_sources"])
    html = f'''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{escape(s['name'])} · 回测报告</title>
<style>body{{margin:0;background:#f5f7fc;color:#22304b;font:15px/1.8 -apple-system,BlinkMacSystemFont,"PingFang SC",sans-serif}}main{{max-width:1100px;margin:48px auto;padding:0 24px}}header,section{{background:white;border:1px solid #e4e9f2;border-radius:20px;padding:30px;margin:22px 0}}.eyebrow{{color:#315ee8;font-size:12px;letter-spacing:2px}}h1{{font-size:30px;margin:12px 0}}h2{{font-size:20px;margin:0 0 16px}}p,li{{color:#65728b}}.metrics{{display:grid;grid-template-columns:repeat(4,1fr);gap:16px}}.metric span{{display:block;color:#78859c;font-size:13px}}strong{{font-size:25px;font-variant-numeric:tabular-nums}}table{{border-collapse:collapse;width:100%;text-align:left}}td,th{{border-bottom:1px solid #edf0f7;padding:12px}}a{{color:#315ee8}}.tag{{border-radius:8px;background:#edf2ff;padding:4px 9px;color:#315ee8}}@media(max-width:700px){{.metrics{{grid-template-columns:1fr 1fr}}strong{{font-size:19px}}section,header{{padding:20px}}}}</style>
<main><header><span class="eyebrow">GUANLAN / A SHARE RESEARCH</span><h1>{escape(s['name'])}</h1><p>{s['start']} — {s['end']} · {s['trading_days']} 个交易日 · 初始资金 {yuan(s['initial_cash'])}</p><span class="tag">{s['exit_label']}</span></header>
<section class="metrics">{cards}</section><section><h2>资金经历了什么</h2><p>蓝线是策略，灰线是首次动量篮子买入持有的参考组合。收益曲线按份额计量，入出金另行记录。</p>{chart_svg(equity,reference)}</section>
<section><h2>资金的执行结果</h2><p>目标仓位 {s['target_exposure']:.1%}，平均实际仓位 {s['average_exposure']:.1%}。成交 {s['trade_count']:,} 笔，{s['capacity_constrained_orders']:,} 笔订单记录容量限制。因容量到期的委托余量累计折合 {yuan(s['capacity_constrained_notional'])}，按各次开盘价计算，包含买卖双向及跨日重复尝试。容量按每证券共享额度执行，现金和受限持仓持续列示。</p><table><tr><td>终点净资产</td><td>{yuan(s['ending_nav'])}</td></tr><tr><td>终点现金 / 股票市值</td><td>{yuan(s['ending_cash'])} / {yuan(s['ending_market_value'])}</td></tr><tr><td>应收 / 待结算权益 / 负债</td><td>{yuan(s['ending_receivables'])} / {yuan(s['ending_pending_equity'])} / {yuan(s['ending_liabilities'])}</td></tr><tr><td>陈旧估值对应市值</td><td>{yuan(s['stale_value'])}</td></tr><tr><td>首次成交</td><td>{s['first_trade_date'] or '等待合格信号'}</td></tr></table></section>
<section><h2>交易成本去向</h2><table><thead><tr><th>项目</th><th>金额</th><th>规则</th></tr></thead><tbody>{costs}<tr><td>合计</td><td>{yuan(s['total_costs'])}</td><td>费用按 Decimal 逐笔记账</td></tr></tbody></table></section>
<section><h2>结果的解释边界</h2><ul>{assumptions}</ul><p>证券池审计：{s['status_coverage']['covered_stock_days']:,} / {s['status_coverage']['required_stock_days']:,} 个待选股票日有历史状态证据。计算设备 {escape(s['compute']['device'])}，float32 / {s['compute']['block_days']} 日分块。账本、订单、成交及逐日选股文件与本报告保存在同一目录。</p></section>
<section><h2>规则来源与复现</h2><ul>{sources}</ul><p>运行编号 {escape(s['run_id'])}<br>数据指纹 {s['input_fingerprint']}<br>状态指纹 {s['status_fingerprint']}</p></section></main></html>'''
    (directory / "report.html").write_text(html, encoding="utf-8")
    packages = {}
    for name in ("numpy","pandas","pyarrow","torch","fastapi","baostock"):
        packages[name] = version(name)
    source_root = __import__("pathlib").Path(__file__).parent
    manifest = {"python": sys.version, "platform": f"{platform.system()} {platform.release()} {platform.machine()}", "dependencies": packages,
                "compute": s["compute"], "data_fingerprint": s["input_fingerprint"],
                "status_fingerprint": s["status_fingerprint"], "ranges": {"warmup": s["warmup"],"start":s["start"],"end":s["end"],"days":s["trading_days"]},
                "source_sha256": {p.name: sha256(p) for p in sorted(source_root.glob("*.py"))}}
    snapshot = directory / "source"
    snapshot.mkdir(exist_ok=True)
    for path in source_root.glob("*.py"):
        (snapshot / path.name).write_bytes(path.read_bytes())
    upstream = source_root.parents[1] / "research" / "sources" / "manifest.json"
    if upstream.exists():
        import json
        manifest["upstream_sources"] = json.loads(upstream.read_text(encoding="utf-8"))
    atomic_json(directory / "manifest.json", manifest)
