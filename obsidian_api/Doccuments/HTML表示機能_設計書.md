# HTML表示機能設計書（AIsecretary 拡張）

**作成日**: 2025年12月28日  
**ステータス**: ✅ Phase 1 実装完了  
**実装方式**: format=html パラメータ採用

---

## 1. 目的

AIsecretary の各種APIの結果（検索結果、ノート内容、アシスタント応答など）を、**iOS Shortcuts / Mac ブラウザで読みやすく表示**する。

### 主要機能
- **HTML表示**: CSS内蔵の自己完結HTML生成
- **Markdown保存**: 表示内容をVaultに保存（新規/完全上書きのみ）
- **テーマ対応**: 4種類のCSS テーマ（Obsidian/Light/Dark/Minimal）
- **モバイル最適化**: iOS Safari 特別チューニング

---

## 2. 実装スコープ

### ✅ Phase 1（完了済み）
- **HtmlRenderer**: CSS内蔵のHTML生成エンジン
- **format=html パラメータ**: 全エンドポイントでHTML表示対応
- **コアエンドポイント**: `/render_html`, `/view_html`
- **保存機能**: `/save_md` with Inbox制限

### 🚫 対象外
- 既存Markdownへの追記・差分更新・部分置換
- 権限の細分化（read/write key分離）
- 高度なテンプレート・ユーザー管理

---

## 3. 使用方法

### 3.1 iOS Shortcuts
**基本ワークフロー:**
1. 「URLの内容を取得」→ `format=html&mobile=true` 指定
2. 「Webページを表示」

**推奨URL例:**
```
http://localhost:8787/assistant?q=[音声入力]&vault=MyVault&format=html&css_theme=obsidian&mobile=true
```

### 3.2 Mac ブラウザ
- ブラウザで直接 HTML エンドポイントにアクセス
- curl でHTMLを取得して確認

---

## 4. API設計

### 4.1 既存エンドポイントの拡張

**✅ 実装済み - format パラメータ方式を採用**

| エンドポイント | format=html対応 | 表示内容 |
|---------------|----------------|----------|
| `GET /assistant` | ✅ | AI応答 → Markdown整形 → HTML |
| `GET /search` | ✅ | 検索結果 → Markdown表 → HTML |
| `GET /files` | ✅ | ファイル一覧 → Markdown表 → HTML |
| `GET /note` | ✅ | ノート本文 → HTML |
| `GET /resolve` | ✅ | 解決候補 → Markdown表 → HTML |

**共通パラメータ:**
- `format`: `json`（デフォルト）| `html`
- `css_theme`: `obsidian`（デフォルト）| `light` | `dark` | `minimal`  
- `mobile`: `true` | `false`（モバイル最適化）

### 4.2 コアエンドポイント

#### ✅ `POST /render_html`
任意のMarkdownをHTML変換
```bash
curl -X POST "/render_html" \
  -d '{"markdown": "# Test", "css_theme": "obsidian", "mobile": true}'
```

#### ✅ `GET /view_html` 
特定MarkdownファイルのHTML表示
```bash
curl "/view_html?path=note.md&css_theme=light&mobile=true"
```

#### ✅ `POST /save_md`
Markdownコンテンツを保存（Inbox制限付き）
```bash
curl -X POST "/save_md" \
  -d '{"path": "output.md", "content": "# Content", "overwrite": true}'
```

---

## 5. 認証

**統一認証**: 既存 X-API-Key ヘッダーを全機能で共用
```bash
curl -H "X-API-Key: your-key" "/assistant?format=html"
```

---

## 6. アーキテクチャ

### 6.1 レンダリングパイプライン
```
API結果 → Presenter → Markdown → HtmlRenderer → HTML
```

### 6.2 実装済みクラス

#### **HtmlRenderer** (`app/presentation/html_renderer.py`)
- CSS内蔵HTML生成
- 4テーマ対応（Obsidian/Light/Dark/Minimal）
- モバイル最適化CSS

