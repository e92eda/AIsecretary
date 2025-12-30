# FuturePlan — Orchestrator方式でAI秘書を設計する（設計ドキュメント）

作成日: 2025-12-28（Asia/Tokyo）

---

## 0.1 現状エンドポイントとの整合性チェック（README基準）

結論：  
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

## 2.1 クラス導入方針（Phase 1 実装完了）

本プロジェクトでは、判断レイヤーを段階的に明確化するため、**Orchestrator をクラスとして導入**し、**Phase 1 の実装が完了**した。
これは将来的な LLM 導入を見据えた **最小限かつ後方互換な設計**である。

### ✅ Phase 1 で実装済みのクラス構成

- **AssistantOrchestrator** (`app/main.py`)  
  `/assistant` エンドポイントの唯一の入口となるクラス。
  Intent分類、ルーティング、実行、フォールバックの全体制御を担う。

- **IntentClassifier** (`app/intent.py`)  
  ルールベースの意図分類器。信頼度スコア付きで intent を判定する。
  Phase 2 で LLM 分類器に差し替え可能なインターフェースを提供。

- **RoutingPolicy** (`app/routing.py`)  
  信頼度に基づく実行方針決定（execute/fallback/clarify/reject）。
  open → search フォールバックなどの戦略を実装。

- **ClarificationGenerator** (`app/routing.py`)  
  曖昧な意図に対する聞き返し質問の生成機能。

### 実装済み機能

#### Intent Classification
- 信頼度スコア（0.0-1.0）付きの分類
- 8つの Intent：open, search, read, summarize, comment, update, table, unknown
- エンティティ抽出（query, note, section, vault）
- 既存コードとの後方互換性維持

#### Routing Policy  
- 高信頼度（≥0.8）：即座に実行
- 中信頼度（≥0.5）：実行 + フォールバック準備
- 低信頼度（<0.5）：clarification（聞き返し）

#### Fallback Strategy
- open → search（ノートが見つからない場合）
- read → search（読み込み失敗時）
- summarize → read（要約対象が不明確な場合）

#### Error Handling & Logging
- 実行結果の詳細ログ
- 信頼度・フォールバック理由の記録
- ユーザーフレンドリーなメッセージ生成

### 設計上の原則（実証済み）

- ✅ Orchestrator は「判断」までを担当し、実処理は既存 API / 関数に委譲
- ✅ クラス導入は **挙動を変えず、構造のみを整理する目的**で実装
- ✅ 既存の `handle_assistant_query()` との完全互換性を維持
- ✅ テスト時に各クラスを単体で差し替え・検証可能

## 3. Intent 設計（最小固定セット）

### 3.1 Intent 一覧（✅ 実装済み）

| intent | 意味 | 実装状況 |
|------|------|----------|
| open | ノートを開く | ✅ 実装済み |
| search | 探す / 候補を出す | ✅ 実装済み |
| read | 内容を読む | ✅ 実装済み |
| summarize | 要約する | ✅ 実装済み |
| comment | 解説・比較・判断支援 | ✅ 実装済み |
| update | 追記案を作る（※実書き込みなし） | ✅ 実装済み |
| table | テーブル抽出 | ✅ 実装済み |
| unknown | 判定不能・要確認 | ✅ 実装済み |

### 3.2 Intent 出力スキーマ（✅ IntentResult クラスとして実装済み）

```json
{
  "intent": "open|search|read|summarize|comment|update|table|unknown",
  "confidence": 0.8,
  "entities": {
    "query": "ユーザーの元クエリ",
    "note": null,
    "section": null,
    "vault": null
  }
}
```

### 3.3 実装済み分類ロジック

#### 高信頼度パターン（confidence = 0.9）
- `open`: "開", "open", "表示", "開く"
- `search`: "検索", "search", "探", "さが", "見つけ"  
- `summarize`: "要約", "summary", "まとめ", "概要"
- `table`: "表", "table", "一覧", "リスト"

#### 中信頼度パターン（confidence = 0.7）
- `read`: "読", "見", "内容", "本文", "全文"

#### 低信頼度パターン（confidence = 0.6）
- `read`: "ノート", "note", "メモ", "文書"

#### 曖昧パターン（confidence = 0.5）
- `comment`: "について", "とは", "って", "どう"

---

## 4. Orchestrator の責務（✅ 実装済み）

### 4.1 実装済み機能

- ✅ intent × confidence から **実行方針を決定**（RoutingPolicy）
- ✅ open 失敗時の **search フォールバック**（自動実行）
- ✅ 曖昧時の **候補提示 or 質問生成**（ClarificationGenerator）
- ✅ 実行ログ・評価ログの生成（詳細レスポンス）

### 4.2 実装済み基本ポリシー

