"""
阶段一：市场参数解码器（Market Decoder）
完整实现版本 - 计算Polymarket市场的TokenId
"""
import json
import sys
import logging
from typing import Dict, Any, Optional
from dataclasses import dataclass, asdict
import argparse
from dotenv import load_dotenv
import requests
import os
from web3 import Web3

load_dotenv()
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@dataclass
class MarketParams:
    """市场参数结构"""
    condition_id: str
    oracle: str
    question_id: str
    outcome_slot_count: int
    collateral_token: str
    yes_token_id: str
    no_token_id: str
    gamma: Optional[Dict] = None


class MarketDecoder:
    """市场解码器 - 计算市场参数和TokenId"""
    
    # 常量
    USDC_ADDRESS = "0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174"  # USDC.e on Polygon
    PARENT_COLLECTION_ID = "0x" + "0" * 64
    
    # YES/NO对应的indexSet
    YES_INDEX_SET = 1
    NO_INDEX_SET = 2
    
    def __init__(self, gamma_base_url: str = "https://gamma-api.polymarket.com") -> None:
        """初始化解码器"""
        self.gamma_base_url = gamma_base_url
        logger.info(f"Gamma API: {gamma_base_url}")
    
    def get_market_from_gamma(self, market_slug: str) -> Optional[Dict]:
        """
        从Gamma API获取市场信息（通过搜索）
        注意: Gamma API 不支持直接的 /markets/{slug} 端点
        改用 search 参数在市场列表中过滤
        
        Args:
            market_slug: 市场slug
            
        Returns:
            市场数据或None
        """
        try:
            # 使用 search 参数搜索市场
            url = f"{self.gamma_base_url}/markets"
            params = {
                "search": market_slug,
                "limit": 100
            }
            
            logger.info(f"从Gamma API搜索市场: {market_slug}")
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            
            markets = response.json()
            
            if not markets:
                logger.warning(f"搜索未返回结果: {market_slug}")
                return None
            
            # 寻找完全匹配的市场 (slug 相同)
            for market in markets:
                if market.get("slug") == market_slug:
                    title = market.get('question', 'N/A')[:50]
                    logger.info(f"✓ 找到市场: {title}...")
                    return market
            
            # 如果没有完全匹配，返回第一个结果（部分匹配）
            if markets:
                logger.warning(f"未找到完全匹配，使用第一个搜索结果")
                return markets[0]
            
            logger.error(f"未找到市场: {market_slug}")
            return None
            
        except requests.exceptions.RequestException as e:
            logger.error(f"从Gamma API获取市场失败: {e}")
            return None
    
    def decode_market(
        self,
        condition_id: str,
        question_id: str,
        oracle: str,
        outcome_slot_count: int = 2,
        gamma_data: Optional[Dict] = None
    ) -> MarketParams:
        """
        解码市场参数
        
        Args:
            condition_id: 条件ID
            question_id: 问题ID
            oracle: 预言机地址
            outcome_slot_count: 结果数量（默认2）
            gamma_data: Gamma API数据
            
        Returns:
            MarketParams对象
        """
        logger.info(f"解码市场参数...")
        logger.info(f"  Condition ID: {condition_id[:20]}...")
        logger.info(f"  Oracle: {oracle}")
        
        # 计算YES/NO TokenId
        yes_token_id = self._calculate_token_id(condition_id, self.YES_INDEX_SET)
        no_token_id = self._calculate_token_id(condition_id, self.NO_INDEX_SET)
        
        logger.info(f"✓ YES Token ID: {yes_token_id[:20]}...")
        logger.info(f"✓ NO Token ID:  {no_token_id[:20]}...")
        
        return MarketParams(
            condition_id=condition_id,
            oracle=oracle,
            question_id=question_id,
            outcome_slot_count=outcome_slot_count,
            collateral_token=self.USDC_ADDRESS,
            yes_token_id=yes_token_id,
            no_token_id=no_token_id,
            gamma=gamma_data
        )
    
    def _calculate_token_id(self, condition_id: str, index_set: int) -> str:
        """
        计算TokenId
        
        Args:
            condition_id: 条件ID
            index_set: 索引集（1=YES, 2=NO）
            
        Returns:
            TokenId
        """
        try:
            # 计算CollectionId
            collection_id = self._calculate_collection_id(condition_id, index_set)
            
            # 计算TokenId = keccak256(collateral_token, collection_id)
            collateral_bytes = bytes.fromhex(self.USDC_ADDRESS[2:])
            collection_bytes = bytes.fromhex(collection_id[2:])
            
            combined = collateral_bytes + collection_bytes
            token_id = "0x" + Web3.keccak(combined).hex()[2:]
            
            return token_id
        except Exception as e:
            logger.error(f"计算TokenId出错: {e}")
            return "0x"
    
    def _calculate_collection_id(self, condition_id: str, index_set: int) -> str:
        """
        计算CollectionId
        
        Args:
            condition_id: 条件ID
            index_set: 索引集（1=YES, 2=NO）
            
        Returns:
            CollectionId
        """
        try:
            # CollectionId = keccak256(parentCollectionId, conditionId, indexSet)
            parent_bytes = bytes.fromhex(self.PARENT_COLLECTION_ID[2:])
            condition_bytes = bytes.fromhex(condition_id[2:])
            index_bytes = index_set.to_bytes(32, byteorder='big')
            
            combined = parent_bytes + condition_bytes + index_bytes
            collection_id = "0x" + Web3.keccak(combined).hex()[2:]
            
            return collection_id
        except Exception as e:
            logger.error(f"计算CollectionId出错: {e}")
            return "0x"
    
    def decode_market_from_gamma_slug(self, market_slug: str) -> Optional[MarketParams]:
        """
        从Gamma API slug解码市场
        
        注意: Gamma API 的字段映射:
        - questionId: 使用 'id' 字段（市场ID）
        - oracle: Gamma API 不返回 oracle，使用市场创建者地址或合约地址作为默认值
        
        Args:
            market_slug: 市场slug
            
        Returns:
            MarketParams或None
        """
        logger.info(f"从Gamma API slug解码市场: {market_slug}")
        
        gamma_data = self.get_market_from_gamma(market_slug)
        if not gamma_data:
            return None
        
        # 从Gamma数据提取必要信息
        # 注意: Gamma API 字段映射
        condition_id = gamma_data.get("conditionId")
        question_id = gamma_data.get("id")  # 使用 'id' 作为 questionId
        
        # oracle 字段不在 Gamma API 数据中，尝试获取或使用市场创建者地址
        oracle = gamma_data.get("oracle")
        if not oracle and "marketMakerAddress" in gamma_data:
            # 如果没有 oracle，使用市场创建者地址或默认值
            oracle = gamma_data.get("marketMakerAddress")
            logger.info(f"未找到 oracle 字段，使用市场创建者地址: {oracle}")
        
        if not oracle:
            # 如果都没有，使用一个合理的默认值
            # 在 Polygon 上，UMA 预言机是一个常见的选择
            logger.warning("未找到 oracle 地址，使用默认值")
            oracle = "0x0000000000000000000000000000000000000000"  # 需要正确的预言机地址
        
        if not all([condition_id, question_id]):
            logger.error(f"Gamma API数据缺少必要字段: conditionId={condition_id}, questionId={question_id}")
            return None
        
        logger.info(f"✓ 成功映射字段:")
        logger.info(f"  - questionId (from id): {question_id}")
        logger.info(f"  - conditionId: {condition_id[:20]}...")
        logger.info(f"  - oracle: {oracle}")
        
        return self.decode_market(
            condition_id=condition_id,
            question_id=question_id,
            oracle=oracle,
            gamma_data=gamma_data
        )


