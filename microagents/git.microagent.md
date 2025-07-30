---
name: Git Microagent
version: 1.0.0
agents:
  - EDIT
  - VCS
triggers:
  - git
  - diff
  - merge
---


# Git Basics: Single-Branch Workflow

This guide covers the essential Git commands for working in a single-branch setup.  
Ideal for simple projects or solo development.

**Important:** Stay on one branch (usually `main`). Avoid merging, rebasing, or branching unless absolutely necessary.


## Initialize a Repository

```bash
git init             # Create a new Git repository
git checkout -b main # Ensure you're on the 'main' branch
```

## Track Changes 

```bash
git status           # View current changes and staging status
git add <file>       # Stage a specific file
git add .            # Stage all changes in the directory
```

## Commit Changes

```bash
git commit -m "Describe your change here"
```

## Review History and Differences

```bash
git log              # Show commit history
git diff             # Show changes not yet staged
git diff --staged    # Show changes staged for the next commit
```

## Undo Changes and Mistakes

```shell
git restore <file>            # Revert changes in the working directory
git restore --staged <file>   # Unstage a file
```

## Other Notes 

- When using `git diff` you will likely only see staged changes. This means that newly created files are not immediately visible until they get staged. 
- Assume your active branch is the main branch, and refrain from using or creating different branches. 
