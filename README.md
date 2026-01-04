# AIsecretary - AI-Powered Obsidian Assistant

**音声入力（Siri）対応の Obsidian Vault 操作 AI システム**

## 概要

AIsecretary は、自然言語による Obsidian Vault 操作を可能にする FastAPI サーバーです。Orchestrator パターンを採用し、音声入力からの曖昧なクエリを適切な意図に分類し、自動実行します。

### 🎯 主要機能

- **🧠 自然言語理解**: LLM + ルールベースの意図分類
- **🔍 ノート操作**: 検索・取得・オープン・要約・コメント
- **🎯 自動フォールバック**: 失敗時の代替実行
- **📊 包括的ログ**: 詳細な実行トレース
- **🔄 A/Bテスト**: 複数分類器の比較評価
- **📱 音声対応**: Siri ショートカット連携
- **🎨 HTML表示**: 美しいレスポンス表示（4テーマ対応）
- **💾 保存機能**: 結果をMarkdownファイルとして保存

## クイックスタート

### 1. 環境設定

```bash
# リポジトリをクローン
git clone <your-repo-url>
cd AIsecretary

# .env ファイルを作成
cp .env.example .env
```

**.env ファイルを編集**:
```bash
# === 必須設定 ===
# Obsidian Vault のルートディレクトリパス
VAULT_ROOT=/path/to/your/obsidian/vault

# API認証用の秘密キー（任意の文字列）
AISECRETARY_API_KEY=your-secret-api-key

# === LLM分類器設定（オプション） ===
# OpenAI APIキー（LLM機能を使用する場合）
OPENAI_API_KEY=your-openai-api-key

# LLM分類器を有効にする（1=有効, 0=無効）
ENABLE_LLM_CLASSIFIER=1

# 分類器のタイプ（auto=自動選択, rule_based=ルールのみ, llm_based=LLMのみ）
CLASSIFIER_TYPE=auto

# 使用するLLMモデル（gpt-4o-mini推奨、コスト効率良好）
LLM_CLASSIFIER_MODEL=gpt-4o-mini

# LLM分類器失敗時のルールベースフォールバック（1=有効, 0=無効）
ENABLE_CLASSIFIER_FALLBACK=1

# === HTML表示設定（オプション） ===
# デフォルトのCSSテーマ（obsidian|light|dark|minimal）
CSS_THEME=obsidian

# モバイル最適化を有効にする（iOS Safari向け、true=有効, false=無効）
MOBILE_OPTIMIZED=true

# HTML表示のフォントサイズ（pxまたはem単位）
HTML_FONT_SIZE=18px

# HTML表示の最大幅（px、%、または100%で画面幅いっぱい）
HTML_MAX_WIDTH=100%

# Markdown保存先の制限ディレクトリ（安全のため、Inboxフォルダに制限推奨）
VAULT_WRITE_ROOT=Inbox
```

### 2. 起動

```bash
# 依存関係インストール
pip install -r requirements.txt

# サーバー起動
uvicorn obsidian_api.app.main:app --host 127.0.0.1 --port 8787 --reload
```

**Swagger UI**: http://127.0.0.1:8787/docs

### 3. 基本的な使用例

```bash
# ヘルスチェック
curl "http://localhost:8787/health"

# AIアシスタント（JSON）
curl -H "X-API-Key: your-key" "http://localhost:8787/assistant?q=部品について教えて&vault=MyVault"

# AIアシスタント（HTML表示）
curl -H "X-API-Key: your-key" "http://localhost:8787/assistant?q=部品について教えて&vault=MyVault&format=html&css_theme=obsidian&mobile=true"
```

## システムアーキテクチャ

### Orchestrator パターン
```
[ User Input ]
      │
      ▼
[ Intent Classification ]  LLM + Rule-based
      │ (intent, confidence)
      ▼
[ Routing Policy ]  信頼度ベース実行制御
      │
      ├─ High Confidence (≥0.8) → 即実行
      ├─ Medium Confidence (≥0.5) → 実行 + フォールバック準備
      └─ Low Confidence (<0.5) → 聞き返し
      ▼
[ Execution Engine ]  既存API実行
      │
      ▼
[ Response Builder ]  結果構築 + HTML変換
```

### 意図分類（Intent Classification）

#### 8つの Intent
| Intent | 機能 | 例 |
|--------|------|-----|
| `open` | ノートを開く | "部品を開いて" |
| `search` | ノートを探す | "ダイオードを検索" |
| `read` | 内容を読む | "部品の内容を教えて" |
| `summarize` | 要約する | "部品ノートをまとめて" |
| `comment` | 解説・分析 | "部品について説明して" |
| `update` | 追記案作成 | "部品に情報を追加" |
| `table` | テーブル抽出 | "部品の表を表示" |
| `unknown` | 判定不能 | 曖昧な入力 |

