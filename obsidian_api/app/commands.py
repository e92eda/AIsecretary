from pathlib import Path
from typing import List
from .models import Command

try:
    import yaml
except ImportError:
    yaml = None

def load_commands(commands_file: Path) -> List[Command]:
    """
    YAMLコマンド定義ファイルを読み込み、Commandオブジェクトのリストに変換
    
    Args:
        commands_file: commands.ymlファイルのパス
        
    Returns:
        List[Command]: 読み込まれたコマンドのリスト（失敗時は空リスト）
        
    処理フロー:
        1. yaml依存関係チェック
        2. ファイル存在確認
        3. YAML解析
        4. 各項目をCommandオブジェクトに変換
        5. 変換に失敗した項目はスキップ
    """
    if yaml is None:
        return []  # Return empty if yaml not available
    if not commands_file.exists():
        return []
    data = yaml.safe_load(commands_file.read_text(encoding="utf-8"))
    if not data:
        return []
    commands = []
    for item in data:
        try:
            commands.append(Command(**item))
        except Exception:
            continue  # 不正な形式の項目は無視して継続
    return commands

def match_command(query: str, commands: List[Command]) -> Command | None:
    """
    クエリ文字列に対応するコマンドを検索・マッチング
    
    Args:
        query: ユーザー入力クエリ（例: "膵癌について", "kakenhi申請"）
        commands: load_commands()で読み込んだコマンドリスト
        
    Returns:
        Command | None: マッチしたコマンド（見つからない場合はNone）
        
    検索方式:
        - 部分一致検索（大文字小文字区別なし）
        - 各コマンドのキーワードリストを順次チェック
        - 最初にマッチしたコマンドを即座に返却
        
    例:
        query="膵癌SBRT" → keywords=["膵癌", ...] → pancreatic_sbrtコマンドを返却
        query="科研費" → keywords=["科研費", ...] → kakenhiコマンドを返却
    """
    q = (query or "").lower()
    for cmd in commands:
        for kw in cmd.keywords:
            if kw.lower() in q:
                return cmd  # 最初にマッチしたコマンドを返却
    return None  # マッチするコマンドなし
