# Update Package README Command

Analyze the package at `{directory_path}` and create/update `{directory_path}/.workflows/package_readme.md`

## Arguments
- Required: `{directory_path}` (e.g., `chatbot/bowl`)

## Process

### 1. Environment Setup
- Check if `{directory_path}/.workflows/` exists, create if missing
- Identify all `.go` files in the directory (exclude `*_test.go` and `*_benchmark_test.go`)
- Read all source files into memory

### 2. Package Overview
Extract and document:
- Package name (from `package` declaration)
- Package-level documentation (comments above `package` line)
- Purpose: synthesize 2-3 sentence summary of what this package does
- Key responsibilities (what problems does it solve?)

### 3. Exported API Surface

For each exported symbol (starts with capital letter), document:

#### Exported Types
For each `type`:
- Full type signature
- Purpose and usage
- Fields (for structs):
  - Field name, type, and purpose
  - Validation rules or constraints
  - Whether it's required or optional
- Methods associated with this type
- Interface compliance (what interfaces does it implement?)

#### Exported Functions
For each exported function:
- Full signature with parameter and return types
- Purpose (what does it do?)
- Parameter descriptions (what each parameter is for)
- Return value descriptions (including error conditions)
- Side effects (does it modify state, perform I/O, spawn goroutines?)
- Thread safety (safe for concurrent use?)
- Example usage pattern (show typical call)

#### Exported Constants and Variables
- Name, type, value
- Purpose and when to use

### 4. Internal Architecture

#### Unexported Types
For significant internal types (>20 lines or used by multiple functions):
- Type signature
- Purpose within the package
- Relationship to exported types

#### Key Internal Functions
For critical internal functions (>30 lines or called from multiple places):
- Signature
- Purpose
- Why it's not exported

#### Data Flow
Describe how data moves through the package:
- Entry points (which exported functions are typically called first?)
- Processing pipeline (what happens to data internally?)
- Exit points (how does data leave the package?)

### 5. Dependencies

#### External Dependencies
Scan all `import` statements:
- List third-party packages (not stdlib, not from current project)
- For each dependency, explain WHY it's used
- Note if dependency is for interface only vs implementation

#### Internal Dependencies
- List other packages from the current project that this package imports
- Explain what functionality is used from each

#### Stdlib Usage
- List significant stdlib usage (io, context, sync, etc.)
- Note concurrency primitives used (mutexes, channels, waitgroups)

### 6. Reverse Dependencies

Scan the ENTIRE codebase:
- Find all files that import this package
- For each importing package:
  - Package name
  - Which symbols from this package are used
  - Usage pattern (how is this package consumed?)
  
Group by usage frequency:
- Primary consumers (use multiple functions/types)
- Secondary consumers (use 1-2 symbols)
- Test-only consumers (only imported in tests)

### 7. Concurrency Model

