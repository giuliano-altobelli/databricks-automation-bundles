# Databricks DAB Monorepo Foundation: What Shipped

Status: Phase 1a shipped; Phase 1b reconciled in this branch

Source of truth: [Databricks DAB Monorepo Foundation Design](../design-docs/databricks-dab-monorepo-foundation-design.md)

This document explains what has shipped in the lightweight Databricks Asset Bundle monorepo foundation. It is intentionally written from the repository outward: first the repo shape, then metadata contracts, local toolchain, validation commands, and changed-bundle detection.

Phase 1a shipped the repository foundation. Phase 1b has now shipped in this branch as a local/PR-validation/evidence-check/dogfood/template slice. It does not add UAT or production deployment workflows and does not upload CI evidence artifacts.

## Repo Shape

The foundation is organized around one stable scaling unit:

```text
projects/<project>/bundles/<bundle>
```

A `project` is the ownership and review boundary. It groups related bundle work under one accountable area. A `bundle` is the deployable Databricks Asset Bundle boundary. It is the unit the repo can discover, validate, classify as changed, and eventually pass to Databricks bundle commands.

That distinction is the core of the repo shape. The repo is not organized around one global Databricks deployment, one global Python runtime, or one giant shared source tree. It is organized around many small bundle boundaries that can be reasoned about independently.

### What Shipped

The current repository has the Phase 1a foundation shape materialized:

```text
.
├── pyproject.toml
├── uv.lock
├── prek.toml
├── README.md
├── ARCHITECTURE.md
├── docs/
│   ├── adr/
│   ├── design-docs/
│   └── implementation/
├── schemas/
│   ├── bundle.schema.json
│   └── project.schema.json
├── tools/
│   └── repoctl/
├── libs/
│   └── README.md
├── templates/
│   ├── README.md
│   ├── bundle-basic/
│   └── project/
├── projects/
│   └── platform-governance/
│       ├── README.md
│       ├── project.yaml
│       └── bundles/
│           └── foundation-smoke/
│               ├── README.md
│               └── bundle.yaml
└── tests/
    └── test_repoctl_foundation.py
```

The shipped `foundation-smoke` bundle is intentionally inert. It proves that the monorepo can discover and validate project and bundle metadata without creating Databricks assets. It does not contain `databricks.yml`, SQL, UDF source, ABAC policies, or access-map contracts.

Phase 1b also adds the first ABAC dogfood bundle:

```text
projects/platform-governance/bundles/abac-jira-project-access/
```

That bundle owns a focused `SPEC.md`, SQL sources, offline fail-closed contract fixtures, an inert native `databricks.yml`, and `repoctl.bundle.yaml` metadata. It proves the Jira project-key access decision shape offline; it does not deploy live Databricks resources.

Phase 1b also adds `.github/workflows/pr-validation.yml`, documentation-grade schemas under `schemas/evidence/`, and the concrete template at `templates/bundles/abac-access-map/`.

### What Each Area Owns

`pyproject.toml` owns the root Python package metadata and root tooling dependencies. In this foundation, the root package is for repository tooling only. It exposes the `repoctl` console command and configures test and lint behavior.

`uv.lock` owns the locked dependency set for the root tooling environment. It is not a runtime lockfile for every future Databricks bundle.

`prek.toml` owns local pre-commit-style hygiene checks. The shipped hooks cover trailing whitespace, end-of-file fixing, and large-file checks.

`docs/` owns architectural explanation, accepted design decisions, implementation tracking, and this shipped-foundation explanation. It records why the foundation exists and what tradeoffs are intentional.

`schemas/` owns machine-checkable metadata contracts for projects and bundles. These schemas define what `project.yaml`, `repoctl.bundle.yaml`, and metadata-only `bundle.yaml` files are allowed to contain. `schemas/evidence/` documents the CI evidence artifact contract.

`tools/repoctl/` owns the small repository control CLI. `repoctl` discovers projects and bundles, validates metadata, and classifies changed files.

`libs/` owns future explicit shared packages. Phase 1a ships only a README because no shared runtime package has been introduced yet.

`templates/` owns approved scaffolds for adding new projects and bundles. Phase 1a ships neutral templates. Phase 1b adds the concrete `templates/bundles/abac-access-map/` template.

`projects/` owns project-specific bundle areas. Phase 1a ships one project, `platform-governance`, as the first ownership boundary.

`projects/platform-governance/project.yaml` owns metadata for the `platform-governance` project: version, name, owning team, and review policy.

`projects/platform-governance/bundles/foundation-smoke/bundle.yaml` owns metadata for the inert smoke bundle: version, name, type, owning team, review policy, target declarations, and dependency declarations.

`projects/platform-governance/bundles/abac-jira-project-access/repoctl.bundle.yaml` owns the same monorepo metadata shape for the native ABAC dogfood bundle. Native Databricks bundle roots use `repoctl.bundle.yaml` so Databricks CLI sees only `databricks.yml` as the native root config. This keeps bundle.yaml as the legacy metadata-only fallback.

`tests/` owns offline verification for the foundation. These tests cover `repoctl` discovery, validation, and changed-file classification.

### Two Repo-Shape Terms To Understand

`repoctl` is the repository control CLI for this monorepo. It is not the Databricks CLI, and it does not deploy Databricks assets. Its job is to understand this repository's shape and contracts.

The repository now ships four `repoctl` command groups:

- `repoctl discover` finds projects and bundles by reading `projects/<project>/project.yaml` plus either `projects/<project>/bundles/<bundle>/repoctl.bundle.yaml` or legacy metadata-only `projects/<project>/bundles/<bundle>/bundle.yaml`.
- `repoctl validate` checks project and bundle metadata against the foundation rules.
- `repoctl changed --base <ref>` classifies changed files and reports which bundles are affected.
- `repoctl evidence check --bundle <path> --target prod --evidence <run-dir>` validates production-promotion evidence fail-closed.

That is useful because native Databricks bundle tooling understands a single bundle, but this repo needs monorepo-level answers before any Databricks command runs. CI needs to know which bundles exist, whether their metadata is valid, whether a change is docs-only, whether a root contract change affects every bundle, and which bundle paths should be validated or deployed later.

`review.policy` is the metadata field that names the review rule for a project or bundle. In the shipped metadata, the policy is `owner-approval`:

```yaml
review:
  policy: owner-approval
```

Today, this field is a required contract marker. `repoctl validate` confirms that `review.policy` exists and is a non-empty string. It does not yet enforce GitHub approvals, branch protection, or CODEOWNERS behavior.

The field is still useful in Phase 1a because it makes review intent explicit at the same boundary where ownership is declared. Later CI or GitHub workflow enforcement can map `owner-approval` to concrete checks, such as requiring approval from the owning team before a bundle is promoted.

### What This Section Does

The repo shape gives every future Databricks asset a predictable home. A new project belongs under `projects/<project>`. A new deployable unit belongs under `projects/<project>/bundles/<bundle>`.

