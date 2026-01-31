# PolyMind MCP

> AI 驱动的 Polymarket 预测市场分析平台，基于 MCP (Model Context Protocol) 构建

[![Python](https://img.shields.io/badge/Python-3.9+-blue.svg)](https://python.org)
[![MCP](https://img.shields.io/badge/MCP-Compatible-green.svg)](https://modelcontextprotocol.io)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

## 🌟 亮点功能

- 🔍 **市场搜索**: 自然语言搜索 Polymarket 预测市场
- 👤 **交易者画像**: 分析地址行为，生成智能标签（聪明钱、巨鲸、套利者）
- 💡 **交易建议**: 基于多因素分析生成买卖建议
- 🔄 **套利扫描**: 实时发现 YES+NO 定价偏差套利机会
- 📊 **聪明钱追踪**: 识别高胜率地址并追踪其动态
- 📈 **链上索引**: 实时索引 Polygon 链上交易数据

---

## 🚀 快速开始（30秒体验）

### 方式一：一键演示模式（推荐）

```bash
# 1. 克隆项目
git clone https://github.com/yourusername/polymind-mcp.git
cd polymind-mcp

# 2. 安装依赖
pip install -r requirements.txt

# 3. 一键启动（自动导入演示数据 + 启动服务）
python start.py demo
```

### 方式二：本地环境搭建

```bash
# 1. 安装 Python 3.9+
# 2. 克隆项目
# 3. 安装依赖
# 4. 配置环境变量
# 5. 启动服务
```

## 功能特性

- 🔗 **链上数据解码** - 解析 Polymarket CTF Exchange OrderFilled 事件
- 🧠 **聪明钱分析** - 追踪高胜率交易者动向
- 💡 **AI 交易建议** - 基于 LLM 的智能分析
- 📊 **实时看板** - 可视化监控面板
- 🤖 **MCP 协议** - 支持 Claude Desktop / Cursor 集成

## 快速开始

### 1. 安装依赖

```bash
python -m venv venv
.\venv\Scripts\activate  # Windows
# source venv/bin/activate  # macOS/Linux

pip install -r requirements.txt
```

### 2. 配置环境变量

```bash
cp .env.example .env
# 编辑 .env，填入配置
```

需要的环境变量：
- `POLYGON_RPC_URL` - Polygon 主网 RPC URL（必需）
- `OPENAI_API_KEY` - OpenAI API Key（可选，用于高级分析）
- `DB_PATH` - 数据库路径（默认 `data/polymarket.db`）

### 3. 启动服务

```bash
# 模式一：索引链上交易数据
python start.py index --from-block 50000000

# 模式二：同步 Gamma API 市场数据
python start.py sync-markets

# 模式三：启动 HTTP API 服务
python start.py api

# 模式四：MCP stdio 服务（用于 Claude Desktop）
python -m src.mcp.mcp_server

# 一键启动所有服务（索引 + 同步 + API）
python start.py all
```

访问:
- 前端看板: http://localhost:3000
- MCP HTTP API: http://localhost:8888
- WebSocket Demo: http://localhost:3000/websocket_demo.html

## HTTP API 端点

| 端点 | 说明 |
|------|------|
| `GET /tools` | MCP 工具列表 |
| `GET /markets/search?q=` | 搜索市场 |
| `GET /smart-money` | 聪明钱活动 |
| `GET /hot` | 热门市场 |
| `GET /arbitrage` | 套利机会 |
| `GET /trader/<address>` | 交易者分析 |
| `GET /trader/<address>/pnl` | 🆕 交易者持仓盈亏 |
| `GET /trader/<address>/positions` | 🆕 交易者持仓列表 |
| `GET /leaderboard/pnl` | 🆕 盈亏排行榜 |
| `GET /stats` | 仪表盘统计（真实数据）|
| `GET /trades/recent` | 最近交易（真实数据）|
| `GET /cache/stats` | 🆕 缓存统计 |
| `POST /cache/flush` | 🆕 清空缓存 |
| `GET /ws/stats` | 🆕 WebSocket 连接统计 |
| `POST /nl-query` | 自然语言查询 |

## WebSocket 实时推送

支持频道订阅：
- `trades` - 所有交易实时流
- `markets` - 市场更新
- `smart_money` - 聪明钱动态
- `market` + target - 特定市场交易
- `trader` + target - 特定交易者活动

```javascript
// 客户端示例
const socket = io('http://localhost:8888');
socket.on('connect', () => console.log('Connected'));
socket.emit('subscribe', { channel: 'trades' });
socket.on('new_trade', (data) => console.log('New trade:', data));
```

## MCP 工具

```python
tools = [
    "get_market_info",          # 市场详情
    "search_markets",           # 搜索市场
    "analyze_trader",           # 交易者画像
    "get_trading_advice",       # 交易建议
    "find_arbitrage",           # 套利扫描
    "get_smart_money_activity", # 聪明钱
    "get_hot_markets",          # 热门市场
    "analyze_market_relationship", # 市场关系分析
    "natural_language_query",   # 自然语言查询
]
```

## Claude Desktop 配置

添加到 `%APPDATA%\Claude\claude_desktop_config.json` (Windows) 或 `~/Library/Application Support/Claude/claude_desktop_config.json` (macOS):

```json
{
  "mcpServers": {
    "polymind": {
      "command": "python",
      "args": ["-m", "src.mcp.mcp_server"],
      "cwd": "C:\\Users\\你的用户名\\Desktop\\Poly Mind MCP",
      "env": {
        "PYTHONPATH": "C:\\Users\\你的用户名\\Desktop\\Poly Mind MCP"
      }
    }
  }
}
```

## 项目结构

```
PolyMind-MCP/
├── src/
│   ├── mcp/               # MCP 服务
│   │   ├── mcp_server.py  # stdio JSON-RPC 服务
│   │   ├── server.py      # HTTP API 服务
│   │   ├── tools.py       # MCP 工具实现
│   │   ├── profiler.py    # 交易者画像分析
│   │   └── advisor.py     # 交易建议引擎
│   ├── api/               # REST API
│   ├── ctf/               # Token ID 计算
│   ├── db/                # 数据库 schema
│   ├── indexer/           # 区块链索引器
│   │   ├── run.py         # 索引器主逻辑
│   │   ├── store.py       # 数据存储
│   │   └── gamma.py       # Gamma API 客户端
│   ├── trade_decoder.py   # 交易解码器
│   └── market_decoder.py  # 市场解码器
├── data/                  # 数据目录
│   └── polymarket.db      # SQLite 数据库
├── frontend/              # Web 看板
├── tests/                 # 测试
├── start.py               # 统一启动脚本
├── run_mcp_server.py      # HTTP API 启动脚本
├── test_mcp.py            # MCP 工具测试
├── test_mcp_stdio.py      # MCP stdio 服务器测试
├── mcp_config.json        # Claude Desktop 配置示例
├── requirements.txt
└── .env.example
```

## 环境变量

| 变量 | 必需 | 说明 |
|------|------|------|
| `RPC_URL` | ✅ | Polygon RPC 地址 |
| `OPENAI_API_KEY` | ❌ | OpenAI API（启用 AI 分析）|
| `DB_PATH` | ❌ | 数据库路径 |

## 数据来源

本项目使用以下数据源：

| 数据类型 | 来源 | 说明 |
|---------|------|------|
| **交易数据** | Polygon 链上 | 通过 RPC 获取 CTF Exchange 的 OrderFilled 事件 |
| **市场元数据** | Gamma API | 获取市场 slug、描述、Token ID 映射 |
| **价格数据** | 链上计算 | 基于交易事件计算 YES/NO 价格 |

### 合约地址

- **CTF Exchange**: `0x4bFb41d5B3570DeFd03C39a9A4D8dE6Bd8B8982E`
- **Neg Risk CTF Exchange**: `0xC5d563A36AE78145C45a50134d48A1215220f80a`
- **OrderFilled Event**: `0xd0a08e8c493f9c94f29311604c9de1b4e8c8d4c06bd0c789af57f2d65bfec0f6`

### 示例数据

- 示例交易哈希: `0x916cad96dd5c219997638133512fd17fe7c1ce72b830157e4fd5323cf4f19946`
- 示例市场: `will-there-be-another-us-government-shutdown-by-january-31`

## 功能说明

### 核心功能

1. **链上数据索引** - 解析 Polymarket CTF Exchange 交易事件
2. **市场数据同步** - 从 Gamma API 获取市场元数据
3. **交易者画像** - 基于 LLM 的语义化标签生成
4. **聪明钱分析** - 追踪高胜率交易者动向
5. **套利检测** - YES+NO 套利和跨市场价差分析
6. **MCP 协议支持** - Claude Desktop / Cursor 集成

### MCP 工具列表

| 工具名称 | 功能描述 |
|---------|---------|
| `get_market_info` | 获取市场详情 |
| `search_markets` | 搜索 Polymarket 市场 |
| `analyze_trader` | 分析交易者行为模式 |
| `get_trading_advice` | 获取交易建议 |
| `find_arbitrage` | 扫描套利机会 |
| `get_smart_money_activity` | 获取聪明钱活动 |
| `get_hot_markets` | 获取热门市场 |
| `analyze_market_relationship` | 分析市场关系 |
| `natural_language_query` | 自然语言查询 |

## 开发

```bash
# 运行测试
pytest tests/

# 验证数据
python verify_data.py

# 运行 MCP stdio 测试
python test_mcp_stdio.py

# 运行 MCP 工具测试
python test_mcp.py
```

## 团队成员

（请在此处填写团队成员信息）

## License

MIT