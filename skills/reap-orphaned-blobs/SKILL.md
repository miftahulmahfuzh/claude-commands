---
name: reap-orphaned-blobs
description: Delete Vercel Blob objects under `shots/` or `nina/` that no database row references, for Run Insights. Use when asked to reap, prune, clean up or garbage-collect the blob store — e.g. "reap the orphaned blobs", "the Blob store is filling up", "how much of the store is garbage?", "did that double-upload bug leave blobs behind?", "clean up shots/", "clean up Nina's chat photos or album" — or after any bug that wrote blobs nothing points at. Also use before worrying about Blob free-tier usage, since most of it is usually orphans.
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

`nina/` has the same shape: `lib/nina/imageTicket.ts` signs an upload, the browser PUTs, and only
then does a `nina_message_images` row name the bytes. F35 phase 7's message delete logs the
pathnames it strands precisely because nothing reaped them until now.

Measured 2026-08-21: 63 blobs in the store, **15 referenced and 48 orphans** — 76% of the objects
and 3.1 MB of the 4.6 MB were garbage.

## The one thing to get right

**A blob is live if the database names it anywhere. Deleting a live blob destroys a runner's photo
with no recovery.** So the question is never "does this look like debris" — it is "can any row
still name it".

Live means the **union** of every site below, and every half is load-bearing:

| Prefix | Source | Why it cannot be skipped |
|---|---|---|
| `shots/` | `run_photos.pathname`, `run_photos.blob_url` | The mutable lifecycle, and the authority after a share revocation — `lib/share/rotateBlobs.ts` renames the blob and writes the new location here (R-15) |
| `shots/` | `extractions.blob_urls` (jsonb array) | An immutable upload-time snapshot; can be the **only** reference to an extraction not yet committed to a run |
| `nina/` | `nina_message_images.pathname`, `.blob_url` | Chat photos, `nina/<userId>/chat/<id>.jpg` |
| `nina/` | `nina_avatars.pathname`, `.blob_url` | The album, `nina/<userId>/avatar-<id>.<ext>` |
| `nina/` | `nina_avatars.thumb_pathname`, `.thumb_url` | **The derived grid thumbnail is a second object under the same prefix.** Nullable, and a NULL means no thumbnail rather than no reference |

Collect **both** `pathname` and `url` from each source. A blob survives if either of its own names
appears — matching one field alone deletes a photo whose row stores the other spelling.

### Count references; never react to a row disappearing

F35 phase 9's `attachExisting` pins an already-uploaded photo to a new message without re-uploading
a byte, so **one blob is legitimately reachable from two `nina_message_images` rows.** A reaper
that asked "did a row disappear?" would delete a photo another message still shows.

This script never asks that. It reads the whole store and the whole database and asks, per blob,
*how many rows name it* — deleting only at zero. The count is reported rather than collapsed to a
boolean, on two lines that are deliberately different numbers:

- `named by 2+ rows` — for `shots/` this is **every** screenshot, because `run_photos` and the
  `extractions` snapshot that preceded it both name those. It has never meant reuse.
- `reused` — 2+ rows **of one table**. That is the `attachExisting` shape, and the one the card
  was about.

### The interlock is per prefix, and has to be

MEASURED 2026-09-05: with the `nina/` reference sites forced empty, the store held 5 `nina/` blobs
while the database still named 270 live `shots/` names. **A single global "is the database empty?"
check passes on those 270 and deletes all five.** The per-prefix check refuses and exits 1. A
`DATABASE_URL` pointing at a branch that predates the `nina_*` tables is exactly that shape.

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
before going further, **per prefix** — the report is one block per prefix now:

- `shots/` — `referenced` should be a multiple of 3-ish and roughly match
  `select count(*) from run_photos`
- `nina/` — `db names here` runs ahead of `referenced` because one `nina_avatars` row can name two
  objects, the original and its thumbnail. Six names over three blobs is healthy, not a leak
- `reused` non-zero means `attachExisting` has been used; it is a fact, never a problem

Narrow a run with `--prefix nina/` when only one prefix is in question — it reads only that
prefix's reference sites, so it is also the fastest way to check one after a schema change.

### 2. Check the interlock did not fire

