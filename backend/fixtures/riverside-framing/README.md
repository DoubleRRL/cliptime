# Riverside framing reference fixtures

Visual reference kit for matching SupoClip output to Riverside Magic Clip exports (`apr23.mp4`).

## Directory layout

| Path | Meaning |
|------|---------|
| `target/` | **Where we're going** — stills from finished Riverside 9:16 export |
| `source/` | **Where we're coming from** — stills from raw 1280×720 side-by-side upload |
| `invisible_bookcase_troupe_jeans_stud.mp4` | Short Riverside export for caption sizing QA (gitignored) |
| `caption-measurements/` | Generated frames + overlay QA from `scripts/measure_riverside_captions.py` |

## Target stills (`apr23.mp4`)

| File | Timestamp | Description |
|------|-----------|-------------|
| `target/solo_green_shirt.jpg` | 1s | Solo — one speaker, face-centered, bookshelf background |
| `target/solo_hat_door.jpg` | 14s | Solo — other speaker, hat + door background |
| `target/dual_stacked.jpg` | 28s | Dual — two speakers stacked vertically, captions on seam |

## Source stills (raw upload @ 17:15–17:32)

| File | Timestamp | Description |
|------|-----------|-------------|
| `source/side_by_side_laugh.jpg` | 17:24 | Both speakers laughing, grid layout |
| `source/right_column_react.jpg` | 17:30 | Right column reacting |
| `source/left_column_speaking.jpg` | 17:32 | Left column monologue |

## Caption sizing reference

`invisible_bookcase_troupe_jeans_stud.mp4` — 1080×1920 Riverside export used to calibrate template defaults (`font_size` base **32**, `position_y` **0.77**).

```bash
cd backend && uv run python scripts/measure_riverside_captions.py
```

## Test slice

`test_slice.mp4` — ffmpeg cut from `riverside_meech_& rrl 06_troupe_jeans's stud.mp4`:

```bash
ffmpeg -ss 1035 -t 90 -i "<source.mp4>" -c:v libx264 -preset ultrafast -c:a aac test_slice.mp4
```

Covers 17:15–18:45 in the full recording (includes the card-joke clip at ~17:24).

## Verification workflow

1. Upload `test_slice.mp4` to SupoClip (not the full 21-min file).
2. Delete any `.speaker_panel_cache.json` beside the slice to force recalibration.
3. Run the pipeline; compare exported clip frames to `target/` stills.
4. Solo segments should match `solo_*.jpg` (face centered, not door/peephole).
5. Reaction beats should match `dual_stacked.jpg` (stacked layout).
6. Final sign-off: one run on the full source file.

## Regenerate stills

```bash
# Target (apr23)
ffmpeg -ss 1  -i apr23.mp4 -frames:v 1 target/solo_green_shirt.jpg
ffmpeg -ss 14 -i apr23.mp4 -frames:v 1 target/solo_hat_door.jpg
ffmpeg -ss 28 -i apr23.mp4 -frames:v 1 target/dual_stacked.jpg

# Source (OG upload)
ffmpeg -ss 17:24 -i "<source.mp4>" -frames:v 1 source/side_by_side_laugh.jpg
ffmpeg -ss 17:30 -i "<source.mp4>" -frames:v 1 source/right_column_react.jpg
ffmpeg -ss 17:32 -i "<source.mp4>" -frames:v 1 source/left_column_speaking.jpg
```
