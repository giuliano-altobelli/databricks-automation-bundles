from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
README = ROOT / "README.md"
DESIGN_DOC = ROOT / "docs" / "design-docs" / "databricks-dab-monorepo-foundation-design.md"
SHIPPED_DOC = (
    ROOT
    / "docs"
    / "exec-plans"
    / "completed"
    / "databricks-dab-monorepo-foundation-shipped.md"
)
TEMPLATES_README = ROOT / "templates" / "README.md"
TRACKER = (
    ROOT
    / "docs"
    / "exec-plans"
    / "active"
    / "databricks-dab-monorepo-phase-1b-enforcement-and-dogfood.md"
)


def text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def assert_contains_all(document: str, fragments: list[str]) -> None:
    missing = [fragment for fragment in fragments if fragment not in document]
    assert not missing, f"Missing expected documentation fragments: {missing}"


def section_between(document: str, start: str, end: str) -> str:
    start_index = document.index(start)
    end_index = document.index(end, start_index)
    return document[start_index:end_index]


def test_design_doc_links_to_existing_phase_1a_tracker() -> None:
    design = text(DESIGN_DOC)
    phase_1a_tracker = "../exec-plans/active/databricks-dab-monorepo-foundation-phase-1.md"

    assert "../implementation/databricks-dab-monorepo-foundation-phase-1.md" not in design
    assert "docs/implementation/" not in design
    assert phase_1a_tracker in design
    assert (DESIGN_DOC.parent / phase_1a_tracker).resolve().exists()


def test_readme_summarizes_phase_1b_delivery_and_metadata_convention() -> None:
    readme = text(README)

    assert_contains_all(
        readme,
        [
            "Phase 1a and Phase 1b",
            "just bootstrap",
            "just verify",
            "uv run pytest -q",
            "repoctl evidence check",
            "schemas/evidence/",
            ".github/workflows/pr-validation.yml",
            "abac-jira-project-access",
            "templates/bundles/abac-access-map/",
            "repoctl.bundle.yaml",
            "native Databricks bundle roots",
            "bundle.yaml",
            "legacy metadata-only",
        ],
    )
    assert "ABAC asset bundle implementation" not in readme


def test_design_doc_phasing_records_phase_1b_shipped_and_filename_convention() -> None:
    design = text(DESIGN_DOC)
    phase_1b = section_between(design, "## Phase 1b", "# Ownership Boundary")

    assert_contains_all(
        phase_1b,
        [
            "shipped 2026-07-08",
            "root `justfile`",
            "PR-validation GitHub Actions workflow",
            "`repoctl evidence check`",
            "ABAC dogfood bundle",
            "concrete `abac-access-map` bundle template",
            "repoctl.bundle.yaml",
            "Databricks CLI root-config collision",
            "UAT and production deployment workflows",
            "after phase 1b",
        ],
    )
    assert "pending" not in phase_1b.lower()


def test_shipped_doc_reconciles_phase_1b_without_claiming_deployments() -> None:
    shipped = text(SHIPPED_DOC)

    assert_contains_all(
        shipped,
        [
            "Phase 1b has now shipped in this branch",
            ".github/workflows/pr-validation.yml",
            "`repoctl evidence check`",
            "schemas/evidence/",
            "projects/platform-governance/bundles/abac-jira-project-access/",
            "templates/bundles/abac-access-map/",
            "repoctl.bundle.yaml",
            "bundle.yaml as the legacy metadata-only fallback",
            "does not add UAT or production deployment workflows",
            "does not upload CI evidence artifacts",
        ],
    )
    assert "Phase 1b is still pending" not in shipped
    assert "Phase 1b should add" not in shipped


def test_shipped_inventory_lists_current_platform_governance_bundles() -> None:
    shipped = text(SHIPPED_DOC)
    inventory = section_between(
        shipped,
        "### Repo-Shape Self-Check",
        "If that table makes sense",
    )

    assert_contains_all(
        inventory,
        [
            "`projects/platform-governance/bundles/foundation-smoke/`",
            "`projects/platform-governance/bundles/abac-jira-project-access/`",
            "`projects/platform-governance/bundles/abac-jira-project-access/repoctl.bundle.yaml`",
            "One of two metadata-backed bundles under the platform governance project.",
            "The repo can validate native-bundle repoctl metadata without confusing "
            "the Databricks CLI.",
        ],
    )
    assert "The repo has one bundle-shaped unit under the project." not in shipped


def test_evidence_check_cli_examples_include_required_evidence_argument() -> None:
    full_command = "repoctl evidence check --bundle <path> --target prod --evidence <run-dir>"
    checked_docs = [
        text(README),
        text(DESIGN_DOC),
        text(SHIPPED_DOC),
        text(TRACKER),
    ]

    for document in checked_docs:
        for line in document.splitlines():
            if "repoctl evidence check --bundle <path> --target prod" in line:
                assert full_command in line

    assert full_command in text(SHIPPED_DOC)


