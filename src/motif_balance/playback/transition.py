"""Smooth display motion between saved states, without interpolating scientific values."""

import math
from copy import deepcopy
from xml.etree import ElementTree as ET

from motif_balance.errors import ArtifactError

SVG = "http://www.w3.org/2000/svg"
Q = "{" + SVG + "}"
ET.register_namespace("", SVG)


def blend_svgs(before: bytes, after: bytes, fraction: float) -> bytes:
    """Move and crossfade native motif groups; endpoints remain exact saved frames.

    Scores and DNA letters are never numerically interpolated. The recovery plot
    remains at the earlier observation until the next saved state is reached.
    Rotation while changing strands is a display transition, not protein motion.
    """
    if type(fraction) not in (int, float) or not math.isfinite(fraction) or not 0 <= fraction <= 1:
        raise ArtifactError("transition fraction must be finite and between zero and one")
    if fraction == 0:
        return before
    if fraction == 1:
        return after
    old, new = ET.fromstring(before), ET.fromstring(after)
    old_duplex = next(n for n in old.iter() if n.get("data-duplex-layout"))
    new_duplex = next(n for n in new.iter() if n.get("data-duplex-layout"))
    old_groups = {n.get("data-motif-id"): n for n in old_duplex if n.get("data-motif-id")}
    new_groups = {n.get("data-motif-id"): n for n in new_duplex if n.get("data-motif-id")}
    if old_groups.keys() != new_groups.keys():
        raise ArtifactError("transition must retain the same motif models")
    t = fraction * fraction * (3 - 2 * fraction)
    canvas = ET.Element(Q + "g", old_duplex.attrib)
    # Keep the duplex moving continuously when the distribution of strands
    # changes the number of rows allocated above it.
    old_text = next((n for n in old_duplex if n.tag == Q + "text" and n.get("y")), None)
    new_text = next((n for n in new_duplex if n.tag == Q + "text" and n.get("y")), None)
    dy = (
        0.0
        if old_text is None or new_text is None
        else float(new_text.attrib["y"]) - float(old_text.attrib["y"])
    )
    for parent, alpha, shift in ((old_duplex, 1 - t, dy * t), (new_duplex, t, dy * (t - 1))):
        group = ET.SubElement(
            canvas, Q + "g", {"opacity": f"{alpha:.8f}", "transform": f"translate(0 {shift:g})"}
        )
        group.extend(deepcopy(n) for n in parent if not n.get("data-motif-id"))
    for identifier, a in old_groups.items():
        b = new_groups[identifier]
        ar, br = a.find(Q + "rect"), b.find(Q + "rect")
        if ar is None or br is None:
            raise ArtifactError("motif transition requires a native match window")
        ax, ay = float(ar.attrib["x"]) + float(ar.attrib["width"]) / 2, float(ar.attrib["y"]) + 10
        bx, by = float(br.attrib["x"]) + float(br.attrib["width"]) / 2, float(br.attrib["y"]) + 10
        cx, cy = ax + (bx - ax) * t, ay + (by - ay) * t
        angle = 180 if a.get("data-strand") != b.get("data-strand") else 0
        for node, alpha, x, y, rotation in (
            (a, 1 - t, ax, ay, angle * t),
            (b, t, bx, by, angle * (t - 1)),
        ):
            wrapper = ET.SubElement(
                canvas,
                Q + "g",
                {
                    "opacity": f"{alpha:.8f}",
                    "transform": (
                        f"translate({cx:g} {cy:g}) rotate({rotation:g}) translate({-x:g} {-y:g})"
                    ),
                },
            )
            copied = deepcopy(node)
            # Duplicate DOM identifiers would make an editable transition ambiguous.
            for item in copied.iter():
                item.attrib.pop("id", None)
            wrapper.append(copied)
    for parent in old.iter():
        if old_duplex in list(parent):
            index = list(parent).index(old_duplex)
            parent.remove(old_duplex)
            parent.insert(index, canvas)
            break
    old.set("data-visual-transition", "true")
    old.set("data-transition-to-evaluations", new.get("data-evaluations", ""))
    width = float(old.attrib["viewBox"].split()[2])
    label = ET.SubElement(
        old,
        Q + "text",
        {
            "x": f"{width - 20:g}",
            "y": "58",
            "text-anchor": "end",
            "font-family": "Arial,sans-serif",
            "font-size": "16",
            "fill": "#666666",
        },
    )
    label.text = "Transition between recorded states"
    return bytes(ET.tostring(old, encoding="utf-8"))
