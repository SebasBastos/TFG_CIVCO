import os
import shutil
from data_converters.convert_dat2csv import convert_dat_to_csv
from data_converters.convert_tdms2csv import convert_tdms_to_csv
from data_converters.procesar_archivos import clean_data_csv

def main():
    """
    Flujo de trabajo principal para la conversión y clasificación de datos
    """
    # 1. Definir directorios
    data_dir = "datos"
    processed_dir = "archivos_procesados"
    static_dir = os.path.join(processed_dir, "Pruebas_Estaticas")
    dynamic_dir = os.path.join(processed_dir, "Pruebas_Dinamicas")

    # Crear directorios si no existen
    for d in [processed_dir, static_dir, dynamic_dir]:
        if not os.path.exists(d):
            os.makedirs(d)

    if not os.path.exists(processed_dir):
        os.makedirs(processed_dir)

        # 2. Iterar, convertir, clasificar y limpiar
    for filename in os.listdir(data_dir):
        input_filepath = os.path.join(data_dir, filename)
        base_name = os.path.splitext(filename)[0]
        
        # Determinar el directorio de destino
        if filename.endswith(('.dat', '.csv')): # Campbell (.dat) y ESP32 (.csv) son estáticas
            target_dir = static_dir
            is_static = True
        elif filename.endswith('.tdms'): # BDI (.tdms) son dinámicas
            target_dir = dynamic_dir
            is_static = False
        else:
            continue # Ignorar otros formatos

        # Rutas de archivo
        original_csv_path = os.path.join(target_dir, f"{base_name}_original.csv")
        modified_csv_path = os.path.join(target_dir, f"{base_name}_modificado.csv")
        
        # A. Conversión / Copia a CSV original
        if filename.endswith('.dat'):
            convert_dat_to_csv(input_filepath, original_csv_path)
        elif filename.endswith('.tdms'):
            convert_tdms_to_csv(input_filepath, original_csv_path)
        elif filename.endswith('.csv'): # Archivos del ESP32
            shutil.copy(input_filepath, original_csv_path)
            print(f"✅ Archivo '{filename}' copiado a original.")

        # B. Limpieza de datos (solo si se creó el original)
        if os.path.exists(original_csv_path):
            clean_data_csv(original_csv_path, modified_csv_path, is_static)
        
    print("\nProceso de conversión, clasificación y limpieza inicial completado.")

if __name__ == "__main__":
    main()