## API エンドポイント

### メインエンドポイント

#### `GET /assistant`
**AI統合機能** - メインエントリーポイント

**パラメータ**:
- `q` (required): クエリ文字列
- `vault` (required): Vault名
- `prefer`: 検索モード (`most_hits`, `highest_score`)
- `heading`: 特定見出し指定
- `section`: 特定セクション指定
- `format`: レスポンス形式 (`json`|`html`)
- `css_theme`: HTMLテーマ (`obsidian`|`light`|`dark`|`minimal`)
- `mobile`: モバイル最適化 (`true`|`false`)

**使用例**:
```bash
# JSONレスポンス（デフォルト）
curl -H "X-API-Key: your-key" \
  "http://localhost:8787/assistant?q=部品について教えて&vault=MyVault"

# HTMLレスポンス（iOS Shortcuts向け）
curl -H "X-API-Key: your-key" \
  "http://localhost:8787/assistant?q=部品について教えて&vault=MyVault&format=html&css_theme=obsidian&mobile=true"

# 検索結果をHTML表示
curl -H "X-API-Key: your-key" \
  "http://localhost:8787/search?q=ダイオード&format=html&css_theme=light"
```

**JSONレスポンス例**:
```json
{
  "action": "comment",
  "success": true,
  "intent": "comment",
  "confidence": 0.85,
  "routing_reason": "High confidence execution",
  "user_message": "部品に関する情報をお伝えします...",
  "session_id": "sess_20251203_154523_abc123",
  "total_duration_ms": 245.3
}
```

### 補助エンドポイント

#### `GET /health`
ヘルスチェック（認証不要）

#### `GET /obsidian-api/health`
詳細ヘルスチェック（認証不要）

#### `GET /files`
ファイル一覧取得（認証必要）
- `format`: レスポンス形式 (`json`|`html`)
- `css_theme`: HTMLテーマ（format=html時）
- `mobile`: モバイル最適化（format=html時）

#### `GET /search`
全文検索（認証必要）
- `q`: 検索クエリ
- `vault`: Vault名
- `format`: レスポンス形式 (`json`|`html`)
- `css_theme`: HTMLテーマ（format=html時）
- `mobile`: モバイル最適化（format=html時）

#### `GET /note`
ノート取得（認証必要）
- `path`: ノートパス
- `section`: セクション名（オプション）
- `format`: レスポンス形式 (`json`|`html`)
- `css_theme`: HTMLテーマ（format=html時）
- `mobile`: モバイル最適化（format=html時）

#### `GET /resolve`
曖昧解決・候補生成（認証必要）
- `q`: クエリ
- `format`: レスポンス形式 (`json`|`html`)
- `css_theme`: HTMLテーマ（format=html時）
- `mobile`: モバイル最適化（format=html時）

#### `GET /open`
Obsidian URL生成（認証必要）

### HTML表示専用エンドポイント

#### `POST /render_html`
任意のMarkdownをHTML変換（認証必要）
```bash
curl -X POST -H "X-API-Key: your-key" -H "Content-Type: application/json" \
  "http://localhost:8787/render_html" \
  -d '{"markdown": "# Test\n\nThis is **bold**.", "css_theme": "obsidian", "mobile": true}'
```

#### `GET /view_html`
特定MarkdownファイルのHTML表示（認証必要）
```bash
curl -H "X-API-Key: your-key" \
  "http://localhost:8787/view_html?path=部品.md&css_theme=light&mobile=true"
```

#### `POST /save_md`
MarkdownコンテンツをVaultに保存（認証必要）
```bash
curl -X POST -H "X-API-Key: your-key" -H "Content-Type: application/json" \
  "http://localhost:8787/save_md" \
  -d '{"path": "output.md", "content": "# 保存内容", "overwrite": true}'
```

## 🎨 HTML表示テーマ

### 利用可能テーマ

#### 🌙 Obsidian（デフォルト）
- **特徴**: ダークグレー背景、紫アクセント
- **用途**: Obsidian ユーザー向け、夜間使用
- **設定**: `css_theme=obsidian`

#### ☀️ Light  
- **特徴**: 白背景、GitHub風デザイン
- **用途**: 日中使用、プレゼンテーション
- **設定**: `css_theme=light`

#### 🌃 Dark
- **特徴**: 黒背景、青アクセント  
- **用途**: 目に優しいダークモード
- **設定**: `css_theme=dark`

#### ✨ Minimal
- **特徴**: シンプル、セリフフォント
- **用途**: 読みやすさ重視、印刷向け
- **設定**: `css_theme=minimal`