The shape also separates repo governance from native Databricks bundle behavior. Monorepo metadata lives in `project.yaml`, `repoctl.bundle.yaml`, or metadata-only `bundle.yaml`. Native Databricks bundle configuration lives in `databricks.yml`.

Finally, the shape makes changed-bundle detection possible. Because bundles live at predictable paths, `repoctl` can map changed files to affected bundles. Root contract changes, such as updates under `schemas/`, `templates/`, or `tools/`, can be treated as affecting all bundles.

### In Scope

Repo shape scope in Phase 1a includes:

- the stable `projects/<project>/bundles/<bundle>` layout
- root repo tooling files
- metadata schemas
- the `repoctl` source tree
- neutral project and bundle templates
- one inert `platform-governance` project fixture
- one inert `foundation-smoke` bundle fixture
- offline tests for foundation behavior
- docs and implementation records

### Out Of Scope

Repo shape scope in Phase 1a excludes:

- live Databricks resource deployment
- a real `databricks.yml` bundle
- ABAC SQL, UDFs, policy definitions, or access-map contracts
- GitHub Actions deployment workflows
- UAT or production deployment paths
- production promotion evidence upload
- Unity Catalog audit writes
- broad shared-code synchronization across bundles
- bundle runtime dependencies managed by the root lockfile

### Why This Shape Matters

The main design pressure is scale. The monorepo is expected to hold many projects and many Databricks bundles over time. If everything shared one root runtime, one deployment boundary, or one ownership model, unrelated teams and bundles would interfere with each other.

The shipped shape avoids that by making ownership and deployment explicit:

- project boundary: who owns and reviews this area
- bundle boundary: what deploys and validates together
- root tooling boundary: what operates on the repository as a whole
- shared library boundary: what is deliberately reused across bundles
- documentation boundary: what explains and governs the foundation

The result is lightweight, but not loose. The repo can stay small in Phase 1a while still enforcing the boundaries that future Databricks work will need.

### How To Read A Path In This Repo

The easiest way to understand the repo shape is to classify a path before thinking about the file contents.

If a path starts with `projects/<project>/`, it belongs to one ownership area. In the shipped repo, `projects/platform-governance/` means the work is owned and reviewed by the platform governance boundary.

If a path starts with `projects/<project>/bundles/<bundle>/`, it belongs to one deployable bundle boundary. In the shipped repo, `projects/platform-governance/bundles/foundation-smoke/` means this is bundle-scoped metadata under the platform governance project.

If a path starts with `tools/repoctl/`, it belongs to repo-level automation. Changes here can affect every bundle because `repoctl` is how the repository discovers, validates, and classifies bundle work.

If a path starts with `schemas/`, it belongs to the metadata contract layer. Changes here can affect every project or bundle because they change what valid metadata means.

If a path starts with `templates/`, it belongs to the scaffold layer. Changes here affect how future projects and bundles are created, even if they do not change an existing bundle directly.

If a path starts with `libs/`, it is reserved for explicit shared packages. Phase 1a has no shared runtime package yet, so this is only a placeholder boundary.

If a path starts with `docs/`, it belongs to explanation, design, decisions, or implementation tracking. Docs can be important, but docs-only changes are intentionally treated differently from deploy-affecting bundle changes.

### Concrete Examples

`projects/platform-governance/project.yaml` is project metadata. It tells the repo that `platform-governance` exists and records its owner and review policy.

`projects/platform-governance/bundles/foundation-smoke/bundle.yaml` is bundle metadata. It tells the repo that `foundation-smoke` exists, belongs to `platform-governance`, declares `dev`, `uat`, and `prod` targets, and has no bundle or library dependencies.

`tools/repoctl/src/repoctl/discovery.py` is root automation. It is not part of a Databricks bundle. It teaches the repo how to find projects and bundles.

`schemas/bundle.schema.json` is a contract file. It defines the allowed shape of bundle metadata. A stricter schema can make existing bundle metadata invalid, so schema changes are treated as broadly relevant.

`templates/bundle-basic/bundle.yaml` is a scaffold. It is not an active bundle. It is an approved starting point for creating future bundle metadata.

`uv.lock` is a root tooling lockfile. It is not the dependency lock for every bundle runtime. A future Python-heavy bundle should get its own local lockfile when it needs bundle-specific Python dependencies.

### Repo-Shape Checkpoint

The mental model to keep:

- A project answers: who owns and reviews this area?
- A bundle answers: what deploys and validates together?
- The root tooling answers: how does the repo discover, validate, and classify work?
- Schemas answer: what metadata is valid?
- Templates answer: how do we create the next valid project or bundle?
- Docs answer: why does the foundation work this way?

If those answers are clear, the rest of the foundation becomes easier to reason about. Metadata contracts are just the machine-checkable version of the project and bundle answers. Changed-bundle detection is just path classification plus dependency awareness. CI/CD is just automation that uses those same boundaries.

### What Not To Infer From The Shape

Do not infer that `projects/platform-governance/` is already a live Databricks deployment area. In Phase 1a it is a real project boundary, but it only contains inert metadata.

Do not infer that `foundation-smoke` is a real Databricks bundle. It is a bundle-shaped metadata fixture. Its purpose is to prove discovery, validation, target metadata, and changed-file classification without introducing Databricks assets yet.

Do not infer that every future bundle must be platform governance work. `platform-governance` is the first shipped project boundary because the foundation is being dogfooded against governance work. The layout is intended to support many future projects.

Do not infer that the root `uv.lock` is the dependency source for all bundles. The root lockfile belongs to repo tooling. Bundle runtime dependencies stay bundle-local when they exist.

Do not infer that `libs/` permits casual shared source between bundles. Shared code must become an explicit package with its own tests and dependency relationship. Broad cross-bundle source syncing is intentionally not the default.

Do not infer that templates are active deployed resources. Templates are starting points for future project or bundle creation. They do not count as discovered bundles.

Do not infer that documentation-only changes should trigger deployment work. Docs define and explain the foundation, but changed-bundle detection can treat docs-only edits as non-deploy-affecting.

### Repo-Shape Self-Check

Before moving on, a reader should be able to answer these questions from the path alone:

| Path | Boundary | What it means |
| --- | --- | --- |
| `projects/platform-governance/` | project | Platform governance owns and reviews this area. |
| `projects/platform-governance/project.yaml` | project metadata | The repo can validate the project name, owner, and review policy. |
| `projects/platform-governance/bundles/foundation-smoke/` | bundle | One of two metadata-backed bundles under the platform governance project. |
| `projects/platform-governance/bundles/foundation-smoke/bundle.yaml` | bundle metadata | The repo can validate bundle ownership, targets, and dependencies. |
| `projects/platform-governance/bundles/abac-jira-project-access/` | bundle | The ABAC dogfood bundle under the platform governance project. |
| `projects/platform-governance/bundles/abac-jira-project-access/repoctl.bundle.yaml` | bundle metadata | The repo can validate native-bundle repoctl metadata without confusing the Databricks CLI. |
| `tools/repoctl/` | root tooling | Changes here affect repo-wide discovery, validation, or change classification. |
| `schemas/` | metadata contracts | Changes here affect what project and bundle metadata is valid. |
| `templates/` | scaffolding | Changes here affect how future projects and bundles are created. |
| `libs/` | shared package boundary | Future shared code belongs here only when it is explicit and tested. |
| `docs/` | explanation and decisions | Docs explain the foundation but are not deployable bundle assets. |
| `uv.lock` | root tooling dependencies | The root lockfile supports repo tooling, not every bundle runtime. |

