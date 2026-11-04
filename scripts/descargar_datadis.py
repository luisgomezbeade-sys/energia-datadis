import os
import sqlite3
from datetime import datetime
import pandas as pd
from datadis_python.client.v1.simple_client import SimpleDatadisClientV1
from datadis_python.exceptions import AuthenticationError, APIError, DatadisError, ValidationError

USERNAME = os.environ["DATADIS_USER"]
PASSWORD = os.environ["DATADIS_PASSWORD"]
AÑO = os.environ.get("DATADIS_YEAR") or str(datetime.now().year - 1)

print(f"📅 Año de descarga: {AÑO}")  # Línea de diagnóstico opcional

def obtener_codigo_distribuidora_desde_cups(cups: str) -> str:
    """Extrae el código de distribuidora de los dígitos 2-4 del CUPS.
    Ej: ES0021... -> '21' (I-DE). ES0022... -> '22' (UFD)."""
    if cups and len(cups) >= 6 and cups.startswith("ES"):
        posible = cups[2:6]  # '0021'
        if posible.isdigit():
            return str(int(posible))  # '21'
    return None


def reparar_cups(cups: str) -> str:
    """Si el CUPS es demasiado corto, prueba a añadir sufijos habituales
    hasta que cumpla el formato que exige la librería."""
    if len(cups) >= 22:  # ya es válido (22-24 caracteres en total)
        return cups
    for sufijo in ("0F", "1P"):
        candidato = cups + sufijo
        if 22 <= len(candidato) <= 24:
            print(f"🔧 CUPS corto detectado. Se probará con: {candidato}")
            return candidato
    return cups  # si nada funciona, devolver el original


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
                cups_original = supply.cups
                codigo_dist = obtener_codigo_distribuidora_desde_cups(cups_original)
                if not codigo_dist:
                    print(f"⚠️ No se pudo extraer el código de distribuidora de {cups_original}")
                    continue

                print(f"\n--- CUPS original: {cups_original} | Distribuidora: {codigo_dist} ---")

                # Reparar el CUPS si es necesario
                cups_reparado = reparar_cups(cups_original)

                try:
                    consumption = client.get_consumption(
                        cups=cups_reparado,
                        distributor_code=codigo_dist,
                        date_from=f"{AÑO}/01",
                        date_to=f"{AÑO}/12",
                    )
                except ValidationError as e:
                    print(f"❌ El CUPS reparado ({cups_reparado}) sigue siendo inválido: {e}")
                    # Probar el otro sufijo como último recurso
                    for sufijo in ("1P", "0F"):
                        candidato = cups_original + sufijo
                        if candidato == cups_reparado:
                            continue
                        print(f"   Reintentando con: {candidato}")
                        try:
                            consumption = client.get_consumption(
                                cups=candidato,
                                distributor_code=codigo_dist,
                                date_from=f"{AÑO}/01",
                                date_to=f"{AÑO}/12",
                            )
                            cups_reparado = candidato
                            break
                        except ValidationError:
                            continue
                    else:
                        print("   ❌ Ningún sufijo ha funcionado. Se omite este suministro.")
                        continue

                if not consumption:
                    print("⚠️ Sin datos para este periodo")
                    continue

                rows = [{
                    "cups": cups_reparado,
                    "fecha": r.date,
                    "consumo_kwh": r.consumptionKWh,
                    "excedentes_kwh": getattr(r, "surplusEnergyKWh", None),
                    "autoconsumo_kwh": getattr(r, "selfConsumptionKWh", None),
                    "metodo": r.obtainMethod,
                } for r in consumption]

                df = pd.DataFrame(rows)
                print(f"✅ {len(df)} registros horarios descargados")

                csv_path = f"data/datadis_{cups_reparado}_{AÑO}.csv"
                df.to_csv(csv_path, index=False, encoding="utf-8-sig")
                print(f"💾 CSV guardado: {csv_path}")

                db_path = "data/mi_energia.db"
                conn = sqlite3.connect(db_path)
                df.to_sql(f"consumo_{cups_reparado}", conn, if_exists="replace", index=False)
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
