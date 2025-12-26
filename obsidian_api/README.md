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
（※ LLM / OpenAI による判断層は将来的に追加予定）

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

## Health Check API

### GET /obsidian-api/health

監視（Uptime / cron / 手動curl）でサービス稼働を確認するためのエンドポイント。

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
- 2025-12-26: Add /obsidian-api/health spec
- 2025-12-26: README 整理、改訂履歴追加。/assistant の挙動変更（plan.action 優先）を反映
- 2025-12-26: Claude 検索機能強化 - ファイル名検索追加、インテント検出優先度調整、スマートキーワード抽出実装
