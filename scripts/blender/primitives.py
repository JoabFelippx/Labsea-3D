"""Primitivas em metros, com origens locais e autoria explícita."""
import math

import bpy
from mathutils import Vector

OWNER = "labsea_reconstruction_v1"


def collection(name, parent=None):
    coll = bpy.data.collections.get(name) or bpy.data.collections.new(name)
    parent = parent or bpy.context.scene.collection
    if coll.name not in parent.children:
        parent.children.link(coll)
    return coll


def attach(obj, name, parent, coll, mat=None):
    obj.name = name
    obj["generated_by"] = OWNER
    for old in list(obj.users_collection):
        old.objects.unlink(obj)
    coll.objects.link(obj)
    obj.parent = parent
    if mat:
        obj.data.materials.append(mat)
    return obj


def root(spec, coll):
    obj = bpy.data.objects.new(spec["id"], None)
    coll.objects.link(obj)
    obj.location = spec["position"]
    obj.rotation_euler = [math.radians(a) for a in spec["rotation_deg"]]
    obj.empty_display_size = .15
    for key in ("dynamic", "confidence", "object_type", "name"):
        obj[key] = spec[key]
    obj["generated_by"] = OWNER
    obj["trackable"] = spec.get("trackable", spec["dynamic"])
    obj["coordinate_system"] = "world"
    obj["reference_capture"] = "20261014_141328"
    obj["dimensions_m"] = spec["dimensions"]
    if 'legacy_id' in spec:
        obj['legacy_id'] = spec['legacy_id']
    return obj


def box(name, dims, loc, parent, coll, mat, bevel=.004):
    # Dimensions live in the mesh; the movable root retains unit scale.
    x, y, z = (d / 2 for d in dims)
    mesh = bpy.data.meshes.new(name + "_Mesh")
    mesh.from_pydata([(a*x,b*y,c*z) for a,b,c in
                     [(-1,-1,-1),(1,-1,-1),(1,1,-1),(-1,1,-1),
                      (-1,-1,1),(1,-1,1),(1,1,1),(-1,1,1)]], [],
                    [(3,2,1,0),(0,1,5,4),(1,2,6,5),(2,3,7,6),(3,0,4,7),(4,5,6,7)])
    obj = attach(bpy.data.objects.new(name, mesh), name, parent, coll, mat)
    obj.location = loc
    if bevel:
        mod = obj.modifiers.new("Bordas", "BEVEL")
        mod.width = min(bevel, min(dims) / 3)
        mod.segments = 2
    return obj


def cylinder(name, radius, depth, loc, parent, coll, mat, vertices=24):
    verts=[(radius*math.cos(2*math.pi*j/vertices),radius*math.sin(2*math.pi*j/vertices),z)
           for z in (-depth/2,depth/2) for j in range(vertices)]
    faces=[tuple(reversed(range(vertices))),tuple(range(vertices,2*vertices))]
    faces += [(j,(j+1)%vertices,(j+1)%vertices+vertices,j+vertices) for j in range(vertices)]
    mesh=bpy.data.meshes.new(name+'_Mesh');mesh.from_pydata(verts,[],faces)
    obj = attach(bpy.data.objects.new(name,mesh), name, parent, coll, mat)
    obj.location = loc
    for p in obj.data.polygons:
        p.use_smooth = len(p.vertices) == 4
    return obj


def sphere(name, dims, loc, parent, coll, mat):
    segments,rings=24,12
    rx,ry,rz=[d/2 for d in dims]
    verts=[(0,0,-rz)]
    for j in range(1,rings):
        theta=math.pi*j/rings
        for i in range(segments):
            phi=2*math.pi*i/segments
            verts.append((rx*math.sin(theta)*math.cos(phi),ry*math.sin(theta)*math.sin(phi),-rz*math.cos(theta)))
    top=len(verts);verts.append((0,0,rz))
    faces=[(0,1+(i+1)%segments,1+i) for i in range(segments)]
    for j in range(rings-2):
        a=1+j*segments;b=a+segments
        faces.extend((a+i,a+(i+1)%segments,b+(i+1)%segments,b+i) for i in range(segments))
    last=1+(rings-2)*segments
    faces.extend((last+i,last+(i+1)%segments,top) for i in range(segments))
    mesh=bpy.data.meshes.new(name+'_Mesh');mesh.from_pydata(verts,[],faces)
    obj=attach(bpy.data.objects.new(name,mesh),name,parent,coll,mat)
    obj.location = loc
    for p in obj.data.polygons:
        p.use_smooth = True
    return obj


def rod(name, a, b, radius, parent, coll, mat):
    delta = Vector(b) - Vector(a)
    obj = cylinder(name, radius, delta.length, (Vector(a)+Vector(b))/2,
                   parent, coll, mat, 12)
    obj.rotation_euler = delta.to_track_quat('Z', 'Y').to_euler()
    return obj


def cable(name, points, parent, coll, mat, radius=.003):
    curve = bpy.data.curves.new(name, 'CURVE')
    curve.dimensions = '3D'
    curve.bevel_depth = radius
    curve.bevel_resolution = 2
    spline = curve.splines.new('BEZIER')
    spline.bezier_points.add(len(points)-1)
    for p, co in zip(spline.bezier_points, points):
        p.co = co
        p.handle_left_type = p.handle_right_type = 'AUTO'
    return attach(bpy.data.objects.new(name, curve), name, parent, coll, mat)


def slab_polygon(name, polygon, z, thickness, parent, coll, mat):
    """Extrusão de um contorno simples; aceita o recorte côncavo da mesa L."""
    n = len(polygon)
    verts = [(x,y,h) for h in (z-thickness,z) for x,y in polygon]
    faces = [tuple(reversed(range(n))), tuple(range(n,2*n))]
    faces += [(i,(i+1)%n,(i+1)%n+n,i+n) for i in range(n)]
    mesh = bpy.data.meshes.new(name)
    mesh.from_pydata(verts, [], faces)
    obj = attach(bpy.data.objects.new(name, mesh), name, parent, coll, mat)
    bevel = obj.modifiers.new("Borda_tampo", 'BEVEL')
    bevel.width, bevel.segments = .004, 3
    return obj
