"""Verificações da reconstrução executadas no Python do Blender, sem salvar."""
import json
from pathlib import Path
import sys
import hashlib
import struct
import math

import bpy
import numpy as np
from bpy_extras.object_utils import world_to_camera_view
from mathutils import Vector, Euler

sys.path.insert(0,str(Path(__file__).resolve().parent))
from scene_builder import snapshot
from renderizar_cameras import configurar_intrinsecos, ler_calibracao

ROOT=Path(__file__).resolve().parents[2]


def check_furniture_clearance(specs):
    """Separating-axis check of table tops and cabinet footprints in world XY.

    The L desk uses its enclosing rectangle (a conservative test); the round
    table uses 128 perimeter points. Chairs may slide under tops and are excluded.
    """
    footprints=[]
    for spec in specs:
        kind=spec['object_type']
        if kind not in ('desk','table','cabinet'): continue
        w,d,h=spec['dimensions']
        if kind=='table':
            points=np.array([(w/2*math.cos(a),d/2*math.sin(a))
                             for a in np.linspace(0,2*math.pi,128,endpoint=False)])
        else:
            points=np.array([[-w/2,-d/2],[w/2,-d/2],[w/2,d/2],[-w/2,d/2]])
        angle=math.radians(spec['rotation_deg'][2])
        rotation=np.array([[math.cos(angle),-math.sin(angle)],[math.sin(angle),math.cos(angle)]])
        points=points@rotation.T+spec['position'][:2]
        footprints.append((spec['id'],points))
    architecture=[]
    for obj in bpy.data.objects:
        if obj.type=='MESH' and obj.name.startswith(('Parede_','Pilar_')):
            corners=np.array([obj.matrix_world@Vector(v) for v in obj.bound_box])
            lo,hi=corners[:,:2].min(axis=0),corners[:,:2].max(axis=0)
            architecture.append((obj.name,np.array([[lo[0],lo[1]],[hi[0],lo[1]],
                                                    [hi[0],hi[1]],[lo[0],hi[1]]])))
    overlaps=[];pairs=0
    for i,(name,a) in enumerate(footprints):
        for other,b in footprints[i+1:]+architecture:
            pairs+=1
            axes=[]
            for points in (a,b):
                edges=np.roll(points,-1,axis=0)-points
                normals=np.stack((-edges[:,1],edges[:,0]),axis=1)
                axes.extend(normals/np.linalg.norm(normals,axis=1)[:,None])
            depths=[]
            for axis in axes:
                pa,pb=a@axis,b@axis
                depths.append(min(pa.max(),pb.max())-max(pa.min(),pb.min()))
            if min(depths)>1e-5:
                overlaps.append({'a':name,'b':other,'penetration_m':float(min(depths))})
    result={'method':'SAT world-XY; rectangles and 128-point round table; L enclosing rectangle',
            'scope':'Desk/table tops, cabinet bodies, walls and pillars; not a full mesh collision check',
            'pairs_checked':pairs,'overlaps':overlaps}
    (ROOT/'saida/validacao/furniture_clearance.json').write_text(json.dumps(result,indent=2)+'\n')
    assert not overlaps,f'Interseções entre móveis: {overlaps}'
    return result


def check_glb(specs):
    path=ROOT/'saida/labsea.glb'
    raw=path.read_bytes()
    magic,version,size=struct.unpack_from('<4sII',raw)
    assert magic==b'glTF' and version==2 and size==len(raw)
    length,kind=struct.unpack_from('<I4s',raw,12)
    assert kind==b'JSON'
    gltf=json.loads(raw[20:20+length])
    nodes={n['name']:n for n in gltf['nodes'] if 'name' in n}
    chairs=[s for s in specs if s['object_type']=='chair']
    for spec in chairs:
        node=nodes[spec['id']]
        assert node['extras']['dynamic'] and node['extras']['trackable']
        assert node.get('children')
        x,y,z=spec['position']
        assert np.max(np.abs(np.array(node.get('translation',[0,0,0]))-[x,z,-y]))<1e-5
        rotation=Euler([math.radians(a) for a in spec['rotation_deg']]).to_quaternion()
        expected=np.array([rotation.x,rotation.z,-rotation.y,rotation.w])
        actual=np.array(node.get('rotation',[0,0,0,1]))
        assert min(np.linalg.norm(actual-expected),np.linalg.norm(actual+expected))<1e-6
    assert not gltf.get('cameras')
    assert gltf.get('images')
    result={'valid_glb2':True,'bytes':len(raw),'nodes':len(gltf['nodes']),
            'meshes':len(gltf['meshes']),'embedded_images':len(gltf['images']),
            'independent_chair_roots':len(chairs),
            'chair_properties_and_axis_conversion_verified':True}
    (ROOT/'saida/validacao/glb_checks.json').write_text(json.dumps(result,indent=2)+'\n')
    return result


