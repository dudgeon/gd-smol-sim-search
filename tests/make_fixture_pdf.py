"""Regenerate papers/volcanoes.pdf (a 2-page text PDF) without any dependencies.

    python tests/make_fixture_pdf.py
"""

from pathlib import Path

PAGES = [
    ["Volcanic eruptions",
     "",
     "A volcano erupts when molten rock called magma rises through the crust",
     "and escapes as lava, ash and volcanic gas. Explosive eruptions happen",
     "when gas-rich magma fragments violently, throwing ash high into the sky."],
    ["Earthquakes and fault lines",
     "",
     "Earthquakes release stress stored along faults where tectonic plates",
     "grind past each other. Seismometers record the shaking, and the",
     "magnitude scale measures the energy released by the rupture."],
]


def _esc(s: str) -> str:
    return s.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def build() -> bytes:
    objs: list[bytes] = []
    n_pages = len(PAGES)
    # 1 catalog, 2 pages, 3 font, then (page, content) pairs
    kids = " ".join(f"{4 + 2 * i} 0 R" for i in range(n_pages))
    objs.append(b"<< /Type /Catalog /Pages 2 0 R >>")
    objs.append(f"<< /Type /Pages /Kids [{kids}] /Count {n_pages} >>".encode())
    objs.append(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")
    for i, lines in enumerate(PAGES):
        content = "BT /F1 12 Tf 72 720 Td 16 TL\n" + "".join(f"({_esc(l)}) Tj T*\n" for l in lines) + "ET"
        cb = content.encode("latin-1")
        objs.append(f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
                    f"/Resources << /Font << /F1 3 0 R >> >> /Contents {5 + 2 * i} 0 R >>".encode())
        objs.append(b"<< /Length %d >>\nstream\n" % len(cb) + cb + b"\nendstream")
    out = bytearray(b"%PDF-1.4\n")
    offsets = []
    for n, body in enumerate(objs, 1):
        offsets.append(len(out))
        out += b"%d 0 obj\n" % n + body + b"\nendobj\n"
    xref = len(out)
    out += b"xref\n0 %d\n0000000000 65535 f \n" % (len(objs) + 1)
    for off in offsets:
        out += b"%010d 00000 n \n" % off
    out += b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n" % (len(objs) + 1, xref)
    return bytes(out)


if __name__ == "__main__":
    dest = Path(__file__).parent / "fixtures" / "papers" / "volcanoes.pdf"
    dest.write_bytes(build())
    print(f"wrote {dest}")
