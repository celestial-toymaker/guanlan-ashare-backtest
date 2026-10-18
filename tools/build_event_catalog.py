"""从固定版本定义提取事件名，并结合本地处理契约生成逐项映射表。"""
from pathlib import Path
import ast
import re

from ashare_bt.extensions import EXTERNAL_REQUIREMENTS
from ashare_bt.utils import atomic_json

ROOT = Path(__file__).resolve().parents[1]
COMMITS = {
    "rqalpha":("ricequant/rqalpha","284b78a1975bd2d6c4bee8fde35586e6846bfd96"),
    "lean":("QuantConnect/Lean","a54e9cc6cee9030e865d4f401c03c0e2373ba199"),
    "zipline":("quantopian/zipline","014f1fc339dc8b7671d29be2d85ce57d3daec343"),
    "backtrader":("mementum/backtrader","b853d7c90b6721476eb5a5ea3135224e33db1f14"),
    "qlib":("microsoft/qlib","54355232463878d2eebb91fe0ee5fa7fa1f5976c"),
}
PROFILES = {
 "clock":("交易日生命周期与策略回调","初始化、09:00、09:30、15:00、15:01、15:02、15:05 与运行结束的固定边界",
          "交易日期、Asia/Shanghai 时区、阶段、截至当前可知行情","先规则及权益，再旧单；收盘估值、登记权益、决策、结算",
          "估值及结算形成净资产快照；回调本身形成事件记录","映射实现","src/ashare_bt/engine.py::_simulate","tests/test_engine.py::test_ten_strategies_full_clock"),
 "market":("行情可用性与数据消息","完整日线收盘可知；出现、中断、恢复、异常或零成交额变化",
           "open/high/low/close/amt/num_trades/cumadj、日期、证券","GPU 批量检测 → 收盘行情 → 估值 → 策略",
           "有效报价更新市值；中断持仓沿用最近报价并累计陈旧交易日","自动检测实现","src/ashare_bt/diagnostics.py::detect_day","tests/test_execution.py::test_blocked_open_then_intraday_opening_and_zero_amount"),
 "universe":("证券池增加、删除及候选资格变化","逐日全市场筛选所得资格发生变化",
             "证券、历史 is_st、known_at、行情有效性、历史长度、ADV20、过滤原因","收盘筛选与排名 → 回调 → 目标权重 → 订单；开盘复核买入资格",
             "资格变化影响后续委托；受限旧仓持续估值并记录退出","映射实现","src/ashare_bt/engine.py::eligibility","tests/test_engine.py::test_ten_strategies_full_clock"),
 "order":("订单状态及修改通知","提交、接受、拒绝、部分成交、成交、撤销或单次开盘后到期",
          "order_id、intent_id、证券、方向、数量、决策及执行日期、状态、理由","提交冻结 → 卖先买后 → 本单解冻复核 → 成交/到期；修改撤销重建",
          "冻结/释放现金与股数；只有成交及费用改变账户经济价值","状态机实现","src/ashare_bt/execution.py::Broker","tests/test_execution.py::test_next_open_cash_capacity_expiry_and_cancel"),
 "trade":("成交、交易持仓变化和已实现损益","合法开盘报价、可卖/资金、候选边界与共享容量均满足",
          "原始开盘价、股数、决策时容量、commission/stamp_tax/transfer/slippage","卖单先处理；每证券共享成交容量；费用与资金逐笔顺序记账",
          "现金、持仓成本、市值、已实现收益与费用同步更新；买入 T+1 锁定","撮合与账本实现","src/ashare_bt/execution.py::Broker.match_open","tests/test_execution.py::test_t1_st_open_recheck_and_quantity_rules"),
 "cash":("资金入出、基金份额、余额与净资产通知","外部资金事件生效且可获知；每次结算更新账户",
         "amount、effective_at、known_at、source；现金、净资产、份额数","先按流入前单位净值增减份额，再调整现金；结算汇总",
         "外部流量记入资本，投资收益采用单位净值剔除资金流影响","注入与记账实现","src/ashare_bt/ledger.py::Ledger.apply","tests/test_ledger.py::test_external_flows_unitization_and_proxy_mode"),
 "dividend":("现金分红登记、除息与支付","登记日保存权益；除息日确认应收；支付日转为现金",
             "action_id、record_date、ex_date、pay_date、cash_per_share、证券、known_at、source","收盘估值并保存登记日快照 → 除息应收 → 现金到账；税款独立事件",
             "登记金额保持为权益依据；应收计入净资产，到账仅资产重分类","显式处理器实现","src/ashare_bt/ledger.py::Ledger.apply","tests/test_ledger.py::test_dividend_dates_tax_duplicate_and_double_entry"),
 "split":("拆并股、送转、待上市与零碎权益","比例事件生效且可获知；到账与可交易日期到达",
          "ratio、action_id、tradable_at、证券、零碎权益结算对价","先持仓/成本/锁定调整，再同步挂单；零碎权益待结算；合法数量重新取整",
          "股数与每股成本反向调整；现金保持；零碎或待上市权益单列","显式处理器实现","src/ashare_bt/ledger.py::Ledger.apply + execution.py::Broker.on_action","tests/test_ledger.py::test_split_fraction_bonus_and_settlement"),
 "conversion":("换股合并、分拆或证券代码变更","转换生效、对价可知、权益可交易日期到达",
               "target_security、ratio、tradable_at、valuation、cash_per_share、pay_at；分拆 cost_allocation","结束原证券委托 → 原成本分配到新权益/应收 → 到期交付；代码转换保持账本衔接",
               "原持仓、目标持仓、待上市权益及现金对价分别入账","显式处理器实现","src/ashare_bt/ledger.py::Ledger.apply","tests/test_ledger.py::test_conversion_spinoff_code_and_delist"),
 "delist":("退市预警、交易资格或退市现金结算","明确状态事件、退市对价及支付日期到达",
           "effective_at、known_at、delist_warning/delisted、price、pay_at、source","预警加入持续退出；结束原委托；按明确对价记应收并到期支付",
           "受限持仓持续估值；退市应收与损益按提供对价确认","注入处理器实现；业务事实待明细","src/ashare_bt/ledger.py::Ledger.apply","tests/test_ledger.py::test_conversion_spinoff_code_and_delist"),
 "tax":("交易费用及依赖明细的显式税额","每笔成交或外部税费金额生效并可知",
        "成交金额、方向、日期、费率或税额 amount、source","成交 → 佣金/印花税/过户费/滑点；显式税款应计负债后用可用现金支付",
        "费用降低净资产；资金不足部分作为负债保留","费用实现；红利税使用显式税额","src/ashare_bt/rules.py::FeeModel + ledger.py::Ledger.accrue_charge","tests/test_execution.py::test_fees_and_history_bands"),
 "factor":("复权单位、复权价格和原始成交股数转换","累计复权因子变化；选定总收益等价单位口径",
           "原始价格、cumadj 当日及上一有效值、证券、运行口径","当日因子推定开盘前生效 → 等价单位调整 → 原始价格撮合；信号按历史可知价格计算",
           "等价数量随因子比变化，成本保持；显式模式单独处理公司行动以使经济影响计入一次","总收益代理实现","src/ashare_bt/ledger.py::Ledger.apply_factor","tests/test_ledger.py::test_external_flows_unitization_and_proxy_mode"),
 "capacity":("方向性限制、合法数量与成交容量","开盘报价触及候选价格边界或委托超过资金、可卖和决策时容量",
             "历史板块/状态、参考价/因子、价格最小单位、决策日 amt 与 ADV20","候选边界取整 → 方向限制 → 按证券共享容量 → 数量取整 → 资金及费用复核",
             "只记实际成交；余量到期并释放占用；目标与实际仓位分别展示","撮合实现","src/ashare_bt/execution.py::Broker.match_open","tests/test_execution.py::test_next_open_cash_capacity_expiry_and_cancel"),
 "timer":("策略定时与阶段调度","收盘决策和配置的调仓间隔；日内定时由细时钟扩展",
          "交易日、rebalance_days、阶段；日内扩展需要分钟/秒级时间戳","预热后首批决策 → 每日信号检查 → 周期性再平衡",
          "回调生成目标权重，后续委托经过相同账本与规则","日频映射实现；日内接口说明","src/ashare_bt/strategies.py::ComposedStrategy","tests/test_engine.py::test_ten_strategies_full_clock"),
 "storage":("持久化、完整重放与中途恢复信号","任务状态写入、回测重放或实盘检查点恢复请求",
            "config、数据及状态指纹、事件流、订单、账本、源代码哈希；恢复需游标/冻结/处理 ID 检查点","当前从固定输入完整重放；中途恢复须同步事件游标与经济状态",
            "完整重放得到一致账本；中途恢复由检查点接口扩展","完整重放实现；中途恢复接口说明","src/ashare_bt/server.py::JobQueue + events.py::EventSource","tests/test_engine.py::test_replay_and_future_market_stability"),
 "meta":("运行名称、标签、性能分析和框架消息","任务元数据、分析结果或用户控制消息变化",
         "run_id、配置、时间、来源、载荷","作为运行清单或 user 事件保存；策略接收 on_event",
         "元数据本身形成诊断；经济变化由注册账本处理器完成","元数据映射及注入接口","src/ashare_bt/events.py::EventSource + ledger.py::Ledger.register_handler","tests/test_ledger.py::test_event_order_idempotency_and_knowledge"),
}


