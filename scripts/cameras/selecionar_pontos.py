import cv2
import numpy as np

from camera_utils import CALIBRACOES, StreamChannel, broker_uri, decodificar_imagem, recortar_roi
from is_wire.core import Subscription

CAMERA_IDS = (1, 2)

MAX_WIDTH = 770
MAX_HEIGHT = 750


def undistort_image(frame, calib_params):

    K = calib_params["K"]
    dist = calib_params["dist"]
    nK = calib_params["nK"]
    roi = calib_params["roi"]

    undistorted = cv2.undistort(
        frame, K, dist, None, nK
    )

    return recortar_roi(undistorted, roi)


def compute_ground_homography(calib_params):

    rt = calib_params["rt"]
    nK = calib_params["nK"]

    r1 = rt[:3, 0]
    r2 = rt[:3, 1]
    t = rt[:3, 3]

    H = nK @ np.column_stack((r1, r2, t))

    return H


def compute_roi_homography(calib_params):

    H = compute_ground_homography(calib_params)

    x_roi, y_roi, _, _ = map(
        int, np.asarray(calib_params["roi"]).reshape(-1)
    )

    T_roi = np.array([
        [1, 0, -x_roi],
        [0, 1, -y_roi],
        [0, 0, 1]
    ], dtype=np.float64)

    return T_roi @ H


def pixel_to_world(u, v, H):

    pixel_h = np.array([u, v, 1.0], dtype=np.float64)

    point_h = np.linalg.solve(H, pixel_h)

    if abs(point_h[2]) < 1e-12:
        raise ValueError("Raio paralelo ao plano do chão.")

    point_h /= point_h[2]

    return np.array([
        point_h[0],
        point_h[1],
        0.0
    ])


def resize_to_screen(frame):

    h, w = frame.shape[:2]

    scale = min(
        MAX_WIDTH / w,
        MAX_HEIGHT / h,
        1.0
    )

    new_w = max(1, round(w * scale))
    new_h = max(1, round(h * scale))

    return cv2.resize(frame, (new_w, new_h))


def click_event(event, x, y, flags, params):

    if event != cv2.EVENT_LBUTTONDOWN:
        return

    states = params["states"]
    cam_id = params["cam_id"]

    state = states[cam_id]

    if state["frame"] is None:
        return

    # Converter clique da janela redimensionada
    # para coordenadas da imagem ROI original
    h, w = state["frame"].shape[:2]
    display_w, display_h = state["display_size"]

    u = min(w - 1, max(0, round(x * w / display_w)))
    v = min(h - 1, max(0, round(y * h / display_h)))

    H_roi = state["H_roi"]

    try:
        point_world = pixel_to_world(u, v, H_roi)
    except (ValueError, np.linalg.LinAlgError) as exc:
        print(f"Erro na câmera {cam_id}: {exc}")
        return

    state["pixel"] = (u, v)
    state["point"] = point_world

    print(f"\n--- Câmera {cam_id} ---")
    print(f"Pixel: ({u}, {v})")
    print(f"Coordenada mundo: {point_world}")

    # Comparar quando ambas possuírem um ponto
    point_cam1 = states[1]["point"]
    point_cam2 = states[2]["point"]

    if point_cam1 is not None and point_cam2 is not None:

        error = np.linalg.norm(point_cam1 - point_cam2)

        print("\n--- COMPARAÇÃO ---")
        print(f"Câmera 1: {point_cam1}")
        print(f"Câmera 2: {point_cam2}")
        print(f"Diferença entre câmeras: {error * 100:.2f} cm")


def main():

    states = {}
    channels = {}
    subscriptions = {}

    for cam_id in CAMERA_IDS:

        calib_path = CALIBRACOES / f"calib_rt{cam_id}.npz"

        with np.load(calib_path) as data:
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

        H_roi = compute_roi_homography(calib_params)

        states[cam_id] = {
            "calib": calib_params,
            "calib_size": calib_size,
            "H_roi": H_roi,
            "frame": None,
            "display_size": None,
            "pixel": None,
            "point": None,
            "window": f"Camera {cam_id}"
        }

        # Um canal por câmera
        channel = StreamChannel(uri=broker_uri())
        subscription = Subscription(channel)

        subscription.subscribe(
            f"CameraGateway.{cam_id}.Frame"
        )

        channels[cam_id] = channel
        subscriptions[cam_id] = subscription

        window_name = states[cam_id]["window"]

        cv2.namedWindow(
            window_name,
            cv2.WINDOW_AUTOSIZE
        )

        cv2.moveWindow(
            window_name,
            20 + (cam_id - 1) * 800,
            50
        )

        cv2.setMouseCallback(
            window_name,
            click_event,
            {
                "states": states,
                "cam_id": cam_id
            }
        )

    print("Clique na mesma marcação do chão nas duas câmeras.")
    print("Pressione C para limpar os pontos.")
    print("Pressione Q para sair.")

    try:

        while True:

            for cam_id in CAMERA_IDS:

                state = states[cam_id]

                msg_rcv = channels[cam_id].consume_last()

                if not isinstance(msg_rcv, bool) and msg_rcv is not None:

                    frame = decodificar_imagem(msg_rcv)

                    if frame is not None and frame.size > 0:

                        if state["calib_size"] is not None:
                            expected = state["calib_size"]
                            received = (frame.shape[1], frame.shape[0])

                            if received != expected:
                                raise ValueError(
                                    f"Câmera {cam_id}: resolução "
                                    f"{received}, calibração {expected}"
                                )

                        state["frame"] = undistort_image(
                            frame,
                            state["calib"]
                        )

                if state["frame"] is None:
                    continue

                display = resize_to_screen(
                    state["frame"].copy()
                )

                dh, dw = display.shape[:2]
                state["display_size"] = (dw, dh)

                # Desenhar ponto selecionado
                if state["pixel"] is not None:

                    u, v = state["pixel"]

                    h, w = state["frame"].shape[:2]

                    px = round(u * dw / w)
                    py = round(v * dh / h)

                    cv2.circle(
                        display,
                        (px, py),
                        6,
                        (0, 0, 255),
                        -1
                    )

                    point = state["point"]

                    cv2.putText(
                        display,
                        f"X={point[0]:.3f} Y={point[1]:.3f}",
                        (10, 30),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        0.6,
                        (0, 255, 0),
                        2
                    )

                cv2.imshow(
                    state["window"],
                    display
                )

            key = cv2.waitKey(1) & 0xFF

            if key == ord("q"):
                break

            elif key == ord("c"):
                for state in states.values():
                    state["point"] = None
                    state["pixel"] = None

                print("\nPontos limpos.")

    finally:
        cv2.destroyAllWindows()

        for state in states.values():
            state["frame"] = None


if __name__ == "__main__":
    main()
