#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")"
OUT=/tmp/accsoon_hls
mkdir -p "$OUT" verification
./reader 0 2>verification/live-reader.log |
  python3 -u framer.py 2>verification/live-framer.log |
  ffmpeg -hide_banner -loglevel error -fflags +genpts -r 60 -f hevc -i - \
    -map 0:v:0 -an -vf fps=30 -c:v h264_videotoolbox -realtime 1 -profile:v baseline -bf 0 -pix_fmt yuv420p -b:v 2500k -g 30 \
    -f rtsp -rtsp_transport tcp rtsp://127.0.0.1:8554/live \
    -map 0:v:0 -map 0:v:0 -an \
    -filter:v:0 fps=30 -filter:v:1 scale=1280:720,fps=30 \
    -c:v h264_videotoolbox -realtime 1 -pix_fmt yuv420p -g 30 \
    -b:v:0 3500k -maxrate:v:0 4200k -bufsize:v:0 7000k \
    -b:v:1 1500k -maxrate:v:1 1800k -bufsize:v:1 3000k \
    -f hls -hls_time 1 -hls_list_size 20 -hls_delete_threshold 10 \
    -hls_start_number_source epoch -hls_flags delete_segments+independent_segments+temp_file \
    -var_stream_map 'v:0 v:1' -master_pl_name stream.m3u8 -master_pl_publish_rate 1 \
    -hls_segment_filename "$OUT/live%v%010d.ts" "$OUT/v%v.m3u8" \
    2>verification/live-ffmpeg.log
