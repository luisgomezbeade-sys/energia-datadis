# ⚡ Energía Datadis

Descarga automática de datos de consumo y excedentes desde la API de Datadis usando GitHub Actions.

## Configuración

Ve a **Settings → Secrets and variables → Actions** y crea:

- `DATADIS_USER`: tu NIF
- `DATADIS_PASSWORD`: tu contraseña de Datadis

Opcionalmente, en **Variables**, crea `DATADIS_YEAR` con el año a descargar.

## Uso

Ve a **Actions → Descarga mensual de Datadis → Run workflow**.

Los resultados aparecerán en la carpeta `data/`.
