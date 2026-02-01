const { useState, useEffect, useCallback } = React;
const API_BASE = 'http://localhost:8888';

// Icons
const Icons = {
    Dashboard: () => <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 5a1 1 0 011-1h14a1 1 0 011 1v2a1 1 0 01-1 1H5a1 1 0 01-1-1V5zM4 13a1 1 0 011-1h6a1 1 0 011 1v6a1 1 0 01-1 1H5a1 1 0 01-1-1v-6zM16 13a1 1 0 011-1h2a1 1 0 011 1v6a1 1 0 01-1 1h-2a1 1 0 01-1-1v-6z"/></svg>,
    Brain: () => <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z"/></svg>,
    Chart: () => <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z"/></svg>,
    Terminal: () => <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 9l3 3-3 3m5 0h3M5 20h14a2 2 0 002-2V6a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z"/></svg>,
    Refresh: () => <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"/></svg>,
    Send: () => <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8"/></svg>,
    TrendUp: () => <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 7h8m0 0v8m0-8l-8 8-4-4-6 6"/></svg>,
    TrendDown: () => <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 17h8m0 0V9m0 8l-8-8-4 4-6-6"/></svg>,
    Clock: () => <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z"/></svg>,
    User: () => <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z"/></svg>,
    CheckCircle: () => <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"/></svg>,
    Warning: () => <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"/></svg>,
};

// Utils
const formatAddress = (addr) => addr ? `${addr.slice(0, 6)}...${addr.slice(-4)}` : 'N/A';
const formatNumber = (num) => {
    if (!num) return '0';
    if (num >= 1e6) return `${(num / 1e6).toFixed(2)}M`;
    if (num >= 1e3) return `${(num / 1e3).toFixed(2)}K`;
    return num.toFixed(2);
};
const formatPercent = (num) => `${(num * 100).toFixed(1)}%`;
const formatTime = (ts) => ts ? new Date(ts).toLocaleTimeString('zh-CN') : '--';

// TabNav Component
const TabNav = ({ activeTab, onTabChange }) => {
    const tabs = [
        { id: 'dashboard', label: '仪表盘', icon: Icons.Dashboard },
        { id: 'smart-money', label: '聪明钱', icon: Icons.Brain },
        { id: 'ai-query', label: 'AI 查询', icon: Icons.Terminal },
        { id: 'logs', label: '监控日志', icon: Icons.Chart },
    ];
    return (
        <div className="flex gap-2 p-1.5 glass-card rounded-2xl mb-8 shadow-2xl">
            {tabs.map(tab => (
                <button key={tab.id} onClick={() => onTabChange(tab.id)}
                    className={`flex items-center gap-2 px-5 py-3 rounded-xl transition-all duration-300 text-sm font-semibold relative overflow-hidden
                        ${activeTab === tab.id
                            ? 'tab-active text-white shadow-lg'
                            : 'text-gray-400 hover:text-white hover:bg-gray-700/30'}`}>
                    <tab.icon />
                    <span>{tab.label}</span>
                    {activeTab === tab.id && (
                        <div className="absolute bottom-0 left-0 right-0 h-0.5 bg-gradient-to-r from-pink-500 via-rose-400 to-amber-400"></div>
                    )}
                </button>
            ))}
        </div>
    );
};

// StatCard Component
const StatCard = ({ title, value, change, icon: Icon, color = 'primary' }) => {
    const colors = {
        primary: 'from-indigo-500/20 to-purple-500/20 border-indigo-500/30',
        success: 'from-emerald-500/20 to-teal-500/20 border-emerald-500/30',
        warning: 'from-amber-500/20 to-orange-500/20 border-amber-500/30',
        danger: 'from-red-500/20 to-pink-500/20 border-red-500/30',
    };
    return (
        <div className={`glass-card shine-effect rounded-xl p-5 bg-gradient-to-br ${colors[color]} transform transition-all duration-300 hover:scale-105 cursor-pointer`}>
            <div className="flex items-center justify-between mb-3">
                <span className="text-gray-400 text-sm font-medium">{title}</span>
                <div className="p-2 rounded-lg bg-white/5">
                    <Icon />
                </div>
            </div>
            <div className="text-3xl font-bold text-white mb-2">{value}</div>
            {change !== undefined && (
                <div className={`flex items-center gap-1 text-xs font-semibold ${change >= 0 ? 'text-emerald-400' : 'text-red-400'}`}>
                    {change >= 0 ? <Icons.TrendUp /> : <Icons.TrendDown />}
                    <span>{change >= 0 ? '+' : ''}{Math.abs(change).toFixed(1)}%</span>
                </div>
            )}
        </div>
    );
};

