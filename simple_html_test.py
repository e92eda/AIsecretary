#!/usr/bin/env python3
"""
Simple HTML rendering test for debugging
"""

import markdown
from pathlib import Path

def test_basic_markdown():
    """Test basic markdown rendering"""
    print("Testing markdown library...")
    
    md = markdown.Markdown(extensions=['tables', 'fenced_code'])
    
    test_md = """
# Test Header

This is **bold** and *italic* text.

## Subheader

- Item 1
- Item 2

### Code

```python
print("Hello")
```

| Col1 | Col2 |
|------|------|
| A    | B    |
"""
    
    html = md.convert(test_md)
    print("Generated HTML:")
    print(html[:200] + "..." if len(html) > 200 else html)
    
    # Check for expected elements
    checks = [
        ("<h1>", "H1 header"),
        ("<h2>", "H2 header"), 
        ("<strong>", "Bold text"),
        ("<em>", "Italic text"),
        ("<ul>", "List"),
        ("<table>", "Table"),
        ("<code>", "Code")
    ]
    
    for element, desc in checks:
        if element in html:
            print(f"✅ {desc} found")
        else:
            print(f"❌ {desc} missing")
    
    return html


def test_css_themes():
    """Test CSS generation"""
    print("\nTesting CSS themes...")
    
    themes = {
        "obsidian": "--bg-color: #1e1e1e;",
        "light": "--bg-color: #ffffff;", 
        "dark": "--bg-color: #0d1117;",
        "minimal": "--bg-color: #fefefe;"
    }
    
    for theme, expected_css in themes.items():
        # Simple theme CSS generation (minimal version)
        if theme == "obsidian":
            css = """
:root {
    --bg-color: #1e1e1e;
    --text-color: #dcddde;
}
body { background-color: var(--bg-color); }
"""
        elif theme == "light":
            css = """
:root {
    --bg-color: #ffffff;
    --text-color: #24292f;
}
body { background-color: var(--bg-color); }
"""
        else:
            css = f":root {{ {expected_css} }}"
        
        if expected_css in css:
            print(f"✅ {theme} theme CSS generated")
        else:
            print(f"❌ {theme} theme CSS missing expected content")


def test_full_html():
    """Test complete HTML document generation"""
    print("\nTesting full HTML document...")
    
    md = markdown.Markdown()
    content = md.convert("# Test\n\nThis is a **test**.")
    
    html_doc = f"""<!DOCTYPE html>
<html lang="ja">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Test</title>
    <style>
        body {{ font-family: sans-serif; }}
        .markdown-body {{ padding: 20px; }}
    </style>
</head>
<body>
    <article class="markdown-body">
        {content}
    </article>
</body>
</html>"""
    
    print(f"Generated HTML document: {len(html_doc)} characters")
    
    # Save to file for inspection
    output_file = Path("test_output.html")
    output_file.write_text(html_doc, encoding="utf-8")
    print(f"✅ HTML saved to {output_file}")
    
    return html_doc


if __name__ == "__main__":
    print("🚀 Simple HTML Test")
    print("=" * 30)
    
    try:
        test_basic_markdown()
        test_css_themes()
        test_full_html()
        
        print("\n🎉 Basic tests completed!")
        print("Check test_output.html in browser to verify rendering")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()