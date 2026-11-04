import os
import sqlite3
from datetime import datetime, timedelta
import pandas as pd
from datadis_python.client.v1.simple_client import SimpleDatadisClientV1
from datadis_python.exceptions import AuthenticationError, APIError, DatadisError, ValidationError

USERNAME = os.environ["DATADIS_USER"]
PASSWORD = os.environ["DATADIS_PASSWORD"]

# Año opcional; si no se indica, se calcula un rango válido automáticamente
AÑO_SOLICITADO = os.environ.get("DATADIS_YEAR", "").strip()


def calcular_rango_fechas(año_solicitado: str):
    """
    Devuelve (date_from, date_to) en formato 'YYYY/MM' garantizando que
    estén dentro de los últimos 24 meses que permite Datadis.
    """
    hoy = datetime.now()
    limite_inferior = hoy - timedelta(days=730)  # ~24 meses

    if año_solicitado and año_solicitado.isdigit():
        año = int(año_solicitado)
        desde = datetime(año, 1, 1)
        hasta = datetime(año, 12, 31)
        # Si el año completo no cabe en la ventana de 24 meses, ajustamos
        if desde < limite_inferior:
            desde = limite_inferior
        if hasta > hoy:
            hasta = hoy
    else:
        # Sin año concreto: usamos los últimos 12 meses completos
        desde = (hoy.replace(day=1) - timedelta(days=365)).replace(day=1)
        hasta = hoy.replace(day=1) - timedelta(days=1)

    return desde.strftime("%Y/%m"), hasta.strftime("%Y/%m")


def obtener_codigo_distribuidora(cups: str) -> str:
    """Extrae el código de distribuidora de los dígitos 2-4 del CUPS."""
    if cups and len(cups) >= 6 and cups.startswith("ES"):
        posible = cups[2:6]
        if posible.isdigit():
            return str(int(posible))  # '0021' -> '21'
    return None


def main():
    date_from, date_to = calcular_rango_fechas(AÑO_SOLICITADO)
    print(f"📅 Rango de descarga: {date_from} → {date_to}")
    print(f"🚀 Iniciando descarga de Datadis...")
    os.makedirs("data", exist_ok=True)
    archivos_generados = 0

    try:
        with SimpleDatadisClientV1(USERNAME, PASSWORD) as client:
            print("✅ Autenticación correcta")
            supplies = client.get_supplies()
            if not supplies:
                raise RuntimeError("No hay puntos de suministro en la cuenta")

            print(f"🔌 {len(supplies)} punto(s) encontrado(s)")

            for supply in supplies:
                cups = supply.cups  # ✅ Usamos el CUPS original, sin modificarlo
                codigo_dist = obtener_codigo_distribuidora(cups)
                if not codigo_dist:
                    print(f"⚠️ No se pudo extraer el código de distribuidora de {cups}")
                    continue

                print(f"\n--- CUPS: {cups} | Distribuidora: {codigo_dist} ---")
                print(f"   Solicitando datos de {date_from} a {date_to}...")

                try:
                    consumption = client.get_consumption(
                        cups=cups,
                        distributor_code=codigo_dist,
                        date_from=date_from,
                        date_to=date_to,
                    )
                except ValidationError as e:
                    print(f"❌ Error de validación con el CUPS {cups}: {e}")
                    continue

                if not consumption:
                    print("⚠️ Sin datos para este periodo")
                    continue

                rows = [{
                    "cups": cups,
                    "fecha": r.date,
                    "consumo_kwh": r.consumptionKWh,
                    "excedentes_kwh": getattr(r, "surplusEnergyKWh", None),
                    "autoconsumo_kwh": getattr(r, "selfConsumptionKWh", None),
                    "metodo": r.obtainMethod,
                } for r in consumption]

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

    except AuthenticationError:
        print("❌ Error de autenticación: revisa NIF y contraseña")
        raise
    except APIError as e:
        print(f"❌ Error de API: {e}")
        raise
    except DatadisError as e:
        print(f"❌ Error de Datadis: {e}")
        raise
    except Exception as e:
        print(f"❌ Error inesperado: {e}")
        raise

    if archivos_generados == 0:
        raise RuntimeError("No se ha generado ningún archivo. Revisa el log.")


if __name__ == "__main__":
    main()
