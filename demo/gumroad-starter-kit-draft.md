# Gumroad商品ドラフト: AI Development Starter Kit

## 商品情報

- **商品名**: Complete AI Development System: From Failures to Autonomous Development
- **価格**: $10（既存商品$3-$5の上位版として差別化）
- **カテゴリ**: Software / Developer Tools
- **形式**: ZIP（テンプレート + スクリプト + ドキュメント一式）

## 商品説明（英語・Gumroad掲載用）

### Tagline
**Stop making the same mistakes twice. Build an AI development system that learns from every failure.**

### Description

I'm a non-engineer who built a 15,000-line game, published 2 Kindle books, and automated marketing across 11 platforms — all with AI agents. Along the way, I made every mistake possible: deleted published articles (twice!), sent garbled tweets, broke production deployments.

This starter kit is the system I wish I had on Day 1. It's the infrastructure that turns AI coding assistants from "helpful but forgetful" into "autonomous and reliable."

### What's Inside

**1. CLAUDE.md Template** (`CLAUDE_Example.md`)
- Production-tested global instructions for Claude Code
- Autonomous decision rules (when to ask, when to act)
- Git safety protocols that actually prevent disasters
- Multi-agent coordination patterns

**2. Hook Scripts** (`Hooks/` — 11 scripts)
- `syntax-check.sh` — Auto-validates code after every edit
- `tweet-guard.sh` — Blocks broken tools, suggests working alternatives
- `cdp-safety-check.sh` — Prevents browser automation disasters
- `cdp-failure-recovery.sh` — Auto-recovers from CDP timeouts
- `context-monitor.sh` — Warns before hitting context limits
- `no-question-to-human.sh` — Enforces autonomous operation
- `brain-guard-hook.sh` — Pre-flight lesson checking (the killer feature)
- And 4 more operational hooks

**3. Shared Brain CLI** (`SharedBrain/`)
- `brain` CLI tool — query, add, and guard lessons
- `brain guard` — Pre-hook that pattern-matches commands against learned lessons
- YAML lesson format with severity, trigger patterns, checklists
- 5 real-world lesson examples from production incidents

**4. Multi-Agent Orchestration** (`Multi_Agent_Orchestration/`)
- Tachikoma loop template (autonomous task coordinator)
- Session management patterns
- Inter-agent communication protocols

**5. Playbook** (`Playbook.md` — 25 pages)
- Chapter 1: Setting Up Your AI Development Environment
- Chapter 2: Writing Effective CLAUDE.md Instructions
- Chapter 3: Hook-Driven Quality Enforcement
- Chapter 4: The Shared Brain Pattern (Learning from Failures)
- Chapter 5: Multi-Agent Coordination
- Chapter 6: Real-World Case Studies (Zenn disaster, Tweet failures, etc.)
- Chapter 7: From Zero to Autonomous Development

### Who This Is For
- Non-engineers using AI coding assistants (Claude Code, Cursor, GitHub Copilot)
- Solo developers who want their AI to stop repeating mistakes
- Anyone building autonomous AI workflows

### Key Differentiator
This isn't theoretical. Every template, hook, and lesson came from real production failures. The Shared Brain system exists because we deleted published articles twice and posted garbled tweets — and then built infrastructure so it could never happen again.

## パッケージ構成

```
ai-dev-starter-kit/
├── README.md                    # Quick start guide
├── CLAUDE_Example.md            # Claude Code global instructions template
├── Hooks/
│   ├── README.md                # Hook installation guide
│   ├── syntax-check.sh
│   ├── tweet-guard.sh
│   ├── cdp-safety-check.sh
│   ├── cdp-failure-recovery.sh
│   ├── context-monitor.sh
│   ├── no-question-to-human.sh
│   ├── brain-guard-hook.sh
│   └── ... (4 more)
├── SharedBrain/
│   ├── README.md                # Shared Brain setup guide
│   ├── brain                    # CLI tool
│   ├── brain_engine.py          # Core engine
│   ├── pyproject.toml
│   └── lessons/                 # Example lessons
│       ├── zenn-get-before-put.yaml
│       ├── tweet-use-cdp.yaml
│       ├── cdp-dialog-new-tab.yaml
│       ├── cdp-use-helper-not-custom.yaml
│       └── knowledge-execution-gap.yaml
├── Multi_Agent_Orchestration/
│   ├── README.md                # Orchestration patterns guide
│   ├── tachikoma-loop-template.sh
│   └── session-management.md
└── Playbook.md                  # 25-page comprehensive guide
```

## 既存商品との差別化

| 項目 | 既存商品 ($3-$5) | このキット ($10) |
|------|------------------|-----------------|
| 対象 | Azure Flame / Kindle本 | 開発システムそのもの |
| 内容 | 完成プロダクト | テンプレート + ツール + ガイド |
| 再利用性 | 消費型 | インフラ型（何度でも使える） |
| 価値提案 | エンターテインメント | 生産性向上 |

## 次のステップ

1. パッケージ内容物の実ファイルを作成
2. Gumroad商品ページをCDP経由で作成
3. サムネイル/カバー画像の作成
4. 公開前レビュー（タチコマ or ぐらす）

## メモ

- Gumroad商品作成はREST APIなし → CDP経由でブラウザ操作が必要
- Google OAuth認証済み（wakakusa.takei@gmail.com）
- 既存4商品（$3-$5）は全て公開済み・売上ゼロ
- このキットは「証明」のコア — 非エンジニアがAIで開発インフラを構築できることの実証
