"""
HTML Renderer for AIsecretary
Converts Markdown to styled HTML for iOS Shortcuts and web display
"""

from __future__ import annotations

import markdown
from markdown.extensions import tables, fenced_code, toc, codehilite
from typing import Optional
from ..config import settings


class HtmlRenderer:
    """HTML renderer with configurable CSS themes and mobile optimization"""
    
    def __init__(
        self, 
        theme: Optional[str] = None, 
        mobile_optimized: Optional[bool] = None,
        font_size: Optional[str] = None,
        max_width: Optional[str] = None
    ):
        # Use settings defaults or override with parameters
        self.theme = theme or settings.css_theme
        self.mobile_optimized = mobile_optimized if mobile_optimized is not None else settings.mobile_optimized
        self.font_size = font_size or settings.html_font_size
        self.max_width = max_width or settings.html_max_width
        
        # Configure markdown processor with common extensions
        self.md = markdown.Markdown(
            extensions=[
                'tables',           # Table support
                'fenced_code',      # ```code blocks
                'toc',              # Table of contents
                'codehilite',       # Syntax highlighting
                'nl2br',            # Newlines to <br>
            ],
            extension_configs={
                'codehilite': {
                    'css_class': 'highlight',
                    'use_pygments': False,  # Use CSS-only highlighting
                }
            }
        )
    
    def render(self, markdown_text: str, title: str = "AIsecretary") -> str:
        """Convert Markdown to styled HTML"""
        # Convert markdown to HTML
        html_content = self.md.convert(markdown_text)
        
        # Generate CSS
        css = self._get_complete_css()
        
        # Build complete HTML document
        return self._build_html_document(html_content, css, title)
    
    def _build_html_document(self, content: str, css: str, title: str) -> str:
        """Build complete HTML document"""
        return f"""<!DOCTYPE html>
<html lang="ja">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <meta name="apple-mobile-web-app-capable" content="yes">
    <meta name="apple-mobile-web-app-status-bar-style" content="default">
    <title>{self._escape_html(title)}</title>
    <style>
{css}
    </style>
</head>
<body>
    <article class="markdown-body">
        {content}
    </article>
</body>
</html>"""
    
    def _escape_html(self, text: str) -> str:
        """Escape HTML entities"""
        return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")
    
    def _get_complete_css(self) -> str:
        """Generate complete CSS with theme and settings"""
        css_parts = [
            self._get_css_variables(),
            self._get_base_css(),
            self._get_theme_css(),
        ]
        
        if self.mobile_optimized:
            css_parts.append(self._get_mobile_css())
        
        return "\n".join(css_parts)
    
    def _get_css_variables(self) -> str:
        """CSS variables from settings"""
        return f"""
/* CSS Variables from settings */
:root {{
    --font-size: {self.font_size};
    --max-width: {self.max_width};
    --line-height: 1.6;
    --border-radius: 6px;
    --spacing: 16px;
}}
"""
    
    def _get_base_css(self) -> str:
        """Base CSS styles"""
        return """
/* Base styles */
.markdown-body {
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif;
    font-size: var(--font-size);
    line-height: var(--line-height);
    max-width: var(--max-width);
    margin: 0 auto;
    padding: 20px;
    word-wrap: break-word;
}

/* Typography */
h1, h2, h3, h4, h5, h6 {
    margin-top: 24px;
    margin-bottom: var(--spacing);
    font-weight: 600;
    line-height: 1.25;
}

h1 { font-size: 2em; }
h2 { font-size: 1.5em; }
h3 { font-size: 1.25em; }
h4 { font-size: 1.1em; }
h5 { font-size: 1em; }
h6 { font-size: 0.9em; }

p {
    margin-bottom: var(--spacing);
    margin-top: 0;
}

/* Code */
code {
    padding: 2px 4px;
    font-family: 'SF Mono', Monaco, 'Cascadia Code', 'Roboto Mono', Consolas, monospace;
    font-size: 85%;
    border-radius: 3px;
}

pre {
    padding: var(--spacing);
    border-radius: var(--border-radius);
    overflow: auto;
    font-family: 'SF Mono', Monaco, 'Cascadia Code', 'Roboto Mono', Consolas, monospace;
    font-size: 85%;
    line-height: 1.45;
    margin-bottom: var(--spacing);
}

pre code {
    padding: 0;
    margin: 0;
    border-radius: 0;
    display: block;
    overflow-x: auto;
}

/* Lists */
ul, ol {
    padding-left: 2em;
    margin-bottom: var(--spacing);
}

li {
    margin-bottom: 0.25em;
}

/* Links */
a {
    text-decoration: none;
    font-weight: 500;
}

a:hover {
    text-decoration: underline;
}

/* Tables */
table {
    border-collapse: collapse;
    width: 100%;
    margin-bottom: var(--spacing);
    overflow-x: auto;
    display: block;
    white-space: nowrap;
}

thead, tbody {
    display: table;
    width: 100%;
    table-layout: fixed;
}

th, td {
    border: 1px solid;
    padding: 8px 12px;
    text-align: left;
    display: table-cell;
}

th {
    font-weight: 600;
}

/* Blockquotes */
blockquote {
    margin: 0 0 var(--spacing) 0;
    padding-left: var(--spacing);
    border-left: 4px solid;
    font-style: italic;
}

/* Horizontal rules */
hr {
    border: none;
    height: 1px;
    margin: calc(var(--spacing) * 2) 0;
}
"""
    
    def _get_theme_css(self) -> str:
        """Theme-specific CSS"""
        themes = {
            "obsidian": self._get_obsidian_theme(),
            "light": self._get_light_theme(),
            "dark": self._get_dark_theme(),
            "minimal": self._get_minimal_theme()
        }
        
        return themes.get(self.theme, themes["obsidian"])
    
    def _get_obsidian_theme(self) -> str:
        """Obsidian-inspired dark theme"""
        return """
/* Obsidian theme */
:root {
    --bg-color: #1e1e1e;
    --text-color: #dcddde;
    --accent-color: #7c3aed;
    --secondary-color: #a78bfa;
    --border-color: #374151;
    --code-bg: #2d2d2d;
    --pre-bg: #1f1f1f;
    --quote-border: #a78bfa;
    --hr-color: #374151;
}

body {
    background-color: var(--bg-color);
    color: var(--text-color);
}

h1, h2, h3, h4, h5, h6 {
    color: var(--accent-color);
}

h1, h2 {
    border-bottom: 1px solid var(--border-color);
    padding-bottom: 8px;
}

code {
    background-color: var(--code-bg);
    color: #f8f8f2;
}

pre {
    background-color: var(--pre-bg);
    border: 1px solid var(--border-color);
}

a {
    color: var(--secondary-color);
}

th {
    background-color: var(--accent-color);
    color: white;
    border-color: var(--border-color);
}

td {
    border-color: var(--border-color);
}

blockquote {
    border-left-color: var(--quote-border);
    color: var(--secondary-color);
}

hr {
    background-color: var(--hr-color);
}
"""
    
    def _get_light_theme(self) -> str:
        """GitHub-inspired light theme"""
        return """
/* Light theme */
:root {
    --bg-color: #ffffff;
    --text-color: #24292f;
    --accent-color: #0969da;
    --secondary-color: #218bff;
    --border-color: #d0d7de;
    --code-bg: #f6f8fa;
    --pre-bg: #f6f8fa;
    --quote-border: #d0d7de;
    --hr-color: #d0d7de;
}

body {
    background-color: var(--bg-color);
    color: var(--text-color);
}

h1, h2, h3, h4, h5, h6 {
    color: var(--text-color);
}

h1, h2 {
    border-bottom: 1px solid var(--border-color);
    padding-bottom: 8px;
}

code {
    background-color: var(--code-bg);
    color: var(--text-color);
}

pre {
    background-color: var(--pre-bg);
    border: 1px solid var(--border-color);
}

a {
    color: var(--accent-color);
}

th {
    background-color: var(--code-bg);
    border-color: var(--border-color);
}

td {
    border-color: var(--border-color);
}

blockquote {
    border-left-color: var(--quote-border);
    color: #656d76;
}

hr {
    background-color: var(--hr-color);
}
"""
    
    def _get_dark_theme(self) -> str:
        """GitHub dark theme"""
        return """
/* Dark theme */
:root {
    --bg-color: #0d1117;
    --text-color: #e6edf3;
    --accent-color: #2f81f7;
    --secondary-color: #58a6ff;
    --border-color: #30363d;
    --code-bg: #161b22;
    --pre-bg: #0d1117;
    --quote-border: #30363d;
    --hr-color: #30363d;
}

body {
    background-color: var(--bg-color);
    color: var(--text-color);
}

h1, h2, h3, h4, h5, h6 {
    color: var(--text-color);
}

h1, h2 {
    border-bottom: 1px solid var(--border-color);
    padding-bottom: 8px;
}

code {
    background-color: var(--code-bg);
    color: var(--text-color);
}

pre {
    background-color: var(--pre-bg);
    border: 1px solid var(--border-color);
}

a {
    color: var(--secondary-color);
}

th {
    background-color: var(--code-bg);
    border-color: var(--border-color);
}

td {
    border-color: var(--border-color);
}

blockquote {
    border-left-color: var(--quote-border);
    color: #7d8590;
}

hr {
    background-color: var(--hr-color);
}
"""
    
    def _get_minimal_theme(self) -> str:
        """Clean minimal theme"""
        return """
/* Minimal theme */
:root {
    --bg-color: #fefefe;
    --text-color: #333333;
    --accent-color: #000000;
    --secondary-color: #666666;
    --border-color: #e1e4e8;
    --code-bg: #f5f5f5;
    --pre-bg: #f8f8f8;
    --quote-border: #e1e4e8;
    --hr-color: #e1e4e8;
}

body {
    background-color: var(--bg-color);
    color: var(--text-color);
}

.markdown-body {
    font-family: Georgia, 'Times New Roman', serif;
}

h1, h2, h3, h4, h5, h6 {
    color: var(--accent-color);
    font-family: -apple-system, BlinkMacSystemFont, sans-serif;
}

code {
    background-color: var(--code-bg);
    color: var(--text-color);
}

pre {
    background-color: var(--pre-bg);
    border-left: 4px solid var(--border-color);
    border-radius: 0;
}

a {
    color: var(--text-color);
    border-bottom: 1px solid var(--border-color);
}

a:hover {
    border-bottom-color: var(--accent-color);
}

th, td {
    border-color: var(--border-color);
}

th {
    background-color: var(--code-bg);
}

blockquote {
    border-left-color: var(--quote-border);
    color: var(--secondary-color);
}

hr {
    background-color: var(--hr-color);
}
"""
    
    def _get_mobile_css(self) -> str:
        """Mobile optimization CSS"""
        return """
/* Mobile optimizations */
@media screen and (max-width: 768px) {
    :root {
        --font-size: 18px;
        --max-width: 100%;
    }
    
    .markdown-body {
        padding: 12px;
        margin: 0;
    }
    
    h1 { font-size: 1.6em; }
    h2 { font-size: 1.4em; }
    h3 { font-size: 1.2em; }
    h4 { font-size: 1.1em; }
    
    /* Touch-friendly links */
    a {
        min-height: 44px;
        display: inline-block;
        padding: 4px 0;
        line-height: 1.4;
    }
    
    /* Prevent horizontal scroll */
    pre {
        overflow-x: auto;
        font-size: 14px;
        padding: 12px;
    }
    
    pre code {
        white-space: pre-wrap;
        word-break: break-all;
    }
    
    /* Scrollable tables */
    table {
        font-size: 14px;
    }
    
    /* Larger tap targets */
    th, td {
        padding: 12px 8px;
    }
    
    /* Compact spacing */
    :root {
        --spacing: 12px;
    }
    
    h1, h2, h3, h4, h5, h6 {
        margin-top: 20px;
        margin-bottom: 12px;
    }
}

/* iOS Safari specific optimizations */
@supports (-webkit-touch-callout: none) {
    .markdown-body {
        -webkit-text-size-adjust: 100%;
        -webkit-font-smoothing: antialiased;
    }
    
    /* Prevent zoom on input focus */
    input, select, textarea {
        font-size: 16px;
    }
    
    /* iOS scroll momentum */
    pre {
        -webkit-overflow-scrolling: touch;
    }
    
    table {
        -webkit-overflow-scrolling: touch;
    }
}
"""