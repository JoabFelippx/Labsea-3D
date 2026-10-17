import argparse

from camera_utils import CALIBRACOES, StreamChannel, broker_uri, decodificar_imagem
from geometria import PAREDES
from is_wire.core import Subscription

import numpy as np
import cv2


def get_wall_points(name, wall, n_points=100):

    cx, cy = wall["center"]
    length = wall["len"]

    if name in ("east", "west"):
        p1 = np.array([cx, cy - length / 2, 0])
        p2 = np.array([cx, cy + length / 2, 0])

    else:
        p1 = np.array([cx - length / 2, cy, 0])
        p2 = np.array([cx + length / 2, cy, 0])

    t = np.linspace(0, 1, n_points)

    points = p1 + t[:, None] * (p2 - p1)

    return points.astype(np.float64)


def draw_walls(frame, walls_params, calib_params):

    rt = calib_params["rt"]
    K = calib_params["K"]
    dist = calib_params["dist"]

    R = rt[:3, :3]
    t = rt[:3, 3]

    rvec, _ = cv2.Rodrigues(R)

    colors = {
        "north": (0, 0, 255),
        "south": (0, 255, 0),
        "east": (255, 0, 0),
        "west": (0, 255, 255)
    }

    for name, wall in walls_params.items():

        points_3d = get_wall_points(name, wall)

        # Coordenadas no referencial da câmera
        points_cam = (R @ points_3d.T).T + t

        # Pontos à frente da câmera
        valid = points_cam[:, 2] > 0.05

        # Projetar os pontos 3D para pixels
        points_2d, _ = cv2.projectPoints(
            points_3d,
            rvec,
            t,
            K,
            dist
        )

        points_2d = points_2d.reshape(-1, 2)

        # Desenhar segmentos consecutivos
        for i in range(len(points_2d) - 1):

            if not (valid[i] and valid[i + 1]):
                continue

            p1 = points_2d[i]
            p2 = points_2d[i + 1]

            if not np.all(np.isfinite([p1, p2])):
                continue

            if np.max(np.abs([p1, p2])) > 1e7:
                continue

            p1 = tuple(np.round(p1).astype(int))
            p2 = tuple(np.round(p2).astype(int))

            cv2.line(
                frame,
                p1,
                p2,
                colors[name],
                2
            )

    return frame


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--cam", type=int, choices=(1, 2, 3, 4), default=1)
    cam_id = parser.parse_args().cam
    camera_topico = f"CameraGateway.{cam_id}.Frame"

    with np.load(
        CALIBRACOES / f"calib_rt{cam_id}.npz"
    ) as data:
        calib_params = {
            key: data[key].copy()
            for key in ("K", "dist", "rt")
        }

    channel = StreamChannel(uri=broker_uri())
    subscription = Subscription(channel)
    subscription.subscribe(camera_topico)

    while True:

        msg_rcv = channel.consume_last()

        if isinstance(msg_rcv, bool):
            continue

        frame = decodificar_imagem(msg_rcv)

        if frame is None or frame.size == 0:
            continue

        frame = draw_walls(
            frame,
            PAREDES,
            calib_params
        )

        cv2.imshow("Paredes projetadas", frame)

        key = cv2.waitKey(1)

        if key & 0xFF == ord("q"):
            break

    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
