# Commit Conventions

This project follows the Conventional Commits format.

## Format

```text
<type>(<scope>): <description>
```

- `type` is required.
- `scope` is optional and identifies the affected application or domain area.
- `description` is required and describes the change.
- Use English for the type, scope and description.
- Write the description in the imperative mood: `add`, `fix`, `remove`, not `added` or `adds`.
- Use lowercase for the type, scope and description.
- Do not end the subject line with a period.
- Keep the subject line short. Put details in the body.

## Types

| Type | Purpose |
| --- | --- |
| `feat` | A new capability or user-facing behaviour. |
| `fix` | A correction to a defect or incorrect behaviour. |
| `refactor` | A code change that neither fixes a bug nor adds a capability. |
| `test` | Adding, changing or reorganising tests. |
| `chore` | Build, tooling, dependency or repository maintenance. |
| `docs` | Documentation only. |

## Scopes

Use the Django application or domain area affected by the change:

- `projects`
- `purchases`
- `inventory`
- `domain` for changes that span purchases and inventory together

Omit the scope when the change is cross-cutting or when no scope adds useful
information.

## Examples

```text
feat(projects): add project archiving
fix(purchases): reject duplicate supplier names
fix: prevent negative recorded balances
refactor(inventory): extract stock movement services
refactor: remove unused template context
test(purchases): cover purchase line receipt limits
chore: pin Django dependency
docs: add commit conventions
```

## Body and footer

Use the commit body to explain what changed and why. Do not use it to repeat
the subject line.

Use the footer for references and breaking changes:

```text
Refs: #12

BREAKING CHANGE: purchase line receipt now requires a catalogue item.
```

A breaking change may also be marked with `!` after the type or scope:

```text
feat(inventory)!: require a reason for every movement cancellation
```

## Rules

- Make one logical change per commit.
- Do not mix refactoring with behaviour changes.
- Keep the test suite green whenever possible.
- Do not commit secrets, `.env`, `db.sqlite3`, `.venv/`, uploads, caches or
  temporary files.
- Do not commit unrelated formatting or generated files with a functional
  change.
