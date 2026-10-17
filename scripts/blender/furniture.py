"""Móveis observados na captura. Cada conjunto tem uma raiz independente."""
import math

from primitives import box, cylinder, sphere, rod, slab_polygon


def create_desk(spec, root, coll, m):
    w,d,h = spec['dimensions']; name=root.name
    if spec.get('shape') == 'L':
        # Frente norte e lateral oeste; canto interno suavizado por arco.
        pts=[(-w/2,-d/2),(-w/2,d/2),(w/2,d/2),(w/2,d/2-.66)]
        cx,cy = -.02,-.04
        pts.append((cx+.22,cy+.22))
        for j in range(1,9):
            a=math.pi/2+j*math.pi/16
            pts.append((cx+.22*math.cos(a),cy+.22*math.sin(a)))
        pts += [(cx-.22,-d/2)]
        slab_polygon(name+'_TampoL', list(reversed(pts)),h,.028,root,coll,m['laminate'])
        legs=[(-w/2+.07,-d/2+.07),(-w/2+.07,d/2-.07),(w/2-.07,d/2-.07)]
        for i,(x,y) in enumerate(legs):
            box(name+f'_Pe{i}',(.045,.045,h-.03),(x,y,(h-.03)/2),root,coll,m['steel'])
        box(name+'_Saia',(w-.15,.025,.32),(0,d/2-.13,h-.22),root,coll,m['laminate'])
    else:
        box(name+'_Tampo',(w,d,.028),(0,0,h-.014),root,coll,m['laminate'])
        box(name+'_Saia',(w-.12,.025,.25),(0,d*.30,h-.20),root,coll,m['laminate'])
        for x in (-w/2+.09,w/2-.09):
            box(name+'_Coluna',(.055,.10,h-.07),(x,.06,(h-.07)/2+.035),root,coll,m['steel'])
            box(name+'_Apoio',(.06,d-.04,.035),(x,0,.025),root,coll,m['steel'])
            for y in (-d/2+.035,d/2-.035):
                box(name+'_Sapata',(.075,.09,.025),(x,y,.015),root,coll,m['black'])
        box(name+'_Travessa',(w-.1,.035,.05),(0,.15,h-.09),root,coll,m['steel'])
        if spec.get('drawer_unit'):
            x=w/2-.33
            box(name+'_Gaveteiro',(.44,d*.8,.55),(x,0,.34),root,coll,m['white'])
            for j in range(3):
                z=.18+j*.17
                box(name+f'_Gaveta{j}',(.42,.022,.16),(x,-d*.4-.014,z),root,coll,m['laminate'])
                rod(name+f'_Puxador{j}',(x-.07,-d*.4-.04,z+.03),(x+.07,-d*.4-.04,z+.03),.006,root,coll,m['steel'])


def create_round_table(spec, root, coll, m):
    w,d,h=spec['dimensions']
    top=cylinder(root.name+'_Tampo',w/2,.03,(0,0,h-.015),root,coll,m['white'],64)
    top.scale.y=d/w
    cylinder(root.name+'_Coluna',.065,h-.10,(0,0,(h-.10)/2+.06),root,coll,m['steel'])
    for a in (0,math.pi/2,math.pi,3*math.pi/2):
        rod(root.name+'_Base',(0,0,.10),(.46*math.cos(a),.46*math.sin(a),.035),.023,root,coll,m['steel'])


def create_office_chair(spec, root, coll, m):
    """Origem no piso. Frente local +Y. Mover apenas Chair_NNN."""
    n=root.name
    if spec.get('variant') == 'visitor':
        box(n+'_Assento',(.46,.44,.045),(0,0,.46),root,coll,m['teal'],.018)
        back=sphere(n+'_Encosto',(.46,.07,.40),(0,-.20,.71),root,coll,m['teal'])
        back.rotation_euler.x=math.radians(-8)
        for x in (-.22,.22):
            rod(n+'_Estrutura',(x,.23,.02),(x,.20,.46),.014,root,coll,m['steel'])
            rod(n+'_Estrutura',(x,-.25,.02),(x,-.20,.86),.014,root,coll,m['steel'])
            rod(n+'_Lateral',(x,-.2,.44),(x,.2,.44),.014,root,coll,m['steel'])
        return
    sphere(n+'_Concha',(.48,.47,.08),(0,0,.43),root,coll,m['black'])
    sphere(n+'_Assento',(.47,.46,.10),(0,.005,.48),root,coll,m['fabric'])
    back=sphere(n+'_EncostoConcha',(.45,.09,.47),(0,-.23,.78),root,coll,m['black'])
    back.rotation_euler.x=math.radians(-8)
    pad=sphere(n+'_EncostoTecido',(.42,.075,.43),(0,-.19,.79),root,coll,m['fabric'])
    pad.rotation_euler.x=math.radians(-8)
    rod(n+'_SuporteEncosto',(0,-.16,.40),(0,-.25,.71),.022,root,coll,m['black'])
    cylinder(n+'_Pistao',.024,.29,(0,0,.29),root,coll,m['steel'])
    cylinder(n+'_CapaPistao',.045,.14,(0,0,.19),root,coll,m['black'])
    for j in range(5):
        a=2*math.pi*j/5
        x,y=.29*math.cos(a),.29*math.sin(a)
        rod(n+f'_Raio{j}',(0,0,.17),(x,y,.09),.024,root,coll,m['black'])
        for side in (-1,1):
            wheel=cylinder(n+f'_Rodizio{j}_{side}',.028,.018,
                           (x+side*.019,y,.044),root,coll,m['black'],16)
            wheel.rotation_euler.y=math.pi/2
    if spec.get('arms',True):
        for x in (-.285,.285):
            rod(n+'_BracoVertical',(x*.8,0,.40),(x,0,.64),.017,root,coll,m['black'])
            box(n+'_ApoioBraco',(.055,.25,.035),(x,.025,.66),root,coll,m['black'],.013)
    rod(n+'_Alavanca',(.13,.02,.40),(.28,.06,.39),.008,root,coll,m['black'])


def create_cabinet(spec, root, coll, m):
    w,d,h=spec['dimensions']; n=root.name
    box(n+'_Corpo',(w,d,h-.06),(0,0,(h+.06)/2),root,coll,m['laminate'])
    for x in (-w/4,w/4):
        box(n+'_Porta',(w/2-.006,.022,h-.09),(x,-d/2-.012,(h+.06)/2),root,coll,m['white'])
        sign=1 if x<0 else -1
        hx=x+sign*(w/4-.065)
        rod(n+'_Puxador',(hx,-d/2-.05,h*.47),(hx,-d/2-.05,h*.55),.007,root,coll,m['steel'])
    for x in (-w/2+.06,w/2-.06):
        for y in (-d/2+.05,d/2-.05):
            cylinder(n+'_Pe',.022,.06,(x,y,.03),root,coll,m['black'])
