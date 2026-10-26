"""Create browser geometry from bundled parts; no external LDraw library needed."""

from typing import Any

from bricklayer.io import from_ldraw

from brickwright.pricing import bom_from_ldraw


def preview_ldraw(source: str) -> dict[str, Any]:
    parts = bom_from_ldraw(source)
    build = from_ldraw(source)
    if build.brick_count > 5000:
        raise ValueError("Preview is limited to 5,000 bricks.")
    meshes: dict[str, Any] = {}
    instances = []
    for placement in build.flattened_placements:
        element = placement.content
        body = placement.collision_body
        part = element.ldraw_id
        if part not in meshes:
            mesh = body.collider.mesh
            meshes[part] = {
                "vertices": mesh.vertices.round(4).tolist(),
                "faces": mesh.faces.tolist(),
            }
        instances.append(
            {
                "part": part,
                "color": [int(element.color.rgb[i : i + 2], 16) for i in (0, 2, 4)],
                "rotation": body.rotation.tolist(),
                "translation": body.translation.tolist(),
            }
        )
    return {
        "brick_count": build.brick_count,
        "parts": [part.model_dump() for part in parts],
        "meshes": meshes,
        "instances": instances,
    }
