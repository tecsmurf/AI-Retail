"""Person-detection benchmark on COCO val2017 (person category only).

    pip install pycocotools
    python eval/coco_person_benchmark.py COCO_DIR MODEL.pt clean|cctv [N]

COCO_DIR holds images/val2017 and annotations/instances_val2017.json (the
Ultralytics coco2017val.zip release asset has both). N images that contain at
least one person are picked with a fixed seed (default 1000), so every model
sees the same images. "cctv" degrades each image the way a CCTV substream
does: half resolution and JPEG quality 30, scaled back up.

Prints one JSON line: person AP (COCO 0.50:0.95), AP50, AP by size, AR@100,
recall of boxes above confidence 0.35, and mean CPU latency per image. Used
for the model choice in docs/CV_VALIDATION.md.
"""
import contextlib
import io
import json
import random
import sys
import time
from pathlib import Path

import cv2
import numpy as np
from pycocotools.coco import COCO
from pycocotools.cocoeval import COCOeval
from ultralytics import YOLO

ROOT = Path(sys.argv[1])
model_path, cond = sys.argv[2], sys.argv[3]
n = int(sys.argv[4]) if len(sys.argv) > 4 else 1000
if cond not in ("clean", "cctv"):
    sys.exit("condition must be clean or cctv")
with contextlib.redirect_stdout(io.StringIO()):
    gt = COCO(str(ROOT / "annotations/instances_val2017.json"))
ids = sorted(gt.getImgIds(catIds=[1]))
random.Random(0).shuffle(ids)
ids = sorted(ids[:n])

model = YOLO(model_path)
model.predict(np.zeros((640, 640, 3), np.uint8), verbose=False, device="cpu")
dets, times = [], []
for iid in ids:
    info = gt.loadImgs(iid)[0]
    img = cv2.imread(str(ROOT / "images/val2017" / info["file_name"]))
    if cond == "cctv":
        h, w = img.shape[:2]
        small = cv2.resize(img, (w // 2, h // 2), interpolation=cv2.INTER_AREA)
        ok, buf = cv2.imencode(".jpg", small, [cv2.IMWRITE_JPEG_QUALITY, 30])
        img = cv2.resize(cv2.imdecode(buf, cv2.IMREAD_COLOR), (w, h), interpolation=cv2.INTER_LINEAR)
    t0 = time.perf_counter()
    r = model.predict(img, conf=0.001, iou=0.6, imgsz=640, classes=[0], device="cpu", verbose=False, max_det=300)[0]
    times.append(time.perf_counter() - t0)
    for (x1, y1, x2, y2), s in zip(r.boxes.xyxy.cpu().numpy(), r.boxes.conf.cpu().numpy()):
        dets.append({"image_id": iid, "category_id": 1, "bbox": [float(x1), float(y1), float(x2 - x1), float(y2 - y1)], "score": float(s)})

def evaluate(d):
    with contextlib.redirect_stdout(io.StringIO()):
        dt = gt.loadRes(d) if d else None
        e = COCOeval(gt, dt, "bbox")
        e.params.imgIds = ids
        e.params.catIds = [1]
        e.evaluate()
        e.accumulate()
        e.summarize()
    return e.stats

s = evaluate(dets)
# Recall/precision at the operating threshold, IoU 0.5, non-crowd people.
op = [x for x in dets if x["score"] >= 0.35]
so = evaluate(op) if op else [0] * 12
res = {
    "model": Path(model_path).stem, "cond": cond, "images": len(ids),
    "AP": round(s[0], 4), "AP50": round(s[1], 4), "AP_small": round(s[3], 4), "AP_medium": round(s[4], 4),
    "AP_large": round(s[5], 4), "AR100": round(s[8], 4),
    "AR_at_conf0.35": round(so[8], 4),
    "ms_per_image": round(1000 * float(np.mean(times[5:])), 1),
}
print(json.dumps(res))
