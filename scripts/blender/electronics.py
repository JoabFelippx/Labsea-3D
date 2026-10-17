"""Monitores, periféricos, quadros e acessórios com geometria exportável."""
import math
from primitives import box, cylinder, sphere, rod, cable, attach


def create_printer(spec, root, coll, m):
    """GTMax Core A2v2: nominal envelope, simplified visible mechanism."""
    if spec.get('variant')!='gtmax_core_a2v2':
        return create_accessory(spec,root,coll,m)
    import bpy
    w,d,h=spec['dimensions'];n=root.name
    # Black steel enclosure with transparent front and top (no solid cube).
    box(n+'_Base',(w,d,.055),(0,0,.0275),root,coll,m['black'])
    box(n+'_Traseira',(w,.012,h),(0,d/2-.006,h/2),root,coll,m['black'])
    for x in (-w/2+.006,w/2-.006):
        box(n+'_Lateral',(.012,d,h),(x,0,h/2),root,coll,m['black'])
    front=-d/2+.006
    box(n+'_PainelSuperior',(w,.012,.13),(0,front,h-.065),root,coll,m['black'])
    box(n+'_PainelInferior',(w,.012,.085),(0,front,.0425),root,coll,m['black'])
    for x in (-w/2+.025,w/2-.025):
        box(n+'_Batente',(.05,.012,h-.215),(x,front,(h-.13+.085)/2),root,coll,m['black'])
    opening_h=h-.215;opening_z=.085+opening_h/2
    box(n+'_PortaAcrilica',(w-.10,.003,opening_h),(0,-d/2-.002,opening_z),root,coll,m['acrylic'],.002)
    box(n+'_TampaAcrilica',(w-.025,d-.025,.003),(0,0,h-.002),root,coll,m['acrylic'],.001)
    for z in (.14,h-.18):
        box(n+'_Dobradica',(.018,.012,.035),(-w/2+.045,-d/2-.009,z),root,coll,m['steel'])
    knob=cylinder(n+'_Puxador',.010,.018,(w/2-.052,-d/2-.012,opening_z),root,coll,m['black'])
    knob.rotation_euler.x=math.pi/2
    box(n+'_LCD_Moldura',(.11,.012,.044),(-w*.27,-d/2-.009,.046),root,coll,m['keycap'])
    box(n+'_LCD',(.087,.002,.027),(-w*.27,-d/2-.016,.046),root,coll,m['screen_on'])
    dial=cylinder(n+'_Seletor',.009,.012,(-w*.04,-d/2-.014,.046),root,coll,m['black'])
    dial.rotation_euler.x=math.pi/2
    # 220 mm plate and internal rails. Internal placement is approximate.
    box(n+'_MesaAquecida',(.22,.22,.012),(0,0,.17),root,coll,m['steel'])
    for x in (-.13,.13):
        rod(n+'_GuiaZ',(x,.12,.075),(x,.12,h-.055),.004,root,coll,m['steel'])
        rod(n+'_TrilhoY',(x,-d*.32,h-.08),(x,d*.32,h-.08),.004,root,coll,m['steel'])
    rod(n+'_TrilhoX',(-.15,.025,h-.08),(.15,.025,h-.08),.004,root,coll,m['steel'])
    box(n+'_Cabecote',(.045,.04,.048),(.03,.025,h-.10),root,coll,m['black'])
    cylinder(n+'_Bico',.004,.012,(.03,.025,h-.13),root,coll,m['steel'])
    for x in (-w*.4,w*.4):
        for y in (-d*.4,d*.4):
            cylinder(n+'_Pe',.017,.015,(x,y,.008),root,coll,m['black'])
    # Small labels are geometry and survive GLB export.
    for suffix,text,size,x,z in [('Marca','GTMAX3D',.026,-w*.40,h-.062),
                                ('Modelo','Core A2v2',.013,-w*.10,.096)]:
        curve=bpy.data.curves.new(n+'_'+suffix,'FONT');curve.body=text;curve.size=size
        label=attach(bpy.data.objects.new(n+'_'+suffix,curve),n+'_'+suffix,root,coll,m['paper'])
        label.location=(x,-d/2-.018,z);label.rotation_euler.x=math.pi/2


