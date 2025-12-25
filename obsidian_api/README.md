# AIsecretary - Obsidian Vault API (FastAPI)

# AIsecretary – Obsidian Vault API

Obsidian Vault を **外部（iOSショートカット・ブラウザ等）から操作するための FastAPI サーバー**。

## できること
- Vault 内 Markdown ファイルの一覧取得
- Vault 全体の全文検索（grep）
- ノート本文／特定セクションの取得
- 曖昧なクエリから対象ノートを解決（辞書 + 推定）
- Obsidian を開く `obsidian://open` URL の生成
- `/assistant` エンドポイントで上記処理を統合的に実行

## 想定用途
- iOS ショートカットから音声／テキスト指示でノートを開く
- Obsidian を「秘書AI」的に操作するためのバックエンド
- ローカルまたはVPS上での個人用APIサーバー

## 技術構成
- FastAPI + Uvicorn
- Markdown / YAML Frontmatter 解析
- APIキーによる簡易認証

## 起動
```bash
uvicorn app.main:app --host 127.0.0.1 --port 8787 --reload

Swagger UI:
	•	http://127.0.0.1:8787/docs
