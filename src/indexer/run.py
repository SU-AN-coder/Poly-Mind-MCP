"""
阶段二：区块链索引器（Indexer）
持续扫描Polymarket交易事件并存储到数据库
"""
import logging
import sys
import json
from typing import List, Dict, Optional, Tuple, Any
from datetime import datetime
import argparse
from dotenv import load_dotenv
import os
from web3 import Web3
from decimal import Decimal
import sqlite3

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from trade_decoder import TradeDecoder, Trade
from market_decoder import MarketDecoder
from db.schema import init_db, get_connection

load_dotenv()
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class PolymarketIndexer:
    """Polymarket交易索引器"""
    
    # 交易所地址
    CTF_EXCHANGE = "0x4bFb41d5B3570DeFd03C39a9A4D8dE6Bd8B8982E"
    NEG_RISK_EXCHANGE = "0xC5d563A36AE78145C45a50134d48A1215220f80a"
    
    # 批处理大小
    BATCH_SIZE = 1000
    
    def __init__(self, rpc_url: str, db_path: str = "data/polymarket.db"):
        """初始化索引器"""
        logger.info("初始化索引器...")
        
        self.rpc_url = rpc_url
        self.db_path = db_path
        self.web3 = Web3(Web3.HTTPProvider(rpc_url))
        
        # 验证RPC连接
        if not self.web3.is_connected():
            raise ConnectionError("无法连接到Polygon RPC")
        
        logger.info(f"✓ RPC连接成功: 链ID {self.web3.eth.chain_id}")
        
        # 初始化数据库
        init_db(db_path)
        logger.info(f"✓ 数据库初始化完成")
        
        # 初始化解码器
        self.trade_decoder = TradeDecoder(rpc_url)
        self.market_decoder = MarketDecoder()
    
    def get_sync_state(self) -> Tuple[int, int]:
        """
        获取同步状态
        
        Returns:
            (最后处理区块, 总处理事件数)
        """
        try:
            conn = get_connection(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute("SELECT last_block, total_events FROM sync_state LIMIT 1")
            row = cursor.fetchone()
            conn.close()
            
            if row:
                return row[0], row[1]
            else:
                # 首次运行，从最近1000个区块开始
                current_block = self.web3.eth.block_number
                start_block = max(current_block - 1000, 0)
                return start_block, 0
        except Exception as e:
            logger.error(f"获取同步状态失败: {e}")
            return 0, 0
    
    def update_sync_state(self, block_num: int, event_count: int) -> None:
        """更新同步状态"""
        try:
            conn = get_connection(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute("""
                INSERT OR REPLACE INTO sync_state (id, last_block, total_events, last_updated)
                VALUES (1, ?, ?, ?)
            """, (block_num, event_count, datetime.now().isoformat()))
            
            conn.commit()
            conn.close()
        except Exception as e:
            logger.error(f"更新同步状态失败: {e}")
    
    def fetch_order_filled_logs(self, from_block: int, to_block: int) -> List[Dict]:
        """
        获取OrderFilled事件日志
        
        Args:
            from_block: 开始区块
            to_block: 结束区块
            
        Returns:
            日志列表
        """
        try:
            logger.info(f"获取区块 {from_block} - {to_block} 的事件...")
            
            # OrderFilled事件签名 (topic0)
            # event OrderFilled(bytes32 indexed conditionId, uint256 indexed tokenId, ...)
            event_topic = "0xb1c9d926dde9f4e10e6e183ccff5b35e41541a1e7b7ed7e7873e6e550fdb68a1"
            
            logs = self.web3.eth.get_logs({
                'fromBlock': from_block,
                'toBlock': to_block,
                'address': [
                    Web3.to_checksum_address(self.CTF_EXCHANGE),
                    Web3.to_checksum_address(self.NEG_RISK_EXCHANGE)
                ],
                'topics': [event_topic]
            })
            
            logger.info(f"✓ 获取到 {len(logs)} 个OrderFilled事件")
            return logs
        
        except Exception as e:
            logger.error(f"获取日志失败: {e}")
            return []
    
    def process_logs(self, logs: List[Dict]) -> List[Dict]:
        """
        处理原始日志
        
        Args:
            logs: 原始日志
            
        Returns:
            处理后的交易数据
        """
        trades = []
        
        for log in logs:
            try:
                # 使用TradeDecoder解码
                tx_hash = log.get('transactionHash')
                if tx_hash:
                    decoded_trades = self.trade_decoder.decode_tx_logs(
                        tx_hash.hex() if isinstance(tx_hash, bytes) else tx_hash
                    )
                    trades.extend([t for t in decoded_trades])
            
            except Exception as e:
                logger.warning(f"解码交易 {log.get('transactionHash')} 失败: {e}")
                continue
        
        return trades
    
    def enrich_with_market_info(self, trades: List[Dict]) -> List[Dict]:
        """
        使用市场信息丰富交易数据
        
        Args:
            trades: 交易列表
            
        Returns:
            丰富后的交易列表
        """
        try:
            conn = get_connection(self.db_path)
            cursor = conn.cursor()
            
            enriched_trades = []
            
            for trade in trades:
                try:
                    token_id = trade.get('tokenId')
                    
                    # 查询市场
                    cursor.execute("""
                        SELECT market_slug, condition_id, yes_token_id, no_token_id
                        FROM markets
                        WHERE yes_token_id = ? OR no_token_id = ?
                    """, (token_id, token_id))
                    
                    market_row = cursor.fetchone()
                    if market_row:
                        trade['market_slug'] = market_row[0]
                        trade['condition_id'] = market_row[1]
                        trade['outcome'] = 'YES' if token_id == market_row[2] else 'NO'
                    
                    enriched_trades.append(trade)
                
                except Exception as e:
                    logger.warning(f"丰富交易数据失败: {e}")
                    enriched_trades.append(trade)
            
            conn.close()
            return enriched_trades
        
        except Exception as e:
            logger.error(f"丰富交易数据失败: {e}")
            return trades
    
    def store_trades(self, trades: List[Dict]) -> int:
        """
        存储交易到数据库
        
        Args:
            trades: 交易列表
            
        Returns:
            成功存储的交易数
        """
        try:
            conn = get_connection(self.db_path)
            cursor = conn.cursor()
            
            stored_count = 0
            
            for trade in trades:
                try:
                    cursor.execute("""
                        INSERT OR IGNORE INTO events (
                            tx_hash, event_type, maker, taker, asset_yes, asset_no,
                            size, price, block_number, timestamp, raw_data
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        trade.get('txHash'),
                        'OrderFilled',
                        trade.get('maker'),
                        trade.get('taker'),
                        trade.get('assetYes'),
                        trade.get('assetNo'),
                        float(trade.get('size', 0)),
                        float(trade.get('price', 0)),
                        trade.get('blockNumber'),
                        datetime.now().isoformat(),
                        json.dumps(trade)
                    ))
                    
                    stored_count += 1
                
                except Exception as e:
                    logger.warning(f"存储交易失败: {e}")
                    continue
            
            conn.commit()
            conn.close()
            
            logger.info(f"✓ 成功存储 {stored_count}/{len(trades)} 个交易")
            return stored_count
        
        except Exception as e:
            logger.error(f"存储交易失败: {e}")
            return 0
    
    def run_indexer(self, from_block: Optional[int] = None, 
                   to_block: Optional[int] = None,
                   continuous: bool = False) -> Dict[str, Any]:
        """
        运行索引器
        
        Args:
            from_block: 起始区块（默认从同步状态读取）
            to_block: 结束区块（默认为最新区块）
            continuous: 是否持续运行
            
        Returns:
            运行结果统计
        """
        logger.info("启动索引器...")
        
        # 获取区块范围
        if from_block is None:
            from_block, _ = self.get_sync_state()
        
        current_block = self.web3.eth.block_number
        if to_block is None:
            to_block = current_block
        
        logger.info(f"处理区块范围: {from_block} - {to_block}")
        
        total_trades = 0
        total_events, _ = self.get_sync_state()
        
        # 分批处理
        batch_start = from_block
        
        while batch_start < to_block:
            batch_end = min(batch_start + self.BATCH_SIZE, to_block)
            
            try:
                logger.info(f"处理批次: {batch_start} - {batch_end}")
                
                # 获取日志
                logs = self.fetch_order_filled_logs(batch_start, batch_end)
                
                if logs:
                    # 处理日志
                    trades = self.process_logs(logs)
                    
                    # 丰富数据
                    trades = self.enrich_with_market_info(trades)
                    
                    # 存储
                    stored = self.store_trades(trades)
                    total_trades += stored
                
                # 更新同步状态
                self.update_sync_state(batch_end, total_events + total_trades)
                
                batch_start = batch_end + 1
                
                logger.info(f"✓ 批次完成，累计存储 {total_trades} 个交易")
            
            except Exception as e:
                logger.error(f"批次处理失败: {e}")
                if not continuous:
                    raise
                else:
                    batch_start = batch_end + 1
                    continue
        
        logger.info(f"✓ 索引完成！总计处理 {total_trades} 个交易")
        
        result = {
            "status": "success",
            "from_block": from_block,
            "to_block": to_block,
            "trades_inserted": total_trades
        }
        
        # 持续模式
        if continuous:
            logger.info("进入持续监听模式...")
            while True:
                try:
                    import time
                    time.sleep(12)  # Polygon出块间隔~12秒
                    
                    # 监听最新区块
                    latest_block = self.web3.eth.block_number
                    if latest_block > batch_end:
                        logger.info(f"发现新区块: {latest_block}")
                        new_result = self.run_indexer(
                            from_block=batch_end + 1,
                            to_block=latest_block,
                            continuous=False
                        )
                        batch_end = latest_block
                        result['trades_inserted'] += new_result['trades_inserted']
                
                except KeyboardInterrupt:
                    logger.info("用户中断索引器")
                    break
                except Exception as e:
                    logger.error(f"持续监听出错: {e}")
                    continue
        
        return result


def main():
    """命令行入口"""
    parser = argparse.ArgumentParser(description="Polymarket区块链索引器")
    parser.add_argument(
        "--rpc-url",
        type=str,
        default=os.getenv("RPC_URL"),
        help="Polygon RPC URL"
    )
    parser.add_argument(
        "--db",
        type=str,
        default="data/polymarket.db",
        help="SQLite数据库路径"
    )
    parser.add_argument(
        "--from-block",
        type=int,
        default=None,
        help="起始区块"
    )
    parser.add_argument(
        "--to-block",
        type=int,
        default=None,
        help="结束区块"
    )
    parser.add_argument(
        "--continuous",
        action="store_true",
        help="持续监听新区块"
    )
    
    args = parser.parse_args()
    
    # 验证RPC_URL
    if not args.rpc_url:
        logger.error("错误: RPC_URL未配置。请设置RPC_URL环境变量或使用 --rpc-url 参数")
        sys.exit(1)
    
    try:
        indexer = PolymarketIndexer(
            rpc_url=args.rpc_url,
            db_path=args.db
        )
        
        result = indexer.run_indexer(
            from_block=args.from_block,
            to_block=args.to_block,
            continuous=args.continuous
        )
        
        logger.info(f"最终结果: {result}")
    
    except Exception as e:
        logger.error(f"索引器运行失败: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
