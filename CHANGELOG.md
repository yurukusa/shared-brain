# Changelog

All notable changes to Shared Brain will be documented in this file.

## [0.1.0] - 2026-02-10

### Added
- `brain guard <command>` — コマンド実行前にリスク評価（正規表現マッチング + チェックリスト表示）
- `brain check <keyword>` — キーワードで教訓を検索
- `brain list` — 全教訓一覧表示
- `brain write [-f file.yaml]` — 新規教訓の追加（対話形式 or YAMLファイルから）
- `brain audit [--json]` — コンプライアンスレポート（遵守率、レッスン別ブレークダウン）
- `brain stats` — 統計サマリー（教訓数、ガード発火回数、防止率）
- `brain export [--format md|json] [--output file]` — 教訓のエクスポート
- `brain hook install|uninstall|status` — Claude Code PreToolUse hookの自動設定
- 18個のbuilt-in教訓（API PUT安全、git force-push防止、CDP操作等）
- 軽量YAMLパーサー（PyYAML不要、標準ライブラリのみで動作）
- JSONL形式の監査ログ（タイムスタンプ、エージェント名、遵守状況）
- 非対話モード対応（tty検出、auto-confirm フラグ）
- BRAIN_HOME / BRAIN_AGENT 環境変数サポート
- 130個のテストケース（pytest、セキュリティテスト23件含む）
- asciinemaデモ録画
- PyPI公開用 pyproject.toml
- `brain tutorial` — インタラクティブチュートリアル
- `brain demo` — サンドボックス付きデモモード
- `brain benchmark` — パフォーマンスベンチマーク
- bash/zsh補完スクリプト
- manページ
- GitHub Pagesドキュメント
- ロゴ・バナーSVG

### Security Fixes
- **ReDoS防止**: 悪意ある正規表現パターンのヒューリスティック検出 + subprocessタイムアウト
- **Path Traversal防止**: 教訓IDのサニタイズ + resolve検証
- **Command Injection防止**: `--from-env`フラグでシェル展開を回避

### Design Decisions
- **依存関係ゼロ**: 標準ライブラリのみ。PyYAMLがあれば使うが、なくても動く
- **単一ファイル配布**: brain_engine.py 1ファイルで完結
- **ファイルベース**: SQLite等のDB不要。YAML + JSONL で十分
- **教訓はYAML**: 人間が読み書きしやすく、gitで差分が追える
- **ガードは「ブロック」ではなく「確認」**: 最終判断はエージェント/人間に委ねる
