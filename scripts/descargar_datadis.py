import os
import sqlite3
from datetime import datetime, timedelta
import requests
import pandas as pd

# ─── CONFIGURACIÓN ───
USERNAME = os.environ["DATADIS_USER"]
PASSWORD = os.environ["DATADIS_PASSWORD"]
BASE_URL = "https://datadis.es"


def authenticate():
    """Obtiene el token JWT de Datadis (se envía en el body y se recibe como texto)."""
    print("🔐 Autenticando con Datadis...")
    r = requests.post(
        f"{BASE_URL}/nikola-auth/tokens/login",
        data={"username": USERNAME, "password": PASSWORD},  # ✅ 'data', no 'params'
        timeout=30,
    )
    r.raise_for_status()  # Lanza excepción si el código HTTP no es 2xx

    token = r.text.strip()  # ✅ El token es texto plano, no JSON
    if not token:
        raise RuntimeError(f"Respuesta de login vacía. Código: {r.status_code}")
    print("✅ Autenticación correcta")
    return token


def get_supplies(token):
    """Lista los CUPS asociados a la cuenta."""
    r = requests.get(
        f"{BASE_URL}/api-private/api/get-supplies",
        headers={"Authorization": f"Bearer {token}"},  # ✅ Formato correcto
        timeout=30,
    )
    r.raise_for_status()
    supplies = r.json()
    print(f"🔌 {len(supplies)} punto(s) encontrado(s)")
    return supplies


def get_consumption(token, cups, distributor_code, start_date, end_date):
    """Descarga la curva horaria de consumo y excedentes."""
    r = requests.get(
        f"{BASE_URL}/api-private/api/get-consumption-data",
        headers={"Authorization": f"Bearer {token}"},
        params={
            "cups": cups,
            "distributorCode": distributor_code,
            "startDate": start_date,
            "endDate": end_date,
            "measurementType": "0",  # 0 = horario
            "pointType": "5",
        },
        timeout=120,
    )
    if r.status_code != 200:
        raise RuntimeError(f"Error API ({r.status_code}): {r.text[:500]}")
    return r.json()


def calcular_rango_fechas():
    """Últimos 12 meses completos (seguro dentro del límite de 24 de Datadis)."""
    hoy = datetime.now()
    desde = (hoy.replace(day=1) - timedelta(days=365)).replace(day=1)
    hasta = hoy.replace(day=1) - timedelta(days=1)
    return desde.strftime("%Y/%m"), hasta.strftime("%Y/%m")


def obtener_codigo_distribuidora(cups: str) -> str:
    """Extrae el código de distribuidora de los dígitos 2-6 del CUPS."""
    if cups and len(cups) >= 6 and cups.startswith("ES"):
        posible = cups[2:6]
        if posible.isdigit():
            return str(int(posible))  # '0021' -> '21'
    return None


def main():
    date_from, date_to = calcular_rango_fechas()
    print(f"📅 Rango de descarga: {date_from} → {date_to}")
    print("🚀 Iniciando descarga directa contra la API de Datadis...")
    os.makedirs("data", exist_ok=True)
    archivos_generados = 0

    token = authenticate()
    supplies = get_supplies(token)

    for supply in supplies:
        cups = supply.get("cups")
        codigo_dist = obtener_codigo_distribuidora(cups)
        if not codigo_dist:
            print(f"⚠️ No se pudo extraer distribuidora de {cups}")
            continue

        print(f"\n--- CUPS: {cups} | Distribuidora: {codigo_dist} ---")
        print(f"   Solicitando datos de {date_from} a {date_to}...")

        data = get_consumption(token, cups, codigo_dist, date_from, date_to)
        if not data:
            print("⚠️ Sin datos para este periodo")
            continue

        df = pd.DataFrame(data)
        print(f"✅ {len(df)} registros horarios descargados")
        print(f"   Columnas: {list(df.columns)}")

        csv_path = f"data/datadis_{cups}_{date_from.replace('/', '-')}_{date_to.replace('/', '-')}.csv"
        df.to_csv(csv_path, index=False, encoding="utf-8-sig")
        print(f"💾 CSV guardado: {csv_path}")

        db_path = "data/mi_energia.db"
        conn = sqlite3.connect(db_path)
        df.to_sql(f"consumo_{cups}", conn, if_exists="replace", index=False)
        conn.close()
        print(f"🗄️  SQLite actualizado: {db_path}")

        archivos_generados += 1

    if archivos_generados == 0:
        raise RuntimeError("No se ha generado ningún archivo. Revisa el log.")


if __name__ == "__main__":
    main()
