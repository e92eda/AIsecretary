# Apple Shortcuts仕様書：AIsecretary接続ガイド

**音声アシスタント対応 Obsidian Vault 操作**  
**作成日**: 2025-01-04  
**対応バージョン**: AIsecretary v0.4.0+

---

## 概要

この仕様書では、iOS/macOS の Apple Shortcuts を使用して AIsecretary に接続し、音声入力による Obsidian Vault 操作を実現する方法を説明します。

### 🎯 実現する機能

- **音声入力**: Siri に話しかけて Obsidian を操作
- **美しい表示**: HTML 形式での結果表示（4テーマ対応）
- **モバイル最適化**: iPhone/iPad での使いやすさ
- **直感的操作**: 自然な日本語コマンド対応

---

## 前提条件

### AIsecretary サーバー側

1. **サーバー起動済み**
   ```bash
   uvicorn obsidian_api.app.main:app --host 127.0.0.1 --port 8787 --reload
   ```

2. **環境変数設定済み** (.env ファイル)
   ```env
   AISECRETARY_API_KEY=your-secret-api-key
   CSS_THEME=obsidian
   MOBILE_OPTIMIZED=true
   ```

3. **ネットワーク接続**
   - iOS デバイスと AIsecretary サーバーが同一ネットワーク上にある
   - または外部からアクセス可能な URL がある

### iOS/macOS 側

- iOS 12+ または macOS Monterey+
- Shortcuts アプリがインストール済み
- Siri が有効

---

## 基本設定

### 1. サーバー URL の確認

**ローカル環境（同一Wi-Fi内）:**
```
http://[MacのIPアドレス]:8787
```

IP アドレス確認方法:
```bash
# macOS で確認
ifconfig | grep inet
# または
ipconfig getifaddr en0
```

**外部環境（Nginx等でホスト済み）:**
```
https://your-domain.com/obsidian-api
```

### 2. API キーの確認

.env ファイルで設定した API キーを確認:
```env
AISECRETARY_API_KEY=your-secret-api-key
```

---

## ショートカットの作成

### 基本ショートカット構成

#### 1. 基本アクション設定

| アクション | 説明 |
|------------|------|
| **URLの内容を取得** | AIsecretary API を呼び出し |
| **Webページを表示** | 結果を HTML 形式で表示 |

#### 2. URL 設定

**ベース URL:**
```
http://[your-server]:8787/assistant
```

**必須パラメータ:**
```
q=[ショートカット入力]
vault=[あなたのVault名]
format=html
```

**推奨パラメータ:**
```
css_theme=obsidian
mobile=true
```

#### 3. ヘッダー設定

**必須ヘッダー:**
```
X-API-Key: your-secret-api-key
```

---

## ショートカット作成手順

### ステップ 1: 新規ショートカット作成

1. **Shortcuts アプリを開く**
2. **「+」をタップして新規作成**
3. **ショートカット名を設定** (例: "Obsidian検索")

### ステップ 2: アクション追加

#### アクション 1: テキスト入力

1. **「アクションを追加」をタップ**
2. **「テキストを入力」を検索して追加**
3. **設定:**
   - 入力タイプ: **「音声で入力」**
   - プロンプト: **「何を検索しますか？」**

#### アクション 2: URL構築

1. **「テキスト」アクションを追加**
2. **以下の URL を入力:**
```
http://192.168.1.100:8787/assistant?q=テキスト入力からの出力&vault=MyVault&format=html&css_theme=obsidian&mobile=true
```
3. **「テキスト入力からの出力」部分をタップして変数に変更**

#### アクション 3: API呼び出し

1. **「URLの内容を取得」アクションを追加**
2. **URL を前のアクションの出力に設定**
3. **ヘッダーを追加:**
   - **名前:** `X-API-Key`
   - **値:** `your-secret-api-key`

#### アクション 4: 結果表示

1. **「Webページを表示」アクションを追加**
2. **Web ページを前のアクションの出力に設定**

### ステップ 3: Siri フレーズ設定

1. **ショートカット設定ページで「Siriに追加」**
2. **音声コマンドを録音** (例: "オブシディアン検索")

---

## 複数ショートカットのテンプレート

### 1. 汎用検索ショートカット

**ショートカット名:** Obsidian検索  
**Siri フレーズ:** "オブシディアン検索"

```
URL: http://[server]:8787/assistant
パラメータ:
  q=[音声入力]
  vault=MyVault
  format=html
  css_theme=obsidian
  mobile=true
```

### 2. ノートオープンショートカット

**ショートカット名:** ノートを開く  
**Siri フレーズ:** "ノート開いて"

```
URL: http://[server]:8787/assistant
パラメータ:
  q=[音声入力]を開いて
  vault=MyVault
  format=html
  css_theme=obsidian
  mobile=true
```