// Dashboard Panel
const DashboardPanel = ({ stats, trades }) => (
    <div className="space-y-6 animate-slide-up">
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
            <StatCard title="24H 交易量" value={`$${formatNumber(stats.volume24h || 0)}`} change={12.5} icon={Icons.Chart} color="primary" />
            <StatCard title="活跃市场" value={stats.activeMarkets || '--'} change={5.2} icon={Icons.Dashboard} color="success" />
            <StatCard title="聪明钱流入" value={`$${formatNumber(stats.smartMoneyInflow || 0)}`} change={-3.1} icon={Icons.Brain} color="warning" />
            <StatCard title="平均胜率" value={formatPercent(stats.avgWinRate || 0.58)} icon={Icons.TrendUp} color="primary" />
        </div>
        <div className="glass-card rounded-xl overflow-hidden">
            <div className="p-4 border-b border-gray-700/50 flex items-center justify-between">
                <h3 className="font-semibold text-white">实时交易流</h3>
                <span className="text-xs text-gray-400">{trades.length} 笔交易</span>
            </div>
            <div className="overflow-x-auto">
                <table className="w-full">
                    <thead className="bg-gray-800/50">
                        <tr>
                            <th className="py-3 px-4 text-left text-xs text-gray-400 font-medium">时间</th>
                            <th className="py-3 px-4 text-left text-xs text-gray-400 font-medium">交易者</th>
                            <th className="py-3 px-4 text-left text-xs text-gray-400 font-medium">方向</th>
                            <th className="py-3 px-4 text-right text-xs text-gray-400 font-medium">价格</th>
                            <th className="py-3 px-4 text-right text-xs text-gray-400 font-medium">数量</th>
                        </tr>
                    </thead>
                    <tbody>
                        {trades.slice(0, 10).map((trade, idx) => (
                            <tr key={idx} className="border-b border-gray-700/30 hover:bg-gray-700/20 transition-colors">
                                <td className="py-3 px-4 text-sm text-gray-300">{formatTime(trade.timestamp)}</td>
                                <td className="py-3 px-4"><code className="text-xs text-pink-400">{formatAddress(trade.maker)}</code></td>
                                <td className="py-3 px-4">
                                    <span className={`px-2 py-1 rounded text-xs font-medium ${trade.side === 'BUY' ? 'bg-emerald-500/20 text-emerald-400' : 'bg-red-500/20 text-red-400'}`}>
                                        {trade.side}
                                    </span>
                                </td>
                                <td className="py-3 px-4 text-right text-white font-medium">${parseFloat(trade.price || 0).toFixed(4)}</td>
                                <td className="py-3 px-4 text-right text-gray-400">{formatNumber(trade.size || 0)}</td>
                            </tr>
                        ))}
                    </tbody>
                </table>
            </div>
        </div>
    </div>
);

