"""Gera o mapa 3D do LabSEA no Blender usando 4 arquivos de calibração.

Exemplo, a partir da pasta do projeto:
    blender --background --python scripts/blender/criar_labsea.py -- \
        --calib-dir ./dados/calibracao --output ./modelos/labsea.blend

IMPORTANTE: as coordenadas das paredes e as poses das câmeras precisam usar
exatamente o mesmo referencial do mundo (X, Y, Z em metros, Z para cima).
"""

import argparse
from pathlib import Path
import sys

import bpy
import numpy as np
from mathutils import Matrix, Vector


PAREDES = {
    "north": {"center": (0.0, 4.335), "len": 6.95},
    "south": {"center": (0.0, -4.335), "len": 6.95},
    "east": {"center": (3.475, 0.0), "len": 8.67},
    "west": {"center": (-3.475, 0.0), "len": 8.67},
}
ALTURA_PAREDE = 3.7
ESPESSURA_PAREDE = 0.10
LARGURA_SALA = 6.95
COMPRIMENTO_SALA = 8.67
CORES_CAMERAS = (
    (0.92, 0.10, 0.10, 1.0),
    (0.08, 0.32, 0.93, 1.0),
    (0.06, 0.68, 0.28, 1.0),
    (1.00, 0.48, 0.04, 1.0),
)


def argumentos():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    raiz = Path(__file__).resolve().parents[2]
    parser = argparse.ArgumentParser(description="Criar modelo 3D do LabSEA no Blender")
    parser.add_argument("--calib-dir", type=Path, default=raiz / "dados" / "calibracao")
    parser.add_argument("--output", type=Path, default=raiz / "modelos" / "labsea.blend")
    return parser.parse_args(argv)


def colecao(nome):
    col = bpy.data.collections.new(nome)
    bpy.context.scene.collection.children.link(col)
    return col


def mover(obj, col):
    for col_antiga in list(obj.users_collection):
        col_antiga.objects.unlink(obj)
    col.objects.link(obj)


def material(nome, rgba):
    mat = bpy.data.materials.new(nome)
    mat.diffuse_color = rgba
    mat.use_nodes = True
    principled = mat.node_tree.nodes.get("Principled BSDF")
    if principled:
        principled.inputs["Base Color"].default_value = rgba
        principled.inputs["Alpha"].default_value = rgba[3]
    if rgba[3] < 1.0 and hasattr(mat, "surface_render_method"):
        mat.surface_render_method = "DITHERED"
    return mat


def bloco(nome, centro, dimensoes, mat, col):
    bpy.ops.mesh.primitive_cube_add(size=1, location=centro)
    obj = bpy.context.object
    obj.name = nome
    obj.dimensions = dimensoes
    obj.data.materials.append(mat)
    mover(obj, col)
    return obj


def fazer_paredes(col, mat_parede, mat_piso):
    bloco(
        "Piso",
        (0, 0, -0.05),
        (LARGURA_SALA, COMPRIMENTO_SALA, 0.10),
        mat_piso, col,
    )
    for nome, parede in PAREDES.items():
        x, y = parede["center"]
        comprimento = parede["len"]
        if nome in ("east", "west"):
            dimensoes = (ESPESSURA_PAREDE, comprimento, ALTURA_PAREDE)
        else:
            dimensoes = (comprimento, ESPESSURA_PAREDE, ALTURA_PAREDE)
        bloco(
            f"Parede_{nome}",
            (x, y, ALTURA_PAREDE / 2),
            dimensoes, mat_parede, col,
        )


def pose_camera(caminho):
    with np.load(caminho, allow_pickle=False) as dados:
        if "rt_inv" in dados:
            T_wc = np.asarray(dados["rt_inv"], dtype=float)
        elif "T_world_camera" in dados:
            T_wc = np.asarray(dados["T_world_camera"], dtype=float)
        else:
            raise KeyError(
                f"{caminho}: não encontrei 'rt_inv' nem 'T_world_camera'."
            )

    if T_wc.shape != (4, 4):
        raise ValueError(f"{caminho}: esperada matriz 4x4, recebida {T_wc.shape}")
    if not np.isfinite(T_wc).all():
        raise ValueError(f"{caminho}: matriz contém NaN ou infinito")
    if not np.allclose(T_wc[3], [0, 0, 0, 1], atol=1e-6):
        raise ValueError(f"{caminho}: última linha não é [0, 0, 0, 1]")

    R_wc = T_wc[:3, :3]
    if not np.allclose(R_wc.T @ R_wc, np.eye(3), atol=1e-2) or not np.isclose(
        np.linalg.det(R_wc), 1.0, atol=1e-2
    ):
        raise ValueError(f"{caminho}: rotação inválida ou não ortonormal")
    return Vector(T_wc[:3, 3].tolist()), Matrix(R_wc.tolist())


