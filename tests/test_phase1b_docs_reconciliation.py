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
    assert "YYYY-MM-DD: Task 13 verification" not in tracker
