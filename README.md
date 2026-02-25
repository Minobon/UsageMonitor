# Usage Monitor

Claude / Codex / Antigravity の API 使用量をデスクトップ上にリアルタイム表示する Windows 用フローティングウィジェットです。

## 機能

- **マルチサービス対応** — Claude (Anthropic)、Codex (OpenAI)、Antigravity (Windsurf) の使用量を一画面に表示
- **2つの表示モード** — 詳細なフルモードとスリムなコンパクトモード
- **プログレスバー** — 使用率(%)、リセットまでの残り時間、経過時間マーカーを視覚的に表示
- **自動更新** — 60秒間隔でポーリング。ドットアニメーションで次回更新までのカウントダウンを表示
- **システムトレイ常駐** — トレイアイコンからウィジェット表示/更新/終了を操作
- **ドラッグ移動** — ウィジェットをドラッグして好きな位置に配置（位置は保存されます）
- **透明度調整** — 20〜100% で背景透明度を設定可能
- **表示スケール** — 50〜300% でUI全体のサイズを調整
- **DPI対応** — 高DPIモニターでも鮮明に表示
- **自動検出** — 設定済みのサービスだけを表示（認証ファイルの有無で判定）

## セットアップ

### EXE版（推奨）

[Releases](https://github.com/Minobon/UsageMonitor/releases) から最新の `Usage_Monitor_vX.X.X.exe` をダウンロードして実行するだけで使えます。

### ソースから実行

```bash
python -m venv .venv
.venv/Scripts/pip install -r requirements.txt
.venv/Scripts/python src/main.py
```

## 認証設定

各サービスの CLI ツールでログイン済みであれば、自動的に認証ファイルを検出します。

| サービス | 認証ファイル | CLI |
|---|---|---|
| Claude | `~/.claude/.credentials.json` | [Claude Code](https://docs.anthropic.com/en/docs/claude-code) でログイン |
| Codex | `~/.codex/auth.json` | [Codex CLI](https://github.com/openai/codex) でログイン |
| Antigravity | `%APPDATA%/Antigravity` | [Windsurf](https://windsurf.com) が起動中であれば自動検出 |

## 操作方法

| 操作 | 動作 |
|---|---|
| 左ドラッグ | ウィジェットを移動 |
| 右クリック | コンテキストメニューを表示 |
| マウスホバー | 不透明度を100%に |

### コンテキストメニュー

- **更新** — 即座にデータを再取得
- **コンパクト表示 切替** — フル⇔コンパクトモードを切替
- **更新タイマー 切替** — ドットカウントダウンの表示/非表示
- **透明度...** — ホバーしていないときの透明度を調整
- **表示スケール...** — UI全体のサイズを調整
- **終了** — アプリケーションを終了

## ビルド

```bash
build.bat
```

`dist/Usage_Monitor_vX.X.X.exe` が生成されます。

## 動作環境

- Windows 10 / 11
- Python 3.10+ (ソース実行時)

## ライセンス

MIT
