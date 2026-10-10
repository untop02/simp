"""Compare an ISO file listing against an extracted tree.

Reads the `tools.xiso ls` output captured to logs/m5_iso_listing.txt and
compares every file's size against the same relative path under the game dir.

Usage:
    py -3 scripts/m5_verify_extract.py <listing.txt> <extracted_root>
"""
import os
import sys


def parse_listing(path):
    entries = {}
    with open(path, "r", encoding="utf-8") as fh:
        for line in fh:
            line = line.rstrip("\n")
            if line.startswith("partition base") or not line.strip():
                continue
            parts = line.split(None, 1)
            if len(parts) != 2:
                continue
            size_s, name = parts
            name = name.strip()
            if not size_s.isdigit() or name == "total":
                continue
            entries[name] = int(size_s)
    return entries


def main():
    listing, root = sys.argv[1], sys.argv[2]
    iso = parse_listing(listing)

    missing, mismatch, ok = [], [], 0
    total_iso = 0
    for name, size in sorted(iso.items()):
        total_iso += size
        local = os.path.join(root, *name.split("/"))
        if not os.path.isfile(local):
            missing.append((name, size))
            continue
        actual = os.path.getsize(local)
        if actual != size:
            mismatch.append((name, size, actual))
        else:
            ok += 1

    print("ISO entries      : %d" % len(iso))
    print("ISO total bytes  : %d" % total_iso)
    print("Matched (size ok): %d" % ok)
    print("Missing          : %d" % len(missing))
    print("Size mismatch    : %d" % len(mismatch))
    for n, s in missing:
        print("  MISSING %10d  %s" % (s, n))
    for n, s, a in mismatch:
        print("  MISMATCH iso=%d local=%d  %s" % (s, a, n))

    # Extra files present locally but not in the ISO listing (excluding build/gen/src).
    skip_dirs = {"build", "src", "TDATA", "UDATA", ".git"}
    extras = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in skip_dirs]
        for fn in filenames:
            full = os.path.join(dirpath, fn)
            rel = os.path.relpath(full, root).replace(os.sep, "/")
            if rel not in iso:
                extras.append(rel)
    print("Extras (not in ISO, excl. build/src/TDATA/UDATA): %d" % len(extras))
    for e in sorted(extras):
        print("  EXTRA  %s" % e)

    return 0 if not missing and not mismatch else 1


if __name__ == "__main__":
    sys.exit(main())