def test_shipped_evidence_section_documents_schemas_as_delivered() -> None:
    shipped = text(SHIPPED_DOC)
    evidence = section_between(shipped, "### Evidence Contract", "### What CI/CD Owns")

    assert_contains_all(
        evidence,
        [
            "Phase 1b ships documentation-grade schemas under `schemas/evidence/`",
            "CI-generated evidence files should not be checked in.",
        ],
    )
    assert "may later add lightweight schemas or documentation" not in evidence


def test_shipped_template_section_lists_neutral_and_abac_templates() -> None:
    shipped = text(SHIPPED_DOC)
    templates = section_between(shipped, "## Templates", "## CI/CD And Evidence Phasing")

    assert_contains_all(
        templates,
        [
            "Phase 1a ships neutral templates",
            "Phase 1b ships the concrete ABAC access-map template",
            "templates/bundles/abac-access-map/",
            "repoctl.bundle.yaml",
            "databricks.yml",
            "metadata shapes aligned with `project.yaml`, `repoctl.bundle.yaml`, "
            "and legacy metadata-only `bundle.yaml`",
        ],
    )
    assert "defers ABAC-specific templates" not in templates
    assert "real Databricks asset templates wait until Phase 1b" not in templates


def test_shipped_metadata_checkpoint_uses_current_bundle_metadata_filenames() -> None:
    shipped = text(SHIPPED_DOC)
    metadata = section_between(shipped, "## Metadata Contracts", "## Local Toolchain")
    checkpoint = section_between(
        metadata,
        "### Metadata Contract Checkpoint",
        "If this is clear",
    )

    assert_contains_all(
        checkpoint,
        [
            "`repoctl.bundle.yaml`",
            "legacy metadata-only `bundle.yaml`",
            "bundle metadata tells the repo which bundle units exist",
        ],
    )
    assert "`bundle.yaml` tells the repo which bundle units exist" not in checkpoint


def test_validation_commands_describe_current_bundle_count_and_metadata_paths() -> None:
    shipped = text(SHIPPED_DOC)
    validation = section_between(shipped, "## Validation Commands", "## Changed-Bundle Detection")

    assert_contains_all(
        validation,
        [
            "`uv run repoctl validate` owns metadata contract validation. It proves "
            "discovered `project.yaml`, `repoctl.bundle.yaml`, and legacy metadata-only "
            "`bundle.yaml` files satisfy the shipped metadata rules.",
            "`repoctl discover` proves the current repository has one project, "
            "`platform-governance`, and two bundles: `foundation-smoke` and "
            "`abac-jira-project-access`.",
            "Run `repoctl validate` after editing `project.yaml`, `repoctl.bundle.yaml`, "
            "legacy metadata-only `bundle.yaml`, or the metadata validator.",
        ],
    )
    assert "one inert bundle, `foundation-smoke`" not in validation
    assert "discovered `project.yaml` and `bundle.yaml` files" not in validation


def test_design_doc_pr_workflow_matches_shipped_phase_1b_checks() -> None:
    design = text(DESIGN_DOC)
    ci_cd = section_between(design, "# GitHub Actions CI/CD", "# Evidence")
    pr_workflow = section_between(ci_cd, "Pull request workflow:", "UAT workflow:")

    assert_contains_all(
        pr_workflow,
        [
            "Run `pytest`, `ruff`, and `prek`.",
            "Run `repoctl discover` and `repoctl validate`.",
            "Compute changed bundles and dependents into the job summary.",
        ],
    )
    assert "Run Databricks bundle validation for changed bundles" not in pr_workflow


def test_templates_readme_lists_phase_1b_abac_template() -> None:
    templates_readme = text(TEMPLATES_README)

    assert_contains_all(
        templates_readme,
        [
            "templates/bundles/abac-access-map/",
            "Phase 1b",
            "repoctl.bundle.yaml",
            "databricks.yml",
        ],
    )
    assert "ABAC-specific templates and Databricks asset files are deferred" not in templates_readme


def test_phase_1b_tracker_marks_tasks_through_docs_reconciliation_complete() -> None:
    tracker = text(TRACKER)

    for task_number in range(1, 14):
        assert f"- [x] {task_number}." in tracker
    assert "- [ ] 14." in tracker
    assert "Task 13 verification:" in tracker
    assert "passed with 13 tests" in tracker
    assert "passed with 5 tests" not in tracker
    assert "YYYY-MM-DD: Task 13 verification" not in tracker