### 3. ファイル一覧ショートカット

**ショートカット名:** ファイル一覧  
**Siri フレーズ:** "ファイル一覧"

```
URL: http://[server]:8787/files
パラメータ:
  vault=MyVault
  format=html
  css_theme=light
  mobile=true
```

### 4. AI要約ショートカット

**ショートカット名:** AI要約  
**Siri フレーズ:** "要約して"

```
URL: http://[server]:8787/assistant
パラメータ:
  q=[音声入力]を要約して
  vault=MyVault
  format=html
  css_theme=obsidian
  mobile=true
```

---

## 詳細パラメータ仕様

### API エンドポイント

| エンドポイント | 用途 | 主要パラメータ |
|----------------|------|----------------|
| `/assistant` | AI統合検索・操作 | q, vault, format |
| `/search` | 全文検索 | q, vault, format |
| `/files` | ファイル一覧 | vault, format |
| `/note` | 特定ノート取得 | path, format |
| `/resolve` | 曖昧解決 | q, format |

### クエリパラメータ仕様

#### 必須パラメータ

| パラメータ | 説明 | 例 |
|------------|------|-----|
| `q` | 検索・操作クエリ | `部品について教えて` |
| `vault` | Vault名 | `MyVault` |

#### フォーマットパラメータ

| パラメータ | 値 | 説明 |
|------------|-----|------|
| `format` | `json`\|`html` | レスポンス形式 |
| `css_theme` | `obsidian`\|`light`\|`dark`\|`minimal` | HTMLテーマ |
| `mobile` | `true`\|`false` | モバイル最適化 |

#### オプションパラメータ

| パラメータ | 説明 | デフォルト |
|------------|------|-----------|
| `prefer` | 検索モード | `most_hits` |
| `heading` | 特定見出し指定 | なし |
| `section` | 特定セクション指定 | なし |

### HTTPヘッダー

| ヘッダー名 | 値 | 必須 |
|------------|-----|------|
| `X-API-Key` | API認証キー | ✅ |
| `Content-Type` | `application/json` | POST時のみ |

---

## CSS テーマ仕様

### テーマ選択ガイド

