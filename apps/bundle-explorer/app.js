import { create } from "./canvas.js";
import { audit, changed, defaults, paths, structure, tree, valid } from "./model.js";

const state = defaults();
const view = {
  add: document.getElementById("add"),
  canvas: document.getElementById("canvas"),
  canvasbutton: document.getElementById("canvasbutton"),
  canvasview: document.getElementById("canvasview"),
  collections: document.getElementById("collections"),
  deployments: document.getElementById("deployments"),
  fit: document.getElementById("fit"),
  input: document.getElementById("project"),
  nodes: document.getElementById("nodes"),
  output: document.getElementById("output"),
  paths: document.getElementById("paths"),
  selection: document.getElementById("selection"),
  status: document.getElementById("status"),
  tree: document.getElementById("tree"),
  treebutton: document.getElementById("treebutton"),
  treeview: document.getElementById("treeview"),
  in: document.getElementById("in"),
  out: document.getElementById("out"),
};

function make(tag, className = "", text = "") {
  const element = document.createElement(tag);
  if (className) {
    element.className = className;
  }
  if (text) {
    element.textContent = text;
  }
  return element;
}

function label(cell, text) {
  cell.dataset.label = text;
  return cell;
}

function mark(input) {
  input.setAttribute("aria-invalid", String(!valid(input.value)));
}

function unique(values, base) {
  if (!values.includes(base)) {
    return base;
  }
  let index = 2;
  while (values.includes(`${base}-${index}`)) {
    index += 1;
  }
  return `${base}-${index}`;
}

const diagram = create(view.canvas, (node) => {
  view.nodes.value = node.path;
  view.selection.value = `${node.kind === "folder" ? "Directory" : "File"}: ${node.path}`;
});

function options(nodes) {
  const selected = view.nodes.value;
  view.nodes.replaceChildren(new Option("Select a repository path", ""));
  nodes.forEach((node) => {
    view.nodes.add(new Option(`${node.kind === "folder" ? "Directory" : "File"} · ${node.path}`, node.path));
  });
  if (nodes.some((node) => node.path === selected)) {
    view.nodes.value = selected;
  } else {
    view.selection.value = "Select a node to inspect its complete path.";
  }
}

function list(element, values, empty) {
  element.replaceChildren();
  if (!values.length) {
    const item = make("li", "empty", empty);
    element.append(item);
    return;
  }
  values.forEach((value) => {
    const item = make("li");
    const code = make("code", "", value);
    item.append(code);
    element.append(item);
  });
}

function deployments(collections, issues) {
  view.deployments.replaceChildren();
  if (issues.length) {
    view.deployments.append(make("p", "blocked", "Blocked until local validation passes."));
    return;
  }
  if (!collections.length) {
    view.deployments.append(make("p", "empty", "No deployment jobs are created."));
    return;
  }

  collections.forEach((collection) => {
    const article = make("article", "deployment");
    const title = make("strong", "", collection.name);
    const job = `apply_${collection.name.replaceAll("-", "_")}`;
    const commands = make("div", "commands");
    ["uat", "prod"].forEach((target) => {
      const row = make("p");
      const badge = make("span", "target", target);
      const code = make(
        "code",
        "",
        `bundle validate -t ${target} → deploy -t ${target} → run -t ${target} ${job}`,
      );
      row.append(badge, code);
      commands.append(row);
    });
    article.append(title, commands);
    view.deployments.append(article);
  });
}

function workflow() {
  const issues = audit(state);
  const collections = changed(state);
  const files = paths(state);
  const bundles = collections.map((collection) => (
    `projects/${state.project || "unnamed-project"}/bundles/${collection.name || "unnamed-collection"}`
  ));

  view.status.className = `status ${issues.length ? "invalid" : "valid"}`;
  view.status.value = issues.length
    ? `${issues.length} validation ${issues.length === 1 ? "issue" : "issues"}`
    : "Validation path clear";
  view.status.setAttribute("data-message", issues.join(" "));
  list(view.paths, files, "No changed bundle paths selected.");
  view.output.textContent = JSON.stringify({ changed_bundles: bundles }, null, 2);
  deployments(collections, issues);
}

function update() {
  const root = structure(state);
  view.tree.textContent = tree(state);
  options(diagram.render(root));
  workflow();
}

function touch(collection, checkbox) {
  collection.changed = true;
  checkbox.checked = true;
}