#### **Presenter群** (`app/presentation/presenters.py`)
- `FilesPresenter`: ファイル一覧 → Markdown表
- `SearchPresenter`: 検索結果 → Markdown
- `AssistantPresenter`: AI応答 → 構造化Markdown
- `NotePresenter`: ノート内容 → Markdown
- `ResolvePresenter`: 候補一覧 → Markdown

### 6.3 設定システム
**環境変数:**
```bash
CSS_THEME=obsidian              # デフォルトテーマ
MOBILE_OPTIMIZED=true           # モバイル最適化
HTML_FONT_SIZE=18px             # フォントサイズ
HTML_MAX_WIDTH=100%             # 最大幅
VAULT_WRITE_ROOT=Inbox          # 保存先制限
```

---

## 7. 安全設計

### 7.1 保存制限
- **拡張子制限**: `.md` ファイルのみ
- **パス制限**: Vault配下のみ（パストラバーサル禁止）
- **書き込み制限**: `VAULT_WRITE_ROOT=Inbox` で安全領域に限定

### 7.2 上書き制御
- `overwrite=true`: 既存ファイル上書き許可
- `overwrite=false`: 既存ファイル保護

---

## 8. テーマシステム

### 8.1 利用可能テーマ

| テーマ | 特徴 | 用途 |
|-------|------|------|
| **obsidian** | ダークグレー背景、紫アクセント | Obsidianユーザー、夜間 |
| **light** | 白背景、GitHub風 | 日中使用、プレゼン |
| **dark** | 黒背景、青アクセント | ダークモード |
| **minimal** | シンプル、セリフフォント | 読みやすさ重視 |

### 8.2 モバイル最適化
- 📱 大きめフォント（18px）
- 👆 タッチしやすいリンク（44px最小）
- 📐 横スクロール防止
- 🔄 iOS Safari 特別対応

---

## 9. ログ・監視

**最小ログ仕様:**
- HTMLエンドポイント呼び出し記録
- 処理時間測定  
- 保存操作（パス・サイズ・成功/失敗）

**実装**: 既存 `logging_utils.py` との統合

---

## 10. 実装完了サマリー

### ✅ 完了項目
1. **HtmlRenderer クラス**: 4テーマ対応のHTML生成エンジン
2. **Presenter システム**: API結果→Markdown変換パイプライン  
3. **format=html パラメータ**: 全エンドポイントでHTML表示対応
4. **コアエンドポイント**: `/render_html`, `/view_html`, `/save_md`
5. **設定システム**: 環境変数による柔軟なカスタマイズ
6. **安全保存**: Inbox制限・上書き制御
7. **テスト**: 基本動作確認完了

### 🎯 品質向上効果
- **iOS Shortcuts UX**: 美しいHTML表示で音声アシスタント体験大幅向上
- **テーマ対応**: 用途に応じた4種類の表示スタイル
- **モバイル最適化**: iOS Safari向け特別チューニング  
- **安全性**: 事故防止を考慮した保存制限
- **拡張性**: 将来のPDF化・カスタムテーマ追加に対応

---

## 11. 設計決定事項

### 採用方針
- ✅ **format パラメータ方式**: `*_html` エンドポイント増加を避け、統一的なインターフェース
- ✅ **表示パイプライン統一**: 「API結果 → Markdown → HTML」の一貫した流れ
- ✅ **CSS内蔵**: 自己完結HTMLでデプロイ・配布が簡単
- ✅ **既存API互換性**: 従来の JSON レスポンスを完全維持
- ✅ **安全第一**: 保存機能は制限付きで事故防止

### 技術選択
- **Python Markdown**: 高機能で拡張性の高いHTML変換
- **CSS Variables**: 動的テーマ切り替えとカスタマイズ対応
- **モバイルファースト**: iOS Shortcuts の主要ユースケースを優先

### 将来拡張予定
- **自動デバイス検出**: User-Agent による最適化
- **PDF エクスポート**: `format=pdf` パラメータ
- **カスタムテーマ**: ユーザー定義CSS
- **プレビューURL**: 認証なし一時表示

---

**Phase 1 の成功により、AIsecretary の実用性と美しさが大幅に向上しました。** 🎉

特に iOS Shortcuts での音声操作体験が格段に改善され、美しくフォーマットされた結果を簡単に閲覧できるようになりました。