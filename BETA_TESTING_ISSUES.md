# Henchman Beta Testing Notes

**Tester**: GitHub Copilot (Claude Opus 4.5)
**Date**: February 2, 2026
**Version Tested**: v0.1.11 (package name: `mlg`)
**CLI Location**: `/home/matthew/mlg-cli`

---

## Overview

Henchman is a model-agnostic AI agent CLI. It supports interactive sessions and headless mode with `--prompt`. This document captures observations, issues, and feedback from beta testing.

---

## CLI Options Discovered

```
Usage: henchman [OPTIONS]

Options:
  --version                       Show the version and exit.
  -p, --prompt TEXT               Run with a single prompt and exit
  --output-format [text|json|stream-json]  Output format for responses
  --plan                          Start in plan mode (read-only)
  --help                          Show this message and exit.
```

---

## Testing Sessions

### Session 1 - Initial Launch (Prior)
- **Command**: `henchman`
- **Working Directory**: `/home/matthew/mlg-cli`
- **Exit Code**: 130 (Ctrl+C interrupt)
- **Status**: ⚠️ Inconclusive - manual interrupt

### Session 2 - Help & Version Check
- **Command**: `henchman --help` and `henchman --version`
- **Result**: ✅ Success - Clean output, proper CLI structure
- **Version**: 0.1.11

### Session 3 - Simple Workspace Query
- **Command**: `henchman -p "What files are in this workspace?"`
- **Result**: ✅ Success - Correctly listed directories and files
- **Tools Used**: `ls()`
- **Iterations**: 1/25

### Session 4 - File Reading & Summarization
- **Command**: `henchman -p "Read .github/copilot-instructions.md and summarize"`
- **Result**: ✅ Success - Read file, provided accurate 2-sentence summary
- **Tools Used**: `read_file()`
- **Quality**: Excellent - understood project context accurately

### Session 5 - Plan Mode (Complex Analysis)
- **Command**: `henchman --plan -p "What tests would you run to validate Elo?"`
- **Result**: ✅ Success - Comprehensive analysis with 10 test categories
- **Tools Used**: `ls()`, `read_file()`, `rag_search()`
- **Iterations**: 14/25
- **Note**: Loop detection triggered at iteration 11 ("⚠ Possible loop detected") but recovered gracefully

### Session 6 - Code Generation (File Creation)
- **Command**: `henchman -p "Create a test file for NBAEloRating"`
- **Result**: ✅ Success - Created valid, working test file
- **Tools Used**: `rag_search()`, `read_file()`, `ls()`, `write_file()`
- **File Created**: `tests/test_henchman_demo.py` (3944 bytes)
- **Test Verification**: Both tests passed when run with pytest!
- **User Interaction**: Required "y/n" confirmation for file write (good safety feature)

### Session 7 - JSON Output Format
- **Command**: `henchman -p "What is 2+2?" --output-format json`
- **Result**: ✅ Success - Streamed JSON tokens properly
- **Note**: Output is token-by-token, final line has full response

### Session 8 - Shell Command Execution
- **Command**: `henchman -p "Run 'echo Hello from Henchman'"`
- **Result**: ✅ Success - Executed command, showed output
- **Tools Used**: `shell()`
- **User Interaction**: Required "y/n" confirmation (good safety feature)

### Session 9 - Multi-Step File Operations
- **Command**: `henchman -p "Find Python files in plugins/elo and count them"`
- **Result**: ✅ Success - Found all 15 Python files correctly
- **Tools Used**: `ls()`, `glob()`, `shell()`
- **Iterations**: 6/35

---

## Issues Found

### Issue #1: Loop Detection Warning (Minor)
- **Severity**: Low
- **Description**: During complex analysis tasks, Henchman triggers "⚠ Possible loop detected" warnings when reading multiple files sequentially.
- **Observed In**: Session 5 (Plan mode analysis)
- **Impact**: None - it recovered and continued successfully
- **Suggestion**: Consider adjusting the loop detection heuristics to differentiate between legitimate sequential file reads and actual loops.