If that table makes sense, the repo-shape section has done its job.

## Planned Review Order

The remaining sections will be expanded after their prior section is reviewed:

- metadata contracts
- local toolchain
- validation commands
- changed-bundle detection
- dependency model
- templates
- CI/CD and evidence phasing
- out-of-scope boundaries

## Metadata Contracts

Metadata contracts are the small YAML files that let the monorepo reason about projects and bundles before it runs any Databricks command.

The repository supports these active metadata contracts:

```text
projects/<project>/project.yaml
projects/<project>/bundles/<bundle>/repoctl.bundle.yaml
projects/<project>/bundles/<bundle>/bundle.yaml
```

Use `repoctl.bundle.yaml` for native Databricks bundle roots that also contain `databricks.yml`. Use `bundle.yaml` as the legacy metadata-only fallback.

The contracts are intentionally lightweight. They do not describe every Databricks resource. They describe the repository facts that every project and bundle must declare so tooling and CI can make consistent decisions.

### What Shipped

The repository ships two schema files:

```text
schemas/project.schema.json
schemas/bundle.schema.json
```

It also ships one active project metadata file:

```yaml
version: 1
name: platform-governance
owner:
  team: platform-governance
review:
  policy: owner-approval
```

And active bundle metadata files with this shape:

```yaml
version: 1
name: foundation-smoke
type: generic
owner:
  team: platform-governance
review:
  policy: owner-approval
targets:
  dev:
    mode: development
    default: true
  uat:
    mode: validation
    ci_only: true
  prod:
    mode: production
    ci_only: true
depends_on:
  bundles: []
  libs: []
```

The same shapes are present in the neutral templates under `templates/project/` and `templates/bundle-basic/`, and in the native ABAC dogfood bundle's `repoctl.bundle.yaml`.

### What Each Metadata File Owns

`project.yaml` owns project-level governance metadata. In Phase 1a, that means:

- `version`: the metadata contract version
- `name`: the project name
- `owner.team`: the team accountable for the project
- `review.policy`: the named review rule for the project

`repoctl.bundle.yaml` or legacy metadata-only `bundle.yaml` owns bundle-level governance metadata. That means:

- `version`: the metadata contract version
- `name`: the bundle name
- `type`: a lightweight bundle category
- `owner.team`: the team accountable for the bundle
- `review.policy`: the named review rule for the bundle
- `targets`: the required `dev`, `uat`, and `prod` target contract
- `depends_on`: declared bundle and library dependencies

The important distinction is that `project.yaml` answers who owns the area, while bundle metadata answers how one deployable unit participates in validation, targeting, and dependency-aware change detection.

### What `repoctl validate` Enforces Today

`repoctl validate` is the current enforcement path for these contracts.

For projects, it enforces:

- only the allowed top-level fields: `version`, `name`, `owner`, and `review`
- all required top-level fields are present
- `version` is `1`
- `name` uses lowercase letters, numbers, and hyphens
- `name` matches the project directory name
- `owner.team` is a non-empty string
- `review.policy` is a non-empty string

For bundles, it enforces:

- only the allowed top-level fields: `version`, `name`, `type`, `owner`, `review`, `targets`, and `depends_on`
- all required top-level fields are present
- `version` is `1`
- `name` uses lowercase letters, numbers, and hyphens
- `name` matches the bundle directory name
- `type` is a non-empty string
- `owner.team` is a non-empty string
- `review.policy` is a non-empty string
- exactly the supported targets are declared: `dev`, `uat`, and `prod`
- `dev` is default development mode
- `uat` is CI-only validation mode
- `prod` is CI-only production mode
- `depends_on` only contains `bundles` and `libs`
- `depends_on.bundles` and `depends_on.libs` are lists of strings

This is deliberately stricter than just checking that YAML parses. Unknown top-level fields are rejected so metadata does not silently drift into undocumented behavior.

### Why The Contract Is Useful

The metadata contract gives CI and local tooling a stable vocabulary.

Without `project.yaml`, the repo can see directories but not ownership or review intent. Without bundle metadata, the repo can see folders but not which folders are actual bundle units, which targets they claim to support, or what dependencies should be considered when a change happens.

The contract also lets the foundation remain Databricks-native. Databricks-specific deployment configuration still belongs in `databricks.yml` when a real bundle appears. The monorepo metadata only adds repository-level facts around that native bundle file.

### Target Contract

Every bundle declares the same three targets:

```text
dev
uat
prod
```

`dev` is the local default. It must be `development` mode and marked `default: true`.

`uat` is a shared validation target. It must be `validation` mode and marked `ci_only: true`.

`prod` is the protected production target. It must be `production` mode and marked `ci_only: true`.

This does not deploy anything by itself. It records the expected target posture so local tooling and future CI can prevent accidental promotion paths from becoming ambiguous.

All three targets are required for every bundle metadata file. A bundle that declares only `dev` and `prod` fails `repoctl validate` because it skips the shared validation lane. The foundation intentionally reserves `uat` from day one so future CI has a consistent non-production target for changed-bundle validation before production promotion.

This does not mean every bundle has a live UAT deployment today. It means every bundle must declare the same target contract so automation can be uniform when deployments are added.

### Dependency Contract

Every bundle declares:

```yaml
depends_on:
  bundles: []
  libs: []
```

In Phase 1a, the validator only checks that both keys exist and are lists of strings. It does not yet resolve whether those strings point to real bundles or libraries.

The contract is still useful because it reserves the shape needed for dependency-aware changed-bundle detection. A future bundle can declare that it depends on another bundle or shared library, and CI can use that declaration to validate dependents when a shared thing changes.

### Review Policy Contract

`review.policy` names the intended review rule. The shipped value is:

```yaml
review:
  policy: owner-approval
```

In Phase 1a, `owner-approval` is a declared policy name, not an implemented approval engine. `repoctl validate` requires the field to exist and be non-empty, but it does not yet check GitHub reviewer identity, CODEOWNERS, branch protection, or PR approval state.

The value is still part of the contract because it records review intent next to ownership. Later enforcement can map `owner-approval` to a concrete GitHub Actions or repository policy.

### In Scope

Metadata contract scope in Phase 1a includes:

- project metadata in `project.yaml`
- bundle metadata in `repoctl.bundle.yaml` or legacy metadata-only `bundle.yaml`
- schema files for project and bundle metadata
- validation that names match directory names
- validation that required fields exist
- validation that unknown top-level fields are rejected
- validation of the required `dev`, `uat`, and `prod` target shape
- dependency declaration shape for future bundle and library dependents
- review policy as declared metadata

