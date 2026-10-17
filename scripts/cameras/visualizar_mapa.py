import numpy as np
import matplotlib.pyplot as plt
from pathlib import Path

from geometria import ALTURA_PAREDE, PAREDES


CALIBRACOES = Path(__file__).resolve().parents[2] / "dados" / "calibracao"

cameras_params = [
    np.load(CALIBRACOES / f"calib_rt{i}.npz")
    for i in range(1, 5)
]

fig = plt.figure(figsize=(10, 8))
ax = fig.add_subplot(111, projection="3d")

# Desenhar paredes
for name, wall in PAREDES.items():

    cx, cy = wall["center"]
    length = wall["len"]

    if name in ("east", "west"):
        x = np.array([
            [cx, cx],
            [cx, cx]
        ])

        y = np.array([
            [cy - length/2, cy + length/2],
            [cy - length/2, cy + length/2]
        ])

    else:
        x = np.array([
            [cx - length/2, cx + length/2],
            [cx - length/2, cx + length/2]
        ])

        y = np.array([
            [cy, cy],
            [cy, cy]
        ])

    z = np.array([
        [0, 0],
        [ALTURA_PAREDE, ALTURA_PAREDE]
    ])

    ax.plot_surface(
        x, y, z,
        alpha=0.5,
        edgecolor="black"
    )

    ax.text(cx, cy, ALTURA_PAREDE, name)


# Desenhar câmeras
colors = ["red", "blue", "green", "orange"]

for cam_id, camera_params in enumerate(cameras_params, start=1):

    rt_inv = camera_params["rt_inv"]

    camera_pos = rt_inv[:3, 3]

    ax.scatter(
        camera_pos[0],
        camera_pos[1],
        camera_pos[2],
        color=colors[cam_id - 1],
        s=25,
        label=f"Cam {cam_id}"
    )

    ax.text(
        camera_pos[0],
        camera_pos[1],
        camera_pos[2] + 0.1,
        f"Cam {cam_id}"
    )

    print(f"Cam {cam_id}: {camera_pos}")

    camera_params.close()


ax.set_xlabel("X (m)")
ax.set_ylabel("Y (m)")
ax.set_zlabel("Z (m)")

ax.set_xlim(-5, 5)
ax.set_ylim(-4, 4)
ax.set_zlim(0, ALTURA_PAREDE)

ax.set_box_aspect((10, 8, ALTURA_PAREDE))
ax.legend()

plt.show()
