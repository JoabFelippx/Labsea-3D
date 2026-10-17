"""Compara um lote real corrigido com quatro renders calibrados.

Exemplo:
    python scripts/cameras/comparar_capturas.py \
        --captura saida/imagens_reais/20261014_120000 \
        --sinteticas saida/imagens_sinteticas
"""

import argparse
import json
from pathlib import Path

import cv2
import numpy as np

from camera_utils import CALIBRACOES, SAIDA, recortar_roi


def ler_calibracao(camera_id):
    with np.load(CALIBRACOES / f"calib_rt{camera_id}.npz", allow_pickle=False) as dados:
        return int(dados["width"]), int(dados["height"]), dados["roi"].copy()


def preparar_par(camera_id, captura, sinteticas):
    real_path = captura / "corrigidas_roi" / f"camera_{camera_id}.png"
    sint_path = sinteticas / f"camera_{camera_id}.png"
    real = cv2.imread(str(real_path), cv2.IMREAD_COLOR)
    sint = cv2.imread(str(sint_path), cv2.IMREAD_COLOR)
    if real is None:
        raise FileNotFoundError(real_path)
    if sint is None:
        raise FileNotFoundError(sint_path)

    width, height, roi = ler_calibracao(camera_id)
    x, y, roi_width, roi_height = map(int, roi)
    if real.shape[:2] != (roi_height, roi_width):
        raise ValueError(f"Câmera {camera_id}: a imagem real não tem o tamanho do ROI {roi_width}x{roi_height}.")
    if sint.shape[:2] == (height, width):
        sint = recortar_roi(sint, roi)
    elif sint.shape[:2] != real.shape[:2]:
        raise ValueError(f"Câmera {camera_id}: render com resolução incompatível {sint.shape[:2]}.")
    return real, sint, [x, y, roi_width, roi_height]


def comparar(real, sint):
    erro_medio = float(np.mean(cv2.absdiff(real, sint)))
    cinza_real = cv2.cvtColor(real, cv2.COLOR_BGR2GRAY)
    cinza_sint = cv2.cvtColor(sint, cv2.COLOR_BGR2GRAY)
    bordas_reais = cv2.Canny(cinza_real, 80, 160) > 0
    bordas_sint = cv2.Canny(cinza_sint, 80, 160) > 0
    vizinhanca = np.ones((7, 7), np.uint8)
    perto_real = cv2.dilate(bordas_reais.astype(np.uint8), vizinhanca) > 0
    perto_sint = cv2.dilate(bordas_sint.astype(np.uint8), vizinhanca) > 0
    precisao = float(np.count_nonzero(bordas_sint & perto_real) / max(1, np.count_nonzero(bordas_sint)))
    revocacao = float(np.count_nonzero(bordas_reais & perto_sint) / max(1, np.count_nonzero(bordas_reais)))
    f1 = 2 * precisao * revocacao / (precisao + revocacao) if precisao + revocacao else 0.0
    return {
        "erro_medio_cor_0_255": round(erro_medio, 3),
        "precisao_bordas_3px": round(precisao, 4),
        "revocacao_bordas_3px": round(revocacao, 4),
        "f1_bordas_3px": round(f1, 4),
        "real_fracao_pixels_canais_acima_250": round(float(np.mean(np.all(real>=250,axis=2))),5),
        "sintetica_fracao_pixels_canais_acima_250": round(float(np.mean(np.all(sint>=250,axis=2))),5),
    }


def comparar_piso(camera_id, real, sint):
    """Região central livre, em Z=0; comparação fotométrica, não geometria."""
    with np.load(CALIBRACOES/f'calib_rt{camera_id}.npz',allow_pickle=False) as c:
        world=np.array([[-1.4,-2.3,0,1],[1.4,-2.3,0,1],[1.4,1.7,0,1],[-1.4,1.7,0,1]])
        p=world@(c['nK']@c['rt'][:3]).T
        uv=p[:,:2]/p[:,2:3]-c['roi'][:2]
    mask=np.zeros(real.shape[:2],np.uint8)
    cv2.fillConvexPoly(mask,np.rint(uv).astype(np.int32),1)
    gray_r=cv2.cvtColor(real,cv2.COLOR_BGR2GRAY)[mask>0]
    gray_s=cv2.cvtColor(sint,cv2.COLOR_BGR2GRAY)[mask>0]
    return {'piso_mediana_real_0_255':float(np.median(gray_r)),
            'piso_mediana_sintetica_0_255':float(np.median(gray_s))}


def rotular(imagem, texto):
    saida = imagem.copy()
    cv2.rectangle(saida, (0, 0), (min(saida.shape[1], 185), 40), (20, 20, 20), -1)
    cv2.putText(saida, texto, (12, 28), cv2.FONT_HERSHEY_SIMPLEX, 0.68,
                (240, 240, 240), 2, cv2.LINE_AA)
    return saida


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--captura", type=Path, required=True,
                        help="Pasta produzida por capturar_imagens.py")
    parser.add_argument("--sinteticas", type=Path,
                        default=SAIDA / "imagens_sinteticas")
    parser.add_argument("--saida", type=Path,
                        help="Pasta de saída; padrão: saida/comparacoes/nome-da-captura")
    args = parser.parse_args()
    captura = args.captura.expanduser().resolve()
    sinteticas = args.sinteticas.expanduser().resolve()
    saida = (args.saida or SAIDA / "comparacoes" / captura.name).expanduser().resolve()
    saida.mkdir(parents=True, exist_ok=True)

    resultado = {
        "captura": str(captura),
        "sinteticas": str(sinteticas),
        "observacao": "Métricas de pixel/borda são auxiliares; móveis dinâmicos e luz podem causar diferenças sem erro de calibração.",
        "cameras": {},
    }
    for camera_id in range(1, 5):
        real, sint, roi = preparar_par(camera_id, captura, sinteticas)
        metricas = comparar(real, sint)
        metricas.update(comparar_piso(camera_id,real,sint))
        resultado["cameras"][str(camera_id)] = {"roi_xywh": roi, **metricas}
        lado_a_lado = cv2.hconcat((rotular(real, "REAL / ROI"), rotular(sint, "SINTETICA / ROI")))
        diferenca = cv2.absdiff(real, sint)
        if not cv2.imwrite(str(saida / f"camera_{camera_id}_comparison.png"), lado_a_lado):
            raise OSError(f"Erro ao salvar comparação da câmera {camera_id}")
        if not cv2.imwrite(str(saida / f"camera_{camera_id}_diff.png"), diferenca):
            raise OSError(f"Erro ao salvar diferença da câmera {camera_id}")
        print(f"Câmera {camera_id}: F1 bordas={metricas['f1_bordas_3px']:.3f}, erro cor={metricas['erro_medio_cor_0_255']:.1f}")

    (saida / "metricas.json").write_text(json.dumps(resultado, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"[OK] Comparações salvas em {saida}")


if __name__ == "__main__":
    main()
