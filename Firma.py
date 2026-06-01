import streamlit as st
from streamlit_drawable_canvas import st_canvas
from datetime import datetime
import pandas as pd
from PIL import Image
import io
import json
from fpdf import FPDF
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload

st.set_page_config(page_title="Firma Odoo PDF", layout="centered")
st.title("Registro de Entrega / Servicio")

# === CONEXIÓN A DRIVE USANDO TU FORMATO [gcp_oauth] ===
@st.cache_resource
def conectar_drive():
    token_info = json.loads(st.secrets["gcp_oauth"]["token"])
    creds = Credentials.from_authorized_user_info(
        token_info,
        scopes=["https://www.googleapis.com/auth/drive"]
    )
    service = build('drive', 'v3', credentials=creds)
    return service

def crear_carpeta_drive(service, nombre_carpeta, id_padre=None):
    query = f"name='{nombre_carpeta}' and mimeType='application/vnd.google-apps.folder' and trashed=false"
    if id_padre:
        query += f" and '{id_padre}' in parents"

    results = service.files().list(q=query, spaces='drive', fields='files(id, name)').execute()
    items = results.get('files', [])

    if items:
        return items[0]['id']
    else:
        file_metadata = {
            'name': nombre_carpeta,
            'mimeType': 'application/vnd.google-apps.folder'
        }
        if id_padre:
            file_metadata['parents'] = [id_padre]
        folder = service.files().create(body=file_metadata, fields='id').execute()
        return folder.get('id')

def subir_a_drive(service, archivo_bytes, nombre_archivo, mimetype, id_carpeta):
    file_metadata = {'name': nombre_archivo, 'parents': [id_carpeta]}
    media = MediaIoBaseUpload(io.BytesIO(archivo_bytes), mimetype=mimetype)
    file = service.files().create(body=file_metadata, media_body=media, fields='id').execute()
    return file.get('id')

# === LÓGICA DE LA APP ===
if 'paso' not in st.session_state:
    st.session_state.paso = 1

if st.session_state.paso == 1:
    st.subheader("Paso 1: Datos del servicio")

    with st.form("form_datos"):
        cliente = st.text_input("1. Cliente *")
        pedido = st.text_input("2. Pedido Cliente *")
        ref_oddo = st.text_input("3. Referencia Odoo *")
        operador = st.text_input("4. Nombre del Operador *")

        if st.form_submit_button("Continuar a firma", type="primary"):
            if all([cliente, pedido, ref_oddo, operador]):
                st.session_state.datos_registro = {
                    "cliente": cliente,
                    "pedido_cliente": pedido,
                    "ref_oddo": ref_oddo,
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
        if st.button("Generar PDF y Subir a Drive", type="primary"):
            if canvas_result.image_data is not None:
                try:
                    service = conectar_drive()

                    # 1. Preparar imagen de firma en memoria
                    img = Image.fromarray(canvas_result.image_data.astype('uint8'), 'RGBA')
                    img_byte_arr = io.BytesIO()
                    img.save(img_byte_arr, format='PNG')
                    img_byte_arr = img_byte_arr.getvalue()

                    # 2. Generar PDF en memoria
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

                    with open("firma_temp.png", "wb") as f:
                        f.write(img_byte_arr)
                    pdf.image("firma_temp.png", x=10, w=100)

                    # ESTA ES LA PARTE QUE ARREGLA TODO BB - JALA CON FPDF Y FPDF2
                    pdf_output = pdf.output(dest='S')
                    if isinstance(pdf_output, str):
                        pdf_bytes = pdf_output.encode('latin-1')
                    else:
                        pdf_bytes = bytes(pdf_output)

                    # 3. Subir a Drive: Fotos_Anden > ref_oddo > PDF
                    id_fotos_anden = crear_carpeta_drive(service, "Fotos_Anden")
                    id_carpeta_ref = crear_carpeta_drive(service, st.session_state.datos_registro['ref_oddo'], id_fotos_anden)

                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    nombre_pdf = f"Entrega_{st.session_state.datos_registro['ref_oddo']}_{timestamp}.pdf"

                    subir_a_drive(service, pdf_bytes, nombre_pdf, 'application/pdf', id_carpeta_ref)

                    st.success(f"PDF guardado en Drive: Fotos_Anden > {st.session_state.datos_registro['ref_oddo']}")
                    st.balloons()

                    st.download_button(
                        label="Descargar PDF también",
                        data=pdf_bytes,
                        file_name=nombre_pdf,
                        mime="application/pdf"
                    )

                    if st.button("Nuevo registro"):
                        st.session_state.paso = 1
                        st.rerun()

                except Exception as e:
                    st.error(f"Error subiendo a Drive: {e}")
            else:
                st.error("El operador debe firmar")
