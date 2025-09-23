import pandas as pd

def convert_dat_to_csv(input_filepath, output_filepath):
    """
    Convierte archivos .dat de Campbell Scientific a .csv
    """
    try:
        df = pd.read_csv(input_filepath, delimiter=',', skiprows=[0, 2, 3])
        df.columns = df.columns.str.strip()
        df.to_csv(output_filepath, index=False)
        print(f" Archivo '{input_filepath}' convertido a '{output_filepath}' con éxito.")
    except Exception as e:
        print(f" Error al convertir el archivo {input_filepath}: {e}")