"""Exporta a geometria visível do modelo para GLB.

Exemplo:
    blender -b modelos/labsea.blend --python scripts/blender/exportar_glb.py

O GLB segue o padrão glTF (Y para cima). As poses calibradas originais em
coordenadas mundo Z para cima permanecem nos arquivos .npz e no .blend.
"""

import argparse
from pathlib import Path
import sys

import bpy


def argumentos():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    raiz = Path(__file__).resolve().parents[2]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--saida", type=Path, default=raiz / "saida" / "labsea.glb")
    return parser.parse_args(argv)


def exportavel(obj):
    if obj.type == "EMPTY":
        return obj.name.startswith("CameraModel_") or obj.get('generated_by') == 'labsea_reconstruction_v1'
    if obj.type not in ("MESH", "CURVE"):
        return False
    if obj.name == "J16_Cortador_Abertura":
        return False
    if obj.name.startswith("Camera_"):
        return False  # Marcadores antigos de posição/direção, não carcaças.
    return True


def main():
    args = argumentos()
    if not bpy.data.filepath:
        raise RuntimeError("Abra um arquivo .blend existente antes de exportar.")
    saida = args.saida.expanduser().resolve()
    saida.parent.mkdir(parents=True, exist_ok=True)

    bpy.ops.object.select_all(action="DESELECT")
    selecionados = [obj for obj in bpy.data.objects if exportavel(obj)]
    for obj in selecionados:
        obj.select_set(True)
    if not selecionados:
        raise RuntimeError("Nenhuma malha exportável encontrada.")

    bpy.ops.export_scene.gltf(
        filepath=str(saida),
        export_format="GLB",
        use_selection=True,
        export_apply=True,
        export_cameras=False,
        export_yup=True,
        export_extras=True,
    )
    print(f"[OK] {len(selecionados)} objetos exportados para {saida}")


if __name__ == "__main__":
    main()
