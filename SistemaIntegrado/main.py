import os
import sys
from data_converters.convert_dat2csv import convert_dat_to_csv
from data_converters.convert_tdms2csv import convert_tdms_to_csv
from data_converters.procesar_archivos import unify_and_clean_csv

def main():
    """
    Flujo de trabajo principal para el procesamiento de datos.
    """
    # 1. Definir directorios
    data_dir = "datos"
    processed_dir = "archivos_procesados"

    if not os.path.exists(processed_dir):
        os.makedirs(processed_dir)

    # 2. Iterar y convertir los archivos
    for filename in os.listdir(data_dir):
        input_filepath = os.path.join(data_dir, filename)
        
        if filename.endswith('.dat'):
            output_filepath = os.path.join(processed_dir, filename.replace('.dat', '.csv'))
            convert_dat_to_csv(input_filepath, output_filepath)
        
        elif filename.endswith('.tdms'):
            output_filepath = os.path.join(processed_dir, filename.replace('.tdms', '.csv'))
            convert_tdms_to_csv(input_filepath, output_filepath)
        
        elif filename.endswith('.csv'):
            # Copiar archivos .csv (como los del ESP32) al directorio de salida
            output_filepath = os.path.join(processed_dir, filename)
            import shutil
            shutil.copy(input_filepath, output_filepath)
            print(f"✅ Archivo '{input_filepath}' copiado a '{output_filepath}'.")

    # 3. Unificar y limpiar todos los archivos .csv convertidos
    final_output_filepath = os.path.join(processed_dir, 'unified_data.csv')
    unify_and_clean_csv(processed_dir, final_output_filepath)
    
if __name__ == "__main__":
    main()