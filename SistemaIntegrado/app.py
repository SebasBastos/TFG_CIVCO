# app.py
import streamlit as st
import pandas as pd
import numpy as np
import os
import shutil

# Importa tus funciones de procesamiento desde el paquete data_converters
from data_converters.convert_dat2csv import convert_dat_to_csv
from data_converters.convert_tdms2csv import convert_tdms_to_csv
from data_converters.procesar_archivos import clean_data_csv

# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(
    page_title="Sistema Integrado de Monitoreo Estructural",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- RUTAS GLOBALES (relativas al directorio donde se ejecuta app.py) ---
DATA_DIR = "datos"
PROCESSED_DIR = "archivos_procesados"
STATIC_DIR = os.path.join(PROCESSED_DIR, "Pruebas_Estaticas")
DYNAMIC_DIR = os.path.join(PROCESSED_DIR, "Pruebas_Dinamicas")

# Asegurar que los directorios existan
for d in [PROCESSED_DIR, STATIC_DIR, DYNAMIC_DIR]:
    if not os.path.exists(d):
        os.makedirs(d)

# --- FUNCIONES DE PROCESAMIENTO (Del anterior main_processor.py) ---
def run_conversion_and_cleaning():
    """
    Ejecuta la conversión, clasificación y limpieza de todos los archivos
    en el directorio DATA_DIR.
    """
    processed_count = 0
    
    files_to_process = [f for f in os.listdir(DATA_DIR) if not f.startswith('.')] # Ignorar archivos ocultos
    if not files_to_process:
        return 0, "No se encontraron archivos en la carpeta 'data/' para procesar."

    st.toast("Iniciando procesamiento de archivos...", icon="⏳")

    for filename in files_to_process:
        input_filepath = os.path.join(DATA_DIR, filename)
        base_name = os.path.splitext(filename)[0]
        
        target_dir = None
        is_static = False
        original_csv_path = None
        
        if filename.endswith(('.dat', '.csv')): 
            target_dir = STATIC_DIR
            is_static = True
            if filename.endswith('.dat'):
                original_csv_path = os.path.join(target_dir, f"{base_name}_original.csv")
                convert_dat_to_csv(input_filepath, original_csv_path)
            elif filename.endswith('.csv'): 
                original_csv_path = os.path.join(target_dir, f"{base_name}_original.csv")
                shutil.copy(input_filepath, original_csv_path)
        
        elif filename.endswith('.tdms'): 
            target_dir = DYNAMIC_DIR
            is_static = False
            original_csv_path = os.path.join(target_dir, f"{base_name}_original.csv")
            convert_tdms_to_csv(input_filepath, original_csv_path)
        else:
            st.warning(f"Ignorando '{filename}': formato no soportado.")
            continue

        if original_csv_path and os.path.exists(original_csv_path):
            modified_csv_path = os.path.join(target_dir, f"{base_name}_modificado.csv")
            clean_data_csv(original_csv_path, modified_csv_path, is_static)
            processed_count += 1
            st.toast(f"✅ Procesado: {filename}")
            
    return processed_count, "¡Proceso de conversión y limpieza completado!"

# --- FUNCIONES DE CARGA DE DATOS PARA EL DASHBOARD ---

@st.cache_data(show_spinner="Cargando datos procesados...")
def load_processed_data(data_folder):
    """
    Carga y unifica todos los archivos _modificado.csv de una carpeta.
    """
    all_dfs = []
    for root, _, files in os.walk(data_folder):
        for file in files:
            if file.endswith('_modificado.csv'):
                filepath = os.path.join(root, file)
                try:
                    df = pd.read_csv(filepath)
                    # Añadir columna de origen para diferenciar si es necesario
                    df['Origen_Archivo'] = file 
                    # Intentar convertir una columna 'Timestamp' o 'TIME' si existe
                    time_col = next((col for col in df.columns if 'time' in col.lower()), None)
                    if time_col:
                        df[time_col] = pd.to_datetime(df[time_col])
                        df.set_index(time_col, inplace=True)
                        
                    all_dfs.append(df)
                except Exception as e:
                    st.error(f"Error al cargar {filepath}: {e}")
    
    if all_dfs:
        # Intentar concatenar, manejando columnas diferentes
        # Considera cómo unificar DataFrames con diferentes sensores.
        # Una opción simple es unir por índice de tiempo si los hay.
        # Para POC, solo concatenaremos y llenaremos NaN.
        unified_df = pd.concat(all_dfs, ignore_index=True) # O usar join por índice si ya está en time
        unified_df.sort_index(inplace=True)
        return unified_df
    return pd.DataFrame() # Retorna un DataFrame vacío si no hay datos

# --- BARRA LATERAL (SIDEBAR) PARA NAVEGACIÓN ---

st.sidebar.title("Navegación del Sistema")

# Selector de página
page_selection = st.sidebar.radio(
    "Ir a:",
    ("Panel de Control", "Dashboard de Datos")
)

st.sidebar.markdown("---")
st.sidebar.write(f"Ruta para cargar archivos: \n `{os.path.join(os.getcwd(), 'datos')}`")
st.sidebar.write(f"Ruta de Archivos Procesados: `{PROCESSED_DIR}/`")

# --- CONTENIDO SELECCIÓN PANEL DE CONTROL ---

