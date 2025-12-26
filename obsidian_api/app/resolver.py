from pathlib import Path
import re
from .commands import load_commands, match_command
from .search import grep_vault
from .models import ResolveResult

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
    commands = load_commands(commands_file)
    cmd = match_command(query, commands)
    if cmd:
        return ResolveResult(found=True, open_path=cmd.open.path, source="command")

    # 元のクエリで検索を試行
    hits = grep_vault(vault_root, query, limit=200)
    
    # ヒットしない場合、キーワード抽出して再検索
    if not hits:
        search_terms = _extract_search_terms(query)
        for term in search_terms:
            hits = grep_vault(vault_root, term, limit=200)
            if hits:
                break
    
    if not hits:
        return ResolveResult(found=False, reason="no hits")

    counts = {}
    for h in hits:
        counts[h["path"]] = counts.get(h["path"], 0) + 1

    candidates = list(counts.items())
    if prefer == "shortest":
        candidates.sort(key=lambda x: (len(x[0]), -x[1]))
    else:
        candidates.sort(key=lambda x: (-x[1], len(x[0])))

    return ResolveResult(found=True, open_path=candidates[0][0], source="search", candidates=candidates[:10])
