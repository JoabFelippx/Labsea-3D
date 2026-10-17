"""Iluminação estimada da captura; potências não são medições do laboratório."""
import bpy
from mathutils import Vector
from primitives import OWNER


def area(name, position, target, power, size, coll, size_y=None):
    light = bpy.data.lights.new(name, 'AREA')
    light.energy = power
    light.color = (1.0,.97,.91)
    light.shape = 'RECTANGLE' if size_y else 'DISK'
    light.size = size
    if size_y:
        light.size_y = size_y
    obj = bpy.data.objects.new(name,light)
    coll.objects.link(obj)
    obj.location = position
    obj.rotation_euler = (Vector(target)-Vector(position)).to_track_quat('-Z','Y').to_euler()
    obj['generated_by']=OWNER
    obj['estimated_lighting']=True


def configure_lighting(coll, ceiling_z):
    scene=bpy.context.scene
    if scene.world is None:
        scene.world=bpy.data.worlds.new('LabSEA_World')
    scene.world.use_nodes=True
    bg=scene.world.node_tree.nodes.get('Background')
    bg.inputs['Color'].default_value=(.78,.83,.90,1)
    bg.inputs['Strength'].default_value=.22
    for j,x in enumerate((-1.79,1.79)):
        area(f'WindowLight_{j}',(x,4.18,1.85),(x,0,1),350,2.8,coll,1.45)
    # Distribuição artificial aproximada. Sem inventar modelos de luminárias
    # cuja quantidade/posição não pode ser lida nestes frames.
    for j,(x,y) in enumerate([(-1.5,-2),(1.5,-2),(-1.5,1.5),(1.5,1.5)]):
        area(f'CeilingLight_{j}',(x,y,ceiling_z-.045),(x,y,0),50,1.2,coll,.18)
    scene.render.engine='CYCLES'
    scene.cycles.samples=32
    scene.cycles.use_denoising=True
    scene.cycles.max_bounces=6
    scene.cycles.diffuse_bounces=3
    scene.cycles.glossy_bounces=3
    scene.cycles.transparent_max_bounces=4
    scene.view_settings.view_transform='AgX'
    scene.view_settings.look='AgX - Medium High Contrast'
    scene.view_settings.exposure=-.5
    scene.view_settings.gamma=1
    scene.render.image_settings.file_format='PNG'
    scene.render.image_settings.color_mode='RGB'
    scene.render.image_settings.color_depth='8'
