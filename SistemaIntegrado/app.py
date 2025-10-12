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
from data_converters.procesar_archivos import clean_data_csv, clean_dynamic_data

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

# --- FUNCIONES DE PROCESAMIENTO ---
def run_conversion_and_cleaning():
    """
    Ejecuta la conversión, clasificación y limpieza de todos los archivos
    en el directorio DATA_DIR.
    """
    processed_count = 0
    
    files_to_process = [f for f in os.listdir(DATA_DIR) if not f.startswith('.')]
    if not files_to_process:
        return 0, "No se encontraron archivos en la carpeta 'datos/' para procesar."

    st.toast("Iniciando procesamiento de archivos...", icon="⏳")

    for filename in files_to_process:
        input_filepath = os.path.join(DATA_DIR, filename)
        base_name = os.path.splitext(filename)[0]
        
        target_dir = None
        is_static = False
        original_csv_path = None
        
        if filename.endswith('.dat'): 
            target_dir = STATIC_DIR
            is_static = True
            original_csv_path = os.path.join(target_dir, f"{base_name}_original.csv")
            convert_dat_to_csv(input_filepath, original_csv_path)
        
        elif filename.endswith('.tdms'): 
            target_dir = DYNAMIC_DIR
            is_static = False
            original_csv_path = os.path.join(target_dir, f"{base_name}_original.csv")
            convert_tdms_to_csv(input_filepath, original_csv_path)
            
        elif filename.endswith('.csv'):
            # PARA CSV DEL ESP32 - siempre van a estáticos
            target_dir = STATIC_DIR
            is_static = True
            original_csv_path = os.path.join(target_dir, f"{base_name}_original.csv")
            
            # Asegurar que el directorio existe
            os.makedirs(target_dir, exist_ok=True)
            
            # Copiar el archivo CSV original
            shutil.copy(input_filepath, original_csv_path)
        if original_csv_path and os.path.exists(original_csv_path):
            modified_csv_path = os.path.join(target_dir, f"{base_name}_modificado.csv")

            try:
                if is_static:
                    clean_data_csv(original_csv_path, modified_csv_path, is_static)
                else:
                    clean_dynamic_data(original_csv_path, modified_csv_path)

                processed_count += 1
                st.toast(f"✅ Procesado: {filename}")
            except Exception as e:
                st.error(f"Error en limpieza de {filename}: {e}")
                continue
            
    return processed_count, "¡Proceso de conversión y limpieza completado!"
@st.cache_data(show_spinner="Cargando datos procesados...")
def load_processed_data(folder_list):
    """
    Carga, unifica y limpia los archivos _modificado.csv de una lista de carpetas.
    Mejorado para manejar diferentes formatos de timestamp.
    """
    all_dfs = []
    RECORD_COL = 'RECORD'
    
    for data_folder in folder_list:
        for root, _, files in os.walk(data_folder):
            for file in files:
                if file.endswith('_modificado.csv'):
                    filepath = os.path.join(root, file)
                    try:
                        df = pd.read_csv(filepath)
                        df['Origen_Archivo'] = file 
                        
                        # Determinar tipo de prueba según la carpeta
                        if STATIC_DIR in root:
                            df['Tipo_Prueba'] = 'Estática'
                        elif DYNAMIC_DIR in root:
                            df['Tipo_Prueba'] = 'Dinámica'
                        
                        # Asegurar que RECORD sea numérico
                        if RECORD_COL in df.columns:
                            df[RECORD_COL] = pd.to_numeric(df[RECORD_COL], errors='coerce')
                        else:
                            st.warning(f"Archivo {file} no tiene columna RECORD")

                        # Manejo robusto de timestamp para diferentes formatos
                        time_col = next((col for col in df.columns if 'timestamp' in col.lower()), None)
                        
                        if time_col:
                            if time_col != 'TIMESTAMP':
                                df.rename(columns={time_col: 'TIMESTAMP'}, inplace=True)
                            
                            # Intentar diferentes formatos de timestamp
                            try:
                                df['TIMESTAMP'] = pd.to_datetime(df['TIMESTAMP'], format="%Y-%m-%d %H:%M:%S.%f", errors='coerce')
                                if df['TIMESTAMP'].isna().all():
                                    df['TIMESTAMP'] = pd.to_datetime(df['TIMESTAMP'], format="%Y-%m-%d %H:%M:%S", errors='coerce')
                                if df['TIMESTAMP'].isna().all():
                                    df['TIMESTAMP'] = pd.to_datetime(df['TIMESTAMP'], format='mixed', errors='coerce')
                            except Exception as e:
                                st.warning(f"No se pudo convertir TIMESTAMP en {file}: {e}")
                                # Si falla, crear un timestamp artificial basado en RECORD
                                if RECORD_COL in df.columns:
                                    df['TIMESTAMP'] = pd.date_range(start='2024-01-01', periods=len(df), freq='1S')
                            
                        all_dfs.append(df)
                    except Exception as e:
                        st.error(f"Error al cargar {filepath}: {e}")
    
    if all_dfs:
        unified_df = pd.concat(all_dfs, ignore_index=True)
        return unified_df
    return pd.DataFrame()