### Out Of Scope

Metadata contract scope in Phase 1a excludes:

- validating actual Databricks resource definitions
- requiring `databricks.yml`
- deploying to any target
- enforcing GitHub approval rules from `review.policy`
- resolving dependency strings to real bundle or library paths
- validating service principals, Unity Catalog grants, or ABAC policies
- validating physical SQL, UDF code, or access-map schemas
- modeling every future bundle type
- allowing arbitrary top-level metadata fields without updating the contract

### Metadata Contract Checkpoint

The mental model to keep:

- `project.yaml` tells the repo who owns a project area and how review should be classified.
- bundle metadata tells the repo which bundle units exist and what target/dependency contract they claim. Native Databricks bundle roots use `repoctl.bundle.yaml`; legacy metadata-only `bundle.yaml` remains supported as a fallback.
- schemas document the accepted metadata shape.
- `repoctl validate` enforces the shipped subset of that shape.
- review policy is declared intent today and future enforcement input later.
- dependency declarations reserve the future dependency graph, even though Phase 1a only validates their shape.

If this is clear, the next section, local toolchain, becomes straightforward: the root toolchain exists so developers and CI can run these contract checks consistently.

## Local Toolchain

The local toolchain is the set of root-level commands a developer uses to work on the repository foundation before any Databricks assets are deployed.

Phase 1a standardizes on `uv` as the entry point. Developers use `uv` to create the locked tooling environment and run the repo tools from that environment.

The key point: the root toolchain is for repository operations. It is not the runtime environment for every future Databricks bundle.

### What Shipped

Phase 1a ships:

```text
pyproject.toml
uv.lock
prek.toml
tools/repoctl/
tests/
```

`pyproject.toml` defines the root Python project. It declares Python `>=3.10`, the runtime dependency needed by `repoctl`, the dev tools, and the `repoctl` console script.

`uv.lock` locks the root tooling environment. It makes the root developer and CI environment reproducible.

`prek.toml` defines lightweight hygiene hooks.

`tools/repoctl/` contains the repository control CLI.

`tests/` contains offline tests for the foundation tooling.

### What Each Tool Owns

`uv` owns environment creation and command execution for the root tooling environment.

`pyproject.toml` owns package metadata, dependency declarations, the `repoctl` entry point, and test/lint configuration.

`uv.lock` owns the exact locked package versions for the root tooling environment.

`prek` owns local pre-commit-style hygiene checks. The shipped hooks check trailing whitespace, end-of-file formatting, and accidentally added large files.

`pytest` owns the offline test suite for `repoctl` discovery, validation, and changed-file classification.

`ruff` owns Python linting for the tooling and tests.

`repoctl` owns repository-aware commands: discovery, metadata validation, and changed-file classification.

### Day 0 Bootstrap

For Phase 1a, a new developer only needs the repository checkout and `uv` available on their machine. No Databricks workspace credentials, Databricks CLI setup, GitHub Actions secrets, or Unity Catalog access are required to bootstrap this foundation locally.

From the repository root, the Day 0 bootstrap is exactly:

```bash
uv sync --locked --all-extras --dev
uv run prek -c prek.toml install
```

The first command creates or updates the root tooling environment from `uv.lock`. The second command installs the local hygiene hooks configured in `prek.toml`.

After those two commands, the developer has the local repo tooling installed, including `repoctl`, `pytest`, `ruff`, and `prek`.

### Bootstrap Command Details

The root bootstrap command is:

```bash
uv sync --locked --all-extras --dev
```

This installs the root environment from `uv.lock`. The `--locked` flag matters because it prevents accidental dependency resolution drift during normal bootstrap.

The hook install command is:

```bash
uv run prek -c prek.toml install
```

This installs the configured local hooks using the same root tooling environment.

### Local Verification Commands

Bootstrap and verification are different steps. The two Day 0 bootstrap commands set up the environment. The verification commands prove the setup and repository contracts are working.

The shipped README records the local verification loop:

```bash
uv run pytest -q
uv run ruff check tools tests
uv run prek -c prek.toml run --all-files
uv run repoctl discover
uv run repoctl validate
uv run repoctl changed --base HEAD
```

Each command checks a different layer:

- `pytest` checks the behavior of the foundation tooling.
- `ruff` checks Python source and tests.
- `prek` checks repository file hygiene.
- `repoctl discover` checks that projects and bundles can be found.
- `repoctl validate` checks metadata contracts.
- `repoctl changed --base HEAD` checks changed-file classification against the current worktree.

### Phase 1b Shipped: `just` Recipes

Phase 1b adds a root `justfile` as an ergonomic command layer over the raw `uv` commands.

The shipped recipes are:

```make
bootstrap:
    uv sync --locked --all-extras --dev
    uv run prek -c prek.toml install

verify:
    uv run pytest -q
    uv run ruff check tools tests
    uv run prek -c prek.toml run --all-files
    uv run repoctl discover
    uv run repoctl validate
    uv run repoctl changed --base HEAD
```

The preferred Day 0 path is:

```bash
just bootstrap
just verify
```

The raw `uv` commands remain documented as the fallback and as the underlying source of truth.

### Why The Root Toolchain Is Useful

The root toolchain gives every developer the same local entry point. A new developer does not need to guess which Python version, which linter, which test command, or which repo validation command to run.

It also creates a clean separation between repository governance and Databricks bundle runtime code. The root environment can evolve to support repo validation and CI without forcing every bundle to share the same Python dependency set.

That separation is important for scale. A future dbt bundle, MLflow bundle, SQL-only bundle, and governance UDF bundle may have different runtime dependencies. They should not all fight over one root runtime lockfile.

### Root Tooling Versus Bundle Runtime

The root environment owns tools such as:

- `repoctl`
- `prek`
- `pytest`
- `ruff`
- YAML parsing used by repo metadata tooling

A future bundle-local environment owns bundle-specific runtime or test dependencies, such as Python packages needed by that bundle's code.

Pure SQL or config-only bundles may not need a bundle-local Python environment at all.

### In Scope

Local toolchain scope in Phase 1a includes:

- root `uv` bootstrap
- a locked root `uv.lock`
- `repoctl` as an installed console script
- `prek` hook configuration
- `pytest` foundation tests
- `ruff` lint configuration
- local commands for discovery, validation, and changed-file classification
- offline verification without live Databricks resources

Phase 1b local-toolchain scope adds:

- a root `justfile`
- `just bootstrap` as the ergonomic wrapper for Day 0 setup
- `just verify` as the ergonomic wrapper for local verification
- documentation that keeps raw `uv` commands available as fallback
- documentation for the new `just` prerequisite

### Out Of Scope

Local toolchain scope in Phase 1a excludes:

- installing or configuring Databricks workspace credentials
- deploying Databricks bundles
- validating live Databricks resources
- managing runtime dependencies for every future bundle from the root lockfile
- creating bundle-local `pyproject.toml` or `uv.lock` files before a bundle needs them
- enforcing GitHub Actions workflows locally
- uploading evidence artifacts
- writing audit evidence to Unity Catalog

