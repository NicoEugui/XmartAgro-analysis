"""The table of CONEAT groups (code, productivity index, dominant soil orders) and how it is read from the MGAP description of the groups.

The description is prose, one block per group headed by its code. Only two things are taken from each block, because they are the ones that
are written the same way everywhere: the productivity index ("Indice de Productividad NN", one value or one per region; the mean is kept)
and the soil orders named in the dominant soils, before the first mention of associated soils.
"""

import csv
import re

ORDERS = ("Vertisol", "Brunosol", "Litosol", "Argisol", "Luvisol", "Acrisol", "Planosol", "Gleysol", "Solonetz", "Inceptisol", "Fluvisol",
          "Histosol", "Arenosol", "Regosol")
COLUMNS = ("code", "productivity_index", "index_values", "dominant_orders")
HEADING = re.compile(r"(?m)^(\d{1,2}\.\d{1,2}[a-z]?)\s*$")
INDEX = re.compile(r"[Ii]ndice de [Pp]roductividad\s*(\d+)")


START = re.compile(r"dominante|predominante|suelos corresponden|suelos son|suelos de este grupo", re.I)


def dominant_orders(block):
    """Soil orders named between the first mention of the dominant soils and the first 'asociad' of a group's block, in order of appearance."""
    start = START.search(block)
    if not start:
        return ()
    text = block[start.start():]
    end = re.search(r"asociad", text, re.I)
    text = text[:end.start()] if end else text
    found = sorted((m.start(), name) for name in ORDERS for m in [re.search(name, text)] if m)
    return tuple(name for _, name in found)


def parse(text):
    """[{code, productivity_index, index_values, dominant_orders}] for every group in the text of the description (`pdftotext` output)."""
    marks = [(m.group(1), m.start()) for m in HEADING.finditer(text)]
    rows, seen = [], set()
    for i, (code, start) in enumerate(marks):
        block = re.sub(r"\s+", " ", text[start:marks[i + 1][1] if i + 1 < len(marks) else len(text)])
        values = [int(v) for v in INDEX.findall(block)]
        code = normalize(code)
        if code in seen:  # the description heads some groups twice ('07.1' and '7.1'): the first block wins
            continue
        seen.add(code)
        rows.append({"code": code, "productivity_index": round(sum(values) / len(values), 1) if values else "",
                     "index_values": ";".join(map(str, values)), "dominant_orders": ";".join(dominant_orders(block))})
    return rows


def write(rows, path):
    with open(path, "w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=COLUMNS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def normalize(code):
    """The group code as the description writes it: the map writes '07.1' and '8.02a' where the description has '7.1' and '8.02a'."""
    head, _, tail = code.partition(".")
    return f"{int(head)}.{tail}" if head.isdigit() else code
