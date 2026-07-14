const results = document.getElementById("results");
const fixture = document.getElementById("fixture");
const summary = document.getElementById("summary");

function assert(condition, message) {
  if (!condition) {
    throw new Error(message);
  }
}

function change(input, value) {
  input.value = value;
  input.dispatchEvent(new Event("input", { bubbles: true }));
}

function toggle(input, checked) {
  input.checked = checked;
  input.dispatchEvent(new Event("change", { bubbles: true }));
}

function settle(frame) {
  return new Promise((resolve) => {
    frame.contentWindow.requestAnimationFrame(() => {
      frame.contentWindow.requestAnimationFrame(resolve);
    });
  });
}

async function mount() {
  const frame = document.createElement("iframe");
  frame.className = "preview";
  frame.title = "Bundle explorer test fixture";
  const loaded = new Promise((resolve, reject) => {
    frame.addEventListener("load", resolve, { once: true });
    frame.addEventListener("error", reject, { once: true });
  });
  frame.src = "../index.html";
  fixture.replaceChildren(frame);
  await loaded;
  await settle(frame);
  return { frame, page: frame.contentDocument };
}

const cases = [
  {
    name: "Default model renders two collection bundles with two maps each",
    async run() {
      const { page } = await mount();
      const tree = page.getElementById("tree").textContent;
      assert(page.querySelectorAll("[data-collection]").length === 2, "Expected two collection rows");
      assert(tree.includes("abac-jira-access/"), "Expected the Jira collection");
      assert(tree.includes("abac-customer-access/"), "Expected the customer collection");
      assert(tree.includes("project.yml"), "Expected the project resource");
      assert(tree.includes("issue.yml"), "Expected the issue resource");
      assert(tree.includes("account.yml"), "Expected the account resource");
      assert(tree.includes("region.yml"), "Expected the region resource");
      assert(tree.includes("rows.json"), "Expected row fixtures");
      assert(tree.includes("cases.json"), "Expected contract fixtures");
    },
  },
  {
    name: "Editing a collection and map updates the generated tree",
    async run() {
      const { page } = await mount();
      const row = page.querySelector('[data-collection="0"]');
      change(row.querySelector("[data-name]"), "abac-workspace-access");
      change(row.querySelector("[data-map]"), "workspace");
      const tree = page.getElementById("tree").textContent;
      assert(tree.includes("abac-workspace-access/"), "Expected the renamed collection");
      assert(tree.includes("workspace.yml"), "Expected the renamed resource");
      assert(!tree.includes("abac-jira-access/"), "Expected the old collection name to disappear");
    },
  },
  {
    name: "Collections and maps can grow without a fixed N or X",
    async run() {
      const { page } = await mount();
      page.getElementById("add").click();
      const row = page.querySelector('[data-collection="2"]');
      assert(row, "Expected a third collection row");
      change(row.querySelector("[data-name]"), "abac-workspace-access");
      change(row.querySelector("[data-map]"), "workspace");
      row.querySelector("[data-add-map]").click();
      const updated = page.querySelector('[data-collection="2"]');
      const maps = updated.querySelectorAll("[data-map]");
      change(maps[1], "team");
      const tree = page.getElementById("tree").textContent;
      assert(maps.length === 2, "Expected two maps in the added collection");
      assert(tree.includes("workspace.yml"), "Expected the first added map");
      assert(tree.includes("team.yml"), "Expected the second added map");
    },
  },
  {
    name: "Only collections selected as changed enter the intended deployment matrix",
    async run() {
      const { page } = await mount();
      const first = page.querySelector('[data-collection="0"] [data-changed]');
      const second = page.querySelector('[data-collection="1"] [data-changed]');
      toggle(first, false);
      toggle(second, true);
      const output = page.getElementById("output").textContent;
      const deployments = page.getElementById("deployments").textContent;
      assert(!output.includes("abac-jira-access"), "Expected Jira to be excluded");
      assert(output.includes("abac-customer-access"), "Expected customer to be selected");
      assert(!deployments.includes("abac-jira-access"), "Expected no Jira deployment");
      assert(deployments.includes("abac-customer-access"), "Expected a customer deployment");
    },
  },
  {
    name: "Invalid repository identifiers block the illustrated deployment",
    async run() {
      const { page } = await mount();
      change(page.getElementById("project"), "Platform Governance");
      assert(page.getElementById("status").classList.contains("invalid"), "Expected invalid status");
      assert(
        page.getElementById("deployments").textContent.includes("Blocked"),
        "Expected deployment to be blocked",
      );
    },
  },
  {
    name: "Canvas mode supports accessible selection and zoom controls",
    async run() {
      const { frame, page } = await mount();
      page.getElementById("canvasbutton").click();
      await settle(frame);
      const canvas = page.getElementById("canvas");
      const nodes = page.getElementById("nodes");
      assert(!page.getElementById("canvasview").hidden, "Expected canvas mode to be visible");
      assert(canvas.width > 0 && canvas.height > 0, "Expected a rendered canvas");
      assert(nodes.options.length > 10, "Expected selectable repository paths");
      nodes.value = "projects/platform-governance/bundles/abac-jira-access";
      nodes.dispatchEvent(new Event("change", { bubbles: true }));
      assert(
        page.getElementById("selection").value.includes("abac-jira-access"),
        "Expected the selected canvas path",
      );
      page.getElementById("in").click();
      page.getElementById("out").click();
      page.getElementById("fit").click();
    },
  },
];

let passed = 0;

for (const test of cases) {
  const item = document.createElement("li");
  try {
    await test.run();
    passed += 1;
    item.textContent = `Pass · ${test.name}`;
  } catch (error) {
    item.className = "fail";
    item.textContent = `Fail · ${test.name}: ${error.message}`;
  }
  results.append(item);
}

const failed = cases.length - passed;
summary.className = `status ${failed ? "invalid" : "valid"}`;
summary.value = `${passed} passed · ${failed} failed`;
document.documentElement.dataset.result = failed ? "fail" : "pass";
