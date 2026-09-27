# Accsoon CineView SE 4K USB transport notes

The reader targets USB VID `0x3561`, PID `0x0064`, interface 0. Bulk endpoints are `0x81` (input) and `0x02` (output). This is not UVC.

## Transport header

- Bytes 0–3: protocol magic `c6 ea 85 78`.
- Byte 4: channel.
- Bytes 6–7: little-endian payload length; total packet length is this value plus 8.
- Bytes 8–11: inner magic `93 6e 77 78`.
- Bytes 12–15: sender UID. No captured device UID is distributed here.
- Byte 16: protocol version `0x40`.
- Byte 17: inner channel.
- Bytes 18–19: command.

The connect packet in `reader.c` requests stream 0 using the arbitrary client UID `0x12345678`; it is periodically resent as a keepalive. These protocol constants are not authentication credentials. Beacon decryption material is not included and is not required by this pipeline.

## Fragment reassembly

Media packs have a 32-byte transport header. Sequence number, fragment count and fragment index begin at byte 24 (`<IHH`). Concatenate the bytes after offset 32 in fragment-index order.

The reassembled message has one 24-byte metadata header. Its little-endian length at offset 20 must match the remaining encoded payload length. Strip this metadata once, not once per fragment. Incomplete messages are discarded. The framer caches VPS/SPS/PPS and waits for an IDR frame before resuming output after gaps.

The native reader writes a four-byte little-endian transfer length followed by transfer bytes. `framer.py` consumes that stream and writes H.265 Annex-B video. The FFmpeg pipeline transcodes it for browsers.
