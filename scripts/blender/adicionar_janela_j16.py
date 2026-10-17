"""Adiciona a janela J16 a um modelo que já contém as aberturas J21 e P6.

Cria abertura J16 na parede sul existente, com moldura de aluminio e
3 modulos de vidro (representacao simplificada de janela maxim-ar).

Na aba Scripting do Blender, execute este arquivo e salve manualmente.
Na linha de comando, passe --saida para salvar um novo arquivo .blend.
"""

import argparse
from pathlib import Path
import sys

import bpy

# -------- AJUSTES DA CENA (metros) --------
WALL_NAME = None            # Ex.: "Parede_south"; None = encontrar automaticamente
WALL_Y = -4.335             # Parede south do modelo do LabSEA
WINDOW_WIDTH = 3.00
WINDOW_HEIGHT = 0.40
SILL_HEIGHT = 2.20
WINDOW_CENTER_X = 1.665    # Posição provisória no modelo atual; 31 cm da borda +X.

# A altura total das paredes deve ter sido ajustada separadamente para 3.70 m.
ROOM_HEIGHT = 3.70
COLLECTION_NAME = "J16_Janela_Alta"
CUTTER_NAME = "J16_Cortador_Abertura"
BOOLEAN_NAME = "J16_Vao_Real"


def get_or_create_collection(name):
    coll = bpy.data.collections.get(name)
    if coll is None:
        coll = bpy.data.collections.new(name)
        bpy.context.scene.collection.children.link(coll)
    return coll


def move_to_collection(obj, coll):
    if coll not in obj.users_collection:
        coll.objects.link(obj)
    for old_coll in list(obj.users_collection):
        if old_coll != coll:
            old_coll.objects.unlink(obj)


def find_south_wall():
    if WALL_NAME:
        obj = bpy.data.objects.get(WALL_NAME)
        if obj is None or obj.type != "MESH":
            raise RuntimeError(f"Parede '{WALL_NAME}' não encontrada como malha.")
        return obj

    candidates = [
        obj for obj in bpy.data.objects
        if obj.type == "MESH"
        and abs(obj.matrix_world.translation.y - WALL_Y) < 0.25
        and obj.dimensions.x > 5.0
        and obj.dimensions.y < 0.45
        and obj.dimensions.z > 2.5
    ]
    if not candidates:
        names = [o.name for o in bpy.data.objects if o.type == "MESH"]
        raise RuntimeError(
            "Não encontrei a parede south automaticamente. "
            "Defina WALL_NAME no começo do script. Malhas: " + ", ".join(names)
        )
    return min(candidates, key=lambda obj: abs(obj.location.y - WALL_Y))


def get_material(name, rgba, metallic=0.0, roughness=0.4, transmission=0.0):
    mat = bpy.data.materials.get(name)
    if mat is None:
        mat = bpy.data.materials.new(name)
    mat.diffuse_color = rgba
    mat.use_nodes = True
    principled = mat.node_tree.nodes.get("Principled BSDF")
    if principled:
        principled.inputs["Base Color"].default_value = rgba
        principled.inputs["Metallic"].default_value = metallic
        principled.inputs["Roughness"].default_value = roughness
        if "Transmission Weight" in principled.inputs:
            principled.inputs["Transmission Weight"].default_value = transmission
        elif "Transmission" in principled.inputs:
            principled.inputs["Transmission"].default_value = transmission
    return mat


def make_cube(name, location, dimensions, collection, material=None):
    old = bpy.data.objects.get(name)
    if old is not None:
        bpy.data.objects.remove(old, do_unlink=True)
    bpy.ops.mesh.primitive_cube_add(size=1.0, location=location)
    obj = bpy.context.object
    obj.name = name
    obj.dimensions = dimensions
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    move_to_collection(obj, collection)
    if material is not None:
        obj.data.materials.append(material)
    return obj


def argumentos():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    parser = argparse.ArgumentParser()
    parser.add_argument("--saida", type=Path, help="Arquivo .blend final")
    return parser.parse_args(argv)