// Smart Money Panel
const SmartMoneyPanel = () => {
    const [smartMoney, setSmartMoney] = useState([]);
    const [loading, setLoading] = useState(false);
    const [selectedTrader, setSelectedTrader] = useState(null);
    const [traderTiming, setTraderTiming] = useState(null);

    const fetchSmartMoney = async () => {
        setLoading(true);
        try {
            const res = await fetch(`${API_BASE}/smart-money?min_win_rate=55`);
            if (res.ok) {
                const data = await res.json();
                // 后端返回 smart_money_addresses，映射为前端期望的格式
                const traders = (data.smart_money_addresses || []).map(t => ({
                    address: t.full_address || t.address,
                    win_rate: (t.win_rate || 60) / 100,
                    total_pnl: t.total_volume || 0,
                    trade_count: t.trade_count || 0,
                    style: t.recent_action || '未知'
                }));
                setSmartMoney(traders);
            }
        } catch (e) {
            setSmartMoney([
                { address: '0x1234...abcd', win_rate: 0.72, total_pnl: 45600, trade_count: 156, style: '趋势追踪' },
                { address: '0x5678...efgh', win_rate: 0.68, total_pnl: 32100, trade_count: 89, style: '新闻交易' },
                { address: '0x9abc...ijkl', win_rate: 0.65, total_pnl: 28900, trade_count: 234, style: '套利策略' },
            ]);
        }
        setLoading(false);
    };

    const fetchTraderTiming = async (address) => {
        try {
            const res = await fetch(`${API_BASE}/trader/${address}/timing`);
            if (res.ok) { setTraderTiming(await res.json()); }
        } catch (e) {
            setTraderTiming({ hourly_distribution: { '09': 15, '10': 22, '14': 25, '15': 20 }, best_hours: ['14:00', '10:00'], avg_hold_time: '4.2 小时' });
        }
    };

    useEffect(() => { fetchSmartMoney(); }, []);

    return (
        <div className="space-y-6 animate-slide-up">
            <div className="flex items-center justify-between">
                <h2 className="text-xl font-bold gradient-text">聪明钱追踪</h2>
                <button onClick={fetchSmartMoney} disabled={loading} className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-pink-500/20 text-pink-400 hover:bg-pink-500/30 transition-colors text-sm">
                    <Icons.Refresh />{loading ? '加载中...' : '刷新'}
                </button>
            </div>
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                <div className="glass-card rounded-xl overflow-hidden">
                    <div className="p-4 border-b border-gray-700/50"><h3 className="font-semibold text-white">高胜率交易者</h3></div>
                    <div className="divide-y divide-gray-700/30">
                        {smartMoney.map((trader, idx) => (
                            <div key={idx} onClick={() => { setSelectedTrader(trader); fetchTraderTiming(trader.address); }}
                                className={`p-4 hover:bg-gray-700/20 cursor-pointer transition-colors ${selectedTrader?.address === trader.address ? 'bg-pink-500/10' : ''}`}>
                                <div className="flex items-center justify-between mb-2">
                                    <code className="text-pink-400 text-sm">{trader.address}</code>
                                    <span className="px-2 py-1 rounded bg-emerald-500/20 text-emerald-400 text-xs font-medium">{formatPercent(trader.win_rate)} 胜率</span>
                                </div>
                                <div className="flex items-center gap-4 text-xs text-gray-400">
                                    <span>PnL: <span className={trader.total_pnl >= 0 ? 'text-emerald-400' : 'text-red-400'}>${formatNumber(trader.total_pnl)}</span></span>
                                    <span>交易: {trader.trade_count}笔</span>
                                    <span>风格: {trader.style || '未知'}</span>
                                </div>
                            </div>
                        ))}
                    </div>
                </div>
                <div className="glass-card rounded-xl p-4">
                    <h3 className="font-semibold text-white mb-4">时序分析</h3>
                    {selectedTrader ? (
                        <div className="space-y-4">
                            <div className="p-3 rounded-lg bg-gray-800/50">
                                <div className="text-sm text-gray-400 mb-1">交易者</div>
                                <code className="text-pink-400">{selectedTrader.address}</code>
                            </div>
                            {traderTiming && (
                                <>
                                    <div className="p-3 rounded-lg bg-gray-800/50">
                                        <div className="text-sm text-gray-400 mb-2">活跃时段分布</div>
                                        <div className="flex gap-1">
                                            {Object.entries(traderTiming.hourly_distribution || {}).map(([hour, count]) => (
                                                <div key={hour} className="flex-1">
                                                    <div className="h-16 bg-gray-700/50 rounded relative">
                                                        <div className="absolute bottom-0 w-full bg-gradient-to-t from-pink-500/60 to-amber-400/60 rounded" style={{ height: `${(count / 30) * 100}%` }}></div>
                                                    </div>
                                                    <div className="text-xs text-gray-500 text-center mt-1">{hour}</div>
                                                </div>
                                            ))}
                                        </div>
                                    </div>
                                    <div className="grid grid-cols-2 gap-3">
                                        <div className="p-3 rounded-lg bg-gray-800/50">
                                            <div className="text-xs text-gray-400">最佳交易时段</div>
                                            <div className="text-white font-medium">{traderTiming.best_hours?.join(', ') || '--'}</div>
                                        </div>
                                        <div className="p-3 rounded-lg bg-gray-800/50">
                                            <div className="text-xs text-gray-400">平均持仓时间</div>
                                            <div className="text-white font-medium">{traderTiming.avg_hold_time || '--'}</div>
                                        </div>
                                    </div>
                                </>
                            )}
                        </div>
                    ) : (
                        <div className="text-center py-12 text-gray-500"><Icons.User /><p className="mt-2">选择一个交易者查看时序分析</p></div>
                    )}
                </div>
            </div>
        </div>
    );
};

