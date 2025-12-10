# ferrisetw 技術調査レポート

**調査日**: 2025-12-10
**調査者**: Claude Code
**関連Issue**: #22

## 1. 概要

本レポートは、PyETWkitの開発にあたり、既存のRust ETWライブラリ「ferrisetw」の活用可能性を調査した結果をまとめたものである。

## 2. ferrisetw について

### 2.1 基本情報

| 項目 | 内容 |
|------|------|
| 名称 | ferrisetw |
| バージョン | 1.2.0 |
| ライセンス | MIT OR Apache-2.0 |
| Rustエディション | 2018 |
| リポジトリ | https://github.com/n4r1b/ferrisetw |
| ドキュメント | https://docs.rs/ferrisetw |
| 起源 | KrabsETW (Microsoft C++ライブラリ) のRust実装 |

### 2.2 主要機能

ferristwは以下の機能を提供する：

1. **ETWセッション管理**
   - `UserTrace`: ユーザーモードプロバイダーのリアルタイムトレース
   - `KernelTrace`: カーネルモードプロバイダーのトレース
   - `FileTrace`: ETLファイルからのイベント読み込み

2. **プロバイダー管理**
   - GUIDまたは名前によるプロバイダー指定
   - 複数プロバイダーの同時有効化
   - フィルター設定（キーワード、レベル等）

3. **イベント処理**
   - コールバックベースのイベント受信
   - `Parser`による型安全なプロパティ解析
   - `SchemaLocator`によるスキーマキャッシング

4. **TDH API統合**
   - イベントスキーマの自動解決
   - プロパティ名と型の動的取得

### 2.3 依存関係

```toml
[dependencies]
windows = "0.61"        # Win32 API バインディング
memoffset = "0.9"       # メモリオフセット計算
rand = "~0.8.0"         # 乱数生成
once_cell = "1.14"      # 遅延初期化
num = "0.4"             # 数値型ユーティリティ
bitflags = "1.3.2"      # ビットフラグ操作
widestring = "1.0"      # ワイド文字列処理
zerocopy = "0.7"        # ゼロコピーシリアライズ
log = "0.4"             # ログ出力

# オプション
time = "0.3"            # 日時処理 (feature: time_rs)
serde = "1.0"           # シリアライズ (feature: serde)
```

### 2.4 API設計

#### 基本的な使用パターン

```rust
use ferrisetw::prelude::*;
use ferrisetw::provider::Provider;
use ferrisetw::trace::UserTrace;

// コールバック定義
fn process_callback(record: &EventRecord, schema_locator: &SchemaLocator) {
    let schema = schema_locator.event_schema(record).unwrap();
    let parser = Parser::create(record, &schema);

    // プロパティの型安全な取得
    let process_id: u32 = parser.try_parse("ProcessId").unwrap();
    println!("ProcessId: {}", process_id);
}

// プロバイダー設定
let provider = Provider::by_guid("22fb2cd6-0e7b-422b-a0c7-2fad1fd0e716")
    .add_callback(process_callback)
    .build();

// トレース実行
let trace = UserTrace::new()
    .named("MyTrace".to_string())
    .enable(provider)
    .start_and_process()
    .unwrap();

// 停止
trace.stop().unwrap();
```

## 3. 他の選択肢との比較

### 3.1 比較対象

| ライブラリ | 言語 | 状態 | 特徴 |
|-----------|------|------|------|
| ferrisetw | Rust | 活発 | windows-rs使用、型安全 |
| KrabsETW | C++ | 活発 | Microsoft公式、.NET対応 |
| pywintrace | Python | 停滞(2023) | ctypes直接使用 |
| pyetw | Python/C++ | アーカイブ(2019) | KrabsETW依存 |
| windows-rs直接 | Rust | 活発 | 最大の自由度 |

### 3.2 詳細比較

#### ferrisetw vs windows-rs直接使用

| 観点 | ferrisetw | windows-rs直接 |
|------|-----------|----------------|
| 開発速度 | **高** - 抽象化済み | 低 - 低レベルAPI |
| 学習コスト | **低** - 例が豊富 | 高 - ETW知識必須 |
| カスタマイズ性 | 中 | **高** |
| バグリスク | **低** - 実績あり | 高 - 新規実装 |
| 依存関係 | 1つ追加 | **最小** |
| パフォーマンス | 同等 | **最適化可能** |
| メンテナンス | 外部依存 | **自己管理** |

#### ferrisetw vs pywintrace

| 観点 | ferrisetw + pyo3 | pywintrace |
|------|------------------|------------|
| パフォーマンス | **高** - Rust | 低 - ctypes |
| 型安全性 | **高** | 低 |
| メンテナンス | **活発** | 停滞 |
| 実装コスト | 高 - バインディング必要 | **低** - 既存 |

