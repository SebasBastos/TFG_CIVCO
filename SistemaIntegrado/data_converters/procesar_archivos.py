"""
Módulo para limpieza y normalización de archivos CSV
Maneja datos estáticos (galgas extensiométricas) y dinámicos (TDMS)
"""
# Código basado en:
# Solución de problemas y optimización hecha con Claude 4.5
# Estructura del código hecha por GeminiAI

import pandas as pd
import numpy as np
import os
import re


def clean_data_csv(input_filepath, output_filepath, is_static):
    """
    Limpia archivos CSV de datos estáticos (galgas extensiométricas, LVDT)
    
    Pasos de limpieza:
    1. Detecta el separador (coma o punto y coma)
    2. Normaliza la columna RECORD como índice numérico
    3. Procesa timestamps a formato estándar
    4. Convierte columnas numéricas y limpia valores NaN
    
    Args:
        input_filepath: Ruta del archivo CSV original
        output_filepath: Ruta donde guardar el archivo limpio
        is_static: True para datos estáticos, False para dinámicos
    """
    try:
        # Detectar separador del CSV
        with open(input_filepath, 'r', encoding='utf-8') as f:
            first_line = f.readline()
        
        separator = ';' if first_line.count(';') > first_line.count(',') else ','
        
        # Leer archivo con el separador correcto
        df = pd.read_csv(input_filepath, sep=separator, na_values=['NAN', ''], encoding='utf-8')
        
        # Normalizar columna RECORD (índice de muestra)
        df = _normalize_record_column(df)
        
        # Procesar columna de tiempo si existe
        if 'TIMESTAMP' in df.columns:
            df['TIMESTAMP'] = pd.to_datetime(df['TIMESTAMP'], errors='coerce')
        
        # Identificar y limpiar columnas de datos numéricos
        data_columns = [col for col in df.columns 
                       if col not in ['RECORD', 'TIMESTAMP'] 
                       and df[col].dtype in ['float64', 'int64', 'object']]
        
        # Convertir columnas a numéricas y limpiar NaN
        for col in data_columns:
            if df[col].dtype == 'object':
                df[col] = pd.to_numeric(df[col], errors='coerce')
            df[col] = df[col].replace({np.nan: '', pd.NA: ''})
        
        # Eliminar filas completamente vacías
        df.dropna(how='all', subset=data_columns, inplace=True)
        
        # Guardar archivo limpio
        os.makedirs(os.path.dirname(output_filepath), exist_ok=True)
        df.to_csv(output_filepath, index=False, encoding='utf-8')
        
    except Exception as e:
        # Fallback: guardar archivo original sin procesar
        try:
            df = pd.read_csv(input_filepath)
            os.makedirs(os.path.dirname(output_filepath), exist_ok=True)
            df.to_csv(output_filepath, index=False)
        except:
            pass
        raise e


def _normalize_record_column(df):
    """
    Normaliza la columna RECORD como índice numérico entero
    
    Args:
        df: DataFrame con los datos
        
    Returns:
        DataFrame con columna RECORD normalizada
    """
    if 'RECORD' in df.columns:
        df['RECORD'] = pd.to_numeric(df['RECORD'], errors='coerce')
        df = df.dropna(subset=['RECORD'])
        df['RECORD'] = df['RECORD'].astype(int)
    else:
        # Buscar columna similar (case insensitive)
        possible_cols = [col for col in df.columns if 'record' in col.lower()]
        if possible_cols:
            df = df.rename(columns={possible_cols[0]: 'RECORD'})
            df['RECORD'] = pd.to_numeric(df['RECORD'], errors='coerce').fillna(0).astype(int)
        else:
            # Crear RECORD basado en el índice
            df['RECORD'] = range(1, len(df) + 1)
    
    return df


def clean_dynamic_data(input_filepath, output_filepath):
    """
    Limpia archivos CSV de datos dinámicos (convertidos de TDMS)
    
    Pasos de limpieza:
    1. Renombra columnas largas a nombres cortos (A2120, LV6195, etc.)
    2. Elimina canales no utilizados (CHAN-1, CHAN-2, etc.)
    3. Convierte 'Time' a 'RECORD' como índice
    
    Args:
        input_filepath: Ruta del archivo CSV original de TDMS
        output_filepath: Ruta donde guardar el archivo limpio
    """
    try:
        df = pd.read_csv(input_filepath)
        
        # Mapeo de nombres originales a nombres cortos
        column_mapping = {
            'Time': 'RECORD',
            'A2120': 'A2120',  # Acelerómetro 1
            'A2121': 'A2121',  # Acelerómetro 2
            'A2122': 'A2122',  # Acelerómetro 3
            'LV6195': 'LV6195',  # LVDT 1
            'LV6282': 'LV6282',  # LVDT 2
        }
        
        # Canales a excluir del análisis
        excluded_channels = ['CHAN-1', 'CHAN-2', 'CHAN-3', 'CHAN-4']
        
        # Renombrar columnas según el mapeo
        rename_map = {}
        for original_col in df.columns:
            for key, new_name in column_mapping.items():
                if key in original_col:
                    rename_map[original_col] = new_name
                    break
        
        df.rename(columns=rename_map, inplace=True)
        
        # Filtrar columnas excluyendo canales no deseados
        columns_to_keep = [col for col in df.columns 
                          if not any(excluded in col for excluded in excluded_channels)]
        
        df = df[columns_to_keep]
        
        # Limpiar valores NaN
        df = df.replace({np.nan: ''})
        
        # Guardar archivo procesado
        df.to_csv(output_filepath, index=False)
        
        print(f"✓ Archivo dinámico procesado: '{output_filepath}'")
        
    except Exception as e:
        print(f"✗ Error al limpiar archivo dinámico {input_filepath}: {e}")