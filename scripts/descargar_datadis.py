import os
import sqlite3
from datetime import datetime, timedelta
import pandas as pd
from datadis_client import create_client

# ─── CONFIGURACIÓN ───
USERNAME = os.environ["DATADIS_USER"]
PASSWORD = os.environ["DATADIS_PASSWORD"]


def calcular_rango_fechas():
    """Últimos 12 meses completos (seguro dentro del límite de 2 años de Datadis)."""
    hoy = datetime.now()
    desde = (hoy.replace(day=1) - timedelta(days=365)).replace(day=1)
    hasta = hoy.replace(day=1) - timedelta(days=1)
    return desde.strftime("%Y/%m"), hasta.strftime("%Y/%m")


def main():
    date_from, date_to = calcular_rango_fechas()
    print(f"📅 Rango de descarga: {date_from} → {date_to}")
    os.makedirs("data", exist_ok=True)
    archivos_generados = 0

    try:
        client = create_client(username=USERNAME, password=PASSWORD)
        print("✅ Autenticación correcta")

        supplies = client.get_supplies()
        if not supplies:
            raise RuntimeError("No hay puntos de suministro en la cuenta")
        print(f"🔌 {len(supplies)} punto(s) encontrado(s)")

        for supply in supplies:
            cups = supply.get("cups")
            # ✅ Usamos el distributorCode que devuelve la API (ej. "2")
            distributor_code = supply.get("distributorCode")
            # ✅ Usamos el pointType que devuelve la API (ej. "5")
            point_type = supply.get("pointType")

            if not all([cups, distributor_code, point_type]):
                print(f"⚠️ Faltan datos en el suministro: {supply}")
                continue

            print(f"\n--- CUPS: {cups} | Distribuidora: {distributor_code} | PointType: {point_type} ---")
            print(f"   Solicitando datos de {date_from} a {date_to}...")

            consumption = client.get_consumption_data(
                cups=cups,
                distributor_code=distributor_code,  # ✅ Valor correcto ("2")
                start_date=date_from,
                end_date=date_to,
                measurement_type="0",               # 0 = horario
                point_type=point_type               # ✅ Valor correcto ("5")
            )

            if not consumption or 'timeCurve' not in consumption:
                print("⚠️ Sin datos para este periodo")
                continue

            rows = []
            for reading in consumption.get('timeCurve', []):
                rows.append({
                    "cups": cups,
                    "fecha": reading.get("date"),
                    "hora": reading.get("time"),
                    "consumo_kwh": reading.get("consumptionKWh"),
                    "metodo": reading.get("obtainMethod"),
                })

            df = pd.DataFrame(rows)
            print(f"✅ {len(df)} registros horarios descargados")

            csv_path = f"data/datadis_{cups}_{date_from.replace('/', '-')}_{date_to.replace('/', '-')}.csv"
            df.to_csv(csv_path, index=False, encoding="utf-8-sig")
            print(f"💾 CSV guardado: {csv_path}")

            db_path = "data/mi_energia.db"
            conn = sqlite3.connect(db_path)
            df.to_sql(f"consumo_{cups}", conn, if_exists="replace", index=False)
            conn.close()
            print(f"🗄️  SQLite actualizado: {db_path}")

            archivos_generados += 1

    except Exception as e:
        print(f"❌ Error inesperado: {e}")
        raise

    if archivos_generados == 0:
        raise RuntimeError("No se ha generado ningún archivo. Revisa el log.")


if __name__ == "__main__":
    main()