### Local Toolchain Checkpoint

The mental model to keep:

- `uv` gives the repo one repeatable way to install and run root tools.
- `uv.lock` freezes only the root tooling environment.
- `prek`, `pytest`, and `ruff` check hygiene, behavior, and Python quality.
- `repoctl` is run from the root environment because it validates repo contracts.
- bundle runtime dependencies stay out of the root environment unless they are truly repo tooling dependencies.

If this is clear, the next section, validation commands, can focus on what each command proves and when to run it.

## Validation Commands

Validation commands are the local checks that prove the Phase 1a foundation is internally consistent.

They are not Databricks deployment commands. They do not contact a workspace, validate live Unity Catalog permissions, deploy bundles, run SQL, or test ABAC policy behavior. They validate the repository foundation: Python tooling, file hygiene, metadata contracts, discovery, and changed-file classification.

### What Shipped

Phase 1a ships this validation loop:

```bash
uv run pytest -q
uv run ruff check tools tests
uv run prek -c prek.toml run --all-files
uv run repoctl discover
uv run repoctl validate
uv run repoctl changed --base HEAD
```

These commands are intentionally offline. They can run after Day 0 bootstrap without Databricks credentials.

### What Each Command Owns

`uv run pytest -q` owns behavioral verification for the foundation code. It runs the tests under `tests/`, including discovery, metadata validation, and changed-file classification behavior.

`uv run ruff check tools tests` owns Python lint validation for the repo tooling and tests. It checks code quality rules configured in `pyproject.toml`.

`uv run prek -c prek.toml run --all-files` owns repository hygiene validation. The shipped hooks check trailing whitespace, end-of-file formatting, and accidentally added large files.

`uv run repoctl discover` owns discovery validation. It proves the repo can find active projects and bundles from the expected metadata paths.

`uv run repoctl validate` owns metadata contract validation. It proves discovered `project.yaml`, `repoctl.bundle.yaml`, and legacy metadata-only `bundle.yaml` files satisfy the shipped metadata rules.

`uv run repoctl changed --base HEAD` owns local changed-file classification. It proves `repoctl` can compare the current worktree to a base ref and classify the result as docs-only, bundle-specific, or all-bundles-affecting.

### What Each Command Proves Today

`pytest` proves the expected behavior is covered by automated tests. In Phase 1a, those tests cover:

- discovery finds the `projects/<project>/bundles/<bundle>` scaling unit
- minimal project and bundle metadata is accepted
- missing required targets are rejected
- unknown metadata fields are rejected
- invalid metadata names are rejected
- docs-only changes are non-deploying
- bundle-local changes map to that bundle
- root tooling changes affect all bundles
- CLI output and error behavior work as expected

`ruff` proves the Python implementation and tests pass the configured lint rule set.

`prek` proves the tracked files satisfy the configured file-hygiene hooks.

`repoctl discover` proves the current repository has one project, `platform-governance`, and two bundles: `foundation-smoke` and `abac-jira-project-access`.

`repoctl validate` proves the active metadata files satisfy the Phase 1a metadata contract.

`repoctl changed --base HEAD` proves the changed-file classifier can inspect committed, staged, unstaged, and untracked changes against `HEAD`.

### When To Run Them

Run the full validation loop after Day 0 bootstrap to prove the local setup works.

Run the full loop before opening a pull request that changes foundation code, schemas, templates, metadata, or docs.

Run `repoctl validate` after editing `project.yaml`, `repoctl.bundle.yaml`, legacy metadata-only `bundle.yaml`, or the metadata validator.

Run `repoctl discover` after adding, removing, or renaming a project or bundle directory.

Run `repoctl changed --base HEAD` when checking how local changes will be classified. In CI, the base ref will normally be a branch base such as `origin/main`.

### In Scope

Validation command scope in Phase 1a includes:

- offline Python tests for foundation behavior
- Python linting for `tools/` and `tests/`
- file hygiene checks through `prek`
- project and bundle discovery checks
- project and bundle metadata validation
- changed-file classification against a Git base ref
- explicit docs-only classification
- explicit all-bundles classification for root tooling and contract paths

### Out Of Scope

Validation command scope in Phase 1a excludes:

- `databricks bundle validate`
- `databricks bundle deploy`
- workspace authentication checks
- live Databricks API calls
- Unity Catalog grant validation
- ABAC policy SQL validation
- UDF runtime validation
- promotion evidence validation
- GitHub Actions status checks
- approval or review-policy enforcement

### Validation Command Checkpoint

The mental model to keep:

- Bootstrap sets up the local toolchain.
- Validation proves the local foundation is coherent.
- `pytest`, `ruff`, and `prek` check code and repository hygiene.
- `repoctl discover`, `repoctl validate`, and `repoctl changed` check monorepo contracts.
- Passing Phase 1a validation does not mean anything has been deployed to Databricks.

If this is clear, the next section, changed-bundle detection, can go deeper on how `repoctl changed` maps file paths to affected bundles.

## Changed-Bundle Detection

Changed-bundle detection is how the monorepo decides which bundles are affected by a set of file changes.

In Phase 1a, this is implemented by:

```bash
uv run repoctl changed --base <ref>
```

The command compares Git changes against a base ref, adds staged, unstaged, and untracked files, and classifies the result. It does not deploy anything. It produces JSON that later CI can use to decide which bundle validations or deployments should run.

### What Shipped

Phase 1a ships path-based changed-file classification in `tools/repoctl/src/repoctl/changes.py`.

The output shape is:

```json
{
  "changed_files": [],
  "changed_bundles": [],
  "docs_only": false,
  "affects_all_bundles": false
}
```

The command discovers active bundles first, then maps changed paths to those discovered bundle paths.

### What The Command Reads

`repoctl changed --base <ref>` reads four Git views:

- committed changes between `<ref>` and `HEAD`
- staged files
- unstaged files
- untracked files that are not ignored

That matters for local development. A developer does not need to commit a file before checking how `repoctl` will classify it.

### Classification Rules

If there are no changed files, the result has no changed bundles, `docs_only: false`, and `affects_all_bundles: false`.

If every changed file is documentation, the result is docs-only:

```text
docs/
README.md
ARCHITECTURE.md
```

Docs-only changes produce:

```json
{
  "changed_bundles": [],
  "docs_only": true,
  "affects_all_bundles": false
}
```

If any changed file is a root contract, tooling, template, shared-code, or CI path, the change affects all discovered bundles:

```text
libs/
schemas/
templates/
tools/
.github/
pyproject.toml
uv.lock
prek.toml
```

All-bundles changes produce `affects_all_bundles: true` and list every discovered bundle in `changed_bundles`.

If a changed file is under a discovered bundle directory, that bundle is marked changed.

For example:

```text
projects/platform-governance/bundles/foundation-smoke/resources/job.yml
```

maps to:

```text
projects/platform-governance/bundles/foundation-smoke
```

