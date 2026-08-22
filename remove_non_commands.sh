#!/bin/bash

# Removes non-command files/dirs that get cloned into ~/.claude/commands.
#
# History: this repo used to be cloned directly into ~/.claude/commands, which
# left behind top-level repo files (CLAUDE.md, README.md, ...) *and* the clone's
# own dotfiles. Anything left there is loaded by every Claude Code session:
# loose .md files show up as bogus "custom commands", and .subagents/ and
# .workflows/ get picked up as skills that shadow the maintained copies in
# ~/.claude/agents. sync.sh no longer creates any of this, so everything below
# is stale by definition and reproducible from this repo.

set -euo pipefail

COMMANDS_DIR="$HOME/.claude/commands"

# Guard: never let a bad expansion turn the loop below into `rm -rf /` or into
# wiping the commands dir itself.
if [ -z "${HOME:-}" ] || [ "$COMMANDS_DIR" != "$HOME/.claude/commands" ]; then
    echo "Refusing to run: COMMANDS_DIR is not \$HOME/.claude/commands" >&2
    exit 1
fi

if [ ! -d "$COMMANDS_DIR" ]; then
    echo "Nothing to clean: $COMMANDS_DIR does not exist"
    exit 0
fi

# Stale repo files from the old clone-into-commands layout.
STALE=(
    CHANGELOG.md
    CLAUDE.md
    README.md
    sync.sh
    remove_non_commands.sh
    agents
    commands
    skills
    cmd
    # Dotfiles/dirs the clone itself brought along. .subagents and .workflows
    # are the harmful ones: Claude Code loads them as skills.
    .git
    .gitignore
    .claude
    .subagents
    .workflows
)

removed=0
for name in "${STALE[@]}"; do
    target="$COMMANDS_DIR/$name"
    if [ -e "$target" ] || [ -L "$target" ]; then
        rm -rf -- "$target"
        echo "  removed $name"
        removed=$((removed + 1))
    fi
done

if [ "$removed" -eq 0 ]; then
    echo "Already clean: no non-command files in $COMMANDS_DIR"
else
    echo "Cleaned $removed non-command entr$([ "$removed" -eq 1 ] && echo y || echo ies) from $COMMANDS_DIR"
fi
