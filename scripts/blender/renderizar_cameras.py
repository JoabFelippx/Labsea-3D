"""Renderiza imagens sintéticas das câmeras do LabSEA.

Execução, na pasta do projeto:
    blender -b modelos/labsea.blend --python scripts/blender/renderizar_cameras.py
    blender -b modelos/labsea.blend --python scripts/blender/renderizar_cameras.py -- --cam 1 --objeto-teste
    blender -b modelos/labsea.blend --python scripts/blender/renderizar_cameras.py -- --cam 1 --luz 80 --exposicao -1.5

Usa a pose das câmeras Camera_1 ... Camera_4 já presentes no .blend.
Usa nK e width/height de calib_rt{i}.npz para configurar cada câmera.
A câmera de perspectiva do Blender não reproduz a distorção dist do OpenCV.
"""

from pathlib import Path
import argparse
import json
import sys

import bpy
import numpy as np


def parse_args():
    args = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    raiz = Path(__file__).resolve().parents[2]
    parser = argparse.ArgumentParser()
    parser.add_argument("--calib-dir", type=Path, default=raiz / "dados" / "calibracao")
    parser.add_argument("--saida", type=Path, default=raiz / "saida" / "imagens_sinteticas")
    parser.add_argument("--cam", type=int, choices=(1, 2, 3, 4), help="Renderizar apenas esta câmera")
    parser.add_argument("--objeto-teste", action="store_true", help="Criar uma caixa colorida temporária")
    parser.add_argument("--preview", type=int, default=100, choices=range(10,101),
                        metavar="10..100", help="Percentual da resolução para diagnóstico, sem mudar K")
    parser.add_argument("--samples", type=int, help="Amostras Cycles; mantém iluminação da reconstrução")
    parser.add_argument("--width", type=int, help="Largura, caso não exista no arquivo NPZ")
    parser.add_argument("--height", type=int, help="Altura, caso não exista no arquivo NPZ")
    parser.add_argument("--luz", type=float, default=120.0,
                        help="Potência de cada luz AREA em W (padrão: 120)")
    parser.add_argument("--ambiente", type=float, default=0.2,
                        help="Intensidade do mundo (padrão: 0.2)")
    parser.add_argument("--exposicao", type=float, default=-1.0,
                        help="Exposição em stops (padrão: -1.0)")
    return parser.parse_args(args)


def ler_calibracao(path, width_override=None, height_override=None):
    if not path.is_file():
        raise FileNotFoundError(f"Arquivo de calibração não encontrado: {path}")

    with np.load(path, allow_pickle=False) as npz:
        if "nK" not in npz:
            raise KeyError(f"{path}: a chave 'nK' não existe")
        K = np.asarray(npz["nK"], dtype=float)

        def dimensao(override, nomes):
            if override is not None:
                return override
            for nome in nomes:
                if nome in npz:
                    return int(np.asarray(npz[nome]).item())
            raise KeyError(
                f"{path}: não encontrei {nomes}. "
                "Informe --width e --height no comando."
            )

        width = dimensao(width_override, ("width", "w"))
        height = dimensao(height_override, ("height", "h"))

    if K.shape != (3, 3):
        raise ValueError(f"{path}: 'nK' deve ter dimensão 3x3")
    if not np.isfinite(K).all() or width <= 0 or height <= 0:
        raise ValueError(f"{path}: parâmetros inválidos")
    if abs(K[0, 1]) > 1e-5 or abs(K[1, 0]) > 1e-5:
        raise ValueError(f"{path}: matriz com skew; a câmera padrão do Blender não o representa")
    if K[0, 0] <= 0 or K[1, 1] <= 0:
        raise ValueError(f"{path}: distâncias focais devem ser positivas")
    return K, width, height


def configurar_intrinsecos(camera, K, width, height):
    """Adaptação de K OpenCV para câmera de perspectiva Blender, sem distorção."""
    fx, fy = float(K[0, 0]), float(K[1, 1])
    cx, cy = float(K[0, 2]), float(K[1, 2])
    ratio = fx / fy

    dados = camera.data
    dados.type = "PERSP"
    dados.sensor_fit = "HORIZONTAL"
    dados.sensor_width = 36.0  # mm; valor arbitrário, compensado em lens
    dados.lens = fx * dados.sensor_width / width
    dados.shift_x = ((width - 1) / 2.0 - cx) / width
    dados.shift_y = (cy - (height - 1) / 2.0) * ratio / width
    dados.clip_start = 0.01
    dados.clip_end = 100.0

    scene = bpy.context.scene
    scene.render.resolution_x = width
    scene.render.resolution_y = height
    scene.render.resolution_percentage = 100
    scene.render.pixel_aspect_x = 1.0
    scene.render.pixel_aspect_y = ratio


def material_opaco(nome):
    mat = bpy.data.materials.get(nome)
    if mat is None:
        return
    rgba = tuple(mat.diffuse_color)
    mat.diffuse_color = (rgba[0], rgba[1], rgba[2], 1.0)
    if mat.use_nodes and mat.node_tree:
        bsdf = mat.node_tree.nodes.get("Principled BSDF")
        if bsdf and "Alpha" in bsdf.inputs:
            bsdf.inputs["Alpha"].default_value = 1.0


