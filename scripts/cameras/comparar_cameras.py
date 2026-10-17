import argparse

import cv2
import numpy as np

from camera_utils import CALIBRACOES, SAIDA, StreamChannel, broker_uri, decodificar_imagem, recortar_roi
from is_wire.core import Subscription

# Limites da janela no monitor de 1660x900
MAX_DISPLAY_WIDTH = 1280
MAX_DISPLAY_HEIGHT = 720


def world_to_pixel(point_3D, calib_params):

    rt = calib_params["rt"]
    nK = calib_params["nK"]
    roi = calib_params["roi"]

    R = rt[:3, :3]
    t = rt[:3, 3]

    pt_cam = R @ point_3D + t

    if pt_cam[2] <= 0:
        return None

    pt_img = nK @ pt_cam

    u = pt_img[0] / pt_img[2]
    v = pt_img[1] / pt_img[2]

    # Corrigir deslocamento do ROI
    x_roi, y_roi, _, _ = roi

    u -= x_roi
    v -= y_roi

    return u, v

def undistort_image(frame, calib_params):

    K = calib_params["K"]
    dist = calib_params["dist"]
    nK = calib_params["nK"]
    roi = calib_params["roi"]

    undistorted = cv2.undistort(
        frame,
        K,
        dist,
        None,
        nK
    )

    return recortar_roi(undistorted, roi)


def resize_to_screen(frame):

    h, w = frame.shape[:2]

    scale = min(
        MAX_DISPLAY_WIDTH / w,
        MAX_DISPLAY_HEIGHT / h,
        1.0
    )

    new_width = max(1, int(w * scale))
    new_height = max(1, int(h * scale))

    return cv2.resize(
        frame,
        (new_width, new_height),
        interpolation=cv2.INTER_AREA
    )


def create_comparison(real_frame, synthetic_frame):

    if real_frame.shape[:2] != synthetic_frame.shape[:2]:
        raise ValueError(
            "As imagens recortadas possuem resoluções diferentes: "
            f"{real_frame.shape[:2]} e {synthetic_frame.shape[:2]}"
        )

    real_view = real_frame.copy()
    synthetic_view = synthetic_frame.copy()

    cv2.putText(
        real_view,
        "REAL",
        (20, 40),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.8,
        (0, 255, 0),
        2
    )

    cv2.putText(
        synthetic_view,
        "SINTETICA",
        (20, 40),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.8,
        (0, 255, 0),
        2
    )

    comparison = cv2.hconcat([
        real_view,
        synthetic_view
    ])

    return resize_to_screen(comparison)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--cam", type=int, choices=(1, 2, 3, 4), default=4)
    cam_id = parser.parse_args().cam
    output_dir = SAIDA / "comparacao_cameras"
    output_dir.mkdir(parents=True, exist_ok=True)

    with np.load(CALIBRACOES / f"calib_rt{cam_id}.npz") as data:
        calib_params = {
            key: data[key].copy()
            for key in ("K", "dist", "nK", "roi", "rt")
        }

        calib_size = None
        if "width" in data and "height" in data:
            calib_size = (
                int(data["width"]),
                int(data["height"])
            )

    roi = calib_params["roi"]

    print(f"ROI: {roi}")

    synthetic_path = SAIDA / "imagens_sinteticas" / f"camera_{cam_id}.png"
    synthetic_frame = cv2.imread(str(synthetic_path))

    if synthetic_frame is None:
        raise FileNotFoundError(synthetic_path)

    channel = StreamChannel(uri=broker_uri())
    subscription = Subscription(channel)

    subscription.subscribe(f"CameraGateway.{cam_id}.Frame")

    window_name = f"Comparacao - Camera {cam_id}"

    cv2.namedWindow(window_name, cv2.WINDOW_AUTOSIZE)

    synthetic_cropped = None
    real_size = None

    print("S: salvar imagens")
    print("Q: sair")

    points_3d = np.array([
        [0.0, 0.0, 0],
    ])


    try:
        while True:

            msg_rcv = channel.consume_last()

            if isinstance(msg_rcv, bool):
                continue

            frame = decodificar_imagem(msg_rcv)

            if frame is None or frame.size == 0:
                continue

            h, w = frame.shape[:2]

            if calib_size is not None and (w, h) != calib_size:
                raise ValueError(
                    f"Resolução real {(w, h)} diferente da "
                    f"resolução de calibração {calib_size}"
                )

            # Preparar a imagem sintética uma única vez
            if synthetic_cropped is None:

                x, y, rw, rh = map(int, np.asarray(roi).reshape(-1))

                if synthetic_frame.shape[:2] == (h, w):
                    synthetic_cropped = recortar_roi(
                        synthetic_frame, roi
                    )

                elif synthetic_frame.shape[:2] == (rh, rw):
                    # Imagem já exportada com ROI
                    synthetic_cropped = synthetic_frame.copy()

                else:
                    raise ValueError(
                        "A imagem sintética precisa ter a resolução "
                        f"completa {(w, h)} ou a resolução ROI "
                        f"{(rw, rh)}. Recebido: "
                        f"{synthetic_frame.shape[1]}x"
                        f"{synthetic_frame.shape[0]}"
                    )

                print(
                    "Imagem sintética recortada:",
                    synthetic_cropped.shape
                )

            # Corrigir distorção e recortar
            real_undistorted = undistort_image(
                frame,
                calib_params
            )

            real_view = real_undistorted.copy()
            synthetic_view = synthetic_cropped.copy()
            for point_3d in points_3d:
                pixel = world_to_pixel(point_3d, calib_params)
                if pixel is None:
                    continue
                u, v = map(int, pixel)
                cv2.circle(real_view, (u, v), 5, (0, 0, 255), -1)
                cv2.circle(synthetic_view, (u, v), 5, (0, 0, 255), -1)
            
            # Criar visualização ajustada ao monitor
            comparison = create_comparison(
                real_view,
                synthetic_view
            )

            cv2.imshow(window_name, comparison)

            key = cv2.waitKey(1) & 0xFF

            if key == ord("s"):

                cv2.imwrite(
                    str(output_dir / f"camera_{cam_id}_original.png"),
                    frame
                )

                cv2.imwrite(
                    str(output_dir / f"camera_{cam_id}_undistorted_roi.png"),
                    real_view
                )

                cv2.imwrite(
                    str(output_dir / f"camera_{cam_id}_synthetic_roi.png"),
                    synthetic_view
                )

                cv2.imwrite(
                    str(output_dir / f"camera_{cam_id}_comparison.png"),
                    comparison
                )

                print("Imagens salvas!")

            elif key == ord("q"):
                break

    finally:
        cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
