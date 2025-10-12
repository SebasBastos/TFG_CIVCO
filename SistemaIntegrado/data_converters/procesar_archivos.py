import pandas as pd
import numpy as np
import os
import re

def clean_data_csv(input_filepath, output_filepath, is_static):
    """
    Limpia un archivo .csv de datos estáticos:
    Solo convierte los valores NaN de Pandas a celdas vacías en el CSV.
    La lógica de eliminación por calibración ha sido removida.
    """
    try:
        # 1. Lee el archivo, tratando explícitamente 'NAN' como nulo.
        df = pd.read_csv(input_filepath, na_values=['NAN', ''])
        
        # Opcional pero recomendado: Limpieza de filas totalmente vacías
        # Esto elimina filas que no contienen ninguna información útil
        df.dropna(how='all', inplace=True) 

        # --- Reemplazo de NAN por celdas vacías ---
        
        # Reemplaza los valores NaN de Python (np.nan o pd.NA) por una cadena vacía ('')
        df = df.replace({np.nan: '', pd.NA: ''})
        
        # Guardar el archivo modificado
        df.to_csv(output_filepath, index=False)
        print(f"   -> Limpieza: Archivo guardado con éxito en '{output_filepath}'.")
        
    except Exception as e:
        print(f"❌ Error al limpiar el archivo {input_filepath}: {e}") 
    

def clean_dynamic_data(input_filepath, output_filepath):
    """
    Limpia y normaliza los archivos .csv generados de TDMS (Pruebas Dinámicas).
    1. Renombra las columnas largas a nombres cortos y claros.
    2. Elimina las columnas que contienen 'CHAN-1' o 'CHAN-2', etc., según la lista de exclusión.
    """
    try:
        df = pd.read_csv(input_filepath)

        # 1. Normalización de Nombres de Columnas
        new_columns = []
        rename_map = {}
        
        # Mapeo de nombres largos a cortos
        target_names = {
            'Time': 'RECORD',
            'A2120': 'A2120', # Acelerómetro
            'A2121': 'A2121', # Acelerómetro
            'A2122': 'A2122', # Acelerómetro
            'LV6195': 'LV6195', # LVDT
            'LV6282': 'LV6282', # LVDT
            # Los canales CHAN-X serán manejados abajo
        }
        
        # Columnas a excluir
        cols_to_exclude = ['CHAN-1', 'CHAN-2', 'CHAN-3', 'CHAN-4'] 
        
        for original_col in df.columns:
            cleaned_col = original_col
            
            # Intentar encontrar un nombre clave (Time, A2120, LV6195, etc.)
            found_key = False
            for key, new_name in target_names.items():
                if key in original_col:
                    rename_map[original_col] = new_name
                    new_columns.append(new_name)
                    found_key = True
                    break
            
            # Si no se encontró clave, revisar si es un canal (CHAN-X) o dejarlo como está
            if not found_key:
                # Usa una expresión regular para encontrar CHAN-N al final del nombre
                match = re.search(r'(CHAN-\d+)', original_col)
                if match:
                    chan_name = match.group(1)
                    if chan_name not in cols_to_exclude:
                         # Si deseas renombrar CHAN-4 a solo CHAN-4, úsalo aquí. 
                         # Por ahora, si no está en la lista de exclusión, lo dejamos.
                        new_columns.append(original_col)
                    # Si está en la lista de exclusión, no lo añadimos a new_columns
                else:
                    # Columna desconocida, la mantenemos con su nombre original largo
                    new_columns.append(original_col)

        # Aplicar el renombramiento
        df.rename(columns=rename_map, inplace=True)
        
        # 2. Eliminación de Columnas y Limpieza de Nombres Finales
        
        # Crear la lista final de columnas a mantener (filtrando las excluidas)
        final_cols_to_keep = [
            col for col in df.columns if not any(c in col for c in cols_to_exclude)
        ]
        
        # Eliminar las columnas que no necesitamos
        df = df[final_cols_to_keep]

        # 3. Guardar el archivo modificado
        # Los archivos TDMS a menudo tienen valores nulos, los mantenemos para el dashboard
        df = df.replace({np.nan: ''})
        df.to_csv(output_filepath, index=False)
        
        print(f"   -> Limpieza Dinámica: Archivo guardado con éxito en '{output_filepath}'. Columnas normalizadas.")
        
    except Exception as e:
        print(f"❌ Error al limpiar archivo dinámico {input_filepath}: {e}")