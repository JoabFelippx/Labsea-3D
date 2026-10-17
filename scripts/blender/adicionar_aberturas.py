"""Abre portas e janelas nas paredes de modelos/labsea.blend.

Preparado para as paredes geradas pelo script 'criar_labsea.py':
  Parede_north, Parede_south, Parede_east, Parede_west.

Uso (a partir da pasta do projeto):
  blender -b modelos/labsea.blend --python scripts/blender/adicionar_aberturas.py

Configuracao: configs/aberturas/labsea.json.
Saida padrao: saida/labsea_sem_j16.blend (nao altera o original).

IMPORTANTE:
- As posicoes no JSON sao provisórias e precisam ser conferidas com a planta real.
- As cameras existentes nao sao movidas nem recalibradas.
- O script deve ser executado sempre sobre labsea.blend ORIGINAL.
"""

import json
import sys
import argparse
from pathlib import Path

import bpy


MARGEM_FURO = 0.03        # Cortador ultrapassa as faces, evitando faces coplanares.
LARGURA_MOLDURA = 0.045  # 4,5 cm: valor visual provisório.
ESPESSURA_VIDRO = 0.012
ESPESSURA_PORTA = 0.035
COLECAO_NOME = "03_Portas_Janelas"
PAREDES_VALIDAS = ("north", "south", "east", "west")


def argumentos():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    raiz = Path(__file__).resolve().parents[2]
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=raiz / "configs" / "aberturas" / "labsea.json")
    parser.add_argument("--saida", type=Path, default=raiz / "saida" / "labsea_sem_j16.blend")
    return parser.parse_args(argv)


def carregar_config(path):
    with open(path, encoding="utf-8") as file:
        cfg = json.load(file)
    aberturas = cfg.get("aberturas", [])
    if not aberturas:
        raise ValueError("O JSON nao contem 'aberturas'.")
    nomes = [a["nome"] for a in aberturas]
    if len(nomes) != len(set(nomes)):
        raise ValueError("Cada abertura deve ter um nome unico.")
    return aberturas


def material(nome, rgba, transparencia=False):
    mat = bpy.data.materials.get(nome)
    if mat is None:
        mat = bpy.data.materials.new(nome)
    mat.diffuse_color = rgba
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    principled = nodes.get("Principled BSDF")
    if principled:
        principled.inputs["Base Color"].default_value = rgba
        principled.inputs["Alpha"].default_value = rgba[3]
        if transparencia:
            t = principled.inputs.get("Transmission Weight") or principled.inputs.get("Transmission")
            if t:
                t.default_value = 0.7
            roughness = principled.inputs.get("Roughness")
            if roughness:
                roughness.default_value = 0.08
    if transparencia:
        if hasattr(mat, "surface_render_method"):
            mat.surface_render_method = "DITHERED"
        elif hasattr(mat, "blend_method"):
            mat.blend_method = "BLEND"
    return mat


def criar_colecao():
    if bpy.data.collections.get(COLECAO_NOME):
        raise RuntimeError(
            f"A colecao '{COLECAO_NOME}' ja existe. "
            "Execute sobre o labsea.blend ORIGINAL para evitar cortes duplicados."
        )
    coll = bpy.data.collections.new(COLECAO_NOME)
    bpy.context.scene.collection.children.link(coll)
    return coll


def mover_para_colecao(obj, coll):
    for antiga in list(obj.users_collection):
        antiga.objects.unlink(obj)
    coll.objects.link(obj)


def criar_bloco(nome, centro, dimensoes, material_bloco, coll=None):
    bpy.ops.mesh.primitive_cube_add(size=1, location=centro)
    obj = bpy.context.object
    obj.name = nome
    obj.dimensions = dimensoes
    bpy.context.view_layer.update()
    if material_bloco is not None:
        obj.data.materials.append(material_bloco)
    if coll is not None:
        mover_para_colecao(obj, coll)
    return obj


