"""
Sistema Integrado de Monitoreo Estructural
Dashboard para visualizar datos de galgas extensiométricas, LVDT y acelerómetros
"""

import streamlit as st
import pandas as pd
import numpy as np
import os
import shutil
import altair as alt

from data_converters.convert_dat2csv import convert_dat_to_csv
from data_converters.convert_tdms2csv import convert_tdms_to_csv
from data_converters.procesar_archivos import clean_data_csv, clean_dynamic_data


# ============================================================================
# CONFIGURACIÓN GLOBAL
# ============================================================================

st.set_page_config(
    page_title="Sistema de Monitoreo Estructural",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Rutas de directorios
DATA_DIR = "datos"
PROCESSED_DIR = "archivos_procesados"
STATIC_DIR = os.path.join(PROCESSED_DIR, "Pruebas_Estaticas")
DYNAMIC_DIR = os.path.join(PROCESSED_DIR, "Pruebas_Dinamicas")

# Crear directorios si no existen
for directory in [PROCESSED_DIR, STATIC_DIR, DYNAMIC_DIR]:
    os.makedirs(directory, exist_ok=True)


# ============================================================================
# FUNCIONES DE PROCESAMIENTO
# ============================================================================

def run_conversion_and_cleaning():
    """
    Convierte y limpia todos los archivos .dat, .tdms y .csv en DATA_DIR
    
    Returns:
        tuple: (cantidad_procesada, mensaje_estado)
    """
    files = [f for f in os.listdir(DATA_DIR) if not f.startswith('.')]
    
    if not files:
        return 0, "No se encontraron archivos en la carpeta 'datos/'"
    
    st.toast("Iniciando procesamiento de archivos...", icon="⏳")
    processed_count = 0
    
    for filename in files:
        input_path = os.path.join(DATA_DIR, filename)
        base_name = os.path.splitext(filename)[0]
        
        # Determinar tipo de archivo y carpeta destino
        target_dir, is_static = _get_target_directory(filename)
        
        if target_dir is None:
            continue  # Archivo no soportado
        
        # Convertir archivo al formato CSV
        original_csv = os.path.join(target_dir, f"{base_name}_original.csv")
        _convert_file(filename, input_path, original_csv, target_dir)
        
        # Limpiar y normalizar el CSV
        if os.path.exists(original_csv):
            modified_csv = os.path.join(target_dir, f"{base_name}_modificado.csv")
            
            try:
                if is_static:
                    clean_data_csv(original_csv, modified_csv, is_static)
                else:
                    clean_dynamic_data(original_csv, modified_csv)
                
                processed_count += 1
                st.toast(f"✅ Procesado: {filename}")
                
            except Exception as e:
                st.error(f"Error en limpieza de {filename}: {e}")
    
    return processed_count, "¡Proceso completado!"


def _get_target_directory(filename):
    """
    Determina el directorio destino según la extensión del archivo
    
    Returns:
        tuple: (directorio_destino, es_estatico)
    """
    if filename.endswith('.dat') or filename.endswith('.csv'):
        return STATIC_DIR, True
    elif filename.endswith('.tdms'):
        return DYNAMIC_DIR, False
    return None, None


def _convert_file(filename, input_path, output_path, target_dir):
    """Convierte archivos .dat, .tdms o .csv a formato CSV normalizado"""
    os.makedirs(target_dir, exist_ok=True)
    
    if filename.endswith('.dat'):
        convert_dat_to_csv(input_path, output_path)
    elif filename.endswith('.tdms'):
        convert_tdms_to_csv(input_path, output_path)
    elif filename.endswith('.csv'):
        shutil.copy(input_path, output_path)


@st.cache_data(show_spinner="Cargando datos procesados...")
def load_processed_data(folder_list):
    """
    Carga y unifica todos los archivos _modificado.csv de las carpetas especificadas
    
    Args:
        folder_list: Lista de rutas de carpetas a procesar
        
    Returns:
        DataFrame unificado con todos los datos procesados
    """
    all_dfs = []
    
    for folder in folder_list:
        for root, _, files in os.walk(folder):
            for file in files:
                if file.endswith('_modificado.csv'):
                    filepath = os.path.join(root, file)
                    df = _load_single_csv(filepath, file, root)
                    if df is not None:
                        all_dfs.append(df)
    
    return pd.concat(all_dfs, ignore_index=True) if all_dfs else pd.DataFrame()


def _load_single_csv(filepath, filename, root):
    """
    Carga un archivo CSV individual y agrega metadatos
    
    Returns:
        DataFrame procesado o None si hay error
    """
    try:
        df = pd.read_csv(filepath)
        df['Origen_Archivo'] = filename
        
        # Clasificar tipo de prueba según la carpeta
        if STATIC_DIR in root:
            df['Tipo_Prueba'] = 'Estática'
        elif DYNAMIC_DIR in root:
            df['Tipo_Prueba'] = 'Dinámica'
        
        # Normalizar columna RECORD
        if 'RECORD' in df.columns:
            df['RECORD'] = pd.to_numeric(df['RECORD'], errors='coerce')
        else:
            st.warning(f"Archivo {filename} no tiene columna RECORD")
        
        # Procesar timestamp
        df = _normalize_timestamp(df, filename)
        
        return df
        
    except Exception as e:
        st.error(f"Error al cargar {filepath}: {e}")
        return None


def _normalize_timestamp(df, filename):
    """Normaliza la columna de timestamp a formato datetime"""
    time_col = next((col for col in df.columns if 'timestamp' in col.lower()), None)
    
    if time_col:
        if time_col != 'TIMESTAMP':
            df.rename(columns={time_col: 'TIMESTAMP'}, inplace=True)
        
        # Intentar diferentes formatos de fecha
        try:
            df['TIMESTAMP'] = pd.to_datetime(df['TIMESTAMP'], errors='coerce')
            
            # Si falló la conversión, crear timestamp artificial
            if df['TIMESTAMP'].isna().all() and 'RECORD' in df.columns:
                df['TIMESTAMP'] = pd.date_range(start='2024-01-01', periods=len(df), freq='1S')
                
        except Exception as e:
            st.warning(f"Error al procesar TIMESTAMP en {filename}: {e}")
    
    return df


# ============================================================================
# FUNCIONES DE VISUALIZACIÓN
# ============================================================================

def _plot_strain_data(df, record_range):
    """Genera gráfico de Strain vs RECORD"""
    strain_cols = [col for col in df.columns 
                   if 'Strain' in col and df[col].dtype in ['float64', 'int64']]
    
    if not strain_cols:
        st.info("No se encontraron columnas de Strain")
        return
    
    st.subheader("Tensión Superficial (Strain) vs. RECORD")
    
    selected = st.multiselect(
        "Seleccionar Galgas:",
        options=strain_cols,
        default=strain_cols,
        key='strain_select'
    )
    
    if selected:
        plot_data = df[['RECORD'] + selected].sort_values(by='RECORD')
        df_melted = plot_data.melt(
            id_vars=['RECORD'],
            value_vars=selected,
            var_name='Galgas',
            value_name='Microstrain'
        )
        
        chart = alt.Chart(df_melted).mark_line(size=1).encode(
            x=alt.X('RECORD:Q', title='Índice de Muestra',
                   scale=alt.Scale(domain=record_range)),
            y=alt.Y('Microstrain:Q', title='Strain (µε)'),
            color='Galgas:N',
            tooltip=['RECORD:Q', 'Galgas:N', 'Microstrain:Q']
        ).properties(
            title='Strain vs. RECORD',
            width='container',
            height=400
        ).interactive()
        
        st.altair_chart(chart, use_container_width=True)
        
        max_strain = df[selected].max().max()
        st.metric("Máximo Strain Registrado (µε)", f"{max_strain:.2f}")
    else:
        st.info("Seleccione al menos una galga")


def _plot_lvdt_data(df, record_range, key_suffix=''):
    """Genera gráfico de LVDT (Desplazamiento) vs RECORD"""
    lvdt_cols = [col for col in df.columns 
                 if (col.startswith('Disp') or col.startswith('LV')) 
                 and df[col].dtype in ['float64', 'int64']]
    
    if not lvdt_cols:
        st.info("No se encontraron columnas de Desplazamiento")
        return
    
    st.subheader("Desplazamiento (LVDT) vs. RECORD")
    
    selected = st.multiselect(
        "Seleccionar Sensores LVDT:",
        options=lvdt_cols,
        default=lvdt_cols,
        key=f'lvdt_select{key_suffix}'
    )
    
    if selected:
        plot_data = df[['RECORD'] + selected].sort_values(by='RECORD')
        df_melted = plot_data.melt(
            id_vars=['RECORD'],
            value_vars=selected,
            var_name='Sensor',
            value_name='Desplazamiento'
        )
        
        chart = alt.Chart(df_melted).mark_line(size=1).encode(
            x=alt.X('RECORD:Q', title='Índice de Muestra',
                   scale=alt.Scale(domain=record_range)),
            y=alt.Y('Desplazamiento:Q', title='Desplazamiento (mm)'),
            color='Sensor:N',
            tooltip=['RECORD:Q', 'Sensor:N', 'Desplazamiento:Q']
        ).properties(
            title='Desplazamiento vs. RECORD',
            width='container',
            height=400
        ).interactive()
        
        st.altair_chart(chart, use_container_width=True)
    else:
        st.info("Seleccione al menos un sensor LVDT")


def _plot_accelerometer_data(df, record_range):
    """Genera gráfico de Aceleración vs RECORD"""
    accel_cols = [col for col in df.columns if col.startswith('A21')]
    
    if not accel_cols:
        st.info("No se encontraron columnas de Aceleración")
        return
    
    st.subheader("Aceleración vs. RECORD")
    
    selected = st.multiselect(
        "Seleccionar Acelerómetros:",
        options=accel_cols,
        default=accel_cols,
        key='accel_select'
    )
    
    if selected:
        plot_data = df[['RECORD'] + selected].sort_values(by='RECORD')
        df_melted = plot_data.melt(
            id_vars=['RECORD'],
            value_vars=selected,
            var_name='Sensor',
            value_name='Aceleración'
        )
        
        chart = alt.Chart(df_melted).mark_line(size=1).encode(
            x=alt.X('RECORD:Q', title='Índice de Muestra',
                   scale=alt.Scale(domain=record_range)),
            y=alt.Y('Aceleración:Q', title='Aceleración (g)'),
            color='Sensor:N',
            tooltip=['RECORD:Q', 'Sensor:N', 'Aceleración:Q']
        ).properties(
            title='Aceleración vs. RECORD',
            width='container',
            height=400
        ).interactive()
        
        st.altair_chart(chart, use_container_width=True)
    else:
        st.info("Seleccione al menos un acelerómetro")


# ============================================================================
# INTERFAZ DE USUARIO - BARRA LATERAL
# ============================================================================

st.sidebar.title("Navegación del Sistema")
page_selection = st.sidebar.radio("Ir a:", ("Panel de Control", "Dashboard de Datos"))

st.sidebar.markdown("---")
st.sidebar.write(f"📁 Cargar archivos en: `{os.path.join(os.getcwd(), 'datos')}`")
st.sidebar.write(f"📊 Archivos procesados: `{PROCESSED_DIR}/`")


# ============================================================================
# PÁGINA 1: PANEL DE CONTROL
# ============================================================================

if page_selection == "Panel de Control":
    st.title("Panel de Control y Procesamiento de Datos ⚙️")
    st.markdown("Convierte y limpia archivos `.dat`, `.tdms` y `.csv`")
    
    col1, col2 = st.columns(2)
    
    # Columna izquierda: Botón de procesamiento
    with col1:
        with st.container(border=True):
            st.subheader("🔄 Procesar Datos")
            st.markdown("Coloque sus archivos en la carpeta `./datos` antes de procesar")
            
            if st.button("🟢 CONVERTIR Y LIMPIAR DATOS", 
                        type="primary", 
                        use_container_width=True):
                with st.spinner("Procesando archivos..."):
                    count, message = run_conversion_and_cleaning()
                    st.cache_data.clear()
                    
                    if count > 0:
                        st.success(f"{message} Procesados: {count} archivos")
                    else:
                        st.warning(message)
    
    # Columna derecha: Información del sistema
    with col2:
        with st.container(border=True):
            st.subheader("📊 Información del Sistema")
            st.info("**Formatos soportados:**\n- .dat\n- .tdms\n- .csv")
            
            if os.path.exists(DATA_DIR):
                archivos = [f for f in os.listdir(DATA_DIR) if not f.startswith('.')]
                st.metric("Archivos por procesar", len(archivos))
                
                if archivos:
                    st.write("**Archivos encontrados:**")
                    for archivo in archivos[:3]:
                        st.code(archivo)
                    if len(archivos) > 3:
                        st.write(f"... y {len(archivos) - 3} más")
                else:
                    st.write("✓ No hay archivos pendientes")
            else:
                st.error("⚠️ Carpeta de datos no encontrada")


# ============================================================================
# PÁGINA 2: DASHBOARD DE VISUALIZACIÓN
# ============================================================================

elif page_selection == "Dashboard de Datos":
    st.title("Dashboard Interactivo de Monitoreo Estructural 📊")
    st.markdown("Visualice datos de Strain, LVDT y Acelerómetros")
    
    # Botón para recargar datos
    if st.button("🔄 Recargar Datos del Disco"):
        st.cache_data.clear()
        st.rerun()
    
    # Cargar todos los datos procesados
    all_data = load_processed_data([STATIC_DIR, DYNAMIC_DIR])
    
    # Validar datos cargados
    if all_data.empty:
        st.warning("No hay datos procesados disponibles")
    elif 'RECORD' not in all_data.columns:
        st.error("Columna 'RECORD' no encontrada en los datos")
    else:
        all_data.dropna(subset=['RECORD'], inplace=True)
        
        # Filtros globales en la barra lateral
        st.sidebar.header("Filtros del Dashboard")
        origins = sorted(all_data['Origen_Archivo'].unique())
        selected_origins = st.sidebar.multiselect(
            "Filtrar por Archivo:",
            options=origins,
            default=origins
        )
        
        df_filtered = all_data[all_data['Origen_Archivo'].isin(selected_origins)]
        
        if df_filtered.empty:
            st.warning("No hay datos para los filtros seleccionados")
        else:
            # Crear pestañas para datos estáticos y dinámicos
            tab1, tab2 = st.tabs(["Pruebas Estáticas (Strain)", "Pruebas Dinámicas (Aceleración)"])
            
            # ================================================================
            # PESTAÑA 1: DATOS ESTÁTICOS (Strain y Desplazamiento)
            # ================================================================
            with tab1:
                st.header("Análisis de Datos Estáticos")
                
                df_static = df_filtered[df_filtered['Tipo_Prueba'] == 'Estática'].copy()
                
                if df_static.empty:
                    st.info("No hay datos estáticos disponibles")
                else:
                    # Slider para rango de muestras
                    min_rec = int(df_static['RECORD'].min())
                    max_rec = int(df_static['RECORD'].max())
                    
                    record_range = st.slider(
                        "Rango de Muestras (RECORD):",
                        min_value=min_rec,
                        max_value=max_rec,
                        value=(min_rec, max_rec),
                        key='slider_static'
                    )
                    
                    df_static = df_static[
                        (df_static['RECORD'] >= record_range[0]) & 
                        (df_static['RECORD'] <= record_range[1])
                    ]
                    
                    st.info(f"📊 Muestras en el rango: {len(df_static):,}")
                    
                    # Gráfico 1: Strain
                    _plot_strain_data(df_static, record_range)
                    
                    st.markdown("---")
                    
                    # Gráfico 2: LVDT (Desplazamiento)
                    _plot_lvdt_data(df_static, record_range, key_suffix='_static')
            
            # ================================================================
            # PESTAÑA 2: DATOS DINÁMICOS (Aceleración y Desplazamiento)
            # ================================================================
            with tab2:
                st.header("Análisis de Datos Dinámicos")
                
                df_dynamic = df_filtered[df_filtered['Tipo_Prueba'] == 'Dinámica'].copy()
                
                if df_dynamic.empty:
                    st.info("No hay datos dinámicos disponibles")
                else:
                    # Slider para rango de muestras
                    min_rec = int(df_dynamic['RECORD'].min())
                    max_rec = int(df_dynamic['RECORD'].max())
                    
                    record_range = st.slider(
                        "Rango de Muestras (RECORD):",
                        min_value=min_rec,
                        max_value=max_rec,
                        value=(min_rec, max_rec),
                        key='slider_dynamic'
                    )
                    
                    df_dynamic = df_dynamic[
                        (df_dynamic['RECORD'] >= record_range[0]) & 
                        (df_dynamic['RECORD'] <= record_range[1])
                    ]
                    
                    st.info(f"📊 Muestras en el rango: {len(df_dynamic):,}")
                    
                    # Gráfico 1: Acelerómetros
                    _plot_accelerometer_data(df_dynamic, record_range)
                    
                    st.markdown("---")
                    
                    # Gráfico 2: LVDT (Desplazamiento)
                    _plot_lvdt_data(df_dynamic, record_range, key_suffix='_dynamic')