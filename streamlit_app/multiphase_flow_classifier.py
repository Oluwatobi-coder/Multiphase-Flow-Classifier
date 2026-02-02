# importing necessary libraries
import streamlit as st
import pandas as pd
import numpy as np
import joblib
import matplotlib.pyplot as plt
from matplotlib.patches import Patch
from PIL import Image

# setting up the app icon
img = Image.open("./image_assets/flowpipe.png")

# setting page config
st.set_page_config(
    page_title="Multiphase Flow Regime Classifier",
    page_icon=img,
    layout="wide"
)

# specifying custom CSS for styling
st.markdown("""
<style>
    .metric-card {
        background-color: #f0f2f6;
        padding: 15px;
        border-radius: 10px;
        border-left: 5px solid #2e86c1;
    }
    .stProgress > div > div > div > div {
        background-color: #2e86c1;
    }
</style>
""", unsafe_allow_html=True)

# setting up the title and description
st.title("🌀 Multiphase Flow Regime Predictive Classifier")
st.markdown("""
This system uses **physics-informed Machine Learning** to predict flow regimes and estimate riser pressures based on operational setpoints.
The models have been trained on the **PRONTO heterogeneous benchmark dataset**, which is based on an industrial-scale multiphase flow facility.
""")
st.divider()

# loading the predictive models and scaler
@st.cache_resource
def load_predictive_engine():
    assets = joblib.load('./model_assets/models_assets.pkl')
    return assets['classifier'], assets['reg_p6'], assets['reg_p8'], assets['scaler']

clf, reg_p6, reg_p8, scaler = load_predictive_engine()


# setting up the sidebar for user inputs
with st.sidebar:
    st.header("🕹️ Operational Control")
    
    # setting up system geometry input
    st.subheader("1. System Geometry")
    
    # giving pipe diameter options in mm - 1 inch to 4 inches
    pipe_options_mm = [25.4, 50.8, 76.2, 101.6]
    

    # writing function to format diameter display
    def format_diameter(mm_val):
        inches = mm_val / 25.4
        return f"{mm_val:.1f} mm ({inches:.1f}\")"

    # setting the diameter selection slider
    st.write("Adjusting the pipe diameter recalibrates the superficial velocities (Vsg, Vsl).")
    pipe_diam_mm = st.select_slider(
        "Pipe Diameter", 
        options=pipe_options_mm, 
        value=50.8,
        format_func=format_diameter,  # <--- This handles the display label
        help="Adjusting diameter recalibrates the superficial velocities (Vsg, Vsl)."
    )
    
    # setting up flow setpoints input
    st.subheader("2. Flow Setpoints")
    st.write("Adjust the water and air flow rates to simulate the flow conditions.")
    air_flow = st.slider("Air Flow Rate (sm³/h)", 0.0, 300.0, 100.0)
    water_flow = st.slider("Water Flow Rate (kg/s)", 0.1, 4.0, 1.0)

# converting diameter to meters and calculating pipe area
PIPE_DIAM_M = pipe_diam_mm / 1000.0
PIPE_AREA = np.pi * (PIPE_DIAM_M / 2)**2

# calculating superficial velocities for air and water
q_gas_m3s = air_flow / 3600.0
vsg = q_gas_m3s / PIPE_AREA

q_liquid_m3s = water_flow / 1000.0
vsl = q_liquid_m3s / PIPE_AREA

# preparing input dataframe for prediction
input_df = pd.DataFrame(
    [[vsg, vsl, PIPE_DIAM_M]], 
    columns=['Vsg', 'Vsl', 'Pipe_Diameter_m']
)
scaled_input = scaler.transform(input_df)

# getting predictions from models
regime_pred = clf.predict(scaled_input)[0]
regime_prob = clf.predict_proba(scaled_input)[0]
pred_p6 = reg_p6.predict(scaled_input)[0]
pred_p8 = reg_p8.predict(scaled_input)[0]

# setting up the three main columns for output display
col_left, col_mid, col_right = st.columns([1.5, 1.5, 2])

