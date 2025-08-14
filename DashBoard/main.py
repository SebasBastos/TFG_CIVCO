import streamlit as st
import pandas as pd
import plotly.express as px
import os
import sys
import warnings

warnings.filterwarnings("ignore")

print("Loading main.py...")

# Código basado desde el canal Programming Is Fun de YouTube
# https://www.youtube.com/@ProgrammingIsFun

# Set the page configuration for the Streamlit app
st.set_page_config(page_title="eBridge Dashboard", page_icon=":bar_chart:", layout="wide")
st.title(":bridge_at_night: TFG CIVCO Dashboard")
st.markdown("<style>div.block-container {padding-top:1rem;} </style>", unsafe_allow_html=True)

fl = st.file_uploader(":file_folder: Upload your file", type=(["csv", "txt", "xlsx", "xls"]))

if fl is not None:
    filename = fl.name
    st.write(f"File uploaded: {filename}")
    df = pd.read_csv(filename, encoding = "ISO-8859-1")
else:
    os.chdir(os.path.dirname(__file__))
    df = pd.read_csv("../data/processed_data.csv", encoding = "ISO-8859-1")
    