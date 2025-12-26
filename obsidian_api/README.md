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

## 改訂履歴
- 2025-12-26: README 整理、改訂履歴追加。/assistant の挙動変更（plan.action 優先）を反映
- 2025-12-26: Claude 検索機能強化 - ファイル名検索追加、インテント検出優先度調整、スマートキーワード抽出実装
