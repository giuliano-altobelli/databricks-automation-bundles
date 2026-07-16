const pattern = /^[a-z0-9][a-z0-9-]*[a-z0-9]$/;

export function defaults() {
  return {
    project: "platform-governance",
    collections: [
      {
        name: "abac-jira-access",
        changed: true,
        maps: ["project", "issue"],
      },
      {
        name: "abac-general-access",
        changed: false,
        maps: ["account", "region"],
      },
    ],
  };
}

export function valid(value) {
  return pattern.test(value);
}

function safe(value, fallback) {
  return value.trim() || fallback;
}

function entry(name, kind, path, changed, children = []) {
  return { name, kind, path, changed, children };
}

function mapentry(project, collection, map, changed) {
  const name = safe(map, "unnamed-map");
  const base = `projects/${project}/bundles/${collection}/maps/${name}`;
  const fixtures = entry("fixtures", "folder", `${base}/fixtures`, changed, [
    entry("rows.json", "file", `${base}/fixtures/rows.json`, changed),
    entry("cases.json", "file", `${base}/fixtures/cases.json`, changed),
  ]);

  return entry(name, "folder", base, changed, [
    entry("apply.sql", "file", `${base}/apply.sql`, changed),
    entry("filter.sql", "file", `${base}/filter.sql`, changed),
    fixtures,
  ]);
}

function collectionentry(project, collection) {
  const name = safe(collection.name, "unnamed-collection");
  const base = `projects/${project}/bundles/${name}`;
  const resources = collection.maps.map((map) => {
    const resource = safe(map, "unnamed-map");
    return entry(`${resource}.yml`, "file", `${base}/resources/${resource}.yml`, collection.changed);
  });
  const maps = collection.maps.map((map) => mapentry(project, name, map, collection.changed));

  return entry(name, "folder", base, collection.changed, [
    entry("databricks.yml", "file", `${base}/databricks.yml`, collection.changed),
    entry("repoctl.bundle.yaml", "file", `${base}/repoctl.bundle.yaml`, collection.changed),
    entry("README.md", "file", `${base}/README.md`, collection.changed),
    entry("resources", "folder", `${base}/resources`, collection.changed, resources),
    entry("sql", "folder", `${base}/sql`, collection.changed, [
      entry("preflight.sql", "file", `${base}/sql/preflight.sql`, collection.changed),
    ]),
    entry("maps", "folder", `${base}/maps`, collection.changed, maps),
  ]);
}

export function structure(state) {
  const project = safe(state.project, "unnamed-project");
  const collections = state.collections.map((collection) => collectionentry(project, collection));
  const bundles = entry("bundles", "folder", `projects/${project}/bundles`, false, collections);
  const projectentry = entry(project, "folder", `projects/${project}`, false, [bundles]);

  return entry("projects", "folder", "projects", false, [projectentry]);
}

export function lines(root) {
  const output = [`${root.name}/`];

  function walk(children, prefix) {
    children.forEach((child, index) => {
      const last = index === children.length - 1;
      const branch = last ? "└── " : "├── ";
      const suffix = child.kind === "folder" ? "/" : "";
      output.push(`${prefix}${branch}${child.name}${suffix}`);
      walk(child.children, `${prefix}${last ? "    " : "│   "}`);
    });
  }

  walk(root.children, "");
  return output;
}

export function tree(state) {
  return lines(structure(state)).join("\n");
}

export function changed(state) {
  return state.collections.filter((collection) => collection.changed);
}

export function paths(state) {
  const project = safe(state.project, "unnamed-project");

  return changed(state).map((collection) => {
    const name = safe(collection.name, "unnamed-collection");
    const map = safe(collection.maps[0] || "", "databricks");
    const leaf = collection.maps.length ? `maps/${map}/apply.sql` : "databricks.yml";
    return `projects/${project}/bundles/${name}/${leaf}`;
  });
}

function duplicates(values) {
  const seen = new Set();
  const repeated = new Set();

  values.forEach((value) => {
    if (seen.has(value)) {
      repeated.add(value);
    }
    seen.add(value);
  });
  return [...repeated];
}

export function audit(state) {
  const issues = [];

  if (!valid(state.project)) {
    issues.push(`Project “${state.project || "empty"}” is not a valid repository identifier.`);
  }

  state.collections.forEach((collection) => {
    if (!valid(collection.name)) {
      issues.push(`Collection “${collection.name || "empty"}” is not a valid bundle identifier.`);
    }
    if (!collection.maps.length) {
      issues.push(`Collection “${collection.name || "empty"}” has no access maps.`);
    }
    collection.maps.forEach((map) => {
      if (!valid(map)) {
        issues.push(`Map “${map || "empty"}” in “${collection.name || "empty"}” is invalid.`);
      }
    });
    duplicates(collection.maps).forEach((map) => {
      issues.push(`Map “${map}” is duplicated in “${collection.name || "empty"}”.`);
    });
  });

  duplicates(state.collections.map((collection) => collection.name)).forEach((collection) => {
    issues.push(`Collection “${collection}” is duplicated.`);
  });

  return issues;
}