function maps(cell, collection, checkbox) {
  const items = make("div", "maps");
  collection.maps.forEach((map, index) => {
    const item = make("span", "map");
    const input = make("input");
    input.value = map;
    input.pattern = "[a-z0-9][a-z0-9-]*[a-z0-9]";
    input.autocomplete = "off";
    input.dataset.map = String(index);
    input.setAttribute("aria-label", `Map ${index + 1} in ${collection.name}`);
    mark(input);
    input.addEventListener("input", () => {
      collection.maps[index] = input.value;
      touch(collection, checkbox);
      mark(input);
      update();
    });

    const remove = make("button", "button quiet", "Remove");
    remove.type = "button";
    remove.dataset.removeMap = String(index);
    remove.setAttribute("aria-label", `Remove map ${map || index + 1} from ${collection.name}`);
    remove.addEventListener("click", () => {
      collection.maps.splice(index, 1);
      collection.changed = true;
      grid();
    });
    item.append(input, remove);
    items.append(item);
  });

  const add = make("button", "button quiet", "Add map");
  add.type = "button";
  add.dataset.addMap = "";
  add.addEventListener("click", () => {
    collection.maps.push(unique(collection.maps, "scope"));
    collection.changed = true;
    grid();
  });
  cell.append(items, add);
}

function grid() {
  view.collections.replaceChildren();
  state.collections.forEach((collection, index) => {
    const row = make("tr");
    row.dataset.collection = String(index);

    const changedcell = label(make("td"), "Changed");
    const switcher = make("label", "switch");
    const checkbox = make("input");
    checkbox.type = "checkbox";
    checkbox.checked = collection.changed;
    checkbox.dataset.changed = "";
    checkbox.setAttribute("aria-label", `Mark ${collection.name} as changed`);
    checkbox.addEventListener("change", () => {
      collection.changed = checkbox.checked;
      update();
    });
    switcher.append(checkbox, make("span", "", "Modified"));
    changedcell.append(switcher);

    const namecell = label(make("td"), "Collection bundle");
    const input = make("input");
    input.value = collection.name;
    input.pattern = "[a-z0-9][a-z0-9-]*[a-z0-9]";
    input.autocomplete = "off";
    input.dataset.name = "";
    input.setAttribute("aria-label", `Collection ${index + 1} name`);
    mark(input);
    input.addEventListener("input", () => {
      collection.name = input.value;
      touch(collection, checkbox);
      mark(input);
      update();
    });
    namecell.append(input);

    const mapcell = label(make("td"), "Access maps");
    maps(mapcell, collection, checkbox);

    const actioncell = label(make("td", "actions"), "Actions");
    const remove = make("button", "button quiet", "Remove collection");
    remove.type = "button";
    remove.dataset.removeCollection = "";
    remove.addEventListener("click", () => {
      state.collections.splice(index, 1);
      grid();
    });
    actioncell.append(remove);

    row.append(changedcell, namecell, mapcell, actioncell);
    view.collections.append(row);
  });
  update();
}

function show(name) {
  const canvas = name === "canvas";
  view.canvasview.hidden = !canvas;
  view.treeview.hidden = canvas;
  view.canvasbutton.setAttribute("aria-pressed", String(canvas));
  view.treebutton.setAttribute("aria-pressed", String(!canvas));
  if (canvas) {
    requestAnimationFrame(diagram.fit);
  }
}

view.input.value = state.project;
mark(view.input);
view.input.addEventListener("input", () => {
  state.project = view.input.value;
  state.collections.forEach((collection) => {
    collection.changed = true;
  });
  document.querySelectorAll("[data-changed]").forEach((checkbox) => {
    checkbox.checked = true;
  });
  mark(view.input);
  update();
});

view.add.addEventListener("click", () => {
  const names = state.collections.map((collection) => collection.name);
  state.collections.push({
    name: unique(names, "abac-collection-access"),
    changed: true,
    maps: ["scope"],
  });
  grid();
});

view.treebutton.addEventListener("click", () => show("tree"));
view.canvasbutton.addEventListener("click", () => show("canvas"));
view.fit.addEventListener("click", diagram.fit);
view.in.addEventListener("click", () => diagram.zoom(1.2));
view.out.addEventListener("click", () => diagram.zoom(0.83));
view.nodes.addEventListener("change", () => diagram.select(view.nodes.value));

grid();
