"""评审快照：把会话当前状态组装为可归档、可校验的 JSON 快照。

快照内容（payload，字段顺序固定）：

- ``schema``：快照格式版本标识；
- ``session_id`` / ``created_at``：会话标识与创建时间（取自数据库，稳定不变）；
- ``candidates`` / ``disabled``：全部候选（最初录入顺序）与停用名单（同序）；
- ``judgments``：全部判断记录（按记录 id 顺序，含涉及停用候选的记录）；
- ``progress`` / ``ranking`` / ``conflict``：与状态接口同一口径的进度、
  Schulze 排名（有序并列组）与循环冲突信息（无冲突时为 None）。

规范序列化：固定字段顺序（即本模块构造 dict 的顺序）＋ UTF-8 ＋ 无空白
（``separators=(",", ":")``），对序列化结果的 UTF-8 字节计算 SHA-256，
即 ``snapshot_sha256``。同一会话状态无论何时生成，payload 与哈希逐位一致；
下载方可按同一规范重新序列化 payload 并比对哈希，校验快照完整未被篡改。
"""
from __future__ import annotations

import hashlib
import json

SCHEMA_VERSION = "pairwise-decision-desk/snapshot@1"


def canonical_json(payload: dict) -> str:
    """payload 的规范 JSON 文本：固定字段顺序（dict 构造序）、无空白、不转义非 ASCII。"""
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))


def snapshot_sha256(payload: dict) -> str:
    """payload 规范序列化结果的 UTF-8 字节 SHA-256（十六进制小写）。"""
    return hashlib.sha256(canonical_json(payload).encode("utf-8")).hexdigest()


def build_snapshot(
    *,
    session_id: str,
    created_at: str,
    all_candidates: list[str],
    disabled: list[str],
    judgments: list[dict],
    progress: dict,
    ranking: list[list[str]],
    conflict: dict | None,
) -> dict:
    """按固定字段顺序组装快照 payload（纯函数，不写库）。

    所有列表 / 字典均重新构造：既让快照与内部视图对象解耦，也保证每个
    嵌套对象的键序与规范序列化口径一致（判断记录固定为 a、b、result）。
    """
    return {
        "schema": SCHEMA_VERSION,
        "session_id": session_id,
        "created_at": created_at,
        # 全部候选（最初录入顺序）；停用不删除候选，也不删除其判断记录
        "candidates": list(all_candidates),
        "disabled": list(disabled),
        # 逐对结果：全部判断记录按记录 id 顺序（含涉及停用候选的记录）
        "judgments": [
            {"a": h["a"], "b": h["b"], "result": h["result"]} for h in judgments
        ],
        # 以下与状态接口同一口径：只按启用候选计算的派生结果
        "progress": {"done": progress["done"], "total": progress["total"]},
        "ranking": [list(group) for group in ranking],
        "conflict": (
            None
            if conflict is None
            else {
                "cycle": list(conflict["cycle"]),
                "edges": [
                    {"a": e["a"], "b": e["b"], "result": e["result"]}
                    for e in conflict["edges"]
                ],
            }
        ),
    }