#### 🌙 Obsidian Theme (`obsidian`)
- **背景**: ダークグレー (#1e1e1e)
- **文字**: 白系 (#dcddde)
- **アクセント**: 紫系
- **用途**: Obsidianユーザー、夜間使用

#### ☀️ Light Theme (`light`)
- **背景**: 白 (#ffffff)
- **文字**: 黒系 (#24292f)
- **アクセント**: 青系
- **用途**: 日中使用、プレゼン

#### 🌃 Dark Theme (`dark`)
- **背景**: 濃い青黒 (#0d1117)
- **文字**: 白系 (#f0f6fc)
- **アクセント**: 青系
- **用途**: 目に優しいダークモード

#### ✨ Minimal Theme (`minimal`)
- **背景**: オフホワイト (#fefefe)
- **文字**: 黒 (#2c3e50)
- **フォント**: セリフ系
- **用途**: 読みやすさ重視

### モバイル最適化

`mobile=true` 設定時の効果:

- **フォントサイズ**: 18px (読みやすい大きさ)
- **リンクサイズ**: 最小44px (タッチしやすい)
- **レイアウト**: 画面幅100%使用
- **スクロール**: 横スクロール防止

---

## 音声コマンド例

### 基本操作

| 音声コマンド | APIクエリ | 実行される動作 |
|-------------|-----------|----------------|
| "部品を開いて" | `部品を開いて` | ノート「部品」を開く |
| "ダイオードを検索" | `ダイオードを検索` | 全文検索実行 |
| "部品について教えて" | `部品について教えて` | AI解説・コメント |
| "部品ノートを要約" | `部品ノートを要約` | 内容要約 |

### 自然言語での複雑な操作

| 音声コマンド | Intent分類 | 動作 |
|-------------|------------|------|
| "最近追加した部品リスト" | `search` | 検索→リスト表示 |
| "LEDの仕様を詳しく" | `comment` | AI詳細解説 |
| "回路図まとめ" | `summarize` | 関連ノート要約 |

---

## エラーハンドリング

### よくあるエラーと対処法

#### 1. 認証エラー (401 Unauthorized)

**症状:** "Access denied" メッセージ

**原因:** API キーが間違っている

**対処法:**
1. ショートカットの X-API-Key ヘッダーを確認
2. .env ファイルの AISECRETARY_API_KEY を確認

#### 2. 接続エラー (Connection Failed)

**症状:** ネットワークエラーメッセージ

**原因:** サーバーに接続できない

**対処法:**
1. AIsecretary サーバーが起動しているか確認
2. URL のIPアドレス・ポート番号を確認
3. 同一ネットワークにいるか確認

#### 3. Vault Not Found エラー

**症状:** "Vault not found" メッセージ

**原因:** Vault名が間違っている

**対処法:**
1. ショートカットの vault パラメータを確認
2. 実際の Vault 名と一致しているか確認

#### 4. 空の結果

**症状:** "No results found"

**原因:** 検索条件に該当するノートがない

**対処法:**
1. より一般的な検索語を試す
2. `/files` エンドポイントでファイル一覧を確認

---

## パフォーマンス最適化

### レスポンス速度改善

#### 1. 分類器設定

```env
# 高速化のためルールベースのみ使用
CLASSIFIER_TYPE=rule_based
ENABLE_LLM_CLASSIFIER=0
```

#### 2. HTML表示の軽量化

```
# よりシンプルなテーマを使用
css_theme=minimal
```

#### 3. ネットワーク最適化

- **キープアライブ**: HTTP/1.1 持続接続使用
- **並列実行**: 複数ショートカットを非同期で実行

### モバイル向け最適化

```
# iOSでの表示最適化
mobile=true
css_theme=obsidian
```

---

## セキュリティ対策

### 1. API キー管理

**❌ 避けるべき:**
- API キーをショートカット名に含める
- 他人と API キーを共有

**✅ 推奨:**
- 複雑なランダム文字列を API キーとして使用
- 定期的な API キー変更

### 2. ネットワークセキュリティ

**ローカル環境:**
- 信頼できるWi-Fiネットワークのみで使用
- ファイアウォール設定でポート制限

**外部公開時:**
- HTTPS 必須
- IP制限やVPN使用を検討

### 3. Vault への書き込み制限

```env
# 安全な書き込み制限
VAULT_WRITE_ROOT=Inbox
```

---

## トラブルシューティング

### デバッグ手順

#### 1. 手動テスト

```bash
# cURLでの動作確認
curl -H "X-API-Key: your-key" \
  "http://192.168.1.100:8787/health"

# 基本的なクエリテスト
curl -H "X-API-Key: your-key" \
  "http://192.168.1.100:8787/assistant?q=テスト&vault=MyVault&format=html"
```

#### 2. ログ確認

```bash
# サーバーログを確認
tail -f server.log

# リアルタイムログ
uvicorn obsidian_api.app.main:app --log-level debug
```

#### 3. ショートカットデバッグ

1. **「URLの内容を取得」後に「テキストを表示」アクションを追加**
2. **生のレスポンスを確認**
3. **エラーメッセージを特定**

---

## 応用例

### 1. 定期レポート生成

**ショートカット名:** 週次レポート  
**自動実行:** 毎週月曜日朝

```
URL: http://[server]:8787/assistant
Query: 今週の進捗をまとめて
→ /save_md で結果を保存
```

### 2. 音声メモ保存

**ショートカット名:** ボイスメモ保存  
**トリガー:** "メモを残して"

```
音声入力 → テキスト変換 
→ /save_md で Inbox/memo_YYYYMMDD.md に保存
```

### 3. マルチ検索

**ショートカット名:** 横断検索  
**機能:** 複数キーワードで一括検索

```
ループ処理で複数クエリ実行
→ 結果を統合して表示
```

---

## 参考リンク

### Apple Shortcuts 公式ドキュメント

- [Shortcuts User Guide (Apple)](https://support.apple.com/guide/shortcuts/)
- [Siri Shortcuts Developer](https://developer.apple.com/siri/)

### AIsecretary 関連

- [AIsecretary API Documentation](../README.md)
- [設定ファイル例](./.env.example)
- [HTMLテーマ詳細](../obsidian_api/app/presentation/html_renderer.py)

---

## FAQ

### Q: 複数のVaultを切り替えたい

**A:** Vault別にショートカットを作成するか、入力時にVault名を指定
```
音声入力: "MyVault1 部品を検索"
→ URL パラメータで vault=MyVault1 を動的設定
```

### Q: 検索結果が表示されない

**A:** 以下を確認：
1. Vault名が正確か
2. 検索対象ファイルが存在するか  
3. ファイルに検索語が含まれているか

### Q: 音声認識精度を上げたい

**A:** 以下を試す：
1. 静かな環境で録音
2. ゆっくり明確に発音
3. 専門用語は避けて一般的な言葉を使用

### Q: カスタムテーマを作りたい

**A:** `html_renderer.py` で新しいテーマを追加可能
```python
"custom": {
    "--bg-color": "#your-color",
    "--text-color": "#your-text-color",
    # ... その他の設定
}
```

---

**作成者**: AIsecretary Team  
**最終更新**: 2025-01-04  
**バージョン**: 1.0  
**サポート**: AIsecretary v0.4.0+

---

## ライセンス・免責事項

本仕様書は AIsecretary プロジェクトの一部として提供されます。使用にあたっては、ネットワークセキュリティとプライバシー保護に十分注意してください。