If a project's `project.yaml` changes, every discovered bundle under that project is marked changed. Project metadata can change ownership or review context for all bundles in that project, so Phase 1a treats it as project-wide.

### Why This Is Useful

Changed-bundle detection keeps CI from treating every pull request as a full monorepo deployment event.

It gives the repo a way to answer:

- Is this change docs-only?
- Does this change affect one bundle?
- Does this change affect every discovered bundle?
- Which bundle paths should later validation or deployment commands receive?

That matters as the monorepo scales. Without changed-bundle detection, every future bundle would pay the validation cost for unrelated changes.

### Current Phase 1a Limits

Phase 1a changed-bundle detection is path-based.

It does not yet resolve dependency strings from `depends_on.bundles` or `depends_on.libs` into a full dependency graph.

It does not yet distinguish between different files inside `libs/`, `schemas/`, `templates/`, or `tools/`; any change under those paths affects all discovered bundles.

It does not inspect Databricks asset contents. A bundle-local README and a bundle-local resource file are both treated as bundle-local changes if they live under the bundle path.

It does not run `databricks bundle validate`. It only reports which bundle paths are affected.

### In Scope

Changed-bundle detection scope in Phase 1a includes:

- collecting committed, staged, unstaged, and untracked Git changes
- discovering active bundles from metadata
- classifying docs-only changes
- classifying root tooling and contract changes as all-bundles-affecting
- classifying bundle-local changes to the owning bundle
- classifying project metadata changes to all bundles under that project
- emitting JSON for later CI use

### Out Of Scope

Changed-bundle detection scope in Phase 1a excludes:

- resolving declared dependency strings to real dependent bundles
- building a full bundle dependency graph
- validating Databricks bundle contents
- deploying changed bundles
- deciding production promotion eligibility
- uploading evidence artifacts
- differentiating high-risk and low-risk files inside a bundle path
- per-template or per-schema impact analysis

### Changed-Bundle Detection Checkpoint

The mental model to keep:

- `repoctl changed` starts with Git file paths.
- It discovers active bundles from metadata.
- Docs-only changes skip bundle impact.
- Root tooling, schemas, templates, shared libraries, lockfiles, and CI config affect all discovered bundles.
- Bundle-local paths affect that bundle.
- Project metadata changes affect every bundle in that project.
- The output is a routing decision for future validation and CI, not a deployment.

If this is clear, the next section, dependency model, can explain why the root lockfile stays scoped to tooling and how future bundle-local dependencies should work.

## Dependency Model

The dependency model defines which Python environment owns which dependencies.

The rule is simple: the root `uv` environment is for repository tooling only. It is not the shared runtime environment for every future Databricks bundle.

### What Shipped

Phase 1a ships one root Python project:

```text
pyproject.toml
uv.lock
```

The root `pyproject.toml` declares:

- Python `>=3.10`
- `pyyaml` as the runtime dependency needed by `repoctl`
- `repoctl` as a console script
- `prek`, `pytest`, and `ruff` as dev dependencies
- test and lint configuration for the foundation tooling

The root `uv.lock` locks those root tooling dependencies.

There are no bundle-local `pyproject.toml` or `uv.lock` files in Phase 1a. The shipped `foundation-smoke` bundle is metadata-only and intentionally has no runtime dependencies.

### What Each Dependency Boundary Owns

The root environment owns repository operations:

- running `repoctl`
- running `prek`
- running `pytest`
- running `ruff`
- parsing YAML metadata for repo validation
- supporting shared test helpers for repository contracts

A bundle-local environment owns bundle-specific runtime or test dependencies when a bundle needs them.

A shared library environment owns dependencies for an explicit shared package under `libs/` when such a package exists.

### Why The Root Lockfile Is Narrow

The root `uv.lock` must stay narrow because this repo is meant to hold many bundles over time.

If every bundle put its runtime dependencies into the root lockfile, unrelated bundle work would interfere with other teams. A small SQL-only bundle, a dbt bundle, an MLflow bundle, a Spark streaming bundle, and a governance UDF bundle could all force lockfile churn for each other.

Keeping the root lockfile scoped to tooling makes root bootstrap predictable and keeps bundle dependency changes local to the bundle that needs them.

### Future Bundle Dependency Rule

A future bundle gets its own `pyproject.toml` and `uv.lock` only when it needs Python runtime or Python test dependencies.

For example:

```text
projects/<project>/bundles/<bundle>/
├── repoctl.bundle.yaml
├── databricks.yml
├── pyproject.toml
├── uv.lock
├── resources/
├── sql/
└── tests/
```

Pure SQL or configuration-only bundles do not need bundle-local Python metadata.

The root environment should not be used as the source of bundle runtime packages.

### Shared Library Dependency Rule

Shared code is allowed only through explicit, tested packages under `libs/`.

A future shared package should own its own package metadata, tests, and lockfile:

```text
libs/
  databricks_platform/
    pyproject.toml
    uv.lock
    src/
    tests/
```

Bundles should depend on shared packages deliberately. Broad cross-bundle Databricks `sync.paths` should not become the default sharing mechanism.

### Relationship To Changed-Bundle Detection

Dependency boundaries affect changed-bundle detection.

In Phase 1a, any change under `libs/` affects all discovered bundles because `repoctl` does not yet resolve a dependency graph.

The metadata contract already reserves this future shape:

```yaml
depends_on:
  bundles: []
  libs: []
```

Later phases can use those declarations to move from broad all-bundles impact to dependency-aware impact.

### In Scope

Dependency model scope in Phase 1a includes:

- root `pyproject.toml` for repository tooling
- root `uv.lock` for repository tooling
- root dev dependencies for `prek`, `pytest`, and `ruff`
- root runtime dependency for `repoctl`
- documenting that bundle runtime dependencies are bundle-local and optional
- documenting that shared libraries must be explicit, tested packages
- leaving pure SQL/config bundles free of Python metadata unless needed

### Out Of Scope

Dependency model scope in Phase 1a excludes:

- bundle-local dependency files for the inert `foundation-smoke` bundle
- centralizing all future bundle runtime dependencies in the root lockfile
- creating shared library packages before they are needed
- resolving `depends_on` declarations to exact package paths
- publishing shared packages
- managing Databricks cluster, job, or workspace library installation
- using broad cross-bundle `sync.paths` as the default code-sharing strategy

### Dependency Model Checkpoint

The mental model to keep:

- root dependencies are for repo tooling
- bundle dependencies are local to bundles when bundles need them
- shared library dependencies are local to explicit shared packages
- pure SQL/config bundles can have no Python dependency files
- the root lockfile should stay stable when unrelated bundle runtimes change

If this is clear, the next section, templates, can explain how future projects and bundles should be scaffolded without violating these boundaries.

## Templates

Templates define the approved starting shapes for new projects and bundles.

Phase 1a ships neutral templates. They help create valid metadata boundaries without introducing Databricks asset files too early. Phase 1b ships the concrete ABAC access-map template for the first dogfood bundle family.