1. ✅ **高信頼度（≥0.8）** → 即実行  
2. ✅ **中信頼度（≥0.5）** → 実行 + フォールバック準備
3. ✅ **低信頼度（<0.5）** → clarification（短い質問）
4. ✅ **実行失敗** → 自動的にフォールバック intent を試行

### 4.3 実装済みフォールバック戦略

| 元 Intent | フォールバック先 | 実装状況 |
|-----------|------------------|----------|
| open | search | ✅ 実装済み |
| read | search | ✅ 実装済み |
| summarize | read | ✅ 実装済み |
| comment | read | ✅ 実装済み |
| update | read | ✅ 実装済み |

### 4.4 実装済みレスポンス構造

```json
{
  "action": "open|search|read|summarize|clarify|failed",
  "success": true,
  "intent": "open",
  "confidence": 0.9,
  "routing_reason": "High confidence execution",
  "user_message": "ノートを開きました",
  "obsidian_url": "obsidian://open?vault=MyVault&file=note1",
  "fallback_intent": null
}
```

---

## 5. Clarification（聞き返し）設計（✅ 実装済み）

### 5.1 実装済み Clarification レスポンス

```json
{
  "action": "clarify",
  "success": false,
  "intent": "unknown",
  "confidence": 0.0,
  "clarification": {
    "question": "「ノート」について、何をしたいですか？",
    "options": [
      {"label": "開く", "intent": "open"},
      {"label": "検索", "intent": "search"},
      {"label": "読む", "intent": "read"}
    ]
  },
  "user_message": "「ノート」について、何をしたいですか？"
}
```

### 5.2 実装済み質問生成パターン

- ✅ **UNKNOWN intent**: 汎用的な選択肢（開く/検索/読む）
- ✅ **低信頼度 OPEN**: 開く vs 検索の2択
- ✅ **低信頼度 READ**: 読む vs 要約の2択
- ✅ **選択肢は 2–3 個まで**（音声 UI / Siri 対応）
- ✅ **短い質問文**（音声インターフェース最適化）

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

### ✅ Phase 1（完了済み - 2025-12-28）
- ✅ **IntentClassifier クラス**：ルールベース intent 分類 + 信頼度
- ✅ **RoutingPolicy クラス**：実行方針決定 + フォールバック制御
- ✅ **ClarificationGenerator クラス**：聞き返し質問生成
- ✅ **AssistantOrchestrator 統合**：全体制御の入口統一
- ✅ **open → search フォールバック**：自動実行
- ✅ **詳細ログ・レスポンス構造**：評価・改善基盤

### Phase 2（次期予定）
- LLM classification 導入（IntentClassifier の差し替え）
- Advanced confidence gate（動的閾値調整）
- State management（セッション状態保持）
- Performance metrics（実行時間・成功率測定）

### Phase 3（将来予定）
- update（Patch 生成）の実装
- provenance（根拠提示）機能
- Multi-turn conversation（複数ターン対話）
- Personalization（ユーザー学習機能）

### 今後の拡張方針

Phase 1 で構築した基盤により、以下が可能：

1. **IntentClassifier の差し替え**：ルールベース → LLM ベース
2. **RoutingPolicy の拡張**：より複雑な判断ロジック
3. **新 Handler の追加**：update, comment 等の実処理
4. **テスタビリティ**：各クラスの単体テスト・A/Bテスト

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

- 2025-12-28: **Phase 1 実装完了** - IntentClassifier, RoutingPolicy, ClarificationGenerator, AssistantOrchestrator の統合実装が完了
- 2025-12-28: README と役割分担を明確化、Orchestrator 設計に特化  
- 2025-12-28: FuturePlan 内の旧API記述を削除し、READMEの現状エンドポイントに合わせて整理（/files, /note, /resolve, /open など）

## 実装完了サマリー（Phase 1）

本ドキュメントで設計した **Orchestrator 方式による AI秘書システム** の Phase 1 が完了しました。

### 達成項目
- ✅ **判断レイヤーの分離**：Intent分類、ルーティング、実行を明確に分割
- ✅ **信頼度ベースの制御**：高/中/低信頼度に応じた適切な処理
- ✅ **自動フォールバック**：失敗時の代替手段自動実行
- ✅ **聞き返し機能**：曖昧な入力に対する適切な質問生成
- ✅ **構造化ログ**：評価・改善のための詳細記録
- ✅ **後方互換性**：既存APIとの完全互換性維持

### システム品質向上
- **安全性**：LLM に全権委任せず、制御をコード側で管理
- **再現性**：ルールベースの分類による一貫した挙動
- **評価可能性**：信頼度・実行結果の詳細ログ
- **拡張性**：Phase 2 でのLLM導入に向けた基盤完成

Phase 1 の成功により、音声入力（Siri）からの曖昧なクエリに対して、適切な意図推定とフォールバック制御が実現され、ユーザーエクスペリエンスが大幅に向上しました。