if page_selection == "Panel de Control":
    st.title("Panel de Control y Procesamiento de Datos ⚙️")
    st.markdown("Utilice esta sección para convertir y limpiar sus archivos de datos brutos.")
    
    col1, col2 = st.columns(2)
    
    with col1:
        with st.container(border=True):
            st.subheader("🔄 Procesar Datos")
            st.markdown("Asegure que sus archivos `.dat`, `.tdms` o `.csv` estén en la carpeta `./datos` antes de iniciar el procesamiento.")
            
            if st.button("🟢 CONVERTIR Y LIMPIAR DATOS", 
                        type="primary", 
                        use_container_width=True,
                        help="Haga clic para procesar todos los archivos en la carpeta de datos"):
                with st.spinner("Procesando archivos..."):
                    count, message = run_conversion_and_cleaning()
                    if count > 0:
                        st.success(f"{message} Se procesaron {count} archivos.")
                        #st.balloons()
                    else:
                        st.warning(message)
    
    with col2:
        with st.container(border=True):
            st.subheader("📊 Información del Sistema")
            st.info("""
            **Formatos soportados:**
            - .dat
            - .tdms  
            - .csv
            """)
            
            st.write("**Estado actual:**")
            if os.path.exists(DATA_DIR):
                archivos = os.listdir(DATA_DIR)
                st.metric("Archivos por procesar", len(archivos))
                if archivos:
                    st.write("**Archivos encontrados:**")
                    for archivo in archivos[:3]:
                        st.code(archivo)
                else:
                    st.write("No hay archivos por procesar")
            else:
                st.error("Carpeta de datos no encontrada")

# --- CONTENIDO SELECCIÓN DASHBOARD ---

elif page_selection == "Dashboard de Datos":
    st.title("Dashboard Interactivo 📊")
    st.markdown("Visualice las mediciones de Strain y Aceleración del puente.")

    # Cargar datos del directorio procesado
    # Unificamos ambos directorios para el dashboard (ajustar si prefieres separarlos)
    all_processed_data = pd.DataFrame()
    
    static_data = load_processed_data(STATIC_DIR)
    dynamic_data = load_processed_data(DYNAMIC_DIR)

    if not static_data.empty:
        all_processed_data = pd.concat([all_processed_data, static_data])
    if not dynamic_data.empty:
        all_processed_data = pd.concat([all_processed_data, dynamic_data])
    
    if all_processed_data.empty:
        st.warning("No hay datos procesados disponibles para mostrar en el dashboard. Por favor, procese los archivos primero.")
    else:
        # --- FILTROS GLOBALES (Ej. por fecha) ---
        st.sidebar.header("Filtros del Dashboard")
        
        # Asumiendo que el índice es de tiempo
        min_date = all_processed_data.index.min()
        max_date = all_processed_data.index.max()
        
        date_range = st.sidebar.slider(
            "Seleccionar Rango de Fechas:",
            value=(min_date.to_pydatetime(), max_date.to_pydatetime()),
            format="YYYY/MM/DD",
            key='dashboard_date_filter'
        )
        
        start_date, end_date = pd.to_datetime(date_range[0]), pd.to_datetime(date_range[1])
        df_filtered = all_processed_data[(all_processed_data.index >= start_date) & (all_processed_data.index <= end_date)]

        if df_filtered.empty:
            st.warning("No hay datos para el rango de fechas seleccionado.")
        else:
            # --- Pestañas para Clasificación (Estatica vs Dinamica) ---
            tab1, tab2 = st.tabs(["Pruebas Estáticas (Strain)", "Pruebas Dinámicas (Aceleración)"])

            # Pestaña 1: Pruebas Estáticas
            with tab1:
                st.header("Tensión Superficial (Strain)")
                strain_cols = [col for col in df_filtered.columns if 'Strain' in col and df_filtered[col].dtype in ['float64', 'int64']]
                
                if strain_cols:
                    selected_strain = st.multiselect(
                        "Seleccionar Galgas:",
                        options=strain_cols,
                        default=strain_cols[0] if strain_cols else [],
                        key='strain_select'
                    )
                    
                    if selected_strain:
                        st.line_chart(df_filtered[selected_strain], use_container_width=True)
                        st.metric("Máximo Strain Registrado (µε)", f"{df_filtered[selected_strain].max().max():.2f}")
                    else:
                        st.info("Selecciona al menos una Galga Extensiométrica para visualizar.")
                else:
                    st.info("No se encontraron columnas de Strain en los datos.")

            # Pestaña 2: Pruebas Dinámicas
            with tab2:
                st.header("Vibración y Aceleración")
                accel_cols = [col for col in df_filtered.columns if ('Aceleracion' in col or 'Accel' in col) and df_filtered[col].dtype in ['float64', 'int64']]

                if accel_cols:
                    selected_accel = st.multiselect(
                        "Seleccionar Acelerómetros:",
                        options=accel_cols,
                        default=accel_cols[0] if accel_cols else [],
                        key='accel_select'
                    )
                    
                    if selected_accel:
                        st.line_chart(df_filtered[selected_accel], use_container_width=True)
                        st.metric("Máxima Amplitud de Aceleración Absoluta (g)", f"{df_filtered[selected_accel].abs().max().max():.3f}")
                    else:
                        st.info("Selecciona al menos un Acelerómetro para visualizar.")
                else:
                    st.info("No se encontraron columnas de Aceleración en los datos.")