# setting up column 1: Flow Regime Status
with col_left:
    st.subheader("Flow Regime Status")
    if regime_pred == 1:
        st.error("🔴 CRITICAL: SLUGGING DETECTED")
        st.write(f"**Confidence:** {regime_prob[1]*100:.1f}%")
        st.warning("⚠️ Action Required: Increase Gas Rate or Throttle Liquid.")
    else:
        st.success("🟢 NORMAL: STABLE FLOW")
        st.write(f"**Confidence:** {regime_prob[0]*100:.1f}%")
        st.info("✅ System Operating within Safe Limits.")

# setting up column 2: Predicted Pressures
with col_mid:
    st.subheader("Predicted Pressures")
    st.metric("**P6 (Riser Base)**", f"{pred_p6:.2f} Bar", "Estimated Pressure")
    st.progress(min(pred_p6 / 3.0, 1.0))
    st.divider()
    st.metric("**P8 (Riser Mid-point)**", f"{pred_p8:.2f} Bar", "Estimated Pressure")
    st.progress(min(pred_p8 / 3.0, 1.0))

# setting up column 3: Flow Regime Map
with col_right:
    st.subheader("Flow Regime Map")
    
    # setting dynamic plot limits based on current velocities
    max_vsg_plot = max(30, vsg * 1.2) 
    max_vsl_plot = max(4.0, vsl * 1.2)
    
    # setting up grid for contour plot
    x_range = np.linspace(0, max_vsg_plot, 100)
    y_range = np.linspace(0, max_vsl_plot, 100)
    xx, yy = np.meshgrid(x_range, y_range)
    
    # creating dataframe for grid points
    grid_df = pd.DataFrame({
        'Vsg': xx.ravel(),
        'Vsl': yy.ravel(),
        'Pipe_Diameter_m': np.full(xx.ravel().shape, PIPE_DIAM_M)
    })
    
    # predicting regimes over the grid
    grid_scaled = scaler.transform(grid_df)
    Z = clf.predict(grid_scaled).reshape(xx.shape)
    
    # plotting the regime map
    fig, ax = plt.subplots(figsize=(6, 4))
    
    # setting contourf for regime zones
    ax.contourf(xx, yy, Z, levels=[-0.1, 0.5, 1.1], colors=['#d4efdf', '#fadbd8'], alpha=0.8)
    
    # setting scatter plot for current operating point
    ax.scatter([vsg], [vsl], color='#2e86c1', s=150, marker='X', 
               edgecolors='white', linewidth=1.5, zorder=10)
    
    # annotating the current point
    ax.annotate(f"Vsg={vsg:.1f}\nVsl={vsl:.1f}", 
                xy=(vsg, vsl), 
                xytext=(0, 15), 
                textcoords='offset points',
                ha='center', fontsize=9, fontweight='bold', 
                bbox=dict(facecolor='white', alpha=0.8, edgecolor='none', pad=2))
    
    # adding labels and title
    ax.set_xlabel("Superficial Gas Velocity Vsg (m/s)")
    ax.set_ylabel("Superficial Liquid Velocity Vsl (m/s)")
    
    inches_disp = pipe_diam_mm / 25.4
    ax.set_title(f"Regime Map @ {pipe_diam_mm} mm ({inches_disp:.1f}\")", fontsize=10)
    
    ax.grid(True, linestyle='--', alpha=0.3)
    
    # setting the limits
    ax.set_xlim(0, max_vsg_plot)
    ax.set_ylim(0, max_vsl_plot)
    
    # setting up the legend
    legend_elements = [
        Patch(facecolor='#fadbd8', edgecolor='none', label='Slugging Zone'),
        Patch(facecolor='#d4efdf', edgecolor='none', label='Stable Zone'),
        plt.Line2D([0], [0], marker='X', color='w', markerfacecolor='#2e86c1', markersize=10, label='Current Point')
    ]
    ax.legend(handles=legend_elements, loc='best', fontsize=8)
    
    st.pyplot(fig)

# seting up expander for calculation details
with st.expander("Calculation Details"):
    st.markdown(f"""
    **Geometry:** `{pipe_diam_mm} mm` ({pipe_diam_mm/25.4:.1f} inches) \n
    **Calculated Velocities:** $V_{{sg}}$: `{vsg:.2f} m/s`, $V_{{sl}}$: `{vsl:.2f} m/s`
    """)