## 4. PyETWkitへの適合性評価

### 4.1 要件との照合

| PyETWkit要件 | ferrisetw対応 | 補足 |
|--------------|---------------|------|
| リアルタイムストリーミング | ✅ | UserTrace |
| 非同期API (asyncio) | ❌ | 要実装 |
| カーネルプロバイダー | ✅ | KernelTrace |
| ユーザープロバイダー | ✅ | UserTrace |
| フィルタリング | ✅ | Provider.add_filter() |
| プロバイダー列挙 | ❌ | 要実装 |
| スキーマ解決 | ✅ | SchemaLocator |
| ETLファイル読み込み | ✅ | FileTrace |
| Pandas/Parquetエクスポート | ❌ | 要実装 |
| 低レベルAPI公開 | △ | 部分的 |

### 4.2 不足機能

ferristwに含まれていない機能（PyETWkitで実装必要）：

1. **Python asyncio統合**
   - ferristwはコールバックベース
   - tokioとasyncioの橋渡しが必要

2. **プロバイダー列挙**
   - `TdhEnumerateProviders` API未実装
   - 別途実装が必要

3. **高レベルWrapper API**
   - イテレータベースのAPI
   - コンテキストマネージャー

4. **エクスポート機能**
   - Pandas DataFrame変換
   - Parquet/Arrow出力

### 4.3 ライセンス互換性

- ferrisetw: MIT OR Apache-2.0
- PyETWkit: MIT
- **結論**: 完全に互換性あり

## 5. アーキテクチャ案

### 5.1 ferristwラップ方式（推奨）

```
┌─────────────────────────────────────────────┐
│              Python Layer                    │
│  ┌─────────────────────────────────────┐    │
│  │  pyetwkit (High-level API)          │    │
│  │  - EtwListener (sync)               │    │
│  │  - EtwStreamer (async)              │    │
│  │  - list_providers()                 │    │
│  └─────────────────────────────────────┘    │
│                    │                         │
│  ┌─────────────────────────────────────┐    │
│  │  pyetwkit.raw (Low-level API)       │    │
│  │  - Direct ETW function access       │    │
│  └─────────────────────────────────────┘    │
└─────────────────────────────────────────────┘
                    │ pyo3
┌─────────────────────────────────────────────┐
│              Rust Layer                      │
│  ┌─────────────────────────────────────┐    │
│  │  pyetwkit-core                      │    │
│  │  - Python bindings                  │    │
│  │  - Async bridge (tokio ↔ asyncio)   │    │
│  │  - Provider enumeration             │    │
│  └─────────────────────────────────────┘    │
│                    │                         │
│  ┌─────────────────────────────────────┐    │
│  │  ferrisetw                          │    │
│  │  - ETW session management           │    │
│  │  - Event parsing                    │    │
│  │  - Schema resolution                │    │
│  └─────────────────────────────────────┘    │
└─────────────────────────────────────────────┘
                    │
┌─────────────────────────────────────────────┐
│         Windows ETW Subsystem               │
└─────────────────────────────────────────────┘
```

### 5.2 実装ロードマップ

1. **Phase 1**: ferristwをラップしたPythonバインディング
2. **Phase 2**: 高レベルAPI（EtwListener, EtwStreamer）
3. **Phase 3**: 不足機能の追加実装
4. **Phase 4**: エクスポート機能

## 6. 結論と推奨事項

### 6.1 結論

ferristwの活用は**推奨**される。理由：

1. **開発効率**: ETWの複雑な低レベル操作が抽象化済み
2. **信頼性**: KrabsETWベースで実績あり
3. **保守性**: 活発にメンテナンスされている
4. **互換性**: ライセンス、依存関係ともに問題なし

### 6.2 推奨アプローチ

**ferristwをラップする方式を採用**

- ferristwをそのまま依存関係として使用
- 不足機能（プロバイダー列挙、asyncio統合）は追加実装
- 低レベルAPIも必要に応じて直接公開

### 6.3 次のステップ

1. ADR（アーキテクチャ決定記録）の作成
2. Issue #2, #3 のRust/Python開発環境セットアップ
3. ferristwを使用したプロトタイプ作成
4. 不足機能の詳細設計

## 7. 参考リンク

- [ferrisetw GitHub](https://github.com/n4r1b/ferrisetw)
- [ferrisetw Documentation](https://docs.rs/ferrisetw)
- [KrabsETW (Microsoft)](https://github.com/microsoft/krabsetw)
- [pywintrace (FireEye)](https://github.com/fireeye/pywintrace)
- [windows-rs ETW Module](https://microsoft.github.io/windows-docs-rs/doc/windows/Win32/System/Diagnostics/Etw/index.html)
- [PyO3 User Guide](https://pyo3.rs/)
