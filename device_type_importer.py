import re
import os
import yaml
import requests

from api_netbox import nb_get, nb_post, get_or_create_manufacturer_id
from device_utils import find_in_tree, TREE
from config import DRY_RUN

DRY = DRY_RUN

def create_generic_device_type():
    """Crea un device-type genérico si no existe"""
    man_id = get_or_create_manufacturer_id("generic")
    
    # Verificar si ya existe
    check = nb_get(
        "dcim/device-types/",
        manufacturer_id=man_id,
        slug="generic",
    )
    if check.get("count", 0):
        print(f"[DEBUG] Device-type genérico ya existe: id={check['results'][0]['id']}")
        return check["results"][0]["id"]
    
    # Crear nuevo device-type genérico
    data = {"manufacturer": man_id, "model": "Generic Device", "slug": "generic"}
    if DRY:
        print("[DEBUG] DRY-IMPORT GENERIC", data)
        return 1  # Retornar un ID ficticio pero válido
    
    try:
        created = nb_post("dcim/device-types/", data)
        print(f"[DEBUG] Device-type genérico creado: {created}")
        return created.get("id")
    except Exception as e:
        print(f"ERROR al crear device-type genérico: {e}")
        return None

def normalize_slug(text: str) -> str:
    """Normaliza un texto para crear un slug válido"""
    if not text:
        return ""
    # Convertir a minúsculas y reemplazar espacios/guiones bajos con guiones
    text = text.lower().strip()
    text = re.sub(r'[\s_]+', '-', text)
    # Reemplazar caracteres especiales
    text = text.replace('+', '-plus')
    # Eliminar caracteres que no sean alfanuméricos o guiones
    text = re.sub(r'[^a-z0-9\-]', '', text)
    # Eliminar guiones múltiples y guiones al inicio/final
    text = re.sub(r'-+', '-', text).strip('-')
    return text

def import_device_type_if_exists(vendor: str, fname: str):
    vendor = normalize_slug(vendor)
    slug_key = normalize_slug(fname)
    print(f"[DEBUG] import_device_type_if_exists: vendor='{vendor}', slug_key='{slug_key}'")
    
    if not vendor or not slug_key:
        print(f"[DEBUG] Vendor o modelo vacío ({vendor}, {slug_key})")
        return None
    
    if not TREE:
        print(f"[DEBUG] Árbol vacío, creando device-type genérico")
        # Si no hay árbol, crear directamente un tipo genérico
        return create_generic_device_type()

    # Comprueba en NetBox
    q = nb_get("dcim/device-types/", slug=slug_key)
    if q.get("count", 0):
        print(f"[DEBUG] Device-type {slug_key} ya existe en NetBox id={q['results'][0]['id']}")
        return q["results"][0]["id"]

    # Busca ruta exacta o sugiere alternativas
    relpath, suggestions = find_in_tree(vendor, slug_key)
    # Nos quedamos con un máximo de 4 sugerencias
    suggestions = suggestions[:4]
    print(
        f"[DEBUG] find_in_tree -> relpath={relpath}, suggestions={suggestions} (total {len(suggestions)})"
    )

    if not relpath:
        if suggestions:
            print(f"No encontró '{slug_key}'. Sugerencias:")
            for idx, path in enumerate(suggestions, 1):
                print(f"  {idx}) {path}")
            gen_idx = len(suggestions) + 1
            print(f"  {gen_idx}) [GENÉRICO] Crear tipo de dispositivo genérico")
            choice = input(f"Elige número (1-{gen_idx}) o ENTER para saltar: ")
            
            if choice.isdigit():
                sel = int(choice) - 1
                if 0 <= sel < len(suggestions):
                    relpath = suggestions[sel]
                    print(f"[DEBUG] Sugerencia seleccionada: {relpath}")
                elif sel == len(suggestions):
                    print("[DEBUG] Opción genérica seleccionada.")
                    relpath = None
                else:
                    print("[DEBUG] Selección fuera de rango, saltando.")
                    return None
            else:
                print("[DEBUG] No se seleccionó ninguna opción. Saltando.")
                return None
        else:
            print(f"[DEBUG] Sin sugerencias para '{slug_key}'. Dispositivo saltado.")
            return None

    # Si relpath es None tras confirmar genérico, creamos genérico
    if not relpath:
        return create_generic_device_type()

    # Importar device-type real
    url = f"https://raw.githubusercontent.com/netbox-community/devicetype-library/master/{relpath}"
    print(f"[DEBUG] Intentando descargar device-type desde: {url}")
    
    raw_data = None
    for attempt in range(5):
        try:
            print(f"[DEBUG] Descarga intento {attempt+1}")
            resp = requests.get(url, timeout=20)
            if resp.status_code == 200:
                print(f"[DEBUG] Descarga OK")
                raw_data = yaml.safe_load(resp.text)
                break
            else:
                print(f"[DEBUG] HTTP {resp.status_code}")
        except requests.RequestException as e:
            print(f"[DEBUG] Error conexión GitHub: {e}")
    
    if raw_data is None:
        print(f"[DEBUG] No se pudo descargar {url} tras 5 intentos")
        return None

    # Preparar datos para crear device-type
    vendor_from_path = relpath.split("/")[1]
    man_id = get_or_create_manufacturer_id(vendor_from_path)
    filename = os.path.basename(relpath)
    base = filename[:-5]  # Quitar .yaml
    tmp = base.replace("+", "-plus")
    tmp = re.sub(r"[\s_]+", "-", tmp)
    clean_slug = re.sub(r"[^a-zA-Z0-9\-]", "", tmp).lower().strip("-")
    model = raw_data.get("model") or base
    
    data = {"manufacturer": man_id, "model": model, "slug": clean_slug}
    print(f"[DEBUG] Crear device-type con: {data}")
    
    if DRY:
        print("[DEBUG] DRY-IMPORT", data)
        return 0
    
    try:
        created = nb_post("dcim/device-types/", data)
        print(f"[DEBUG] Device-type creado en NetBox: {created}")
        return created.get("id")
    except Exception as e:
        print(f"ERROR al crear device-type {clean_slug}: {e}")
        return None
