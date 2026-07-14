const width = 168;
const height = 32;
const column = 204;
const row = 46;

function flatten(root) {
  const nodes = [];
  const links = [];
  let cursor = 0;

  function visit(entry, depth, parent) {
    const node = { ...entry, depth, x: depth * column, y: 0, parent };
    nodes.push(node);
    if (parent) {
      links.push({ parent, child: node });
    }

    if (!entry.children.length) {
      node.y = cursor * row;
      cursor += 1;
      return node;
    }

    const children = entry.children.map((child) => visit(child, depth + 1, node));
    node.y = (children[0].y + children[children.length - 1].y) / 2;
    return node;
  }

  visit(root, 0, null);
  return { nodes, links };
}

function clamp(value, minimum, maximum) {
  return Math.min(Math.max(value, minimum), maximum);
}

function shorten(context, value) {
  if (context.measureText(value).width <= width - 20) {
    return value;
  }

  let text = value;
  while (text.length > 1 && context.measureText(`${text}…`).width > width - 20) {
    text = text.slice(0, -1);
  }
  return `${text}…`;
}

export function create(canvas, onselect) {
  const context = canvas.getContext("2d");
  let graph = { nodes: [], links: [] };
  let scale = 1;
  let origin = { x: 24, y: 24 };
  let selected = "";
  let dragging = null;

  function palette() {
    const style = getComputedStyle(canvas);
    return {
      background: style.getPropertyValue("--background").trim(),
      border: style.getPropertyValue("--border").trim(),
      changed: style.getPropertyValue("--changed").trim(),
      file: style.getPropertyValue("--file").trim(),
      folder: style.getPropertyValue("--folder").trim(),
      foreground: style.getPropertyValue("--foreground").trim(),
      muted: style.getPropertyValue("--muted-foreground").trim(),
      primary: style.getPropertyValue("--primary").trim(),
      selected: style.getPropertyValue("--selected").trim(),
    };
  }

  function resize() {
    const bounds = canvas.getBoundingClientRect();
    if (!bounds.width || !bounds.height) {
      return;
    }
    const density = window.devicePixelRatio || 1;
    canvas.width = Math.round(bounds.width * density);
    canvas.height = Math.round(bounds.height * density);
    context.setTransform(density, 0, 0, density, 0, 0);
    draw();
  }

  function draw() {
    const bounds = canvas.getBoundingClientRect();
    if (!bounds.width || !bounds.height) {
      return;
    }
    const colors = palette();
    context.save();
    context.clearRect(0, 0, bounds.width, bounds.height);
    context.fillStyle = colors.background;
    context.fillRect(0, 0, bounds.width, bounds.height);
    context.translate(origin.x, origin.y);
    context.scale(scale, scale);
    context.lineWidth = 1 / scale;
    context.strokeStyle = colors.border;

    graph.links.forEach((link) => {
      const start = { x: link.parent.x + width, y: link.parent.y + height / 2 };
      const end = { x: link.child.x, y: link.child.y + height / 2 };
      const middle = (start.x + end.x) / 2;
      context.beginPath();
      context.moveTo(start.x, start.y);
      context.bezierCurveTo(middle, start.y, middle, end.y, end.x, end.y);
      context.stroke();
    });

    graph.nodes.forEach((node) => {
      const active = node.path === selected;
      context.beginPath();
      context.roundRect(node.x, node.y, width, height, 7);
      context.fillStyle = active
        ? colors.selected
        : node.kind === "folder"
          ? colors.folder
          : colors.file;
      context.fill();
      context.strokeStyle = active ? colors.primary : node.changed ? colors.changed : colors.border;
      context.lineWidth = (active ? 3 : node.changed ? 2 : 1) / scale;
      context.stroke();
      context.fillStyle = colors.foreground;
      context.font = "500 12px ui-monospace, SFMono-Regular, Menlo, Consolas, monospace";
      context.textBaseline = "middle";
      context.fillText(shorten(context, node.name), node.x + 10, node.y + height / 2);
      if (node.changed) {
        context.fillStyle = colors.changed;
        context.beginPath();
        context.arc(node.x + width - 10, node.y + 9, 3, 0, Math.PI * 2);
        context.fill();
      }
    });

    context.restore();
  }

  function fit() {
    if (!graph.nodes.length) {
      return;
    }
    const bounds = canvas.getBoundingClientRect();
    if (!bounds.width || !bounds.height) {
      return;
    }
    const maximum = Math.max(...graph.nodes.map((node) => node.x + width));
    const bottom = Math.max(...graph.nodes.map((node) => node.y + height));
    scale = clamp(Math.min((bounds.width - 48) / maximum, (bounds.height - 48) / bottom), 0.12, 1.15);
    origin = { x: 24, y: 24 };
    draw();
  }

  function zoom(factor, focus) {
    const bounds = canvas.getBoundingClientRect();
    const center = focus || { x: bounds.width / 2, y: bounds.height / 2 };
    const world = {
      x: (center.x - origin.x) / scale,
      y: (center.y - origin.y) / scale,
    };
    const next = clamp(scale * factor, 0.12, 3);
    origin = {
      x: center.x - world.x * next,
      y: center.y - world.y * next,
    };
    scale = next;
    draw();
  }

  function point(event) {
    const bounds = canvas.getBoundingClientRect();
    return {
      screen: { x: event.clientX - bounds.left, y: event.clientY - bounds.top },
      world: {
        x: (event.clientX - bounds.left - origin.x) / scale,
        y: (event.clientY - bounds.top - origin.y) / scale,
      },
    };
  }

  function select(path) {
    const node = graph.nodes.find((candidate) => candidate.path === path);
    selected = node ? node.path : "";
    draw();
    if (node) {
      onselect(node);
    }
  }

  canvas.addEventListener("pointerdown", (event) => {
    const position = point(event);
    dragging = {
      pointer: event.pointerId,
      start: position.screen,
      origin: { ...origin },
      moved: false,
    };
    canvas.setPointerCapture(event.pointerId);
  });

  canvas.addEventListener("pointermove", (event) => {
    if (!dragging || dragging.pointer !== event.pointerId) {
      return;
    }
    const position = point(event).screen;
    const delta = { x: position.x - dragging.start.x, y: position.y - dragging.start.y };
    dragging.moved = dragging.moved || Math.hypot(delta.x, delta.y) > 4;
    origin = { x: dragging.origin.x + delta.x, y: dragging.origin.y + delta.y };
    draw();
  });

  canvas.addEventListener("pointerup", (event) => {
    if (!dragging || dragging.pointer !== event.pointerId) {
      return;
    }
    const moved = dragging.moved;
    dragging = null;
    canvas.releasePointerCapture(event.pointerId);
    if (moved) {
      return;
    }
    const position = point(event).world;
    const node = [...graph.nodes].reverse().find((candidate) => (
      position.x >= candidate.x
      && position.x <= candidate.x + width
      && position.y >= candidate.y
      && position.y <= candidate.y + height
    ));
    if (node) {
      select(node.path);
    }
  });

  canvas.addEventListener("wheel", (event) => {
    event.preventDefault();
    const position = point(event).screen;
    zoom(event.deltaY < 0 ? 1.12 : 0.89, position);
  }, { passive: false });

  const observer = new ResizeObserver(resize);
  observer.observe(canvas);

  return {
    render(root) {
      graph = flatten(root);
      canvas.setAttribute(
        "aria-label",
        `Repository canvas with ${graph.nodes.length} selectable paths. Drag to pan and use the controls or mouse wheel to zoom.`,
      );
      if (!graph.nodes.some((node) => node.path === selected)) {
        selected = "";
      }
      resize();
      fit();
      return graph.nodes.map((node) => ({ name: node.name, kind: node.kind, path: node.path }));
    },
    fit,
    zoom,
    select,
  };
}
