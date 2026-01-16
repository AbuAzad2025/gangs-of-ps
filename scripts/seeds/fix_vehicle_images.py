from models.vehicle import Vehicle
from extensions import db
from factory import create_app
import os
import sys
import json
from pathlib import Path

sys.path.append(
    os.path.abspath(
        os.path.join(
            os.path.dirname(__file__),
            "..",
            "..")))


def _load_seed_vehicles():
    seed_path = Path(__file__).resolve(
    ).parents[2] / "data" / "seeds" / "vehicles.json"
    with seed_path.open("r", encoding="utf-8") as f:
        return json.load(f)


def _static_images_root():
    return Path(__file__).resolve().parents[2] / "static" / "images"


def _normalize_image_path(img: str | None) -> str:
    if not img:
        return ""
    img = img.strip().lstrip("/").replace("\\", "/")
    if img.startswith("static/"):
        img = img[len("static/"):]
    if img.startswith("images/"):
        img = img[len("images/"):]
    return img


def main():
    app = create_app()
    images_root = _static_images_root()
    seed = _load_seed_vehicles()
    by_name = {row["name"]: (row.get("image") or "") for row in seed}

    changed = 0
    missing_before = 0

    with app.app_context():
        vehicles = Vehicle.query.all()
        for v in vehicles:
            current = _normalize_image_path(v.image)
            desired = _normalize_image_path(by_name.get(v.name, "")) or current

            if not desired:
                desired = "vehicles/default.jpg"

            desired_path = images_root / desired
            if not desired_path.exists():
                missing_before += 1
                seed_img = _normalize_image_path(by_name.get(v.name, ""))
                if seed_img and (images_root / seed_img).exists():
                    desired = seed_img
                else:
                    desired = "vehicles/default.jpg"

            if _normalize_image_path(v.image) != desired:
                v.image = desired
                db.session.add(v)
                changed += 1

        db.session.commit()

    print("vehicle_images_fixed", changed)
    print("vehicles_missing_before_fix", missing_before)


if __name__ == "__main__":
    main()
