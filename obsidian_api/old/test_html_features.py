#!/usr/bin/env python3
"""
Test HTML display features for AIsecretary
Quick validation of HTML rendering and format parameter functionality
"""

import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent / "app"))

from app.presentation.html_renderer import HtmlRenderer
from app.presentation.presenters import create_presenter


def test_html_renderer():
    """Test HTML renderer with different themes"""
    print("🔍 Testing HTML Renderer...")
    
    markdown_test = """
# Test Document

This is a **test document** with various markdown elements.

## Features Tested

- Basic text formatting
- **Bold** and *italic* text
- `inline code`
- Lists and bullets

### Code Block

```python
def hello():
    return "Hello, World!"
```

### Table

| Feature | Status | Notes |
|---------|--------|-------|
| Headers | ✅ Working | H1, H2, H3 support |
| Lists | ✅ Working | Bullet and numbered |
| Code | ✅ Working | Inline and blocks |
| Links | 🔄 Testing | [Example](https://example.com) |

> This is a blockquote to test styling.

---

End of test document.
"""
    
    themes = ["obsidian", "light", "dark", "minimal"]
    
    for theme in themes:
        print(f"  📱 Testing {theme} theme...")
        renderer = HtmlRenderer(theme=theme, mobile_optimized=True)
        html = renderer.render(markdown_test, f"Test - {theme.title()} Theme")
        
        # Basic validation
        assert "<!DOCTYPE html>" in html
        assert f"Test - {theme.title()} Theme" in html
        assert "markdown-body" in html
        assert "<h1>" in html and "</h1>" in html
        assert "<table>" in html and "</table>" in html
        
        print(f"    ✅ {theme} theme: {len(html)} chars generated")
    
    print("✅ HTML Renderer tests passed!")


def test_presenters():
    """Test presenter classes"""
    print("🔍 Testing Presenters...")
    
    # Test Files Presenter
    files_presenter = create_presenter('files')
    files_data = ["note1.md", "folder/note2.md", "部品.md"]
    files_md = files_presenter.to_markdown(files_data, "TestVault")
    assert "ファイル一覧" in files_md
    assert "部品" in files_md
    print("  ✅ Files presenter working")
    
    # Test Search Presenter  
    search_presenter = create_presenter('search')
    search_data = [
        {"file": "note1.md", "snippet": "test content", "line": 10, "score": 0.95},
        {"file": "部品.md", "snippet": "ダイオード情報", "line": 5, "score": 0.87}
    ]
    search_md = search_presenter.to_markdown(search_data, "ダイオード")
    assert "検索結果" in search_md
    assert "ダイオード" in search_md
    print("  ✅ Search presenter working")
    
    # Test Assistant Presenter
    assistant_presenter = create_presenter('assistant')
    assistant_data = {
        "action": "open",
        "success": True,
        "intent": "open",
        "confidence": 0.95,
        "user_message": "ノートを開きました",
        "obsidian_url": "obsidian://open?vault=Test&file=note1"
    }
    assistant_md = assistant_presenter.to_markdown(assistant_data)
    assert "AIsecretary 応答" in assistant_md
    assert "obsidian://open" in assistant_md
    print("  ✅ Assistant presenter working")
    
    print("✅ Presenter tests passed!")


def test_css_variables():
    """Test CSS variable functionality"""
    print("🔍 Testing CSS Variables...")
    
    # Test custom settings
    renderer = HtmlRenderer(
        theme="obsidian",
        mobile_optimized=True,
        font_size="20px",
        max_width="600px"
    )
    
    html = renderer.render("# Test", "CSS Test")
    css_variables = renderer._get_css_variables()
    
    assert "--font-size: 20px" in css_variables
    assert "--max-width: 600px" in css_variables
    print("  ✅ Custom CSS variables working")
    
    # Test mobile CSS
    mobile_css = renderer._get_mobile_css()
    assert "@media screen" in mobile_css
    assert "max-width: 768px" in mobile_css
    print("  ✅ Mobile CSS working")
    
    print("✅ CSS variable tests passed!")


