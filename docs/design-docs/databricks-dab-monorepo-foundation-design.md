# Databricks DAB Monorepo Foundation Design

Status: draft for feedback

This design proposes a lightweight foundation for a future Databricks Declarative Automation Bundles monorepo. The monorepo is outside this Terraform repository and is intended to support many projects over time. Each project may contain multiple Databricks bundles for dbt, apps, MLflow, Spark streaming, Auto Loader, UDFs, and other Databricks-native workloads.

The phase-1 design intentionally starts with one dogfood resource: Databricks attribute-based access control for Jira project-key row access. The ABAC governance model is defined in [Databricks ABAC Governance Design Doc](./databricks-abac-governance-design.md). This document defines the monorepo foundation needed to support that first slice and grow safely later.

# Goals

- Establish a scalable monorepo shape for many projects and bundles.
- Use `uv` and `prek` as the standard local developer entry point.
- Use GitHub Actions for CI/CD.
- Make changed-bundle detection a day-one design standard.
- Keep dependency locking scoped so unrelated bundles do not fight over one global runtime lock.
- Dogfood one ABAC access decision shape without designing every future Databricks resource.
- Require lightweight promotion evidence for production from the beginning.
- Keep implementation details out of this foundation design when they belong in a focused bundle spec.

# Ownership Boundary

The future DAB monorepo consumes platform controls owned by this Terraform repository.

Terraform owns stable platform controls:

- `prod_security` and its governance schemas
- governed tag definitions and allowed values
- Unity Catalog grants
- service principals
- workspace and account setup
- stable ABAC policy definitions

The DAB monorepo owns delivery and validation around those controls:

- Databricks bundle assets
- UDF source
- access-map contracts
- validation tests and fixtures
- GitHub Actions CI/CD
- run evidence

This boundary prevents the DAB monorepo from becoming a second infrastructure control plane while still letting it dogfood ABAC quickly.

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
                ├── bundle.yaml
                ├── databricks.yml
                ├── pyproject.toml    # optional; only when the bundle needs Python deps
                ├── uv.lock           # optional; scoped to this bundle
                ├── resources/
                ├── sql/
                └── tests/
```

`databricks.yml` remains the native Databricks bundle definition. `project.yaml` and `bundle.yaml` are monorepo governance metadata used by `repoctl` and GitHub Actions.

`templates/README.md` explains the approved scaffold path. Phase 1 includes a concrete `abac-access-map` template. Other future bundle templates are intentionally not defined in this design.

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
uv run repoctl evidence check --bundle <path> --target prod
```

Initial responsibilities:

- discover projects and bundles
- validate `project.yaml` and `bundle.yaml`
- compute changed bundles and dependents
- distinguish docs-only changes from deploy-affecting changes
- validate promotion evidence before `prod`

`repoctl` should stay small. It coordinates repo standards; it is not a replacement for the Databricks CLI or a general Databricks deployment framework.

# GitHub Actions CI/CD

GitHub Actions is the assumed CI/CD system.

Pull request workflow:

1. Bootstrap the root `uv` tooling environment.
2. Run `prek`.
3. Run `repoctl validate`.
4. Compute changed bundles and dependents.
5. Run Databricks bundle validation for changed bundles.

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
projects/<project>/bundles/<bundle>/bundle.yaml
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

- Implementing the monorepo.
- Creating live Databricks resources.
- Migrating this Terraform repo.
- Designing every Databricks bundle resource type.
- Final physical DDL for Jira access maps.
- Final ABAC policy SQL.
- Final UDF implementation details.
- Writing evidence to Unity Catalog audit tables.
- Full access workflow or approval-system design.
- Multi-workspace rollout design beyond keeping the structure compatible.
- Phase-1 CI checks for accidental direct consumer grants on `prod_security.access_maps` or `prod_security.access_audit`.

# References

- [Architecture](../../ARCHITECTURE.md)
- [Databricks ABAC Governance Design Doc](./databricks-abac-governance-design.md)
- [ADR 0001: Use `prod_security` as the Platform Governance Catalog](../adr/0001-platform-governance-catalog.md)