def create_monitor(spec, root, coll, m):
    w,d,h=spec['dimensions']; n=root.name
    if spec.get('wall_mount'):
        box(n+'_Carcaca',(w,.055,h),(0,0,h/2),root,coll,m['black'],.008)
        box(n+'_Tela',(w-.028,.003,h-.028),(0,-.029,h/2),root,coll,m['screen'],.001)
        return
    box(n+'_Base',(.23,.18,.018),(0,0,.009),root,coll,m['black'])
    rod(n+'_Haste',(0,.025,.02),(0,.025,.22),.018,root,coll,m['black'])
    box(n+'_Carcaca',(w,.045,h*.70),(0,0,h*.65),root,coll,m['black'],.008)
    box(n+'_Tela',(w-.025,.003,h*.70-.025),(0,-.024,h*.65),root,coll,
        m['screen_on'] if spec.get('on') else m['screen'],.001)
    cylinder(n+'_LED',.0018,.002,(w/2-.025,-.026,h*.30),root,coll,m['teal'])
    cable(n+'_Cabo',[(0,.03,.20),(.06,.12,.04),(.1,.20,-.2),(.05,.18,-.45)],root,coll,m['black'])


def create_computer(spec, root, coll, m):
    w,d,h=spec['dimensions'];n=root.name
    box(n+'_Gabinete',(w,d,h),(0,0,h/2),root,coll,m['black'],.008)
    for z in (.55*h,.70*h,.85*h):
        box(n+'_Baia',(w*.85,.006,.035),(0,-d/2-.004,z),root,coll,m['keycap'])
    for j in range(7):
        box(n+'_Ventilacao',(w*.72,.004,.003),(0,-d/2-.009,.08+j*.014),root,coll,m['keycap'],0)


def create_keyboard(spec, root, coll, m):
    w,d,h=spec['dimensions']; n=root.name
    box(n+'_Base',(w,d,h),(0,0,h/2),root,coll,m['black'])
    for row in range(5):
        for col in range(15):
            box(n+f'_Tecla_{row}_{col}',(w/16-.002,d/6-.002,.004),
                ((col-7)*w/16,(row-2)*d/6,h),root,coll,m['keycap'],0)
    sphere(n+'_Mouse',(.056,.10,.033),(w/2+.11,0,.019),root,coll,m['black'])
    cable(n+'_MouseCabo',[(w/2+.11,.04,.02),(w/2+.10,.19,.005),(.1,.25,.005)],root,coll,m['black'],.0015)


