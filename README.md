# 🧠 Shared Brain

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![Tests](https://img.shields.io/badge/tests-33%20passed-brightgreen.svg)](https://github.com/yurukusa/shared-brain)
[![No Dependencies](https://img.shields.io/badge/dependencies-none-brightgreen.svg)](https://github.com/yurukusa/shared-brain)
[![Lessons](https://img.shields.io/badge/built--in%20lessons-11-blue.svg)](https://github.com/yurukusa/shared-brain)

**AI agents that learn from each other's mistakes — and prove it.**

## Demo

[![asciicast](https://asciinema.org/a/M60qmrt7QscqWVLb.svg)](https://asciinema.org/a/M60qmrt7QscqWVLb)

## The Problem

An AI agent deleted 5 articles by using `PUT` without first doing `GET`. We wrote a lesson: "Always GET before PUT." The next day, the **same agent made the same mistake**. The lesson existed — but nobody checked it.

**Writing lessons is useless if nobody reads them.**

## The Solution

Shared Brain is a CLI tool that:
- **Stores** structured lessons from agent incidents
- **Guards** — automatically warns before risky operations
- **Tracks** — records whether agents checked AND followed lessons
- **Audits** — proves compliance with hard numbers

## Prerequisites

Python 3.8+ required. Check with: `python3 --version`

## Quick Start

```bash
# Install
git clone https://github.com/yurukusa/shared-brain.git
cd shared-brain
mkdir -p ~/bin && export PATH=~/bin:$PATH
ln -s $(pwd)/brain ~/bin/brain
# Or run directly: python3 brain guard <your-command>

# See what lessons exist
brain list

# Check a command before running it
brain guard "curl -X PUT https://api.example.com/articles/123"

# ⚠️  CRITICAL LESSON: api-put-safety
#    (violated 2x, last: 2026-02-09)
#    "PUT replaces entire resource. Always GET first."
#    Proceed? [y/N]

# Add your own lesson
brain write

# See compliance report
brain audit
```

## Commands

| Command | Description |
|---------|-------------|
| `brain list` | Show all lessons |
| `brain guard <cmd>` | Check command against lessons |
| `brain check <keyword>` | Search lessons by topic |
| `brain write` | Add a new lesson interactively |
| `brain write -f <file>` | Add lesson from YAML file |
| `brain audit` | Compliance report |
| `brain stats` | Quick summary |
| `brain export` | Export lessons (markdown/json) |
| `brain hook install` | Auto-install guard as Claude Code hook |
| `brain hook uninstall` | Remove brain guard hook |
| `brain hook status` | Check if hook is installed |

## How It Works

### Lessons
Stored as YAML files in `~/.brain/lessons/`:

```yaml
id: api-put-safety
severity: critical
trigger_patterns:
  - "PUT /api/"
  - "curl.*-X PUT"
lesson: |
  PUT replaces the entire resource.
  Always GET before PUT.
checklist:
  - "GET the current state"
  - "PUT body contains ALL fields"
```

### Guard
When you run `brain guard`, it matches your command against all lesson `trigger_patterns`. If a match is found, it shows the lesson and asks for confirmation.

### Audit Trail
Every guard check is logged to `~/.brain/audit.jsonl`:
```json
{"timestamp": "2026-02-09T10:30:00Z", "agent": "cc-main", "action": "PUT /api/articles", "checked": true, "followed": true}
```

## Integration
For other AI tools, call brain guard directly before operations.

### As a Claude Code Hook
```bash
# One command — auto-installs into ~/.claude/settings.json
brain hook install

# Verify
brain hook status
# 🟢 Installed

# Remove if needed
brain hook uninstall
```

### Environment Variables
- `BRAIN_HOME` — Override brain directory (default: `~/.brain`)
- `BRAIN_AGENT` — Set agent name for audit logging

## Built-in Lessons (Starter Pack)

Ships with 11 lessons covering the most common agent mistakes:

| ID | Severity | What It Catches |
|----|----------|----------------|
| `api-put-safety` | 🔴 Critical | PUT without GET (data loss) |
| `git-force-push` | 🔴 Critical | Force push, hard reset, rm -rf |
| `no-secrets-in-code` | 🔴 Critical | API keys/passwords in commits |
| `no-production-db-direct` | 🔴 Critical | Destructive queries on production DB |
| `dont-delete-without-confirm` | 🔴 Critical | Deleting files/resources without backup |
| `verify-before-claim` | 🟡 Warning | Claiming success without verification |
| `test-before-deploy` | 🟡 Warning | Deploying without running tests |
| `backup-before-migration` | 🟡 Warning | DB migration without backup |
| `check-rate-limits` | 🟡 Warning | Bulk API requests without rate limiting |
| `validate-input-boundaries` | 🟡 Warning | Unsanitized external input |
| `read-error-messages` | ℹ️ Info | Ignoring error messages when debugging |

## The Story Behind This

This tool was born from a real incident: an AI agent (Claude Code) was automating marketing across 11 platforms. On Day 1, it overwrote one Zenn article by using PUT incorrectly. The team wrote a lesson. On Day 2, the **same mistake destroyed all 5 articles**. A reader discovered it.

The lesson existed in a Markdown file. But the agent never checked it before acting. Shared Brain makes sure that can't happen again — not by trusting agents to read docs, but by putting guardrails in their path.

The same AI-automated marketing pipeline that caused these incidents also produced a real result: a game built entirely by a non-engineer with Claude Code sold its first copy — $2, from a buyer in Poland who found the project through GitHub. The marketing worked. The safety didn't. Shared Brain fixes the safety part.

## Documentation

Full documentation: [yurukusa.github.io/shared-brain](https://yurukusa.github.io/shared-brain)

## License

MIT

---

*Built with Claude Code. The same tool that caused the incidents this tool prevents.*

---

## 🇯🇵 日本語ドキュメント

### Shared Brain とは？

AIエージェントが**失敗から学び、その教訓を共有し、本当に守ったかを証明する**CLIツールです。

### 背景

あるAIエージェントがZennの記事をPUT APIで上書きし、5本の記事を消失させました。「PUTの前に必ずGETする」という教訓をドキュメントに書きましたが、翌日**同じエージェントが同じミスを繰り返しました**。教訓は存在していた——でも誰もチェックしなかった。

**教訓を書くだけでは意味がない。読んだか・守ったかを追跡しなければ。**

### 主な機能

| コマンド | 説明 |
|---------|------|
| `brain list` | 全教訓を一覧表示 |
| `brain guard <cmd>` | コマンド実行前に関連する教訓をチェック |
| `brain check <keyword>` | キーワードで教訓を検索 |
| `brain write` | 新しい教訓を対話形式で追加 |
| `brain audit` | コンプライアンスレポートを表示 |
| `brain stats` | 統計サマリーを表示 |
| `brain hook install` | Claude Codeのhookとして自動インストール |

### クイックスタート

```bash
# インストール
git clone https://github.com/yurukusa/shared-brain.git
cd shared-brain
mkdir -p ~/bin && export PATH=~/bin:$PATH
ln -s $(pwd)/brain ~/bin/brain

# 教訓を確認
brain list

# コマンド実行前にガードチェック
brain guard "curl -X PUT https://api.example.com/articles/123"
# ⚠️  重大な教訓: api-put-safety
#    「PUTはリソース全体を置換する。必ず先にGETすること。」
#    実行しますか？ [y/N]

# 自分の教訓を追加
brain write

# 監査レポート
brain audit
```

### 仕組み

1. **教訓（Lessons）** — YAMLファイルとして `~/.brain/lessons/` に保存。トリガーパターン、重要度、チェックリストを含む
2. **ガード（Guard）** — `brain guard` を実行すると、コマンドを全教訓のトリガーパターンと照合。一致すれば教訓を表示し確認を求める
3. **監査証跡（Audit）** — 全てのガードチェックを `~/.brain/audit.jsonl` に記録。「読んだか・守ったか」をデータで証明

### 同梱教訓（11個）

GETなしPUT、force push、本番DB直接操作、シークレットのコミット、バックアップなし削除など、AIエージェントがよく犯すミスをカバーする11個の教訓が付属しています。

### ライセンス

MIT

*このツールはClaude Codeで構築されました。このツールが防ぐインシデントを起こした、まさにそのツールで。*
