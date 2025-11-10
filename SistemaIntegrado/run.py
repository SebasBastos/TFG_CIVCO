import subprocess
import os

def run_stramlit():
    # obtiene la ruta del script de stramlit
    script_path = os.path.join(os.path.dirname(__file__), 'app.py')

    # ejecuta el script de stramlit
    subprocess.run(['streamlit', 'run', script_path])

if __name__ == "__main__":
    run_stramlit()

