"""Captura um conjunto de quatro frames reais e salva originais e ROI corrigidas.

Execute na rede do LabSEA:
    python scripts/cameras/capturar_imagens.py

Para processar arquivos previamente capturados, sem acessar o broker:
    python scripts/cameras/capturar_imagens.py --originais-dir /caminho/para/imagens
"""

import argparse
from collections import deque
from dataclasses import dataclass
from datetime import datetime, timezone
from itertools import product
import json
import os
from pathlib import Path
import re
import socket
import time

import cv2
import numpy as np
from is_msgs.image_pb2 import Image
from is_wire.core import Subscription

from camera_utils import BROKER_URI, CALIBRACOES, SAIDA, StreamChannel, recortar_roi


CAMERAS = (1, 2, 3, 4)
TOPICO = re.compile(r"CameraGateway\.([1-4])\.Frame")


@dataclass
class Frame:
    camera_id: int
    imagem: np.ndarray
    recebido_em: float
    origem_em: float | None = None
    sequencia: int | None = None


def instante_da_imagem(imagem):
    if imagem.HasField("header") and imagem.header.HasField("stamp"):
        stamp = imagem.header.stamp
        if stamp.seconds > 0:
            return float(stamp.seconds) + float(stamp.nanos) / 1_000_000_000
    return None


def escolher_conjunto(filas):
    """Escolhe os quatro frames com menor intervalo temporal observado."""
    if any(not filas.get(camera_id) for camera_id in CAMERAS):
        return None

    com_origem = [
        [frame for frame in filas[camera_id] if frame.origem_em is not None]
        for camera_id in CAMERAS
    ]
    if all(com_origem):
        candidatos = com_origem
        atributo = "origem_em"
    else:
        candidatos = [filas[camera_id] for camera_id in CAMERAS]
        atributo = "recebido_em"

    melhor = min(
        product(*candidatos),
        key=lambda grupo: (
            max(getattr(frame, atributo) for frame in grupo)
            - min(getattr(frame, atributo) for frame in grupo),
            -max(getattr(frame, atributo) for frame in grupo),
        ),
    )
    tempos = [getattr(frame, atributo) for frame in melhor]
    return dict(zip(CAMERAS, melhor)), atributo, max(tempos) - min(tempos)


def capturar(broker, tempo_limite, diferenca_maxima):
    filas = {camera_id: deque(maxlen=8) for camera_id in CAMERAS}
    canal = None
    try:
        canal = StreamChannel(uri=broker)
        inscricao = Subscription(canal)
        for camera_id in CAMERAS:
            inscricao.subscribe(f"CameraGateway.{camera_id}.Frame")

        prazo = time.monotonic() + tempo_limite
        while time.monotonic() < prazo:
            try:
                mensagem = canal.consume(timeout=min(0.5, max(0.0, prazo - time.monotonic())))
            except (socket.timeout, TimeoutError):
                continue

            topico = TOPICO.fullmatch(mensagem.topic)
            if topico is None:
                continue
            camera_id = int(topico.group(1))
            imagem_pb = mensagem.unpack(Image)
            frame = cv2.imdecode(np.frombuffer(imagem_pb.data, dtype=np.uint8), cv2.IMREAD_COLOR)
            if frame is None or frame.size == 0:
                print(f"[AVISO] Frame inválido da câmera {camera_id}; ignorado.")
                continue

            filas[camera_id].append(Frame(
                camera_id=camera_id,
                imagem=frame,
                recebido_em=time.time(),
                origem_em=instante_da_imagem(imagem_pb),
                sequencia=int(imagem_pb.sequence),
            ))
            conjunto = escolher_conjunto(filas)
            if conjunto is not None and conjunto[2] <= diferenca_maxima:
                return conjunto
    finally:
        if canal is not None:
            canal.close()

    conjunto = escolher_conjunto(filas)
    if conjunto is None:
        faltantes = [camera_id for camera_id in CAMERAS if not filas[camera_id]]
        raise TimeoutError(f"Sem frame das câmeras {faltantes} após {tempo_limite:.1f} s.")
    print(f"[AVISO] Melhor conjunto disponível tem intervalo de {conjunto[2]:.3f} s.")
    return conjunto


def carregar_arquivos(pasta):
    frames = {}
    for camera_id in CAMERAS:
        caminho = next((
            p for p in (pasta / f"camera_{camera_id}.png", pasta / f"camera_{camera_id}_original.png")
            if p.is_file()
        ), None)
        if caminho is None:
            raise FileNotFoundError(f"Falta camera_{camera_id}.png em {pasta}")
        imagem = cv2.imread(str(caminho), cv2.IMREAD_COLOR)
        if imagem is None:
            raise ValueError(f"Imagem inválida: {caminho}")
        frames[camera_id] = Frame(camera_id, imagem, caminho.stat().st_mtime)
    return frames, "arquivos_sem_sincronizacao", None


