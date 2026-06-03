# CV Pipeline

## Architecture
```
Video Frame → Person Detection (YOLO11) → Multi-Object Tracking (ByteTrack) → Zone Mapping → Event Generation
```

## Person Detection
- **Model**: YOLO11n (nano variant for speed)
- **Classes**: Person only (COCO class 0)
- **Confidence**: 0.5 threshold
- **Output**: Bounding boxes (x1, y1, x2, y2), confidence scores

## Multi-Object Tracking (ByteTrack)
- **Algorithm**: Two-stage IoU matching
- **Stage 1**: High-confidence detections matched to existing tracks
- **Stage 2**: Low-confidence detections matched to remaining tracks
- **Track buffer**: 30 frames before declaring lost
- **Output**: Persistent track IDs across frames

## Zone Mapping
- **Algorithm**: Ray-casting point-in-polygon
- **Input**: Bottom-center of bounding box (foot position)
- **Zones**: Predefined polygons per store/camera
- **Output**: Zone name for each tracked person

## Event Generation
Transitions are detected by comparing current zone vs previous zone:
- New track → `ENTRY` event
- Zone changes → `ZONE_EXIT` + `ZONE_ENTER` events
- Track lost → `EXIT` event
- Long zone stay → `DWELL_TIME` event

## Processing Modes
1. **Real-time**: Process live RTSP streams at 5 FPS
2. **Batch**: Process uploaded video files
3. **Demo**: Use pre-generated events from sample data

## Performance
- YOLO11n: ~50ms/frame on GPU, ~200ms on CPU
- ByteTrack: ~2ms/frame
- Zone mapping: ~0.1ms/frame
- **Total**: 5-10 FPS on GPU, 2-3 FPS on CPU
