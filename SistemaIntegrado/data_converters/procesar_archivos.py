import pandas as pd
import numpy as np
import os

def clean_data_csv(input_filepath, output_filepath, is_static):
    """
    Limpia un archivo .csv: elimina filas antes de calibración y
    reemplaza valores NAN por celda vacía.
    """

    try:
        # Lee el archivo, asegurándose de que los 'NAN' del texto se interpreten como nulos.
        df = pd.read_csv(input_filepath, na_values=['NAN', ''])
        
        # --- 1. Manejo de Calibración Inicial (Solo para Pruebas Estáticas) ---
        if is_static:
            
            # Columnas de galgas extensiométricas a revisar
            strain_cols = [col for col in df.columns if 'Strain' in col]
            
            # Lógica para encontrar la primera fila donde se considera calibrado (entre -2 y 2)
            start_index = 0
            
            if strain_cols:
                # Crea una máscara booleana: True si TODAS las galgas en esa fila están entre -2 y 2
                calibration_mask = (df[strain_cols].apply(lambda x: (x >= -2) & (x <= 2)).all(axis=1))
                
                # Encuentra el índice de la PRIMERA ocurrencia de la máscara True
                try:
                    first_calibration_row = calibration_mask.idxmax()
                    # Si el primer valor True está más allá de la fila 0, recortamos
                    if first_calibration_row > 0:
                        start_index = first_calibration_row
                        print(f"   -> Calibración: Eliminando {start_index} filas iniciales.")
                except:
                    # Si no encuentra True, podría no haber una calibración visible, no hace nada
                    pass 

            # Recorta el DataFrame a partir del índice encontrado
            df = df.iloc[start_index:]
            df.reset_index(drop=True, inplace=True) # Resetea el índice

        # --- 2. Reemplazo de NAN por celdas vacías ---
        
        # Reemplaza los valores NaN de Python (np.nan) por una cadena vacía ('')
        # Esto hace que la celda quede vacía en el archivo CSV resultante.
        df = df.replace({np.nan: ''})
        
        # Guardar el archivo modificado
        df.to_csv(output_filepath, index=False)
        print(f"   -> Limpieza: Archivo guardado con éxito en '{output_filepath}'.")
        
    except Exception as e:
        print(f"❌ Error al limpiar el archivo {input_filepath}: {e}") 
    


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