import { useState, useEffect, useCallback, type ReactNode } from "react";
import {
  LayoutDashboard,
  FlaskConical,
  ListFilter,
  ArrowLeftRight,
  LogOut,
  Layers3,
  Play,
  ChevronRight,
  ChevronDown,
  ArrowUpRight,
  Download,
  Plus,
  X,
  Check,
  Clock3,
  CircleHelp,
  Settings2,
  Search,
  Cpu,
  CheckCircle2,
  AlertCircle,
  Loader2,
  Wallet,
  ArrowDownLeft,
  ArrowUpLeft,
  SlidersHorizontal,
  ExternalLink,
  RefreshCw,
  Square,
  Menu,
  CalendarDays,
  ChevronLeft,
  Info,
  Activity,
} from "lucide-react";
import {
  ResponsiveContainer,
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ComposedChart,
  ReferenceLine,
} from "recharts";

type Row = Record<string, any>;
type View =
  | "overview"
  | "strategies"
  | "universe"
  | "trades"
  | "exits"
  | "compare";
type Job = {
  id: string;
  status: string;
  progress: number;
  message: string;
  created_at: string;
  config: Row;
  summary?: Row;
  error?: string;
};
type Spec = {
  id: string;
  name: string;
  family: string;
  description: string;
  example: string;
  risk: string;
  defaults: Row;
  min_history: number;
  required_fields: string[];
};
type Meta = {
  defaults: Row;
  strategies: Spec[];
  exit_modes: Record<string, string>;
  filter_reasons: Record<string, string>;
  devices: Row;
  profile: Row;
  status_sync: Row;
  status_coverage: Row;
};
const number = (value: any, digits = 2) =>
  Number(value || 0).toLocaleString("zh-CN", {
    maximumFractionDigits: digits,
    minimumFractionDigits: digits,
  });
const pct = (value: any, digits = 2) =>
  `${number(Number(value || 0) * 100, digits)}%`;
const cash = (value: any) => {
  const n = Number(value || 0);
  return Math.abs(n) >= 1e8
    ? `${number(n / 1e8)} 亿`
    : Math.abs(n) >= 1e4
      ? `${number(n / 1e4)} 万`
      : number(n);
};
const statusLabels: Row = {
  queued: "排队中",
  running: "运行中",
  completed: "已完成",
  cancelled: "已取消",
  failed: "需检查",
};
const names: Row = {
  commission: "佣金",
  stamp_tax: "印花税",
  transfer: "过户费",
  slippage: "滑点成本",
  tax: "显式税款",
  fee: "显式费用",
};
const parameterLabels: Row = {
  window: "观察窗口",
  fast: "短均线周期",
  slow: "长均线周期",
  exit_window: "退出通道周期",
  entry: "进入阈值",
  exit: "退出阈值",
  deviations: "标准差倍数",
  symbol: "指定证券",
  allocation: "仓位分配",
};
const allocationLabels: Row = { equal: "等权", inverse_volatility: "逆波动率" };
const fieldLabels: Row = {
  open: "开盘价",
  high: "最高价",
  low: "最低价",
  close: "收盘价",
  amt: "成交额",
  cumadj: "累计复权因子",
  is_st: "历史 ST 状态",
};
const nav = [
  { id: "overview", label: "总览与结果", icon: LayoutDashboard },
  { id: "strategies", label: "策略实验室", icon: FlaskConical },
  { id: "universe", label: "全市场选股", icon: ListFilter },
  { id: "trades", label: "交易时间线", icon: ArrowLeftRight },
  { id: "exits", label: "退出计划", icon: LogOut },
  { id: "compare", label: "策略比较", icon: Layers3 },
];

async function api(path: string, init?: RequestInit) {
  const response = await fetch(`/api${path}`, init);
  if (!response.ok) {
    const detail = await response
      .json()
      .catch(() => ({ detail: "服务连接需要检查" }));
    throw new Error(
      typeof detail.detail === "string"
        ? detail.detail
        : JSON.stringify(detail.detail),
    );
  }
  return response.json();
}
function useRemote(path: string | null) {
  const [data, setData] = useState<any>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  useEffect(() => {
    let live = true;
    setData(null);
    setError("");
    if (!path) return;
    setLoading(true);
    api(path)
      .then((value) => {
        if (live) setData(value);
      })
      .catch((err) => {
        if (live) setError(err.message);
      })
      .finally(() => {
        if (live) setLoading(false);
      });
    return () => {
      live = false;
    };
  }, [path]);
  return { data, error, loading };
}
function Hint({ text }: { text: string }) {
  const [position, setPosition] = useState<Row>({});
  const place = (element: HTMLElement) => {
    const box = element.getBoundingClientRect();
    const width = Math.min(250, window.innerWidth - 32);
    setPosition({
      position: "fixed",
      top: box.bottom + 9,
      left: Math.max(
        16,
        Math.min(box.left - width / 2, window.innerWidth - width - 16),
      ),
      right: "auto",
      width,
    });
  };
  return (
    <span
      className="hint"
      tabIndex={0}
      aria-label={text}
      onMouseEnter={(e) => place(e.currentTarget)}
      onFocus={(e) => place(e.currentTarget)}
    >
      <CircleHelp size={13} />
      <span className="hint-bubble" style={position}>
        {text}
      </span>
    </span>
  );
}
function Pill({
  children,
  tone = "blue",
}: {
  children: ReactNode;
  tone?: string;
}) {
  return <span className={`pill ${tone}`}>{children}</span>;
}
function Empty({
  title = "先运行一次回测",
  text = "完成后，实际结果会出现在这里。",
  action,
}: {
  title?: string;
  text?: string;
  action?: ReactNode;
}) {
  return (
    <div className="empty">
      <div className="empty-icon">
        <Activity size={28} />
      </div>
      <h3>{title}</h3>
      <p>{text}</p>
      {action}
    </div>
  );
}
function SectionTitle({
  title,
  description,
  action,
}: {
  title: string;
  description?: string;
  action?: ReactNode;
}) {
  return (
    <div className="section-title">
      <div>
        <h2>{title}</h2>
        {description && <p>{description}</p>}
      </div>
      {action}
    </div>
  );
}
function Spinner() {
  return (
    <div className="loading">
      <Loader2 className="spin" size={22} /> 正在读取结果
    </div>
  );
}
function Alert({ children }: { children: ReactNode }) {
  return (
    <div className="alert">
      <AlertCircle size={17} />
      <div>{children}</div>
    </div>
  );
}