### What Shipped

The shipped template directory is:

```text
templates/
├── README.md
├── project/
│   ├── README.md
│   └── project.yaml
├── bundle-basic/
│   ├── README.md
│   └── bundle.yaml
└── bundles/
    └── abac-access-map/
        ├── README.md
        ├── SPEC.md
        ├── repoctl.bundle.yaml
        ├── databricks.yml
        ├── sql/
        └── tests/
```

`templates/README.md` explains that Phase 1a includes neutral project and bundle metadata templates, while Phase 1b adds `templates/bundles/abac-access-map/` with repoctl metadata, inert native Databricks bundle configuration, SQL placeholders, and offline contract-test fixtures.

### Project Template

The project template is:

```yaml
version: 1
name: example-project
owner:
  team: example-team
review:
  policy: owner-approval
```

It is used when adding a new ownership and review boundary under:

```text
projects/<project>/
```

The template gives the new project the required metadata shape, but the placeholder values must be replaced. In a real project, `name` must match the project directory name.

### Basic Bundle Template

The basic bundle template is:

```yaml
version: 1
name: example-bundle
type: generic
owner:
  team: example-team
review:
  policy: owner-approval
targets:
  dev:
    mode: development
    default: true
  uat:
    mode: validation
    ci_only: true
  prod:
    mode: production
    ci_only: true
depends_on:
  bundles: []
  libs: []
```

It is used when adding neutral bundle metadata under:

```text
projects/<project>/bundles/<bundle>/
```

The template creates the monorepo governance metadata shape. It does not create a native Databricks bundle yet.

### What Templates Do

Templates reduce copy-paste mistakes when adding new project or bundle boundaries.

They make the required metadata obvious:

- versioned metadata contract
- lowercase hyphenated names
- owning team
- review policy
- required bundle targets
- dependency declaration shape

They also make the intended sequence explicit: use neutral templates for generic metadata boundaries, and use concrete templates only when a shipped bundle family has a focused contract.

### What Templates Do Not Do

Templates are not active projects or active bundles.

`repoctl discover` does not discover templates as deployable units because templates are outside `projects/`.

Templates do not validate themselves through `repoctl validate` as active metadata. They are examples and scaffolds.

Neutral Phase 1a templates do not create `databricks.yml`, SQL, UDF code, resources, or tests for a real Databricks workload. The Phase 1b ABAC access-map template includes inert `databricks.yml`, SQL placeholders, and offline fixture/test scaffolding, but still creates no live Databricks resources.

Templates do not install dependencies or create lockfiles.

### Phase 1b Template Shipped

Phase 1b ships the concrete ABAC access-map template:

```text
templates/bundles/abac-access-map/
```

That template belongs with the ABAC dogfood bundle work because it needs concrete access-map conventions and Databricks asset structure that Phase 1a intentionally deferred.

Other future bundle templates are still out of scope until a specific bundle family needs them.

### In Scope

Template scope in Phase 1a includes:

- neutral project scaffold
- neutral bundle metadata scaffold
- README guidance for template purpose
- metadata shapes aligned with `project.yaml`, `repoctl.bundle.yaml`, and legacy metadata-only `bundle.yaml`
- placeholders that make required fields visible

### Out Of Scope

Template scope in Phase 1a excludes:

- ABAC-specific bundle templates
- `databricks.yml`
- SQL files
- UDF source
- access-map contracts
- Databricks resource files
- bundle-local dependency files
- generating files through a scaffold command
- validating template placeholders as active repo metadata

### Template Checkpoint

The mental model to keep:

- templates are approved starting points, not active bundle units
- Phase 1a templates are metadata-only
- copied template values must be renamed to match real directories
- Phase 1b adds the concrete ABAC access-map template, still with no live Databricks deployment
- templates should preserve the project/bundle/dependency boundaries already described

If this is clear, the next section, CI/CD and evidence phasing, can explain which automation has shipped and which enforcement remains pending.

## CI/CD And Evidence Phasing

CI/CD and evidence are part of the foundation design, but they are not fully implemented in Phase 1a.

Phase 1a shipped the local contracts that CI will eventually run:

- root `uv` tooling
- `prek` configuration
- `repoctl discover`
- `repoctl validate`
- `repoctl changed`
- metadata schemas
- target metadata for `dev`, `uat`, and `prod`

It did not ship GitHub Actions workflows, UAT deployment, production deployment, or evidence artifact upload.

### What Shipped

Phase 1a shipped no `.github/` workflow files.

It shipped the local command surface that a future workflow can call:

```bash
uv sync --locked --all-extras --dev
uv run prek -c prek.toml run --all-files
uv run repoctl validate
uv run repoctl changed --base <ref>
```

It also shipped bundle target metadata that records the intended control split:

- `dev`: local default development target
- `uat`: CI-only validation target
- `prod`: CI-only production target

Those target declarations are metadata only in Phase 1a. They do not deploy anything.

### Phase 1b CI Shipped

Phase 1b adds the first GitHub Actions enforcement workflow:

```text
.github/workflows/pr-validation.yml
```

The shipped pull request workflow is:

1. Bootstrap the root `uv` tooling environment.
2. Run the same verification commands as `just verify`: `pytest`, `ruff`, `prek`, `repoctl discover`, `repoctl validate`, and changed-bundle computation.
3. Write changed-bundle output into the GitHub Actions job summary.

The Phase 1b delivery also includes:

- `repoctl evidence check --bundle <path> --target prod --evidence <run-dir>`
- documentation-grade evidence schemas in `schemas/evidence/`
- the ABAC dogfood bundle
- the concrete `abac-access-map` template
- the root `justfile` with `just bootstrap` and `just verify`

This phase does not run UAT or production deployment workflows, does not upload CI evidence artifacts, and does not perform promotion automation.

### Later UAT And Production TODO

The design keeps UAT and production deployment workflows after Phase 1b.

The intended UAT workflow is:

1. Deploy changed bundles to `uat` through CI.
2. Run dogfood-specific tests or contract checks.
3. Upload the evidence artifact.

The intended production workflow is:

1. Require approval or an explicit release trigger.
2. Validate promotion-decision evidence.
3. Deploy changed bundles to `prod`.

This phasing matters because Phase 1a is contract-first. The repo needs reliable local discovery, validation, and changed-bundle detection before CI starts making deployment decisions.

### Evidence Contract

The design says Phase 1 evidence should be persisted to GitHub Actions artifact storage, not committed to the repo.

The intended artifact layout is:

```text
GitHub Actions artifact:
  evidence/
    <run-id>/
      repo-validation.json
      changed-bundles.json
      bundle-validate-<target>.json
      abac-contract-tests.json
      promotion-decision.json
```

Phase 1a does not generate this artifact layout yet. It only records the design expectation.

Phase 1b ships documentation-grade schemas under `schemas/evidence/` for the evidence shape. CI-generated evidence files should not be checked in.

### What CI/CD Owns

Future GitHub Actions workflows own repeatable enforcement of the same local commands developers run manually.

