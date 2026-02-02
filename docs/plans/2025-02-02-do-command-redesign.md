# Do Command Redesign - Context Isolation Architecture

**Date:** 2025-02-02
**Status:** Design Validated
**Related Tasks:** #1, #2, #3, #4, #5, #6

---

## Overview

Redesign the `/do` command to keep the main context clean for code implementation only. All supporting work (searching, reading, planning, documenting) is delegated to isolated subagents.

## Problem Statement

The current `/do` command performs all work in the main context:
- Searching for tasks across todos.md files
- Loading context from multiple documentation files
- Creating implementation plans
- Executing code changes
- Updating documentation and git

This pollutes the main context with non-implementation data, reducing token efficiency and focus.

## Solution Architecture

### Pipeline Design

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│  Prep Phase     │    │  Main Context   │    │  Post Phase     │
│  (Sequential    │───▶│  (Code Only)     │───▶│  (Single        │
│   Subagents)    │    │                  │    │   Subagent)     │
└─────────────────┘    └─────────────────┘    └─────────────────┘
```

---

## Implementation Tasks

| Task ID | Description | Dependencies |
|---------|-------------|--------------|
| #1 | Create Subagent 1: Task Locator | None |
| #2 | Create Subagent 2: Context Loader | #1 |
| #3 | Create Subagent 3: Plan Generator | #1, #2 |
| #4 | Update Main Context Execution Logic | #3 |
| #5 | Create Subagent 4: Completion Handler | #4 |
| #6 | Update do.md Documentation | #1, #2, #3, #4, #5 |

## Token Efficiency

| Metric | Original | Redesigned | Improvement |
|--------|----------|------------|-------------|
| Context size before implementation | All docs + plans | Clean brief only | ~80% reduction |
| Context size during implementation | Same + file edits | Target files only | ~70% reduction |

See the full design document for complete specifications of each subagent, data flow diagrams, error handling, and examples.