export default function App() {
  const [meta, setMeta] = useState<Meta | null>(null);
  const [jobs, setJobs] = useState<Job[]>([]);
  const [view, setView] = useState<View>("overview");
  const [activeId, setActiveId] = useState(
    new URLSearchParams(window.location.search).get("run") ||
      localStorage.getItem("guanlan-run") ||
      "",
  );
  const [config, setConfig] = useState<Row | null>(null);
  const [error, setError] = useState("");
  const [mobile, setMobile] = useState(false);
  const [tradeId, setTradeId] = useState("");
  const [focusDate, setFocusDate] = useState("");
  const [compareIds, setCompareIds] = useState<string[]>([]);
  const refresh = useCallback(() => {
    api("/runs")
      .then((items: Job[]) =>
        setJobs(
          items.map((item) => ({
            ...item,
            config: item.summary?.config || item.config,
          })),
        ),
      )
      .catch((e) => setError(e.message));
  }, []);
  useEffect(() => {
    api("/meta")
      .then(setMeta)
      .catch((e) => setError(e.message));
    refresh();
    const timer = setInterval(refresh, 2500);
    return () => clearInterval(timer);
  }, [refresh]);
  useEffect(() => {
    if (!activeId && jobs.length) {
      const completed = jobs.find((j) => j.status === "completed");
      setActiveId(completed?.id || jobs[0].id);
    }
  }, [jobs, activeId]);
  useEffect(() => {
    localStorage.setItem("guanlan-run", activeId);
  }, [activeId]);
  const job = jobs.find((j) => j.id === activeId);
  const summary = job?.summary;
  const failure = useRemote(
    job?.status === "failed" ? `/runs/${activeId}` : null,
  );
  const completed = jobs.filter((j) => j.status === "completed");
  const activeJobs = jobs.filter((j) =>
    ["running", "queued"].includes(j.status),
  );
  const equityData = useRemote(
    summary ? `/runs/${activeId}/table/equity?limit=3000` : null,
  );
  const chart = (equityData.data?.rows || []).map(
    (row: Row) => ({
      ...row,
      return: (Number(row.unit_nav) - 1) * 100,
      exposure: Number(row.exposure) * 100,
    }),
  );
  const pickView = (next: View) => {
    setView(next);
    setMobile(false);
    setError("");
  };
  const launch = async (values: Row) => {
    try {
      const started = await api("/runs", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(values),
      });
      setActiveId(started.id);
      setConfig(null);
      setView("overview");
      refresh();
    } catch (e: any) {
      setError(e.message);
      throw e;
    }
  };
  if (!meta)
    return (
      <div className="boot">
        <div className="brand-mark">观</div>
        <h1>观澜</h1>
        {error ? <Alert>{error}</Alert> : <Spinner />}
      </div>
    );
  const setup = (strategy = "momentum") => {
    const spec = meta.strategies.find((s) => s.id === strategy)!;
    setConfig({
      ...meta.defaults,
      strategy,
      name: `${spec.name} · 全市场`,
      parameters: { ...spec.defaults, allocation: "equal" },
    });
  };
  const startButton = (
    <button
      className="button primary"
      onClick={() => launch(meta.defaults).catch(() => {})}
    >
      <Play size={15} fill="currentColor" />
      运行默认示例
    </button>
  );
  return (
    <div className="app-shell">
      {mobile && (
        <button
          className="sidebar-scrim"
          onClick={() => setMobile(false)}
          aria-label="收起导航"
        />
      )}
      <aside className={`sidebar ${mobile ? "open" : ""}`}>
        <a
          className="brand"
          href="#"
          onClick={(e) => {
            e.preventDefault();
            pickView("overview");
          }}
        >
          <span className="brand-mark">
            <svg viewBox="0 0 32 32">
              <path
                d="M4 19c5 0 5-9 10-9s5 13 10 13 4-5 4-5M4 25c5 0 6-5 11-5s6 7 13 7"
                fill="none"
                stroke="currentColor"
                strokeWidth="2.6"
                strokeLinecap="round"
              />
            </svg>
          </span>
          <span>
            <strong>观澜</strong>
            <small>看懂每一次投资决策</small>
          </span>
        </a>
        <div className="sidebar-label">研究工作台</div>
        <nav>
          {nav.map(({ id, label, icon: Icon }) => (
            <button
              key={id}
              className={view === id ? "active" : ""}
              onClick={() => pickView(id as View)}
            >
              <Icon size={18} />
              <span>{label}</span>
              {id === "strategies" && <small>10</small>}
            </button>
          ))}
        </nav>
        <div className="sidebar-bottom">
          <div className="sidebar-label">
            最近的回测 <span>{jobs.length}</span>
          </div>
          {jobs.slice(0, 3).map((j) => (
            <button
              className={`recent-job ${j.id === activeId ? "selected" : ""}`}
              key={j.id}
              onClick={() => {
                setActiveId(j.id);
                pickView("overview");
              }}
            >
              <span className={`status-dot ${j.status}`} />
              <span>
                {j.config.name}
                <small>
                  {j.config.strategy} · {statusLabels[j.status]}
                </small>
              </span>
            </button>
          ))}
          <div className="local-note">
            <span className="online-dot" />
            <div>
              本地研究环境<small>人民币现货 · 日频回测</small>
            </div>
            <Cpu size={16} />
          </div>
        </div>
      </aside>
      <div className="workspace">
        <header className="topbar">
          <div className="breadcrumb">
            <button
              className="icon-button mobile-toggle"
              onClick={() => setMobile(true)}
              aria-label="展开导航"
            >
              <Menu size={21} />
            </button>
            <span>工作台</span>
            <ChevronRight size={13} />
            <strong>{nav.find((n) => n.id === view)?.label}</strong>
          </div>
          <div className="top-actions">
            <span className="device-label">
              <span className="online-dot" />
              {meta.devices.mps
                ? "Apple MPS"
                : meta.devices.cuda
                  ? "NVIDIA CUDA"
                  : "GPU 环境待连接"}
            </span>
            <button className="button small secondary" onClick={() => setup()}>
              <Plus size={15} />
              新建回测
            </button>
          </div>
        </header>
        <main>
          {error && (
            <Alert>
              {error}
              <button
                className="icon-button"
                onClick={() => setError("")}
                aria-label="关闭提示"
              >
                <X size={15} />
              </button>
            </Alert>
          )}
          {summary?.exit_planning?.uses_future_market_data && (
            <div className="soft-note" style={{ marginBottom: 20 }}>
              <Info size={19} />
              <p><strong>退出采用事后规划口径。</strong>{summary.exit_planning.disclosure}</p>
            </div>
          )}
          {activeJobs.length > 0 && (
            <div className="queue-banner">
              <div className="queue-icon">
                <Loader2 className="spin" size={20} />
              </div>
              <div>
                <strong>
                  {activeJobs.find((j) => j.status === "running")?.config
                    .name || "任务已进入队列"}
                </strong>
                <span>
                  {activeJobs.find((j) => j.status === "running")?.message ||
                    "GPU 任务依次执行，页面刷新后可继续查看。"}
                </span>
              </div>
              <div className="queue-meter">
                <div
                  style={{
                    width: `${(activeJobs.find((j) => j.status === "running")?.progress || 0) * 100}%`,
                  }}
                />
              </div>
              <span>{activeJobs.length} 个任务</span>
              <button
                className="text-button"
                onClick={() => {
                  const j =
                    activeJobs.find((j) => j.status === "running") ||
                    activeJobs[0];
                  api(`/runs/${j.id}/cancel`, { method: "POST" })
                    .then(refresh)
                    .catch((e) => setError(e.message));
                }}
              >
                <Square size={12} />
                取消当前任务
              </button>
            </div>
          )}
          {view === "overview" && (
            <>
              <div className="page-heading">
                <div>
                  <div className="eyebrow">YOUR RESEARCH, EXPLAINED</div>
                  <h1>让每一笔收益，都有来处。</h1>
                  <p>
                    从一个想法出发，看看它怎样变成真实的订单、持仓与资金变化。
                  </p>
                </div>
                <div className="heading-actions">
                  {jobs.length > 0 && (
                    <select
                      aria-label="选择回测结果"
                      className="run-select"
                      value={activeId}
                      onChange={(e) => setActiveId(e.target.value)}
                    >
                      {jobs.map((j) => (
                        <option key={j.id} value={j.id}>
                          {j.config.name} · {statusLabels[j.status]}
                        </option>
                      ))}
                    </select>
                  )}
                  {startButton}
                </div>
              </div>
              <div className="period-strip">
                <span>
                  <CalendarDays size={15} />
                  {(summary?.start || meta.defaults.start).replaceAll(
                    "-",
                    ".",
                  )}{" "}
                  — {(summary?.end || meta.defaults.end).replaceAll("-", ".")}
                </span>
                <i />
                <span>{summary?.trading_days || 424} 个交易日</span>
                <i />
                <span>2024 年预热</span>
                <i />
                <span>沪深全市场 · 非 ST</span>
                <span className="strip-right">
                  研究配置{" "}
                  <Hint text="默认资金 10 亿元；收盘决策，次日开盘成交。实际配置随所选运行保存在报告。" />
                </span>
              </div>
              {job?.status === "failed" && (
                <Alert>
                  <strong>这次运行需要检查</strong>
                  <p>{job.message}</p>
                  <button
                    className="button secondary small"
                    onClick={() => setConfig(job.config)}
                  >
                    检查配置并重试
                  </button>
                  <details>
                    <summary>查看诊断</summary>
                    <pre>{failure.data?.error || job.message}</pre>
                  </details>
                </Alert>
              )}
              {job?.status === "cancelled" && (
                <div className="soft-note" style={{ marginBottom: 20 }}>
                  <CheckCircle2 size={17} />
                  <p>
                    这次任务已取消，配置已保存。可从历史任务选择已完成结果，或重新设置本次实验。
                  </p>
                  <button
                    className="text-button"
                    onClick={() => setConfig(job.config)}
                  >
                    重新设置
                    <ChevronRight size={14} />
                  </button>
                </div>
              )}
              {equityData.error && (
                <Alert>{equityData.error}</Alert>
              )}
              <div className="metric-grid">
                <Metric
                  label={summary ? "投资赚亏" : "初始资金"}
                  hint="终点净资产减去初始资金和净入金，已扣除交易成本。"
                  value={
                    summary
                      ? `${Number(summary.net_profit) >= 0 ? "+" : ""}${cash(summary.net_profit)}`
                      : "10.00 亿"
                  }
                  unit="元"
                  sub={
                    summary
                      ? "初始资金 " + cash(summary.initial_cash) + " 元"
                      : "默认初始资金"
                  }
                  accent={
                    summary
                      ? Number(summary.net_profit) >= 0
                        ? "positive"
                        : "negative"
                      : ""
                  }
                  icon={<Wallet size={17} />}
                />
                <Metric
                  label="区间收益率"
                  hint="剔除入出金影响后，资金在整个期间增长的比例。"
                  value={summary ? pct(summary.return) : "—"}
                  sub={
                    summary
                      ? `已扣除交易成本 · 最多 ${summary.config.max_positions} 只`
                      : "运行后显示实际收益"
                  }
                  accent={
                    summary
                      ? Number(summary.return) >= 0
                        ? "positive"
                        : "negative"
                      : ""
                  }
                />
                <Metric
                  label="最大回撤"
                  hint="曾经赚到的最高点，随后最多回落了多少。例如 100 万涨至 120 万再跌至 108 万，回撤为 10%。"
                  value={summary ? pct(summary.max_drawdown) : "—"}
                  sub="从高点到低点的最大跌幅"
                />
                <Metric
                  label="平均实际仓位"
                  hint="每天股票市值占账户净资产的比例，再取平均。容量限制会让实际仓位低于目标。"
                  value={summary ? pct(summary.average_exposure) : "—"}
                  sub={`目标仓位 ${pct(summary?.target_exposure || 0.95, 0)} · 受成交规则约束`}
                />
              </div>
              <div className="overview-grid">
                <section className="panel curve-panel">
                  <SectionTitle
                    title="资金曲线"
                    description={
                      summary
                        ? `${summary.name} · 已扣除全部已计交易成本`
                        : "运行默认示例，观察资金如何随时间变化"
                    }
                    action={
                      <div className="chart-legend">
                        <span>
                          <i />
                          策略
                        </span>
                      </div>
                    }
                  />
                  {equityData.loading ? (
                    <Spinner />
                  ) : chart.length ? (
                    <EquityChart
                      data={chart}
                      onDate={(date) => {
                        setFocusDate(date);
                        pickView("trades");
                      }}
                    />
                  ) : (
                    <div className="chart-placeholder">
                      <svg viewBox="0 0 800 180" aria-hidden="true">
                        <defs>
                          <linearGradient
                            id="ghost"
                            x1="0"
                            y1="0"
                            x2="0"
                            y2="1"
                          >
                            <stop stopColor="#4b71f1" stopOpacity=".12" />
                            <stop
                              offset="1"
                              stopColor="#4b71f1"
                              stopOpacity="0"
                            />
                          </linearGradient>
                        </defs>
                        <path
                          d="M0 150C60 145 80 90 140 115S210 150 280 95 350 115 400 70 470 110 530 55 630 80 700 25 760 38 800 10V180H0Z"
                          fill="url(#ghost)"
                        />
                        <path
                          d="M0 150C60 145 80 90 140 115S210 150 280 95 350 115 400 70 470 110 530 55 630 80 700 25 760 38 800 10"
                          stroke="#c6d3fa"
                          fill="none"
                          strokeWidth="2"
                        />
                      </svg>
                      <div>
                        <Pill>等待第一份实际结果</Pill>
                        <h3>把想法交给数据验证</h3>
                        <p>曲线将在回测完成后显示，点击曲线可定位当天交易。</p>
                        {startButton}
                      </div>
                    </div>
                  )}
                  <div className="chart-footer">
                    <span>
                      <Info size={14} />
                      曲线按逐日净值展示，点击日期可查看当天交易。
                    </span>
                    {summary && (
                      <a
                        className="text-button"
                        href={`/api/runs/${activeId}/file/report.md`}
                        target="_blank"
                        rel="noreferrer"
                      >
                        Markdown 报告
                        <ArrowUpRight size={15} />
                      </a>
                    )}
                  </div>
                </section>
                <section className="panel account-panel">
                  <div className="section-title">
                    <h2>账户一览</h2>
                    <span className="icon-tile">
                      <Wallet size={17} />
                    </span>
                  </div>
                  <div className="account-total">
                    <span>终点净资产</span>
                    <strong>
                      ¥{" "}
                      {cash(summary?.ending_nav || meta.defaults.initial_cash)}
                    </strong>
                    <small>现金 + 股票 + 应收及权益 − 负债</small>
                  </div>
                  <div className="allocation-bar">
                    <span
                      style={{
                        width: `${Math.max(0, Math.min(100, Number(summary?.ending_exposure || 0) * 100))}%`,
                      }}
                    />
                  </div>
                  <div className="balance-line">
                    <span>
                      <i className="dot blue-dot" />
                      股票市值
                    </span>
                    <b>¥ {cash(summary?.ending_market_value || 0)}</b>
                  </div>
                  <div className="balance-line">
                    <span>
                      <i className="dot grey-dot" />
                      账户现金
                    </span>
                    <b>
                      ¥{" "}
                      {cash(summary?.ending_cash || meta.defaults.initial_cash)}
                    </b>
                  </div>
                  <div className="balance-line muted">
                    <span>应收与待结算权益</span>
                    <b>
                      ¥{" "}
                      {cash(
                        Number(summary?.ending_receivables || 0) +
                          Number(summary?.ending_pending_equity || 0),
                      )}
                    </b>
                  </div>
                  <div className="account-note">
                    <CheckCircle2 size={17} />
                    <span>
                      {summary ? summary.exit_label : "按规则最晚启动退出"}
                      <small>{summary?.exit_mode === "latest_feasible" || !summary ? "按后续实际可卖路径倒排" : "按所选末日规则处理"}</small>
                    </span>
                  </div>
                </section>
              </div>
              <div className="secondary-grid">
                <section className="panel">
                  <SectionTitle
                    title="从选股到成交"
                    description="策略想买多少，与规则允许买多少，分别记录。"
                    action={
                      <button
                        className="text-button"
                        onClick={() => pickView("universe")}
                      >
                        查看选股
                        <ChevronRight size={14} />
                      </button>
                    }
                  />
                  <div className="flow-steps">
                    {[
                      ["01", "扫描全市场", "逐日检查全部证券"],
                      ["02", "确认非 ST", "核对历史风险状态"],
                      ["03", "排序与分配", "因子排名 + 目标仓位"],
                      ["04", "次日开盘", "复核资金、封板与容量"],
                    ].map(([n, title, text]) => (
                      <div key={n}>
                        <span>{n}</span>
                        <strong>{title}</strong>
                        <p>{text}</p>
                      </div>
                    ))}
                  </div>
                  <div className="soft-note">
                    <SlidersHorizontal size={17} />
                    <p>
                      单只股票的成交上限为决策日成交额与 20 日均额较小值的
                      1%。10 亿资金下，实际持仓可能逐步建立。
                      {summary && (
                        <>
                          本次因容量到期的委托余量累计折合 ¥{" "}
                          {cash(summary.capacity_constrained_notional)}
                          ，含跨日重复尝试。
                        </>
                      )}
                    </p>
                  </div>
                </section>
                <section className="panel">
                  <SectionTitle
                    title="费用，也要算清楚"
                    action={
                      summary ? (
                        <a
                          className="icon-button"
                          href={`/api/runs/${activeId}/file/fees.csv`}
                          aria-label="下载费用明细"
                        >
                          <Download size={17} />
                        </a>
                      ) : undefined
                    }
                  />
                  <div className="cost-total">
                    <strong>
                      ¥ {summary ? cash(summary.total_costs) : "—"}
                    </strong>
                    <span>期间累计成本</span>
                  </div>
                  {[
                    "commission",
                    "stamp_tax",
                    "transfer",
                    "slippage",
                    ...["tax", "fee"].filter(
                      (key) => Number(summary?.costs?.[key] || 0) > 0,
                    ),
                  ].map((type) => (
                    <div className="cost-line" key={type}>
                      <span>{names[type]}</span>
                      <b>
                        {summary
                          ? `¥ ${cash(summary.costs[type] || 0)}`
                          : type === "commission"
                            ? "双边各万一"
                            : type === "stamp_tax"
                              ? "卖出万五"
                              : type === "slippage"
                                ? "成交额万五"
                                : "按历史规则"}
                      </b>
                    </div>
                  ))}
                </section>
              </div>
            </>
          )}
          {view === "strategies" && (
            <>
              <div className="page-heading">
                <div>
                  <div className="eyebrow">STRATEGY LAB</div>
                  <h1>同一套规则，检验不同想法。</h1>
                  <p>每张卡片都是一个可运行的策略。先理解原理，再调整参数。</p>
                </div>
                <Pill>10 类内置策略 · 统一账本</Pill>
              </div>
              <div className="strategy-grid">
                {meta.strategies.map((s, index) => (
                  <article className="strategy-card" key={s.id}>
                    <div className="strategy-top">
                      <span className={`strategy-icon variant-${index % 4}`}>
                        <samp>{String(index + 1).padStart(2, "0")}</samp>
                      </span>
                      <Pill tone="grey">{s.family}</Pill>
                    </div>
                    <h2>{s.name}</h2>
                    <p>{s.description}</p>
                    <div className="strategy-example">
                      <span>用金额想一想</span>
                      {s.example}
                    </div>
                    <div className="strategy-parameters">
                      {Object.entries(s.defaults).map(([key, value]) => (
                        <span key={key}>
                          {parameterLabels[key] || key} <b>{String(value)}</b>
                        </span>
                      ))}
                      {!Object.keys(s.defaults).length && (
                        <span>
                          观察窗口 <b>20 日均额</b>
                        </span>
                      )}
                    </div>
                    <div className="strategy-meta">
                      <span>≥ {s.min_history} 日历史</span>
                      <span>历史非 ST</span>
                    </div>
                    <details className="strategy-data">
                      <summary>
                        所需数据
                        <ChevronDown size={12} />
                      </summary>
                      <p>
                        {s.required_fields
                          .map((field) => fieldLabels[field] || field)
                          .join("、")}
                      </p>
                    </details>
                    <button
                      className="button secondary full"
                      onClick={() => setup(s.id)}
                    >
                      设置并运行
                      <ArrowUpRight size={16} />
                    </button>
                  </article>
                ))}
              </div>
              <div className="soft-note">
                <Layers3 size={20} />
                <p>
                  扩展策略由证券池、选股、择时、仓位分配和调仓周期组合。插件共用可获知时间截断、撮合与资金账本。
                  信号型策略逐日判断，优先延续满足条件的持仓，再按已知流动性补充名额。
                </p>
              </div>
            </>
          )}
          {["universe", "trades", "exits"].includes(view) && !summary && (
            <>
              <PageIntro view={view} />
              <section className="panel">
                <Empty action={startButton} />
              </section>
            </>
          )}
          {view === "universe" && summary && (
            <Universe
              run={activeId}
              summary={summary}
              dates={chart.map((r: Row) => r.date)}
              meta={meta}
            />
          )}
          {view === "trades" && summary && (
            <Trades
              run={activeId}
              initialDate={focusDate}
              onTrade={setTradeId}
              dates={chart.map((r: Row) => r.date)}
            />
          )}
          {view === "exits" && summary && (
            <Exits
              run={activeId}
              summary={summary}
              dates={chart.map((r: Row) => r.date)}
            />
          )}
          {view === "compare" && (
            <Compare
              jobs={completed}
              selected={compareIds}
              setSelected={setCompareIds}
              onNew={() => setup()}
            />
          )}
          <footer className="page-footer">
            <span>观澜 · 用数据理解策略，用账本解释结果</span>
            <span>Asia/Shanghai · 本地研究版</span>
          </footer>
        </main>
      </div>
      {config && (
        <ConfigModal
          initial={config}
          meta={meta}
          onClose={() => setConfig(null)}
          onRun={launch}
        />
      )}
      {tradeId && (
        <TradeDetail
          run={activeId}
          id={tradeId}
          onClose={() => setTradeId("")}
        />
      )}
    </div>
  );
}