```
REFUSING: the database named 0 live blobs under nina/ while the store holds 5.
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

Only the prefixes in the script's `PREFIXES` registry — `shots/` and `nina/` today. Anything else
is counted and reported as `under no known prefix — never touched`. If a future feature writes
blobs under a new prefix, **teach the script that prefix's reference sites before pointing it at
them** — an unknown prefix with no known references is indistinguishable from pure garbage, which
is exactly the interlock's whole subject.

`--prefix nina/` narrows a run to one prefix, and only reads that prefix's reference sites. An
unknown value is rejected with exit 2 rather than silently matching nothing.

### The defensive sweep

`nina_turns.args` and `nina_memory_slots.value` are untyped `jsonb` holding no blob references
today — and `args` exists precisely so a later phase can put its own job shape there. Rather than
assert that and be wrong later, the script walks both columns for strings that look like a known
prefix, **adds anything it finds to the live set**, and says so loudly:

```
!! the jsonb sweep found 2 blob name(s) NO declared reference site holds.
   A writer this script does not know about is naming blobs. Add its column to PREFIXES
   before the next --delete. They are protected for now:
```

A name only the sweep found is a reference site missing from the registry. The blob is protected
either way; the message is what stops the gap from lasting two releases.

## Common mistakes

| Mistake | What happens |
|---|---|
| Matching `pathname` only | Deletes photos whose row stores the URL spelling |
| Reading `run_photos` only | Deletes a pending extraction's screenshots before it is committed |
| Reading `extractions` only | Deletes rotated photos, since that snapshot holds the pre-rotation path |
| Reading `nina_message_images` only | Deletes **every album photo and every derived thumbnail** — `nina_avatars` owns four more columns under the same prefix |
| Forgetting `thumb_pathname` / `thumb_url` | Deletes every grid thumbnail; they are separate objects, and only those two columns name them |
| A global "is the db empty?" interlock | Passes on `shots/` rows while deleting the whole of `nina/` — the guard is per prefix for this reason |
| Reacting to a deleted row | Deletes a photo `attachExisting` still shows on another message |
| `--allow-empty-db` to silence a refusal | Deletes the whole store on a misconfigured connection |
| `--min-age-hours 0` in production | Deletes the blobs of whoever is uploading right now |
| Trusting "it looks like debris" | Age and naming are evidence; appearance is not |

## Adding a new reference site

If a feature starts storing blob URLs somewhere new — another jsonb column, a share bundle
snapshot, anything — **add it to the `live` set in the same commit**. The check is cheap:

```bash
grep -nE "jsonb\('|url|pathname" lib/db/schema.ts
```

Eight columns today: `extractions.blob_urls`, `run_photos.blob_url`, `run_photos.pathname`,
`nina_message_images.blob_url`, `nina_message_images.pathname`, `nina_avatars.blob_url`,
`nina_avatars.pathname`, `nina_avatars.thumb_url` and `nina_avatars.thumb_pathname`.
`insights.payload`, `extractions.raw_response`, `extractions.corrections`, `nina_turns.args` and
`nina_memory_slots.value` are jsonb but hold no blob references — confirmed, not assumed, and the
last two are swept anyway.

## Testing note

Verified end to end against the real store on 2026-08-21: a dry run, a 48-blob delete, a confirming
dry run, and the interlock exercised with `live` forced empty (refuses and exits 1 even with
`--delete` present).

Re-verified 2026-09-05 after the `nina/` prefix landed (P1-RI-A014), against 183 real blobs:

- a full dry run — 276 live names, `shots/` 135 referenced and 43 orphans, `nina/` 3 referenced,
  2 unreferenced and both under the age floor, so **0 orphans** and nothing to delete
- `nina_avatars`' 2 rows produced 6 names covering 3 blobs — the original, its thumbnail, and a
  second original. **Without `thumb_pathname`/`thumb_url` that thumbnail reads as unreferenced**,
  which is the concrete form of the mistake in the table above
- `--prefix nina/` reads only the `nina/` sites; `--prefix bogus/` exits 2
- the per-prefix interlock exercised with the `nina/` sites forced empty, **with `--delete`
  present**: refuses and exits 1 while the database still named 270 `shots/` names — the case a
  global interlock passes

Still **not** pressure-tested with subagents the way `superpowers-extended-cc:writing-skills`
prescribes.
