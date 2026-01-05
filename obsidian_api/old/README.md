# AIsecretary - Obsidian Vault API

**音声入力（Siri）対応の Obsidian Vault 操作 API サーバー**

## 概要

Obsidian Vault を外部アプリから操作するための FastAPI サーバー。

**主要機能**:
- 🧠 自然言語クエリの意図推定（LLM + ルールベース）
- 🔍 ノート検索・取得・オープン
- 🎯 フォールバック制御（失敗時の自動代替実行）
- 📊 詳細ログ出力（日本語対応）

## クイックスタート

### 環境設定
```bash
# .env ファイル
VAULT_ROOT=/path/to/your/obsidian/vault
AISECRETARY_API_KEY=your-secret-key
OPENAI_API_KEY=your-openai-key
ENABLE_LLM_CLASSIFIER=1
CLASSIFIER_TYPE=auto
```

### 起動

Local

```bash
uvicorn app.main:app --host 127.0.0.1 --port 8787 --reload
```

Swagger UI: http://127.0.0.1:8787/docs
Server 

## 主要エンドポイント

### GET /assistant
**メインエンドポイント**: AI統合機能

**例**: `GET /assistant?q=部品について教えて&vault=MyVault`

**機能**:
- 意図推定（open/search/read/summarize/comment等）
- 信頼度ベースの実行制御
- 自動フォールバック
- ObsidianURL生成

### その他エンドポイント
- `GET /health` - ヘルスチェック
- `GET /files` - ファイル一覧
- `GET /search?q=キーワード` - 全文検索
- `GET /note?path=note.md` - ノート取得
- `GET /resolve?q=曖昧なクエリ` - ファイル解決

## システム構成

### Orchestrator Pattern
```
User Input → Intent Classifier → Routing → Executor → Response
                ↓
     (LLM + Rule-based)    (Fallback制御)
```

### Intent Types
- `open`: ノートを開く
- `search`: 検索実行
- `read`: 内容取得
- `summarize`: 要約
- `comment`: 解説・質問
- `table`: テーブル抽出

## 設定

### 環境変数
| Variable | 必須 | 説明 |
|----------|------|------|
| `VAULT_ROOT` | ✅ | Obsidian Vaultパス |
| `AISECRETARY_API_KEY` | ✅ | API認証キー |
| `OPENAI_API_KEY` | - | LLM機能用 |
| `ENABLE_LLM_CLASSIFIER` | - | LLM分類器有効化 |
| `CLASSIFIER_TYPE` | - | auto/rule_based/llm_based |

### 認証
```bash
curl -H "X-API-Key: your-api-key" http://127.0.0.1:8787/files
```
## Commands.yml
事前定義されたクエリ → ファイルパスのマッピング

```yaml
- name: parts
  keywords:
    - 部品
    - パーツ
    - parts
    - 部品リスト
  open:
    path: 部品.md

  open:
    path: "_special:files"  # Special handler for file listing

```

## ログ出力例
```
2025-12-29 00:00:11 - orchestrator - INFO - ✅ Open: {
  'session_id': 'session_1766934011954',
  'query': '部品 開く',
  'intent_detected': 'open',
  'confidence': 0.9,
  'success': True,
  'duration_ms': 11.3
}
```

## プロジェクト構造
```
app/
├── main.py              # FastAPI アプリ
├── intent.py            # Intent分類器（ルール）
├── llm_classifier.py    # LLM分類器
├── classifier_factory.py # A/Bテスト統合
├── routing.py           # ルーティング・フォールバック
├── logging_utils.py     # ログ機能
├── resolver.py          # クエリ解決
└── commands.py          # コマンド処理
```