def external(family):
    r=next(r for r in EXTERNAL_REQUIREMENTS if r.family==family)
    return (r.family+" 扩展事件",r.trigger,"、".join(r.fields),"由更细时钟/事件适配器排序后交给资产模型与策略",
            r.asset_model,"数据与资产模型需求说明",r.interface,"tests/test_catalog.py::test_external_contracts")


def generate():
    output=[]
    details = {
        "POST_SYSTEM_INIT":("系统初始化结束","配置、事件源与账户结构就绪后"),
        "BEFORE_SYSTEM_RESTORED":("恢复账户前的检查点钩子","读取检查点之后、替换运行状态之前；当前可从头重放"),
        "POST_SYSTEM_RESTORED":("恢复账户后的检查点钩子","账户、订单和事件游标恢复后；中途恢复需要完整检查点"),
        "POST_USER_INIT":("策略初始化结束","策略对象构造与参数登记完成后"),
        "POST_UNIVERSE_CHANGED":("候选证券池变化","当前可知的合格证券集合相对上一决策发生增加或删除"),
        "PRE_BEFORE_TRADING":("盘前处理之前","交易日切换后，T+1 解锁及已知公司行动处理之前"),
        "BEFORE_TRADING":("盘前策略观察阶段","已生效规则、解锁和权益完成后，开盘撮合之前"),
        "POST_BEFORE_TRADING":("盘前策略观察结束","盘前阶段完成后、开盘报价撮合之前"),
        "PRE_OPEN_AUCTION":("开盘集合竞价处理前","到达下一交易日 09:30，既有订单撮合之前"),
        "OPEN_AUCTION":("开盘撮合阶段","按原始开盘价及当日有效性假设处理既有委托"),
        "POST_OPEN_AUCTION":("开盘撮合结束","全部卖单、买单和余量到期处理完成后"),
        "PRE_BAR":("完整日线处理前","收盘完整日线可知后、账户估值更新之前"),
        "BAR":("收盘日线可知","当前交易日的高低收与日线诊断完成，提供截至当前历史"),
        "POST_BAR":("日线处理结束","收盘估值与行情通知完成后"),
        "PRE_TICK":("逐笔回调前","外部逐笔消息按时间与序号到达；需要 tick 时钟"),
        "TICK":("逐笔成交或报价消息","交易所逐笔字段与可获知时间到达"),
        "POST_TICK":("逐笔回调后","逐笔策略回调完成；需要 tick 事件适配器"),
        "PRE_SCHEDULED":("收盘调度前","当前收盘信号与调仓周期计算之前"),
        "POST_SCHEDULED":("收盘调度后","on_close 返回目标权重之后"),
        "PRE_AFTER_TRADING":("收盘策略阶段之前","日线估值和权益登记完成，开始收盘决策"),
        "AFTER_TRADING":("收盘策略阶段","当前历史截断后生成下一交易日的固定委托数量"),
        "POST_AFTER_TRADING":("收盘策略阶段结束","收盘目标、退出估算及订单登记完成后"),
        "PRE_SETTLEMENT":("日终结算前","收盘订单生成之后、资产与总账一致性核对之前"),
        "SETTLEMENT":("日终结算","检查现金、成本与借贷平衡并保存净值和持仓"),
        "POST_SETTLEMENT":("日终结算结束","日终快照保存后，准备下一交易日"),
        "ORDER_PENDING_NEW":("新委托待校验","收到策略或注入的下单请求，进入 submitted"),
        "ORDER_CREATION_PASS":("新委托接受","数量与预计可卖资格通过，现金或持仓冻结已登记"),
        "ORDER_CREATION_REJECT":("新委托拒绝","证券、数量、可卖持仓等下单校验失败"),
        "ORDER_PENDING_CANCEL":("撤单申请","收到针对尚在途订单的撤销请求"),
        "ORDER_CANCELLATION_PASS":("撤单完成","冻结释放并将订单状态置为 cancelled"),
        "ORDER_CANCELLATION_REJECT":("撤单请求未通过","订单编号待核对或订单已进入终态"),
        "ORDER_UNSOLICITED_UPDATE":("订单状态更新","开盘部分成交、全部成交或余量到期等状态变化"),
        "TRADE":("成交与持仓更新","开盘撮合产生实际模拟成交数量"),
        "ON_LINE_PROFILER_RESULT":("性能分析结果","因子设备、分块耗时与运行性能统计生成"),
        "DO_PERSIST":("持久化请求","配置、状态和运行结果写入本地原子文件"),
        "DO_RESTORE":("中途恢复请求","请求载入订单、账户、已处理事件 ID 及游标检查点"),
        "STRATEGY_HOLD_SET":("策略暂停指令","用户控制消息要求暂停策略；需要控制事件处理器"),
        "STRATEGY_HOLD_CANCELLED":("策略恢复指令","用户控制消息恢复策略；需要控制事件处理器"),
        "HEARTBEAT":("定时调度脉冲","日频时钟到达已配置边界；实时心跳需要连接时钟"),
        "BEFORE_STRATEGY_RUN":("运行开始","完整回测输入和策略对象就绪，开始初始决策之前"),
        "POST_STRATEGY_RUN":("运行完成","最后交易日结算及终点权益处理结束"),
        "USER":("自定义用户消息","JSONL 事件生效且达到可获知时间"),
        "PAY_TAXES":("税额应计和支付请求","明确税额事件生效且可获知"),
        "TAXES_PAID":("税额支付完成","可用现金用于支付已应计的税款负债"),
        "INIT_PORTFOLIO":("初始资本登记","初始资金以资本对现金的平衡分录建立账户"),
        "OnWarmupFinished":("预热结束回调","2024 年指标准备完成，开始 2024-12-31 首批决策"),
        "Initialize":("策略初始化","建立策略参数、输入字段与初始账户"),
        "PostInitialize":("初始化后钩子","策略构造及配置完成，进入预热/正式时钟"),
        "OnData":("行情切片回调","当前时间可获知的日线或扩展数据切片到达"),
        "OnFrameworkData":("框架行情切片回调","与 OnData 相同可知边界，交给策略组合模块"),
        "OnSplits":("拆并股消息回调","显式 split/stock_dividend 生效并完成持仓与挂单调整"),
        "OnDividends":("分红消息回调","登记、除息或支付阶段事件到达"),
        "OnDelistings":("退市预警与结算回调","明确的预警日期或退市结算条款到达"),
        "OnSymbolChangedEvents":("证券代码变化回调","代码转换或换股事件生效且可获知"),
        "OnSecuritiesChanged":("证券集合变化回调","候选证券池新增或删除证券"),
        "OnFrameworkSecuritiesChanged":("框架证券集合变化回调","证券池变化传播到组合策略模型"),
        "OnEndOfTimeStep":("时间片结束回调","当前日频阶段内事件已按固定顺序处理完毕"),
        "OnEndOfDay()":("全局日终回调","当前交易日结算完成；源接口保留的旧重载"),
        "OnEndOfDay(Symbol)":("单证券日终回调","指定证券完成当日估值与交易处理"),
        "OnEndOfAlgorithm":("策略终止回调","终点正常撮合、选定退出假设及报告数据完成"),
        "OnOrderEvent":("订单事件回调","订单状态转换或成交数量更新"),
        "OnMarginCall":("保证金强平指令回调","多资产账户触及强平阈值，需要担保品与负债模型"),
        "OnMarginCallWarning":("保证金预警回调","可用保证金低于资产模型阈值，需要保证金字段"),
        "OnAssignmentOrderEvent":("期权被指派通知","期权持仓被行权指派，需要行权和交收模型"),
        "OnBrokerageMessage":("券商消息通知","券商状态、错误或账户消息到达"),
        "OnBrokerageDisconnect":("券商连接中断通知","实盘连接心跳或通信层确认断开"),
        "OnBrokerageReconnect":("券商连接恢复通知","连接恢复后补报订单与账户快照"),
        "OnCommand":("外部命令回调","可获知的用户命令到达事件源"),
        "AS_TRADED_EQUITY":("原始成交口径证券消息","按原始价格/股数与选定复权口径建立证券视图"),
        "MERGER":("合并换股消息","合并比例、现金对价、目标证券与可交易日已知"),
        "SPLIT":("拆并股消息","明确比例在生效时间达到时处理"),
        "DIVIDEND":("分红消息","登记、除息与支付字段按各自日期展开"),
        "TRANSACTION":("实际成交消息","订单在允许价格和数量内生成一笔成交"),
        "ORDER":("订单消息","新订单登记或订单状态发生变化"),
        "EMPTY":("空行情消息","时间推进而当前证券缺少有效行情记录"),
        "DONE":("数据流结束消息","到达输入终点并完成终点结算"),
        "CUSTOM":("自定义数据消息","带时点和来源的扩展数据到达"),
        "BENCHMARK":("参考组合数据消息","首次动量篮子的相同成本路径生成净值"),
        "COMMISSION":("成交费用消息","成交产生佣金与其他成本"),
        "CLOSE_POSITION":("持仓结束消息","退出规则卖出或明确提供的清算对价完成权益结算"),
        "SESSION_START":("交易日开始","交易日推进，开始规则更新、解锁与到期权益"),
        "SESSION_END":("交易日结束","当日结算、净值、持仓与费用完成"),
        "MINUTE_END":("分钟结束","分钟频时钟推进；当前日频数据需扩展分钟记录"),
        "BEFORE_TRADING_START_BAR":("开盘前数据阶段","完成当日可知状态与权益更新，等待开盘撮合"),
        "_clip_amount_by_volume":("按成交容量裁剪数量","Qlib 扣除 dealt_order_amount 的累计容量；本系统按决策日成交额共享金额上限"),
        "get_amount_of_trade_unit":("复权单位对应的交易单位","Qlib 使用 trade_unit / factor；本系统将等价权益与原始成交股数分别记录"),
        "round_amount_by_trade_unit":("合法交易单位取整","Qlib 以 factor 转换取整；本系统按主板、创业板与科创板规则取整"),
        "_update_limit":("建立买卖方向交易限制","Qlib 分别计算 limit_buy/limit_sell；本系统使用候选开盘边界及状态覆盖"),
        "_calc_trade_info_by_order":("成交金额、费用和资金裁剪","Qlib 可设置平方参与率冲击；本系统默认独立万五成本，费用逐笔 Decimal"),
        "generate_order_for_target_amount_position":("目标持仓转订单","源实现使用执行区间报价/因子；本系统固定使用决策收盘资产与价格确定数量"),
    }
    def add(framework,path,name,line,profile,category="event",value=None):
        values=PROFILES.get(profile) or external(profile)
        meaning,trigger,fields,sequence,impact,status,implementation,test=values
        if name in details:
            meaning, trigger = details[name]
        elif category in {"order_status","trade_status","feed_status"}:
            leaf=name.split(".")[-1]
            status_details={"Created":("委托已创建","委托对象初始化"),"New":("委托待提交","下单对象已创建，准备校验"),
                "Submitted":("委托已提交","下单请求交给校验及登记环节"),"Accepted":("委托已接受","委托通过校验并登记冻结"),
                "Partial":("部分成交","实际成交量大于零且小于委托量"),"PartiallyFilled":("部分成交","开盘合法成交量小于委托余量"),
                "Completed":("全部成交","累计成交量达到委托数量"),"Filled":("全部成交","委托数量已全部执行"),
                "Canceled":("委托撤销","撤单生效并释放冻结"),"Cancelled":("撤销别名","源框架 Canceled 的拼写别名"),
                "CancelPending":("撤销待确认","外部券商撤单申请尚待确认；本地撤销在固定阶段立即完成"),
                "Expired":("委托到期","单次开盘撮合完成后仍有余量"),"Rejected":("委托被拒绝","提交资格或预计可卖持仓校验失败"),
                "Invalid":("无效订单","参数、证券或下单规则校验失败"),"Margin":("保证金不足状态","源框架的保证金拒单；现货账户映射为资金限制"),
                "UpdateSubmitted":("订单修改已提交","撤销旧订单并用同一决策时点重建"),"None":("初始状态占位","源框架状态占位；本地明确使用 submitted 起点"),
                "OPEN":("订单在途","订单接受后等待下一次开盘"),"FILLED":("订单已成交","委托余量为零"),"CANCELLED":("订单撤销","撤销在途订单并释放占用"),
                "REJECTED":("订单拒绝","下单资格校验失败"),"HELD":("订单挂起","源框架允许保留挂起；本地一次开盘余量到期，持久挂单需要有效期扩展"),
                "Open":("持仓打开","成交后股票数量大于零"),"Closed":("持仓关闭","退出成交或对价结算后股票数量为零"),
                "CONNECTED":("行情源已连接","连接层确认建立数据源会话"),"DISCONNECTED":("行情源已断开","连接层确认会话结束"),
                "CONNBROKEN":("行情源连接故障","通信异常触发连接中断"),"DELAYED":("行情延迟","消息时间晚于实时时钟，需延迟与可知时间字段"),
                "LIVE":("实时行情到达","数据源切换为实时推送"),"NOTSUBSCRIBED":("订阅资格待确认","订阅请求由数据源返回资格状态"),
                "NOTSUPPORTED_TF":("周期资格待确认","数据源返回周期支持状态；需对应分钟或逐笔流"),"UNKNOWN":("连接状态待核实","数据源返回尚待识别的状态码")}
            meaning,trigger=status_details.get(leaf,(meaning,trigger))
            if leaf in {"CancelPending","HELD","None"}:status="语义映射及有效期/券商接口说明"
        repo,commit=COMMITS[framework]
        output.append({"id":f"{framework}:{category}:{name}","framework":framework,"category":category,"original_name":name,
                       "original_value":value,"commit":commit,"source_path":path,"source_line":line,
                       "source_url":f"https://github.com/{repo}/blob/{commit}/{path}#L{line}",
                       "meaning":meaning,"trigger":trigger,"required_fields":fields,"processing_order":sequence,
                       "ledger_effect":impact,"implementation_status":status,"implementation":implementation,"test_location":test})
    def content(framework,path):
        return (ROOT/"research/sources"/framework/path).read_text(encoding="utf-8")
    rqpath="rqalpha/core/events.py"
    rq=ast.parse(content("rqalpha",rqpath))
    enum=next(n for n in rq.body if isinstance(n,ast.ClassDef) and n.name=="EVENT")
    for node in enum.body:
        if not isinstance(node,ast.Assign):continue
        name=node.targets[0].id
        key="clock"
        if name.startswith("ORDER_"):key="order"
        elif name=="TRADE":key="trade"
        elif "TICK" in name:key="tick"
        elif "UNIVERSE" in name:key="universe"
        elif "SCHEDULED" in name or name=="HEARTBEAT":key="timer"
        elif "RESTOR" in name or name=="DO_PERSIST":key="storage"
        elif name in {"PAY_TAXES","TAXES_PAID"}:key="tax"
        elif name=="INIT_PORTFOLIO":key="cash"
        elif name in {"USER","ON_LINE_PROFILER_RESULT","STRATEGY_HOLD_SET","STRATEGY_HOLD_CANCELLED"}:key="meta"
        add("rqalpha",rqpath,name,node.lineno,key,value=ast.literal_eval(node.value))
    for name,key in [("before_trading","clock"),("settlement","delist"),("_handle_dividend_book_closure","dividend"),
                     ("_handle_dividend_payable","dividend"),("_handle_split","split"),("_pay_dividend_tax","tax")]:
        path="rqalpha/mod/rqalpha_mod_sys_accounts/position_model.py"
        node=next(n for n in ast.walk(ast.parse(content("rqalpha",path))) if isinstance(n,ast.FunctionDef) and n.name==name)
        add("rqalpha",path,"StockPosition."+name,node.lineno,key,"account_hook")
    for path,name,key in [("rqalpha/portfolio/account.py","apply_trade","trade"),("rqalpha/portfolio/account.py","deposit_withdraw","cash"),
                          ("rqalpha/mod/rqalpha_mod_sys_transaction_cost/deciders.py","_update_tax_rate","tax")]:
        tree=ast.parse(content("rqalpha",path))
        matches=[n for n in ast.walk(tree) if isinstance(n,ast.FunctionDef) and n.name==name]
        if matches:add("rqalpha",path,name,matches[0].lineno,key,"account_hook")
    path="Common/Interfaces/IAlgorithm.cs"
    lean=content("lean",path)
    overrides={"OnSplits":"split","OnDividends":"dividend","OnDelistings":"delist","OnSymbolChangedEvents":"conversion",
               "OnSecuritiesChanged":"universe","OnFrameworkSecuritiesChanged":"universe","OnData":"market","OnFrameworkData":"market",
               "OnOrderEvent":"order","OnMarginCall":"margin","OnMarginCallWarning":"margin","OnAssignmentOrderEvent":"options",
               "OnBrokerageMessage":"live","OnBrokerageDisconnect":"live","OnBrokerageReconnect":"live","OnCommand":"meta"}
    for i,line in enumerate(lean.splitlines(),1):
        match=re.search(r"(?:void|bool\?)\s+(On\w+|Initialize|PostInitialize)\(([^;]*)\);",line)
        if match:
            method,signature=match.groups()
            name=method+("(Symbol)" if method=="OnEndOfDay" and signature else "()" if method=="OnEndOfDay" else "")
            add("lean",path,name,i,overrides.get(method,"clock"),"callback")
        match=re.search(r"event AlgorithmEvent<.*>\s+(\w+);",line)
        if match:add("lean",path,match.group(1),i,"meta","framework_event")
    path="Common/Interfaces/IBrokerage.cs"
    for i,line in enumerate(content("lean",path).splitlines(),1):
        match=re.search(r"event EventHandler<.*>\s+(\w+);",line)
        if match:add("lean",path,match.group(1),i,"options" if "Option" in match.group(1) else "live","brokerage_event")
    path="Common/Orders/OrderTypes.cs"
    text=content("lean",path)
    start=text.index("public enum OrderStatus")
    for match in re.finditer(r"^\s*(\w+)\s*=\s*(\d+),?",text[start:],re.M):
        add("lean",path,"OrderStatus."+match.group(1),text[:start+match.start()].count("\n")+1,"order","order_status",match.group(2))
    path="zipline/protocol.py"
    tree=ast.parse(content("zipline",path))
    enum=next(n for n in tree.body if isinstance(n,ast.Assign) and any(getattr(t,"id",None)=="DATASOURCE_TYPE" for t in n.targets))
    zmap={"MERGER":"conversion","SPLIT":"split","DIVIDEND":"dividend","TRANSACTION":"trade","ORDER":"order","DONE":"clock",
          "CUSTOM":"meta","BENCHMARK":"factor","COMMISSION":"tax","CLOSE_POSITION":"delist","EMPTY":"market","AS_TRADED_EQUITY":"factor"}
    for arg in enum.value.args:
        add("zipline",path,ast.literal_eval(arg),arg.lineno,zmap.get(ast.literal_eval(arg),"market"),"datasource")
    path="zipline/gens/sim_engine.pyx"
    for i,line in enumerate(content("zipline",path).splitlines(),1):
        match=re.match(r"    ([A-Z_]+) = (\d+)$",line)
        if match:add("zipline",path,match.group(1),i,"tick" if match.group(1)=="MINUTE_END" else "clock","clock",match.group(2))
    path="zipline/finance/order.py"
    tree=ast.parse(content("zipline",path))
    enum=next(n for n in tree.body if isinstance(n,ast.Assign) and any(getattr(t,"id",None)=="ORDER_STATUS" for t in n.targets))
    for arg in enum.value.args:add("zipline",path,"ORDER_STATUS."+ast.literal_eval(arg),arg.lineno,"order","order_status")
    for path,names in {"zipline/finance/ledger.py":{"capital_change":"cash","process_transaction":"trade","process_commission":"tax","process_splits":"split","pay_dividends":"dividend"},
                       "zipline/algorithm.py":{"calculate_capital_changes":"cash"}}.items():
        for node in ast.walk(ast.parse(content("zipline",path))):
            if isinstance(node,ast.FunctionDef) and node.name in names:add("zipline",path,node.name,node.lineno,names[node.name],"account_hook")
    path="backtrader/strategy.py"
    names={"start":"clock","stop":"clock","prenext_open":"clock","nextstart_open":"clock","next_open":"clock",
           "notify_order":"order","notify_trade":"trade","notify_cashvalue":"cash","notify_fund":"cash","notify_timer":"timer","notify_data":"market","notify_store":"live"}
    seen=set()
    for node in ast.walk(ast.parse(content("backtrader",path))):
        if isinstance(node,ast.FunctionDef) and node.name in names and node.name not in seen:
            add("backtrader",path,node.name,node.lineno,names[node.name],"callback");seen.add(node.name)
    path="backtrader/lineiterator.py"
    for node in ast.walk(ast.parse(content("backtrader",path))):
        if isinstance(node,ast.FunctionDef) and node.name in {"prenext","nextstart","next"} and node.name not in seen:
            add("backtrader",path,node.name,node.lineno,"clock","callback");seen.add(node.name)
    for path,names,category,key in [
        ("backtrader/order.py",["Created","Submitted","Accepted","Partial","Completed","Canceled","Expired","Margin","Rejected","Cancelled"],"order_status","order"),
        ("backtrader/feed.py",["CONNECTED","DISCONNECTED","CONNBROKEN","DELAYED","LIVE","NOTSUBSCRIBED","NOTSUPPORTED_TF","UNKNOWN"],"feed_status","live"),
        ("backtrader/trade.py",["Created","Open","Closed"],"trade_status","trade")]:
        lines=content("backtrader",path).splitlines()
        for name in names:
            line=next(i for i,s in enumerate(lines,1) if re.search(r"\b"+name+r"\b",s) and not s.lstrip().startswith(('#','-')))
            add("backtrader",path,name,line,key,category)
    path="qlib/backtest/exchange.py"
    qmap={"get_factor":"factor","get_amount_of_trade_unit":"factor","round_amount_by_trade_unit":"capacity","_update_limit":"capacity",
          "check_stock_limit":"capacity","check_stock_suspended":"market","is_stock_tradable":"capacity","_get_vol_limit":"capacity",
          "_clip_amount_by_volume":"capacity","_get_buy_amount_by_cash_limit":"capacity","_calc_trade_info_by_order":"trade",
          "deal_order":"trade","generate_amount_position_from_weight_position":"factor","generate_order_for_target_amount_position":"order"}
    for node in ast.walk(ast.parse(content("qlib",path))):
        if isinstance(node,ast.FunctionDef) and node.name in qmap:add("qlib",path,node.name,node.lineno,qmap[node.name],"comparison_hook")
    atomic_json(ROOT/"research/event_catalog.json",output)
    import pandas as pd
    pd.DataFrame(output).to_csv(ROOT/"research/event_mapping.csv",index=False,encoding="utf-8-sig")
    heading="# 固定源码版本的事件逐项映射\n\n本表逐项保留原名与原始值。`映射`表示本系统提供对应业务阶段或状态，接口说明列明确需要补充的数据与资产模型。RQAlpha 的原始拼写 `pre_open_oction` 与 `auction` 保存在原始值，内部使用统一阶段名称。\n\n"
    for framework in COMMITS:
        subset=[r for r in output if r["framework"]==framework]
        heading+=f"## {framework} · {COMMITS[framework][1]}\n\n|原名|源码|含义及触发|字段|顺序|账本影响|状态|代码及测试|\n|---|---|---|---|---|---|---|---|\n"
        for r in subset:
            heading+="|"+"|".join(str(v).replace("|"," / ").replace("\n"," ") for v in
                (r["original_name"],f'[{r["source_path"]}:{r["source_line"]}]({r["source_url"]})',r["meaning"]+"；"+r["trigger"],
                 r["required_fields"],r["processing_order"],r["ledger_effect"],r["implementation_status"],r["implementation"]+"；"+r["test_location"]))+"|\n"
        heading+="\n"
    heading+="## 扩展资产及数据契约\n\n"
    for requirement in EXTERNAL_REQUIREMENTS:
        heading+=f"- **{requirement.family}**：{requirement.trigger}。字段：{'、'.join(requirement.fields)}。入口：{requirement.interface}。资产模型：{requirement.asset_model}。\n"
    (ROOT/"research/event_mapping.md").write_text(heading,encoding="utf-8")
    print({framework:len([r for r in output if r["framework"]==framework]) for framework in COMMITS})


if __name__=="__main__":generate()
