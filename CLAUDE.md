# Usage Monitor - Development Notes

## Project Structure
- `src/main.py` - エントリーポイント（データフロー: main → services → main → ui）
- `src/config.py` - 定数・設定値（PROJECT_ROOT, ASSETS_DIR等）
- `src/models.py` - データモデル
- `src/ui/widget.py` - メインウィジェット（状態管理・イベント・公開API）
- `src/ui/drawing.py` - 描画ロジック（WidgetRenderer）
- `src/ui/timer.py` - タイマーインジケーター（TimerIndicator）
- `src/ui/tray.py` - システムトレイアイコン (pystray)
- `src/services/` - API連携 (claude.py, codex.py, antigravity.py)
- `scripts/` - ビルド・デバッグ用ヘルパー (gen_icon.py, get_ls_info.py)
- `assets/` - アイコン画像

## Version & Build
- **VERSION file**: `./VERSION` (ルート直下、1行テキスト。例: `1.2.0`)
- **Build script**: `./build.bat`
- **Output**: `./dist/Usage_Monitor_v{VERSION}.exe`

## Build & Launch Check 手順
```bash
# 1. VERSION を更新
# 2. ビルド (build.bat を使用。venv作成・PyInstallerインストールも自動)
cmd.exe //C ".\\build.bat"

# 3. 起動チェック (5秒待ってプロセス確認)
"./dist/Usage_Monitor_v$(cat VERSION | tr -d '\r').exe" &
sleep 5 && tasklist | grep -i Usage_Monitor

# 4. 終了
powershell -Command "Stop-Process -Name 'Usage_Monitor_v$(cat VERSION | tr -d '\r')' -Force"
```

## Notes
- bash環境 (Git Bash) 前提。`taskkill /IM` は Git Bash で `/IM` がパス展開されるため `powershell Stop-Process` を使う
- 設定ファイル: `~/.claude/usage_monitor_settings.json`
- 認証情報: `~/.claude/.credentials.json` (Claude), `~/.codex/auth.json` (Codex), `%APPDATA%/Antigravity` (Antigravity)
- Codex の `CODEX_CLIENT_ID` はパブリックOAuthクライアントIDであり、Codex CLIのソースコードにも公開されている