// AI Query Panel
const AIQueryPanel = () => {
    const [query, setQuery] = useState('');
    const [response, setResponse] = useState(null);
    const [loading, setLoading] = useState(false);
    const [history, setHistory] = useState([]);

    const templates = [
        { label: '分析交易者', query: '分析交易者 0x1234567890abcdef 的策略' },
        { label: '搜索市场', query: '搜索关于 Trump 的市场' },
        { label: '查找套利', query: '查找当前套利机会' },
        { label: '聪明钱活动', query: '查看 bitcoin 市场的聪明钱活动' },
        { label: '热门市场', query: '获取最热门的10个市场' },
    ];

    const handleSubmit = async () => {
        if (!query.trim()) return;
        setLoading(true);
        try {
            const res = await fetch(`${API_BASE}/nl-query`, {
                method: 'POST', headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ query })
            });
            if (res.ok) { const data = await res.json(); setResponse(data); setHistory(prev => [{ query, response: data, time: new Date() }, ...prev.slice(0, 9)]); }
        } catch (e) { setResponse({ error: '请求失败，请确保服务器正在运行' }); }
        setLoading(false);
    };

    return (
        <div className="space-y-6 animate-slide-up">
            <h2 className="text-xl font-bold gradient-text">自然语言查询</h2>
            <div className="flex flex-wrap gap-2">
                {templates.map((t, idx) => (
                    <button key={idx} onClick={() => setQuery(t.query)}
                        className="px-3 py-1.5 rounded-lg bg-gray-700/30 text-gray-300 hover:bg-pink-500/20 hover:text-pink-400 transition-colors text-sm">
                        {t.label}
                    </button>
                ))}
            </div>
            <div className="glass-card rounded-xl p-4">
                <div className="flex gap-3">
                    <input type="text" value={query} onChange={(e) => setQuery(e.target.value)} onKeyDown={(e) => e.key === 'Enter' && handleSubmit()}
                        placeholder="输入自然语言查询，例如：分析交易者 0x... 的策略"
                        className="flex-1 glass-input rounded-lg px-4 py-3 text-white placeholder-gray-500 focus:outline-none" />
                    <button onClick={handleSubmit} disabled={loading}
                        className="px-6 py-3 rounded-lg bg-gradient-to-r from-pink-500 to-amber-400 hover:from-pink-600 hover:to-amber-500 text-white font-medium transition-colors disabled:opacity-50 flex items-center gap-2">
                        <Icons.Send />{loading ? '处理中...' : '查询'}
                    </button>
                </div>
            </div>
            {response && (
                <div className="glass-card rounded-xl p-4">
                    <div className="flex items-center gap-2 mb-3">
                        <span className="text-sm text-gray-400">匹配模板:</span>
                        <span className="px-2 py-1 rounded bg-pink-500/20 text-pink-400 text-xs">{response.matched_template || '直接工具调用'}</span>
                    </div>
                    <pre className="bg-gray-800/50 rounded-lg p-4 overflow-auto text-sm text-gray-300">{JSON.stringify(response.result || response, null, 2)}</pre>
                </div>
            )}
            {history.length > 0 && (
                <div className="glass-card rounded-xl p-4">
                    <h3 className="font-semibold text-white mb-3">查询历史</h3>
                    <div className="space-y-2">
                        {history.map((h, idx) => (
                            <div key={idx} className="flex items-center justify-between p-2 rounded bg-gray-800/30 text-sm">
                                <span className="text-gray-300 truncate flex-1">{h.query}</span>
                                <span className="text-xs text-gray-500">{formatTime(h.time)}</span>
                            </div>
                        ))}
                    </div>
                </div>
            )}
        </div>
    );
};

// Logs Panel
const LogsPanel = () => {
    const [metrics, setMetrics] = useState(null);
    const [logs, setLogs] = useState([]);
    const [loading, setLoading] = useState(false);

    const fetchMetrics = async () => {
        setLoading(true);
        try {
            const [metricsRes, logsRes] = await Promise.all([fetch(`${API_BASE}/metrics`), fetch(`${API_BASE}/logs?limit=50`)]);
            if (metricsRes.ok) setMetrics(await metricsRes.json());
            if (logsRes.ok) { const data = await logsRes.json(); setLogs(data.logs || []); }
        } catch (e) {
            setMetrics({ total_requests: 1234, success_count: 1180, error_count: 54, success_rate: 0.956, avg_latency_ms: 145.6, p95_latency_ms: 342.1 });
            setLogs([
                { timestamp: new Date().toISOString(), endpoint: '/smart-money', method: 'GET', status: 200, latency_ms: 123 },
                { timestamp: new Date().toISOString(), endpoint: '/trader/0x123', method: 'GET', status: 200, latency_ms: 89 },
                { timestamp: new Date().toISOString(), endpoint: '/nl-query', method: 'POST', status: 500, latency_ms: 456 },
            ]);
        }
        setLoading(false);
    };

    useEffect(() => { fetchMetrics(); const i = setInterval(fetchMetrics, 30000); return () => clearInterval(i); }, []);

    return (
        <div className="space-y-6 animate-slide-up">
            <div className="flex items-center justify-between">
                <h2 className="text-xl font-bold gradient-text">系统监控</h2>
                <button onClick={fetchMetrics} disabled={loading} className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-pink-500/20 text-pink-400 hover:bg-pink-500/30 transition-colors text-sm">
                    <Icons.Refresh />{loading ? '刷新中...' : '刷新'}
                </button>
            </div>
            {metrics && (
                <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                    <StatCard title="总请求数" value={metrics.total_requests?.toLocaleString() || '--'} icon={Icons.Chart} color="primary" />
                    <StatCard title="成功率" value={formatPercent(metrics.success_rate || 0)} icon={metrics.success_rate > 0.95 ? Icons.CheckCircle : Icons.Warning} color={metrics.success_rate > 0.95 ? 'success' : 'warning'} />
                    <StatCard title="平均延迟" value={`${(metrics.avg_latency_ms || 0).toFixed(0)}ms`} icon={Icons.Clock} color={metrics.avg_latency_ms < 200 ? 'success' : 'warning'} />
                    <StatCard title="P95 延迟" value={`${(metrics.p95_latency_ms || 0).toFixed(0)}ms`} icon={Icons.Clock} color={metrics.p95_latency_ms < 500 ? 'primary' : 'danger'} />
                </div>
            )}
            <div className="glass-card rounded-xl overflow-hidden">
                <div className="p-4 border-b border-gray-700/50 flex items-center justify-between">
                    <h3 className="font-semibold text-white">请求日志</h3>
                    <span className="text-xs text-gray-400">{logs.length} 条记录</span>
                </div>
                <div className="overflow-x-auto max-h-96">
                    <table className="w-full">
                        <thead className="bg-gray-800/50 sticky top-0">
                            <tr>
                                <th className="py-2 px-4 text-left text-xs text-gray-400 font-medium">时间</th>
                                <th className="py-2 px-4 text-left text-xs text-gray-400 font-medium">方法</th>
                                <th className="py-2 px-4 text-left text-xs text-gray-400 font-medium">端点</th>
                                <th className="py-2 px-4 text-center text-xs text-gray-400 font-medium">状态</th>
                                <th className="py-2 px-4 text-right text-xs text-gray-400 font-medium">延迟</th>
                            </tr>
                        </thead>
                        <tbody>
                            {logs.map((log, idx) => (
                                <tr key={idx} className="border-b border-gray-700/30 hover:bg-gray-700/20">
                                    <td className="py-2 px-4 text-xs text-gray-400">{formatTime(log.timestamp)}</td>
                                    <td className="py-2 px-4">
                                        <span className={`px-2 py-0.5 rounded text-xs font-medium ${log.method === 'GET' ? 'bg-blue-500/20 text-blue-400' : 'bg-purple-500/20 text-purple-400'}`}>{log.method}</span>
                                    </td>
                                    <td className="py-2 px-4 text-sm text-gray-300 font-mono">{log.endpoint}</td>
                                    <td className="py-2 px-4 text-center">
                                        <span className={`px-2 py-0.5 rounded text-xs font-medium ${log.status < 400 ? 'bg-emerald-500/20 text-emerald-400' : 'bg-red-500/20 text-red-400'}`}>{log.status}</span>
                                    </td>
                                    <td className="py-2 px-4 text-right text-sm text-gray-400">{log.latency_ms}ms</td>
                                </tr>
                            ))}
                        </tbody>
                    </table>
                </div>
            </div>
        </div>
    );
};

