# Icons

The bundled icon library: 55 entries in `assets/icons/`, used through `dax.py icon`. Icons are the one kind of picture allowed on a slide, and only because they carry no words.

## Rules

- **Functional, never decorative.** An icon labels something - a KPI tile, a process step, a category column, an `.exh-t` caption. If removing it loses no information, remove it.
- **Small.** 20-32px on the slide. The default is 24px. Never scale an icon up to fill space.
- **On palette.** Glyphs are tinted to a brand token: `navy` (default), `brandBlue`, or `white` inside a navy circle; `black`, `slate` and `muted` for quiet labels. `positive` / `warning` / `negative` only when the icon signals that state.
- **One per label.** A KPI row of four tiles gets at most four icons. A slide never gets an icon in every bullet.
- **No icon fonts, no emoji, no inline `<svg>`.** Always the `<img>` snippet the command returns.
- Illustration-style icons keep their own colours, which are off palette. Use one only when the user asked for that specific icon.
- The logo goes in the footer's left span or on a title slide, sized by height (22-28px), never recoloured or stretched.

## Commands

```bash
dax.py --workspace WS icon list --search revenue      # find candidates by name or tag
dax.py --workspace WS icon use kpi --size 24 --color navy
dax.py --workspace WS icon use tick --size 20 --color positive
dax.py --workspace WS icon use data-axle-logo --size 24
```

`icon use` writes the file into `WS/images/` (tinted glyphs are rendered at 2x for crisp export) and returns `img_html`, which references `../images/...` - the path the verify screenshot, the preview inliner and the export all resolve. Paste `img_html` as returned; do not restyle it beyond adjusting `margin`.

| Flag | Meaning |
|---|---|
| `--size` | CSS pixels, 12-96. Slide icons are 20-32. |
| `--color` | Brand token or 6-digit hex. Ignored for illustrations and the logo. |

## Patterns

**Points (the most common use):** `dax.py exhibit --type points` puts each icon in white inside a
navy circle for you. Pass the icon name in each item. Only **glyph** icons work there.



**KPI tile with an icon label** (paste inside a `kpi_row` tile or your own):

```html
<div style="display:flex;align-items:center;gap:10px;margin-bottom:8px;">
  <img src="../images/icon-kpi-navy-24.png" alt="" style="width:24px;height:24px;display:block;flex:0 0 auto;">
  <div style="font-size:9.5px;letter-spacing:.09em;text-transform:uppercase;color:#6A7C90;font-weight:700;">Match-rate lift</div>
</div>
```

**Process step header**: put the icon before the step title inside the navy header bar, tinted `brandBlue` so it reads against navy.

**Footer logo**:

```html
<span style="display:flex;align-items:center;gap:10px;">
  <img src="../images/data-axle-logo.svg" alt="Data Axle" style="height:22px;width:auto;display:block;">
  <span>Exhibit 1 | What the exhibit shows</span>
</span>
```

## Export behaviour

Icons become pictures in the PPTX. Text next to them stays editable text. The export result does not count icons; check them by eye in the verify screenshot.

## Catalogue

### Glyphs - tintable (41)

| Name | Tags |
|---|---|
| `accept` | check, done, approved, success, complete, yes |
| `adding` | add, plus, new, create, insert, expand |
| `ai-model` | ai, model, neural, machine learning, llm, network |
| `arrow-right` | arrow, next, forward, flow, step, direction |
| `banned` | block, stop, prohibited, no, forbidden, exclude, suppress |
| `brand` | brand, award, badge, reputation, identity, ribbon |
| `calendar` | calendar, date, schedule, timeline, month, deadline |
| `channel` | channel, media, distribution, share, social, outlets |
| `coding` | code, developer, engineering, api, software, integration |
| `context` | context, document, notes, brief, reference, file |
| `cpu` | cpu, chip, processor, compute, hardware, infrastructure |
| `crowd-of-users` | audience, users, customers, people, segment, population, crowd |
| `data` | data, records, dataset, cloud, media, assets |
| `database` | database, storage, warehouse, schema, table, records |
| `database-filled` | database, storage, warehouse, records, sql, filled |
| `email` | email, envelope, message, mail, newsletter, outreach |
| `favorite` | star, favorite, rating, quality, top, preferred |
| `filter` | filter, funnel, segment, refine, criteria, select |
| `fingerprint` | identity, fingerprint, unique, match, security, verification |
| `interactive` | click, interactive, touch, engagement, action, cta |
| `interconnected` | connected, hierarchy, org, structure, tree, relationship |
| `kpi` | kpi, metric, gauge, performance, dashboard, speedometer |
| `layout` | layout, grid, template, structure, design, wireframe |
| `link` | link, url, connection, hyperlink, integration, chain |
| `list` | list, bullets, checklist, items, agenda, menu |
| `lock` | lock, security, privacy, compliance, protected, encryption |
| `mail` | mail, envelope, email, letter, direct mail, post |
| `multi-channel` | multichannel, channels, hierarchy, distribution, branches |
| `multi-channel-devices` | multichannel, devices, omnichannel, mobile, desktop, cross-device |
| `network` | network, graph, nodes, connections, ecosystem, integration |
| `quality` | quality, certified, badge, verified, standard, seal |
| `refresh` | refresh, reload, cycle, repeat, iterate, loop |
| `refresh-data` | refresh, sync, update, database, reload, pipeline |
| `route` | route, path, journey, roadmap, steps, process |
| `send` | send, submit, deliver, launch, paper plane, dispatch |
| `speed` | speed, fast, performance, velocity, latency, gauge |
| `target` | target, goal, objective, aim, precision, bullseye |
| `tick` | check, tick, done, complete, verified, approved |
| `two-arrows` | exchange, swap, sync, transfer, bidirectional, integration |
| `user` | user, person, profile, customer, contact, individual |
| `warning` | warning, risk, alert, caution, issue, attention |

### Illustrations - keep their own colours, off palette (13)

| Name | Tags |
|---|---|
| `ai-brain` | ai, brain, intelligence, model, llm, machine learning |
| `artificial-intelligence` | ai, atom, science, intelligence, model |
| `campaign` | campaign, marketing, megaphone, promotion, announce, outreach |
| `coins` | money, revenue, cost, price, coins, budget, finance |
| `conversation` | chat, conversation, message, question, support, dialogue |
| `data-analysis` | analysis, analyst, chart, insight, report, dashboard |
| `deal` | deal, handshake, agreement, partnership, contract, sales |
| `direction` | direction, signpost, choice, decision, path, options |
| `excel` | excel, spreadsheet, xlsx, data file, microsoft |
| `google-docs` | document, docs, google, file, text |
| `support` | support, help, service, care, assistance, customer service |
| `system-update` | update, upgrade, system, settings, gear, maintenance |
| `task` | task, checklist, clipboard, todo, plan, action items |

### Logo

| Name | Tags |
|---|---|
| `data-axle-logo` | logo, brand, data axle, wordmark |

Attribution for the icon files is in `assets/icons/ATTRIBUTION.md`.
