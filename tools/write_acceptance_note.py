"""依据已保存证据生成交付与验收记录。"""
from decimal import Decimal as D
import json
from ashare_bt.config import ROOT


def write():
    acceptance=json.loads((ROOT/'data/acceptance.json').read_text());assert acceptance['passed']
    s=json.loads((ROOT/'runs/report-5dr-100/summary.json').read_text())
    completed=json.loads((ROOT/'data/full-acceptance.json').read_text())
    refresh=json.loads((ROOT/'data/report-refresh-check.json').read_text())
    example=json.loads((ROOT/'data/5dr-report-check.json').read_text())
    exits=json.loads((ROOT/'data/actual-exit-check.json').read_text())
    cash=lambda value:f'{D(str(value)):,.2f}'
    names={item['strategy']:item['name'] for item in acceptance['strategies']}
    rows=[f"| {names[item['strategy']]} | {item['return']:.2%} | {cash(item['net_profit'])} | {item['max_drawdown']:.2%} | {item['average_exposure']:.2%} | {item['trade_count']:,} |" for item in completed['strategies']]
    text=f'''# 观澜工作台交付与验收记录

## 1. 打开与研究口径

双击根目录的 `启动工作台.command`，或运行 `.venv/bin/ashare-bt ui`。[5DR 本地样例](http://127.0.0.1:8765/?run=report-5dr-100)对应本次 100 只股票版本。

交易与业绩区间为 **2025-01-02 至 2026-09-30，共 424 个交易日**；2024 年数据用于预热，2024-12-31 收盘生成首批委托，2025-01-02 开盘首笔成交。加载区间包含 666 日、5,451 列证券，其中 5,450 列属于沪深股票范围。

账户初始资金 **10 亿元人民币**。佣金单边万一、每单最低 5 元，卖出印花税万五，另计历史过户费与独立滑点万五。逐日历史非 ST、60 日有效历史及 20 日平均成交额 2,000 万元构成基础资格；次日开盘复核资金、T+1、数量和方向限制。

每证券开盘共享容量为 **1% × min（前一决策日成交额，截至该日的 20 日平均成交额）**。默认使用实际可卖路径倒排最晚启动退出日，包含新增买入能否按期退出的校验。**后续行情的使用仅限此功能，属于事后规划口径。** 策略因子、选股、策略回调及日常撮合保持原有时间边界，公告按当前可获知时间筛选。

## 2. 100 只股票的 5DR 样例

`configs/5dr.toml` 采用过去 5 日复权收益从低到高排序，同分按证券代码；每 5 个交易日调仓，最多 **100 只**，目标仓位 **95%**，等权分配。选满时，每只目标权重为 **0.95%**，初始对应 **950 万元**。

教学例子：甲从 10 元跌到 9 元，5DR 为 −10%；乙跌到 9.80 元，5DR 为 −2%。甲优先入选，表达观察短期回升的策略假设。复权价格等于原始价格乘以累计复权因子，实际成交和费用使用原始价格。

| 观察项目 | 本次实际结果 |
|---|---:|
| 区间收益 | {s['return']:.2%} |
| 投资赚亏 | {cash(s['net_profit'])} 元 |
| 最大回撤 | {s['max_drawdown']:.2%} |
| 平均实际仓位 | {s['average_exposure']:.2%} |
| 成交笔数 | {s['trade_count']:,} |
| 累计成本 | {cash(s['total_costs'])} 元 |
| 期末净资产及现金 | {cash(s['ending_nav'])} 元 |
| 期末股票、应收款、待结算权益 | 均为 0 |
| 首批目标 / 实际持仓峰值 | {example['first_target_count']} / {example['max_actual_positions']} 只 |

资金曲线采用 1880×580 白底 PNG，蓝线展示该策略全部 424 个交易日的累计收益。目标仓位与实际仓位分别记录，容量到期委托余量累计折合 **{cash(s['capacity_constrained_notional'])} 元**；该值包含买卖双向和跨日重复尝试。

## 3. 十类策略既有结果

以下十类策略沿用已验收的参数，其中排名策略持仓上限为 20 只；该表与上节新重算的 100 只 5DR 分别记录。资金、期间、成本、历史状态来源及退出方式一致。此次依据保存账本刷新单策略报告，{sum(item['financial_files_checked'] for item in refresh['runs'])} 个主策略财务文件逐项保持一致，原始来源与刷新记录均保留。

| 策略 | 区间收益 | 投资赚亏（元） | 最大回撤 | 平均实际仓位 | 成交笔数 |
|---|---:|---:|---:|---:|---:|
{chr(10).join(rows)}

## 4. 验收证据

- **数据与历史状态**：七矩阵对齐，2024 预热和业绩隔离，终点后数据入口截断；正式待选股票日覆盖 {s['status_coverage']['covered_stock_days']:,} / {s['status_coverage']['required_stock_days']:,}，待核实数量为 0。
- **100 只样例与完整重放**：MPS 全区间重算，首批目标 100 只、单只 0.95%，每日目标及实际持仓均在上限内；订单、成交、账本、净值、持仓、费用、退出、证券池、选股、订单事件及终点结算共 11 张表精确一致。见 [5DR 核对](data/5dr-report-check.json)与[重放证据](validation/5dr100-replay-check.json)。
- **排名精度**：Apple M3 Pro / PyTorch 2.5.1 / float32 / 128 日分块；425 个决策日的前 100 名与原始精度排序一致。见[排名核对](data/5dr100-ranking-check.json)。原有 64/128/256 日分块、33 项因子及十类策略信号验收见 [MPS 证据](data/mps_validation.json)。
- **逐笔执行与账本**：核对历史非 ST、次日开盘、方向限制、T+1、共享容量、费用、借贷平衡及终点净资产；主策略模拟函数和 10 个执行模块与原发布版本逐项一致。见[主策略实现核对](data/main-strategy-preservation.json)。
- **实际退出路径**：核对 {exits['projected_fills_checked']:,} 条路径成交的实际开盘价、当次规则容量、日期范围与共享上限；十类既有策略及新 5DR 样例均结清股票及待结算权益。见[退出验收](data/actual-exit-check.json)。
- **报告与图片**：11 份单策略报告均使用 1880×580 白底 PNG；测试覆盖全部原始日线点、日期刻度、单曲线及零交易结果。见[图片核对](data/png-report-check.json)与[历史报告刷新核对](data/report-refresh-check.json)。
- **程序与浏览器**：{acceptance['python_tests']} 项 Python 测试、{acceptance['browser_tests']} 项浏览器测试通过；覆盖报告下载、历史配置读入、单策略曲线、100 只目标、交易解释、退出页面、比较页面、任务持久化与取消。
- **公司行动与因果性**：人工金额测试覆盖分红多日期、税款、拆并股与挂单、零碎权益、配股、换股、分拆、代码转换及退市对价；未来行情和公告的访问边界、三种退出方式均由测试核对。
- **CUDA**：设备无关 PyTorch 实现及验收脚本保持可用，NVIDIA 实机验收待具备环境后运行 `.venv/bin/python tools/validate_gpu.py --device cuda`。
- **来源盘点**：RQAlpha、LEAN、Zipline、Backtrader、Qlib 共 177 项逐项映射，固定提交及来源见[事件映射](research/event_mapping.md)。

## 5. 文件与复现

- [5DR 入门说明](reports/5dr/README.md)、[Markdown 报告](reports/5dr/report.md)、[PNG 曲线](reports/5dr/equity-curve.png)、[样例配置](configs/5dr.toml)。
- [综合验收](data/acceptance.json)、[Python 结果](validation/python-tests.xml)、[浏览器结果](validation/browser-tests.json)、[十类策略结果](data/full-acceptance.json)。
- 每次运行保存配置、净值、订单、成交、借贷分录、持仓、费用、退出路径、证券池、逐日选股、事件及源码快照。本次编号为 `report-5dr-100`；完整重放编号为 `report-5dr-100-replay`。
- `manifest.json` 保存依赖、设备、行情及状态指纹、源码哈希。十类历史报告额外保存原始模拟来源与报告刷新信息。源码交付包可用 `.venv/bin/python tools/package_source.py` 生成。

研究假设包括当日累计复权因子的开盘前生效推定、完整日线成交额对开盘记录的有效性核验，以及 BaoStock 逐日风险状态的开盘前可知推定。候选涨跌停、首次观测与估值状态保留推断或来源标签，完整解释范围见每份报告。
'''
    (ROOT/'验收记录.md').write_text(text)
    print('已生成100只5DR及单策略报告验收记录')


if __name__=='__main__':write()
