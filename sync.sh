#!/bin/bash

# Claude Commands Sync Script
# This script syncs custom Claude Code commands and agents to ~/.claude directories

set -e

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}") && pwd)"
CLAUDE_DIR="$HOME/.claude"
COMMANDS_DIR="$CLAUDE_DIR/commands"
AGENTS_DIR="$CLAUDE_DIR/agents"

echo "Syncing Claude Commands & Agents..."
echo "Repository: $REPO_DIR"

# Create ~/.claude directory if it doesn't exist
if [ ! -d "$CLAUDE_DIR" ]; then
    echo "Creating ~/.claude directory..."
    mkdir -p "$CLAUDE_DIR"
fi

# Sync commands
echo "Syncing commands..."
mkdir -p "$COMMANDS_DIR"
cp -r "$REPO_DIR/commands/"* "$COMMANDS_DIR/"
echo "  Commands synced to $COMMANDS_DIR"

# Sync agents
echo "Syncing agents..."
mkdir -p "$AGENTS_DIR"
cp -r "$REPO_DIR/agents/"* "$AGENTS_DIR/"
echo "  Agents synced to $AGENTS_DIR"

# List what was synced
echo ""
echo "Synced commands:"
for cmd_file in "$REPO_DIR/commands/"*.md; do
    if [ -f "$cmd_file" ]; then
        cmd_name=$(basename "$cmd_file" .md)
        echo "   /$cmd_name"
    fi
done

echo ""
echo "Synced agents:"
for agent_file in "$REPO_DIR/agents/"*.md; do
    if [ -f "$agent_file" ]; then
        agent_name=$(basename "$agent_file" .md)
        echo "   $agent_name"
    fi
done

echo ""
echo "Sync complete!"