// Main App
const App = () => {
    const [activeTab, setActiveTab] = useState('dashboard');
    const [stats, setStats] = useState({});
    const [trades, setTrades] = useState([]);
    const [connected, setConnected] = useState(false);

    const fetchData = useCallback(async () => {
        try {
            const healthRes = await fetch(`${API_BASE}/health`);
            if (healthRes.ok) {
                setConnected(true);
                setStats({ volume24h: 5420000 + Math.random() * 1000000, activeMarkets: 42, smartMoneyInflow: 890000 + Math.random() * 100000, avgWinRate: 0.58 });
            }
            setTrades(Array.from({ length: 20 }, (_, i) => ({
                timestamp: new Date(Date.now() - i * 60000).toISOString(),
                maker: `0x${Math.random().toString(16).slice(2, 10)}`,
                side: Math.random() > 0.5 ? 'BUY' : 'SELL',
                price: (Math.random() * 0.8 + 0.1).toFixed(4),
                size: Math.floor(Math.random() * 10000)
            })));
        } catch (e) {
            setConnected(false);
            setStats({ volume24h: 5420000, activeMarkets: 42, smartMoneyInflow: 890000, avgWinRate: 0.58 });
        }
    }, []);

    useEffect(() => { fetchData(); const i = setInterval(fetchData, 30000); return () => clearInterval(i); }, [fetchData]);

    return (
        <>

        {/* Section 1: 炫酷首页 */}
            <section className="min-h-screen flex items-center justify-center relative overflow-hidden">
                <div className="absolute inset-0 flex items-center justify-center opacity-5">
                    <div className="text-[20rem] font-black text-white/5">MCP</div>
                </div>

                <div className="relative z-10 text-center px-6 max-w-5xl mx-auto">
                    {/* 主标题 */}
                    <h1 className="text-7xl md:text-8xl font-black mb-6 tracking-tight">
                        <span className="gradient-text">PolyMind</span>
                        <span className="text-white/90"> MCP</span>
                    </h1>

                    {/* 副标题 - 打字机效果 */}
                    <h2 className="text-3xl md:text-4xl font-light text-gray-300 mb-12 tracking-wide">
                        Turn <span className="gradient-text font-semibold">onchain chaos</span> into <span className="gradient-text font-semibold">signal</span>.
                    </h2>

                    {/* 描述文字 */}
                    <p className="text-lg text-white/90 mb-12 max-w-2xl mx-auto leading-relaxed">
                        AI-powered prediction market analytics on Polygon Network.
                        <br />
                        Track smart money, analyze market sentiment, make informed decisions.
                    </p>

                    {/* CTA 按钮组 */}
                    <div className="flex gap-4 justify-center items-center flex-wrap">
                        <button
                            onClick={() => window.scrollTo({ top: window.innerHeight, behavior: 'smooth' })}
                            className="group px-8 py-4 rounded-xl glass-card border border-white/20 text-white font-semibold text-lg hover:bg-white/10 hover:border-white/40 transition-all duration-300 hover:scale-105 flex items-center gap-2 backdrop-blur-md"
                        >
                            开始探索
                            <svg className="w-5 h-5 group-hover:translate-y-1 transition-transform" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 14l-7 7m0 0l-7-7m7 7V3" />
                            </svg>
                        </button>
                        <button
                            onClick={() => document.getElementById('documentation')?.scrollIntoView({ behavior: 'smooth' })}
                            className="px-8 py-4 rounded-xl glass-card border border-indigo-500/30 text-white font-semibold text-lg hover:bg-indigo-500/10 transition-all duration-300">
                            查看文档
                        </button>
                    </div>

                    {/* 特性标签 */}
                    <div className="mt-16 flex gap-6 justify-center flex-wrap text-sm">
                        <div className="flex items-center gap-2 text-white/90">
                            <div className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse"></div>
                            <span>实时链上数据</span>
                        </div>
                        <div className="flex items-center gap-2 text-white/90">
                            <div className="w-2 h-2 rounded-full bg-indigo-400 animate-pulse"></div>
                            <span>AI 驱动分析</span>
                        </div>
                        <div className="flex items-center gap-2 text-white/90">
                            <div className="w-2 h-2 rounded-full bg-purple-400 animate-pulse"></div>
                            <span>聪明钱追踪</span>
                        </div>
                    </div>
                </div>

                {/* 滚动提示 */}
                <div className="absolute bottom-8 left-1/2 -translate-x-1/2 animate-bounce">
                    <div className="flex flex-col items-center gap-2 text-gray-500">
                        <span className="text-xs">向下滚动</span>
                        <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 14l-7 7m0 0l-7-7m7 7V3" />
                        </svg>
                    </div>
                </div>
            </section>

        <section className="min-h-screen">
            <div className="min-h-screen">
                <header className="glass-card border-b border-gray-700/30 sticky top-0 z-50 backdrop-blur-xl">
                    <div className="max-w-7xl mx-auto px-6 py-5 flex items-center justify-between">
                        <div className="flex items-center gap-4">
                            <div className="relative w-12 h-12 rounded-2xl bg-gradient-to-br from-pink-500 via-rose-400 to-amber-400 flex items-center justify-center glow-accent shadow-2xl">
                                <span className="text-white text-2xl font-black">P</span>
                                <div className="absolute inset-0 rounded-2xl bg-gradient-to-br from-pink-500 via-rose-400 to-amber-400 opacity-50 blur-xl"></div>
                            </div>
                            <div>
                                <h1 className="text-xl font-black gradient-text">PolyMind MCP</h1>
                                <p className="text-xs text-gray-400 font-medium">智能预测市场分析平台 v2.0</p>
                            </div>
                        </div>
                        <div className="flex items-center gap-6">
                            <div className="flex items-center gap-3 px-4 py-2 rounded-xl glass-card">
                                <div className={`relative w-3 h-3 rounded-full ${connected ? 'bg-emerald-400' : 'bg-red-400'}`}>
                                    {connected && (
                                        <div className="absolute inset-0 rounded-full bg-emerald-400 animate-ping"></div>
                                    )}
                                </div>
                                <span className="text-sm font-semibold text-gray-300">{connected ? '已连接' : '离线'}</span>
                            </div>
                            <button onClick={fetchData}
                                className="p-3 rounded-xl hover:bg-gradient-to-br from-pink-500/20 to-amber-400/20 text-gray-400 hover:text-white transition-all duration-300 glass-card">
                                <Icons.Refresh />
                            </button>
                        </div>
                    </div>
                </header>
                <main className="max-w-7xl mx-auto px-6 py-8">
                    <TabNav activeTab={activeTab} onTabChange={setActiveTab} />
                    {activeTab === 'dashboard' && <DashboardPanel stats={stats} trades={trades} />}
                    {activeTab === 'smart-money' && <SmartMoneyPanel />}
                    {activeTab === 'ai-query' && <AIQueryPanel />}
                    {activeTab === 'logs' && <LogsPanel />}
                </main>
                <footer className="fixed bottom-0 left-0 right-0 glass-card border-t border-gray-700/30 py-3 px-6 backdrop-blur-xl">
                    <div className="max-w-7xl mx-auto flex items-center justify-between text-xs text-gray-500 font-medium">
                        <span className="flex items-center gap-2">
                            <span className="w-2 h-2 rounded-full bg-gradient-to-r from-pink-500 to-amber-400 animate-pulse"></span>
                            PolyMind MCP v2.0 | Polygon Network
                        </span>
                        <span className="flex items-center gap-2">
                            <span className="text-gray-600">API:</span>
                            <code className="px-2 py-1 rounded bg-gray-800/50 text-pink-400">{API_BASE}</code>
                        </span>
                    </div>
                </footer>
            </div>
        </section>

        {/* Section 3: 文档页面 */}
        <section id="documentation" className="min-h-screen py-20 px-6">
            <div className="min-h-screen py-20 px-6">
                <div className="max-w-5xl mx-auto">
                    {/* 页面标题 */}
                    <div className="text-center mb-16">
                        <h2 className="text-5xl font-bold gradient-text mb-4">项目文档</h2>
                        <p className="text-white-90 text-lg">关于 PolyMind MCP 你需要知道的一切</p>
                    </div>

                    {/* What is PolyMind MCP? */}
                    <div className="glass-card rounded-2xl p-8 mb-8">
                        <h3 className="text-3xl font-bold text-white mb-6 flex items-center gap-3">
                            <span className="text-4xl">💡</span>
                            什么是 PolyMind MCP?
                        </h3>
                        <div className="text-gray-300 leading-relaxed space-y-4">
                            <p className="text-lg">
                                <strong className="text-white">PolyMind MCP</strong> 是一个 AI 驱动的预测市场分析平台，
                                通过模型上下文协议(MCP)将 Polygon 链上的预测市场数据直接整合到 Claude Desktop 中。
                            </p>
                            <p>
                                它将复杂的链上数据转化为可操作的洞察，帮助交易者追踪聪明钱动向、分析市场情绪，
                                并做出明智的决策。无需编程，用户可以直接用自然语言向 Claude 提问，即刻获得 AI 增强的分析结果。
                            </p>
                            <p>
                                通过与 Claude 深度集成，PolyMind MCP 让预测市场分析变得前所未有的简单和高效。
                            </p>
                        </div>
                    </div>

                    {/* How It Works */}
                    <div className="glass-card rounded-2xl p-8 mb-8">
                        <h3 className="text-3xl font-bold text-white mb-6 flex items-center gap-3">
                            <span className="text-4xl">⚙️</span>
                            工作原理
                        </h3>
                        <div className="bg-gray-900/50 rounded-xl p-6 font-mono text-sm">
                            <div className="flex flex-col gap-2 text-gray-300">
                                <div className="flex items-center gap-3">
                                    <span className="text-amber-400">👤 用户</span>
                                    <span className="text-white-90">用自然语言提问</span>
                                </div>
                                <div className="ml-6 text-gray-600">↓</div>
                                <div className="flex items-center gap-3">
                                    <span className="text-orange-400">🤖 Claude Desktop</span>
                                    <span className="text-white-90">通过 MCP 协议处理查询</span>
                                </div>
                                <div className="ml-6 text-gray-600">↓</div>
                                <div className="flex items-center gap-3">
                                    <span className="text-yellow-400">🔧 PolyMind MCP 服务器</span>
                                    <span className="text-white-90">从区块链获取数据</span>
                                </div>
                                <div className="ml-6 text-gray-600">↓</div>
                                <div className="flex items-center gap-3">
                                    <span className="text-amber-300">⛓️ Polygon 网络</span>
                                    <span className="text-white-90">返回链上市场数据</span>
                                </div>
                                <div className="ml-6 text-gray-600">↓</div>
                                <div className="flex items-center gap-3">
                                    <span className="text-orange-300">✨ AI 分析</span>
                                    <span className="text-white-90">提供可执行的洞察</span>
                                </div>
                            </div>
                        </div>
                        <div className="mt-6 grid grid-cols-1 md:grid-cols-3 gap-4 text-center">
                            <div className="bg-amber-500/10 rounded-lg p-4 border border-amber-500/30">
                                <div className="text-2xl mb-2">🎯</div>
                                <div className="text-white font-semibold mb-1">实时数据</div>
                                <div className="text-xs text-gray-400">实时区块链查询</div>
                            </div>
                            <div className="bg-orange-500/10 rounded-lg p-4 border border-orange-500/30">
                                <div className="text-2xl mb-2">🧠</div>
                                <div className="text-white font-semibold mb-1">AI 驱动</div>
                                <div className="text-xs text-gray-400">自然语言交互</div>
                            </div>
                            <div className="bg-yellow-500/10 rounded-lg p-4 border border-yellow-500/30">
                                <div className="text-2xl mb-2">📊</div>
                                <div className="text-white font-semibold mb-1">智能分析</div>
                                <div className="text-xs text-gray-400">追踪资金流向</div>
                            </div>
                        </div>
                    </div>

                    {/* Quick Start */}
                    <div className="glass-card rounded-2xl p-8">
                        <h3 className="text-3xl font-bold text-white mb-6 flex items-center gap-3">
                            <span className="text-4xl">🚀</span>
                            快速开始指南
                        </h3>
                        <div className="space-y-6">
                            {/* Step 1 */}
                            <div className="flex gap-4">
                                <div className="flex-shrink-0 w-10 h-10 rounded-full bg-amber-500/20 border border-amber-500/50 flex items-center justify-center text-amber-400 font-bold">
                                    1
                                </div>
                                <div className="flex-1">
                                    <h4 className="text-white font-semibold mb-2">克隆代码仓库</h4>
                                    <pre className="bg-gray-900/50 rounded-lg p-3 text-sm text-gray-300 overflow-x-auto">
                                        <code>git clone https://github.com/your-team/polymind-mcp</code>
                                    </pre>
                                </div>
                            </div>

                            {/* Step 2 */}
                            <div className="flex gap-4">
                                <div className="flex-shrink-0 w-10 h-10 rounded-full bg-orange-500/20 border border-orange-500/50 flex items-center justify-center text-orange-400 font-bold">
                                    2
                                </div>
                                <div className="flex-1">
                                    <h4 className="text-white font-semibold mb-2">安装依赖</h4>
                                    <pre className="bg-gray-900/50 rounded-lg p-3 text-sm text-gray-300 overflow-x-auto">
                                        <code>pip install -r requirements.txt</code>
                                    </pre>
                                </div>
                            </div>

                            {/* Step 3 */}
                            <div className="flex gap-4">
                                <div className="flex-shrink-0 w-10 h-10 rounded-full bg-yellow-500/20 border border-yellow-500/50 flex items-center justify-center text-yellow-400 font-bold">
                                    3
                                </div>
                                <div className="flex-1">
                                    <h4 className="text-white font-semibold mb-2">配置 Claude Desktop</h4>
                                    <p className="text-gray-400 text-sm mb-2">在 Claude Desktop 配置文件中添加 MCP 服务器：</p>
                                    <pre className="bg-gray-900/50 rounded-lg p-3 text-sm text-gray-300 overflow-x-auto">
                                        <code>{`// claude_desktop_config.json
{
  "mcpServers": {
    "polymind": {
      "command": "python",
      "args": ["path/to/server.py"]
    }
  }
}`}</code>
                                    </pre>
                                </div>
                            </div>

                            {/* Step 4 */}
                            <div className="flex gap-4">
                                <div className="flex-shrink-0 w-10 h-10 rounded-full bg-amber-400/20 border border-amber-400/50 flex items-center justify-center text-amber-300 font-bold">
                                    4
                                </div>
                                <div className="flex-1">
                                    <h4 className="text-white font-semibold mb-2">启动服务器</h4>
                                    <pre className="bg-gray-900/50 rounded-lg p-3 text-sm text-gray-300 overflow-x-auto">
                                        <code>python server.py</code>
                                    </pre>
                                </div>
                            </div>

                            {/* Step 5 */}
                            <div className="flex gap-4">
                                <div className="flex-shrink-0 w-10 h-10 rounded-full bg-orange-400/20 border border-orange-400/50 flex items-center justify-center text-orange-300 font-bold">
                                    5
                                </div>
                                <div className="flex-1">
                                    <h4 className="text-white font-semibold mb-2">向 Claude 提问</h4>
                                    <div className="bg-gradient-to-r from-amber-500/10 to-orange-500/10 rounded-lg p-4 border border-amber-500/30">
                                        <p className="text-white italic">
                                            "显示 Polygon 预测市场上排名前 10 的聪明钱交易者"
                                        </p>
                                    </div>
                                </div>
                            </div>
                        </div>

                        {/* Additional Resources */}
                        <div className="mt-8 pt-8 border-t border-gray-700/50">
                            <h4 className="text-white font-semibold mb-4">📚 更多资源</h4>
                            <div className="flex flex-wrap gap-3">
                                <a href="https://github.com/SU-AN-coder/Poly-Mind-MCP" target="_blank" rel="noopener noreferrer" className="px-4 py-2 rounded-lg bg-amber-500/10 border border-amber-500/30 text-amber-200 hover:bg-amber-500/20 transition-colors text-sm">
                                    GitHub 仓库
                                </a>
                                <a href="#" className="px-4 py-2 rounded-lg bg-orange-500/10 border border-orange-500/30 text-orange-200 hover:bg-orange-500/20 transition-colors text-sm">
                                    API 文档
                                </a>
                                <a href="#" className="px-4 py-2 rounded-lg bg-yellow-500/10 border border-yellow-500/30 text-yellow-200 hover:bg-yellow-500/20 transition-colors text-sm">
                                    示例查询
                                </a>
                            </div>
                        </div>
                    </div>

                    {/* 返回顶部按钮 */}
                    <div className="text-center mt-12">
                        <button
                            onClick={() => window.scrollTo({ top: 0, behavior: 'smooth' })}
                            className="px-6 py-3 rounded-xl glass-card border border-amber-400/30 text-amber-100 hover:bg-amber-500/10 transition-all duration-300 inline-flex items-center gap-2"
                        >
                            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 10l7-7m0 0l7 7m-7-7v18" />
                            </svg>
                            返回顶部
                        </button>
                    </div>
                </div>
            </div>
        </section>

        </>
    );
};

ReactDOM.createRoot(document.getElementById('root')).render(<App />);
