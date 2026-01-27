# PolyMind MCP

> 🧠 基于 MCP 协议的 AI 预测市场分析平台

![Python](https://img.shields.io/badge/Python-3.10+-blue)
![MCP](https://img.shields.io/badge/MCP-Enabled-purple)
![License](https://img.shields.io/badge/License-MIT-green)

## 功能特性

- 🔗 **链上数据解码** - 解析 Polymarket CTF Exchange 交易
- 🧠 **聪明钱分析** - 追踪高胜率交易者动向
- 💡 **AI 交易建议** - 基于 LLM 的智能分析
- 📊 **实时看板** - 可视化监控面板

## 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 配置环境变量

```bash
cp .env.example .env
# 编辑 .env，填入 RPC_URL 和 OPENAI_API_KEY（可选）
```

### 3. 启动服务

```bash
python start.py
```

访问:
- 前端看板: http://localhost:3000
- MCP API: http://localhost:8888

## API 端点

| 端点 | 说明 |
|------|------|
| `GET /tools` | MCP 工具列表 |
| `GET /markets/search?q=` | 搜索市场 |
| `GET /smart-money` | 聪明钱活动 |
| `GET /hot` | 热门市场 |
| `GET /arbitrage` | 套利机会 |
| `GET /trader/<address>` | 交易者分析 |
| `POST /nl-query` | 自然语言查询 |

## MCP 工具

```python
tools = [
    "search_markets",           # 搜索市场
    "get_market_info",          # 市场详情
    "analyze_trader",           # 交易者画像
    "get_smart_money_activity", # 聪明钱
    "get_hot_markets",          # 热门市场
    "find_arbitrage",           # 套利扫描
    "get_trading_advice",       # 交易建议
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
      "cwd": "/path/to/PolyMind-MCP"
    }
  }
}
```

## 项目结构

```
PolyMind-MCP/
├── src/
│   ├── mcp/           # MCP 服务 (server.py, tools.py, profiler.py)
│   ├── api/           # REST API
│   ├── ctf/           # Token 计算
│   ├── db/            # 数据库
│   ├── indexer/       # 区块索引
│   ├── trade_decoder.py
│   └── market_decoder.py
├── frontend/          # 数据看板
├── tests/             # 测试
├── start.py           # 启动脚本
├── requirements.txt
└── .env.example
```

## 环境变量

| 变量 | 必需 | 说明 |
|------|------|------|
| `RPC_URL` | ✅ | Polygon RPC 地址 |
| `OPENAI_API_KEY` | ❌ | OpenAI API（启用 AI 分析）|
| `DB_PATH` | ❌ | 数据库路径 |

## 开发

```bash
# 运行测试
pytest tests/

# 仅启动 MCP 服务器
python start.py --mcp-only

# 自定义端口
python start.py --mcp-port 9000 --frontend-port 3001
```

## License

MIT
