// One-time explicit source tagging: static template text is localized BEFORE interpolation.
// Dynamic care text, messages, names, document text and assessment stimuli stay untouched.
const fs = require("fs"),
  path = require("path"),
  babel = require("prettier/plugins/babel");
const catalogOnly = process.argv.includes("--catalog-only");
const root = path.resolve(__dirname, ".."),
  catalog = new Set();
const singles = new Set(
  "Home Settings Support Companion Messages Overview Audit Menu Refresh Send Stop Cancel Confirm Save Password Account Patient Participant Family Clinician Pending Completed All Later Done Back Next Retry Download Remove Delete Close Play Pause Language English".split(
    " ",
  ),
);
const decode = (s) =>
  s
    .replace(/&amp;/g, "&")
    .replace(/&quot;/g, '"')
    .replace(/&#39;/g, "'")
    .replace(/&lt;/g, "<")
    .replace(/&gt;/g, ">");
const add = (value) => {
  const s = decode(value.trim());
  if (s.length > 1 && /[a-zA-Z]/.test(s) && !/^Neuro(?:Twin|Companion)$/.test(s)) catalog.add(s);
};
function htmlKeys(text) {
  for (const token of text.match(/<[^>]*>|[^<]+/g) || []) {
    if (token.startsWith("<")) {
      for (const m of token.matchAll(/\b(?:aria-label|title|placeholder|alt)=(['"])(.*?)\1/gs))
        m[2].split(/\uE000\d+\uE001/g).forEach(add);
    } else token.split(/\uE000\d+\uE001/g).forEach(add);
  }
}
const files = [];
for (const folder of ["mobile", "dashboard"])
  for (const name of fs.readdirSync(path.join(root, "web", folder)))
    if (name.endsWith(".js") && !["ar-catalog.js", "localization.js"].includes(name))
      files.push(path.join(root, "web", folder, name));
for (const file of files) {
  const source = fs.readFileSync(file, "utf8"),
    ast = babel.parsers.babel.parse(source),
    edits = [];
  function walk(node, parent) {
    if (!node || typeof node !== "object") return;
    if (
      node.type === "TemplateLiteral" &&
      node.quasis.some((q) => /<[a-zA-Z/!]/.test(q.value.cooked || ""))
    ) {
      htmlKeys(
        node.quasis
          .map(
            (q, i) =>
              (q.value.cooked || "") + (i < node.expressions.length ? `\uE000${i}\uE001` : ""),
          )
          .join(""),
      );
      if (parent?.type !== "TaggedTemplateExpression")
        edits.push({ start: node.start, end: node.start, value: "ntUi" });
    }
    if (
      node.type === "TemplateLiteral" &&
      !node.quasis.some((q) => /<[a-zA-Z/!]/.test(q.value.cooked || "")) &&
      ((parent?.type === "TaggedTemplateExpression" && parent.tag?.name === "ntText") ||
        (parent?.type === "CallExpression" && ["note", "confirm"].includes(parent.callee?.name)))
    ) {
      node.quasis.forEach((q) => add(q.value.cooked || ""));
      if (parent?.type !== "TaggedTemplateExpression")
        edits.push({ start: node.start, end: node.start, value: "ntText" });
    }
    if (node.type === "StringLiteral") {
      const value = node.value;
      if (parent?.type === "CallExpression" && parent.callee?.name === "ntTr") add(value);
      if (
        (parent?.type === "CallExpression" &&
          ["setVoiceState", "confirm"].includes(parent.callee?.name)) ||
        (parent?.type === "NewExpression" && parent.callee?.name === "Error")
      )
        add(value);
      if (/<[a-zA-Z/!]/.test(value)) {
        htmlKeys(value);
        if (!(parent?.type === "CallExpression" && parent.callee?.name === "ntUi"))
          edits.push({
            start: node.start,
            end: node.end,
            value: `ntUi(${source.slice(node.start, node.end)})`,
          });
      } else if (
        !/[=\/<>{}]/.test(value) &&
        (singles.has(value) ||
          /^[A-Z][a-z]+$/.test(value) ||
          (value.includes(" ") && /[A-Z]/.test(value))) &&
        ((parent?.type === "ObjectProperty" && parent.value === node && !parent.computed) ||
          (parent?.type === "ArrayExpression" &&
            parent.elements.length >= 2 &&
            parent.elements.indexOf(node) > 0 &&
            parent.elements[0]?.type === "StringLiteral") ||
          parent?.type === "ConditionalExpression" ||
          (parent?.type === "LogicalExpression" && parent.right === node) ||
          parent?.type === "ReturnStatement" ||
          (parent?.type === "CallExpression" &&
            ["note", "carePageHeading"].includes(parent.callee?.name)))
      ) {
        add(value);
        edits.push({
          start: node.start,
          end: node.end,
          value: `ntTr(${source.slice(node.start, node.end)})`,
        });
      }
    }
    for (const [key, value] of Object.entries(node))
      if (!["loc", "tokens", "comments", "extra"].includes(key)) {
        if (Array.isArray(value)) value.forEach((x) => walk(x, node));
        else if (value && typeof value === "object") walk(value, node);
      }
  }
  walk(ast, null);
  let result = source;
  for (const e of edits.sort((a, b) => b.start - a.start))
    result = result.slice(0, e.start) + e.value + result.slice(e.end);
  if (!catalogOnly) fs.writeFileSync(file, result);
}
for (const key of [
  "Application language",
  "Language",
  "Arabic interface wording is a draft; qualified language review is pending.",
  "Changing language reloads the application and clears unsaved input. Continue?",
  "Arabic voice is unavailable on this device. You can read the text or type instead.",
  "Original-language care text is shown without automatic translation.",
  "These research activities remain English-only. Changing the app language does not translate the assessment.",
])
  catalog.add(key);
const out = path.join(root, "tmp", "localization-review");
fs.mkdirSync(out, { recursive: true });
fs.writeFileSync(
  path.join(out, "source-strings.json"),
  JSON.stringify([...catalog].sort(), null, 2),
);
console.log(JSON.stringify({ tagged_files: files.length, static_strings: catalog.size }));