def calibracao(camera_id):
    caminho = CALIBRACOES / f"calib_rt{camera_id}.npz"
    with np.load(caminho, allow_pickle=False) as dados:
        K = dados["K"].copy()
        nK = dados["nK"].copy()
        dist = dados["dist"].copy()
        roi = dados["roi"].copy()
        width = int(dados["width"])
        height = int(dados["height"])
    return caminho, K, nK, dist, roi, width, height


def salvar(frames, metodo, intervalo, pasta):
    preparados = {}
    for camera_id in CAMERAS:
        frame = frames[camera_id]
        caminho, K, nK, dist, roi, width, height = calibracao(camera_id)
        if frame.imagem.shape[:2] != (height, width):
            raise ValueError(
                f"Câmera {camera_id}: imagem {frame.imagem.shape[1]}x{frame.imagem.shape[0]}, "
                f"calibração {width}x{height}."
            )
        corrigida = cv2.undistort(frame.imagem, K, dist, None, nK)
        preparados[camera_id] = (frame, recortar_roi(corrigida, roi), roi, caminho)

    if pasta.exists():
        raise FileExistsError(f"A pasta de captura já existe: {pasta}")
    (pasta / "originais").mkdir(parents=True)
    (pasta / "corrigidas_roi").mkdir()

    manifesto = {
        "observacao": "Estado observado nesta captura; cadeiras e outros objetos móveis podem mudar de posição.",
        "metodo_sincronizacao": metodo,
        "intervalo_entre_frames_s": intervalo,
        "cameras": {},
    }
    for camera_id, (frame, corrigida, roi, caminho_calibracao) in preparados.items():
        original = pasta / "originais" / f"camera_{camera_id}.png"
        saida_corrigida = pasta / "corrigidas_roi" / f"camera_{camera_id}.png"
        if not cv2.imwrite(str(original), frame.imagem):
            raise OSError(f"Não foi possível salvar {original}")
        if not cv2.imwrite(str(saida_corrigida), corrigida):
            raise OSError(f"Não foi possível salvar {saida_corrigida}")
        manifesto["cameras"][str(camera_id)] = {
            "topico": f"CameraGateway.{camera_id}.Frame",
            "calibracao": str(caminho_calibracao.relative_to(CALIBRACOES.parent.parent)),
            "sequencia": frame.sequencia,
            "timestamp_origem_utc": datetime.fromtimestamp(frame.origem_em, timezone.utc).isoformat() if frame.origem_em else None,
            "recebido_em_utc": datetime.fromtimestamp(frame.recebido_em, timezone.utc).isoformat(),
            "roi_xywh": [int(v) for v in roi],
            "resolucao_original_wh": [frame.imagem.shape[1], frame.imagem.shape[0]],
            "resolucao_corrigida_wh": [corrigida.shape[1], corrigida.shape[0]],
        }
    (pasta / "manifesto.json").write_text(json.dumps(manifesto, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return pasta


def argumentos():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--broker", default=os.environ.get("LABSEA_BROKER_URI", BROKER_URI))
    parser.add_argument("--timeout", type=float, default=20.0, help="Tempo máximo de captura em segundos")
    parser.add_argument("--max-diferenca", type=float, default=0.5,
                        help="Intervalo máximo desejado entre frames em segundos")
    parser.add_argument("--originais-dir", type=Path,
                        help="Processar camera_1.png a camera_4.png desta pasta sem usar o broker")
    parser.add_argument("--saida", type=Path,
                        help="Pasta nova de destino; padrão: saida/imagens_reais/data-hora")
    args = parser.parse_args()
    if args.timeout <= 0 or args.max_diferenca < 0:
        parser.error("--timeout deve ser positivo e --max-diferenca não pode ser negativo")
    return args


def main():
    args = argumentos()
    pasta = args.saida or (SAIDA / "imagens_reais" / datetime.now().strftime("%Y%m%d_%H%M%S"))
    if args.originais_dir:
        conjunto = carregar_arquivos(args.originais_dir.expanduser().resolve())
    else:
        conjunto = capturar(args.broker, args.timeout, args.max_diferenca)
    destino = salvar(*conjunto, pasta.expanduser().resolve())
    print(f"[OK] Quatro imagens originais e corrigidas salvas em {destino}")


if __name__ == "__main__":
    main()
