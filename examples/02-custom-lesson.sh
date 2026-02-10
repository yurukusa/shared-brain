#!/bin/bash
# 例2: カスタム教訓の作成と使用
# チーム固有のルールを教訓として登録するデモ

echo "=== Shared Brain: カスタム教訓の作成 ==="
echo ""

# 一時ディレクトリを使用（既存の教訓を汚さない）
export BRAIN_HOME=$(mktemp -d)/brain
echo "テスト用BRAIN_HOME: $BRAIN_HOME"

# 教訓YAMLを作成
LESSON_FILE=$(mktemp --suffix=.yaml)
cat > "$LESSON_FILE" << 'YAML'
id: no-production-db
severity: critical
created: "2026-02-10"
violated_count: 0

trigger_patterns:
  - "production.*db"
  - "prod-.*database"
  - "mysql.*prod"
  - "psql.*production"

lesson: |
  本番DBへの直接接続は禁止。
  必ずステージング環境で検証してから本番に反映すること。
  緊急時でもread replicaを使え。

checklist:
  - "ステージングで検証済み？"
  - "ロールバック手順を確認した？"
  - "DBAに連絡した？"

tags: [database, production, safety]
YAML

echo "--- 教訓を登録 ---"
brain write -f "$LESSON_FILE"
echo ""

echo "--- 教訓一覧 ---"
brain list
echo ""

echo "--- ガード発動テスト ---"
brain guard "mysql -h production-db.internal -u admin" --auto-confirm
echo ""

echo "--- 統計 ---"
brain stats

# クリーンアップ
rm -f "$LESSON_FILE"
rm -rf "$BRAIN_HOME"
