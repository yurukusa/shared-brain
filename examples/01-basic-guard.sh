#!/bin/bash
# 例1: 基本的なguard使用
# コマンド実行前にリスク評価を行うデモ

echo "=== Shared Brain: 基本的なguard使用 ==="
echo ""

# 安全なコマンド → 何も起きない
echo "--- 安全なコマンド ---"
brain guard "curl -X GET https://api.example.com/articles"
echo "結果: $? (0 = 安全)"
echo ""

# 危険なコマンド → 警告が表示される
echo "--- 危険なコマンド（PUT） ---"
brain guard "curl -X PUT https://api.example.com/articles/123" --auto-confirm
echo "結果: $? (0 = 確認済み)"
echo ""

# git force-push → 強い警告
echo "--- 非常に危険なコマンド（force push） ---"
brain guard "git push --force origin main" --auto-confirm
echo "結果: $? (0 = 確認済み)"
echo ""

echo "=== 監査ログを確認 ==="
brain audit
