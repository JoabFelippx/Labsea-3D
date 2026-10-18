"""Evolui a arquitetura existente usando scene_data/objects.json.

 blender -b modelos/labsea.blend --python scripts/blender/scene_builder.py -- --saida saida/labsea_atualizado.blend
Somente objetos marcados generated_by são substituídos nas reexecuções.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path
import sys

import bpy
import numpy as np

sys.path.insert(0,str(Path(__file__).resolve().parent))
from primitives import OWNER, collection, root, box, rod, attach
from materials import make_materials, assign_material, floor_texture, material
from furniture import create_desk, create_round_table, create_office_chair, create_cabinet
from electronics import create_monitor, create_computer, create_keyboard, create_board, create_accessory, create_printer
from camera_models import create_camera_model
from lighting import configure_lighting
from renderizar_cameras import ler_calibracao, configurar_intrinsecos

ROOT=Path(__file__).resolve().parents[2]


def snapshot():
    """Compare original mesh coordinates, transforms, modifiers and cameras."""
    result={}
    for obj in bpy.data.objects:
        if obj.get('generated_by') == OWNER:
            continue
        row={'matrix':[list(r) for r in obj.matrix_world]}
        if obj.type=='MESH':
            payload=[list(v.co) for v in obj.data.vertices]
            row['mesh_sha256']=hashlib.sha256(json.dumps(payload).encode()).hexdigest()
            row['faces_sha256']=hashlib.sha256(json.dumps([list(p.vertices) for p in obj.data.polygons]).encode()).hexdigest()
            row['modifiers']=[(m.name,m.type,getattr(m,'operation',None),getattr(getattr(m,'object',None),'name',None)) for m in obj.modifiers]
        if obj.type=='CAMERA':
            row['camera']={key:getattr(obj.data,key) for key in
                ('lens','sensor_width','sensor_height','shift_x','shift_y','sensor_fit','type','clip_start','clip_end')}
        result[obj.name]=row
    return result


def relink(obj, coll):
    for old in list(obj.users_collection):
        old.objects.unlink(obj)
    coll.objects.link(obj)


def organise():
    lab=collection('LabSEA')
    result={}
    hierarchy={'Architecture':['Walls','Floor','Ceiling','Doors','Windows','Pillars'],
               'Furniture':['Desks','Tables','Cabinets','Shelves'],
               'DynamicObjects':['Chairs'],
               'Electronics':['Monitors','Computers','Keyboards','Accessories','Printers'],
               'WallObjects':['Whiteboards','Noticeboards'],
               'Cameras':['RenderCameras','CameraModels','CalibrationMarkers'],
               'Lighting':[]}
    for parent,children in hierarchy.items():
        result[parent]=collection(parent,lab)
        for child in children:
            result[child]=collection(child,result[parent])
    for obj in list(bpy.data.objects):
        if obj.get('generated_by')==OWNER:
            continue
        name=obj.name
        target=None
        if obj.type=='CAMERA': target='RenderCameras'
        elif name.startswith('Camera_'):
            target='CalibrationMarkers'; obj.hide_render=True
        elif name.startswith('Parede_'): target='Walls'
        elif name=='Piso': target='Floor'
        elif name.startswith('Pilar_'): target='Pillars'
        elif name.startswith(('J16_','J21_')): target='Windows'
        elif name.startswith('P6_'): target='Doors'
        if target: relink(obj,result[target])
    # Empty historical collections can be removed; their objects were relinked.
    for name in ('01_Ambiente','02_Cameras','03_Portas_Janelas','J16_Janela_Alta','Collection'):
        old=bpy.data.collections.get(name)
        if old and not old.objects and not old.children:
            bpy.data.collections.remove(old)
    return result


def architecture_materials(mats):
    for obj in bpy.data.objects:
        if obj.type!='MESH' or obj.get('generated_by')==OWNER: continue
        name=obj.name
        if name=='Piso': mat='floor'
        elif name.startswith(('Parede_','Pilar_')): mat='paint'
        elif 'vidro' in name.lower(): mat='glass'
        elif name.startswith(('J16_','J21_')): mat='steel'
        elif name.startswith('P6_'): mat='wood' if 'folha' in name else 'green_tile'
        else: continue
        assign_material(obj,mats[mat])


def architectural_details(data,colls,m):
    ceiling_z=data['ceiling']['height_m']
    box('Ceiling_PVC',(6.85,8.57,.04),(0,0,ceiling_z+.02),None,colls['Ceiling'],m['white'],0)
    for j in range(35):
        x=-3.4+j*.2
        box(f'Ceiling_Joint_{j}',(.0015,8.55,.001),(x,0,ceiling_z-.001),None,colls['Ceiling'],m['edge'],0)
    # 5 cm pastilhas at 0.84–1.04 m, visible on the walls in all four views.
    # Leave door opening untouched. Individual tiles retain appearance in GLB.
    tile=.05
    for side in ('east','west','north','south'):
        length=8.55 if side in ('east','west') else 6.85
        for j in range(int(length/tile)):
            along=-length/2+(j+.5)*tile
            if side=='south' and -3.025<along<-1.425: continue
            for k in range(4):
                z=.85+(k+.5)*tile
                if side in ('east','west'):
                    loc=(3.421 if side=='east' else -3.421,along,z);dims=(.006,.047,.047)
                else:
                    loc=(along,4.281 if side=='north' else -4.281,z);dims=(.047,.006,.047)
                box(f'Tile_{side}_{j}_{k}',dims,loc,None,colls['Walls'],m['green_tile'],0)
    # Recess lines between slabs, fitted approximately to floor observations.
    for axis in (0,1):
        limit=3.4 if axis==0 else 4.28
        for j in range(-4,5):
            v=j*1.18+.02
            if abs(v)>limit: continue
            dims=(.006,8.55,.001) if axis==0 else (6.85,.006,.001)
            loc=(v,0,.001) if axis==0 else (0,v,.001)
            box(f'Floor_Joint_{axis}_{j}',dims,loc,None,colls['Floor'],m['seam'],0)
    # Old bench footprints are surface marks only: no obsolete central furniture.
    for j,x in enumerate((-.03,.018)):
        box(f'Floor_Wear_Long_{j}',(.023,5.2,.001),(x,-.40,.0018),None,colls['Floor'],m['wear'],0)
    for j,y in enumerate((-2.98,.53,2.08)):
        box(f'Floor_Wear_End_{j}',(1.48,.027,.001),(0,y,.0019),None,colls['Floor'],m['wear'],0)
    marker_path=ROOT/'scene_data/floor_markers.json'
    if marker_path.exists():
        # Preserve the manually edited marker meshes, including when rebuilding
        # from the architecture-only file. Existing unowned markers stay intact.
        markers=json.loads(marker_path.read_text())
        marker_mat=material('ManualFloorMarker',(.8,.8,.8),.5)[0]
        for spec in markers['objects']:
            if bpy.data.objects.get(spec['name']): continue
            mesh=bpy.data.meshes.new(spec['name']+'_Mesh')
            mesh.from_pydata(spec['vertices'],[],spec['faces'])
            obj=attach(bpy.data.objects.new(spec['name'],mesh),spec['name'],None,colls['Floor'],marker_mat)
            obj.location=spec['location'];obj.rotation_euler=spec['rotation'];obj.scale=spec['scale']
            obj['marker_x']=spec['marker_x'];obj['marker_y']=spec['marker_y']
            obj['source']='received_blend_2026-10-15'
    else:
        for j,(x,y) in enumerate(data.get('floor_markers_xy',[])):
            for angle in (-45,45):
                obj=box(f'Floor_Target_{j}_{angle}',(.055,.008,.001),(x,y,.002),None,colls['Floor'],m['marker'],0)
                obj.rotation_euler.z=math.radians(angle)
    # Visors visible on both wooden door leaves, surface approximation only.
    for j,x in enumerate((-2.62,-1.83)):
        box(f'Door_Visor_{j}',(.25,.005,1.10),(x,-4.31,1.40),None,colls['Doors'],m['paper'])


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--objects',type=Path,default=ROOT/'scene_data/objects.json')
    parser.add_argument('--saida',type=Path,default=ROOT/'saida/labsea_atualizado.blend')
    parser.add_argument('--audit',type=Path,default=ROOT/'saida/validacao/build_audit.json')
    argv=sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else []
    args=parser.parse_args(argv)
    if not bpy.data.filepath: raise RuntimeError('Abra o .blend final existente como entrada.')
    if Path(bpy.data.filepath).resolve()==args.saida.resolve():
        raise ValueError('A saída deve ser uma cópia; use outro nome para preservar a entrada.')
    data=json.loads(args.objects.read_text())
    before=snapshot()
    hashes={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in (ROOT/'dados/calibracao').glob('*.npz')}
    for obj in list(bpy.data.objects):
        if obj.get('generated_by')==OWNER: bpy.data.objects.remove(obj,do_unlink=True)
    # Dispose only orphaned datablocks owned by earlier runs of this builder.
    for blocks in (bpy.data.meshes,bpy.data.curves,bpy.data.lights):
        for block in list(blocks):
            if block.users==0: blocks.remove(block)
    colls=organise(); mats=make_materials()
    architecture_materials(mats)
    floor_texture(bpy.data.objects['Piso'],mats['floor'],data.get('rendering',{}).get('floor_texture_srgb_factor',.82))
    architectural_details(data,colls,mats)
    functions={'desk':('Desks',create_desk),'table':('Tables',create_round_table),
               'chair':('Chairs',create_office_chair),'cabinet':('Cabinets',create_cabinet),
               'monitor':('Monitors',create_monitor),'computer':('Computers',create_computer),
               'keyboard':('Keyboards',create_keyboard),'whiteboard':('Whiteboards',create_board),
               'noticeboard':('Noticeboards',create_board),'accessory':('Accessories',create_accessory),
               'printer_3d':('Printers',create_printer)}
    for spec in data['objects']:
        if spec['object_type']=='camera_model':
            create_camera_model(spec,colls['CameraModels'],mats,data['ceiling']['height_m'])
        else:
            cname,fn=functions[spec['object_type']]
            obj=root(spec,colls[cname]); fn(spec,obj,colls[cname],mats)
    configure_lighting(colls['Lighting'],data['ceiling']['height_m'])
    scene=bpy.context.scene
    scene['labsea_reconstructed']=True
    scene['reference_capture']=data['reference_capture']
    scene['ceiling_height_estimated_m']=data['ceiling']['height_m']
    photometry=data.get('rendering',{})
    scene['exposure_base_ev']=photometry.get('exposure_base_ev',-.5)
    scene['camera_exposure_offsets_ev']=json.dumps(photometry.get('camera_exposure_offsets_ev',{}))
    scene.view_settings.exposure=scene['exposure_base_ev']+photometry.get('camera_exposure_offsets_ev',{}).get('1',0)
    scene.unit_settings.system='METRIC';scene.unit_settings.scale_length=1
    bpy.context.view_layer.update()
    after=snapshot()
    if before != after:
        changed=[name for name in before if before[name]!=after.get(name)]
        raise RuntimeError(f'Geometria/câmeras originais alteradas: {changed}')
    # Explicit, documented survey revisions only. Absolute targets are idempotent.
    adjustments=[]
    for change in data.get('architecture_adjustments',[]):
        obj=bpy.data.objects[change['object_id']]
        if obj.type=='CAMERA' or obj.name=='Piso':
            raise ValueError('Ajustes de levantamento não podem alterar piso/câmeras.')
        old=list(obj.location)
        if not (np.allclose(old,change['original_location'],atol=1e-6) or
                np.allclose(old,change['target_location'],atol=1e-6)):
            raise ValueError(f'Objeto mudou desde a revisão documentada: {obj.name}')
        obj.location=change['target_location']
        obj['survey_revision']=change['reason'];obj['survey_confidence']=change['confidence']
        adjustments.append({**change,'input_location':old})
        print(f'[REVISÃO EXPLÍCITA] {obj.name}: {old} -> {list(obj.location)}')
    bpy.context.view_layer.update()
    # The source file contains default 50 mm lenses. The existing renderer
    # supplied nK at runtime. Persist that same projection explicitly here.
    projection_storage={}
    for i in range(1,5):
        camera=bpy.data.objects[f'Camera_{i}']
        K,width,height=ler_calibracao(ROOT/f'dados/calibracao/calib_rt{i}.npz')
        projection_storage[camera.name]={'before':before[camera.name]['camera']}
        configurar_intrinsecos(camera,K,width,height)
        camera['nK_flat']=K.ravel().tolist()
        camera['calibrated_resolution']=[width,height]
        camera['pixel_aspect_y']=float(K[0,0]/K[1,1])
        projection_storage[camera.name]['after']=snapshot()[camera.name]['camera']
    scene.camera=bpy.data.objects['Camera_1']
    K,width,height=ler_calibracao(ROOT/'dados/calibracao/calib_rt1.npz')
    configurar_intrinsecos(scene.camera,K,width,height)
    audit={'source_blend':str(Path(bpy.data.filepath).relative_to(ROOT)),
           'architecture_and_camera_poses_exactly_preserved':not bool(adjustments),'original_objects':len(before),
           'architecture_adjustments_applied':adjustments,
           'camera_poses_exactly_preserved':True,
           'projection_storage_initialized_from_npz':projection_storage,
           'objects_total':len(bpy.data.objects),'roots_created':len(data['objects']),
           'calibration_sha256':hashes,'ceiling':data['ceiling'],
           'original_snapshot':before}
    args.audit.parent.mkdir(parents=True,exist_ok=True)
    args.audit.write_text(json.dumps(audit,indent=2)+'\n')
    args.saida.parent.mkdir(parents=True,exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=str(args.saida.resolve()))
    print(f'[OK] {len(data["objects"])} raízes; câmeras preservadas; '
          f'{len(adjustments)} revisão arquitetônica explícita. {args.saida}')


if __name__=='__main__': main()
