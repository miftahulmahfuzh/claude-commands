---
name: reap-orphaned-blobs
description: Delete Vercel Blob objects under `shots/` that no database row references, for Run Insights. Use when asked to reap, prune, clean up or garbage-collect the blob store — e.g. "reap the orphaned blobs", "the Blob store is filling up", "how much of the store is garbage?", "did that double-upload bug leave blobs behind?", "clean up shots/" — or after any bug that wrote blobs nothing points at. Also use before worrying about Blob free-tier usage, since most of it is usually orphans.
---

# Reap orphaned blobs

> **This is the travelling copy. The canonical one is `.claude/skills/reap-orphaned-blobs/SKILL.md`
> inside the `run-insights` repo, next to the `scripts/blob-reap.mjs` it drives.** Edit it there and
> re-copy; editing this file alone leaves the two out of step. This copy exists so the skill is
> discoverable from any directory on any laptop — but it only *works* from a `run-insights` checkout,
> because the script and the `.env.local` holding `DATABASE_URL` and `BLOB_READ_WRITE_TOKEN` both
> live there. Invoked from anywhere else, stop and say so rather than improvising a reaper.

**A blob is written before any row points at it.** The browser PUTs straight to Blob and only then
does `POST /api/extract` insert the `extractions` row naming it (F04 §10). Anything interrupting
that gap leaves bytes nothing references, and nothing ever cleans them up on its own:

- a pick the runner abandoned before "Read this run"
- a kind change — `changeKind` re-uploads from the original bytes, abandoning the first blob on
  purpose, because the kind is baked into a signed upload token (F16 §3)
- a superseded upload whose result `patchIfCurrent` correctly dropped
- a failed extraction
- every dev session
- and, until F17, **one blob per picked file** from `onPick`'s Strict Mode double-fire

Measured 2026-08-21: 63 blobs in the store, **15 referenced and 48 orphans** — 76% of the objects
and 3.1 MB of the 4.6 MB were garbage.

## The one thing to get right

**A blob is live if the database names it anywhere. Deleting a live blob destroys a runner's photo
with no recovery.** So the question is never "does this look like debris" — it is "can any row
still name it".

Live means the **union** of two places, and both halves are load-bearing:

| Source | Why it cannot be skipped |
|---|---|
| `run_photos.pathname`, `run_photos.blob_url` | The mutable lifecycle, and the authority after a share revocation — `lib/share/rotateBlobs.ts` renames the blob and writes the new location here (R-15) |
| `extractions.blob_urls` (jsonb array) | An immutable upload-time snapshot; can be the **only** reference to an extraction not yet committed to a run |

Collect **both** `pathname` and `url` from each source. A blob survives if either of its own names
appears — matching one field alone deletes a photo whose row stores the other spelling.

`extractions.blob_urls` goes **stale** after a rotation, naming bytes that no longer exist. That
direction is harmless: a reference to nothing protects nothing. It shows up in the script's
`db rows naming missing bytes` line.

## The loop

### 1. Dry run first, always

```bash
npm run blob:reap                                        # or:
node --env-file=.env.local scripts/blob-reap.mjs
```

`npm run blob:reap` is the dry run; flags go after `--`, e.g. `npm run blob:reap -- --delete`.
The script is dry by default; `--delete` is the only thing that destroys anything. Read the output
before going further — in particular, `referenced` should be a multiple of 3-ish and roughly match
`select count(*) from run_photos`.

### 2. Check the interlock did not fire

```
REFUSING: the database named 0 live blobs while the store holds 15.
```

**This is the failure that matters, and it exits 1.** Every blob looks unreferenced when the
database says nothing — which is exactly what a `DATABASE_URL` pointing at the wrong Neon branch,
an empty local Postgres, or a typo'd env file produces. The arithmetic stays internally consistent,
so the mistake is silent and its happy path is "delete the entire store".

If you see this, **fix the connection**. `--allow-empty-db` exists for a store that genuinely is
all garbage; reaching for it to make a refusal go away is how you lose photos.

### 3. Choose the age floor deliberately

`--min-age-hours` defaults to **24**. It exists for the one race that is not a bug: someone who has
picked screenshots and not yet pressed "Read this run" owns blobs no row mentions yet. Deleting
those breaks a live session.

- **Production, unattended:** leave it at 24.
- **A dev store you just made a mess of:** lower it, but state the reasoning. On 2026-08-21 the
  whole store was under two hours old, so `--min-age-hours 0.2` (12 minutes) reaped everything
  while keeping a real guard armed rather than disabling it.
- **Never** pass `0` out of impatience. A guard set to twelve minutes is a decision; a guard set to
  zero is an accident waiting for a user to be mid-upload.

### 4. Delete, then verify

```bash
node --env-file=.env.local scripts/blob-reap.mjs --min-age-hours 0.2 --delete
node --env-file=.env.local scripts/blob-reap.mjs          # confirm: unreferenced 0
```

The verifying dry run is the point. A reap that worked leaves `unreferenced 0` and
`referenced == blobs in store`.

## What it never touches

Only `shots/`. Anything under another prefix is counted and reported as `elsewhere — never
touched`, because this script knows the reference sites for screenshots and nothing else. If a
future feature writes blobs under a new prefix, **teach the script that prefix's reference sites
before pointing it at them** — an unknown prefix with no known references is indistinguishable from
pure garbage, which is exactly the interlock's whole subject.

## Common mistakes

| Mistake | What happens |
|---|---|
| Matching `pathname` only | Deletes photos whose row stores the URL spelling |
| Reading `run_photos` only | Deletes a pending extraction's screenshots before it is committed |
| Reading `extractions` only | Deletes rotated photos, since that snapshot holds the pre-rotation path |
| `--allow-empty-db` to silence a refusal | Deletes the whole store on a misconfigured connection |
| `--min-age-hours 0` in production | Deletes the blobs of whoever is uploading right now |
| Trusting "it looks like debris" | Age and naming are evidence; appearance is not |

## Adding a new reference site

If a feature starts storing blob URLs somewhere new — another jsonb column, a share bundle
snapshot, anything — **add it to the `live` set in the same commit**. The check is cheap:

```bash
grep -nE "jsonb\('|url|pathname" lib/db/schema.ts
```

`extractions.blob_urls`, `run_photos.blob_url` and `run_photos.pathname` are the only three today.
`insights.payload`, `extractions.raw_response` and `extractions.corrections` are jsonb but hold no
blob references — confirmed, not assumed.

## Testing note

This skill's script was verified end to end against the real store on 2026-08-21: a dry run, a
48-blob delete, a confirming dry run, and the interlock exercised with `live` forced empty (refuses
and exits 1 even with `--delete` present). It has **not** been pressure-tested with subagents the
way `superpowers-extended-cc:writing-skills` prescribes.