If package uses concurrency:
- Goroutine lifecycle (where are they spawned? how do they terminate?)
- Synchronization mechanisms (mutexes, channels, atomic operations)
- Thread-safety guarantees (what's safe to call concurrently?)
- Deadlock risks (blocking operations, lock ordering)
- Resource cleanup (how are goroutines/channels cleaned up?)

If package is NOT concurrent:
- State explicitly: "This package is not designed for concurrent use."

### 8. Error Handling

Document error patterns:
- Custom error types defined in this package
- Sentinel errors (exported `var ErrXxx` values)
- Error wrapping strategy (does it use `fmt.Errorf` with `%w`?)
- Error propagation (how are errors passed up the stack?)
- Panic usage (when does this package panic, if ever?)

### 9. Performance Characteristics

From source code analysis:
- Memory allocation patterns (heavy allocation in hot paths?)
- Expensive operations (I/O, network calls, large computations)
- Caching strategy (if any)
- Optimization notes (what's optimized for?)

If benchmark files exist (`*_benchmark_test.go`):
- Reference benchmark results
- Note performance-critical functions
- Known bottlenecks

DO NOT run benchmarks or copy benchmark code. Just reference their existence.

### 10. Configuration and Initialization

Document:
- How to construct instances of main types
- Required initialization steps
- Configuration options
- Default values and their rationale
- Cleanup/disposal requirements (Close methods, resource cleanup)

### 11. Usage Patterns

Based on reverse dependency analysis and function signatures:
- Common use cases (typical workflows)
- Anti-patterns (how NOT to use this package)
- Edge cases (unusual but valid usage)
- Gotchas (surprising behavior, common mistakes)

### 12. Historical Context

If `package_readme.md` already exists:
- Preserve "Historical Context" section if present
- Add new section: "Recent Changes" with timestamp
- Note what changed since last documentation

If this is initial creation:
- Add section: "Documentation Created: {timestamp}"

## Output Format

Generate `{directory_path}/.workflows/package_readme.md`:

```markdown
# Package: {package_name}

**Location**: `{directory_path}`  
**Last Updated**: {timestamp}

## Overview

{2-3 sentence summary}

**Key Responsibilities:**
- Responsibility 1
- Responsibility 2

## Exported API

### Types

#### {TypeName}
```go
type TypeName struct {
    Field1 Type1 // purpose
    Field2 Type2 // purpose
}
```

Purpose: ...

Methods:
- `Method1() return` - description
- `Method2() return` - description

### Functions

#### {FunctionName}
```go
func FunctionName(param1 Type1, param2 Type2) (ReturnType, error)
```

Purpose: ...

Parameters:
- `param1`: description
- `param2`: description

Returns:
- `ReturnType`: description
- `error`: error conditions

Thread-safety: safe/unsafe for concurrent use

Example usage:
```go
result, err := FunctionName(val1, val2)
if err != nil {
    // handle error
}
```

### Constants

{List constants with purpose}

## Internal Architecture

### Key Internal Types
{Document significant unexported types}

### Data Flow
Entry → Processing → Exit

## Dependencies

### External Packages
- `github.com/pkg/name` - used for {purpose}

### Internal Packages
- `project/pkg/name` - uses {symbols} for {purpose}

### Standard Library
- `context` - cancellation and timeouts
- `sync` - {specific primitives used}

## Reverse Dependencies

### Primary Consumers
- `package/path` - uses {TypeName}, {FunctionName} for {purpose}

### Secondary Consumers
- `package/path` - uses {TypeName} only

## Concurrency

{Describe concurrency model or state "Not designed for concurrent use"}

Thread-safety guarantees:
- {List safe operations}

## Error Handling

Custom errors:
```go
var ErrXxx = errors.New("description")
```

Error wrapping: {Yes/No, strategy}

Panics: {When panics occur, if ever}

## Performance

Allocation patterns: {heavy/light/moderate}

Expensive operations:
- {Operation} - {why expensive}

Benchmark coverage: {Yes/No, reference to benchmark files}

## Usage

### Initialization
```go
instance := NewType(config)
defer instance.Close()
```

### Common Patterns
```go
// Pattern 1: {description}
code example

// Pattern 2: {description}
code example
```

### Gotchas
- Gotcha 1: {description}
- Gotcha 2: {description}

## Notes

{Any additional context, historical notes, future plans}
```

## Update Strategy

If `package_readme.md` exists:
- Read existing content
- Compare with current code state
- Update changed sections
- Preserve "Notes" and "Historical Context" sections
- Add "Recent Changes" section at bottom with timestamp and summary of updates

If significant refactoring occurred:
- Note deprecated patterns in "Notes" section
- Keep old documentation in "Historical Context" section
- Document migration path if API changed

## Do NOT

- Copy test code or test patterns (excluded from analysis)
- Copy benchmark implementation details (only reference existence)
- Document internal implementation details that could change
- Include file paths in code examples
- Add TODO comments or suggest improvements (that's for todos.md)
