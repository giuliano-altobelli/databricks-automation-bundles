# Databricks DAB Monorepo Phase 1b Enforcement and Dogfood Tracker

Status: active

This tracker records the Phase 1b implementation scope for enforcement and the first ABAC dogfood bundle. The original active plan file at this path was empty; this tracker reconstructs the task list from the active goal plus the current design, shipped-foundation, Phase 1a tracker, and README docs.

## Source Documents

- `docs/design-docs/databricks-dab-monorepo-foundation-design.md`
- `docs/design-docs/databricks-abac-governance-design.md`
- `docs/exec-plans/completed/databricks-dab-monorepo-foundation-shipped.md`
- `docs/exec-plans/active/databricks-dab-monorepo-foundation-phase-1.md`
- `README.md`

## Approved Scope

- Keep Phase 1b local, contract-focused, and suitable for offline verification.
- Add developer wrappers around the existing raw `uv` commands without removing the raw-command fallback.
- Strengthen changed-bundle classification so root enforcement and workflow changes can affect all bundles.
- Add fail-closed promotion evidence validation for `prod`.
- Add documentation-grade evidence schemas without adding dependencies.
- Add the first real dogfood bundle under `projects/platform-governance/bundles/abac-jira-project-access/`.
- Use the dogfood bundle to settle the focused DDL, UDF, and policy SQL decisions intentionally deferred from the foundation and ABAC design docs.
- Add offline contract tests and fixtures that represent fail-closed ABAC behavior.
- Add a concrete `abac-access-map` template and prove it materializes into a valid, test-passing bundle.
- Add PR validation with parity to local verification; verify locally only in this phase task set.
- Reconcile design, shipped, and README docs after the implementation lands.

## Non-Goals

- No live Databricks resource creation.
- No UAT or production deployment.
- No push, no PR, and no remote GitHub Actions run as part of this phase tracker.
- No CI evidence artifact upload beyond local workflow definition.
- No Unity Catalog audit writes.
- No migration of Terraform-owned platform controls into this DAB monorepo.
- No broad design for every future Databricks bundle type.
- No root lockfile ownership of bundle runtime dependencies.

## Implementation Checklist

- [x] 1. Add the Phase 1b tracker doc.
- [x] 2. Add the root justfile with bootstrap/verify commands.
- [x] 3. Fix changed-file classification so a root `justfile` change affects all bundles, and update README docs while preserving raw `uv` commands as fallback.
- [x] 4. Add `repoctl evidence check --bundle <path> --target prod --evidence <run-dir>` with fail-closed missing-file behavior.
- [x] 5. Content-validate evidence: malformed JSON, unapproved decision, or bundle/target mismatch reject.
- [x] 6. Add documentation-grade JSON Schemas under `schemas/evidence/` with no new dependencies.
- [x] 7. Add the full ABAC dogfood bundle `projects/platform-governance/bundles/abac-jira-project-access`: metadata and focused `SPEC.md` owning DDL, UDF, and policy SQL decisions deferred by the design doc.
- [x] 8. Add SQL sources for the ABAC dogfood DDL, UDF, and policy decisions.
- [x] 9. Add offline fail-closed contract tests with fixtures for the ABAC dogfood bundle.
- [x] 10. Add a minimal `databricks.yml` for the ABAC dogfood bundle that deploys nothing.
- [x] 11. Add PR-validation workflow with local-verify parity: prek, ruff, pytest including bundle tests, repoctl validate, and changed-bundle computation into the job summary. Verify locally only; no push, no PR.
- [x] 12. Add concrete `templates/bundles/abac-access-map/` template with a test proving it materializes into a valid, test-passing bundle.
- [x] 13. Reconcile docs: design-doc phasing, shipped doc, README.
- [ ] 14. Final verification sweep with a red-then-green evidence-check smoke.

## Design Decisions Already Settled

