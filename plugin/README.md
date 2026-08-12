# claudectl — the plugin

The in-session surface of [claudectl](https://github.com/babarmuhammad/claudectl).

```
/plugin marketplace add babarmuhammad/claudectl
/plugin install claudectl@claudectl
```

## What it adds

| | |
|---|---|
| `/claudectl:recall <topic>` | This project's task-relevant memory, scored locally against the topic |
| `/claudectl:status` | Memory age, repositories and worktrees, health checks |
| `/claudectl:review` | Review the current diff against this project's own learned conventions |
| 8 skills | changelog, code-explainer, commit-message, pr-description, refactor-planner, security-review, test-writer, token-economy |

The three commands shell out to the `claudectl` CLI, so install it too:

```
pip install claudectl
```

The skills work without it.

## What it deliberately does NOT add

**Hooks.** claudectl already installs its own — the memory-recall hook, the
worklog capture, the guard hooks — through a manager that places them per
account and can show, repair and remove them. Shipping the same hooks in the
plugin would give two owners to one entry in `settings.json`: installing both
runs the recall hook twice on every prompt, and uninstalling either leaves the
other behind looking broken. Use `claudectl` → Hooks.
