"""Funções compartilhadas pelos scripts de câmeras reais."""

import os
from pathlib import Path
import socket

import cv2
import numpy as np
from is_msgs.image_pb2 import Image
from is_wire.core import Channel


RAIZ = Path(__file__).resolve().parents[2]
CALIBRACOES = RAIZ / "dados" / "calibracao"
SAIDA = RAIZ / "saida"
BROKER_URI = "amqp://guest:guest@10.10.50.176:30000"


def broker_uri():
    return os.environ.get("LABSEA_BROKER_URI", BROKER_URI)


def decodificar_imagem(mensagem):
    imagem = mensagem.unpack(Image)
    if isinstance(imagem, np.ndarray):
        return imagem
    buffer = np.frombuffer(imagem.data, dtype=np.uint8)
    return cv2.imdecode(buffer, cv2.IMREAD_COLOR)


def recortar_roi(frame, roi):
    x, y, largura, altura = map(int, np.asarray(roi).reshape(-1))
    altura_frame, largura_frame = frame.shape[:2]
    if largura <= 0 or altura <= 0:
        raise ValueError(f"ROI inválida: {roi}")
    if x < 0 or y < 0 or x + largura > largura_frame or y + altura > altura_frame:
        raise ValueError(f"ROI {roi} fora da imagem {(largura_frame, altura_frame)}")
    return frame[y:y + altura, x:x + largura]


class StreamChannel(Channel):
    def __init__(self, uri, exchange="is"):
        super().__init__(uri=uri, exchange=exchange)

    def consume_last(self, return_dropped=False):
        dropped = 0
        try:
            msg = super().consume(timeout=0.1)
        except socket.timeout:
            return False

        while True:
            try:
                msg = super().consume(timeout=0.0)
                dropped += 1
            except socket.timeout:
                return (msg, dropped) if return_dropped else msg