def desenhar_camera(col, id_camera, caminho, mat):
    pos, R_wc = pose_camera(caminho)

    # OpenCV: X direita, Y baixo, Z para a frente.
    # Blender: X direita, Y cima, câmera olha no -Z local.
    # Essa conversão NÃO muda as coordenadas do mundo.
    cv_para_blender = Matrix(((1, 0, 0), (0, -1, 0), (0, 0, -1)))
    R_blender = R_wc @ cv_para_blender

    camera_data = bpy.data.cameras.new(f"Camera_{id_camera}_dados")
    camera_data.display_size = 0.35
    camera = bpy.data.objects.new(f"Camera_{id_camera}", camera_data)
    col.objects.link(camera)
    camera.matrix_world = Matrix.Translation(pos) @ R_blender.to_4x4()
    camera.show_name = True

    # Marcador visível, colocado no centro óptico da câmera.
    bpy.ops.mesh.primitive_uv_sphere_add(segments=16, ring_count=8, radius=0.09, location=pos)
    marcador = bpy.context.object
    marcador.name = f"Camera_{id_camera}_posicao"
    marcador.data.materials.append(mat)
    mover(marcador, col)

    # Seta na direção real de observação (+Z no referencial OpenCV).
    direcao = (R_wc @ Vector((0, 0, 1))).normalized()
    orientacao_seta = direcao.to_track_quat("Z", "Y").to_euler()

    bpy.ops.mesh.primitive_cylinder_add(
        vertices=12, radius=0.022, depth=0.55,
        location=pos + direcao * 0.275,
    )
    haste = bpy.context.object
    haste.name = f"Camera_{id_camera}_direcao"
    haste.rotation_euler = orientacao_seta
    haste.data.materials.append(mat)
    mover(haste, col)

    bpy.ops.mesh.primitive_cone_add(
        vertices=16, radius1=0.075, radius2=0, depth=0.20,
        location=pos + direcao * 0.65,
    )
    ponta = bpy.context.object
    ponta.name = f"Camera_{id_camera}_seta"
    ponta.rotation_euler = orientacao_seta
    ponta.data.materials.append(mat)
    mover(ponta, col)

    print(f"[Camera {id_camera}] posição = {tuple(round(v, 4) for v in pos)}")
    print(f"[Camera {id_camera}] direção = {tuple(round(v, 4) for v in direcao)}")
    return camera


def configurar_viewport():
    # Melhora a visualização ao abrir o .blend na interface gráfica.
    for tela in bpy.data.screens:
        for area in tela.areas:
            if area.type == "VIEW_3D":
                espaco = area.spaces.active
                espaco.region_3d.view_location = (0.0, 0.0, 1.5)
                espaco.region_3d.view_distance = 15.0
                espaco.overlay.show_floor = True
                espaco.shading.type = "SOLID"
                espaco.shading.color_type = "MATERIAL"
                espaco.shading.show_xray = True
                espaco.shading.xray_alpha = 0.45


def main():
    args = argumentos()
    pasta_calibracao = args.calib_dir.expanduser().resolve()
    saida = args.output.expanduser().resolve()

    arquivos = [pasta_calibracao / f"calib_rt{i}.npz" for i in range(1, 5)]
    faltantes = [str(p) for p in arquivos if not p.is_file()]
    if faltantes:
        raise FileNotFoundError("Calibrações não encontradas:\n" + "\n".join(faltantes))

    # ATENÇÃO: apaga os objetos da cena atual (não outros arquivos no disco).
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)

    cena = bpy.context.scene
    cena.unit_settings.system = "METRIC"
    cena.unit_settings.scale_length = 1.0

    ambiente = colecao("01_Ambiente")
    cameras = colecao("02_Cameras")
    mat_paredes = material("Paredes", (0.48, 0.73, 0.85, 0.55))
    mat_piso = material("Piso", (0.65, 0.67, 0.70, 1.0))
    fazer_paredes(ambiente, mat_paredes, mat_piso)

    for id_camera, caminho in enumerate(arquivos, start=1):
        mat_camera = material(f"Camera_{id_camera}_cor", CORES_CAMERAS[id_camera - 1])
        cam = desenhar_camera(cameras, id_camera, caminho, mat_camera)
        if id_camera == 1:
            cena.camera = cam

    configurar_viewport()
    saida.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=str(saida))
    print(f"[OK] Mapa 3D salvo em: {saida}")


if __name__ == "__main__":
    main()
