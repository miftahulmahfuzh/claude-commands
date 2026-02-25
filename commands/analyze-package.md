# Analyze Package Command

Perform deep analysis of the package at `{directory_path}` and generate `{directory_path}/.workflows/analysis_report.md`

## Prerequisites

### Required Files
Read `{directory_path}/.workflows/package_readme.md` first. If it doesn't exist, abort and instruct user to run `/update-readme {directory_path}` first.

### Optional Files (enhance analysis)
Read `{directory_path}/.workflows/benchmark_analysis.md` if exists. Extract:
- Performance characteristics documented
- Known bottlenecks identified
- Optimization opportunities mentioned
- Scaling behavior patterns
- Memory usage patterns
- Concurrent performance data

Use benchmark data to validate or contradict static code analysis findings.

## Analysis Requirements

### 1. Code Complexity
- Calculate cyclomatic complexity for each function (>10 = refactor candidate)
- Identify functions with >50 lines (complexity risk)
- Flag deeply nested logic (>4 levels)

### 2. API Usage Analysis
- Scan entire codebase for imports of this package
- List which functions/types are actually used externally
- Identify exported symbols that are NEVER imported (dead code candidates)
- Check if internal (unexported) functions should be exported based on usage patterns

### 3. Error Handling Audit
- Functions returning errors without wrapping them
- Ignored error returns (assignments to `_`)
- Panic usage outside of initialization code
- Missing error context

### 4. Concurrency Risks
- Unprotected shared state (non-atomic access to shared variables)
- Channel operations without timeout/context
- Goroutines without synchronization
- Missing mutex locks on shared resources

### 5. Performance Concerns
- Allocations in hot paths (loops, frequently called functions)
- Unbounded slice/map growth
- Excessive lock contention points
- Channel buffer sizes (unbuffered in performance-critical paths)

### 6. Code Quality Issues
- Duplicate logic (similar code blocks in different functions)
- God functions (>100 lines or >5 responsibilities)
- Magic numbers without constants
- Missing documentation on exported symbols

## Output Format

Generate `{directory_path}/.workflows/analysis_report.md`:

```markdown
# Analysis Report: {package_name}
Generated: {timestamp}

## Summary
- Total Functions: X
- Exported Functions: Y
- Complexity Score: Z (avg cyclomatic complexity)
- Dead Code Candidates: N

## Critical Issues
(Issues requiring immediate attention)

## Refactoring Opportunities
(Improvements that would increase maintainability)

## Performance Notes
(Optimization opportunities)

## API Surface Review
### Exported but Unused
- List functions/types

### Should Be Exported
- List internal functions used across packages

## Detailed Findings
(Per-function breakdown)
```

If .workflows/analysis_report.md already exists, UPDATE it with current findings and note what changed since last analysis.
