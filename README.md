# libre2netbox

Sincronizador de dispositivos de LibreNMS a NetBox.

## Índice

1. [Descripción](#descripción)
2. [Requisitos](#requisitos)
3. [Instalación](#instalación)
4. [Configuración](#configuración)
5. [Estructura del Proyecto](#estructura-del-proyecto)
6. [Flujo de Trabajo](#flujo-de-trabajo)
7. [Módulos y Responsabilidades](#módulos-y-responsabilidades)
8. [Ejecución](#ejecución)
9. [Modo Dry-Run](#modo-dry-run)
10. [Solución de Problemas](#solución-de-problemas)

## Descripción

Este proyecto automatiza la sincronización de dispositivos desde LibreNMS hacia NetBox, creando en NetBox:
- Sitios
- Roles de dispositivo
- Tipos de dispositivo (importándolos desde la librería oficial o generando genéricos)
- Dispositivos propiamente dichos, con sus custom fields (`librenms_id`)

## Requisitos

- Python 3.7+
- Acceso a la API de LibreNMS
- Acceso a la API de NetBox
- Conexión a Internet para descargar device-types desde GitHub

## Instalación

1. Clonar o descargar este repositorio.
2. Crear y activar un entorno virtual (recomendado):
   ```sh
   python3 -m venv ./venv
   source ./venv/bin/activate