# --- BARRA LATERAL ---
st.sidebar.title("Navegación del Sistema")

page_selection = st.sidebar.radio(
    "Ir a:",
    ("Panel de Control", "Dashboard de Datos")
)

st.sidebar.markdown("---")
st.sidebar.write(f"Ruta para cargar archivos: \n `{os.path.join(os.getcwd(), 'datos')}`")
st.sidebar.write(f"Ruta de Archivos Procesados: `{PROCESSED_DIR}/`")

# --- PANEL DE CONTROL ---
if page_selection == "Panel de Control":
    st.title("Panel de Control y Procesamiento de Datos ⚙️")
    st.markdown("Utilice esta sección para convertir y limpiar sus archivos de datos brutos.")
    
    col1, col2 = st.columns(2)
    
    with col1:
        with st.container(border=True):
            st.subheader("📄 Procesar Datos")
            st.markdown("Asegure que sus archivos `.dat`, `.tdms` o `.csv` estén en la carpeta `./datos` antes de iniciar el procesamiento.")
            
            if st.button("🟢 CONVERTIR Y LIMPIAR DATOS", 
                        type="primary", 
                        use_container_width=True,
                        help="Haga clic para procesar todos los archivos en la carpeta de datos"):
                with st.spinner("Procesando archivos..."):
                    count, message = run_conversion_and_cleaning()
                    st.cache_data.clear()
                    if count > 0:
                        st.success(f"{message} Se procesaron {count} archivos.")
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

