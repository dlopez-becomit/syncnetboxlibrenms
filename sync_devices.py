from api_librenms import get_librenms_devices, get_librenms_device_ports
from api_netbox import nb_get, nb_post, get_ip_address_id
from device_type_importer import import_device_type_if_exists
from device_utils import resolve_device_type, validate_device
from config import DEFAULT_SITE_SLUG, DEFAULT_ROLE_SLUG


def get_site_id(slug: str):
    resp = nb_get("dcim/sites/", slug=slug)
    if resp.get("count"):
        return resp["results"][0]["id"]
    raise ValueError(f"No existe el sitio: {slug}")


def get_role_id(slug: str):
    resp = nb_get("dcim/device-roles/", slug=slug)
    if resp.get("count"):
        return resp["results"][0]["id"]
    raise ValueError(f"No existe el role: {slug}")


def get_platform_id(slug: str | None):
    if not slug:
        return None
    resp = nb_get("dcim/platforms/", slug=slug)
    if resp.get("count"):
        return resp["results"][0]["id"]
    return None


def sync_devices():
    devices = get_librenms_devices()
    print(f"LibreNMS → {len(devices)} devices")
    try:
        site_id = get_site_id(DEFAULT_SITE_SLUG)
        role_id = get_role_id(DEFAULT_ROLE_SLUG)
    except Exception as e:
        print(f"Error: {e}")
        return
    for d in devices:
        if not validate_device(d):
            print("SKIP inválido", d)
            continue
        lid = d.get("device_id")
        nm = d.get("hostname") or d.get("sysName")
        vendor, model = resolve_device_type(d)
        dtid = import_device_type_if_exists(vendor, model)
        if dtid is None:
            print(f"SKIP {nm}: Sin device_type válido (vendor={vendor} model={model})")
            continue

        platform_id = get_platform_id((d.get("os") or "").strip().lower())
        primary_ip = d.get("ip")
        ip_id = get_ip_address_id(primary_ip)

        cf = {"cf_librenms_id": lid}
        resp_dev = nb_get("dcim/devices/", **cf)
        if resp_dev.get("count"):
            nb_dev_id = resp_dev["results"][0]["id"]
            print(f"= Ya existe {nm}")
        else:
            pl = {
                "name": nm,
                "device_type": dtid,
                "role": role_id,
                "site": site_id,
                "status": "active",
                "custom_fields": {"librenms_id": str(lid)},
            }
            if platform_id:
                pl["platform"] = platform_id
            if ip_id:
                if primary_ip and ":" in primary_ip:
                    pl["primary_ip6"] = ip_id
                else:
                    pl["primary_ip4"] = ip_id
            created = nb_post("dcim/devices/", pl)
            nb_dev_id = created.get("id")
            print(f"+ Creado {nm} ({lid}) con device_type {dtid}")

        ports = get_librenms_device_ports(lid)
        for p in ports:
            name = p.get("ifName") or p.get("ifDescr")
            if not name:
                continue
            exists = nb_get("dcim/interfaces/", device_id=nb_dev_id, name=name).get(
                "count", 0
            )
            if exists:
                print(f"= IF ya existe {name} en {nm}")
                continue
            payload = {
                "device": nb_dev_id,
                "name": name,
                "description": p.get("ifDescr") or "",
                "speed": p.get("ifSpeed") or 0,
                "enabled": (p.get("ifOperStatus", "").lower() == "up"),
                "type": "other",
                "custom_fields": {"librenms_port_id": str(p.get("port_id"))},
            }
            if p.get("ifPhysAddress"):
                payload["mac_address"] = p.get("ifPhysAddress")
            if p.get("ifMtu"):
                payload["mtu"] = p.get("ifMtu")
            nb_post("dcim/interfaces/", payload)
            print(f"+ IF creada {name} en {nm}")


if __name__ == "__main__":
    sync_devices()
