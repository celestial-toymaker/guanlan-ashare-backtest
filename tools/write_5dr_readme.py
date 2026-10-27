"""从 100 只 5DR 保存结果生成入门阅读说明。"""
from decimal import Decimal as D
import json
import pandas as pd
from ashare_bt.config import ROOT


def write():
    directory=ROOT/'runs/report-5dr-100';s=json.loads((directory/'summary.json').read_text())
    cash=lambda value:f'{D(str(value)):,.2f}'
    exits=pd.read_parquet(directory/'exits.parquet');trades=pd.read_parquet(directory/'trades.parquet');examples=[]
    for security in ('000017.SZ','000037.SZ','000506.SZ','688117.SH'):
        frame=exits[(exits.security==security)&(exits.date>='2026-09-01')&exits.exit_active]
        if frame.empty:continue
        first=frame.iloc[0];sold=trades[(trades.security==security)&(trades.side=='sell')&(trades.date>first.date)]
        examples.append(f'| {security} | {D(first.quantity):,} | {sold.date.min()} | {sold.date.max()} |')
    text=f'''# 5DR：用一个小例子读懂整份回测

5DR 样例观察过去 5 个交易日的复权收益，从合格股票里优先选择近期跌幅较大的股票，研究短期回升的可能。它每 5 个交易日调整一次，最多持有 **100 只**，目标投入账户净资产的 **95%**。选满时，每只股票的目标资金为净资产的 **0.95%**。

## 先看金额

假设甲的复权价格从 10 元跌到 9 元，5 日收益为 −10%；乙从 10 元跌到 9.80 元，收益为 −2%。本样例让甲排在乙前面。教学金额方便手算，正式回测账户使用 **10 亿元人民币**；初始选满 100 只时，每只目标资金为 **950 万元**。

公式为 `5DR = 当日复权收盘价 / 5 个交易日前复权收盘价 − 1`，按从低到高排序；同分时按证券代码排序。复权收盘价为原始收盘价乘以累计复权因子。

## 这次发生了什么

| 项目 | 实际结果 |
|---|---:|
| 交易与业绩区间 | 2025-01-02 至 2026-09-30，424 日 |
| 持仓上限 | 100 只 |
| 初始资金 | {cash(s['initial_cash'])} 元 |
| 首笔成交 | {s['first_trade_date']} 开盘 |
| 投资赚亏 | {cash(s['net_profit'])} 元 |
| 区间收益 | {s['return']:.2%} |
| 最大回撤 | {s['max_drawdown']:.2%} |
| 目标仓位 / 平均实际仓位 | 95% / {s['average_exposure']:.2%} |
| 期末净资产 | {cash(s['ending_nav'])} 元 |
| 期末现金 | {cash(s['ending_cash'])} 元 |
| 期末股票及等价持仓市值 | {cash(s['ending_market_value'])} 元 |
| 已计交易成本 | {cash(s['total_costs'])} 元 |

收益是这组已声明规则下的历史模拟结果。95% 表示策略希望投入的比例，{s['average_exposure']:.2%} 表示实际平均投入的比例。10 亿元资金下，逐证券开盘容量、买卖限制和退出规划共同影响实际仓位。期末股票、应收款及待结算权益均为 0，净资产体现为现金。

**退出采用事后规划口径。** 仅退出倒排及新增买入的退出可行性校验使用截至期末的后续实际行情；策略因子、选股、策略回调和日常撮合保持原有时间边界。每次开盘容量为前一决策日成交额与截至该日的 20 日均额较小值的 1%，逐日重放封板、行情、T+1 和数量规则。完整记录位于 `exits.parquet`。

例如，某只股票持有 500 股，倒数第二个开盘实际可卖 1,000 股，最后一个开盘因容量下降只能卖 100 股，退出会在倒数第二个开盘启动。正式运行逐证券保存实际路径。

[Markdown 中文报告](report.md)包含资金曲线、成本、状态覆盖和研究假设；蓝线展示 5DR 的每日累计收益。[PNG 图片](equity-curve.png)与[账户净值 CSV](equity.csv)对应全部 424 个交易日；精确金额和配置见 [summary.json](summary.json) 与 [config.json](config.json)。

![5DR 中文报告](../../docs/images/5dr-report.png)

## 实际退出记录

以下记录来自本次 100 只版本的实际账本：

| 证券 | 启动决策时持仓单位 | 实际首笔卖出 | 结清日 |
|---|---:|---|---|
{chr(10).join(examples)}

总收益等价单位中的零碎权益随整股退出结算；冻结数量按在途订单逐项重算。逐证券容量路径、启动日与成交进度可在工作台退出页面查看。

## 如何重跑

完成根目录 README 的安装与课程数据准备后运行：

```bash
.venv/bin/ashare-bt run --config configs/5dr.toml
.venv/bin/ashare-bt ui
```

配置采用 `strategy = "reversal"`、`window = 5`、`max_positions = 100` 与等权分配。2024 年数据用于预热，2024-12-31 收盘生成首批委托；次日开盘按实际价格、历史非 ST、资金、数量、容量和方向限制执行。

## 代码与证据

- [样例 TOML](../../configs/5dr.toml)：资金、费用、期间、窗口与持仓上限。
- [策略实现](../../src/ashare_bt/strategies.py)：5DR 信号及原始精度排名复核。
- [实际退出路径](../../src/ashare_bt/exit_path.py)与[退出验收](../../data/actual-exit-check.json)：实际容量、开盘价和结清核对。
- [5DR 核对](../../data/5dr-report-check.json)与[完整重放](../../validation/5dr100-replay-check.json)：100 只配置的逐笔一致性。
- [前 100 名精度核对](../../data/5dr100-ranking-check.json)：MPS 与原始精度的 425 日排名一致。
- [PNG 图片核对](../../data/png-report-check.json)与[来源清单](manifest.json)：单曲线、尺寸、数据及源码哈希。
- [课程讨论](https://github.com/aslan9/pku_quantllm/issues/8#issuecomment-6215092680)：5DR 的正向和反转用法，本样例采用反转方向。

完整逐笔结果保存在本机 `runs/{s['run_id']}`。公开报告保存聚合结果与来源指纹；历史状态、当日复权因子和成交额的研究假设见 Markdown 报告第 6 节。
'''
    (ROOT/'reports/5dr/README.md').write_text(text)


if __name__=='__main__':write()
