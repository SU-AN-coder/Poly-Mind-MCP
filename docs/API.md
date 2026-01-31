# PolyMind MCP API 文档

## 基础信息

- **Base URL**: `http://localhost:8888`
- **协议**: HTTP/HTTPS
- **数据格式**: JSON

## 端点列表

### 系统

| 方法 | 端点 | 说明 |
|------|------|------|
| GET | `/health` | 健康检查 |
| GET | `/stats` | 获取统计数据 |
| GET | `/api-docs` | 获取 OpenAPI 文档 |

### 交易

| 方法 | 端点 | 说明 |
|------|------|------|
| GET | `/trades/recent` | 获取最近交易 |
| GET | `/trades/large` | 获取大单交易 |

### 市场

| 方法 | 端点 | 说明 |
|------|------|------|
| GET | `/hot` | 获取热门市场 |
| GET | `/markets/search` | 搜索市场 |
| GET | `/market/{slug}` | 获取市场详情 |
| GET | `/market/{slug}/price-history` | 获取价格历史 |

### 分析

| 方法 | 端点 | 说明 |
|------|------|------|
| GET | `/sentiment` | 获取市场情绪 |
| GET | `/smart-money` | 获取聪明钱活动 |
| GET | `/trader/{address}` | 获取交易者详情 |
| GET | `/arbitrage` | 获取套利机会 |
| GET | `/relationship` | 分析市场关系 |

### AI

| 方法 | 端点 | 说明 |
|------|------|------|
| POST | `/nl-query` | 自然语言查询 |
| GET | `/advice/{slug}` | 获取交易建议 |
| GET | `/alerts/{slug}` | 获取智能提醒 |

### WebSocket

| 方法 | 端点 | 说明 |
|------|------|------|
| GET | `/ws/stats` | WebSocket 连接统计 |
| POST | `/ws/subscribe` | 模拟订阅（测试用）|

## 详细说明

### GET /stats

获取整体统计数据。

**响应示例:**
```json
{
  "total_trades": 1234,
  "unique_traders": 567,
  "total_volume": 123456.78,
  "total_markets": 89,
  "large_trades_count": 45,
  "timestamp": "2024-01-29T12:00:00Z"
}
```

### GET /trades/large

获取大单交易列表。

**查询参数:**
- `limit` (int, 默认 50): 返回数量
- `min_size` (float, 默认 1000): 最小交易金额

**响应示例:**
```json
{
  "trades": [...],
  "count": 45,
  "min_size": 1000,
  "summary": {
    "total_volume": 50000.00,
    "buy_volume": 30000.00,
    "sell_volume": 20000.00,
    "buy_ratio": 60.0
  }
}
```

### GET /sentiment

获取市场情绪指数。

**查询参数:**
- `hours` (int, 默认 24): 时间范围
- `market` (string, 可选): 限定特定市场

**响应示例:**
```json
{
  "market": "全市场",
  "sentiment_index": 65.5,
  "sentiment_label": "乐观",
  "buy_count": 1000,
  "sell_count": 500,
  "buy_volume": 100000.00,
  "sell_volume": 50000.00
}
```

### POST /nl-query

自然语言查询。

**请求体:**
```json
{
  "query": "搜索关于 Trump 的市场"
}
```

**响应示例:**
```json
{
  "type": "search",
  "results": [...],
  "count": 10
}
```

## 错误处理

所有端点在出错时返回以下格式：

```json
{
  "error": "错误描述"
}
```

HTTP 状态码：
- `200`: 成功
- `400`: 请求参数错误
- `500`: 服务器内部错误

## WebSocket 频道

支持的订阅频道：
- `trades`: 所有交易
- `large_trades`: 大单交易
- `smart_money`: 聪明钱活动
- `arbitrage`: 套利机会
- `markets`: 市场更新
- `alerts`: 系统提醒
