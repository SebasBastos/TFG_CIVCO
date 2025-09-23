

import pandas as pd
import os

def unify_and_clean_csv(input_directory, output_filepath):
    """
    Unifica todos los archivos .csv en un directorio, elimina datos en blanco
    y reorganiza las columnas.
    """
    try:
        all_dataframes = []
        for filename in os.listdir(input_directory):
            if filename.endswith('.csv'):
                filepath = os.path.join(input_directory, filename)
                df = pd.read_csv(filepath)
                # Opcional: Estandarizar nombres de columnas
                df.columns = [col.lower().replace(' ', '_') for col in df.columns]
                
                # Opcional: Eliminar columnas con datos faltantes o que no se usaron
                df.dropna(axis=1, how='all', inplace=True)
                
                all_dataframes.append(df)
        
        # Concatena todos los DataFrames
        if all_dataframes:
            unified_df = pd.concat(all_dataframes, ignore_index=True)
            unified_df.to_csv(output_filepath, index=False)
            print(f"✅ Todos los archivos CSV unificados y limpiados en '{output_filepath}'.")
        else:
            print("⚠️ No se encontraron archivos CSV para unificar.")
            
    except Exception as e:
        print(f"❌ Error al unificar y limpiar los datos: {e}")