def preparar_cena(args):
    scene = bpy.context.scene
    # Essas malhas são apenas marcadores de visualização do mapa 3D.
    for obj in bpy.data.objects:
        if obj.type == "MESH" and obj.name.startswith("Camera_"):
            obj.hide_render = True

    if scene.get('labsea_reconstructed'):
        # A iluminação, exposição e materiais foram definidos e salvos pelo builder.
        if args.samples is not None:
            scene.cycles.samples = args.samples
        return

    material_opaco("Paredes")
    material_opaco("Piso")

    if scene.world is None:
        scene.world = bpy.data.worlds.new("Mundo_LabSEA")
    scene.world.use_nodes = True
    fundo = scene.world.node_tree.nodes.get("Background")
    if fundo:
        fundo.inputs["Color"].default_value = (0.75, 0.8, 0.9, 1.0)
        fundo.inputs["Strength"].default_value = args.ambiente

    # Luzes artificiais, sem salvar alterações no arquivo .blend.
    for i, (x, y) in enumerate([(0, -2.0), (0, 2.0)], start=1):
        nome = f"LuzRender_{i}"
        if bpy.data.objects.get(nome) is not None:
            continue
        luz = bpy.data.lights.new(nome, "AREA")
        luz.energy = args.luz
        luz.shape = "DISK"
        luz.size = 3.0
        obj = bpy.data.objects.new(nome, luz)
        scene.collection.objects.link(obj)
        obj.location = (x, y, 3.05)
        # Na rotação padrão, luz AREA aponta para -Z (em direção ao chão).

    # Render rápido em Eevee quando disponível, senão Cycles.
    for engine in ("BLENDER_EEVEE_NEXT", "BLENDER_EEVEE", "CYCLES"):
        try:
            scene.render.engine = engine
            break
        except TypeError:
            continue
    if scene.render.engine == "CYCLES":
        scene.cycles.samples = 24

    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGB"
    scene.render.image_settings.color_depth = "8"
    scene.render.film_transparent = False
    # AgX preserva melhor detalhes nas áreas claras do que Standard.
    try:
        scene.view_settings.view_transform = "AgX"
    except (TypeError, ValueError):
        # Blender antigo: mantém o transform disponível.
        pass
    scene.view_settings.exposure = args.exposicao
    scene.view_settings.gamma = 1.0
    print(f"[LUZ] cada AREA={args.luz} W | mundo={args.ambiente} | exposição={args.exposicao} EV | view={scene.view_settings.view_transform}")


def colocar_objeto_teste():
    bpy.ops.mesh.primitive_cube_add(size=1, location=(0.0, 0.0, 0.45))
    obj = bpy.context.object
    obj.name = "Caixa_teste"
    obj.dimensions = (0.7, 0.7, 0.9)
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    mat = bpy.data.materials.new("Material_Caixa_teste")
    mat.diffuse_color = (0.8, 0.16, 0.07, 1)
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    if bsdf:
        bsdf.inputs["Base Color"].default_value = (0.8, 0.16, 0.07, 1)
    obj.data.materials.append(mat)


def main():
    args = parse_args()
    if not bpy.data.filepath:
        raise RuntimeError("Abra o arquivo .blend final ao executar: blender -b modelos/labsea.blend --python scripts/blender/renderizar_cameras.py")

    pasta_calib = args.calib_dir.expanduser().resolve()
    pasta_saida = args.saida.expanduser().resolve()
    pasta_saida.mkdir(parents=True, exist_ok=True)

    preparar_cena(args)
    if args.objeto_teste:
        colocar_objeto_teste()

    ids = (args.cam,) if args.cam else (1, 2, 3, 4)
    scene = bpy.context.scene
    modelos_fisicos = bpy.data.collections.get("CameraModels") or bpy.data.collections.get("04_Modelos_Cameras")
    for cam_id in ids:
        nome = f"Camera_{cam_id}"
        camera = bpy.data.objects.get(nome)
        if camera is None or camera.type != "CAMERA":
            raise ValueError(f"A câmera '{nome}' não foi encontrada em {bpy.data.filepath}")

        K, width, height = ler_calibracao(
            pasta_calib / f"calib_rt{cam_id}.npz", args.width, args.height
        )
        configurar_intrinsecos(camera, K, width, height)
        scene.render.resolution_percentage = args.preview
        if scene.get('camera_exposure_offsets_ev'):
            offsets=json.loads(scene['camera_exposure_offsets_ev'])
            scene.view_settings.exposure=float(scene['exposure_base_ev'])+float(offsets.get(str(cam_id),0))
        if modelos_fisicos is not None:
            # A carcaça da própria câmera não deve entrar no seu render.
            # As outras carcaças continuam visíveis na cena.
            for obj in modelos_fisicos.objects:
                if obj.type == "MESH":
                    obj.hide_render = obj.get("camera_id_visual") == cam_id
        scene.camera = camera
        scene.render.filepath = str(pasta_saida / f"camera_{cam_id}.png")
        print(f"[RENDER] Câmera {cam_id} | {width}x{height} | {scene.render.filepath}")
        bpy.ops.render.render(write_still=True)

    print(f"[OK] Imagens salvas em {pasta_saida}")


if __name__ == "__main__":
    main()
