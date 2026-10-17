"""Materiais PBR procedurais. Coordenadas de textura em metros do mundo."""
import bpy
import numpy as np


def material(name, color, roughness=.5, metallic=0):
    mat = bpy.data.materials.get("LabSEA_"+name) or bpy.data.materials.new("LabSEA_"+name)
    mat.use_nodes = True
    mat.node_tree.nodes.clear()
    nodes, links = mat.node_tree.nodes, mat.node_tree.links
    bsdf = nodes.new('ShaderNodeBsdfPrincipled')
    out = nodes.new('ShaderNodeOutputMaterial')
    links.new(bsdf.outputs['BSDF'], out.inputs['Surface'])
    bsdf.inputs['Base Color'].default_value = (*color, 1)
    bsdf.inputs['Roughness'].default_value = roughness
    bsdf.inputs['Metallic'].default_value = metallic
    mat.diffuse_color = (*color,1)
    return mat, nodes, links, bsdf


def noise_finish(mat, scale, strength, distance):
    nodes, links = mat.node_tree.nodes, mat.node_tree.links
    bsdf = next(n for n in nodes if n.type == 'BSDF_PRINCIPLED')
    geo = nodes.new('ShaderNodeNewGeometry')
    noise = nodes.new('ShaderNodeTexNoise')
    noise.inputs['Scale'].default_value = scale
    noise.inputs['Detail'].default_value = 2
    links.new(geo.outputs['Position'], noise.inputs['Vector'])
    bump = nodes.new('ShaderNodeBump')
    bump.inputs['Strength'].default_value = strength
    bump.inputs['Distance'].default_value = distance
    links.new(noise.outputs['Fac'], bump.inputs['Height'])
    links.new(bump.outputs['Normal'], bsdf.inputs['Normal'])
    return noise


def make_materials():
    specs = {
        'paint': ((.66,.67,.61),.82,0),
        'laminate': ((.60,.62,.58),.42,0),
        'white': ((.73,.75,.71),.4,0),
        'edge': ((.33,.36,.34),.52,0),
        'steel': ((.48,.52,.50),.32,.65),
        'black': ((.005,.007,.009),.62,0),
        'fabric': ((.010,.014,.019),.93,0),
        'keycap': ((.018,.023,.025),.75,0),
        'teal': ((.035,.29,.26),.56,0),
        'screen': ((.008,.015,.020),.32,0),
        'screen_on': ((.32,.45,.55),.5,0),
        'cork': ((.36,.23,.10),.97,0),
        'paper': ((.72,.73,.66),.85,0),
        'wood': ((.12,.062,.030),.55,0),
        'green_tile': ((.035,.080,.040),.38,0),
        'grout': ((.38,.41,.35),.9,0),
        'floor': ((.21,.20,.17),.26,0),
        'seam': ((.055,.049,.040),.8,0),
        'wear': ((.065,.055,.045),.9,0),
        'marker': ((.018,.035,.085),.8,0),
        'glass': ((.68,.76,.80),.22,0),
        'acrylic': ((.80,.84,.85),.18,0),
        'board_ink': ((.025,.08,.065),.8,0),
        'blue': ((.018,.07,.23),.55,0),
        'orange': ((.52,.22,.025),.6,0),
        'cardboard': ((.33,.23,.12),.87,0),
    }
    mats = {k: material(k,*args)[0] for k,args in specs.items()}
    noise_finish(mats['paint'],180,.12,.0008)
    noise_finish(mats['fabric'],450,.45,.001)
    noise_finish(mats['cork'],220,.3,.002)
    noise_finish(mats['wood'],90,.12,.001)
    # Terrazzo: fragments at millimetre scale, warm grey matrix, low relief.
    mat = mats['floor']; nodes, links = mat.node_tree.nodes, mat.node_tree.links
    noise = noise_finish(mat,160,.22,.001)
    ramp = nodes.new('ShaderNodeValToRGB')
    ramp.color_ramp.elements.remove(ramp.color_ramp.elements[1])
    stops = [(.20,(.018,.017,.014,1)),(.40,(.065,.061,.050,1)),
             (.47,(.16,.15,.12,1)),(.54,(.28,.26,.21,1)),(.68,(.55,.53,.45,1))]
    for j,(pos,color) in enumerate(stops):
        el = ramp.color_ramp.elements[0] if j == 0 else ramp.color_ramp.elements.new(pos)
        el.position, el.color = pos, color
    links.new(noise.outputs['Fac'], ramp.inputs[0])
    bsdf = next(n for n in nodes if n.type == 'BSDF_PRINCIPLED')
    links.new(ramp.outputs['Color'], bsdf.inputs['Base Color'])
    glass = next(n for n in mats['glass'].node_tree.nodes if n.type == 'BSDF_PRINCIPLED')
    glass.inputs['Transmission Weight'].default_value = .35
    glass.inputs['IOR'].default_value = 1.45
    # Exterior não reconstruído: radiância difusa aproxima a janela clara.
    glass.inputs['Emission Color'].default_value = (.80,.85,.95,1)
    glass.inputs['Emission Strength'].default_value = 1.8
    acrylic = next(n for n in mats['acrylic'].node_tree.nodes if n.type == 'BSDF_PRINCIPLED')
    acrylic.inputs['Transmission Weight'].default_value = .9
    acrylic.inputs['IOR'].default_value = 1.49
    return mats


