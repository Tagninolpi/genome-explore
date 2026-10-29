const ROW_H = 30, HEAD_H = 44;          // must match the CSS heights
const MODES = ["both", "ncbi", "gwh"];  // click on a header cycles through these

let rows = [], cols = [], modes = {}, page = 0, pageSize = 10;

const $ = id => document.getElementById(id);

$("go").onclick = load;
$("taxid").onkeydown = e => { if (e.key === "Enter") load(); };
$("prev").onclick = () => { page--; render(); };
$("next").onclick = () => { page++; render(); };
document.querySelectorAll("[data-mode]").forEach(b => b.onclick = () => {
  cols.forEach(c => modes[c] = b.dataset.mode);
  render();
});
window.onresize = render;

async function load() {
  $("status").textContent = "Loading... (see server console for progress)";
  $("go").disabled = true;
  const res = await fetch(`/api/fuse/${$("taxid").value.trim()}`);
  rows = await res.json();
  // columns = union of keys, in first-seen order (nothing hard-coded)
  cols = [...new Set(rows.flatMap(r => Object.keys(r)))];
  cols.forEach(c => modes[c] = "both");
  page = 0;
  $("go").disabled = false;
  $("status").textContent = `${rows.length} genomes`;
  render();
}

// a fused value is either a plain value (both DBs agree) or {ncbi, gwh}
const isPair = v => v && typeof v === "object" && !Array.isArray(v) && "ncbi" in v && "gwh" in v;
const fmt = v => (v !== null && typeof v === "object") ? JSON.stringify(v) : String(v);

function tag(db) {
  const s = document.createElement("span");
  s.className = `tag ${db}`;
  s.textContent = db.toUpperCase();
  return s;
}

function fillCell(td, v, mode) {
  if (!isPair(v)) {                       // both agree -> same in every mode
    td.textContent = v === null || v === undefined ? "" : fmt(v);
    return;
  }
  const n = v.ncbi, g = v.gwh;
  const has = x => x !== null && x !== undefined;

  if (mode === "ncbi" || mode === "gwh") {
    const x = mode === "ncbi" ? n : g;
    if (has(x)) td.textContent = fmt(x);
    else { td.textContent = "-"; td.className = "nil"; }
    return;
  }
  // mode "both": show whatever exists, with a tag saying where it comes from
  if (has(n)) { td.append(tag("ncbi"), fmt(n)); }
  if (has(n) && has(g)) { const s = document.createElement("span"); s.className = "sep"; s.textContent = "|"; td.append(s); }
  if (has(g)) { td.append(tag("gwh"), fmt(g)); }
  if (!has(n) && !has(g)) { td.textContent = "-"; td.className = "nil"; }
}

function render() {
  const table = $("table");
  table.innerHTML = "";
  if (!rows.length) return;

  // rows per page = what fits in the table area without vertical scroll
  pageSize = Math.max(1, Math.floor(($("wrap").clientHeight - HEAD_H - 2) / ROW_H));
  const pages = Math.ceil(rows.length / pageSize);
  page = Math.min(Math.max(page, 0), pages - 1);

  const thead = table.createTHead().insertRow();
  cols.forEach(c => {
    const th = document.createElement("th");
    th.textContent = c;
    const sub = document.createElement("small");
    sub.textContent = modes[c];
    th.append(sub);
    th.onclick = () => { modes[c] = MODES[(MODES.indexOf(modes[c]) + 1) % MODES.length]; render(); };
    thead.append(th);
  });

  const tbody = table.createTBody();
  rows.slice(page * pageSize, (page + 1) * pageSize).forEach(r => {
    const tr = tbody.insertRow();
    cols.forEach(c => fillCell(tr.insertCell(), r[c], modes[c]));
  });

  $("pageinfo").textContent = `page ${page + 1} / ${pages}`;
  $("prev").disabled = page === 0;
  $("next").disabled = page >= pages - 1;
  document.querySelectorAll("[data-mode]").forEach(b =>
    b.classList.toggle("on", cols.length && cols.every(c => modes[c] === b.dataset.mode)));
}
