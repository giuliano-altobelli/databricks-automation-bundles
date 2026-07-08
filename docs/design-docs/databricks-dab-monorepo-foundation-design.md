# Databricks DAB Monorepo Foundation Design

Status: accepted (2026-07-06)

This design defines the lightweight foundation for this repository, the Databricks Declarative Automation Bundles monorepo. Platform controls consumed here are owned by the external [databricks-infra](https://github.com/giuliano-altobelli/databricks-infra.git) Terraform repository. The monorepo is intended to support many projects over time. Each project may contain multiple Databricks bundles for dbt, apps, MLflow, Spark streaming, Auto Loader, UDFs, and other Databricks-native workloads.

The phase-1 design intentionally starts with one dogfood resource: Databricks attribute-based access control for Jira project-key row access. The ABAC governance model is defined in [Databricks ABAC Governance Design Doc](./databricks-abac-governance-design.md). This document defines the monorepo foundation needed to support that first slice and grow safely later. The [Phasing](#phasing) section records how phase 1 is delivered in slices.

# Goals

- Establish a scalable monorepo shape for many projects and bundles.
- Use `uv` and `prek` as the standard local developer entry point.
- Use GitHub Actions for CI/CD.
- Make changed-bundle detection a day-one design standard.
- Keep dependency locking scoped so unrelated bundles do not fight over one global runtime lock.
- Dogfood one ABAC access decision shape without designing every future Databricks resource.
- Require lightweight promotion evidence for production from the beginning.
- Keep implementation details out of this foundation design when they belong in a focused bundle spec.

# Phasing

Phase 1 is delivered in two slices. This document remains the target design for all of phase 1; this section records delivery status.

## Phase 1a: Repository Foundation (shipped 2026-06-25)

Tracked in [Databricks DAB Monorepo Foundation Phase 1](../exec-plans/active/databricks-dab-monorepo-foundation-phase-1.md). The tracker predates this phasing split and is titled "Phase 1".

Shipped:

- root `uv` tooling environment and `prek.toml`
- `repoctl` with `discover`, `validate`, and `changed`
- project and bundle metadata schemas and validation
- generic project and bundle templates
- one inert sample project and bundle metadata fixture
- offline tests and a recorded local verification log

## Phase 1b: Enforcement and Dogfood (shipped 2026-07-08)

- root `justfile` with `just bootstrap` and `just verify` wrappers over the raw `uv` commands, keeping raw `uv` fallback documented
- PR-validation GitHub Actions workflow: `uv` bootstrap, `prek`, `repoctl validate`, and changed-bundle computation
- `repoctl evidence check` for promotion-decision evidence
- ABAC dogfood bundle `projects/platform-governance/bundles/abac-jira-project-access/` with its focused `SPEC.md`, SQL sources, offline fail-closed contract fixtures, inert `databricks.yml`, and `repoctl.bundle.yaml` metadata
- concrete `abac-access-map` bundle template

Native Databricks bundle roots use `repoctl.bundle.yaml` for monorepo metadata because `bundle.yaml` can be interpreted by the Databricks CLI as a second root config next to `databricks.yml`. Keeping repoctl metadata in `repoctl.bundle.yaml` avoids that Databricks CLI root-config collision. Metadata-only and legacy bundles may still use `bundle.yaml`.

UAT and production deployment workflows and CI evidence artifact upload remain after phase 1b.

# Ownership Boundary

This DAB monorepo consumes platform controls owned by the external [databricks-infra](https://github.com/giuliano-altobelli/databricks-infra.git) Terraform repository.

The `databricks-infra` Terraform repository owns stable platform controls:

- `prod_security` and its governance schemas
- governed tag definitions and allowed values
- Unity Catalog grants
- service principals
- workspace and account setup
- stable ABAC policy definitions

This DAB monorepo owns delivery and validation around those controls:

- Databricks bundle assets
- UDF source
- access-map contracts
- validation tests and fixtures
- GitHub Actions CI/CD
- run evidence

This boundary prevents this DAB monorepo from becoming a second infrastructure control plane while still letting it dogfood ABAC quickly.

# Repository Structure

The stable scaling unit is:

```text
projects/<project>/bundles/<bundle>
```

A project is an ownership and review boundary. A bundle is one deployable Databricks asset bundle.

Recommended phase-1 shape:

```text
.
├── pyproject.toml              # repo tooling only
├── uv.lock                     # repo tooling only
├── prek.toml
├── README.md
├── docs/
│   ├── architecture.md
│   ├── design-docs/
│   └── adr/
├── schemas/
├── tools/
│   └── repoctl/
├── libs/
├── templates/
│   ├── README.md
│   ├── project/
│   └── bundles/
│       └── abac-access-map/
└── projects/
    └── platform-governance/
        ├── README.md
        ├── project.yaml
        └── bundles/
            └── abac-jira-project-access/
                ├── README.md
                ├── SPEC.md
                ├── repoctl.bundle.yaml
                ├── databricks.yml
                ├── pyproject.toml    # optional; only when the bundle needs Python deps
                ├── uv.lock           # optional; scoped to this bundle
                ├── resources/
                ├── sql/
                └── tests/
```

`databricks.yml` remains the native Databricks bundle definition. `project.yaml`, `repoctl.bundle.yaml`, and legacy metadata-only `bundle.yaml` files are monorepo governance metadata used by `repoctl` and GitHub Actions.

`templates/README.md` explains the approved scaffold path. Phase 1a ships generic project and bundle templates; phase 1b adds the concrete `abac-access-map` template. Other future bundle templates are intentionally not defined in this design.

# Dependency Model

The root `uv` environment is for repo tooling only:

- `repoctl`
- `prek`
- formatters and linters
- schema validators
- shared test helpers for repo contracts

The root `uv.lock` must not own every project and bundle runtime dependency. That would create unnecessary coupling and lockfile churn as the monorepo scales.

Dependency standard:

- root `uv.lock` locks only repo tooling
- bundles get local `pyproject.toml` and `uv.lock` files only when they need Python runtime or test dependencies
- independently versioned shared libraries may have their own lockfiles
- pure SQL or config bundles do not need bundle-local Python metadata
- GitHub Actions and `repoctl` must respect these dependency scopes

# Shared Code

Shared code is allowed only through explicit, tested shared packages.

Example:

```text
libs/
  databricks_platform/
    pyproject.toml
    uv.lock
    src/
```

Broad cross-bundle Databricks `sync.paths` should not be the default. Bundles should own their deployable source unless a shared package is deliberately versioned, tested, and referenced as a dependency.

# Bundle Target Contract

Every bundle starts with three targets:

```text
dev
uat
prod
```

Target semantics:

- `dev` is personal, default, and uses Databricks bundle development mode.
- `uat` is a shared GitHub Actions-controlled validation target.
- `prod` is a protected release target.

Developers deploy locally to `dev` only by default. `uat` and `prod` are controlled through GitHub Actions.

# Developer Experience

Developers use the root tooling environment for repo operations:

```bash
uv sync --locked --all-extras --dev
uv run prek install
uv run prek run
uv run repoctl validate
uv run repoctl changed --base origin/main
```

For bundle work, the default local loop is `dev` only:

```bash
cd projects/platform-governance/bundles/abac-jira-project-access
databricks bundle validate -t dev
databricks bundle deploy -t dev
```

If a bundle has local Python dependencies, the bundle owns its own `uv` environment and lockfile. The root environment should not be used as the bundle runtime dependency source.

# repoctl

The monorepo includes a small Python CLI, `repoctl`, managed by the root `uv` environment.

Phase-1 commands:

```bash
uv run repoctl discover
uv run repoctl validate
uv run repoctl changed --base origin/main
uv run repoctl evidence check --bundle <path> --target prod --evidence <run-dir>
```

Initial responsibilities:

- discover projects and bundles
- validate `project.yaml`, `repoctl.bundle.yaml`, and legacy metadata-only `bundle.yaml`
- compute changed bundles and dependents
- distinguish docs-only changes from deploy-affecting changes
- validate promotion evidence before `prod`

`repoctl` should stay small. It coordinates repo standards; it is not a replacement for the Databricks CLI or a general Databricks deployment framework.

# GitHub Actions CI/CD

GitHub Actions is the assumed CI/CD system.

Pull request workflow:

1. Bootstrap the root `uv` tooling environment.
2. Run `pytest`, `ruff`, and `prek`.
3. Run `repoctl discover` and `repoctl validate`.
4. Compute changed bundles and dependents into the job summary.

UAT workflow:

1. Deploy changed bundles to `uat` through CI.
2. Run dogfood-specific tests or contract checks.
3. Upload the evidence artifact.

Production workflow:

1. Require approval or an explicit release trigger.
2. Validate promotion-decision evidence.
3. Deploy changed bundles to `prod`.

Changed-bundle detection is required from day one:

- changed bundle paths trigger those bundles
- changed shared libraries trigger dependent bundles
- changed root tooling or CI config can trigger all bundles
- docs-only changes can skip deploy gates

# Evidence

Phase-1 evidence is persisted to GitHub Actions artifact storage. It is not committed to the repo.

Required artifact layout:

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

The repository may include documentation or lightweight schemas describing the evidence shape. CI-generated evidence files should not be checked in.

Writing evidence to `prod_security.access_audit` or another Unity Catalog location is out of scope for phase 1.

# Documentation Standards

The foundation uses lightweight written contracts:

```text
docs/architecture.md
docs/adr/
projects/<project>/README.md
projects/<project>/project.yaml
projects/<project>/bundles/<bundle>/README.md
projects/<project>/bundles/<bundle>/repoctl.bundle.yaml
```

Do not require a full `SPEC.md` for every small bundle from day one. Require a focused spec when a bundle introduces a governance-sensitive pattern, a new shared contract, or a new resource family.

The first ABAC dogfood bundle has a focused `SPEC.md` because it establishes an access-control pattern.

# ABAC Dogfood Slice

The first dogfood bundle is:

```text
projects/platform-governance/bundles/abac-jira-project-access/
```

Its purpose is to prove the monorepo foundation against one concrete access decision shape: Jira project-key row access.

The bundle consumes Terraform-owned controls:

- `prod_security`
- governed tags
- Unity Catalog grants
- service principals
- stable ABAC policy definitions

The bundle owns:

- UDF source
- access-map contract for `prod_security.access_maps.jira_project_access`
- contract tests and fixtures
- Databricks bundle resources needed to deploy owned assets
- CI evidence for validation and promotion

The foundation contract is:

- Jira row access is keyed by `project_key`.
- Access maps are scoped by access decision shape, not one table per project.
- Access-map rows include query-time fields and linkage to source decisions.
- Coarse RBAC without a current effective access row fails closed to zero protected rows.
- Final physical DDL is deferred to the bundle `SPEC.md`.
- Final ABAC policy SQL and full UDF implementation details are deferred to the bundle `SPEC.md`.

# Success Measures

## Structure

- A new project and bundle can be added from templates.
- Every bundle declares owner metadata, targets, and review policy.
- The root dependency lock is limited to repo tooling.
- Bundle dependency locks are local and optional.

## Developer Experience

- A new developer can bootstrap with `uv` and `prek`.
- Local validation and `dev` deploy are documented.
- Local deploys target `dev` only by default.

## CI/CD

- GitHub Actions validates changed bundles plus dependents.
- `uat` and `prod` are CI-controlled.
- `prod` requires promotion-decision evidence.
- CI uploads evidence to GitHub Actions artifact storage.

## ABAC Dogfood

- Jira project-key access validates the access-map contract.
- UDF source and tests live with the dogfood bundle.
- Fail-closed behavior is represented by lightweight contract tests or fixtures.

Time targets, such as cold bootstrap under 10 minutes or pull request feedback under 10 minutes, are useful aspirational measurements. They are not hard phase-1 acceptance gates.

# Out of Scope

- Implementing the monorepo in this document; delivery is tracked in `docs/exec-plans/` and summarized in [Phasing](#phasing).
- Creating live Databricks resources.
- Migrating the `databricks-infra` Terraform repository into this monorepo.
- Designing every Databricks bundle resource type.
- Final physical DDL for Jira access maps.
- Final ABAC policy SQL.
- Final UDF implementation details.
- Writing evidence to Unity Catalog audit tables.
- Full access workflow or approval-system design.
- Multi-workspace rollout design beyond keeping the structure compatible.
- Phase-1 CI checks for accidental direct consumer grants on `prod_security.access_maps` or `prod_security.access_audit`.

# References

- [Imported Platform Context from `databricks-infra`](../../ARCHITECTURE.md)
- [databricks-infra Terraform repository](https://github.com/giuliano-altobelli/databricks-infra.git)
- [Databricks ABAC Governance Design Doc](./databricks-abac-governance-design.md)
- [ADR 0001: Use `prod_security` as the Platform Governance Catalog](../adr/0001-platform-governance-catalog.md)
- [Phase 1a Implementation Tracker](../exec-plans/active/databricks-dab-monorepo-foundation-phase-1.md)
