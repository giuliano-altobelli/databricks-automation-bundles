---
name: write-databricks-bundle-tests
description: >
    Design, implement, review, and improve automated tests specifically for the databricks-automation-bundles repository.
    Use when changing repoctl Python code, metadata or evidence schemas, templates, Databricks bundle YAML or SQL, GitHub workflows, justfile commands, or ABAC contracts, and for pytest regressions, CI parity, offline contract validation, flaky tests, coverage gaps, or mocking decisions in this repository.
version: "1.0.0"
user-invocable: true
context: inline
allowed-tools: Bash, Read, Write, Edit, Grep, Glob
---

# Write Databricks Bundle Tests

Build focused, deterministic pytest coverage for this repository while keeping local verification offline and aligned with CI. Make tests correct, thorough, small, understandable, and resilient to refactoring.

## Establish the repository contract

1. Read `pyproject.toml`, `justfile`, the relevant spec or design document, nearby tests, and the implementation or artifact under change.
2. State the observable contract and partition its legal inputs, states, and failures. Include important boundaries and fail-closed security cases.
3. Add a focused failing test before production code when implementing a feature or fixing a bug. Confirm that it fails for the intended reason.
4. Keep executable pytest modules in root `tests/`. Keep bundle-owned JSON input data under `projects/<project>/bundles/<bundle>/tests/fixtures/`.

Do not assume another skill is installed. Apply these invariants directly: test behavior rather than private structure, mock only external boundaries, never synchronize with `sleep`, seed randomness, control time and concurrency, and keep every fixed bug as a regression.

## Match the test to the repository surface

### Test `repoctl` library behavior

- Import functions from `tools/repoctl/src/repoctl` through the configured pytest `pythonpath`.
- Exercise pure logic directly and create miniature repositories with `tmp_path`.
- Partition cases across valid input, missing data, malformed data, unsupported values, boundary paths, and interactions that change results.
- Assert result objects and semantic errors. Avoid coupling tests to private helper calls.

### Test the CLI boundary

- Run the real boundary with `sys.executable -m repoctl.cli`, `capture_output=True`, and `text=True` when testing process behavior.
- Assert the exit code and the relevant JSON, stdout, or stderr contract.
- Use direct `cli.main(...)` with `monkeypatch` and `capsys` only when injecting a boundary failure that a subprocess cannot reproduce safely, such as an operating-system read error.
- Do not mock the CLI behavior being tested.

### Test schemas, metadata, and templates

- Parse JSON and YAML and assert semantic structure, required fields, rejected fields, lifecycle targets, and cross-file invariants.
- Prefer focused structural assertions over whole-file snapshots or incidental formatting checks.
- Materialize templates into `tmp_path`, replace placeholders, and exercise real discovery and validation when testing generated behavior.
- Test mirrored template and dogfood contracts where a change must remain aligned across both.

### Test workflows and command parity

- Parse workflow YAML and normalize shell commands before comparing behavior.
- Preserve parity between `just verify` and CI validation commands.
- Treat triggers, credential isolation, trusted-repository checks, environments, deployment targets, concurrency, and forbidden production paths as security contracts.
- Avoid exact snapshots of an entire workflow when focused invariants express the requirement.

### Test ABAC and SQL contracts

- Keep local pytest offline. Do not require Databricks credentials, workspace state, network access, or a live warehouse.
- Drive contract cases from bundle-owned JSON fixtures and use a fixed clock for validity windows.
- Include allow and deny partitions for missing principals or keys, inactive grants, disallowed access levels, future grants, expiration boundaries, and duplicate or interacting rows.
- Compare SQL policy literals and structure with the offline reference contract when parity is required.
- Report live Databricks validation as a separate integration layer; never imply that offline text inspection proves deployed runtime behavior.

### Test Git behavior

- Initialize an isolated repository under `tmp_path`, configure local test identity, and use real noninteractive Git subprocesses.
- Never depend on or mutate the developer's current worktree, global Git configuration, untracked files, or remote network state.

## Isolate without over-mocking

- Prefer real Python logic, parsers, temporary files, and temporary Git repositories.
- Replace external dependencies at their boundary: network, live Databricks, filesystem failures, clocks, randomness, hardware, or other services.
- Prefer `tmp_path` over mocking normal filesystem behavior.
- Never monkeypatch the `repoctl` function or private helper whose behavior the test is meant to validate.
- Verify calls or ordering only when the interaction is part of a public command, security, or deployment contract.
- Pair a fake or mock with a focused integration or contract test when important wiring would otherwise remain untested.

## Preserve determinism

- Use fixed timestamps and explicit timezone-aware values. Do not read the wall clock inside expected-value logic.
- Never use `sleep`. Coordinate asynchronous or concurrent behavior with explicit events, barriers, or awaited state.
- Sort results before comparison when ordering is not contractual; assert exact order only when it is.
- Control relevant environment variables and process state. Restore them with pytest fixtures.
- Use unique temporary paths and make tests independent of execution order and parallelism.
- Do not weaken a flaky assertion or increase a timeout; remove the uncontrolled input.

## Run the testing loop

1. Run one new or changed test while iterating:

   ```sh
   uv run pytest -q tests/<test_file>.py -k <behavior>
   ```

2. Run the relevant test module after the focused case passes:

   ```sh
   uv run pytest -q tests/<test_file>.py
   ```

3. Run the full test and lint checks:

   ```sh
   uv run pytest -q
   uv run ruff check tools tests
   ```

4. Run the complete local gate before finishing a repository change:

   ```sh
   just verify
   ```

The repository has no configured coverage dependency or threshold. Use partition and branch reasoning to find gaps; do not invent a percentage or add coverage tooling unless the task includes that scope.

## Review before finishing

- Ensure expectations come from a spec, schema, security invariant, or documented behavior rather than the current implementation alone.
- Cover happy paths, important negatives, boundaries, regressions, and meaningful interactions without a redundant Cartesian product.
- Use descriptive `test_<behavior>` names, minimal typed helpers, direct assertions, and useful failure output.
- Keep unit failures local while retaining focused CLI, template, workflow, SQL-contract, and integration-boundary coverage.
- Report the behaviors covered, commands run, results, and any live-system risk that remains unverified.
