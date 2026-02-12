# CSC Agent Workflow Guidelines

This document defines the process for an LLM agent when contributing to the Cloud Systems Compiler (CSC) project.

## 1. Project Management & GitHub Integration

Every contribution must be linked to a GitHub Issue and tracked in the GitHub Project board.

### Phase 1: Picking Up Work
- **Find an Issue**: Search for open issues in the `sholtomaud/cloud-systems-compiler` repository using `gh issue list`.
- **Assign Yourself**: Use `gh issue edit <NUMBER> --add-assignee "@me"`.
- **Update Project Status**: Move the corresponding card in Project #17 to "In Progress".

### Phase 2: Branching & Environment
- **Switch Branch**: Every issue has a pre-planned branch name (e.g., `feature/issue-<NUMBER>-<description>`).
- **Checkout**: `git checkout feature/issue-<NUMBER>-...`
- **Verify Specs**: Read the `README.md` (the source of truth) and the detailed requirements in the Issue body.

### Phase 3: Implementation & Verification
- **TDD First**: Write tests to verify the compiler behavior against the specification.
- **Incremental Commits**: Commit logically grouped changes with clear messages.
- **Link PRs**: PR descriptions must include "Closes #<NUMBER>" to automate project movement.

## 2. Technical Philosophy (The "CSC Way")

- **README is the Bible**: The `README.md` contains the architectural vision. Never deviate from it without explicit approval.
- **Zero-Lambda Default**: Prefer VTL and native AWS integrations over custom Lambda code.
- **Compiled Security**: Security is baked into the compiler output (IAM, WAF, Cognito), not configured manually in the source.
- **Local Parity**: Ensure every feature works identically in the `csc dev` emulator as it does in production.

## 3. Tooling
- Use `uv` for Python environment management (if applicable).
- Use `gh` CLI for all GitHub interactions.
- Update `walkthrough.md` and `task.md` artifacts in your brain context to track your specific sub-tasks.
