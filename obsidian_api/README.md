# AIsecretary – Obsidian Vault API

Obsidian Vault を **外部（iOSショートカット・ブラウザ等）から操作するための FastAPI サーバー**。

## 概要
- Vault 内ノートを検索・取得・解決・オープンするための API を提供
- `/assistant` エンドポイントで複数機能を統合
- 音声入力（Siri / ショートカット）からの利用を想定

## 主な機能
- Markdown ファイル一覧取得
- 全文検索（grep）
- ノート本文／特定セクション取得
- 曖昧なクエリから対象ノートを解決
- `obsidian://open` URL 生成
- APIキーによる簡易認証

## 位置づけ
本プロジェクトは **「秘書AI（Siri × ChatGPT × Obsidian）」構築における実行レイヤー**を担う。
現在は `/assistant` エンドポイント内部に **Orchestrator（判断レイヤーの最小実装）** を持ち、
intent 判定・フォールバック・統合実行の入口を 1 箇所に集約している。
（※ LLM / OpenAI による高度な判断層は段階的に追加予定）

## 起動
```bash
uvicorn app.main:app --host 127.0.0.1 --port 8787 --reload
```

- Swagger UI: http://127.0.0.1:8787/docs

## テスト

### 依存関係のインストール
```bash
pip install -r requirements.txt
```

### テストの実行
```bash
# obsidian_api ディレクトリ内から実行
cd obsidian_api
python -m pytest test_api.py -v

# または、プロジェクトルートから実行
python -m pytest obsidian_api/test_api.py -v

# 特定のテストクラスのみ実行
python -m pytest test_api.py::TestFilesEndpoint -v

# 詳細出力付きで実行
python -m pytest test_api.py -v -s
```

### テスト内容
- **ヘルスチェック**: `/health` エンドポイントの動作確認
- **ファイル一覧**: `/files` でのMDファイル取得
- **検索機能**: `/search` でのテキスト検索
- **ノート取得**: `/note` での個別ノート・セクション取得
- **クエリ解決**: `/resolve` での曖昧検索
- **Obsidian連携**: `/open` でのURL生成
- **アシスタント**: `/assistant` での統合機能
- **認証テスト**: APIキー認証の検証

## APIエンドポイント詳細

### GET /health
サービスの基本的なヘルスチェック

- **認証**: 不要
- **レスポンス**: サービスステータス、バージョン、タイムスタンプ

### GET /obsidian-api/health
監視用のヘルスチェックエンドポイント

- **認証**: 不要（監視用途のため）
- **メソッド**: `GET /obsidian-api/health`
- **レスポンス**: `application/json`（キャッシュなし）

#### レスポンス例
```json
{
  "status": "ok",
  "service": "obsidian-api", 
  "version": "0.3.0",
  "time": "2025-12-26T23:59:00+09:00"
}
```

### GET /files
Vault内のMarkdownファイル一覧を取得

- **認証**: 必要（X-API-Key ヘッダー）
- **レスポンス**: Vault内の全`.md`ファイルのパス一覧

#### レスポンス例
```json
{
  "files": ["note1.md", "folder/note2.md", "物品/部品ケース１.md"]
}
```

### GET /search
Vault内の全文検索

- **認証**: 必要
- **パラメーター**:
  - `q` (required): 検索クエリ
  - `limit` (optional, default=30): 結果の上限数

#### レスポンス例
```json
{
  "q": "検索キーワード",
  "hits": [
    {
      "file": "note1.md",
      "line": 42,
      "content": "検索キーワードを含む行"
    }
  ]
}
```

### GET /note
指定したノートの内容を取得

- **認証**: 必要
- **パラメーター**:
  - `path` (required): Vault相対パス（例: "Foo/Bar.md"）
  - `section` (optional): 抽出する見出しタイトル（完全一致）
  - `with_frontmatter` (optional, default=true): フロントマターを含めるか

