import pandas as pd
import numpy as np
import os
import re

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
            
            # **SOLUCIÓN:** Inicializar start_index a 0 antes del bloque condicional
            start_index = 0 
            
            strain_cols = [col for col in df.columns if 'Strain' in col]
            
            # Convertir las columnas de Strain a numérico
            for col in strain_cols:
                df[col] = pd.to_numeric(df[col], errors='coerce') 
            
            # Quitar filas que solo contienen NaN en las columnas de Strain
            df.dropna(subset=strain_cols, how='all', inplace=True)
            
            # Lógica para encontrar la primera fila donde se considera calibrado (entre -2 y 2)
            if strain_cols and not df.empty: # Añadir comprobación de df no vacío
                
                calibration_mask = (df[strain_cols].apply(lambda x: (x >= -2) & (x <= 2)).all(axis=1))
                
                try:
                    # idxmax() encuentra el primer índice con True
                    first_calibration_row = calibration_mask.idxmax()
                    
                    # Si la calibración ocurre después de la primera fila
                    if first_calibration_row > 0 and calibration_mask.any():
                        start_index = first_calibration_row
                        print(f"   -> Calibración: Eliminando {start_index} filas iniciales.")
                except Exception as e:
                    # Esto maneja el caso donde la máscara está vacía o algo falló en idxmax
                    print(f"   -> Advertencia en calibración: {e}")
                    pass 

            # Recorta el DataFrame a partir del índice encontrado
            # Esta línea ahora siempre funcionará porque start_index está definido
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