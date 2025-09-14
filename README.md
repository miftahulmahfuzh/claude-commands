# Claude Commands Collection 🚀

A curated collection of custom Claude Code commands that supercharge your development workflow. These commands automate common git operations with intelligent analysis and semantic versioning.

## 🛠️ Installation

Clone this repository and run the installation script to set up all commands:

```bash
git clone https://github.com/yourusername/claude-commands.git
cd claude-commands
./install.sh
```

The installation script will:
- ✅ Create a symlink from `~/.claude/commands` to this repository
- 📦 Backup any existing commands directory
- 🔗 Keep your commands in sync with this git repository
- 🎉 Enable immediate use of all custom commands

### Manual Installation

If you prefer manual setup:

```bash
# Backup existing commands (if any)
mv ~/.claude/commands ~/.claude/commands.backup

# Create symlink to this repository
ln -s /path/to/claude-commands ~/.claude/commands
```

## 📋 Available Commands

### `/push` - Intelligent Git Workflow Automation

Streamlines your entire git commit and push process with AI-powered commit message generation.

**What it does:**
- 🔍 Analyzes all your code changes using `git diff`
- 🧠 Generates intelligent commit messages following conventional commit format
- 📝 Categorizes changes (feat, fix, refactor, docs, etc.)
- 🚀 Stages, commits, and pushes everything in one command
- ✨ Provides detailed summary of all operations

**Usage:**
```
/push
```

**Perfect for:**
- Quick commits with meaningful messages
- Following consistent commit conventions
- Understanding the impact of your changes
- Streamlined development workflow

---

### `/up-version` - Automated Semantic Versioning

Automates the entire version release process with intelligent semantic versioning and changelog generation.

**What it does:**
- 🏷️ Finds your latest version tag on main branch
- 📊 Analyzes all changes since the last release
- 📈 Determines appropriate version bump (major/minor/patch)
- 📝 Generates/updates CHANGELOG.md with categorized changes
- 🔀 Merges changes to main branch
- 🏷️ Creates and pushes new version tag
- 🔄 Returns you to your original branch

**Usage:**
```
/up-version
```

**Perfect for:**
- Release management
- Maintaining semantic versioning
- Automated changelog generation
- Professional project maintenance

## 🎯 Why Use These Commands?

- **🤖 AI-Powered**: Leverages Claude's intelligence to understand your code changes
- **⚡ Time-Saving**: Eliminates repetitive git operations
- **📐 Consistent**: Enforces best practices and conventional formats
- **🔍 Insightful**: Provides detailed analysis of what changed and why
- **🛡️ Safe**: Includes comprehensive error handling and validation
- **🔄 Workflow-Aware**: Designed for real development workflows

## 🤝 Contributing

Found a bug or have an idea for a new command? Contributions are welcome!

1. Fork this repository
2. Create your feature branch (`git checkout -b feature/amazing-command`)
3. Test your changes thoroughly
4. Commit your changes (`git commit -m 'feat: add amazing new command'`)
5. Push to the branch (`git push origin feature/amazing-command`)
6. Open a Pull Request

## 📄 License

This project is open source and available under the [MIT License](LICENSE).

## 🙏 Acknowledgments

- Built for [Claude Code](https://claude.ai/code) by Anthropic
- Inspired by the need for smarter development workflows
- Powered by AI-driven code analysis

---

*Happy coding! 🎉*