def main():
    args = argumentos()
    saida = args.saida.expanduser().resolve() if args.saida else None
    if saida and Path(bpy.data.filepath).resolve() == saida:
        raise ValueError("A saída deve ser diferente do arquivo de entrada.")

    coll = get_or_create_collection(COLLECTION_NAME)
    wall = find_south_wall()
    z_center = SILL_HEIGHT + WINDOW_HEIGHT / 2
    print(f"Parede encontrada: {wall.name}; dimensões: {tuple(wall.dimensions)}")

    if abs(wall.dimensions.z - ROOM_HEIGHT) > 0.02:
        print("AVISO: parede com altura diferente de 3.70 m. "
              "Atualize a altura da sala antes de finalizar o modelo.")

    # Cortador atravessa toda a espessura da parede: abertura verdadeira.
    old_cutter = bpy.data.objects.get(CUTTER_NAME)
    if old_cutter is not None:
        old_cutter.hide_set(False)
        bpy.data.objects.remove(old_cutter, do_unlink=True)

    cut_depth = max(float(wall.dimensions.y) + 0.40, 0.55)
    cutter = make_cube(
        CUTTER_NAME,
        (WINDOW_CENTER_X, WALL_Y, z_center),
        (WINDOW_WIDTH, cut_depth, WINDOW_HEIGHT),
        coll,
    )

    mod = wall.modifiers.get(BOOLEAN_NAME)
    if mod is None:
        mod = wall.modifiers.new(name=BOOLEAN_NAME, type="BOOLEAN")
    mod.operation = "DIFFERENCE"
    mod.solver = "EXACT"
    mod.object = cutter
    cutter.display_type = "WIRE"
    cutter.hide_render = True
    cutter.hide_set(True)

    aluminum = get_material("J16_Aluminio", (0.42, 0.46, 0.49, 1), metallic=0.8)
    glass = get_material("J16_Vidro", (0.55, 0.78, 0.85, 1), roughness=0.1, transmission=0.75)

    x_left = WINDOW_CENTER_X - WINDOW_WIDTH / 2
    x_right = WINDOW_CENTER_X + WINDOW_WIDTH / 2
    z_bottom = SILL_HEIGHT
    z_top = SILL_HEIGHT + WINDOW_HEIGHT
    bar = 0.035
    depth = 0.085

    for name, z in (("Base", z_bottom + bar / 2), ("Topo", z_top - bar / 2)):
        make_cube(f"J16_Moldura_{name}", (WINDOW_CENTER_X, WALL_Y, z),
                  (WINDOW_WIDTH, depth, bar), coll, aluminum)

    for name, x in (("Esquerda", x_left + bar / 2), ("Direita", x_right - bar / 2),
                    ("Divisao_1", x_left + 1.0), ("Divisao_2", x_left + 2.0)):
        make_cube(f"J16_Moldura_{name}", (x, WALL_Y, z_center),
                  (bar, depth, WINDOW_HEIGHT), coll, aluminum)

    # Três módulos de vidro. A articulação maxim-ar não é animada.
    for i in range(3):
        module_center_x = x_left + (i + 0.5) * (WINDOW_WIDTH / 3)
        make_cube(
            f"J16_Vidro_Modulo_{i + 1}",
            (module_center_x, WALL_Y, z_center),
            (WINDOW_WIDTH / 3 - bar, 0.008, WINDOW_HEIGHT - 2 * bar),
            coll, glass,
        )

    print(f"J16 criada: centro=({WINDOW_CENTER_X:.3f}, {WALL_Y:.3f}, {z_center:.3f}) m")
    print(f"Vão: {WINDOW_WIDTH:.2f} x {WINDOW_HEIGHT:.2f} m; base Z={SILL_HEIGHT:.2f} m")
    if saida:
        saida.parent.mkdir(parents=True, exist_ok=True)
        bpy.ops.wm.save_as_mainfile(filepath=str(saida))
        print(f"[OK] Salvo em: {saida}")
    else:
        print("Salve o .blend com Ctrl+S para manter as alterações.")


if __name__ == "__main__":
    main()
