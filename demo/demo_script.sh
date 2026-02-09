#!/bin/bash
# Shared Brain - Hackathon Demo Script
# Run this to demonstrate the full workflow
set -e

BRAIN="$(dirname "$(dirname "$(readlink -f "$0")")")/brain"
export BRAIN_HOME="/tmp/brain-demo"
export BRAIN_AGENT="demo-agent"

echo "🧠 Shared Brain Demo"
echo "===================="
echo ""

# Clean demo environment
rm -rf "$BRAIN_HOME"
mkdir -p "$BRAIN_HOME/lessons"

# --- Act 1: The Problem ---
echo "📖 Act 1: The Problem"
echo "---------------------"
echo ""
echo "An AI agent needs to update an article. It uses PUT..."
echo ""
echo '  $ curl -X PUT https://api.zenn.dev/api/articles/my-article \'
echo '    -d '"'"'{"body_markdown": "Just a footer link"}'"'"''
echo ""
echo "💥 The article body is REPLACED with just the footer."
echo "   5 articles destroyed. A reader discovered it."
echo ""
echo "The team writes a lesson. But the next day..."
echo "   Same agent. Same mistake. Same destruction."
echo ""
echo "The lesson existed. The agent didn't check it."
echo ""
read -p "Press Enter to continue..." _

# --- Act 2: Install Shared Brain ---
echo ""
echo "📖 Act 2: Shared Brain"
echo "----------------------"
echo ""
echo "Now let's install the lesson..."
echo ""

# Copy the PUT safety lesson
cp "$(dirname "$(dirname "$(readlink -f "$0")")")/lessons/api-put-safety.yaml" "$BRAIN_HOME/lessons/"
echo '  $ brain write -f api-put-safety.yaml'
echo ""

"$BRAIN" list
echo ""
read -p "Press Enter to see the guard in action..." _

# --- Act 3: Guard in Action ---
echo ""
echo "📖 Act 3: Guard Catches the Mistake"
echo "------------------------------------"
echo ""
echo '  $ brain guard "curl -X PUT https://api.zenn.dev/api/articles/abc"'
echo ""

echo "y" | "$BRAIN" guard "curl -X PUT https://api.zenn.dev/api/articles/abc123"
echo ""
read -p "Press Enter to see a different agent..." _

# --- Act 4: Cross-Agent Learning ---
echo ""
echo "📖 Act 4: A Different Agent"
echo "---------------------------"
echo ""
echo "A subagent (not the one who learned the lesson) tries the same thing..."
echo ""

export BRAIN_AGENT="subagent-3"
echo '  $ BRAIN_AGENT=subagent-3 brain guard "requests.put(url, json=data)"'
echo ""

echo "y" | "$BRAIN" guard 'requests.put("https://api.example.com/articles/123", json={"title": "oops"})'
echo ""

echo "The lesson was learned ONCE. Every agent benefits."
echo ""
read -p "Press Enter to see the audit..." _

# --- Act 5: Audit Dashboard ---
echo ""
echo "📖 Act 5: Proof"
echo "---------------"
echo ""

"$BRAIN" stats
echo ""
"$BRAIN" audit
echo ""

echo "This is the proof. Not that we wrote the lesson —"
echo "that we CHECKED it. Every time. Automatically."
echo ""
echo "🧠 Shared Brain: AI agents that learn from each other's mistakes — and prove it."

# Clean up
rm -rf "$BRAIN_HOME"
