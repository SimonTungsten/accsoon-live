# Accsoon Live

A minimal, password-protected browser viewer for the Accsoon CineView SE 4K USB receiver on macOS. The native reader reconstructs H.265 video; FFmpeg produces a low-latency WebRTC feed through MediaMTX, with adaptive HLS fallback. The viewer has no playback controls or overlays. Any camera OSD in the incoming video remains visible. Audio is not relayed.

This is the native USB project, not the separate M7 Pro screen-mirroring relay or Android companion. Receiver support is specific to USB VID `0x3561`, PID `0x0064`; other Accsoon hardware is not established as compatible.

## Requirements and build

- macOS with VideoToolbox H.264 encoding support.
- Xcode Command Line Tools, Python 3, FFmpeg, MediaMTX, libusb and pkg-config.
- A compatible receiver connected by USB and receiving video.

```sh
brew install python ffmpeg mediamtx libusb pkg-config
make
make test
```

Python runtime code uses only the standard library. `web/hls.min.js` bundles hls.js 1.5.17; its license and notices are included alongside it.

## Run

From this folder, enter a private password without placing it in shell history:

```sh
export STREAM_PASSWORD="$(python3 -c 'import getpass; print(getpass.getpass("Viewer password: "))')"
python3 service.py
```

Open <http://127.0.0.1:8888/>. The supervisor runs in the foreground; Ctrl-C stops its child processes. Do not start another reader or pipeline against the same receiver. Keep the Mac and receiver awake.

For viewing from other devices on a trusted LAN, set `STREAM_HOST=0.0.0.0` before starting and open the Mac's LAN address on port 8888. `STREAM_PORT` optionally changes that HTTP port. MediaMTX discovers local interface addresses; if needed, set `MTX_WEBRTCADDITIONALHOSTS` to the hostname or address reachable by viewers. WebRTC media uses UDP/TCP port 8189. Internal RTSP (8554) and WebRTC signaling (8889) bind to loopback.

The server refuses to start without a non-empty `STREAM_PASSWORD`. It generates a local `.session-key` with owner-only permissions. Keep that file private. Login cookies last up to one year; changing the password alone does not revoke existing cookies. To revoke all sessions, stop the service, remove its local `.session-key`, and restart with a new password.

## Publication and deployment boundaries

This repository contains source, generic configuration and synthetic parser tests only. It excludes existing credentials, personal machine paths, device-specific identifiers, public tunnel addresses, recorded footage, screenshots, logs, USB dumps, compiled executables, APKs and signing keys. Development captures and vendor firmware are not part of this distribution. Protocol magic values and USB product IDs identify a format/device family, not an account credential.

Runtime logs and process IDs go into the ignored `verification/` folder; HLS media goes into `/tmp/accsoon_hls`. Those files can contain private footage or network details. Do not publish them or ZIP an active working directory. Use `git archive HEAD` for a source-only export, and review staged files before future commits.

The built-in server is plain HTTP and is intended for a trusted LAN. Public-internet deployment needs HTTPS and a separate deployment-security review. Publication sanitization is not a guarantee that this prototype is hardened for hostile networks. No tunnel is configured or started by this project.

## Components

- `reader.c`: asynchronous libusb capture with ordered transfer emission.
- `framer.py`: fragment reassembly and H.265 output.
- `serve-native.sh`: FFmpeg WebRTC/RTSP and adaptive HLS pipeline.
- `service.py`: process supervision.
- `hlsserve.py`: password-gated viewer, HLS files and WebRTC signaling proxy.
- `mediamtx.yml`: generic MediaMTX configuration.
- `web/`: browser player and bundled HLS dependency.
- `tests/test_framer.py`: synthetic reassembly regression tests.

See `PROTOCOL.md` for the transport layout used by the reader. The project is an independent prototype, not an official Accsoon product.

## Publication verification

The source-only export was verified with a native reader build, both existing reassembly tests, Python/JavaScript and shell syntax checks, and a Gitleaks source scan. An isolated HTTP smoke run covered missing-password refusal, incorrect-password rejection, successful login, authenticated asset access, unauthenticated media/WebRTC rejection, forged-cookie rejection and private session-key permissions. The generic MediaMTX configuration also started successfully on isolated local ports. The bundled hls.js file matched the published 1.5.17 distribution byte for byte.

Physical receiver capture and end-to-end live browser playback were not repeated during publication preparation.
