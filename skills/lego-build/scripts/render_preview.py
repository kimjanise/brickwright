"""Render bundled part geometry through the pinned runtime's depth-buffer renderer."""

from pathlib import Path

import numpy as np
from bricklayer.io import from_ldraw
from brickwright.tools.software_rendering import Mesh, _inset_part, _rasterize
from PIL import Image


def render_preview(
    ldraw: str,
    output: Path,
    *,
    new_from: int = 0,
    camera: tuple[float, float, float] = (-1.0, -0.7, -1.3),
) -> None:
    build = from_ldraw(ldraw)
    if not 0 < build.brick_count <= 2000:
        raise ValueError("Preview supports 1–2,000 pieces.")
    combined = Mesh()
    for index, placement in enumerate(build.flattened_placements):
        body = placement.collision_body
        mesh = body.collider.mesh
        vertices = _inset_part(mesh.vertices)
        world = (vertices @ body.rotation.T + body.translation) * [1, -1, -1]
        faces = world[mesh.faces]
        color = placement.content.color
        rgba = [int(color.rgb[i : i + 2], 16) / 255 for i in (0, 2, 4)] + [
            getattr(color, "alpha", 255) / 255
        ]
        if index < new_from:
            rgba = [0.78, 0.8, 0.81, 1.0]
        combined.part_vertices.append(faces)
        combined.part_colors.append(np.tile(rgba, (len(faces), 1)))
    vertices, colors = combined.combined()
    flat = vertices.reshape(-1, 3)
    low, high = flat.min(axis=0), flat.max(axis=0)
    center = (low + high) / 2
    padding = np.array([center - (high - low) * 0.7, center + (high - low) * 0.7])
    # Invisible degenerate triangles provide framing margin; they never rasterize.
    framed = (
        np.concatenate([vertices, np.repeat(padding[:, None, :], 3, axis=1)]),
        np.concatenate([colors, np.zeros((2, 4))]),
    )
    pixels = _rasterize(framed, camera, (0.0, 1.0, 0.0), 1000)
    foreground = Image.fromarray(pixels)
    background = Image.new("RGBA", foreground.size, "#f5f5f2")
    Image.alpha_composite(background, foreground).convert("RGB").save(output)