### モバイル最適化

**モバイル最適化効果:**
- 📱 大きめフォント（18px）
- 👆 タッチしやすいリンク（44px最小）
- 📐 横スクロール防止
- 🔄 iOS Safari特別対応

```bash
# モバイル最適化 ON（iOS推奨）
curl "http://localhost:8787/assistant?q=部品&vault=MyVault&format=html&mobile=true"

# デスクトップ表示
curl "http://localhost:8787/assistant?q=部品&vault=MyVault&format=html&mobile=false"
```

## 📱 iOS Shortcuts での使用

### 基本ワークフロー

1. **ショートカット作成**
   - 「URLの内容を取得」アクション
   - URL: `http://localhost:8787/assistant?q=[音声入力]&vault=MyVault&format=html&css_theme=obsidian&mobile=true`
   - ヘッダー: `X-API-Key: your-secret-key`

2. **表示**
   - 「Webページを表示」アクション

### 推奨設定

```
URL: http://localhost:8787/assistant
パラメータ:
  q: [ショートカット入力]  
  vault: MyVault
  format: html
  css_theme: obsidian
  mobile: true
ヘッダー:
  X-API-Key: your-secret-key
```

### 音声コマンド例

- **「部品を開いて」** → ノートオープン（HTML表示）
- **「ダイオードを検索」** → 検索結果（HTML表示）
- **「部品について教えて」** → AI解説（HTML表示）

## 分類器比較

### Rule-based（ルールベース）
- **速度**: 高速（~0.1ms）
- **精度**: シンプルなパターンに最適
- **コスト**: 無料
- **用途**: 明確なコマンド

### LLM-based（LLM）
- **速度**: 中程度（~200ms）
- **精度**: 複雑な自然言語に強い
- **コスト**: API利用料
- **用途**: 曖昧・複雑なクエリ

### Auto（自動選択）
クエリの複雑さに応じて自動選択

## フォールバック戦略

| 元 Intent | フォールバック先 | 条件 |
|-----------|------------------|------|
| open | search | ノートが見つからない |
| read | search | 読み込み失敗 |
| summarize | read | 要約対象不明確 |
| comment | read | コメント対象不明確 |
| update | read | 更新対象不明確 |

## 認証

全ての保護されたエンドポイントには `X-API-Key` ヘッダーが必要：
```bash
curl -H "X-API-Key: your-secret-key" "http://localhost:8787/files?vault=MyVault"
```

## テスト

```bash
# 基本テスト
python -m pytest obsidian_api/test_api.py -v

# Intent分類器テスト  
python obsidian_api/test_intent_classifier.py

# Phase 2機能テスト
python obsidian_api/test_phase2.py

# HTML表示機能テスト
python obsidian_api/test_html_features.py

# 簡易HTML動作確認
python simple_html_test.py

# オーケストレーター統合テスト
python obsidian_api/test_orchestrator_flow.py
```

### HTML表示テスト

```bash
# 各テーマでのHTML生成テスト
python obsidian_api/test_html_features.py

# サンプルHTML生成（ブラウザ確認用）
ls test_output/*.html
```

## 実装フェーズ

### ✅ Phase 1（完了済み）
**Orchestrator 基盤構築**

- **IntentClassifier**: ルールベース意図分類 + 信頼度
- **RoutingPolicy**: 実行方針決定 + フォールバック制御
- **ClarificationGenerator**: 聞き返し質問生成
- **AssistantOrchestrator**: 統合制御クラス
- **自動フォールバック**: open → search 等
- **構造化レスポンス**: 評価・改善基盤

### ✅ Phase 2（完了済み）
**LLM統合 & 高度ログ**

- **LLMIntentClassifier**: OpenAI structured output活用
- **統合分類器**: A/Bテスト対応の統一インターフェース
- **包括的ログシステム**: ステップ別実行トレース
- **パフォーマンス計測**: 遅延・トークン使用量追跡
- **自然言語処理改善**: スペース問題解決
- **設定駆動**: 環境変数による分類器選択

### ✅ Phase 2.5（完了済み）
**HTML表示機能**

- **HtmlRenderer**: 4テーマ対応のHTML生成エンジン
- **Presenter システム**: API結果→Markdown→HTML変換パイプライン
- **format=html パラメータ**: 全エンドポイントでHTML表示対応
- **モバイル最適化**: iOS Safari向け特別チューニング
- **保存機能**: HTML表示内容をMarkdownファイルとして保存
- **設定可能**: CSS テーマ・フォントサイズ・幅などカスタマイズ

### 🚧 Phase 3（将来予定）
**高度機能拡張**

