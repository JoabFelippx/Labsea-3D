"""Adiciona somente as carcaças com montagem horizontal no teto.

A modelagem é compartilhada com scene_builder.py, em camera_models.py.
Para a reconstrução completa, use scene_builder.py sobre a arquitetura original.
"""
import argparse
import json
from pathlib import Path
import sys

import bpy

sys.path.insert(0, str(Path(__file__).resolve().parent))
from camera_models import create_camera_model
from materials import material
from primitives import collection

ROOT = Path(__file__).resolve().parents[2]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--saida', type=Path, default=ROOT/'saida/labsea_cameras_fisicas.blend')
    argv = sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else []
    args = parser.parse_args(argv)
    if not bpy.data.filepath or Path(bpy.data.filepath).resolve() == args.saida.resolve():
        raise ValueError('Abra a arquitetura existente e escolha uma saída diferente da entrada.')
    data = json.loads((ROOT/'scene_data/objects.json').read_text())
    specs = [s for s in data['objects'] if s['object_type'] == 'camera_model']
    poses = {i: bpy.data.objects[f'Camera_{i}'].matrix_world.copy() for i in range(1,5)}
    for name in ('04_Modelos_Cameras', 'CameraModels'):
        old = bpy.data.collections.get(name)
        if old:
            for obj in list(old.objects):
                # These collections are reserved for the visual camera assemblies.
                if obj.type != 'CAMERA':
                    bpy.data.objects.remove(obj, do_unlink=True)
    coll = collection('CameraModels')
    mats = {
        'white': material('CameraWhite', (.73,.75,.71), .4)[0],
        'edge': material('CameraEdge', (.15,.17,.18), .4)[0],
        'black': material('CameraBlack', (.005,.007,.009), .6)[0],
        'screen': material('CameraLens', (.008,.015,.020), .2)[0],
    }
    for spec in specs:
        create_camera_model(spec, coll, mats, data['ceiling']['height_m'])
    bpy.context.view_layer.update()
    assert all(bpy.data.objects[f'Camera_{i}'].matrix_world == pose for i, pose in poses.items())
    args.saida.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=str(args.saida.resolve()))
    print(f'[OK] Quatro carcaças com base horizontal: {args.saida}')


if __name__ == '__main__':
    main()
