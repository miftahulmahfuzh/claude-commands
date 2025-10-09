#!/bin/bash

# Claude Commands Installation Script
# This script installs custom Claude Code commands by symlinking this repository
# to ~/.claude/commands directory

set -e

CLAUDE_COMMANDS_DIR="$HOME/.claude/commands"
REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "🚀 Installing Claude Commands..."
echo "Repository: $REPO_DIR"
echo "Target: $CLAUDE_COMMANDS_DIR"

# Check if Claude CLI is installed
if ! command -v claude &> /dev/null; then
    echo "⚠️  Warning: Claude CLI not found. Please install Claude Code first:"
    echo "   https://claude.ai/code"
    echo ""
fi

# Create ~/.claude directory if it doesn't exist
if [ ! -d "$HOME/.claude" ]; then
    echo "📁 Creating ~/.claude directory..."
    mkdir -p "$HOME/.claude"
fi

# Handle existing commands directory
if [ -L "$CLAUDE_COMMANDS_DIR" ]; then
    echo "🔗 Existing symlink found at $CLAUDE_COMMANDS_DIR"
    LINK_TARGET=$(readlink "$CLAUDE_COMMANDS_DIR")
    if [ "$LINK_TARGET" = "$REPO_DIR" ]; then
        echo "✅ Commands are already installed and up to date!"
        exit 0
    else
        echo "🔄 Updating symlink target from $LINK_TARGET to $REPO_DIR"
        rm "$CLAUDE_COMMANDS_DIR"
    fi
elif [ -d "$CLAUDE_COMMANDS_DIR" ]; then
    echo "📦 Backing up existing commands directory..."
    BACKUP_DIR="$CLAUDE_COMMANDS_DIR.backup.$(date +%Y%m%d_%H%M%S)"
    mv "$CLAUDE_COMMANDS_DIR" "$BACKUP_DIR"
    echo "   Backup created at: $BACKUP_DIR"
elif [ -e "$CLAUDE_COMMANDS_DIR" ]; then
    echo "❌ Error: $CLAUDE_COMMANDS_DIR exists but is not a directory or symlink"
    exit 1
fi

# Create the symlink
echo "🔗 Creating symlink..."
ln -s "$REPO_DIR" "$CLAUDE_COMMANDS_DIR"

# Verify installation
if [ -L "$CLAUDE_COMMANDS_DIR" ] && [ -d "$CLAUDE_COMMANDS_DIR" ]; then
    echo "✅ Installation successful!"
    echo ""
    echo "📋 Available commands:"
    for cmd_file in "$REPO_DIR"/*.md; do
        if [ -f "$cmd_file" ]; then
            cmd_name=$(basename "$cmd_file" .md)
            # Skip documentation files that are not commands
            if [[ "$cmd_name" != "CHANGELOG" && "$cmd_name" != "README" ]]; then
                echo "   /$cmd_name"
            fi
        fi
    done
    echo ""
    echo "🎉 You can now use these commands in Claude Code!"
    echo "   Example: /push"
else
    echo "❌ Installation failed!"
    exit 1
fi