def main():
    """主函数 - 命令行入口"""
    parser = argparse.ArgumentParser(
        description="PolyMind 市场解码器 - 计算Polymarket市场TokenId"
    )
    parser.add_argument(
        "--market-slug",
        type=str,
        help="市场slug (从Gamma API获取)"
    )
    parser.add_argument(
        "--condition-id",
        type=str,
        help="条件ID"
    )
    parser.add_argument(
        "--question-id",
        type=str,
        help="问题ID"
    )
    parser.add_argument(
        "--oracle",
        type=str,
        help="预言机地址"
    )
    parser.add_argument(
        "--output",
        type=str,
        default=None,
        help="输出JSON文件路径 (可选)"
    )
    
    args = parser.parse_args()
    
    decoder = MarketDecoder()
    market_params = None
    
    # 从Gamma API获取
    if args.market_slug:
        logger.info(f"方式: Gamma API Slug")
        market_params = decoder.decode_market_from_gamma_slug(args.market_slug)
    
    # 直接使用提供的参数
    elif all([args.condition_id, args.question_id, args.oracle]):
        logger.info(f"方式: 直接参数")
        market_params = decoder.decode_market(
            condition_id=args.condition_id,
            question_id=args.question_id,
            oracle=args.oracle
        )
    
    else:
        logger.error("错误: 需要提供 --market-slug 或 (--condition-id + --question-id + --oracle)")
        parser.print_help()
        sys.exit(1)
    
    if not market_params:
        logger.error("无法解码市场参数")
        sys.exit(1)
    
    # 转换为JSON
    market_dict = asdict(market_params)
    
    # 输出结果
    if args.output:
        try:
            with open(args.output, 'w', encoding='utf-8') as f:
                json.dump(market_dict, f, indent=2, ensure_ascii=False)
            logger.info(f"✓ 市场数据已保存到: {args.output}")
        except Exception as e:
            logger.error(f"保存文件失败: {e}")
            sys.exit(1)
    else:
        print("\n=== 解码结果 ===")
        print(json.dumps(market_dict, indent=2, ensure_ascii=False))
    
    logger.info("解码完成!")


if __name__ == "__main__":
    main()