def create_board(spec, root, coll, m):
    w,d,h=spec['dimensions']; n=root.name
    box(n+'_Moldura',(w,d,h),(0,0,0),root,coll,m['steel'])
    notice=spec['object_type']=='noticeboard'
    box(n+'_Superficie',(w-.04,.008,h-.04),(0,-d/2-.003,0),root,coll,m['cork' if notice else 'white'])
    if notice:
        for j in range(13):
            # Pequenos papéis; sem reproduzir fotos ou textos pessoais.
            x=-w*.39+(j%4)*.13; z=h*.36-(j//4)*.14
            box(n+f'_Papel{j}',(.085,.002,.09),(x,-d/2-.009,z),root,coll,m['paper'],0)
            box(n+f'_Imagem{j}',(.064,.002,.058),(x,-d/2-.011,z+.009),root,coll,m['blue' if j%3==0 else 'edge'],0)
    else:
        box(n+'_Bandeja',(w*.9,.07,.015),(0,-.06,-h/2),root,coll,m['steel'])
        # Traços esquemáticos esparsos; nenhum texto fictício legível.
        for row in range(3):
            for j in range(5):
                x=-w*.40+j*.38; z=h*.25-row*.22
                cable(n+'_Escrita',[(x,-d/2-.01,z),(x+.08,-d/2-.01,z+.015),
                                   (x+.15,-d/2-.01,z)],root,coll,m['board_ink'],.0015)


def create_accessory(spec, root, coll, m):
    n=root.name;w,d,h=spec['dimensions'];kind=spec.get('variant')
    if kind == 'ladder':
        for x in (-w/2,w/2):
            rod(n+'_Longarina',(x,-.10,0),(x,.10,h),.018,root,coll,m['steel'])
        for j in range(6):
            z=.16+j*.25
            box(n+'_Degrau',(w,.10,.025),(0,-.10+.20*z/h,z),root,coll,m['steel'])
    elif kind == 'printer3d':
        box(n+'_Base',(w,d,.06),(0,0,.03),root,coll,m['black'])
        box(n+'_MesaImpressao',(w*.8,d*.8,.018),(0,0,.14),root,coll,m['steel'])
        for x in (-w/2+.03,w/2-.03):
            rod(n+'_Guia',(x,.06,.05),(x,.06,h),.018,root,coll,m['black'])
        rod(n+'_Travessa',(-w/2,.06,h),(w/2,.06,h),.018,root,coll,m['black'])
        box(n+'_Extrusora',(.06,.07,.08),(.04,.035,.28),root,coll,m['black'])
    elif kind == 'bin':
        cylinder(n+'_Cesto',w/2,h,(0,0,h/2),root,coll,m['teal'])
        cylinder(n+'_Interior',w*.43,.003,(0,0,h+.002),root,coll,m['black'])
    elif kind == 'projector':
        box(n+'_Corpo',(w,d,h),(0,0,0),root,coll,m['keycap'],.025)
        lens=cylinder(n+'_Lente',.035,.02,(w*.22,-d/2-.01,0),root,coll,m['screen'])
        lens.rotation_euler.x=math.pi/2
        rod(n+'_Suporte',(0,0,h/2),(0,0,spec.get('mount_length',.20)),.015,root,coll,m['black'])
    elif kind == 'folded_board':
        panel=box(n+'_Painel',(w,.045,h),(0,0,h/2+.08),root,coll,m['edge'])
        panel.rotation_euler.x=math.radians(15)
        rod(n+'_Apoio',(-w/2,0,.04),(w/2,0,.04),.018,root,coll,m['steel'])
    elif kind == 'shelf':
        for x in (-w/2,w/2):
            box(n+'_Lado',(.02,d,h),(x,0,0),root,coll,m['white'])
        for z in (-h/2,h/2):
            box(n+'_Horizontal',(w,d,.02),(0,0,z),root,coll,m['white'])
        cylinder(n+'_Objeto',.035,h*.65,(0,0,-h*.12),root,coll,m['blue'])
    elif kind == 'cup':
        cylinder(n+'_Copo',w/2,h,(0,0,h/2),root,coll,m['paper'])
        cylinder(n+'_Faixa',w/2+.0005,h*.40,(0,0,h*.42),root,coll,m['teal'])
        cylinder(n+'_Borda',w*.45,.004,(0,0,h),root,coll,m['black'])
    elif kind == 'equipment_case':
        box(n+'_Maleta',(w,d,h),(0,0,h/2),root,coll,m['black'],.065)
        for x in (-w*.3,w*.3):
            box(n+'_FaixaMetal',(.025,d+.002,h+.002),(x,0,h/2),root,coll,m['edge'],.03)
        rod(n+'_Alca',(-.10,-d/2-.02,h*.55),(.10,-d/2-.02,h*.55),.014,root,coll,m['black'])
    elif kind == 'ball':
        sphere(n+'_Bola',(w,d,h),(0,0,h/2),root,coll,m['orange'])
    else:
        box(n+'_Caixa',(w,d,h),(0,0,h/2),root,coll,m['cardboard'])
