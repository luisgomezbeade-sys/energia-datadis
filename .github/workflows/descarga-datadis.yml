import os
import sqlite3
from datetime import datetime
import pandas as pd
from datadis_python.client.v1.simple_client import SimpleDatadisClientV1
from datadis_python.exceptions import AuthenticationError, APIError, DatadisError

# ─── CONFIGURACIÓN ───
USERNAME = os.environ["DATADIS_USER"]
PASSWORD = os.environ["DATADIS_PASSWORD"]
AÑO = os.environ.get("DATADIS_YEAR", str(datetime.now().year - 1))


def obtener_codigo_distribuidora(supply):
    """Devuelve el código de distribuidora probando varios nombres de atributo.
    Como último recurso, lo extrae del propio CUPS (los 2 dígitos tras 'ES')."""
    for attr in ("distributorCode", "distributor_code", "code", "distributor"):
        valor = getattr(supply, attr, None)
        if valor is not None and not callable(valor):
            return valor
    cups = getattr(supply, "cups", "")
    if cups and len(cups) > 4 and cups.startswith("ES"):
        posible = cups[2:4]
        if posible.isdigit():
            return posible
    return None


def main():
    print(f"🚀 Descargando datos de Datadis para el año {AÑO}...")
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
                codigo_dist = obtener_codigo_distribuidora(supply)
                if not codigo_dist:
                    attrs = [a for a in dir(supply) if not a.startswith("_")]
                    print(f"⚠️ No se pudo determinar el código de distribuidora para {supply.cups}")
                    print(f"   Atributos disponibles: {attrs}")
                    continue

                print(f"\n--- CUPS: {supply.cups} | Distribuidora: {codigo_dist} ---")

                consumption = client.get_consumption(
                    cups=supply.cups,
                    distributor_code=codigo_dist,
                    date_from=f"{AÑO}/01",
                    date_to=f"{AÑO}/12",
                )

                if not consumption:
                    print("⚠️ Sin datos para este periodo")
                    continue

                rows = [{
                    "cups": supply.cups,
                    "fecha": r.date,
                    "consumo_kwh": r.consumptionKWh,
                    "excedentes_kwh": getattr(r, "surplusEnergyKWh", None),
                    "autoconsumo_kwh": getattr(r, "selfConsumptionKWh", None),
                    "metodo": r.obtainMethod,
                } for r in consumption]

                df = pd.DataFrame(rows)
                print(f"✅ {len(df)} registros horarios descargados")

                csv_path = f"data/datadis_{supply.cups}_{AÑO}.csv"
                df.to_csv(csv_path, index=False, encoding="utf-8-sig")
                print(f"💾 CSV guardado: {csv_path}")

                db_path = "data/mi_energia.db"
                conn = sqlite3.connect(db_path)
                df.to_sql(f"consumo_{supply.cups}", conn, if_exists="replace", index=False)
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