- **update実装**: 実際のノート更新機能
- **provenance**: 根拠提示機能
- **Multi-turn conversation**: 複数ターン対話
- **Personalization**: ユーザー学習機能
- **State management**: セッション状態保持
- **PDF エクスポート**: `format=pdf` パラメータ
- **自動デバイス検出**: User-Agent による最適化

## ログ例

```
============================================================
🤖 ORCHESTRATOR EXECUTION LOG
============================================================
📅 Time: 2025-12-28T20:45:23.123456
🔍 Query: '部品を開いて'
⏱️  Total Duration: 347.8ms

🧠 CLASSIFICATION (gpt-4o-mini)
   Intent: open (confidence: 0.95)
   Extracted Note: '部品'
   LLM Latency: 245.1ms

🎯 ROUTING
   Action: execute
   Reason: High confidence execution

⚡ EXECUTION STEPS
   1. ✅ Intent Classification (2.1ms)
   2. ✅ Routing Decision (0.3ms)  
   3. ✅ Execute Intent (100.4ms)

📊 RESULTS
   Final Action: open
   Success: ✅ Yes
   Result Type: obsidian_open
   Obsidian URL: obsidian://open?vault=MyVault&file=部品
   User Message: 'ノートを開きました'
```

## 技術スタック

- **FastAPI**: Web フレームワーク
- **Pydantic**: データ検証
- **OpenAI API**: LLM分類器
- **Python Markdown**: HTML変換エンジン
- **YAML**: 設定管理
- **pytest**: テストフレームワーク

## プロジェクト構造

```
AIsecretary/
├── .env.example                    # 環境変数サンプル
├── requirements.txt                # 依存関係
├── README.md                       # このファイル
├── simple_html_test.py             # 簡易HTML動作テスト
└── obsidian_api/
    ├── app/
    │   ├── main.py                 # FastAPI アプリケーション
    │   ├── config.py               # 設定管理
    │   ├── intent.py               # ルールベース意図分類器
    │   ├── llm_classifier.py       # LLM意図分類器
    │   ├── classifier_factory.py   # A/Bテスト統合
    │   ├── routing.py              # ルーティング・フォールバック
    │   ├── logging_utils.py        # ログ機能
    │   ├── resolver.py             # クエリ解決
    │   ├── assistant_logic.py      # アシスタントロジック
    │   ├── presentation/           # HTML表示機能
    │   │   ├── html_renderer.py    # HTML生成エンジン
    │   │   └── presenters.py       # データ→Markdown変換
    │   ├── search.py               # 検索機能
    │   ├── vault.py                # Vault操作
    │   └── security.py             # 認証機能
    ├── test_*.py                   # 各種テストファイル
    └── Doccuments/                 # 設計ドキュメント
```

## 設計原則

1. **安全性**: LLMに全権委任せず、制御をコード側で管理
2. **再現性**: ルールベース分類による一貫した挙動
3. **評価可能性**: 信頼度・実行結果の詳細ログ
4. **拡張性**: クラス設計による将来機能追加対応
5. **後方互換性**: 既存APIとの完全互換性維持
6. **モバイルファースト**: iOS Shortcuts での使いやすさを重視

## トラブルシューティング

### よくある問題

#### 1. "Module not found" エラー
```bash
# 仮想環境をアクティベート
source .venv/bin/activate
pip install -r requirements.txt
```

#### 2. Vault が見つからない
```bash
# .env ファイルの VAULT_ROOT を確認
echo $VAULT_ROOT
ls "$VAULT_ROOT"  # ファイルが存在するか確認
```

#### 3. API キーエラー
```bash
# .env ファイルの API キー設定を確認
echo $AISECRETARY_API_KEY
```

#### 4. LLM 分類器が動かない
```bash
# OpenAI API キーを確認
echo $OPENAI_API_KEY
# LLM 分類器を無効にして確認
ENABLE_LLM_CLASSIFIER=0 uvicorn obsidian_api.app.main:app --reload
```

---

**作成**: 2025-12-28  
**最終更新**: 2025-12-28  
**バージョン**: 0.4.0  
**ステータス**: Phase 2.5 完了済み（HTML表示機能追加）

### 🎯 主な改善点

- ✅ **iOS Shortcuts 最適化**: 美しいHTML表示で音声アシスタント体験向上
- ✅ **4テーマ対応**: Obsidian / Light / Dark / Minimal
- ✅ **モバイル特化**: iOS Safari向け特別チューニング
- ✅ **保存機能**: 表示内容をMarkdownファイルとして安全保存
- ✅ **統一インターフェース**: 全エンドポイントで `format=html` 対応
- ✅ **包括的ドキュメント**: 詳細な設定方法と使い方ガイド

AIsecretary がより使いやすく、より美しく進化しました！🚀