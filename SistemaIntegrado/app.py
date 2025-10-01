# app.py
import streamlit as st
import pandas as pd
import numpy as np
import os
import shutil
import altair as alt

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
        return 0, "No se encontraron archivos en la carpeta 'datos/' para procesar."

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

# app.py - ACTUALIZAR FUNCIONES DE CARGA DE DATOS
@st.cache_data(show_spinner="Cargando datos procesados...")
def load_processed_data(folder_list):
    """
    Carga, unifica y limpia los archivos _modificado.csv de una lista de carpetas.
    Asegura que las columnas de RECORD y TIMESTAMP se manejen correctamente.
    """
    all_dfs = []
    RECORD_COL = 'RECORD'
    
    # Itera sobre la lista de carpetas (STATIC y DYNAMIC)
    for data_folder in folder_list:
        for root, _, files in os.walk(data_folder):
            for file in files:
                if file.endswith('_modificado.csv'):
                    filepath = os.path.join(root, file)
                    try:
                        df = pd.read_csv(filepath)
                        df['Origen_Archivo'] = file 
                        
                        # Manejo de RECORD (Necesario para eje X)
                        if RECORD_COL in df.columns:
                            # Forzar la conversión a numérico. Los errores (NAN, etc.) serán NaN.
                            df[RECORD_COL] = pd.to_numeric(df[RECORD_COL], errors='coerce')

                        # Manejo de TIMESTAMP (Para futuro uso o indexación)
                        time_col = next((col for col in df.columns if 'timestamp' in col.lower() or 'time' in col.lower()), None)
                        if time_col:
                            try:
                                # Intenta parsear con microsegundos, si falla usa 'mixed'
                                df[time_col] = pd.to_datetime(df[time_col], format="%Y-%m-%d %H:%M:%S.%f", errors='coerce')
                                if df[time_col].isna().all():
                                    df[time_col] = pd.to_datetime(df[time_col], format='mixed', errors='coerce')
                                df.set_index(time_col, inplace=True)
                            except Exception:
                                # Si falla, deja el índice como está
                                pass 
                            
                        all_dfs.append(df)
                    except Exception as e:
                        st.error(f"Error al cargar {filepath}: {e}")
    
    if all_dfs:
        # Concatenar todos los DataFrames y rellenar con NaN donde falte una columna
        unified_df = pd.concat(all_dfs, ignore_index=True)
        return unified_df
    return pd.DataFrame() 

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
                    st.cache_data.clear() # Limpiar caché para recargar datos en el dashboard
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

# app.py - SECCIÓN Dashboard de Datos (MODIFICADO)

elif page_selection == "Dashboard de Datos":
    st.title("Dashboard Interactivo de Monitoreo Estructural 📊")
    st.markdown("Visualice las mediciones de Strain y Aceleración del puente.")

    # Botón de Recarga Manual
    if st.button("🔄 Recargar Datos del Disco"):
        st.cache_data.clear()
        st.rerun() # Forzar el re-renderizado de toda la página
    
    # 1. Cargar datos de ambas carpetas
    all_processed_data = load_processed_data([STATIC_DIR, DYNAMIC_DIR])

    # 2. Verificación de archivos encontrados (Ahora en la carga)
    found_files_static = [f for f in os.listdir(STATIC_DIR) if f.endswith('_modificado.csv')]
    st.sidebar.markdown("### Archivos Encontrados (Estaticos):")
    st.sidebar.write(found_files_static)
    # -------------------------------------------------------------------
    # --- Comprobación de existencia de datos y la columna RECORD ---
    # -------------------------------------------------------------------
    
    if all_processed_data.empty:
        st.warning("No hay datos procesados disponibles para mostrar en el dashboard.")
    elif 'RECORD' not in all_processed_data.columns:
        st.error("La columna 'RECORD' (índice de muestra) es necesaria para los gráficos estáticos y no se encuentra.")
    else:
        # Asegurarse de que RECORD esté limpio para el eje X
        all_processed_data.dropna(subset=['RECORD'], inplace=True)
        
        # --- FILTROS GLOBALES ---
        st.sidebar.header("Filtros del Dashboard")
        
        # Filtro de Origen de Archivo (para ver solo CR3000 o ESP32)
        origins = sorted(all_processed_data['Origen_Archivo'].unique())
        selected_origin = st.sidebar.multiselect(
            "Filtrar por Archivo Origen:",
            options=origins,
            default=origins
        )
        
        df_filtered = all_processed_data[all_processed_data['Origen_Archivo'].isin(selected_origin)]
        
        if df_filtered.empty:
            st.warning("No hay datos para la selección actual de filtros.")
        else:
            # --- Pestañas para Clasificación (Estatica vs Dinamica) ---
            tab1, tab2 = st.tabs(["Pruebas Estáticas (Strain)", "Pruebas Dinámicas (Aceleración)"])

            # Pestaña 1: Pruebas Estáticas (RECORD vs STRAIN)
            with tab1:
                st.header("Tensión Superficial (Strain)")
                
                # Identificar todas las columnas de Strain numéricas
                strain_cols = [col for col in df_filtered.columns if 'Strain' in col and df_filtered[col].dtype in ['float64', 'int64']]
                
                if strain_cols:
                    selected_strain = st.multiselect(
                        "Seleccionar Galgas:",
                        options=strain_cols,
                        default=strain_cols[0] if strain_cols else [],
                        key='strain_select'
                    )
                    
                    if selected_strain:
                        # Crear la lista de datos a graficar: RECORD + Strain seleccionados
                        cols_to_plot = ['RECORD'] + selected_strain
                        plot_data = df_filtered[cols_to_plot].sort_values(by='RECORD')

                        st.subheader("Gráfico: RECORD vs. Strain")
                        
                        # Usar st.line_chart con el DataFrame, especificando el eje X.
                        # NOTA: st.line_chart usa el índice, por lo que usaremos Altair para mayor control.
                        import altair as alt
                        
                        # Derretir el DataFrame para facilitar la graficación de múltiples series en Altair
                        df_melted = plot_data.melt(
                            id_vars=['RECORD'],
                            value_vars=selected_strain,
                            var_name='Galgas',
                            value_name='Microstrain'
                        )

                        chart = alt.Chart(df_melted).mark_line().encode(
                            x=alt.X('RECORD', title='Índice de Muestra (RECORD)'),
                            y=alt.Y('Microstrain', title='Strain (microstrain)'),
                            color='Galgas',
                            tooltip=['RECORD', 'Galgas', 'Microstrain']
                        ).properties(
                            title='Strain vs. RECORD'
                        ).interactive() # Permite hacer zoom y pan
                        
                        st.altair_chart(chart, use_container_width=True)
                        
                        # Métrica clave
                        max_val = df_filtered[selected_strain].max().max()
                        st.metric("Máximo Strain Registrado (µε)", f"{max_val:.2f}")
                    else:
                        st.info("Selecciona al menos una Galga Extensiométrica para visualizar.")
                else:
                    st.info("No se encontraron columnas de Strain en los datos.")

            # Pestaña 2: Pruebas Dinámicas (Mantener por si usa Acelerómetros)
            with tab2:
                # ... Lógica para Acelerómetros vs. TIMESTAMP o RECORD (depende de la prueba) ...
                st.info("Esta sección es para datos dinámicos como Aceleración (vs. TIMESTAMP).")
                # Aquí podrías usar una lógica similar, pero graficando vs. TIMESTAMP.
