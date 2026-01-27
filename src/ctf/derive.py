"""
CTF (Conditional Token Framework) 工具函数
用于计算TokenId等链上参数
"""
from dataclasses import dataclass
from web3 import Web3
from typing import Tuple


@dataclass
class BinaryPositions:
    """二元头寸信息"""
    position_yes: str
    position_no: str
    collection_id_yes: str
    collection_id_no: str


def derive_binary_positions(
    oracle: str,
    question_id: str,
    condition_id: str,
    collateral_token: str
) -> BinaryPositions:
    """推导二元市场的头寸TokenId"""
    
    # YES和NO的indexSet
    INDEX_SET_YES = 1
    INDEX_SET_NO = 2
    PARENT_COLLECTION_ID = "0x" + "0" * 64
    
    # 计算CollectionId
    collection_id_yes = _calculate_collection_id(
        PARENT_COLLECTION_ID, condition_id, INDEX_SET_YES
    )
    collection_id_no = _calculate_collection_id(
        PARENT_COLLECTION_ID, condition_id, INDEX_SET_NO
    )
    
    # 计算TokenId
    position_yes = _calculate_position_id(collateral_token, collection_id_yes)
    position_no = _calculate_position_id(collateral_token, collection_id_no)
    
    return BinaryPositions(
        position_yes=position_yes,
        position_no=position_no,
        collection_id_yes=collection_id_yes,
        collection_id_no=collection_id_no
    )


def _calculate_collection_id(parent_collection_id: str, condition_id: str, index_set: int) -> str:
    """计算CollectionId"""
    parent = bytes.fromhex(parent_collection_id[2:])
    condition = bytes.fromhex(condition_id[2:])
    index_bytes = index_set.to_bytes(32, byteorder='big')
    
    combined = parent + condition + index_bytes
    collection_id = "0x" + Web3.keccak(combined).hex()
    return collection_id


def _calculate_position_id(collateral_token: str, collection_id: str) -> str:
    """计算PositionId (TokenId)"""
    collateral = bytes.fromhex(collateral_token[2:])
    collection = bytes.fromhex(collection_id[2:])
    
    combined = collateral + collection
    position_id = "0x" + Web3.keccak(combined).hex()
    return position_id
