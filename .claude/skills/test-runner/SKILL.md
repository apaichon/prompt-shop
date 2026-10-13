---
name: test-runner
description: Use when running tests and updating last_run on test artifacts.
---

# Test Runner

## Steps
1. Identify the test(s) to run (one TEST-XXXX, all tests for a task, or full suite).
2. Run the actual test command. Capture pass/fail.
3. Update each test file's frontmatter `last_run: {date: <today>, result: pass|fail}`.
4. For any fail, invoke `task-progress-update <linked-task-id> blocked` and add a note.
