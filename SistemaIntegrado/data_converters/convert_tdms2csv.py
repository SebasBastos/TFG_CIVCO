import pandas as pd
from nptdms import TdmsFile

def convert_tdms_to_csv(input_filepath, output_filepath):
    """
    Convierte archivos .tdms de Bridge Diagnostics (BDI) a .csv
    """
    try:
        with TdmsFile.open(input_filepath) as tdms_file:
            data = {}
            for group in tdms_file.groups():
                for channel in group.channels():
                    column_name = f"{group.name}_{channel.name}"
                    data[column_name] = channel[:]
            
            df = pd.DataFrame(data)
            df.to_csv(output_filepath, index=False)
            print(f" Archivo '{input_filepath}' convertido a '{output_filepath}' con éxito.")
    except Exception as e:
        print(f" Error al convertir el archivo {input_filepath}: {e}")