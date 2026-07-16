# Bundle Collection Explorer

This dependency-free static application illustrates a collection-oriented ABAC bundle repository. It models one project with any number of collection bundles and any number of maps per collection.

The default model is the proposed `platform-governance` layout with:

- `abac-jira-access`: `project` and `issue`
- `abac-general-access`: `account` and `region`

The directory tree and canvas use the same model. Marking collections as modified updates the intended `changed_bundles` output and selective deployment matrix.

## Run Locally

From the repository root:

```bash
just explore
```

Open <http://127.0.0.1:8000/>.

Pass a different port when needed:

```bash
just explore 9000
```

This runs the Python standard-library server against only this directory. The application has no npm installation, build step, backend, database, or network dependency.

## Browser Tests

With the local server running, open <http://127.0.0.1:8000/tests/>. The browser suite mounts a fresh application frame for every case and reports its result on the page.

Testing strategy:

- Default boundary: two collections with two maps each.
- Edit behavior: collection and map names update the generated structure.
- Growth behavior: collections and maps have no fixed count.
- Selection behavior: only modified collections enter `changed_bundles` and deployment.
- Validation behavior: invalid repository identifiers block deployment.
- Canvas behavior: the literal canvas renders and exposes selection, fit, and zoom controls.

The root Python suite also checks that the complete static application and browser suite are present and contain no remote or backend dependency.

## Workflow Scope

The workflow view describes the intended collection-oriented deployment design. It does not claim that the current GitHub workflows already deploy an arbitrary changed-bundle matrix.

Today, UAT conditionally deploys the hardcoded `abac-jira-project-access` bundle and production always deploys that same bundle. Implementing the generalized workflow remains separate from this visual application.
