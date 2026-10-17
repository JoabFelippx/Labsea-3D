"""Montagem no forro: base horizontal, lente orientada pela calibração."""
import math
from mathutils import Vector
from primitives import root, cylinder, sphere, rod

DIAMETER = .109
HEIGHT = .0855


def create_camera_model(spec, coll, mats, ceiling_z):
    import bpy
    camera = bpy.data.objects[f"Camera_{spec['camera_id']}"]
    obj = root(spec, coll)
    # Root at calibrated optical centre in WORLD axes, not tilted with the base.
    obj.location = camera.matrix_world.translation
    obj.rotation_euler = (0,0,0)
    behind = camera.matrix_world.to_3x3() @ Vector((0,0,1))
    centre = behind * .025
    centre.z=.015
    # Approximate internal optical offset. Only external envelope is specified
    # by the manufacturer; the ceiling gap is explicitly estimated.
    base_z = .055
    base = cylinder(obj.name+'_Base',DIAMETER/2,.020,
                    (centre.x,centre.y,base_z),obj,coll,mats['white'],48)
    cylinder(obj.name+'_Aro',.049,.015,(centre.x,centre.y,.042),obj,coll,mats['edge'],48)
    sphere(obj.name+'_Dome',(.088,.088,.071),centre,obj,coll,mats['white'])
    for name,radius,depth,offset,mat in [('AroLente',.022,.008,.002,'black'),
                                       ('Lente',.011,.003,-.003,'screen')]:
        lens=cylinder(obj.name+'_'+name,radius,depth,behind*offset,obj,coll,mats[mat],40)
        lens.rotation_euler=camera.rotation_euler.copy()
    gap=ceiling_z-(obj.location.z+base_z+.01)
    if gap>0:
        rod(obj.name+'_EspacadorForro',(centre.x,centre.y,base_z),
            (centre.x,centre.y,ceiling_z-obj.location.z),.022,obj,coll,mats['white'])
    obj['nominal_height_m']=HEIGHT
    obj['nominal_diameter_m']=DIAMETER
    obj['mount']='ceiling'
    obj['optical_offset_approximate']=True
    for child in obj.children:
        child['camera_id_visual']=spec['camera_id']
    return obj
