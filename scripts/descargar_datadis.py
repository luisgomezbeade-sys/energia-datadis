import os
import sqlite3
from datetime import datetime
import pandas as pd
from datadis_python.client.v1.simple_client import SimpleDatadisClientV1
from datadis_python.exceptions import AuthenticationError, APIError, DatadisError

USERNAME = os.environ["DATADIS_USER"]
PASSWORD = os.environ["DATADIS_PASSWORD"]
AÑO = os.environ.get("DATADIS_YEAR", str(datetime.now().year - 1))

def main():
    print(f"🚀 Descargando datos de Datadis para el año {AÑO}...")
    os.makedirs("data", exist_ok=True)

    try:
        with SimpleDatadisClientV1(USERNAME, PASSWORD) as client:
            print("✅ Autenticación correcta")

            supplies = client.get_supplies()
            if not supplies:
                print("❌ No hay puntos de suministro")
                return

            print(f"🔌 {len(supplies)} punto(s) encontrado(s)")

            for supply in supplies:
                print(f"\n--- CUPS: {supply.cups} | Distribuidora: {supply.distributorCode} ---")

                consumption = client.get_consumption(
                    cups=supply.cups,
                    distributor_code=supply.distributorCode,
                    date_from=f"{AÑO}/01",
                    date_to=f"{AÑO}/12",
                )

                if not consumption:
                    print("⚠️ Sin datos para este periodo")
                    continue

                rows = []
                for r in consumption:
                    rows.append({
                        "cups": supply.cups,
                        "fecha": r.date,
                        "consumo_kwh": r.consumptionKWh,
                        "excedentes_kwh": getattr(r, "surplusEnergyKWh", None),
                        "autoconsumo_kwh": getattr(r, "selfConsumptionKWh", None),
                        "metodo": r.obtainMethod,
                    })

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

    except AuthenticationError:
        print("❌ Error de autenticación: revisa usuario/contraseña")
    except APIError as e:
        print(f"❌ Error de API: {e}")
    except DatadisError as e:
        print(f"❌ Error de Datadis: {e}")
    except Exception as e:
        print(f"❌ Error inesperado: {e}")

if __name__ == "__main__":
    main()
