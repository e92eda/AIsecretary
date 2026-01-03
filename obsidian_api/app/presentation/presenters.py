"""
Presenters for AIsecretary
Convert API responses to Markdown format for HTML display
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from datetime import datetime
import json


class BasePresenter:
    """Base presenter with common formatting utilities"""
    
    def escape_markdown(self, text: str) -> str:
        """Escape markdown special characters"""
        if not text:
            return ""
        
        # Escape common markdown characters
        chars_to_escape = ['*', '_', '`', '\\', '[', ']', '(', ')', '#', '+', '-', '.', '!']
        for char in chars_to_escape:
            text = text.replace(char, f'\\{char}')
        
        return text
    
    def format_timestamp(self, timestamp: Optional[str] = None) -> str:
        """Format timestamp for display"""
        if not timestamp:
            timestamp = datetime.now().isoformat()
        
        try:
            dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
            return dt.strftime('%Y年%m月%d日 %H:%M')
        except:
            return timestamp


class FilesPresenter(BasePresenter):
    """Convert file list to Markdown"""
    
    def to_markdown(self, files: List[str], vault_name: str = "") -> str:
        """Convert file list to Markdown table"""
        if not files:
            return "## ファイル一覧\n\n**該当するファイルがありません。**"
        
        header = f"## ファイル一覧 ({len(files)}件)"
        if vault_name:
            header += f" - {vault_name}"
        
        markdown = [header, ""]
        
        # Create table
        markdown.extend([
            "| # | ファイル名 | パス |",
            "|---|----------|------|"
        ])
        
        for i, file_path in enumerate(files, 1):
            # Extract filename from path
            filename = file_path.split('/')[-1] if '/' in file_path else file_path
            filename = filename.replace('.md', '')  # Remove .md extension
            
            # Escape markdown in paths
            safe_filename = self.escape_markdown(filename)
            safe_path = self.escape_markdown(file_path)
            
            markdown.append(f"| {i} | **{safe_filename}** | `{safe_path}` |")
        
        return "\n".join(markdown)


class SearchPresenter(BasePresenter):
    """Convert search results to Markdown"""
    
    def to_markdown(self, search_results: List[Dict[str, Any]], query: str = "") -> str:
        """Convert search results to Markdown"""
        if not search_results:
            query_display = f" '{query}'" if query else ""
            return f"## 検索結果{query_display}\n\n**該当する結果がありません。**"
        
        query_display = f" '{query}'" if query else ""
        header = f"## 検索結果{query_display} ({len(search_results)}件)"
        
        markdown = [header, ""]
        
        for i, result in enumerate(search_results, 1):
            file_path = result.get('file', '不明')
            snippet = result.get('snippet', '').strip()
            line_number = result.get('line', '')
            score = result.get('score', 0)
            
            # Clean filename
            filename = file_path.split('/')[-1] if '/' in file_path else file_path
            filename = filename.replace('.md', '')
            
            markdown.append(f"### {i}. {self.escape_markdown(filename)}")
            
            if line_number:
                markdown.append(f"**行:** {line_number}")
            
            if score:
                markdown.append(f"**スコア:** {score:.2f}")
            
            markdown.append(f"**パス:** `{self.escape_markdown(file_path)}`")
            
            if snippet:
                # Format snippet with proper markdown
                cleaned_snippet = snippet.replace('\n', ' ').strip()
                if len(cleaned_snippet) > 200:
                    cleaned_snippet = cleaned_snippet[:200] + '...'
                
                markdown.append(f"**内容:**")
                markdown.append(f"> {cleaned_snippet}")
            
            markdown.append("")  # Add spacing between results
        
        return "\n".join(markdown)


class NotePresenter(BasePresenter):
    """Convert note content to Markdown"""
    
    def to_markdown(self, note_content: str, note_path: str = "", section: str = "") -> str:
        """Convert note content to Markdown with metadata"""
        if not note_content:
            return f"## ノート: {note_path}\n\n**内容がありません。**"
        
        # Build header
        filename = note_path.split('/')[-1] if '/' in note_path else note_path
        filename = filename.replace('.md', '')
        
        header = f"## {self.escape_markdown(filename)}"
        if section:
            header += f" - {self.escape_markdown(section)}"
        
        markdown = [header, ""]
        
        # Add metadata
        if note_path:
            markdown.append(f"**パス:** `{self.escape_markdown(note_path)}`")
            markdown.append("")
        
        # Add content (preserve original markdown)
        markdown.append("---")
        markdown.append("")
        markdown.append(note_content)
        
        return "\n".join(markdown)


class ResolvePresenter(BasePresenter):
    """Convert resolve/candidates to Markdown"""
    
    def to_markdown(self, candidates: List[Dict[str, Any]], query: str = "") -> str:
        """Convert resolution candidates to Markdown"""
        if not candidates:
            query_display = f" '{query}'" if query else ""
            return f"## 候補{query_display}\n\n**該当する候補がありません。**"
        
        query_display = f" '{query}'" if query else ""
        header = f"## 候補{query_display} ({len(candidates)}件)"
        
        markdown = [header, ""]
        
        # Create table
        markdown.extend([
            "| # | ノート名 | 関連度 | パス |",
            "|---|---------|--------|------|"
        ])
        
        for i, candidate in enumerate(candidates, 1):
            name = candidate.get('name', '不明')
            score = candidate.get('score', 0)
            path = candidate.get('path', '')
            
            # Format score
            score_display = f"{score:.2f}" if isinstance(score, (int, float)) else str(score)
            
            safe_name = self.escape_markdown(name)
            safe_path = self.escape_markdown(path)
            
            markdown.append(f"| {i} | **{safe_name}** | {score_display} | `{safe_path}` |")
        
        return "\n".join(markdown)


class AssistantPresenter(BasePresenter):
    """Convert assistant response to Markdown"""
    
    def to_markdown(self, assistant_response: Dict[str, Any]) -> str:
        """Convert assistant response to formatted Markdown"""
        action = assistant_response.get('action', 'unknown')
        success = assistant_response.get('success', False)
        user_message = assistant_response.get('user_message', '')
        intent = assistant_response.get('intent', '')
        confidence = assistant_response.get('confidence', 0)
        
        # Build header
        status_emoji = "✅" if success else "❌"
        header = f"## {status_emoji} AIsecretary 応答"
        
        markdown = [header, ""]
        
        # Add metadata section
        markdown.extend([
            "### 📊 実行情報",
            "",
            f"- **アクション:** `{action}`",
            f"- **成功:** {status_emoji} {'はい' if success else 'いいえ'}",
        ])
        
        if intent:
            markdown.append(f"- **意図:** `{intent}`")
        
        if confidence:
            confidence_percent = f"{confidence * 100:.1f}%" if confidence <= 1 else f"{confidence:.2f}"
            markdown.append(f"- **信頼度:** {confidence_percent}")
        
        # Add timing info if available
        duration = assistant_response.get('total_duration_ms')
        if duration:
            markdown.append(f"- **処理時間:** {duration:.1f}ms")
        
        session_id = assistant_response.get('session_id')
        if session_id:
            markdown.append(f"- **セッション:** `{session_id}`")
        
        markdown.append("")  # Add spacing
        
        # Add main response
        if user_message:
            markdown.extend([
                "### 💬 応答内容",
                "",
                user_message,
                ""
            ])
        
        # Add Obsidian URL if available
        obsidian_url = assistant_response.get('obsidian_url')
        if obsidian_url:
            markdown.extend([
                "### 🔗 リンク",
                "",
                f"[Obsidian で開く]({obsidian_url})",
                ""
            ])
        
        # Add clarification if available  
        clarification = assistant_response.get('clarification')
        if clarification:
            question = clarification.get('question', '')
            options = clarification.get('options', [])
            
            markdown.extend([
                "### ❓ 確認が必要です",
                "",
                question,
                ""
            ])
            
            if options:
                markdown.append("**選択肢:**")
                for option in options:
                    label = option.get('label', '')
                    intent_opt = option.get('intent', '')
                    if label:
                        markdown.append(f"- {label} (`{intent_opt}`)")
                
                markdown.append("")
        
        # Add error details if failed
        if not success:
            error_detail = assistant_response.get('error', '')
            fallback_info = assistant_response.get('fallback_intent', '')
            
            markdown.extend([
                "### ⚠️ エラー詳細",
                ""
            ])
            
            if error_detail:
                markdown.append(f"**エラー:** {error_detail}")
            
            if fallback_info:
                markdown.append(f"**代替処理:** {fallback_info}")
        
        # Add raw response for debugging (in development)
        debug_info = assistant_response.get('routing_reason')
        if debug_info:
            markdown.extend([
                "",
                "<details>",
                "<summary>詳細情報</summary>",
                "",
                f"**ルーティング理由:** {debug_info}",
                "",
                "```json",
                json.dumps(assistant_response, indent=2, ensure_ascii=False),
                "```",
                "",
                "</details>"
            ])
        
        return "\n".join(markdown)


class TablePresenter(BasePresenter):
    """Convert table extraction results to Markdown"""
    
    def to_markdown(self, table_data: Dict[str, Any]) -> str:
        """Convert table extraction results to Markdown"""
        tables = table_data.get('tables', [])
        source_file = table_data.get('source_file', '')
        
        if not tables:
            return "## テーブル抽出\n\n**該当するテーブルがありません。**"
        
        header = f"## テーブル抽出 ({len(tables)}件)"
        if source_file:
            filename = source_file.split('/')[-1] if '/' in source_file else source_file
            header += f" - {filename.replace('.md', '')}"
        
        markdown = [header, ""]
        
        for i, table in enumerate(tables, 1):
            markdown.append(f"### テーブル {i}")
            markdown.append("")
            
            headers = table.get('headers', [])
            rows = table.get('rows', [])
            
            if headers and rows:
                # Build markdown table
                header_row = "| " + " | ".join([self.escape_markdown(h) for h in headers]) + " |"
                separator = "| " + " | ".join(["---"] * len(headers)) + " |"
                
                markdown.append(header_row)
                markdown.append(separator)
                
                for row in rows:
                    if len(row) == len(headers):
                        escaped_row = [self.escape_markdown(str(cell)) for cell in row]
                        row_md = "| " + " | ".join(escaped_row) + " |"
                        markdown.append(row_md)
            
            markdown.append("")  # Add spacing between tables
        
        return "\n".join(markdown)


# Factory function for easy access
def create_presenter(content_type: str) -> BasePresenter:
    """Create appropriate presenter for content type"""
    presenters = {
        'files': FilesPresenter(),
        'search': SearchPresenter(),
        'note': NotePresenter(),
        'resolve': ResolvePresenter(),
        'assistant': AssistantPresenter(),
        'table': TablePresenter(),
    }
    
    return presenters.get(content_type, BasePresenter())