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
st.set_page_config(page_title="TFG CIVCO Dashboard", page_icon=":bar_chart:", layout="wide")
st.title("TFG CIVCO Dashboard")

