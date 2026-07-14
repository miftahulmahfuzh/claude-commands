---
name: confluence-writer
description: Use when writing, formatting, or publishing a document to Confluence (URLs like wiki.*, /pages/viewpage.action?pageId=, or /wiki/spaces/), when markdown pasted into a Confluence page renders with broken formatting, or when the "Insert > Markup" wiki-markup importer fails (HTTP 500, conf_wikimarkup_conversion_errors). Covers Confluence Server/Data Center and Cloud.
---

# Confluence Writer

## Overview

Confluence's editor is **not** markdown. Pasting raw markdown produces broken formatting, and the built-in wiki-markup importer is fragile on many instances (throws HTTP 500 / `conf_wikimarkup_conversion_errors`).

**Core principle: don't fight the importer — paste rich text.** Confluence's editor ingests rich text natively (the same path as pasting from Word/Google Docs). So render the document as HTML, open it in a browser, copy the *rendered* page, and paste into the editor. Headings, tables, bold, lists, code blocks, and panels all convert to native Confluence elements. This works on both Server/DC and Cloud, and bypasses every converter.

## Detect the Confluence flavor first

| URL pattern | Flavor | Native importer |
|---|---|---|
| `.../pages/viewpage.action?pageId=` or `.../display/SPACE/Page` | **Server / Data Center** | "Insert > Markup > Confluence Wiki" (often flaky) |
| `.../wiki/spaces/.../pages/...` | **Cloud** | "Insert > Markdown" (usually reliable) |

The rich-text-paste method below works on **both** — prefer it when in doubt or when an importer 500s.

## The reliable method (rich-text paste)

1. Convert the source (markdown/notes) into a **self-contained HTML file** — you (the assistant) author this directly, following the rules below. Adapt `template.html` in this skill directory.
2. Open it in a browser. WSL: `explorer.exe "$(wslpath -w path/to/file.html)"`. macOS: `open file.html`. Linux: `xdg-open file.html`. Windows: `start file.html`.
3. In the browser: **Ctrl+A** then **Ctrl+C** (select all, copy the rendered page).
4. In the Confluence page editor: **first select and delete any previously-pasted broken content**, click into the body, then **Ctrl+V**.
5. Verify tables/panels rendered; fix any stragglers with the editor toolbar.

## HTML authoring rules (so paste stays clean)

- **Use semantic HTML**, not CSS layout: `<h1>`–`<h3>`, `<table>`/`<th>`/`<td>`, `<ul>`/`<ol>`/`<li>`, `<strong>`, `<em>`, `<code>`, `<pre>`, `<a>`. Confluence keeps structure and drops most inline CSS on paste — that is fine.
- **Tables** carry over well. For a line break *inside* a cell use `<br>`.
- **ASCII diagrams / preformatted text** go in `<pre>`. Escape `<`, `>`, `&` as `&lt;` `&gt;` `&amp;`.
- **Panels/callouts:** a `<div>` styled like an info/note box pastes as a shaded block. (Or add a native panel in the editor afterward.)
- **Avoid** exotic Unicode box-drawing (`─│┌┐`) — it often pastes as garbage. Use plain ASCII (`- | + v`) and ASCII substitutes: `->` not `→`, `x` not `×`, `~` not `≈`, `>=` not `≥`.

## Fallbacks

- **Cloud:** "Insert > Markdown" ingests a markdown file directly — try it first on Cloud.
- **Server wiki markup:** "Insert > Markup > Confluence Wiki" accepts `h2.` headings, `||h||h||` / `|c|c|` tables, `{info}`/`{note}` panels, `{noformat}` blocks, `{{monospace}}`, `\\` for in-cell line breaks. Use only if it doesn't 500.
- **Storage-format XHTML** via REST API for automation — heavy; reserve for scripted publishing.

## Common mistakes

| Symptom | Cause | Fix |
|---|---|---|
| Pasted markdown shows literal `#`, `**`, `\|` | Editor isn't markdown | Use rich-text HTML paste |
| 500 / `conf_wikimarkup_conversion_errors` | Server wiki-markup module flaky/disabled, or a construct choked it | Abandon the importer; use rich-text HTML paste |
| Diagram is scrambled | Unicode box-drawing chars | Redraw in plain ASCII inside `<pre>` |
| Table cell line break lost | Used markdown `<br>`/newline in wiki markup | `<br>` in HTML, or `\\` in wiki markup |
| Only one config's importer works | Wrong flavor assumed | Detect via URL first (table above) |

## Confirm which layer failed

If an importer 500s and you're unsure it's the instance vs your content, paste a trivial snippet (e.g. `<h2>Test</h2>` or `h2. Test`) into the same dialog. Still 500 → it's the module/instance, not your document → switch to rich-text paste.
