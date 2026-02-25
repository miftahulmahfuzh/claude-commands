# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.1.0] - 2026-02-25

### Added
- **Subagent-based Architecture for /do and /implement**: Complete redesign with context isolation
  - Task Locator, Context Loader, Plan Generator, and Completion Handler subagents
  - Improved task execution with dedicated context management
  - Better error handling and task tracking

- **New Commands**:
  - `/postmortem`: Session problem documentation with TaskID integration
  - `/reorganize-todos`: Task organization with automatic completed tasks management
  - `/analyze-package`: Package analysis command
  - `/analyze`: Code archaeology and analysis command
  - `/update-readme`: Automated README updates
  - `/update-todos`: Task list management command

- **Difficulty Classification System**: Automatic HARD task branch management
  - P1/P2/P3 priority system with difficulty indicators
  - Automatic branch creation for complex tasks

- **TaskID System**: Comprehensive task tracking with unique identifiers
  - Enforced uniqueness and 4-section structure
  - Completed tasks separation and archive management

- **Pusher Agent**: Specialized git commit and push operations

- **Sync Script**: Repository synchronization utility with portability fixes

### Changed
- **Repository Reorganization**: Improved directory structure
  - Moved plan files to dedicated plan directory
  - Moved push.md to agents/pusher.md
  - Added .workflows/todos.md for workflow tracking

- **Enhanced Documentation**:
  - Comprehensive README updates with 487 new lines
  - Detailed command documentation for all new commands
  - Interactive clarification guidance for confusion handling

### Fixed
- **sync.sh**: Fixed dirname command syntax for portability across shell implementations

### Removed
- **install.sh**: Replaced with sync.sh for improved workflow

## [1.0.0] - 2025-09-14

### Added
- **Installation script (install.sh)**: Automated setup script for easy installation with symlink management
  - Creates symlink from `~/.claude/commands` to repository directory
  - Handles backup of existing commands directory with timestamp
  - Validates Claude CLI installation and provides setup guidance
  - Lists available commands after successful installation
  - Includes comprehensive error handling and user feedback

- **Comprehensive README.md**: Complete project documentation and usage guide
  - Detailed installation instructions with both automated and manual options
  - Complete command descriptions with usage examples and use cases
  - Project benefits and feature highlights
  - Contributing guidelines and development workflow
  - Professional formatting with clear sections and visual elements

- **Custom Claude Commands**: Two powerful workflow automation commands
  - `/push`: Intelligent git workflow automation with AI-powered commit messages
  - `/up-version`: Automated semantic versioning and changelog maintenance

### Technical Details
- Total additions: 186 lines of code across 2 new files
- Repository structure established for command management
- Symlink-based installation system for seamless updates
- Keep a Changelog format compliance for version tracking

### Project Milestone
This represents the initial release of the Claude Commands Collection, providing a complete foundation for custom Claude Code command management with professional documentation and automated installation.