def test_markdown_processing():
    """Test markdown processing edge cases"""
    print("🔍 Testing Markdown Processing...")
    
    # Test Japanese content
    japanese_md = """
# 日本語テスト

これは**日本語**の*テスト*です。

## 機能
- リスト項目 1
- リスト項目 2

`コード` と [リンク](https://example.com) の テスト。

> 引用文のテスト

---

終了
"""
    
    renderer = HtmlRenderer(theme="obsidian")
    html = renderer.render(japanese_md, "日本語テスト")
    
    assert "日本語テスト" in html
    assert "これは<strong>日本語</strong>" in html
    assert "リスト項目" in html
    print("  ✅ Japanese content processing working")
    
    # Test empty/minimal content
    empty_html = renderer.render("", "Empty Test")
    assert "<!DOCTYPE html>" in empty_html
    assert "Empty Test" in empty_html
    print("  ✅ Empty content handling working")
    
    print("✅ Markdown processing tests passed!")


def generate_sample_html():
    """Generate sample HTML files for manual testing"""
    print("🔍 Generating sample HTML files...")
    
    sample_md = """
# AIsecretary HTML Display Test

## 📱 iOS Shortcuts対応テスト

このページは **AIsecretary** の HTML表示機能をテストするためのサンプルです。

### ✅ 実装済み機能

1. **Markdown → HTML変換**
   - 基本的なマークダウン記法
   - 日本語フォント最適化
   - モバイル対応

2. **テーマシステム**  
   - Obsidian風ダークテーマ
   - GitHub風ライト/ダークテーマ
   - ミニマルテーマ

3. **エンドポイント統合**
   - `format=html` パラメータ
   - 動的テーマ切り替え
   - モバイル最適化制御

### 🎯 使用例

```bash
# 検索結果をHTML表示
curl "http://localhost:8787/search?q=部品&format=html&css_theme=obsidian&mobile=true"

# ノート内容をHTML表示  
curl "http://localhost:8787/note?path=部品.md&format=html&css_theme=light"

# AIアシスタント応答をHTML表示
curl "http://localhost:8787/assistant?q=部品を開いて&vault=MyVault&format=html"
```

### 📊 技術仕様

| 項目 | 仕様 | 状態 |
|------|------|------|
| **レンダラ** | Python markdown | ✅ |
| **テーマ** | 4種類CSS内蔵 | ✅ |
| **モバイル** | iOS Safari最適化 | ✅ |
| **文字エンコード** | UTF-8対応 | ✅ |

### 🔗 関連リンク

- [Obsidian](https://obsidian.md)で開く: `obsidian://open?vault=MyVault&file=テスト`
- [GitHub Repository](https://github.com/example/aisecretary)

---

**生成時刻**: 2025年12月28日  
**テーマ**: {theme}  
**モバイル最適化**: {mobile}
"""
    
    themes = ["obsidian", "light", "dark", "minimal"] 
    output_dir = Path("test_output")
    output_dir.mkdir(exist_ok=True)
    
    for theme in themes:
        for mobile in [True, False]:
            mobile_suffix = "_mobile" if mobile else "_desktop"
            filename = f"sample_{theme}{mobile_suffix}.html"
            
            renderer = HtmlRenderer(theme=theme, mobile_optimized=mobile)
            formatted_md = sample_md.format(theme=theme, mobile="有効" if mobile else "無効")
            html = renderer.render(formatted_md, f"AIsecretary テスト - {theme.title()}")
            
            output_path = output_dir / filename
            output_path.write_text(html, encoding="utf-8")
            print(f"  📄 Generated: {output_path}")
    
    print(f"✅ Sample files generated in {output_dir}/")
    print(f"   Open any .html file in browser to test display")


def main():
    """Run all tests"""
    print("🚀 Starting AIsecretary HTML Features Test")
    print("="*50)
    
    try:
        test_html_renderer()
        print()
        
        test_presenters() 
        print()
        
        test_css_variables()
        print()
        
        test_markdown_processing()
        print()
        
        generate_sample_html()
        print()
        
        print("🎉 All tests passed!")
        print("✅ HTML display functionality is working correctly")
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0


if __name__ == "__main__":
    sys.exit(main())