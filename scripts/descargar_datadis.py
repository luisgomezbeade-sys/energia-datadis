import os
import sqlite3
from datetime import datetime, timedelta
import pandas as pd
from datadis_python.client.v1.simple_client import SimpleDatadisClientV1
from datadis_python.exceptions import AuthenticationError, APIError, DatadisError, ValidationError

# ─── PARCHE OPCIONAL (solo si quieres intentar saltar la validación de 2 años) ───
# import datadis_python.utils.validators as _validators
# _validators.validate_date_range = lambda *args, **kwargs: args[:2]

USERNAME = os.environ["DATADIS_USER"]
PASSWORD = os.environ["DATADIS_PASSWORD"]


def calcular_rango_maximo_permitido():
    """
    Devuelve (date_from, date_to) en formato 'YYYY/MM' para solicitar
    el máximo histórico que Datadis permite (últimos 2 años desde hoy).
    """
    hoy = datetime.now()
    # El límite inferior es hoy menos 2 años. Para evitar que el día exacto
    # cause problemas, nos situamos un día después del límite.
    limite_inferior = (hoy - timedelta(days=730)) + timedelta(days=1)
    # El límite superior es el mes actual (o el mes pasado si hoy es el día 1)
    limite_superior = hoy if hoy.day > 1 else (hoy.replace(day=1) - timedelta(days=1))

    # Formateamos como 'YYYY/MM'
    desde = limite_inferior.strftime("%Y/%m")
    hasta = limite_superior.strftime("%Y/%m")

    # Aseguramos que el mes de inicio no sea anterior al límite real
    if limite_inferior.month == 12:
        desde = f"{limite_inferior.year + 1}/01"
    else:
        desde = f"{limite_inferior.year}/{limite_inferior.month + 1:02d}"

    return desde, hasta


def obtener_codigo_distribuidora(cups: str) -> str:
    """Extrae el código de distribuidora de los dígitos 2-4 del CUPS."""
    if cups and len(cups) >= 6 and cups.startswith("ES"):
        posible = cups[2:6]
        if posible.isdigit():
            return str(int(posible))
    return None


def main():
    date_from, date_to = calcular_rango_maximo_permitido()
    print(f"📅 Rango de descarga (máximo permitido por Datadis): {date_from} → {date_to}")
    print("🚀 Iniciando descarga...")
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
                cups = supply.cups
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
                    print(f"❌ Error de validación: {e}")
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
    
