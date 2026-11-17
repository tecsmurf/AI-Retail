# Following a shopper through the store (re-identification)

Status: **in-camera linking tested on made clips only; cross-camera linking
built but OFF by default** (`REID_STORE_LINKING=false`) until it is checked on
a store's own cameras. Nothing here is accuracy in a real store.

## What it does

1. While a video is analysed, about once a second per person the worker
   computes an appearance descriptor from the whole-body crop
   (`app/cv/reid.py`, LightMBN-n, ~30 ms per crop on 4 vCPU). Crops cut off by
   the frame edge or covered >20% by another person are skipped.
2. After the video, `app/cv/linker.py` joins track fragments of the same
   person into one shopper when the gap looks like a short occlusion: the
   person vanished inside the picture and reappeared close by within 10 s,
   and the descriptors are close. The distance limit (0.40) is lowered
   automatically to 0.9 x the 5th percentile of distances between people seen
   at the same time, and halved for dark video (mean grey < 90).
3. Re-entries (walked out, came back; or a long gap) are **not** joined.
4. Optional, off by default: `app/services/visit_service.py` links shoppers
   across cameras and consecutive files of one store into store visit ids
   (`V...`) and rebuilds journeys across cameras.
5. Each video also stores a feet-position heatmap (64 x 36 grid, person
   seconds), shown on the Heatmap page over the camera picture.

## Results on the 16 made clips (17 Nov 2026)

Same clips and truth as the 16 Nov vision check (4 public Intel sample scenes
x clear / cheap CCTV / dark / blurry 4 fps; truth counted by Claude, not a
human). "People" = distinct people counted in the video.

| Scene | True | Clear | Cheap CCTV | Dark | Blurry 4 fps |
|---|---|---|---|---|---|
| Store aisle (busy) | 6 | 8 -> **7** | 10 -> **7** | 14 -> 14 | 9 -> **7** |
| One by one | 6 | 6 -> 6 | 6 -> 6 | 6 -> 6 | 6 -> 6 |
| People walking | 7 | 7 -> 7 | 7 -> 7 | 1 -> 1 | 8 -> 8 |
| Corridor | 7 | 7 -> 7 | 7 -> 7 | 1 -> 1 | 7 -> 7 |

Entries unchanged on every clip. Every join made on the clear, CCTV and
blurry aisle clips was checked against crop sheets: all correct (hat man,
teal top woman, brown jacket woman, blue jacket man). The remaining extra
person on each aisle clip comes from the tracker swapping two people's ids
mid-track, which joining cannot fix.

Cost: re-ID took 6 s of ~26-31 s processing for the 65 s busy aisle clip
(about +25% on a busy camera), 0.1-3 s on quieter clips.

## What went wrong on the way (why the defaults are strict)

* With a plain distance limit and 90 s gaps, the one-by-one clip dropped from
  6 people to 3: two different men dressed in black, seen from behind, were
  0.11 apart, and a grey-cardigan woman and a blonde woman in black 0.27
  apart. Hence re-entries are never joined.
* On dark (grey, grainy) video every person looked alike (people seen at the
  same time were 0.09-0.2 apart). The self-calibration and the dark-video
  guard stop joins there; the dark aisle stays at 14.
* Two-camera test made by cutting one public clip into two "cameras": the
  model put the same woman 0.46 apart across the cut (colour/size change,
  one short crop) and two different women 0.25 apart on one camera. This
  is why cross-camera linking ships off. The cut test is weak (people are
  half out of frame); real two-camera footage is needed.

## Privacy

No face model. Descriptors are numbers about clothing and build; they stay in
memory during analysis, and (only when store linking is on) one per fragment
is kept in object storage for `REID_DESCRIPTOR_HOURS` (24) and then deleted.
Visits are never linked across days. See DECISIONS D24 and the privacy pack
addendum.

## Next

1. Run on a recording from the shop's Hikvision cameras; label a few minutes.
2. Two cameras from the same shop, same time: measure cross-camera joins
   before switching `REID_STORE_LINKING` on.
3. Floor-plan heatmap: place each camera on a store plan (4 points) so the
   per-camera heatmaps join into one store map.
4. Licence: weights are trained on research datasets (see D24).
