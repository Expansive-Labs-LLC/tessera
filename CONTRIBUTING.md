# Contributing to Tessera

Thank you for your interest in contributing to Tessera! This guide covers everything you need to get started.

## Development Environment Setup

1. **Clone the repository:**
   ```bash
   git clone https://github.com/Expansive-Labs-LLC/tessera.git
   cd tessera
   ```

2. **Create a Python virtual environment:**
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate   # macOS / Linux
   # .venv\Scripts\activate    # Windows
   ```

3. **Install development dependencies:**
   ```bash
   pip install pytest black isort flake8 mypy
   ```

4. **Symlink the add-on into Blender's add-on directory:**
   ```bash
   # Linux
   ln -s "$(pwd)/tessera" ~/.config/blender/4.2/scripts/addons/tessera

   # macOS
   ln -s "$(pwd)/tessera" ~/Library/Application\ Support/Blender/4.2/scripts/addons/tessera

   # Windows (PowerShell, run as Administrator)
   New-Item -ItemType SymbolicLink -Path "$env:APPDATA\Blender Foundation\Blender\4.2\scripts\addons\tessera" -Target "$(Get-Location)\tessera"
   ```

5. **Verify the add-on loads in Blender:**
   - Open Blender → **Edit → Preferences → Add-ons**
   - Search for "Tessera" and enable it
   - Check the Blender console for `Tessera add-on registered`

6. **Run the test suite to confirm your setup:**
   ```bash
   pytest tests/
   ```

## Commit Messages

Tessera uses [Conventional Commits v1.0.0](https://www.conventionalcommits.org/) because automated semantic versioning via `semantic-release` depends on this format. **This is mandatory** — commits that do not follow this format will not trigger releases and may be rejected by CI.

### Format

```
<type>(<scope>): <description>
```

### Allowed Types

| Type | Description | Release Impact |
|------|-------------|----------------|
| `feat` | A new feature | Minor version bump |
| `fix` | A bug fix | Patch version bump |
| `docs` | Documentation changes only | No release |
| `style` | Code style changes (formatting, semicolons) | No release |
| `refactor` | Code changes that neither fix a bug nor add a feature | No release |
| `perf` | Performance improvements | Patch version bump |
| `test` | Adding or updating tests | No release |
| `build` | Build system or dependency changes | No release |
| `ci` | CI/CD configuration changes | No release |
| `chore` | Maintenance tasks | No release |

> **Note:** Additional commit types `spec` and `task` are accepted for specification and task file changes (aligned with the engineering playbook's extended commitlint configuration). These are not required for typical contributions.

### Examples

```bash
# New feature
feat(export): add OBJ export format support

# Bug fix
fix(validator): correct wall thickness calculation for SLA printers

# Documentation
docs(readme): update system requirements table
```

### Breaking Changes

For breaking changes, add `BREAKING CHANGE:` in the commit footer or use `!` after the type:

```bash
feat(api)!: rename BaseAdapter to BaseReconstructionAdapter
```

## Pull Request Process

1. **Fork the repository** and create a feature branch:
   ```bash
   git checkout -b <type>/<short-description>
   ```
   Branch naming convention: `<type>/<short-description>` (e.g., `feat/add-obj-export`, `fix/wall-thickness-calc`).

2. **Make your changes** following the code style guidelines below.

3. **Commit with Conventional Commits** format.

4. **Push your branch** and open a pull request against `main`.

5. **All PR checks must pass** before merge.

6. **At least 1 reviewer must approve** the PR.

7. **Follow the PR template checklist** — it will be pre-populated when you open the PR.

## Testing

### Run the Full Test Suite

```bash
pytest tests/
```

### Run Tests in Blender Headless Mode

```bash
blender --background --python -m pytest tests/
```

### Before Submitting a PR

- All tests must pass.
- Add new tests for any new functionality following the existing `tests/test_*.py` naming pattern.
- Tests should cover both the expected behavior and edge cases.

### Adding New Tests

1. Create a file in `tests/` following the `test_<module>.py` pattern.
2. Use `pytest` fixtures from `tests/conftest.py` for shared setup.
3. Run your new tests to verify they pass before committing.

## Code Style

Tessera follows Python community standards for code formatting and linting.

| Tool | Purpose | Configuration |
|------|---------|---------------|
| **PEP 8** | Style guide | Standard Python conventions |
| **black** | Code formatter | Default settings |
| **isort** | Import sorting | `profile = "black"` |
| **flake8** | Linter | Default settings |
| **mypy** | Type checking (optional) | Default settings |

### Before Committing

```bash
# Format code
black tessera/ tests/
isort tessera/ tests/

# Lint
flake8 tessera/ tests/

# Type check (optional)
mypy tessera/
```

All tool configurations are defined in `pyproject.toml` when applicable.

## Spec Workflow

Tessera uses a **Task → Spec → Implement → Review** workflow for significant changes. This ensures new features and architectural changes are well-documented before code is written.

### When to Create a Spec

- Adding a new pipeline stage or major feature
- Changing public API contracts
- Modifying error handling or validation behavior
- Architectural refactors

### Spec Format

Specifications live in `specs/` and follow this structure:

1. **Metadata** — Spec ID, Task ID, Status, Version, Author
2. **Problem Statement** — Business context, user story, proposed approach
3. **Functional Requirements** — `SHALL` (required), `SHOULD` (recommended), `MAY` (optional)
4. **Constraints** — Hard prohibitions the implementation must follow
5. **Acceptance Criteria** — Given-When-Then format defining "done"
6. **Test Scenarios** — Mapped to acceptance criteria for traceability

### Contributing a Spec Change

When proposing a significant change, update the relevant spec in `specs/` or create a new one following the format above. Reference the spec in your PR description.

## License

By contributing to Tessera, you agree that your contributions will be licensed under the **GPL-2.0-or-later** license.

### License Header for New Files

Every new `.py` file **must** include the following license header:

```python
# SPDX-License-Identifier: GPL-2.0-or-later
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.
```

Documentation content is licensed under [CC-BY-4.0](https://creativecommons.org/licenses/by/4.0/).

## Getting Help

- **Bug reports and feature requests:** [GitHub Issues](https://github.com/Expansive-Labs-LLC/tessera/issues)
- **Questions and discussions:** [GitHub Discussions](https://github.com/Expansive-Labs-LLC/tessera/discussions) (if enabled)
- **Project updates:** Watch this repository for release notifications
