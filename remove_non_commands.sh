#!/bin/bash

# Removes non-command files/dirs that get cloned into ~/.claude/commands
# when this repo is pulled there. Without this, files like CLAUDE.md or
# README.md show up as "custom commands" in every Claude Code session.

set -e

COMMANDS_DIR="$HOME/.claude/commands"

rm -f "$COMMANDS_DIR/CHANGELOG.md"
rm -f "$COMMANDS_DIR/CLAUDE.md"
rm -f "$COMMANDS_DIR/README.md"
rm -f "$COMMANDS_DIR/sync.sh"
rm -rf "$COMMANDS_DIR/agents"
rm -rf "$COMMANDS_DIR/commands"

echo "Cleaned non-command files from $COMMANDS_DIR"
