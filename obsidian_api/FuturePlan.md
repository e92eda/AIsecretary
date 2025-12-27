# FuturePlan — Orchestrator方式でAI秘書を設計する（設計ドキュメント）

作成日: 2025-12-28（Asia/Tokyo）

---

## 0.1 現状エンドポイントとの整合性チェック（README基準）

結論：**現状の実装/READMEに対して、旧記述（/notes や /note/{note_path} など）は不整合**です。  
本ファイルでは以降、README に記載のエンドポイントを正とします。

### README（現状）での主要エンドポイント
- `/health`（認証不要）
- `/obsidian-api/health`（認証不要）
- `/files`（認証必要）
- `/search`（認証必要）
- `/note`（認証必要。`path` と任意で `section`）
- `/resolve`（認証必要）
- `/open`（認証必要）
- `/assistant`（認証必要）

### 旧記述で出ていたが現状と合わないもの（今後は使わない）
- `/notes`
- `/note/{note_path}`

### 推奨（現状側を直すなら）  
現状は README 側と API の命名が揃っているため、**まずは FuturePlan 側の記述を直すのが安全**です。  
もし API 側を変えるなら、互換性を壊さないように次の方針を推奨します：  
- `/notes` を追加するなら **`/files` のエイリアス**として実装（段階的移行）  
- `/note/{note_path}` を追加するなら **`/note?path=` のエイリアス**として実装  
- いずれも 1〜2リリース猶予を置き、将来 deprecated を README に明記

---

## 0. 本ドキュメントの位置づけ

- `README.md` : **実行レイヤー（FastAPI / Vault API）の仕様書**  
- `FuturePlan.md` : **判断レイヤー（Orchestrator / Intent / Policy）の設計書**

本ファイルは「何を・どの順序で・どの方針で実行するか」を決める **頭脳部分** を扱う。  
実際のファイル操作・検索・open 処理は README に記載された API が担う。

---

## 1. 目的（Why）

- ユーザー入力（音声・短文・自然文）から **意図（Intent）を推定** する  
- 適切な API（open / search / read / summarize など）へ **自動ルーティング** する  
- LLM に全権委任せず、  
  - 安全性  
  - 再現性  
  - 評価可能性  
  を担保するため **制御はコード側に置く**

---

## 2. 全体アーキテクチャ（Orchestrator Pattern）

```
[ User Input ]
      │
      ▼
[ Preprocess ]  正規化 / 言語判定 / 履歴参照
      │
      ▼
[ Intent Classifier ]  rule + optional LLM
      │  (intent, confidence)
      ▼
[ Orchestrator ]  ← 本ドキュメントの主対象
      │
      ├─ policy 判定
      ├─ fallback 制御
      └─ clarification 判定
      ▼
[ Executor ]  (README.md に定義された API)
      │
      ▼
[ Response Builder ]
```

---

## 3. Intent 設計（最小固定セット）

### 3.1 Intent 一覧

| intent | 意味 |
|------|------|
| open | ノートを開く |
| search | 探す / 候補を出す |
| read | 内容を読む |
| summarize | 要約する |
| comment | 解説・比較・判断支援 |
| update | 追記案を作る（※実書き込みなし） |
| unknown | 判定不能・要確認 |

### 3.2 Intent 出力スキーマ

```json
{
  "intent": "open|search|read|summarize|comment|update|unknown",
  "confidence": 0.0,
  "entities": {
    "query": null,
    "note": null,
    "section": null,
    "vault": null
  }
}
```

---

## 4. Orchestrator の責務（最重要）

### 4.1 やること

- intent × confidence から **実行方針を決定**  
- open 失敗時の **search フォールバック**  
- 曖昧時の **候補提示 or 質問生成**  
- 実行ログ・評価ログの生成

### 4.2 基本ポリシー

1. intent=open & confidence 高 → 即実行  
2. open 失敗 → search に自動遷移  
3. confidence 中 → 実行 + 候補提示  
4. confidence 低 → clarification（短い質問）

---

## 5. Clarification（聞き返し）設計

```json
{
  "question": "どちらですか？",
  "options": [
    {"label": "開く", "intent": "open"},
    {"label": "検索", "intent": "search"}
  ]
}
```

- 選択肢は **2–3 個まで**  
- 音声 UI / Siri でも成立する短さを優先

---

## 6. State（状態管理）

### 6.1 短期状態（セッション）

- last_intent  
- last_candidates  
- last_opened_note

### 6.2 中期状態（作業文脈）

- finding_note  
- confirming_target  
- drafting_update

---

## 7. 評価・改善のためのログ

最低限残す項目：

- user_input  
- predicted_intent  
- confidence  
- executed_action  
- fallback_reason  
- latency_ms

→ 将来的に intent 精度・UX 改善に使用

---

## 8. 実装ロードマップ

### Phase 1（現在）
- ルールベース intent  
- open → search フォールバック

### Phase 2
- LLM classification 導入（分類専用）  
- confidence gate

### Phase 3
- update（Patch 生成）  
- provenance（根拠提示）

---

## 9. README との対応関係（確認用）

| README の API | Orchestrator 側の役割 |
|-------------|----------------------|
| /open | open intent 実行（URI生成まで） |
| /resolve | open/search の前段（曖昧解決・候補生成） |
| /search | search intent 実行 / fallback |
| /note | read intent 実行（section指定含む） |
| /files | 候補生成（UI/補助） |
| /assistant | Orchestrator エントリーポイント |
| /health, /obsidian-api/health | 稼働監視（Orchestrator外） |

---

## 改訂履歴

- 2025-12-28: README と役割分担を明確化、Orchestrator 設計に特化  
- 2025-12-28: FuturePlan 内の旧API記述を削除し、READMEの現状エンドポイントに合わせて整理（/files, /note, /resolve, /open など）