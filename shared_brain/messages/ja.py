"""
Shared Brain CLI - 日本語メッセージカタログ.

プレースホルダー ({lid}, {dest} 等) は英語のまま維持する。
ANSIカラーコードは含めない(表示ロジック側で付与)。
"""

MESSAGES = {

    # =========================================================================
    # 共通 / ユーティリティ
    # =========================================================================

    "aborted": "中止しました。",
    "proceed_prompt": "続行しますか？ [y/N] ",
    "proceed_auto_confirmed": "続行しますか？ [y/N] y  (自動承認)",
    "non_interactive_warning": "非インタラクティブモードで実行中。注意して続行します。",
    "press_enter": "Enterキーで続行...",

    # =========================================================================
    # 警告 (stderr出力)
    # =========================================================================

    "warn_load_failed": "警告: {path} の読み込みに失敗: {error}",
    "warn_audit_read_failed": "警告: 監査ファイルの読み込みに失敗: {error}",
    "warn_audit_corrupt_line": "警告: 監査エントリの{line_num}行目が破損しているためスキップ",
    "warn_regex_timeout": "警告: 正規表現パターンがタイムアウト (ReDoSの可能性): {pattern}",

    # =========================================================================
    # brain write
    # =========================================================================

    "write_error_file_not_found": "エラー: ファイルが見つかりません: {src}",
    "write_error_file_not_found_detail": "  YAMLファイル '{src}' が存在しません。",
    "write_error_file_not_found_hint": "  先にファイルを作成するか、'brain write' でインタラクティブに追加してください。",
    "write_error_invalid_id": "エラー: 無効なレッスンID '{raw_lid}'。",
    "write_error_invalid_id_detail": "  レッスンIDには単語文字とハイフンのみ使用できます。",
    "write_error_invalid_id_path_sep": "  パス区切り (/, \\) と '..' は使用できません。",
    "write_error_invalid_id_short": "エラー: 無効なレッスンID '{raw_lid}'。単語文字とハイフンのみ使用してください。",
    "write_error_path_traversal": "エラー: レッスンID '{raw_lid}' にパストラバーサルが検出されました。",
    "write_success_from_file": "Lesson '{lid}' を {dest} に書き込みました",
    "write_success_interactive": "\nLesson '{lid}' を {dest} に保存しました",
    "write_header": "新しいレッスン",
    "write_prompt_id": "ID (短い、ケバブケース): ",
    "write_prompt_severity": "重要度 (critical/warning/info) [warning]: ",
    "write_prompt_lesson": "レッスン (エージェントに何を教えたいか？): ",
    "write_prompt_trigger_intro": "トリガーパターン (正規表現、空行で終了):",
    "write_prompt_trigger": "  パターン> ",
    "write_prompt_checklist_intro": "チェックリスト項目 (空行で終了):",
    "write_prompt_checklist": "  チェック> ",

    # =========================================================================
    # brain guard
    # =========================================================================

    "guard_error_no_command": "エラー: コマンドが指定されていません。",
    "guard_error_no_command_desc": "  brain guard は実行前にコマンドを既知のレッスンと照合します。",
    "guard_error_no_command_usage": '  使用例: brain guard "curl -X PUT https://api.example.com/articles/123"',
    "guard_severity_lesson": "  {severity} レッスン: {lid}",
    "guard_violated_count": "   (違反 {count}回、最終: {last})",
    "guard_no_description": "説明がありません。",
    "guard_checklist_header": "チェックリスト:",
    "guard_source_label": "   出典: {incident}",

    # =========================================================================
    # brain check
    # =========================================================================

    "check_error_no_keyword": "エラー: キーワードが指定されていません。",
    "check_error_no_keyword_desc": "  brain check は全レッスンをキーワードで検索します。",
    "check_error_no_keyword_usage": '  使用例: brain check "PUT" または brain check "api safety"',
    "check_no_results": "'{keyword}' に一致するレッスンはありません",
    "check_found": "'{keyword}' に一致するレッスンが {count} 件見つかりました:\n",
    "check_no_description": "(説明なし)",
    "check_violated_count": "     違反 {count} 回",

    # =========================================================================
    # brain list
    # =========================================================================

    "list_empty": "レッスンが見つかりません。'brain write' で追加してください。",
    "list_header": "{count} 件のレッスン:\n",
    "list_builtin_label": " (組み込み)",
    "list_no_description": "(説明なし)",
    "list_triggers_label": "     トリガー: {triggers}",
    "list_violated_label": "     違反 {count}回",

    # =========================================================================
    # brain audit
    # =========================================================================

    "audit_empty": "監査エントリはまだありません。",
    "audit_header": "監査レポート",
    "audit_total_checks": "総チェック数: {count}",
    "audit_followed": "遵守:         {count}",
    "audit_blocked": "ブロック:     {count}",
    "audit_compliance": "コンプライアンス率: {rate:.0f}%",
    "audit_per_lesson": "レッスン別内訳:",
    "audit_last_entries": "\n直近 {count} 件:",

    # =========================================================================
    # brain stats
    # =========================================================================

    "stats_header": "Shared Brain 統計",
    "stats_lessons": "レッスン数:    {total} ({critical} critical)",
    "stats_violations": "違反数:        {count} (累積)",
    "stats_guard_fires": "ガード発火:    {count}",
    "stats_proceeded": "続行:          {count}",
    "stats_aborted": "中止:          {count}",
    "stats_prevention": "防止率:        {rate:.0f}% (ミス検出)",
    "stats_severity_header": "重要度別内訳:",
    "stats_severity_critical": "  Critical: {count}",
    "stats_severity_warning": "  Warning:  {count}",
    "stats_severity_info": "  Info:     {count}",
    "stats_categories_header": "カテゴリ (タグ別):",
    "stats_top_triggers_header": "ガード発火 トップ5:",
    "stats_recently_added_header": "最近追加 (直近5件):",

    # =========================================================================
    # brain hook
    # =========================================================================

    "hook_error_invalid": "エラー: サブコマンドが無効または未指定です。",
    "hook_error_invalid_desc": "  brain hook は Claude Code の PreToolUse 連携を管理します。",
    "hook_error_invalid_usage": "  使用例: brain hook install | brain hook uninstall | brain hook status",
    "hook_status_not_installed_no_settings": "未インストール (settings.json が見つかりません)",
    "hook_status_installed": "インストール済み",
    "hook_status_not_installed": "未インストール",
    "hook_uninstall_no_settings": "アンインストール対象がありません (settings.json が見つかりません)",
    "hook_uninstall_not_found": "Brain guard フックが設定に見つかりません",
    "hook_uninstall_success": "Brain guard フックを Claude Code から削除しました",
    "hook_install_created": "Brain guard をインストールしました！ ({path} を作成)",
    "hook_install_already": "Brain guard フックは既にインストール済みです",
    "hook_install_success": "Brain guard を Claude Code にインストールしました！",
    "hook_install_description": "   すべての Bash コマンドがレッスンと照合されます。",
    "hook_install_verify_hint": "   'brain hook status' で確認してください。",

    # =========================================================================
    # brain export
    # =========================================================================

    "export_error_unknown_format": "エラー: 不明なフォーマット '{fmt}'。",
    "export_error_unknown_format_detail": "  対応フォーマット: {formats}。",
    "export_error_unknown_format_usage": "  使用例: brain export --format md --output lessons.md",
    "export_md_title": "# Shared Brain \u2014 エクスポートされたレッスン",
    "export_md_count": "*{count} 件のレッスンをエクスポート ({date})*",
    "export_md_severity_label": "**重要度:** {severity}",
    "export_md_triggers_label": "**トリガー:** ",
    "export_md_tags_label": "**タグ:** {tags}",
    "export_success": "{count} 件のレッスンを {path} にエクスポートしました",

    # =========================================================================
    # brain search
    # =========================================================================

    "search_error_no_term": "エラー: 検索語が指定されていません。",
    "search_error_no_term_desc": "  brain search はキーワードでレッスンを検索します。",
    "search_error_no_term_usage1": '  使用例: brain search "CDP"',
    "search_error_no_term_usage2": "         brain search --tag api",
    "search_error_no_term_usage3": '         brain search --severity critical "PUT"',
    "search_no_results": "'{query}' に一致するレッスンはありません",
    "search_result_count": "{count} 件の検索結果:\n",
    "search_tags_label": "タグ:",
    "search_triggers_label": "トリガー:",
    "search_matched_in_label": "一致箇所:",

    # =========================================================================
    # brain benchmark
    # =========================================================================

    "benchmark_error_not_found": "エラー: ベンチマークスクリプトが見つかりません。",
    "benchmark_error_expected_at": "  期待されるパス: {path}",
    "benchmark_error_hint": "  このファイルはソースリポジトリに同梱されています。試してください: git clone && cd shared-brain",

    # =========================================================================
    # brain help
    # =========================================================================

    "help_text": """Shared Brain - AIエージェントがお互いのミスから学ぶシステム

使い方:
  brain write                 インタラクティブにレッスンを追加
  brain write -f <file.yaml>  YAMLファイルからレッスンを追加
  brain guard <command>       コマンドを既知のレッスンと照合
  brain check <keyword>       キーワードでレッスンを検索
  brain search <term>         ハイライト付きの全文検索
  brain search --tag <tag>    タグでレッスンを絞り込み
  brain search --severity <s> 重要度でレッスンを絞り込み
  brain list                  全レッスンを一覧表示
  brain audit [--json]        コンプライアンスレポートを表示
  brain stats                 統計サマリーを表示
  brain stats --verbose       カテゴリ別・トップトリガー等の詳細
  brain export [--format md|json|html] [--output file]
                              レッスンを他プロジェクト向けにエクスポート
  brain share <lesson_id>     レッスンをグローバル共有に同意
  brain unshare <lesson_id>   グローバル共有を取り消し
  brain update                グローバル安全パックを更新
  brain registry stats        グローバルレジストリ統計を表示
  brain registry build        共有レッスンからパックを生成
  brain hook install          ガードを Claude Code フックに自動インストール
  brain hook uninstall        brain guard フックを削除
  brain hook status           フックがインストール済みか確認
  brain uninstall [--all]     フックと監査ログを削除 (--all: レッスン・プラグインも)
  brain doctor                環境診断を実行
  brain new                   現在のディレクトリにYAMLレッスンテンプレートを生成
  brain tutorial              新規ユーザー向けインタラクティブガイド

環境変数:
  BRAIN_HOME    brainディレクトリを上書き (デフォルト: ~/.brain)
  BRAIN_AGENT   監査ログ用のエージェント名を設定
  BRAIN_LANG    言語を設定 (例: ja, en)
  BRAIN_REGISTRY_PACK  グローバル安全パックのパス (デフォルト: ~/.brain/registry/beginner_safety_pack.json)

使用例:
  brain guard "curl -X PUT https://api.example.com/articles/123"
  brain check "api safety"
  brain write -f my-lesson.yaml
  brain export --format json --output lessons.json
""",

    # =========================================================================
    # brain uninstall
    # =========================================================================

    "uninstall_warning": "Shared Brainのデータをシステムから削除します。",
    "uninstall_will_remove_hook": "  - Claude Code brain guardフック",
    "uninstall_will_remove_audit": "  - 監査ログ ({path})",
    "uninstall_will_remove_lessons": "  - ユーザーレッスン ({path} 内の {count} ファイル)",
    "uninstall_will_remove_plugins": "  - プラグイン ({path} 内の {count} ファイル)",
    "uninstall_will_remove_brain_dir": "  - Brainディレクトリ ({path})",
    "uninstall_confirm": "本当に削除しますか？ [y/N] ",
    "uninstall_hook_removed": "Claude Code brain guardフックを削除しました",
    "uninstall_audit_removed": "監査ログを削除しました",
    "uninstall_lessons_removed": "ユーザーレッスン {count} 件を削除しました",
    "uninstall_plugins_removed": "プラグイン {count} 件を削除しました",
    "uninstall_brain_dir_removed": "Brainディレクトリを削除しました",
    "uninstall_complete": "アンインストール完了。ビルトインレッスンはソースリポジトリに残ります。",
    "uninstall_nothing": "アンインストール対象がありません（Brainディレクトリが見つかりません）。",
    "uninstall_keep_lessons_hint": "  ヒント: --all を使うとユーザーレッスンとプラグインも削除します。",

    # =========================================================================
    # brain doctor
    # =========================================================================

    "doctor_header": "Brain Doctor - 環境チェック",
    "doctor_python_version": "Python: {version}",
    "doctor_brain_dir": "Brainディレクトリ: {path}",
    "doctor_brain_dir_missing": "Brainディレクトリ: {path} (未作成 - 初回使用時に作成されます)",
    "doctor_lessons_count": "レッスン: ユーザー {user} + ビルトイン {builtin} = 合計 {total}",
    "doctor_lessons_errors": "レッスンエラー: {count} ファイルの読み込みに失敗",
    "doctor_lessons_error_detail": "  - {file}: {error}",
    "doctor_audit_ok": "監査ログ: {count} エントリ ({path})",
    "doctor_audit_missing": "監査ログ: 未作成",
    "doctor_audit_corrupt": "監査ログ: {ok} 正常, {bad} 破損エントリ",
    "doctor_hook_installed": "Claude Codeフック: インストール済み",
    "doctor_hook_not_installed": "Claude Codeフック: 未インストール",
    "doctor_hook_no_settings": "Claude Codeフック: settings.jsonが見つかりません",
    "doctor_permissions_ok": "権限: OK（Brainディレクトリ書き込み可能）",
    "doctor_permissions_bad": "権限: 警告 - {path} に書き込みできません",
    "doctor_plugins_count": "プラグイン: {count} 件読み込み済み",
    "doctor_plugins_none": "プラグイン: なし",
    "doctor_all_ok": "全チェックパス！",
    "doctor_issues_found": "{count} 件の問題が見つかりました。",

    # =========================================================================
    # brain new
    # =========================================================================

    "new_header": "レッスンテンプレート生成",
    "new_prompt_id": "レッスンID (短い、ケバブケース): ",
    "new_prompt_severity": "重要度 (critical/warning/info) [warning]: ",
    "new_prompt_description": "説明 (エージェントに何を教えたいか？): ",
    "new_prompt_trigger_intro": "トリガーパターン (正規表現、空行で終了):",
    "new_prompt_trigger": "  パターン> ",
    "new_prompt_checklist_intro": "チェックリスト項目 (空行で終了):",
    "new_prompt_checklist": "  チェック> ",
    "new_prompt_tags": "タグ (カンマ区切り、例: api,safety): ",
    "new_saved": "テンプレートを {path} に保存しました",
    "new_hint": "  インポート: brain write -f {path}",

    # =========================================================================
    # main
    # =========================================================================

    "main_error_unknown_command": "エラー: 不明なコマンド '{cmd}'。",
    "main_error_available_commands": "  利用可能なコマンド: write, guard, check, search, list, audit, stats, export, hook, uninstall, doctor, new, tutorial, benchmark",
    "main_error_help_hint": "  詳細は 'brain help' を実行してください。",
}
