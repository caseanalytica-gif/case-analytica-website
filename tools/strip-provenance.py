#!/usr/bin/env python3
"""Strip embedded tool metadata (C2PA manifests, XMP, text chunks) from site media.

Files handed back by some tools arrive with a signed C2PA "content credentials"
manifest naming the tool. This removes it without re-encoding: JPEG segments and
PNG chunks are dropped byte-for-byte, and MP4s are remuxed with ffmpeg -c copy,
because the manifest box sits before mdat and deleting it by hand would break
the chunk offsets.

  python3 tools/strip-provenance.py [--check] <dir-or-file> ...

--check lists what would change and exits 1 if anything would, writes nothing.
The deploy workflow runs it over the built site, so new media is covered even
if nobody remembers to run it locally.
"""
import os
import shutil
import struct
import subprocess
import sys
import tempfile

MARKERS = (b"c2pa", b"jumb", b"anthropic", b"claude", b"openai", b"dall-e",
           b"midjourney", b"trainedalgorithmicmedia", b"xmpmeta")
C2PA_UUID = bytes.fromhex("d8fec3d61b0e483c92975828877ec481")


def flagged(blob):
    low = blob.lower()
    return any(m in low for m in MARKERS)


def strip_jpeg(d):
    if d[:2] != b"\xff\xd8":
        return d
    out, i = bytearray(d[:2]), 2
    while i + 4 <= len(d):
        if d[i] != 0xFF:
            return d  # not a clean marker stream; leave the file alone
        m = d[i + 1]
        if m == 0xDA:  # start of scan: everything after is image data
            out += d[i:]
            return bytes(out)
        seg_len = struct.unpack(">H", d[i + 2:i + 4])[0]
        seg = d[i:i + 2 + seg_len]
        # APP11 carries the C2PA JUMBF; APP1/APP13 can carry XMP pointing at it.
        if m == 0xEB or (m in (0xE1, 0xED) and flagged(seg)):
            pass
        else:
            out += seg
        i += 2 + seg_len
    return d


def strip_png(d):
    sig = b"\x89PNG\r\n\x1a\n"
    if d[:8] != sig:
        return d
    out, i = bytearray(sig), 8
    while i + 8 <= len(d):
        n, t = struct.unpack(">I4s", d[i:i + 8])
        chunk = d[i:i + 12 + n]
        if t == b"caBX" or (t in (b"tEXt", b"iTXt", b"zTXt") and flagged(chunk)):
            pass
        else:
            out += chunk
        i += 12 + n
    return bytes(out)


def mp4_has_manifest(d):
    i = 0
    while i + 8 <= len(d):
        size, t = struct.unpack(">I4s", d[i:i + 8])
        hdr = 8
        if size == 1:
            size, hdr = struct.unpack(">Q", d[i + 8:i + 16])[0], 16
        elif size == 0:
            size = len(d) - i
        if t == b"uuid" and d[i + hdr:i + hdr + 16] == C2PA_UUID:
            return True
        if size < hdr:
            return False
        i += size
    return False


def strip_mp4(path):
    fd, tmp = tempfile.mkstemp(suffix=".mp4")
    os.close(fd)
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", path, "-map", "0",
                    "-c", "copy", "-map_metadata", "-1", "-movflags", "+faststart",
                    tmp], check=True)
    shutil.move(tmp, path)


def walk(paths):
    for p in paths:
        if os.path.isfile(p):
            yield p
        else:
            for root, dirs, files in os.walk(p):
                dirs[:] = [x for x in dirs if not x.startswith(".")]
                for f in files:
                    yield os.path.join(root, f)


def main(argv):
    check = "--check" in argv
    targets = [a for a in argv if a != "--check"] or ["."]
    changed = []
    for path in walk(targets):
        ext = os.path.splitext(path)[1].lower()
        if ext not in (".jpg", ".jpeg", ".png", ".mp4", ".m4v", ".mov"):
            continue
        with open(path, "rb") as fh:
            d = fh.read()
        if ext in (".mp4", ".m4v", ".mov"):
            if mp4_has_manifest(d):
                changed.append(path)
                if not check:
                    strip_mp4(path)
            continue
        new = strip_jpeg(d) if ext in (".jpg", ".jpeg") else strip_png(d)
        if new != d:
            changed.append(path)
            if not check:
                with open(path, "wb") as fh:
                    fh.write(new)
    for p in changed:
        print(("would strip " if check else "stripped ") + p)
    print(f"{len(changed)} file(s)")
    return 1 if (check and changed) else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