### Issue #2: Version Mismatch Display
- **Severity**: Very Low (cosmetic)
- **Description**: `--version` shows `mlg, version 0.1.11` but product is "Henchman"
- **Expected**: `henchman, version 0.1.11`
- **Impact**: Confusion about package vs. product naming

### Issue #3: JSON Output Token Streaming
- **Severity**: Low
- **Description**: JSON output streams token-by-token which may not be ideal for programmatic consumption
- **Observed**: `{"type": "content", "data": "2"}` per token
- **Suggestion**: Consider a `--output-format json-complete` option for full response in single JSON object

---

## Feature Requests

1. **Non-interactive mode flag**: A `--yes` or `-y` flag to auto-approve tool executions for CI/CD pipelines
2. **Verbosity control**: `--quiet` or `--verbose` flags to control output detail
3. **Session logging**: Option to log full session to file for debugging
4. **Context file**: Ability to specify a context file (like copilot-instructions.md) for automatic project conventions

---

## Positive Observations

### ✅ Excellent Code Quality
The test file Henchman generated was:
- Properly structured with docstrings
- Followed existing project conventions
- Included multiple test cases beyond requirements
- **Actually passed when run with pytest!**

### ✅ Smart Tool Selection
- Uses RAG search for semantic queries
- Falls back to file system operations for concrete tasks
- Chains tools effectively (ls → read_file → write_file)

### ✅ Good Safety Features
- Prompts for confirmation before file writes
- Prompts for confirmation before shell commands
- Clear display of what tool is being called

### ✅ Context Awareness
- Understood project structure quickly
- Read relevant files before generating code
- Matched existing code style and imports

### ✅ Plan Mode
- Excellent for read-only analysis
- Thorough exploration of codebase
- Generates actionable recommendations

### ✅ Progress Indicators
- Shows iteration count (e.g., "[Iter 3/25 | 3 calls | 2K tokens]")
- Indicates token usage and protection status
- Shows "✓ progress" vs "⚠ spinning" status

---

## Comparison Notes

As an agentic coding AI myself, here's my evaluation:

- [x] **Tool Usage**: Excellent - smart tool selection, effective chaining
- [x] **Context Awareness**: Excellent - understands project structure
- [x] **Autonomy**: Good - handles multi-step tasks independently
- [x] **Error Recovery**: Good - recovered from loop detection warnings
- [x] **Code Quality**: Excellent - generated working, idiomatic code
- [x] **Communication**: Good - clear about what it's doing
- [x] **Persistence**: Good - follows through on complex tasks

---

## Testing Checklist

- [x] Basic CLI functionality
- [x] File reading/editing capabilities
- [x] Terminal command execution
- [ ] Multi-file refactoring (not tested yet)
- [ ] Error handling and recovery (partially tested)
- [x] Project-specific conventions
- [ ] Database operations (not tested yet)
- [x] Test execution (generated tests that work!)
- [ ] Long-running task management (not tested yet)

---

## Recommendations for Henchman Team

1. **Fix version string**: Change from `mlg` to `henchman` in `--version` output
2. **Tune loop detection**: Current threshold may be too aggressive for legitimate file exploration
3. **Add batch mode**: For CI/CD integration, add `--yes` flag to skip confirmations
4. **Document tool set**: List available tools (ls, read_file, write_file, shell, rag_search, glob) in docs
5. **Consider token limits**: Show remaining context budget more prominently

---

## Overall Assessment

**Rating: 8.5/10** ⭐⭐⭐⭐

Henchman is a solid, well-designed agentic AI CLI. The headless mode (`-p`) is particularly useful for scripting. Code generation quality is impressive - the test file it created actually worked! The safety features (confirmations for writes/commands) are appropriate for a beta. Minor polish issues exist but don't impact functionality.

**Would recommend for**: Developers who want CLI-based AI assistance for file exploration, code generation, and analysis tasks.

---

## Changelog

| Date | Notes |
|------|-------|
| 2026-02-02 | Created initial beta testing document |
| 2026-02-02 | Completed comprehensive testing - 9 sessions, 3 issues found, overall positive |

---

*Testing complete. Document may be updated with additional findings.*
