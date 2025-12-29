from pathlib import Path
import re
from .commands import load_commands, match_command
from .search import grep_vault
from .models import ResolveResult
from .logging_utils import setup_orchestrator_logger

# Setup logger for resolver module
try:
    logger = setup_orchestrator_logger("resolver")
except Exception:
    # Fallback if logging setup fails
    import logging
    logger = logging.getLogger("resolver")


def _extract_search_terms(query: str) -> list[str]:
    """クエリから検索に有効なキーワードを抽出"""
    # .mdファイル名パターンを優先抽出
    md_pattern = r'([^\s]+\.md)'
    md_matches = re.findall(md_pattern, query, re.IGNORECASE)
    if md_matches:
        return md_matches
    
    # 一般的なキーワード抽出（アクション語を除外）
    action_words = {'開', '開く', 'open', '表示', '要約', 'summary', 'まとめ', 'ノート', '全文', '本文', 'table', '表', '一覧'}
    words = re.findall(r'\S+', query)
    keywords = [w for w in words if w.lower() not in action_words]
    
    return keywords if keywords else [query]

def resolve_query(query: str, vault_root: Path, commands_file: Path, prefer: str = "most_hits") -> ResolveResult:
    """
    クエリを解決してObsidianファイルパスを特定する
    
    解決戦略:
    1. コマンド定義ファイル (commands.yml) での完全マッチ検索
    2. Vault内でのgrep検索（元のクエリ）
    3. キーワード抽出による再検索（ヒット数0の場合）
    4. 候補ソートとベストマッチ選択
    """
    logger.debug(f"🔍 Starting query resolution: '{query}' with prefer='{prefer}'")
    
    # Step 1: 事前定義されたコマンドから検索
    commands = load_commands(commands_file)
    cmd = match_command(query, commands)
    if cmd:
        logger.info(f"✅ Command match found: {cmd.open.path}")
        return ResolveResult(found=True, open_path=cmd.open.path, source="command")

    # Step 2: 元のクエリでVault全体を検索
    logger.debug(f"🔎 Searching vault with original query: '{query}'")
    hits = grep_vault(vault_root, query, limit=200)
    
    # ヒットしない場合、キーワード抽出して再検索
    if not hits:
        search_terms = _extract_search_terms(query)
        logger.debug(f"🔍 No hits with original query, trying extracted terms: {search_terms}")
        for term in search_terms:
            hits = grep_vault(vault_root, term, limit=200)
            if hits:
                logger.debug(f"✅ Found {len(hits)} hits with term: '{term}'")
                break
    else:
        logger.debug(f"✅ Found {len(hits)} hits with original query")
    
    if not hits:
        logger.warning(f"❌ No hits found for query: '{query}'")
        return ResolveResult(found=False, reason="no hits")

    counts = {}
    for h in hits:
        counts[h["path"]] = counts.get(h["path"], 0) + 1

    candidates = list(counts.items())
    if prefer == "shortest":
        candidates.sort(key=lambda x: (len(x[0]), -x[1]))
        logger.debug(f"📊 Sorted {len(candidates)} candidates by shortest path")
    else:
        candidates.sort(key=lambda x: (-x[1], len(x[0])))
        logger.debug(f"📊 Sorted {len(candidates)} candidates by most hits")

    selected_path = candidates[0][0]
    logger.info(f"🎯 Selected path: {selected_path} (hits: {candidates[0][1]})")
    
    return ResolveResult(found=True, open_path=selected_path, source="search", candidates=candidates[:10])
