import os
import re
import requests
from urllib.parse import quote

# Suposición: nb_get y nb_post ya definidas, restituyen JSON/dict
API_TREE_URL = (
    "https://api.github.com/repos/netbox-community/devicetype-library"
    "/git/trees/master?recursive=1"
)
DRY = False  # DRY-run global

def ensure_slug(endpoint, slug):
    return slug

def resolve_device_type(device: dict) -> tuple[str, str]:
    vendor = (device.get("vendor") or device.get("os") or "generic").lower().strip()
    model = (device.get("hardware") or device.get("model") or device.get("type") or "").strip()
    slug = re.sub(r"[\s_]+", "-", model.lower())
    slug = re.sub(r"[^a-z0-9\-]", "", slug)
    return vendor, slug

def fetch_tree() -> list[str]:
    try:
        resp = requests.get(API_TREE_URL, timeout=20)
        resp.raise_for_status()
        data = resp.json()
        return [item["path"] for item in data.get("tree", []) if item.get("path","").endswith(".yaml")]
    except Exception as e:
        print(f"ERROR obteniendo árbol de device-types: {e}")
        return []

TREE = fetch_tree()
print(f"[DEBUG] TREE cargado: {len(TREE)} paths")   # <-- Añade esto temporalmente

def find_in_tree(vendor: str, slug: str) -> tuple[str | None, list[str]]:
    """
    Busca la ruta exacta en el árbol. Si no hay exact match, devuelve sugerencias.
    Retorna (ruta, lista_sugerencias).
    """
    exact = f"{vendor}/{slug}.yaml"
    if exact in TREE:
        return exact, []

    # Scoped fuzzy dentro de la carpeta del vendor
    suggestions = []
    prefix = f"{vendor}/"
    for path in TREE:
        if path.startswith(prefix) and slug in os.path.basename(path):
            suggestions.append(path)
    if suggestions:
        return None, suggestions

    # Global fuzzy
    suggestions = [p for p in TREE if slug in os.path.basename(p)]
    return None, suggestions[:5]

def validate_device(d: dict) -> bool:
    return bool(d.get("device_id") and (d.get("hostname") or d.get("sysName")))

def get_or_create_manufacturer_id(slug: str) -> int:
    slug = ensure_slug("dcim/manufacturers/", slug)
    resp = nb_get("dcim/manufacturers/", slug=slug)
    if resp.get("count", 0) > 0:
        return resp["results"][0]["id"]
    data = {"name": slug.capitalize(), "slug": slug}
    created = nb_post("dcim/manufacturers/", data)
    return created.get("id")

def get_or_create_generic_device_type():
    from api_netbox import get_or_create_manufacturer_id
    man_id = get_or_create_manufacturer_id("generic")
    data = {
        "manufacturer": man_id,
        "model": "generic",
        "slug": "generic"
    }
    if DRY:
        print("DRY-IMPORT GENERIC", data)
        return 0
    try:
        created = nb_post("dcim/device-types/", data)
        return created.get("id")
    except Exception as e:
        print(f"ERROR al crear device-type generico: {e}")
        return None

if __name__ == "__main__":
    device = {"os": "Synology", "hardware": "DS420+", "device_id": 9, "hostname": "10.0.0.75"}
    if not validate_device(device):
        print("Dispositivo inválido")
        import sys; sys.exit(1)

    vendor, slug_key = resolve_device_type(device)
    relpath, suggestions = find_in_tree(vendor, slug_key)
    print(f"[DEBUG] find_in_tree -> relpath={relpath}, suggestions={suggestions[:3]} (total {len(suggestions)})")
    if relpath:
        print(f"Ruta encontrada: {relpath}")
    else:
        print(f"No encontrado '{slug_key}'. Sugerencias:")
        for i, s in enumerate(suggestions, 1):
            print(f"{i}. {s}")
        device_type_id = get_or_create_generic_device_type()
        print(f"Generic Device-Type ID: {device_type_id}")
    man_id = get_or_create_manufacturer_id(vendor)
    print(f"Manufacturer ID: {man_id}")