Pull request CI owns repository validation and changed-bundle routing.

UAT CI owns shared validation deployment and evidence creation.

Production CI owns release gating, promotion evidence checks, and protected production deployment.

`repoctl` owns repo-aware coordination inputs for CI, but it should not become a general Databricks deployment framework.

### What Evidence Owns

Evidence owns the machine-readable record of what CI checked and why a promotion decision was allowed.

The design separates evidence storage from source code:

- source repo stores contracts, schemas, tooling, and docs
- GitHub Actions artifact storage stores run-specific evidence
- Unity Catalog audit writes are deferred

That separation avoids committing generated run artifacts while still giving production promotion an auditable trail.

### In Scope

CI/CD and evidence scope in Phase 1a includes:

- documenting GitHub Actions as the assumed CI/CD system
- local commands intended for future PR workflow reuse
- target metadata that marks `uat` and `prod` as CI-only
- changed-bundle detection output for future workflow routing
- design-level evidence artifact layout
- explicit deferral of evidence upload and deployment workflows

Phase 1b delivered scope adds:

- PR validation workflow
- `repoctl evidence check`
- ABAC dogfood validation needs
- concrete ABAC access-map template
- `just bootstrap` and `just verify` wrappers

Later scope includes:

- UAT deployment workflow
- production deployment workflow
- CI evidence artifact upload

### Out Of Scope

CI/CD and evidence scope in Phase 1a excludes:

- `.github/` workflows
- live Databricks deployment
- `databricks bundle validate` in CI
- UAT deployment
- production deployment
- production approval enforcement
- evidence artifact generation
- evidence artifact upload
- writing evidence to `prod_security.access_audit`
- checking accidental direct consumer grants on `prod_security.access_maps` or `prod_security.access_audit`

### CI/CD And Evidence Checkpoint

The mental model to keep:

- Phase 1a shipped local contracts and commands, not GitHub Actions workflows.
- `dev`, `uat`, and `prod` are declared now so future CI has a target contract.
- Phase 1b starts enforcement with PR validation and production evidence checking.
- UAT/prod deployment workflows and artifact upload come after Phase 1b.
- Evidence belongs in GitHub Actions artifact storage, not in committed repo files.

If this is clear, the next section, out-of-scope boundaries, can consolidate what Phase 1a deliberately does not attempt to solve.

## Out-Of-Scope Boundaries

Out-of-scope boundaries explain what Phase 1a deliberately does not attempt to solve.

This matters because the repository now has real tooling, metadata, templates, and validation commands. Those pieces can make the foundation feel more complete than it is. Phase 1a is still a local, lightweight, contract-focused foundation. It is not yet a live Databricks deployment system.

### What Phase 1a Owns

Phase 1a owns the local foundation:

- repository shape
- metadata contracts
- root tooling environment
- local validation commands
- changed-bundle detection
- neutral templates
- inert sample project and bundle metadata
- offline tests
- documentation of the accepted design

That is enough to let the repo define and validate its own boundaries before real Databricks assets arrive.

### What Phase 1a Does Not Own

Phase 1a does not own live Databricks execution:

- no live Databricks resource creation
- no `databricks.yml`
- no `databricks bundle validate`
- no `databricks bundle deploy`
- no SQL deployment
- no UDF deployment
- no access-map table deployment
- no workspace authentication flow

Phase 1a does not own the ABAC dogfood bundle:

- no `projects/platform-governance/bundles/abac-jira-project-access/`
- no ABAC bundle `SPEC.md`
- no final Jira access-map DDL
- no final ABAC policy SQL
- no final UDF implementation
- no ABAC contract tests or fixtures

Phase 1a does not own CI/CD enforcement:

- no `.github/` workflows
- no pull request validation workflow
- no UAT workflow
- no production workflow
- no GitHub approval enforcement
- no production release trigger

Phase 1a does not own evidence generation:

- no evidence artifact upload
- no `repoctl evidence check`
- no `promotion-decision.json`
- no CI-generated evidence files
- no writes to `prod_security.access_audit`
- no Unity Catalog audit evidence path

Phase 1a does not own platform infrastructure:

- no migration of the external `databricks-infra` Terraform repository
- no Unity Catalog grant changes
- no service principal creation
- no governed tag creation
- no workspace or account setup
- no multi-workspace rollout design beyond compatibility

Phase 1a does not own a full access workflow:

- no access request system
- no approval ledger implementation
- no revocation workflow
- no consumer-facing audit views
- no direct-consumer grant checks for `prod_security.access_maps` or `prod_security.access_audit`

### Why These Boundaries Exist

The foundation is intentionally sequenced.

First, the repo needs to know how to structure projects and bundles.

Then, it needs metadata contracts that can be validated locally.

Then, it needs changed-bundle detection so CI can eventually avoid treating every change as global.

Only after those contracts exist should the repo add real Databricks bundles, CI deployment paths, production evidence gates, and ABAC-specific implementation details.

This sequencing keeps Phase 1a small enough to verify offline while preserving the boundaries needed for later deployment work.

### What Phase 1b Adds

Phase 1b is the enforcement and dogfood slice delivered in this branch.

It adds:

- root `justfile` with `just bootstrap` and `just verify`
- PR-validation GitHub Actions workflow
- `repoctl evidence check`
- ABAC dogfood bundle
- focused ABAC dogfood `SPEC.md`
- concrete `abac-access-map` template

Phase 1b starts using the Phase 1a foundation for real enforcement, but still does not solve every future Databricks bundle family.

### What Comes After Phase 1b

After Phase 1b, later work can add:

- UAT deployment workflow
- production deployment workflow
- GitHub Actions evidence upload
- production promotion evidence artifacts
- broader dependency-aware changed-bundle detection
- additional bundle templates when real bundle families need them
- Unity Catalog audit writes only if a later phase explicitly designs them

### In Scope

Out-of-scope boundary documentation includes:

- identifying what Phase 1a shipped
- identifying what Phase 1a intentionally deferred
- separating Phase 1a, Phase 1b, and later work
- preventing readers from mistaking metadata contracts for live Databricks deployment
- preventing readers from mistaking target metadata for CI/CD implementation
- preventing readers from mistaking evidence design for generated evidence artifacts

### Out Of Scope

This boundary section does not:

- implement deferred work
- add GitHub Actions workflows
- add ABAC assets
- create Databricks resources
- define final ABAC SQL, UDFs, or DDL
- create evidence schemas or artifacts
- change Terraform-owned platform controls

### Out-Of-Scope Checkpoint

The mental model to keep:

- Phase 1a makes the repo understandable and locally verifiable.
- Phase 1a does not deploy anything.
- Phase 1a does not implement ABAC.
- Phase 1a does not enforce CI/CD.
- Phase 1a does not generate production evidence.
- Phase 1b begins enforcement and dogfood work using the foundation.

If this is clear, the shipped-foundation document now covers the full Phase 1a foundation at the level requested: ownership, behavior, in-scope boundaries, and out-of-scope boundaries for each major section.