def validar_abertura(abertura, parede):
    tipo = abertura["tipo"]
    lado = abertura["parede"]
    if tipo not in ("porta_dupla", "janela"):
        raise ValueError(f"{abertura['nome']}: tipo desconhecido: {tipo}")
    if lado not in PAREDES_VALIDAS:
        raise ValueError(f"{abertura['nome']}: parede desconhecida: {lado}")
    if parede.type != "MESH":
        raise TypeError(f"Parede_{lado} nao e um objeto de malha.")
    if any(abs(a) > 1e-5 for a in parede.rotation_euler):
        raise ValueError(f"Parede_{lado} esta rotacionada; esperado objeto alinhado a XYZ.")

    comprimento = float(parede.dimensions.y if lado in ("east", "west") else parede.dimensions.x)
    largura = float(abertura["largura"])
    centro = float(abertura["centro_ao_longo"])
    altura = float(abertura["altura"])
    base = float(abertura["base_z"])
    centro_parede = float(parede.location.y if lado in ("east", "west") else parede.location.x)
    meio_z = float(parede.location.z)
    z_min = meio_z - float(parede.dimensions.z) / 2
    z_max = meio_z + float(parede.dimensions.z) / 2

    if largura <= 0 or altura <= 0:
        raise ValueError(f"{abertura['nome']}: largura e altura devem ser positivas.")
    if abs(centro) + largura / 2 >= comprimento / 2 - 0.03:
        raise ValueError(
            f"{abertura['nome']}: nao cabe na Parede_{lado}. "
            f"centro_ao_longo={centro} (deslocamento em metros desde o centro da parede), "
            f"largura={largura}, comprimento_parede={comprimento}."
        )
    if base < z_min - 0.005 or base + altura > z_max - 0.03:
        raise ValueError(
            f"{abertura['nome']}: altura fora dos limites da parede "
            f"(z={z_min:.3f} a {z_max:.3f})."
        )
    if tipo == "porta_dupla" and abs(base - z_min) > 0.01:
        raise ValueError("Porta deve partir do piso da parede (base_z = 0 no modelo atual).")
    if largura <= 4 * LARGURA_MOLDURA or altura <= 4 * LARGURA_MOLDURA:
        raise ValueError(f"{abertura['nome']}: abertura pequena demais para as molduras.")
    return centro_parede + centro


def posicao_bloco(lado, parede, ponto_ao_longo, z):
    """Recebe coordenada ao longo da parede e Z. Retorna centro XYZ no mundo."""
    if lado in ("east", "west"):
        return (float(parede.location.x), ponto_ao_longo, z)
    return (ponto_ao_longo, float(parede.location.y), z)


def dimensoes_bloco(lado, ao_longo, profundidade, altura):
    if lado in ("east", "west"):
        return (profundidade, ao_longo, altura)
    return (ao_longo, profundidade, altura)


def aplicar_escala(obj):
    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)


def abrir_vao(parede, abertura, along_global):
    lado = abertura["parede"]
    centro_z = abertura["base_z"] + abertura["altura"] / 2
    largura = abertura["largura"]
    profundidade = float(parede.dimensions.x if lado in ("east", "west") else parede.dimensions.y)
    centro = posicao_bloco(lado, parede, along_global, centro_z)
    corte = criar_bloco(
        "TEMP_cortador_" + abertura["nome"],
        centro,
        dimensoes_bloco(lado, largura, profundidade + 2 * MARGEM_FURO,
                         abertura["altura"] + 2 * MARGEM_FURO),
        None,
    )
    aplicar_escala(parede)
    aplicar_escala(corte)
    bpy.ops.object.select_all(action="DESELECT")
    parede.select_set(True)
    bpy.context.view_layer.objects.active = parede
    mod = parede.modifiers.new("Corte_" + abertura["nome"], "BOOLEAN")
    mod.operation = "DIFFERENCE"
    mod.solver = "EXACT"
    mod.object = corte
    try:
        bpy.ops.object.modifier_apply(modifier=mod.name)
    finally:
        bpy.data.objects.remove(corte, do_unlink=True)
    bpy.context.view_layer.update()


