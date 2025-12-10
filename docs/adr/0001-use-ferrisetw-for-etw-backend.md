# ADR-0001: ETWバックエンドにferristwを採用

## ステータス

**採用** (2025-12-10)

## コンテキスト

PyETWkitは、PythonからWindows ETW (Event Tracing for Windows) を利用するためのツールキットである。
ETWの実装にはRustバックエンドを使用する方針であり、以下の選択肢を検討した：

1. **ferristwをラップする** - 既存のRust ETWライブラリを活用
2. **ferristwをフォーク** - カスタマイズのためにフォーク
3. **ferristwを参考に独自実装** - 参考にしつつゼロから実装
4. **windows-rsを直接使用** - 低レベルAPIから全て自前実装

## 決定

**選択肢1: ferristwをラップする方式を採用する**

ferrisetw v1.2.0 を依存関係として使用し、その上にPythonバインディングと追加機能を構築する。

## 根拠

### 採用理由

1. **開発効率の向上**
   - ETWの複雑な低レベル操作（StartTrace, ProcessTrace, EnableTraceEx2等）が既に抽象化されている
   - スキーマ解決（TDH API）も実装済み
   - 推定開発期間を50%以上短縮可能

2. **信頼性**
   - MicrosoftのKrabsETWをベースにした設計
   - 実運用での実績がある
   - テストとサンプルコードが充実

3. **技術的適合性**
   - windows-rs (v0.61) を使用しており、PyETWkitの方針と一致
   - MIT OR Apache-2.0 ライセンスで完全に互換
   - Rustエディション2018で現代的

4. **コミュニティ**
   - GitHubで79スター、34フォーク
   - 継続的なメンテナンス

### 却下した選択肢

#### フォーク方式
- メンテナンス負荷が増大
- 上流の更新を追従する作業が発生
- ferristwの変更が必要な箇所が少ない

#### 独自実装方式
- 開発期間が大幅に増加
- ETWの複雑さによるバグリスク
- 既存の良いソリューションを再発明することになる

#### windows-rs直接方式
- 学習コストが高い
- 低レベル過ぎて生産性が低下
- カスタマイズ性の利点は現時点で必要ない

## 影響

### 正の影響

- コア機能の迅速な実装が可能
- 既存のETW専門知識を活用できる
- メンテナンス負荷の軽減

### 負の影響

- 外部依存関係が1つ増加
- ferristwの設計に一部制約される
- ferristwにない機能は追加実装が必要

### 追加実装が必要な機能

1. **Python asyncio統合**
   - ferristwはコールバックベース
   - tokioとasyncioのブリッジを実装

2. **プロバイダー列挙 (`TdhEnumerateProviders`)**
   - ferristwに未実装
   - windows-rsで直接実装

3. **高レベルPython API**
   - `EtwListener` (同期イテレータ)
   - `EtwStreamer` (非同期イテレータ)

4. **低レベルAPI公開**
   - ferristwの機能を直接公開
   - 追加のWindows API公開

## 技術仕様

### 依存関係

```toml
[dependencies]
ferrisetw = "1.2"
pyo3 = "0.22"
tokio = { version = "1", features = ["rt-multi-thread", "sync"] }
```

### アーキテクチャ

```
Python API (pyetwkit)
       │
       ▼
pyo3 bindings (pyetwkit-core)
       │
       ├── ferrisetw (ETW core)
       └── windows-rs (追加API)
       │
       ▼
Windows ETW Subsystem
```

## 代替案

将来的にferristwの制限が問題になった場合：

1. ferristwにPRを送り機能追加を提案
2. 特定機能のみwindows-rsで直接実装
3. 最終手段としてフォーク

## 関連ドキュメント

- [ferrisetw技術調査レポート](../research/ferrisetw-evaluation.md)
- [Issue #22: ferrisetw活用の検討](https://github.com/m96-chan/PyETWkit/issues/22)

## 注記

本決定は、プロジェクト初期段階での技術選定である。
プロジェクトの進行に伴い、必要に応じて見直しを行う。