# --- DASHBOARD ---
elif page_selection == "Dashboard de Datos":
    st.title("Dashboard Interactivo de Monitoreo Estructural 📊")
    st.markdown("Visualice las mediciones de Strain y Aceleración del puente.")

    if st.button("🔄 Recargar Datos del Disco"):
        st.cache_data.clear()
        st.rerun()
    
    all_processed_data = load_processed_data([STATIC_DIR, DYNAMIC_DIR])

    found_files_static = [f for f in os.listdir(STATIC_DIR) if f.endswith('_modificado.csv')]
    
    if all_processed_data.empty:
        st.warning("No hay datos procesados disponibles para mostrar en el dashboard.")
    elif 'RECORD' not in all_processed_data.columns:
        st.error("La columna 'RECORD' (índice de muestra) es necesaria para los gráficos estáticos y no se encuentra.")
    else:
        all_processed_data.dropna(subset=['RECORD'], inplace=True)
        
        # --- FILTROS GLOBALES ---
        st.sidebar.header("Filtros del Dashboard")
        
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
            # --- PESTAÑAS ---
            tab1, tab2 = st.tabs(["Pruebas Estáticas (Strain)", "Pruebas Dinámicas (Aceleración)"])

            # PESTAÑA 1: ESTÁTICAS
            with tab1:
                st.header("Análisis de Datos Estáticos (Strain y Desplazamiento)")
                
                # Filtrar solo datos estáticos
                df_static = df_filtered[df_filtered['Tipo_Prueba'] == 'Estática'].copy()
                
                if df_static.empty:
                    st.info("No hay datos estáticos disponibles.")
                else:
                    # Slider específico para datos estáticos
                    max_record_static = df_static['RECORD'].max()
                    min_record_static = df_static['RECORD'].min()
                    
                    record_range_static = st.slider(
                        "Seleccionar Rango de Muestra (RECORD) - Estático:",
                        min_value=int(min_record_static) if not np.isnan(min_record_static) else 0,
                        max_value=int(max_record_static) if not np.isnan(max_record_static) else 1000,
                        value=(int(min_record_static), int(max_record_static)),
                        step=1,
                        key='slider_static'
                    )
                    
                    df_static = df_static[
                        (df_static['RECORD'] >= record_range_static[0]) & 
                        (df_static['RECORD'] <= record_range_static[1])
                    ]
                    
                    st.info(f"📊 Datos en el rango seleccionado: {len(df_static):,} muestras")
                    
                    # --- GRÁFICO 1: STRAIN ---
                    strain_cols = [col for col in df_static.columns if 'Strain' in col and df_static[col].dtype in ['float64', 'int64']]
                    
                    if strain_cols:
                        st.subheader("Tensión Superficial (Strain) vs. RECORD")
                        
                        selected_strain = st.multiselect(
                            "Seleccionar Galgas:",
                            options=strain_cols,
                            default=strain_cols,#[0] if strain_cols else [],
                            key='strain_select'
                        )
                        
                        if selected_strain:
                            cols_to_plot = ['RECORD'] + selected_strain
                            plot_data = df_static[cols_to_plot].sort_values(by='RECORD')

                            df_melted = plot_data.melt(
                                id_vars=['RECORD'],
                                value_vars=selected_strain,
                                var_name='Galgas',
                                value_name='Microstrain'
                            )

                            chart = alt.Chart(df_melted).mark_line(size=1).encode(
                                x=alt.X('RECORD:Q', 
                                       title='Índice de Muestra (RECORD)',
                                       scale=alt.Scale(domain=[record_range_static[0], record_range_static[1]])),
                                y=alt.Y('Microstrain:Q', title='Strain (microstrain)'),
                                color='Galgas:N',
                                tooltip=['RECORD:Q', 'Galgas:N', 'Microstrain:Q']
                            ).properties(
                                title='Strain vs. RECORD',
                                width='container',
                                height=400
                            ).interactive()
                            
                            st.altair_chart(chart, use_container_width=True)
                            
                            max_val = df_static[selected_strain].max().max()
                            st.metric("Máximo Strain Registrado (µε)", f"{max_val:.2f}")
                        else:
                            st.info("Selecciona al menos una Galga Extensiométrica para visualizar.")
                    else:
                        st.info("No se encontraron columnas de Strain en los datos.")
                    
                    st.markdown("---")
                    
                    # --- GRÁFICO 2: DESPLAZAMIENTO (LVDT) ---
                    lvdt_cols = [col for col in df_static.columns if col.startswith('Disp') and df_static[col].dtype in ['float64', 'int64']]
                    
                    if lvdt_cols:
                        st.subheader("Desplazamiento (LVDT) vs. RECORD")
                        
                        selected_lvdt_static = st.multiselect(
                            "Seleccionar Sensores de Desplazamiento (LVDT):",
                            options=lvdt_cols,
                            default=lvdt_cols,
                            key='lvdt_select_static'
                        )
                        
                        if selected_lvdt_static:
                            cols_to_plot_lvdt = ['RECORD'] + selected_lvdt_static
                            plot_data_lvdt = df_static[cols_to_plot_lvdt].sort_values(by='RECORD')
                            
                            df_melted_lvdt = plot_data_lvdt.melt(
                                id_vars=['RECORD'],
                                value_vars=selected_lvdt_static,
                                var_name='Sensor',
                                value_name='Desplazamiento'
                            )

                            chart_lvdt = alt.Chart(df_melted_lvdt).mark_line(size=1).encode(
                                x=alt.X('RECORD:Q', 
                                       title='Índice de Muestra (RECORD)',
                                       scale=alt.Scale(domain=[record_range_static[0], record_range_static[1]])),
                                y=alt.Y('Desplazamiento:Q', title='Desplazamiento (mm)'),
                                color='Sensor:N',
                                tooltip=['RECORD:Q', 'Sensor:N', 'Desplazamiento:Q']
                            ).properties(
                                title='Desplazamiento vs. RECORD',
                                width='container',
                                height=400
                            ).interactive()
                            
                            st.altair_chart(chart_lvdt, use_container_width=True)
                        else:
                            st.info("Selecciona al menos un LVDT para visualizar.")
                    else:
                        st.info("No se encontraron columnas de Desplazamiento (disp_mm, disp2_mm) para graficar.")
            # PESTAÑA 2: DINÁMICAS
            with tab2:
                st.header("Análisis de Datos Dinámicos (Aceleración y Desplazamiento)")
                
                # Filtrar solo datos dinámicos
                df_dynamic = df_filtered[df_filtered['Tipo_Prueba'] == 'Dinámica'].copy()
                
                if df_dynamic.empty:
                    st.info("No hay datos dinámicos disponibles.")
                else:
                    # Slider específico para datos dinámicos
                    max_record_dynamic = df_dynamic['RECORD'].max()
                    min_record_dynamic = df_dynamic['RECORD'].min()
                    
                    record_range_dynamic = st.slider(
                        "Seleccionar Rango de Muestra (RECORD) - Dinámico:",
                        min_value=int(min_record_dynamic) if not np.isnan(min_record_dynamic) else 0,
                        max_value=int(max_record_dynamic) if not np.isnan(max_record_dynamic) else 1000,
                        value=(int(min_record_dynamic), int(max_record_dynamic)),
                        step=1,
                        key='slider_dynamic'
                    )
                    
                    df_dynamic = df_dynamic[
                        (df_dynamic['RECORD'] >= record_range_dynamic[0]) & 
                        (df_dynamic['RECORD'] <= record_range_dynamic[1])
                    ]
                    
                    st.info(f"📊 Datos en el rango seleccionado: {len(df_dynamic):,} muestras")
                    
                    # --- GRÁFICO 1: ACELERÓMETROS ---
                    accel_cols = [col for col in df_dynamic.columns if col.startswith('A21')]
                    
                    if accel_cols:
                        st.subheader("Aceleración vs. RECORD")
                        
                        selected_accel = st.multiselect(
                            "Seleccionar Acelerómetros:",
                            options=accel_cols,
                            default=accel_cols,
                            key='accel_select_dyn'
                        )
                        
                        if selected_accel:
                            cols_to_plot_accel = ['RECORD'] + selected_accel
                            plot_data_accel = df_dynamic[cols_to_plot_accel].sort_values(by='RECORD') 
                            
                            df_melted_accel = plot_data_accel.melt(
                                id_vars=['RECORD'],
                                value_vars=selected_accel,
                                var_name='Sensor',
                                value_name='Aceleración'
                            )

                            chart_accel = alt.Chart(df_melted_accel).mark_line(size=1).encode(
                                x=alt.X('RECORD:Q', 
                                       title='Índice de Muestra (RECORD)',
                                       scale=alt.Scale(domain=[record_range_dynamic[0], record_range_dynamic[1]])),
                                y=alt.Y('Aceleración:Q', title='Aceleración (unidades)'),
                                color='Sensor:N',
                                tooltip=['RECORD:Q', 'Sensor:N', 'Aceleración:Q']
                            ).properties(
                                title='Aceleración vs. RECORD',
                                width='container',
                                height=400
                            ).interactive()
                            
                            st.altair_chart(chart_accel, use_container_width=True)
                        else:
                            st.info("Selecciona al menos un Acelerómetro para visualizar.")
                            
                    st.markdown("---")
                        
                    # --- GRÁFICO 2: DESPLAZAMIENTO ---
                    lvdt_cols = [col for col in df_dynamic.columns if col.startswith('LV')]
                    
                    if lvdt_cols:
                        st.subheader("Desplazamiento (LVDT) vs. RECORD")
                        
                        selected_lvdt = st.multiselect(
                            "Seleccionar Sensores de Desplazamiento (LVDT):",
                            options=lvdt_cols,
                            default=lvdt_cols,
                            key='lvdt_select_dyn'
                        )
                        
                        if selected_lvdt:
                            cols_to_plot_lvdt = ['RECORD'] + selected_lvdt
                            plot_data_lvdt = df_dynamic[cols_to_plot_lvdt].sort_values(by='RECORD') 
                            
                            df_melted_lvdt = plot_data_lvdt.melt(
                                id_vars=['RECORD'],
                                value_vars=selected_lvdt,
                                var_name='Sensor',
                                value_name='Desplazamiento'
                            )

                            chart_lvdt = alt.Chart(df_melted_lvdt).mark_line(size=1).encode(
                                x=alt.X('RECORD:Q', 
                                       title='Índice de Muestra (RECORD)',
                                       scale=alt.Scale(domain=[record_range_dynamic[0], record_range_dynamic[1]])),
                                y=alt.Y('Desplazamiento:Q', title='Desplazamiento (unidades)'),
                                color='Sensor:N',
                                tooltip=['RECORD:Q', 'Sensor:N', 'Desplazamiento:Q']
                            ).properties(
                                title='Desplazamiento vs. RECORD',
                                width='container',
                                height=400
                            ).interactive() 
                            
                            st.altair_chart(chart_lvdt, use_container_width=True)
                        else:
                            st.info("Selecciona al menos un LVDT para visualizar.")
                    else:
                        st.info("No se encontraron columnas de Desplazamiento (LV6XXX) para graficar.")