#!/usr/bin/env python3
"""Read and write the ATIS of a Simrad Shipmate RS8300 in its NM93C46 EEPROM.

Requires the Arduino sketch in src/ and pyserial (pip install pyserial).

  python3 atis.py dump                  # back up the EEPROM (dumps/*.bin)
  python3 atis.py show                  # show the stored ATIS
  python3 atis.py set 9211xxxxxx        # write a new ATIS (automatic backup first)
  python3 atis.py restore dumps/x.bin   # write a backup back (only differing words)

Options: --port /dev/ttyACM0
"""
import argparse, datetime, glob, pathlib, re, sys, time

# ATIS layout (64 x 16 bit, word addresses), determined on an RS8300:
#   digits 1-4  -> word 0x2E (BCD)
#   digits 5-8  -> word 0x2F (BCD)
#   digits 9-10 -> word 0x3D, high byte (BCD); the low byte is left unchanged
ADDR_A, ADDR_B, ADDR_C = 0x2E, 0x2F, 0x3D
DUMP_DIR = pathlib.Path(__file__).resolve().parent / "dumps"


class Eeprom:
    def __init__(self, port):
        import serial
        port = port or (sorted(glob.glob("/dev/ttyACM*") + glob.glob("/dev/ttyUSB*")) or [None])[0]
        if not port:
            sys.exit("No Arduino found (use --port)")
        self.ser = serial.Serial(port, 115200, timeout=1)
        time.sleep(2.5)  # wait for the Arduino auto-reset
        self._dump()     # the first access sometimes returns garbage -> discard

    def _dump(self):
        self.ser.reset_input_buffer()
        self.ser.write(b"d\n")
        words, deadline = {}, time.time() + 5
        while len(words) < 64 and time.time() < deadline:
            line = self.ser.readline().decode(errors="replace").strip()
            m = re.match(r"^([0-9A-F]{2}):((?: [0-9A-F]{4}){8})", line)
            if m:
                base = int(m.group(1), 16)
                for i, w in enumerate(m.group(2).split()):
                    words[base + i] = int(w, 16)
        if len(words) != 64:
            sys.exit(f"Incomplete dump ({len(words)}/64 words) - is the sketch flashed?")
        return [words[i] for i in range(64)]

    def read_stable(self, n=3):
        reads = [self._dump() for _ in range(n)]
        if any(r != reads[0] for r in reads):
            sys.exit("Reads differ - check clip, wiring and power. Nothing was changed.")
        if len(set(reads[0])) == 1:
            sys.exit(f"All words = {reads[0][0]:04X} - no contact or chip not powered.")
        return reads[0]

    def write(self, adr, val):
        self.ser.reset_input_buffer()
        self.ser.write(f"w {adr:02X} {val:04X}\n".encode())
        resp = self.ser.readline().decode(errors="replace").strip()
        print(f"  w {adr:02X} {val:04X} -> {resp}")
        if "verify ok" not in resp:
            sys.exit("Write failed - aborted.")


def to_bytes(words):
    return b"".join(w.to_bytes(2, "big") for w in words)


def from_bytes(data):
    if len(data) != 128:
        sys.exit("Backup must be exactly 128 bytes")
    return [int.from_bytes(data[i:i + 2], "big") for i in range(0, 128, 2)]


def show(words):
    for r in range(0, 64, 8):
        print(f"{r:02X}: " + " ".join(f"{w:04X}" for w in words[r:r + 8]))


def atis_of(words):
    return f"{words[ADDR_A]:04X}{words[ADDR_B]:04X}{words[ADDR_C] >> 8:02X}"


def save(words, tag):
    DUMP_DIR.mkdir(exist_ok=True)
    f = DUMP_DIR / f"nm93c46_{datetime.datetime.now():%Y%m%d_%H%M%S}_{tag}.bin"
    f.write_bytes(to_bytes(words))
    return f


def write_diff(ee, current, target):
    changes = [i for i in range(64) if current[i] != target[i]]
    for i in changes:
        ee.write(i, target[i])
    after = ee.read_stable(2)
    if after != target:
        bad = [f"{i:02X}" for i in range(64) if after[i] != target[i]]
        sys.exit(f"Verification failed at {bad}!")
    return changes


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--port")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("dump")
    sub.add_parser("show")
    p = sub.add_parser("set"); p.add_argument("atis")
    p = sub.add_parser("restore"); p.add_argument("file")
    a = ap.parse_args()

    if a.cmd == "set" and not re.fullmatch(r"9\d{9}", a.atis):
        sys.exit("ATIS must have 10 digits and start with 9")
    target_file = None
    if a.cmd == "restore":
        target_file = from_bytes(pathlib.Path(a.file).read_bytes())

    ee = Eeprom(a.port)
    words = ee.read_stable()

    if a.cmd == "dump":
        show(words)
        print(f"\nATIS: {atis_of(words)}\nSaved: {save(words, 'dump')}")
    elif a.cmd == "show":
        print(f"ATIS: {atis_of(words)}")
    elif a.cmd == "set":
        old = atis_of(words)
        print(f"Current ATIS: {old}\nBackup: {save(words, 'before_set_' + old)}")
        target = list(words)
        target[ADDR_A] = int(a.atis[0:4], 16)
        target[ADDR_B] = int(a.atis[4:8], 16)
        target[ADDR_C] = (int(a.atis[8:10], 16) << 8) | (words[ADDR_C] & 0xFF)
        write_diff(ee, words, target)
        print(f"New ATIS: {a.atis} (written and verified)")
    elif a.cmd == "restore":
        print(f"Backup of current state: {save(words, 'before_restore')}")
        n = write_diff(ee, words, target_file)
        print(f"{len(n)} words written back, contents now match {a.file}")


if __name__ == "__main__":
    main()