function Metric({
  label,
  hint,
  value,
  unit,
  sub,
  accent = "",
  icon,
}: {
  label: string;
  hint: string;
  value: string;
  unit?: string;
  sub: string;
  accent?: string;
  icon?: ReactNode;
}) {
  return (
    <section className={`metric-card ${accent}`}>
      <div className="metric-label">
        {label}
        <Hint text={hint} />
        <span>{icon}</span>
      </div>
      <div className="metric-value">
        {value}
        {unit && <small>{unit}</small>}
      </div>
      <div className="metric-sub">{sub}</div>
    </section>
  );
}
function EquityChart({
  data,
  onDate,
}: {
  data: Row[];
  onDate?: (date: string) => void;
}) {
  return (
    <div className="equity-chart">
      <ResponsiveContainer width="100%" height="100%">
        <ComposedChart
          data={data}
          margin={{ top: 18, right: 14, left: 0, bottom: 8 }}
          onClick={(state: any) => {
            if (state?.activeLabel && onDate) onDate(state.activeLabel);
          }}
        >
          <defs>
            <linearGradient id="equityFill" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="#4169e8" stopOpacity={0.13} />
              <stop offset="100%" stopColor="#4169e8" stopOpacity={0} />
            </linearGradient>
          </defs>
          <CartesianGrid
            vertical={false}
            stroke="#edf0f6"
            strokeDasharray="3 4"
          />
          <XAxis
            dataKey="date"
            tickFormatter={(v) => v.slice(2, 7).replace("-", ".")}
            minTickGap={48}
            axisLine={false}
            tickLine={false}
            tick={{ fontSize: 11, fill: "#8b97ac" }}
            dy={9}
          />
          <YAxis
            tickFormatter={(v) => `${v.toFixed(0)}%`}
            width={48}
            tick={{ fontSize: 11, fill: "#8b97ac" }}
            axisLine={false}
            tickLine={false}
          />
          <Tooltip
            contentStyle={{
              borderRadius: 12,
              border: "1px solid #e6eaf2",
              boxShadow: "0 8px 30px #1a2a4b10",
              fontSize: 12,
            }}
            formatter={(v: any, name: any) => [
              `${Number(v).toFixed(2)}%`,
              "策略收益",
            ]}
          />
          <ReferenceLine y={0} stroke="#dbe1ed" />
          <Area
            type="monotone"
            dataKey="return"
            stroke="#4169e8"
            strokeWidth={2.3}
            fill="url(#equityFill)"
            animationDuration={350}
            isAnimationActive={false}
          />
        </ComposedChart>
      </ResponsiveContainer>
    </div>
  );
}
function PageIntro({ view }: { view: string }) {
  const text: Row = {
    universe: ["全市场选股", "从全部证券开始，逐项查看过滤、排序与入选理由。"],
    trades: [
      "每一笔成交，都能追溯。",
      "前一日决策、开盘成交和费用，沿着同一条时间线查看。",
    ],
    exits: [
      "为退出，留出交易时间。",
      "逐开盘核对容量、封板、数量与 T+1，查看实际路径与退出进度。",
    ],
  };
  return (
    <div className="page-heading">
      <div>
        <div className="eyebrow">{view.toUpperCase()}</div>
        <h1>{text[view][0]}</h1>
        <p>{text[view][1]}</p>
      </div>
    </div>
  );
}
function DatePick({
  value,
  onChange,
  dates,
  all = false,
}: {
  value: string;
  onChange: (v: string) => void;
  dates: string[];
  all?: boolean;
}) {
  return (
    <label className="date-picker">
      <CalendarDays size={15} />
      <select
        aria-label="选择交易日期"
        value={value}
        onChange={(e) => onChange(e.target.value)}
      >
        {all && <option value="">全部日期</option>}
        {dates.map((day) => (
          <option key={day} value={day}>
            {day}
          </option>
        ))}
      </select>
    </label>
  );
}
function Pager({
  offset,
  total,
  onChange,
}: {
  offset: number;
  total: number;
  onChange: (v: number) => void;
}) {
  return (
    <div className="pager">
      <span>
        共 {number(total, 0)} 条 · {Math.min(total, offset + 1)}–
        {Math.min(total, offset + 100)}
      </span>
      <div>
        <button
          className="icon-button"
          aria-label="上一页"
          disabled={offset === 0}
          onClick={() => onChange(Math.max(0, offset - 100))}
        >
          <ChevronLeft size={17} />
        </button>
        <button
          className="icon-button"
          aria-label="下一页"
          disabled={offset + 100 >= total}
          onClick={() => onChange(offset + 100)}
        >
          <ChevronRight size={17} />
        </button>
      </div>
    </div>
  );
}
function Universe({
  run,
  summary,
  dates,
  meta,
}: {
  run: string;
  summary: Row;
  dates: string[];
  meta: Meta;
}) {
  const [date, setDate] = useState(summary.warmup.last_decision);
  const [filter, setFilter] = useState("all");
  const [query, setQuery] = useState("");
  const [offset, setOffset] = useState(0);
  const data = useRemote(
    `/runs/${run}/table/selection?date=${date}&offset=${offset}&query=${encodeURIComponent(query)}${filter === "eligible" ? "&eligible=true" : filter === "selected" ? "&selected=true" : ""}`,
  );
  const pool = useRemote(`/runs/${run}/table/universe?date=${date}`);
  const row = pool.data?.rows[0];
  useEffect(() => setOffset(0), [date, filter, query]);
  const count = (keys: string[]) =>
    keys.reduce((n, k) => n + Number(row?.[`filtered_${k}`] || 0), 0);
  return (
    <>
      <PageIntro view="universe" />
      <div className="toolbar">
        <DatePick
          value={date}
          onChange={setDate}
          dates={[summary.warmup.last_decision, ...dates]}
        />
        <Pill tone="green">
          <CheckCircle2 size={12} />
          历史 ST 已覆盖 {number(
            summary.status_coverage.covered_stock_days,
            0,
          )}{" "}
          个待选股票日
        </Pill>
      </div>
      <div className="funnel-grid">
        {[
          ["全部证券", row?.securities, "矩阵覆盖的沪深证券"],
          ["股票范围", row?.stocks, "证券类型筛选"],
          [
            "行情与历史",
            Number(row?.stocks || 0) - count(["2", "3"]),
            "有效行情、足够历史",
          ],
          ["合格候选", row?.eligible, "历史非 ST 与流动性"],
          ["策略目标", row?.selected, "因子排名和仓位分配"],
        ].map(([label, value, note], i) => (
          <div className={`funnel-card ${i === 4 ? "final" : ""}`} key={label}>
            <span>{label}</span>
            <strong>{value === undefined ? "—" : number(value, 0)}</strong>
            <small>{note}</small>
            {i < 4 && <ChevronRight size={16} />}
          </div>
        ))}
      </div>
      <section className="panel table-panel">
        <div className="table-toolbar">
          <div className="segmented">
            {[
              ["all", "全部证券"],
              ["eligible", "合格候选"],
              ["selected", "策略目标"],
            ].map(([key, label]) => (
              <button
                key={key}
                onClick={() => setFilter(key)}
                className={filter === key ? "active" : ""}
              >
                {label}
              </button>
            ))}
          </div>
          <label className="search">
            <Search size={15} />
            <input
              placeholder="搜索证券代码"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
            />
          </label>
        </div>
        {data.loading ? (
          <Spinner />
        ) : (
          <div className="table-scroll">
            <table>
              <thead>
                <tr>
                  <th>证券</th>
                  <th>候选排名</th>
                  <th>历史状态</th>
                  <th>筛选与目标说明</th>
                  <th className="numeric">因子分数</th>
                  <th className="numeric">20 日平均成交额</th>
                  <th className="numeric">目标仓位</th>
                </tr>
              </thead>
              <tbody>
                {data.data?.rows.map((r: Row) => (
                  <tr
                    key={r.security}
                    className={r.selected ? "selected-row" : ""}
                  >
                    <td>
                      <strong>{r.security}</strong>
                      {r.selected && (
                        <span className="selected-check">
                          <Check size={12} />
                        </span>
                      )}
                    </td>
                    <td>{r.rank || "—"}</td>
                    <td>
                      <Pill
                        tone={
                          r.is_st === 0
                            ? "green"
                            : r.is_st === 1
                              ? "orange"
                              : "grey"
                        }
                      >
                        {r.is_st === 0
                          ? "非 ST"
                          : r.is_st === 1
                            ? "ST / *ST"
                            : "待核实"}
                      </Pill>
                    </td>
                    <td className="reason-cell">
                      {r.selection_reason || meta.filter_reasons[r.filter_code]}
                    </td>
                    <td className="numeric">
                      {r.score === null ? "—" : number(r.score, 5)}
                    </td>
                    <td className="numeric">¥ {cash(r.adv20)}</td>
                    <td className="numeric">
                      {r.target_weight > 0 ? pct(r.target_weight) : "—"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        <Pager
          offset={offset}
          total={data.data?.total || 0}
          onChange={setOffset}
        />
      </section>
      <div className="soft-note">
        <Info size={19} />
        <p>
          历史 ST 来源为 BaoStock
          逐日快照，并支持本地文件与事件覆盖。逐日状态推定开盘前可知；带明确时间的覆盖在可获知后生效。来源指纹：
          <code>{summary.status_fingerprint?.slice(0, 20)}</code>
          。首次出现行情作为“首次观测”保存。
        </p>
      </div>
      {data.error && <Alert>{data.error}</Alert>}
    </>
  );
}
function Trades({
  run,
  initialDate,
  onTrade,
  dates,
}: {
  run: string;
  initialDate: string;
  onTrade: (id: string) => void;
  dates: string[];
}) {
  const [date, setDate] = useState(initialDate);
  const [tab, setTab] = useState("trades");
  const [query, setQuery] = useState("");
  const [side, setSide] = useState("");
  const [offset, setOffset] = useState(0);
  const data = useRemote(
    `/runs/${run}/table/${tab}?date=${date}&query=${encodeURIComponent(query)}&offset=${offset}${side ? `&side=${side}` : ""}`,
  );
  useEffect(() => setOffset(0), [date, query, side, tab]);
  const changeDate = (value: string) => setDate(value);
  return (
    <>
      <PageIntro view="trades" />
      <section className="panel table-panel">
        <div className="table-toolbar">
          <div className="segmented">
            {[
              ["trades", "成交"],
              ["orders", "订单"],
              ["journal", "资金分录"],
              ["fees", "费用"],
            ].map(([key, label]) => (
              <button
                key={key}
                className={tab === key ? "active" : ""}
                onClick={() => setTab(key)}
              >
                {label}
              </button>
            ))}
          </div>
          <a
            className="button secondary small"
            href={`/api/runs/${run}/file/${tab}.csv`}
          >
            <Download size={14} />
            下载明细
          </a>
        </div>
        <div className="filters-row">
          <DatePick value={date} onChange={changeDate} dates={dates} all />
          <label className="search">
            <Search size={15} />
            <input
              placeholder="证券代码"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
            />
          </label>
          {["trades", "orders"].includes(tab) && (
            <select
              aria-label="买卖方向"
              value={side}
              onChange={(e) => setSide(e.target.value)}
            >
              <option value="">全部方向</option>
              <option value="buy">买入</option>
              <option value="sell">卖出</option>
            </select>
          )}
        </div>
        {data.loading ? (
          <Spinner />
        ) : data.data?.rows.length ? (
          <div className="table-scroll">
            <table>
              <thead>
                <tr>
                  {tab === "trades" ? (
                    <>
                      <th>日期 / 成交编号</th>
                      <th>证券</th>
                      <th>方向</th>
                      <th className="numeric">数量</th>
                      <th className="numeric">价格</th>
                      <th className="numeric">成交金额</th>
                      <th className="numeric">费用</th>
                      <th />
                    </>
                  ) : tab === "orders" ? (
                    <>
                      <th>决策 → 执行</th>
                      <th>订单 / 证券</th>
                      <th>方向</th>
                      <th className="numeric">委托 / 成交</th>
                      <th>状态</th>
                      <th>解释</th>
                    </>
                  ) : tab === "journal" ? (
                    <>
                      <th>日期 / 分录</th>
                      <th>证券</th>
                      <th>账户</th>
                      <th>业务</th>
                      <th className="numeric">借方</th>
                      <th className="numeric">贷方</th>
                    </>
                  ) : (
                    <>
                      <th>日期</th>
                      <th>证券</th>
                      <th>费用</th>
                      <th className="numeric">金额</th>
                      <th>订单</th>
                    </>
                  )}
                </tr>
              </thead>
              <tbody>
                {data.data.rows.map((r: Row, i: number) => (
                  <tr
                    key={i}
                    className={tab === "trades" ? "clickable" : ""}
                    onClick={() => {
                      if (tab === "trades") onTrade(r.trade_id);
                    }}
                  >
                    {tab === "trades" ? (
                      <>
                        <td>
                          {r.date}
                          <small className="cell-sub">{r.trade_id}</small>
                        </td>
                        <td>
                          <strong>{r.security}</strong>
                        </td>
                        <td>
                          <Pill tone={r.side === "buy" ? "blue" : "orange"}>
                            {r.side === "buy" ? "买入" : "卖出"}
                          </Pill>
                        </td>
                        <td className="numeric">{number(r.quantity, 0)}</td>
                        <td className="numeric">{number(r.price)}</td>
                        <td className="numeric">¥ {cash(r.notional)}</td>
                        <td className="numeric">¥ {cash(r.fees)}</td>
                        <td>
                          <ArrowUpRight size={15} />
                        </td>
                      </>
                    ) : tab === "orders" ? (
                      <>
                        <td>
                          {r.decision_date}
                          <small className="cell-sub">
                            → {r.execution_date}
                          </small>
                        </td>
                        <td>
                          {r.order_id}
                          <small className="cell-sub">{r.security}</small>
                        </td>
                        <td>{r.side === "buy" ? "买入" : "卖出"}</td>
                        <td className="numeric">
                          {number(r.quantity, 0)} / {number(r.filled, 0)}
                        </td>
                        <td>
                          <Pill tone={r.status === "filled" ? "green" : "grey"}>
                            {{
                              filled: "已成交",
                              expired: "余量到期",
                              rejected: "已拒绝",
                              cancelled: "已撤销",
                              accepted: "已接受",
                              partially_filled: "部分成交",
                            }[r.status as string] || r.status}
                          </Pill>
                        </td>
                        <td className="reason-cell">{r.last_reason}</td>
                      </>
                    ) : tab === "journal" ? (
                      <>
                        <td>
                          {r.date}
                          <small className="cell-sub">{r.entry_id}</small>
                        </td>
                        <td>{r.security || "账户"}</td>
                        <td>
                          <code>{r.account}</code>
                        </td>
                        <td>{r.type}</td>
                        <td className="numeric">{number(r.debit)}</td>
                        <td className="numeric">{number(r.credit)}</td>
                      </>
                    ) : (
                      <>
                        <td>{r.date}</td>
                        <td>{r.security}</td>
                        <td>{names[r.type] || r.type}</td>
                        <td className="numeric">¥ {number(r.amount)}</td>
                        <td>{r.order_id || r.event_id}</td>
                      </>
                    )}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <Empty
            title="这个筛选条件下有 0 条记录"
            text="可切换日期、证券代码或明细类型继续查看。"
          />
        )}
        <Pager
          offset={offset}
          total={data.data?.total || 0}
          onChange={setOffset}
        />
      </section>
      {data.error && <Alert>{data.error}</Alert>}
    </>
  );
}
function Exits({
  run,
  summary,
  dates,
}: {
  run: string;
  summary: Row;
  dates: string[];
}) {
  const [date, setDate] = useState(dates.at(-2) || summary.end);
  const [offset, setOffset] = useState(0);
  const data = useRemote(
    `/runs/${run}/table/exits?date=${date}&offset=${offset}`,
  );
  useEffect(() => setOffset(0), [date]);
  return (
    <>
      <PageIntro view="exits" />
      <div className="exit-intro">
        <div className="exit-mode-icon">
          <LogOut size={26} />
        </div>
        <div>
          <Pill>本次运行</Pill>
          <h2>{summary.exit_label}</h2>
          <p>
            {summary.exit_planning?.disclosure || "按所选末日规则执行，记录实际成交与剩余权益。"}
          </p>
        </div>
        <div className="exit-ending">
          <span>终点股票与待结算权益</span>
          <strong>
            ¥{" "}
            {cash(
              Number(summary.ending_market_value) +
                Number(summary.ending_pending_equity),
            )}
          </strong>
          <small>截至 {summary.end}</small>
        </div>
      </div>
      <section className="panel table-panel">
        <div className="table-toolbar">
          <h2>逐证券实际退出路径</h2>
          <DatePick
            value={date}
            onChange={setDate}
            dates={[summary.warmup.last_decision, ...dates]}
          />
        </div>
        {data.loading ? (
          <Spinner />
        ) : data.data?.rows.length ? (
          <div className="table-scroll">
            <table>
              <thead>
                <tr>
                  <th>证券</th>
                  <th className="numeric">持仓单位</th>
                  <th className="numeric">当前规则容量</th>
                  <th className="numeric">路径所需开盘</th>
                  <th className="numeric">剩余交易日</th>
                  <th>实际路径最晚启动日</th>
                  <th>计划 / 实际启动</th>
                  <th className="numeric">已卖 / 剩余单位</th>
                  <th>当前动作</th>
                </tr>
              </thead>
              <tbody>
                {data.data.rows.map((r: Row) => (
                  <tr key={r.security}>
                    <td>
                      <strong>{r.security}</strong>
                    </td>
                    <td className="numeric">{number(r.quantity, 3)}</td>
                    <td className="numeric">¥ {cash(r.known_capacity)}</td>
                    <td className="numeric">
                      {r.required_sessions ?? "路径受限 / 末日规则"}
                    </td>
                    <td className="numeric">{r.remaining_sessions}</td>
                    <td>{r.actual_latest_start || (r.path_feasible === false ? "路径受限" : "已结清 / 末日规则")}</td>
                    <td>
                      {r.planned_start || "等待路径触发"}
                      <small className="cell-sub">
                        实际：{r.actual_start || "等待触发"}
                      </small>
                    </td>
                    <td className="numeric">
                      {number(r.sold_quantity, 3)} /{" "}
                      {number(r.remaining_quantity ?? r.quantity, 3)}
                    </td>
                    <td>
                      <Pill tone={r.exit_active ? "orange" : "green"}>
                        {r.planned_action}
                      </Pill>
                      {r.capacity_path && JSON.parse(r.capacity_path).length > 0 && <details>
                        <summary>查看逐日容量</summary>
                        {JSON.parse(r.capacity_path).map((cell: Row, i: number) => <small className="cell-sub" key={i}>
                          {cell.date} · 容量 ¥{number(cell.capacity)} · {number(cell.quantity, 0)} 单位 × ¥{number(cell.price)}
                        </small>)}
                      </details>}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <Empty
            title="当天持仓已结清，或尚待建仓"
            text="选择其他日期可以查看每次持仓的实际退出路径。"
          />
        )}
        <Pager
          offset={offset}
          total={data.data?.total || 0}
          onChange={setOffset}
        />
      </section>
      <div className="soft-note">
        <Clock3 size={19} />
        <p>
          默认退出逐日倒排截至期末的实际可卖路径；新增买入按该次开盘容量允许的最大潜在成交量校验退出可行性，实际买入仍由资金与规则决定。后续行情仅供此功能使用。公告和外部事件继续按当前可获知时间截断。末日按规则退出保留受限权益；末日强制结清单列估值清算假设。
        </p>
      </div>
      {summary.terminal_assumptions?.length > 0 && (
        <section className="panel">
          <SectionTitle
            title="终点假设清算"
            description="这里的变现独立于正常开盘模拟成交。"
          />
          {summary.terminal_assumptions.map((r: Row, i: number) => (
            <div className="balance-line" key={i}>
              <span>
                {r.security} · {r.type}
              </span>
              <b>¥ {cash(r.gross)}</b>
            </div>
          ))}
        </section>
      )}
    </>
  );
}
function Compare({
  jobs,
  selected,
  setSelected,
  onNew,
}: {
  jobs: Job[];
  selected: string[];
  setSelected: (v: string[]) => void;
  onNew: () => void;
}) {
  const [chosen, setChosen] = useState(selected);
  const active = jobs.filter((j) => chosen.includes(j.id));
  useEffect(() => {
    if (!chosen.length && jobs.length) {
      const ids = jobs.slice(0, 3).map((j) => j.id);
      setChosen(ids);
      setSelected(ids);
    }
  }, [jobs.length]);
  const toggle = (id: string) => {
    const next = chosen.includes(id)
      ? chosen.filter((x) => x !== id)
      : [...chosen, id].slice(-6);
    setChosen(next);
    setSelected(next);
  };
  const shared = [
    "initial_cash",
    "start",
    "end",
    "exit_mode",
    "commission_rate",
    "min_commission",
    "stamp_tax_rate",
    "slippage_rate",
  ];
  const differences =
    active.length > 1
      ? shared.filter((k) =>
          active.some((j) =>
            ["start", "end", "exit_mode"].includes(k)
              ? j.config[k] !== active[0].config[k]
              : Number(j.config[k]) !== Number(active[0].config[k]),
          ),
        )
      : [];
  const configLabels: Row = {
    initial_cash: "初始资金",
    start: "开始日期",
    end: "结束日期",
    exit_mode: "退出方式",
    commission_rate: "佣金",
    min_commission: "最低佣金",
    stamp_tax_rate: "印花税",
    slippage_rate: "滑点成本",
  };
  return (
    <>
      <div className="page-heading">
        <div>
          <div className="eyebrow">SIDE BY SIDE</div>
          <h1>放在一起，才看得出差别。</h1>
          <p>用相同资金、成本和期间比较策略；配置差异也一起展示。</p>
        </div>
        <button className="button primary" onClick={onNew}>
          <Plus size={16} />
          新增比较策略
        </button>
      </div>
      {!jobs.length ? (
        <section className="panel">
          <Empty
            title="先完成一组回测"
            text="运行两个或更多策略，即可并排比较收益、回撤、仓位与费用。"
          />
        </section>
      ) : (
        <>
          <div className="compare-selector">
            {jobs.map((j) => (
              <button
                key={j.id}
                onClick={() => toggle(j.id)}
                className={chosen.includes(j.id) ? "checked" : ""}
              >
                <span className="checkbox">
                  {chosen.includes(j.id) && <Check size={12} />}
                </span>
                {j.config.name}
                <small>{j.config.strategy}</small>
              </button>
            ))}
          </div>
          {differences.length > 0 ? (
            <Alert>
              比较组存在配置差异：
              {differences.map((key) => configLabels[key]).join("、")}
              。请结合下方配置一起阅读结果。
            </Alert>
          ) : (
            <div className="soft-note">
              <CheckCircle2 size={17} />
              <p>
                当前比较组的初始资金、期间、佣金、印花税、滑点与退出方式一致。
              </p>
            </div>
          )}
          <section className="panel table-panel">
            <div className="table-scroll">
              <table className="compare-table">
                <thead>
                  <tr>
                    <th>观察维度</th>
                    {active.map((j) => (
                      <th key={j.id}>
                        {j.config.name}
                        <small className="cell-sub">{j.id.slice(0, 15)}</small>
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {[
                    ["投资赚亏", "net_profit", "cash"],
                    ["区间收益", "return", "pct"],
                    ["最大回撤", "max_drawdown", "pct"],
                    ["平均实际仓位", "average_exposure", "pct"],
                    ["累计成本", "total_costs", "cash"],
                    ["成交笔数", "trade_count", "number"],
                    ["终点剩余股票", "ending_market_value", "cash"],
                  ].map(([label, key, kind]) => (
                    <tr key={key}>
                      <td>{label}</td>
                      {active.map((j) => (
                        <td key={j.id} className="numeric">
                          {kind === "pct"
                            ? pct(j.summary?.[key])
                            : kind === "cash"
                              ? `¥ ${cash(j.summary?.[key])}`
                              : number(j.summary?.[key], 0)}
                        </td>
                      ))}
                    </tr>
                  ))}
                  {[
                    ["初始资金", "initial_cash"],
                    ["策略参数", "parameters"],
                    ["目标仓位", "target_exposure"],
                    ["调仓间隔", "rebalance_days"],
                    ["持仓上限", "max_positions"],
                    ["有效历史门槛", "min_history"],
                    ["20 日均额门槛", "min_adv20"],
                    ["成交容量比例", "participation"],
                    ["单边佣金", "commission_rate"],
                    ["每单最低佣金", "min_commission"],
                    ["卖出印花税", "stamp_tax_rate"],
                    ["独立滑点成本", "slippage_rate"],
                    ["公司行动口径", "accounting_mode"],
                    ["退出方式", "exit_mode"],
                    ["期间开始", "start"],
                    ["期间结束", "end"],
                  ].map(([label, key]) => (
                    <tr key={key}>
                      <td>{label}</td>
                      {active.map((j) => (
                        <td key={j.id}>
                          {key === "parameters"
                            ? Object.entries(j.config[key])
                                .map(
                                  ([k, v]) =>
                                    `${parameterLabels[k] || k}：${k === "allocation" ? allocationLabels[String(v)] || v : v}`,
                                )
                                .join("，")
                            : ["target_exposure", "participation"].includes(key)
                              ? pct(j.config[key])
                              : [
                                    "commission_rate",
                                    "stamp_tax_rate",
                                    "slippage_rate",
                                  ].includes(key)
                                ? `万分之 ${number(Number(j.config[key]) * 10000, 2)}`
                                : key === "min_commission"
                                  ? `¥ ${number(j.config[key])}`
                                  : key === "accounting_mode"
                                    ? j.config[key] === "explicit"
                                      ? "显式公司行动"
                                      : "总收益等价单位"
                                    : key === "exit_mode"
                                      ? {
                                          latest_feasible: "按规则最晚启动退出",
                                          force_cash: "末日强制结清",
                                          strict_end: "末日按规则退出",
                                        }[j.config[key] as string] ||
                                        j.config[key]
                                      : ["initial_cash", "min_adv20"].includes(
                                            key,
                                          )
                                        ? `¥ ${cash(j.config[key])}`
                                        : String(j.config[key])}
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>
        </>
      )}
    </>
  );
}
function ConfigModal({
  initial,
  meta,
  onClose,
  onRun,
}: {
  initial: Row;
  meta: Meta;
  onClose: () => void;
  onRun: (config: Row) => Promise<void>;
}) {
  const [config, setConfig] = useState<Row>({
    ...initial,
    parameters: { ...initial.parameters },
  });
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const spec = meta.strategies.find((s) => s.id === config.strategy)!;
  const set = (key: string, value: any) =>
    setConfig((c) => ({ ...c, [key]: value }));
  const param = (key: string, value: any) =>
    setConfig((c) => ({ ...c, parameters: { ...c.parameters, [key]: value } }));
  const label: Row = {
    window: "观察窗口（交易日）",
    fast: "短均线周期",
    slow: "长均线周期",
    exit_window: "退出通道周期",
    entry: "进入阈值",
    exit: "退出阈值",
    deviations: "标准差倍数",
    symbol: "指定证券代码",
  };
  const submit = async () => {
    setBusy(true);
    try {
      await onRun(config);
    } catch (e: any) {
      setError(e.message);
      setBusy(false);
    }
  };
  return (
    <div
      className="modal-backdrop"
      onMouseDown={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <section
        className="modal config-modal"
        role="dialog"
        aria-modal="true"
        aria-label="新建回测"
      >
        <header>
          <div>
            <span className="eyebrow">NEW EXPERIMENT</span>
            <h2>把策略变成一次实验</h2>
          </div>
          <button
            className="icon-button"
            onClick={onClose}
            aria-label="关闭设置"
          >
            <X size={21} />
          </button>
        </header>
        <div className="modal-body">
          <label className="field">
            实验名称
            <input
              value={config.name}
              onChange={(e) => set("name", e.target.value)}
            />
          </label>
          <label className="field">
            策略
            <select
              aria-label="策略"
              value={config.strategy}
              onChange={(e) => {
                const next = meta.strategies.find(
                  (s) => s.id === e.target.value,
                )!;
                setConfig((c) => ({
                  ...c,
                  strategy: next.id,
                  name: `${next.name} · 全市场`,
                  parameters: {
                    ...next.defaults,
                    allocation: c.parameters.allocation || "equal",
                  },
                }));
              }}
            >
              {meta.strategies.map((s) => (
                <option key={s.id} value={s.id}>
                  {s.name}
                </option>
              ))}
            </select>
          </label>
          <div className="config-example">
            <FlaskConical size={20} />
            <div>
              <strong>{spec.description}</strong>
              <p>{spec.example}</p>
            </div>
          </div>
          <div className="field-grid">
            <label className="field">
              开始交易
              <input
                type="date"
                value={config.start}
                onChange={(e) => set("start", e.target.value)}
              />
            </label>
            <label className="field">
              交易终点
              <input
                type="date"
                value={config.end}
                onChange={(e) => set("end", e.target.value)}
              />
            </label>
            <label className="field">
              初始资金（人民币元）
              <input
                type="number"
                min="1000"
                value={config.initial_cash}
                onChange={(e) => set("initial_cash", e.target.value)}
              />
              <small>¥ {cash(config.initial_cash)} 元</small>
            </label>
            <label className="field">
              目标股票仓位（%）
              <input
                type="number"
                min="1"
                max="100"
                value={Number(config.target_exposure) * 100}
                onChange={(e) =>
                  set("target_exposure", String(Number(e.target.value) / 100))
                }
              />
              <small>余额用于交易费用与现金缓冲</small>
            </label>
            <label className="field">
              最多持仓只数
              <input
                type="number"
                min="1"
                max="5450"
                value={config.max_positions}
                onChange={(e) => set("max_positions", Number(e.target.value))}
              />
              <small>扫描范围始终为数据覆盖的沪深全市场</small>
            </label>
            <label className="field">
              调仓间隔（交易日）
              <input
                type="number"
                min="1"
                value={config.rebalance_days}
                onChange={(e) => set("rebalance_days", Number(e.target.value))}
              />
              <small>有独立进出信号的策略逐日检查信号</small>
            </label>
            {Object.entries(spec.defaults).map(([key, value]) => (
              <label className="field" key={key}>
                {label[key] || key}
                <input
                  type={typeof value === "number" ? "number" : "text"}
                  value={config.parameters[key] ?? value}
                  onChange={(e) =>
                    param(
                      key,
                      typeof value === "number"
                        ? Number(e.target.value)
                        : e.target.value,
                    )
                  }
                />
              </label>
            ))}
            <label className="field">
              仓位分配
              <select
                value={config.parameters.allocation || "equal"}
                onChange={(e) => param("allocation", e.target.value)}
              >
                <option value="equal">等权：每只分配相同目标资金</option>
                <option value="inverse_volatility">
                  逆波动率：较低波动分配较多
                </option>
              </select>
            </label>
          </div>
          <h3 className="form-heading">最后怎样退出</h3>
          <div className="exit-options">
            {Object.entries(meta.exit_modes).map(([key, value]) => (
              <button
                key={key}
                className={config.exit_mode === key ? "chosen" : ""}
                onClick={() => set("exit_mode", key)}
              >
                <span className="radio-dot" />
                <div>
                  <strong>
                    {value}
                    {key === "latest_feasible" && <small>默认</small>}
                  </strong>
                  <p>
                    {key === "latest_feasible"
                      ? "使用截至期末的后续实际行情倒排最晚退出日，并校验新增买入能否按期退出；属于事后规划。"
                      : key === "force_cash"
                        ? "末日正常撮合后，以收盘或明确估值假设变现余量，清算假设另行列示。"
                        : "最后交易日按正常规则卖出，受限持仓与权益保留在终点报告。"}
                  </p>
                </div>
              </button>
            ))}
          </div>
          <details className="advanced">
            <summary>
              <Settings2 size={16} />
              费用、数据与高级设置
              <ChevronDown size={16} />
            </summary>
            <div className="field-grid">
              <label className="field">
                单边佣金（万分之）
                <input
                  type="number"
                  step=".1"
                  min="0"
                  value={Number(config.commission_rate) * 10000}
                  onChange={(e) =>
                    set(
                      "commission_rate",
                      String(Number(e.target.value) / 10000),
                    )
                  }
                />
              </label>
              <label className="field">
                最低佣金（元 / 单）
                <input
                  type="number"
                  min="0"
                  value={config.min_commission}
                  onChange={(e) => set("min_commission", e.target.value)}
                />
              </label>
              <label className="field">
                卖出印花税（万分之）
                <input
                  type="number"
                  min="0"
                  step=".1"
                  value={Number(config.stamp_tax_rate) * 10000}
                  onChange={(e) =>
                    set(
                      "stamp_tax_rate",
                      String(Number(e.target.value) / 10000),
                    )
                  }
                />
              </label>
              <label className="field">
                独立滑点成本（万分之）
                <input
                  type="number"
                  min="0"
                  step=".1"
                  value={Number(config.slippage_rate) * 10000}
                  onChange={(e) =>
                    set("slippage_rate", String(Number(e.target.value) / 10000))
                  }
                />
              </label>
              <label className="field">
                最少有效历史（交易日）
                <input
                  type="number"
                  min="60"
                  value={config.min_history}
                  onChange={(e) => set("min_history", Number(e.target.value))}
                />
              </label>
              <label className="field">
                20 日均额门槛（万元）
                <input
                  type="number"
                  min="0"
                  value={Number(config.min_adv20) / 10000}
                  onChange={(e) =>
                    set("min_adv20", String(Number(e.target.value) * 10000))
                  }
                />
              </label>
              <label className="field">
                成交容量比例（%）
                <input
                  type="number"
                  min=".01"
                  max="100"
                  step=".1"
                  value={Number(config.participation) * 100}
                  onChange={(e) =>
                    set("participation", String(Number(e.target.value) / 100))
                  }
                />
              </label>
              <label className="field">
                计算设备
                <select
                  value={config.device}
                  onChange={(e) => set("device", e.target.value)}
                >
                  <option value="auto">自动选择 GPU</option>
                  <option value="mps">Apple MPS</option>
                  <option value="cuda">NVIDIA CUDA</option>
                </select>
              </label>
              <label className="field">
                公司行动口径
                <select
                  value={config.accounting_mode}
                  onChange={(e) => set("accounting_mode", e.target.value)}
                >
                  <option value="total_return">
                    累计复权因子的总收益等价单位
                  </option>
                  <option value="explicit">显式事件：原始股数与现金权益</option>
                </select>
              </label>
              <label className="field">
                JSONL 事件文件
                <input
                  placeholder="例：examples/corporate_actions.jsonl"
                  value={config.events_file || ""}
                  onChange={(e) => set("events_file", e.target.value || null)}
                />
              </label>
            </div>
            <p className="field-note">
              更长的策略观察窗口会自动提高有效历史要求，并写入实际运行配置。
              预热从 2024 年开始，区间终点后数据在入口截断。默认首批委托于
              2024-12-31 收盘生成。退出口径及已确认研究假设会写入每份报告。
            </p>
          </details>
          {error && <Alert>{error}</Alert>}
        </div>
        <footer>
          <span>
            <Cpu size={15} />
            GPU 任务串行排队，配置自动保存
          </span>
          <button className="button primary" disabled={busy} onClick={submit}>
            {busy ? (
              <Loader2 className="spin" size={16} />
            ) : (
              <Play size={15} fill="currentColor" />
            )}
            开始回测
          </button>
        </footer>
      </section>
    </div>
  );
}
function TradeDetail({
  run,
  id,
  onClose,
}: {
  run: string;
  id: string;
  onClose: () => void;
}) {
  const { data, error, loading } = useRemote(`/runs/${run}/trade/${id}`);
  const trade = data?.trade;
  const order = data?.order[0];
  const selected = data?.selection[0];
  return (
    <div
      className="modal-backdrop drawer-backdrop"
      onMouseDown={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <section
        className="trade-drawer"
        role="dialog"
        aria-modal="true"
        aria-label="成交逐笔解释"
      >
        <header>
          <div>
            <div className="eyebrow">FOLLOW THE MONEY</div>
            <h2>一笔成交的来龙去脉</h2>
            <p>{id}</p>
          </div>
          <button
            className="icon-button"
            onClick={onClose}
            aria-label="关闭交易详情"
          >
            <X size={21} />
          </button>
        </header>
        {loading ? (
          <Spinner />
        ) : error ? (
          <Alert>{error}</Alert>
        ) : (
          trade && (
            <div className="drawer-body">
              <div className="trade-headline">
                <div>
                  <h2>{trade.security}</h2>
                  <span>{trade.date} · 开盘成交</span>
                </div>
                <Pill tone={trade.side === "buy" ? "blue" : "orange"}>
                  {trade.side === "buy" ? "买入" : "卖出"}
                </Pill>
              </div>
              <div className="trade-amount">
                ¥ {number(trade.notional)}
                <span>
                  {number(trade.quantity, 0)} 股 × {number(trade.price)} 元
                </span>
              </div>
              <div className="timeline">
                <TimelineStep
                  n="1"
                  title="收盘作出决策"
                  time={`${trade.decision_date} · 15:02`}
                >
                  <p>{order.reason}</p>
                  {selected && (
                    <div className="detail-pair">
                      <span>
                        当日因子排名 <b>{selected.rank || "—"}</b>
                      </span>
                      <span>
                        目标仓位 <b>{pct(selected.target_weight)}</b>
                      </span>
                    </div>
                  )}
                  <p>
                    决策价格 {number(order.reference_price)} 元，委托数量{" "}
                    {number(order.quantity, 0)} 股。
                  </p>
                </TimelineStep>
                <TimelineStep
                  n="2"
                  title="登记委托与冻结"
                  time={order.order_id}
                >
                  <p>
                    {trade.side === "buy"
                      ? "按已知价格估计占款，开盘释放本单冻结后复核现金。"
                      : "登记预计可卖持仓，开盘复核 T+1 和共享容量。"}
                  </p>
                  <div className="event-chips">
                    {data.events.map((e: Row, i: number) => (
                      <Pill key={i} tone="grey">
                        {{
                          accepted: "已接受",
                          filled: "已成交",
                          partially_filled: "部分成交",
                          expired: "余量到期",
                        }[e.to as string] || e.to}
                      </Pill>
                    ))}
                  </div>
                </TimelineStep>
                <TimelineStep
                  n="3"
                  title="下一交易日开盘成交"
                  time={`${trade.date} · 09:30`}
                >
                  <p>
                    按原始开盘价成交 {number(trade.quantity, 0)} 股，共享容量 ¥{" "}
                    {cash(trade.capacity)}；本证券当日已用 ¥{" "}
                    {cash(trade.capacity_used)}。
                  </p>
                  <p className="muted">{trade.execution_basis}</p>
                </TimelineStep>
                <TimelineStep
                  n="4"
                  title="扣除费用，更新账户"
                  time="Decimal 逐笔记账"
                >
                  <div className="fee-breakdown">
                    {["commission", "stamp_tax", "transfer", "slippage"].map(
                      (k) => (
                        <div key={k}>
                          <span>{names[k]}</span>
                          <b>¥ {number(trade[k])}</b>
                        </div>
                      ),
                    )}
                  </div>
                  <div className="total-line">
                    <span>费用合计</span>
                    <strong>¥ {number(trade.fees)}</strong>
                  </div>
                  <div className="total-line">
                    <span>成交后现金</span>
                    <strong>¥ {number(trade.cash_after)}</strong>
                  </div>
                </TimelineStep>
              </div>
              <details className="advanced">
                <summary>
                  查看对应总账分录
                  <ChevronDown size={16} />
                </summary>
                <div className="table-scroll">
                  <table>
                    <thead>
                      <tr>
                        <th>账户</th>
                        <th className="numeric">金额</th>
                      </tr>
                    </thead>
                    <tbody>
                      {data.journal.map((j: Row, i: number) => (
                        <tr key={i}>
                          <td>
                            <code>{j.account}</code>
                          </td>
                          <td className="numeric">{number(j.amount)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </details>
            </div>
          )
        )}
      </section>
    </div>
  );
}
function TimelineStep({
  n,
  title,
  time,
  children,
}: {
  n: string;
  title: string;
  time: string;
  children: ReactNode;
}) {
  return (
    <section className="timeline-step">
      <span className="timeline-number">{n}</span>
      <div>
        <div className="timeline-title">
          <h3>{title}</h3>
          <small>{time}</small>
        </div>
        {children}
      </div>
    </section>
  );
}