def assign_material(obj, mat):
    obj.data.materials.clear()
    obj.data.materials.append(mat)


def floor_texture(obj, mat, albedo_factor=.82):
    """Granilite determinístico, tile de 1 m, empacotado e exportável em glTF.

    Textura criada por algoritmo; não contém fotografia nem iluminação capturada.
    Fragmentos aproximados com raios de 1–4 mm. UV mede metros no mundo.
    """
    size=1024
    rng=np.random.default_rng(20261014)
    pixels=np.ones((size,size,4),dtype=np.float32)
    noise=rng.normal(0,.014,(size,size,1))
    pixels[:,:,:3]=np.clip(np.array([.50,.48,.425])+noise,0,1)
    palette=np.array([[.16,.15,.13],[.27,.26,.23],[.70,.69,.64],[.61,.59,.53],[.41,.39,.34]])
    for _ in range(23000):
        x,y=rng.integers(4,size-4,2); rx,ry=rng.integers(1,5,2)
        yy,xx=np.ogrid[-ry:ry+1,-rx:rx+1]
        mask=(xx/rx)**2+(yy/ry)**2<=1
        patch=pixels[y-ry:y+ry+1,x-rx:x+rx+1,:3]
        patch[mask]=np.clip(palette[rng.integers(len(palette))]+rng.normal(0,.018),0,1)
    # Ajuste de refletância pelas regiões livres do piso nas quatro imagens.
    # Aplica-se ao material da cena inteira; não é correção de cada render.
    pixels[:,:,:3]*=albedo_factor
    img=bpy.data.images.get('LabSEA_Terrazzo_1m')
    if img: bpy.data.images.remove(img)
    img=bpy.data.images.new('LabSEA_Terrazzo_1m',size,size,alpha=False)
    img.colorspace_settings.name='sRGB'
    img.pixels.foreach_set(pixels.ravel())
    img.pack()
    nodes,links=mat.node_tree.nodes,mat.node_tree.links
    for node in list(nodes):
        if node.type=='TEX_IMAGE': nodes.remove(node)
    tex=nodes.new('ShaderNodeTexImage');tex.image=img;tex.extension='REPEAT'
    bsdf=next(n for n in nodes if n.type=='BSDF_PRINCIPLED')
    links.new(tex.outputs['Color'],bsdf.inputs['Base Color'])
    bump=next(n for n in nodes if n.type=='BUMP')
    links.new(tex.outputs['Color'],bump.inputs['Height'])
    uv=obj.data.uv_layers.get('Terrazzo_WorldMeters') or obj.data.uv_layers.new(name='Terrazzo_WorldMeters')
    obj.data.uv_layers.active=uv
    uv.active_render=True
    for loop in obj.data.loops:
        world=obj.matrix_world@obj.data.vertices[loop.vertex_index].co
        uv.data[loop.index].uv=world.x,world.y
