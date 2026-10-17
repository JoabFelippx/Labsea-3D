import argparse
from pathlib import Path

import cv2
import matplotlib.pyplot as plt


def main():
    raiz = Path(__file__).resolve().parents[2]
    parser = argparse.ArgumentParser(description="Gera um grid 2×2 dos quatro renders")
    parser.add_argument("--imagens-dir", type=Path,
                        default=raiz / "saida" / "imagens_sinteticas")
    parser.add_argument("--saida", type=Path,
                        help="Caminho PNG; padrão: grid_cameras.png na pasta de imagens")
    args = parser.parse_args()
    image_dir = args.imagens_dir.expanduser().resolve()
    output_path = (args.saida or image_dir / "grid_cameras.png").expanduser().resolve()

    fig, axes = plt.subplots(2, 2, figsize=(16, 12))
    for ax in axes.flat:
        ax.axis("off")
    for cam_id in range(1, 5):
        image_path = image_dir / f"camera_{cam_id}.png"
        image = cv2.imread(str(image_path))
        if image is None:
            raise FileNotFoundError(image_path)
        ax = axes.flat[cam_id - 1]
        ax.imshow(cv2.cvtColor(image, cv2.COLOR_BGR2RGB))
        ax.set_title(f"Câmera {cam_id}")

    fig.tight_layout()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path, dpi=200, bbox_inches="tight")
    plt.close(fig)
    print(f"Grid salvo em: {output_path}")


if __name__ == "__main__":
    main()
