#!/bin/bash

# Claude Commands Sync Script
# This script syncs custom Claude Code commands and agents to ~/.claude directories

set -e

REPO_DIR="$(cd "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
CLAUDE_DIR="$HOME/.claude"
COMMANDS_DIR="$CLAUDE_DIR/commands"
AGENTS_DIR="$CLAUDE_DIR/agents"
SKILLS_DIR="$CLAUDE_DIR/skills"

# A deploy target must be a real directory on the Linux filesystem.
#
# MEASURED 2026-09-06: ~/.claude/commands was a symlink to a second clone of this repo
# on the Windows drive (/mnt/c/...), reached over WSL's 9p mount. Commands were the only
# artifact type behind 9p -- skills and agents are real ext4 directories -- and they were
# the only ones that intermittently failed to load, with every /command reporting
# "Unknown command" while skills kept working. 9p readdir is ~50-100x slower than ext4
# and can stall outright (host hiccup, sleep/resume, an antivirus pass), and a discovery
# scan that times out yields an empty registry rather than an error. Pointing at a repo
# ROOT made it worse: discovery walked .git/ -- 486 entries over 9p instead of 14 -- and
# registered the clone's .subagents/ and .workflows/ as phantom directory-scoped skills.
#
# This refuses rather than repairs: a symlink here was put there on purpose once, and
# silently replacing someone's link is worse than telling them what is wrong.
check_target() {
    local label="$1" dir="$2"
    if [ -L "$dir" ]; then
        echo "ERROR: $CLAUDE_DIR/$label is a symlink -> $(readlink "$dir")" >&2
        echo "       Claude Code discovers $label by scanning this path at startup." >&2
        echo "       Make it a real directory, then re-run ./sync.sh:" >&2
        echo "         rm $dir && mkdir $dir && ./sync.sh" >&2
        echo "       (rm on a symlink removes only the link, never the target.)" >&2
        exit 1
    fi
    if [ -d "$dir" ]; then
        local fstype
        fstype="$(stat -f -c '%T' "$dir" 2>/dev/null || echo unknown)"
        case "$fstype" in
            ext2/ext3|ext4|btrfs|xfs|zfs|overlayfs|tmpfs|unknown) ;;
            *)
                echo "WARNING: $CLAUDE_DIR/$label sits on a '$fstype' filesystem." >&2
                echo "         Startup discovery over a network/9p mount is slow and can" >&2
                echo "         time out, which presents as 'Unknown command'." >&2
                ;;
        esac
    fi
}

check_target commands "$COMMANDS_DIR"
check_target agents   "$AGENTS_DIR"
check_target skills   "$SKILLS_DIR"

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

# Sync skills (each skill is a directory containing SKILL.md + optional assets)
if [ -d "$REPO_DIR/skills" ]; then
    echo "Syncing skills..."
    mkdir -p "$SKILLS_DIR"
    cp -r "$REPO_DIR/skills/"* "$SKILLS_DIR/"
    echo "  Skills synced to $SKILLS_DIR"
fi

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

if [ -d "$REPO_DIR/skills" ]; then
    echo ""
    echo "Synced skills:"
    for skill_dir in "$REPO_DIR/skills/"*/; do
        if [ -f "$skill_dir/SKILL.md" ]; then
            skill_name=$(basename "$skill_dir")
            echo "   $skill_name"
        fi
    done
fi

echo ""
echo "Sync complete!"
