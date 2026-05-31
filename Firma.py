import streamlit as st
from streamlit_drawable_canvas import st_canvas
from datetime import datetime
import pandas as pd
from PIL import Image
import os
from fpdf import FPDF

st.set_page_config(page_title="Firma Odoo PDF", layout="centered")
st.title("Registro de Entrega / Servicio")

os.makedirs("registros/pdf", exist_ok=True)
os.makedirs("registros/firmas", exist_ok=True)

if 'paso' not in st.session_state:
    st.session_state.paso = 1

if st.session_state.paso == 1:
    st.subheader("Paso 1: Datos del servicio")
    
    with st.form("form_datos"):
        cliente = st.text_input("1. Cliente *")
        pedido = st.text_input("2. Pedido Cliente *")
        ref_oddo = st.text_input("3. Referencia Odoo *")  # <--- Variable
        operador = st.text_input("4. Nombre del Operador *")
        
        if st.form_submit_button("Continuar a firma", type="primary"):
            if all([cliente, pedido, ref_oddo, operador]):
                st.session_state.datos_registro = {
                    "cliente": cliente,
                    "pedido_cliente": pedido,
                    "ref_oddo": ref_oddo,  # <--- CORREGIDO AQUÍ
                    "operador": operador,
                    "fecha_hora": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                }
                st.session_state.paso = 2
                st.rerun()
            else:
                st.error("Llena todos los campos")

if st.session_state.paso == 2:
    st.subheader("Paso 2: Firma del Operador")
    
    st.info(f"""
    *Cliente:* {st.session_state.datos_registro['cliente']}  
    *Pedido:* {st.session_state.datos_registro['pedido_cliente']}  
    *Ref. Odoo:* {st.session_state.datos_registro['ref_oddo']}  
    *Operador:* {st.session_state.datos_registro['operador']}
    """)
    
    st.write("*5. Firma aquí:*")
    canvas_result = st_canvas(
        fill_color="rgba(0, 0, 0, 0)", stroke_width=3, stroke_color="#000", 
        background_color="#fff", height=180, width=700, 
        drawing_mode="freedraw", key="canvas",
    )
    
    col1, col2 = st.columns(2)
    with col1:
        if st.button("← Editar datos"):
            st.session_state.paso = 1
            st.rerun()
    with col2:
        if st.button("Generar PDF", type="primary"):
            if canvas_result.image_data is not None:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                nombre_base = f"{st.session_state.datos_registro['ref_oddo']}_{timestamp}"
                
                ruta_firma = f"registros/firmas/{nombre_base}.png"
                img = Image.fromarray(canvas_result.image_data.astype('uint8'), 'RGBA')
                img.save(ruta_firma)
                
                pdf = FPDF()
                pdf.add_page()
                pdf.set_font("Arial", 'B', 16)
                pdf.cell(0, 10, "Comprobante de Entrega / Servicio", ln=True, align='C')
                pdf.ln(10)
                
                pdf.set_font("Arial", 'B', 12)
                pdf.cell(0, 10, "Datos del Registro:", ln=True)
                pdf.set_font("Arial", '', 12)
                
                for key, value in st.session_state.datos_registro.items():
                    label = key.replace('_', ' ').title()
                    pdf.cell(50, 10, f"{label}:", 0)
                    pdf.cell(0, 10, str(value), ln=True)
                
                pdf.ln(5)
                pdf.set_font("Arial", 'B', 12)
                pdf.cell(0, 10, "Firma del Operador:", ln=True)
                pdf.image(ruta_firma, x=10, w=100)
                
                ruta_pdf = f"registros/pdf/{nombre_base}.pdf"
                pdf.output(ruta_pdf)
                
                st.session_state.datos_registro['archivo_pdf'] = ruta_pdf
                df_nuevo = pd.DataFrame([st.session_state.datos_registro])
                ruta_csv = "registros/registros_firmados.csv"
                if os.path.exists(ruta_csv):
                    df_existente = pd.read_csv(ruta_csv)
                    df_final = pd.concat([df_existente, df_nuevo], ignore_index=True)
                else:
                    df_final = df_nuevo
                df_final.to_csv(ruta_csv, index=False)
                
                st.success("PDF generado correctamente")
                st.balloons()
                
                with open(ruta_pdf, "rb") as f:
                    st.download_button(
                        label="Descargar PDF",
                        data=f,
                        file_name=f"{nombre_base}.pdf",
                        mime="application/pdf"
                    )
                
                st.write(f"*Guardado en:* {ruta_pdf}")
                
                if st.button("Nuevo registro"):
                    st.session_state.paso = 1
                    st.rerun()
            else:
                st.error("El operador debe firmar")