- The stable scaling unit remains `projects/<project>/bundles/<bundle>`.
- A project is the ownership and review boundary; a bundle is the deployable Databricks Asset Bundle boundary.
- Root `uv` dependencies are for repository tooling only. Bundle runtime dependencies stay bundle-local and optional.
- Every bundle declares `dev`, `uat`, and `prod`; `dev` is the local default, while `uat` and `prod` are CI-controlled.
- `repoctl` remains a small repository control CLI. It discovers, validates, computes changed bundles, and checks promotion evidence; it does not replace the Databricks CLI.
- Changed-bundle detection must treat root tooling, schemas, templates, workflow config, and equivalent repo contracts as broadly affecting bundles, while docs-only changes remain non-deploy-affecting.
- The root `justfile` is a developer-experience wrapper, not the only supported interface. README updates must keep raw `uv` commands as fallback.
- Phase 1 evidence is stored as GitHub Actions artifacts, not committed to the repo and not written to Unity Catalog.
- Production promotion requires promotion-decision evidence and must fail closed when required evidence is missing or invalid.
- Evidence validation must reject malformed JSON, unapproved decisions, and bundle or target mismatches.
- Documentation-grade evidence schemas may describe the artifact contract, but Phase 1b must not add new runtime dependencies for schema validation.
- The first dogfood bundle is `projects/platform-governance/bundles/abac-jira-project-access/`.
- The dogfood bundle proves Jira project-key row access as one concrete access decision shape.
- The dogfood bundle consumes Terraform-owned controls such as `prod_security`, governed tags, Unity Catalog grants, service principals, and stable ABAC policy definitions.
- The dogfood bundle owns UDF source, the `prod_security.access_maps.jira_project_access` contract, contract tests and fixtures, Databricks bundle resources needed for owned assets, and CI evidence for validation and promotion.
- Jira row access is keyed by `project_key`.
- Access maps are scoped by access decision shape, not by one table per resource and not by one generic catch-all table.
- Access-map rows include query-time fields plus linkage to source decisions.
- Coarse RBAC without a current effective access row fails closed to zero protected rows.
- Approval history and wide audit payloads do not belong in hot-path access mapping tables.
- ABAC policies should attach at the highest safe Unity Catalog scope and be constrained by governed tags.
- Reusable policy-supporting UDFs live in `prod_security.policies`; domain-specific UDFs require a future focused spec.
- Final physical DDL, UDF details, and ABAC policy SQL for this first dogfood slice are owned by the dogfood bundle `SPEC.md`.
- The minimal dogfood `databricks.yml` for Phase 1b deploys nothing while establishing the native bundle boundary.
- CI and local verification should use the same meaningful checks: `prek`, `ruff`, `pytest`, `repoctl validate`, and changed-bundle computation.

## Verification Log

- 2026-06-25: Phase 1a final verification passed with `uv run pytest -q` reporting 11 tests.
- 2026-06-25: Phase 1a final verification passed with `uv run ruff check tools tests`.
- 2026-07-08: Phase 1b baseline from task handoff confirms `uv run pytest -q` passed with 11 tests before this tracker task.
- 2026-07-08: Phase 1b baseline from task handoff confirms `uv run ruff check tools tests` passed before this tracker task.

Task-level entries:

- 2026-07-08: Tasks 2-3 verification: justfile tests, changed-file classifier tests, README fallback docs, and full repo validation passed during those tasks.
- 2026-07-08: Tasks 4-6 verification: evidence-check unit tests and evidence schema documentation tests passed.
- 2026-07-08: Tasks 7-10 verification: ABAC dogfood metadata, SQL source, fail-closed contract fixtures, and inert `databricks.yml` tests passed.
- 2026-07-08: Task 11 verification: PR-validation workflow parity tests passed locally; no push, PR, deploy, or remote workflow run.
- 2026-07-08: Task 12 verification: `templates/bundles/abac-access-map/` materialization test passed.
- 2026-07-08: Task 13 verification: `uv run pytest -q tests/test_phase1b_docs_reconciliation.py` passed with 13 tests after failing red against stale Phase 1b docs; `uv run pytest -q` passed with 69 tests; `uv run ruff check tests/test_phase1b_docs_reconciliation.py` passed.

## Self-Review Checklist

- [x] Tracker file is populated from the reconstructed Phase 1b task list.
- [x] All 14 Phase 1b tasks are preserved explicitly.
- [x] Scope and non-goals are documented for later agents.
- [x] Existing design decisions are captured without changing the docs that define them.
- [x] Verification log includes the known baseline and leaves structured space for later task evidence.
- [x] This task modifies only this tracker document.
