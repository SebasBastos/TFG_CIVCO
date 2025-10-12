import pandas as pd
import numpy as np
import os
import re

def clean_data_csv(input_filepath, output_filepath, is_static):
    """
    Limpia un archivo .csv de datos estáticos:
    - Maneja archivos con punto y coma como separador
    - Preserva la columna RECORD como numérica
    - Convierte valores NaN a celdas vacías en columnas de datos
    """
    try:
        # 1. Detectar el separador automáticamente
        with open(input_filepath, 'r', encoding='utf-8') as f:
            first_line = f.readline()
        
        # Detectar si usa punto y coma como separador
        if ';' in first_line and first_line.count(';') > first_line.count(','):
            separator = ';'
        else:
            separator = ','
        
        # 2. Leer el archivo con el separador correcto
        df = pd.read_csv(input_filepath, sep=separator, na_values=['NAN', ''], encoding='utf-8')
        
        # 3. Preservar y asegurar que RECORD sea numérico
        if 'RECORD' in df.columns:
            df['RECORD'] = pd.to_numeric(df['RECORD'], errors='coerce')
            df = df.dropna(subset=['RECORD'])
            df['RECORD'] = df['RECORD'].astype(int)
        else:
            # Buscar columnas que contengan 'record' (case insensitive)
            possible_record_cols = [col for col in df.columns if 'record' in col.lower()]
            if possible_record_cols:
                original_col_name = possible_record_cols[0]
                df = df.rename(columns={original_col_name: 'RECORD'})
                df['RECORD'] = pd.to_numeric(df['RECORD'], errors='coerce').fillna(0).astype(int)
            else:
                # Si no hay RECORD, crear una columna basada en el índice
                df['RECORD'] = range(1, len(df) + 1)
        
        # 4. Procesar columna TIMESTAMP
        if 'TIMESTAMP' in df.columns:
            try:
                df['TIMESTAMP'] = pd.to_datetime(df['TIMESTAMP'], errors='coerce')
                if df['TIMESTAMP'].isna().all():
                    df['TIMESTAMP'] = pd.to_datetime(df['TIMESTAMP'], format='%d/%m/%Y %H:%M', errors='coerce')
            except Exception:
                pass  # Mantener como está si falla la conversión
        
        # 5. Identificar y limpiar columnas de datos
        data_columns = []
        for col in df.columns:
            if col not in ['RECORD', 'TIMESTAMP'] and df[col].dtype in ['float64', 'int64', 'object']:
                if df[col].dtype == 'object':
                    df[col] = pd.to_numeric(df[col], errors='coerce')
                data_columns.append(col)
        
        # 6. Limpieza de datos numéricos (reemplazar NaN con '')
        for col in data_columns:
            df[col] = df[col].replace({np.nan: '', pd.NA: ''})
        
        # 7. Eliminar filas totalmente vacías
        df.dropna(how='all', subset=data_columns, inplace=True)
        
        # 8. Guardar el archivo modificado
        os.makedirs(os.path.dirname(output_filepath), exist_ok=True)
        df.to_csv(output_filepath, index=False, encoding='utf-8')
        
    except Exception as e:
        # En caso de error, guardar el archivo original como respaldo
        try:
            df = pd.read_csv(input_filepath)
            os.makedirs(os.path.dirname(output_filepath), exist_ok=True)
            df.to_csv(output_filepath, index=False)
        except:
            pass
        raise e
    

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