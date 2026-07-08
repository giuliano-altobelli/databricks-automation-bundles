# Evidence Schemas

These JSON Schemas document the strict CI artifact contract for evidence files
produced before `repoctl evidence check` runs.

`repoctl evidence check` currently performs dependency-free field validation
against the consumed evidence fields. These schemas are documentation-grade
contracts and are not wired in as a runtime dependency.