def main():
    audit=json.loads((ROOT/'saida/validacao/build_audit.json').read_text())
    data=json.loads((ROOT/'scene_data/objects.json').read_text())
    revisions={r['object_id']:r for r in data.get('architecture_adjustments',[])}
    current=snapshot()
    for name,record in audit['original_snapshot'].items():
        now=current[name]
        expected=np.array(record['matrix'])
        if name in revisions:
            expected[:3,3]=revisions[name]['target_location']
        assert np.max(np.abs(np.array(now['matrix'])-expected))<1e-7,f'Transformação modificada: {name}'
        for key in ('mesh_sha256','faces_sha256','modifiers'):
            if key in record:
                assert json.loads(json.dumps(now[key]))==record[key],f'Geometria modificada: {name}, {key}'
    for path,sha in audit['calibration_sha256'].items():
        assert hashlib.sha256((ROOT/path).read_bytes()).hexdigest()==sha,path
    specs=data['objects']
    roots=[o for o in bpy.data.objects if o.get('generated_by')=='labsea_reconstruction_v1' and o.type=='EMPTY']
    assert sorted(o.name for o in roots)==sorted(s['id'] for s in specs)
    for spec in specs:
        obj=bpy.data.objects[spec['id']]
        assert np.max(np.abs(np.array(obj.location)-spec['position']))<1e-5,spec['id']
        expected=Euler([math.radians(a) for a in spec['rotation_deg']]).to_matrix()
        assert np.max(np.abs(np.array(obj.rotation_euler.to_matrix())-np.array(expected)))<1e-6,spec['id']
    check_furniture_clearance(specs)
    markers_path=ROOT/'scene_data/floor_markers.json'
    marker_count=0
    if markers_path.exists():
        for spec in json.loads(markers_path.read_text())['objects']:
            obj=bpy.data.objects[spec['name']]
            assert [list(v.co) for v in obj.data.vertices]==spec['vertices']
            assert [list(p.vertices) for p in obj.data.polygons]==spec['faces']
            assert list(obj.location)==spec['location']
            assert list(obj.rotation_euler)==spec['rotation']
            assert list(obj.scale)==spec['scale']
            marker_count+=1
    # Validate nK against Blender's real projection, accounting for half pixels.
    scene=bpy.context.scene
    projection_errors={};pose_errors={}
    for i in range(1,5):
        cam=bpy.data.objects[f'Camera_{i}']
        with np.load(ROOT/f'dados/calibracao/calib_rt{i}.npz') as c:
            K,w,h=ler_calibracao(ROOT/f'dados/calibracao/calib_rt{i}.npz')
            configurar_intrinsecos(cam,K,w,h)
            scene.camera=cam
            bpy.context.view_layer.update()
            expected=c['rt_inv'].copy();expected[:3,:3]=expected[:3,:3]@np.diag([1,-1,-1])
            pose_errors[str(i)]=float(np.max(np.abs(np.array(cam.matrix_world)-expected)))
            errors=[]
            for x in (-2,0,2):
                for y in (-3,0,3):
                    for z in (0,.75,1.5):
                        p=np.array([x,y,z,1]);q=K@c['rt'][:3]@p
                        if q[2]<=0:continue
                        uv=q[:2]/q[2]
                        ndc=world_to_camera_view(scene,cam,Vector(p[:3]))
                        blender_uv=np.array([ndc.x*w-.5,(1-ndc.y)*h-.5])
                        errors.append(float(np.linalg.norm(blender_uv-uv)))
            projection_errors[str(i)]=max(errors)
            assert pose_errors[str(i)]<2e-6
            assert projection_errors[str(i)]<.01,(i,projection_errors[str(i)])
    # Move each dynamic root, verify every descendant and all other roots.
    chair_count=0
    for obj in roots:
        if obj.get('object_type')!='chair':continue
        chair_count+=1
        for prop in ('dynamic','trackable'):assert obj[prop] is True
        assert obj['coordinate_system']=='world'
        assert tuple(obj.scale)==(1,1,1)
        originals={ch.name:ch.matrix_world.copy() for ch in obj.children_recursive}
        other_roots={r.name:r.matrix_world.copy() for r in roots if r!=obj}
        start=obj.location.copy();obj.location.x+=.25
        bpy.context.view_layer.update()
        for ch in obj.children_recursive:
            expected=originals[ch.name].copy();expected.translation.x+=.25
            assert np.max(np.abs(np.array(ch.matrix_world)-np.array(expected)))<1e-5
        for name,matrix in other_roots.items():
            assert np.max(np.abs(np.array(bpy.data.objects[name].matrix_world)-np.array(matrix)))<1e-7
        obj.location=start;bpy.context.view_layer.update()
    result={'architecture_meshes_preserved':True,
            'architecture_transforms_preserved_except_documented_revisions':True,
            'documented_architecture_revisions':list(revisions),
            'calibration_files_unchanged':True,
            'camera_pose_max_abs_error':pose_errors,'blender_opencv_projection_max_error_px':projection_errors,
            'independent_chairs_tested':chair_count,'root_ids_verified':len(roots),
            'manual_floor_markers_preserved':marker_count,
            'objects_total':len(bpy.data.objects),'meshes_total':sum(o.type=='MESH' for o in bpy.data.objects)}
    (ROOT/'saida/validacao/scene_checks.json').write_text(json.dumps(result,indent=2)+'\n')
    check_glb(specs)
    print(json.dumps(result,indent=2))


if __name__=='__main__':main()
