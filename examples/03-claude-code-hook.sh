#!/bin/bash
# 例3: Claude Code hookとしての使用
# brain guardをClaude CodeのPreToolUseフックとして設定するデモ

echo "=== Shared Brain: Claude Code Hook設定 ==="
echo ""

echo "--- 現在のhookステータス ---"
brain hook status
echo ""

echo "--- hookをインストール ---"
echo "(注意: 実際にインストールされます。brain hook uninstall で元に戻せます)"
echo ""
echo "インストールするには以下を実行:"
echo "  brain hook install"
echo ""
echo "これにより、Claude CodeでBashツールが実行されるたびに"
echo "brain guard が自動的にチェックを行います。"
echo ""

echo "--- 仕組み ---"
echo "1. Claude Code が Bash コマンドを実行しようとする"
echo "2. PreToolUse hook が発火"
echo "3. brain guard がコマンドを全教訓と照合"
echo "4. マッチあり → 警告表示、チェックリスト提示"
echo "5. マッチなし → そのまま実行"
echo ""

echo "--- 環境変数 ---"
echo "BRAIN_HOME  教訓の保存場所 (default: ~/.brain)"
echo "BRAIN_AGENT 監査ログのエージェント名 (default: cli-user)"
echo ""
echo "例: BRAIN_AGENT=my-claude-agent brain guard 'rm -rf /'"