def criar_elementos(abertura, parede, along_global, coll, mat_moldura, mat_porta, mat_vidro):
    """Molduras, folhas e vidro ficam DENTRO do vao booleano."""
    lado = abertura["parede"]
    tipo = abertura["tipo"]
    nome = abertura["nome"]
    w, h = float(abertura["largura"]), float(abertura["altura"])
    z0 = float(abertura["base_z"])
    t = LARGURA_MOLDURA
    prof_parede = float(parede.dimensions.x if lado in ("east", "west") else parede.dimensions.y)
    prof_moldura = prof_parede + 0.02

    def componente(sufixo, offset, z, largura_comp, altura_comp, profundidade, material_comp):
        return criar_bloco(
            f"{nome}_{sufixo}",
            posicao_bloco(lado, parede, along_global + offset, z),
            dimensoes_bloco(lado, largura_comp, profundidade, altura_comp),
            material_comp,
            coll,
        )

    # Laterais e travessa superior, posicionado dentro do vao.
    for sinal, tag in ((-1, "lado_A"), (1, "lado_B")):
        componente(f"batente_{tag}", sinal * (w / 2 - t / 2),
                   z0 + h / 2, t, h, prof_moldura, mat_moldura)
    componente("batente_superior", 0, z0 + h - t / 2,
               w, t, prof_moldura, mat_moldura)

    if tipo == "janela":
        componente("batente_inferior", 0, z0 + t / 2,
                   w, t, prof_moldura, mat_moldura)
        componente("vidro", 0, z0 + h / 2,
                   w - 2*t - 0.01, h - 2*t - 0.01, ESPESSURA_VIDRO, mat_vidro)
        componente("divisoria_central", 0, z0 + h / 2,
                   t * 0.75, h - 2*t, prof_moldura, mat_moldura)
    elif tipo == "porta_dupla":
        # Duas folhas FECHADAS; o vao na parede continua sendo um corte real.
        largura_folha = (w - 2*t - 0.015) / 2
        h_folha = h - t - 0.025
        for sinal, tag in ((-1, "esquerda"), (1, "direita")):
            offset = sinal * (largura_folha / 2 + 0.0075)
            componente(f"folha_{tag}", offset, z0 + h_folha/2 + 0.012,
                       largura_folha, h_folha, ESPESSURA_PORTA, mat_porta)


def verificar_intersecoes(aberturas):
    por_parede = {}
    for a in aberturas:
        por_parede.setdefault(a["parede"], []).append(a)
    for lado, itens in por_parede.items():
        for i, a in enumerate(itens):
            for b in itens[i+1:]:
                # Conflito só se os intervalos horizontal E vertical se cruzarem.
                aw, bw = a["largura"] / 2, b["largura"] / 2
                overlap_xy = abs(a["centro_ao_longo"] - b["centro_ao_longo"]) < aw + bw + 0.04
                overlap_z = max(a["base_z"], b["base_z"]) < min(a["base_z"]+a["altura"], b["base_z"]+b["altura"])
                if overlap_xy and overlap_z:
                    raise ValueError(f"Aberturas {a['nome']} e {b['nome']} se cruzam na parede {lado}.")


def main():
    args = argumentos()
    aberturas = carregar_config(args.config.expanduser().resolve())
    verificar_intersecoes(aberturas)

    # Exige o arquivo original ja carregado, com as paredes e cameras existentes.
    if not bpy.data.filepath:
        raise RuntimeError("Abra o arquivo .blend como entrada: blender -b modelos/labsea.blend --python ...")
    nomes_paredes = {a["parede"] for a in aberturas}
    paredes = {}
    for lado in nomes_paredes:
        parede = bpy.data.objects.get(f"Parede_{lado}")
        if parede is None:
            raise KeyError(f"Nao encontrei Parede_{lado}. Objetos esperados: Parede_north/south/east/west.")
        paredes[lado] = parede

    # Valida a configuracao inteira ANTES de alterar qualquer malha.
    centros = [validar_abertura(a, paredes[a["parede"]]) for a in aberturas]
    coll = criar_colecao()
    mat_moldura = material("Aberturas_Moldura_Branca", (0.85, 0.87, 0.86, 1.0))
    mat_porta = material("Aberturas_Porta_Madeira", (0.34, 0.20, 0.13, 1.0))
    mat_vidro = material("Aberturas_Vidro", (0.38, 0.65, 0.73, 0.25), transparencia=True)

    for abertura, along_global in zip(aberturas, centros):
        parede = paredes[abertura["parede"]]
        abrir_vao(parede, abertura, along_global)
        criar_elementos(abertura, parede, along_global, coll, mat_moldura, mat_porta, mat_vidro)
        print(f"[OK] {abertura['nome']}: parede={abertura['parede']} "
              f"centro_ao_longo={abertura['centro_ao_longo']:.3f} m; "
              f"largura={abertura['largura']:.3f} m; "
              f"base_z={abertura['base_z']:.3f} m; altura={abertura['altura']:.3f} m")

    bpy.context.scene.unit_settings.system = "METRIC"
    bpy.context.scene.unit_settings.scale_length = 1.0
    saida = args.saida.expanduser().resolve()
    if Path(bpy.data.filepath).resolve() == saida:
        raise ValueError("Saida nao pode ser igual ao arquivo de entrada.")
    saida.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=str(saida))
    print(f"[OK] Salvo em: {saida}")
    print("[OK] Objetos das cameras foram preservados.")


if __name__ == "__main__":
    main()