#### レスポンス例
```json
{
  "path": "note1.md",
  "text": "# タイトル\n\n本文内容...",
  "frontmatter": {"tags": ["tag1", "tag2"]}
}
```

### GET /resolve
曖昧なクエリから対象ノートを解決

- **認証**: 必要
- **パラメーター**:
  - `q` (required): 解決したいクエリ
  - `prefer` (optional, default="most_hits"): 優先順位ロジック

#### レスポンス例
```json
{
  "found": true,
  "source": "grep",
  "open_path": "note1.md",
  "reason": null,
  "candidates": [...]
}
```

### GET /open
Obsidianで開くためのURI生成（iOSショートカット向け）

- **認証**: 必要
- **パラメーター**:
  - `q` (required): 検索クエリ
  - `vault` (required): ObsidianのVault名
  - `prefer` (optional): 優先順位ロジック
  - `heading` (optional): 特定の見出しにジャンプ

#### レスポンス例
```json
{
  "found": true,
  "source": "grep",
  "open_path": "note1.md",
  "obsidian_url": "obsidian://open?vault=MyVault&file=note1",
  "obsidian_urls": {
    "without_md": "obsidian://open?vault=MyVault&file=note1",
    "with_md": "obsidian://open?vault=MyVault&file=note1.md"
  },
  "candidates": [...]
}
```

### GET /assistant
統合アシスタント機能（音声入力・Siri対応）

- **認証**: 必要
- **パラメーター**:
  - `q` (required): ユーザーのクエリ・音声コマンド
  - `vault` (required): ObsidianのVault名
  - `prefer` (optional): 解決の優先順位
  - `heading` (optional): 特定見出しへのジャンプ
  - `section` (optional): セクション指定

#### 機能
- Orchestrator による intent 判定（open / search / read / summarize 等）
- open 失敗時の search フォールバックなどの統合制御
- 既存 API（/open, /search, /note 等）を組み合わせた自動実行
- （将来）LLM 分類器・プランナーの段階的導入

#### レスポンス例
```json
{
  "action": "open",
  "success": true,
  "obsidian_url": "obsidian://open?vault=MyVault&file=note1",
  "user_message": "ノートを開きました",
  "data": {...}
}
```

### 認証
APIキーによる認証が必要（`/health`系エンドポイントを除く）

#### 設定方法
1. 環境変数 `AISECRETARY_API_KEY` を設定
2. リクエスト時に `X-API-Key` ヘッダーでAPIキーを送信

#### 使用例
```bash
curl -H "X-API-Key: your-api-key" http://127.0.0.1:8787/files
```

### 環境変数
- `VAULT_ROOT`: Obsidian Vaultのルートディレクトリ（default: `/srv/obsidian/Vault`）
- `AISECRETARY_API_KEY`: API認証キー
- `CORS_ORIGINS`: CORS許可オリジン（カンマ区切り、default: `*`）
- `ENABLE_LLM_PLANNER`: LLMプランナー有効化（`1`で有効）
- `OPENAI_API_KEY`: OpenAI APIキー（LLMプランナー使用時）

#### 動作確認
```bash
curl -sS http://127.0.0.1:8787/obsidian-api/health
```

期待値: JSONが返り、`status`が`"ok"`

#### 実装の注意
- DBアクセス無し（プロセス生存確認に徹する）
- リダイレクト / ログイン強制を挟まない
- nginx の location 設定で `/obsidian-api/` 配下のパス競合に注意

## 改訂履歴
- 2025-12-28: /assistant に Orchestrator クラスを導入し、判断レイヤーの入口を 1 箇所に集約
- 2025-12-26: Add /obsidian-api/health spec
- 2025-12-26: README 整理、改訂履歴追加。/assistant の挙動変更（plan.action 優先）を反映
- 2025-12-26: Claude 検索機能強化 - ファイル名検索追加、インテント検出優先度調整、スマートキーワード抽出実装
