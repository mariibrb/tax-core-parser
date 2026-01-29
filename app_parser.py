import pandas as pd
import io
import zipfile
import xml.etree.ElementTree as ET
import re
import streamlit as st

# --- 1. CONFIGURAÇÃO DE ESTILO (PADRÃO MATRIZ FISCAL + UPLOADER ORIGINAL) ---
def aplicar_estilo_matriz():
    st.set_page_config(page_title="MATRIZ FISCAL", layout="wide", page_icon="📊")

    st.markdown("""
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Montserrat:wght@400;800&family=Plus+Jakarta+Sans:wght@400;700&display=swap');

        header, [data-testid="stHeader"] { display: none !important; }
        
        /* Fundo Gradiente Suave */
        .stApp { 
            background: radial-gradient(circle at top right, #FFDEEF 0%, #F8F9FA 100%) !important; 
        }

        /* Sidebar Branca Corporativa */
        [data-testid="stSidebar"] {
            background-color: #FFFFFF !important;
            border-right: 1px solid #FFDEEF !important;
            min-width: 350px !important;
        }

        /* BOTÃO COM NEON ROSA E GLOW */
        div.stButton > button {
            color: #6C757D !important; 
            background-color: #FFFFFF !important; 
            border: 1px solid #DEE2E6 !important;
            border-radius: 15px !important;
            font-family: 'Montserrat', sans-serif !important;
            font-weight: 800 !important;
            height: 60px !important;
            text-transform: uppercase;
            transition: all 0.4s cubic-bezier(0.175, 0.885, 0.32, 1.275) !important;
            width: 100% !important;
        }

        div.stButton > button:hover {
            transform: translateY(-5px) !important;
            box-shadow: 0 10px 20px rgba(255,105,180,0.2) !important;
            border-color: #FF69B4 !important;
            color: #FF69B4 !important;
        }

        /* ÁREA DE UPLOAD IGUAL AO EXEMPLO (TRAVADA) */
        [data-testid="stFileUploader"] { 
            border: 2px dashed #FF69B4 !important; 
            border-radius: 20px !important;
            background: #FFFFFF !important;
            padding: 20px !important;
        }

        /* BOTÃO DOWNLOAD ROSA */
        div.stDownloadButton > button {
            background-color: #FF69B4 !important; 
            color: white !important; 
            font-weight: 700 !important;
            border-radius: 15px !important;
            text-transform: uppercase;
            width: 100% !important;
            height: 60px !important;
            box-shadow: 0 0 15px rgba(255, 105, 180, 0.3) !important;
        }

        h1, h2, h3 {
            font-family: 'Montserrat', sans-serif;
            font-weight: 800;
            color: #FF69B4 !important;
            text-align: center;
        }

        .instrucoes-card {
            background-color: rgba(255, 255, 255, 0.7);
            border-radius: 15px;
            padding: 25px;
            border-left: 5px solid #FF69B4;
            margin-bottom: 25px;
            box-shadow: 0 10px 30px rgba(0,0,0,0.05);
        }

        .stTextInput>div>div>input {
            border: 2px solid #FFDEEF !important;
            border-radius: 10px !important;
        }
        </style>
    """, unsafe_allow_html=True)

aplicar_estilo_matriz()

# --- 2. MOTOR DE PROCESSAMENTO ---
def safe_float(v):
    if v is None or pd.isna(v): return 0.0
    txt = str(v).strip().upper()
    if txt in ['NT', '', 'N/A', 'ISENTO', 'NULL', 'ZERO', '-', ' ']: return 0.0
    try:
        txt = txt.replace('R$', '').replace(' ', '').replace('%', '').strip()
        if ',' in txt and '.' in txt: txt = txt.replace('.', '').replace(',', '.')
        elif ',' in txt: txt = txt.replace(',', '.')
        return round(float(txt), 4)
    except: return 0.0

def buscar_tag(tag_alvo, no):
    if no is None: return ""
    for elemento in no.iter():
        tag_nome = elemento.tag.split('}')[-1]
        if tag_nome == tag_alvo: return elemento.text if elemento.text else ""
    return ""

def ler_xml(content, dados_lista, cnpj_cliente):
    try:
        xml_str = content.decode('utf-8', errors='replace')
        xml_str = re.sub(r'\sxmlns(:\w+)?="[^"]+"', '', xml_str) 
        root = ET.fromstring(xml_str)
        inf = root.find('.//infNFe')
        if inf is None: return 

        ide = root.find('.//ide'); emit = root.find('.//emit')
        cnpj_emit = re.sub(r'\D', '', buscar_tag('CNPJ', emit))
        cnpj_alvo = re.sub(r'\D', '', str(cnpj_cliente))
        tipo_op = "SAIDA" if (cnpj_emit == cnpj_alvo and buscar_tag('tpNF', ide) == '1') else "ENTRADA"

        for det in root.findall('.//det'):
            prod = det.find('prod'); imp = det.find('imposto')
            icms = det.find('.//ICMS'); ibs = det.find('.//IBS'); cbs = det.find('.//CBS') 
            
            orig = buscar_tag('orig', icms)
            cst_p = buscar_tag('CST', icms) or buscar_tag('CSOSN', icms)
            
            dados_lista.append({
                "CHAVE_ACESSO": inf.attrib.get('Id', '')[3:],
                "NUM_NF": buscar_tag('nNF', ide),
                "DATA_EMISSAO": buscar_tag('dhEmi', ide) or buscar_tag('dEmi', ide),
                "TIPO_SISTEMA": tipo_op,
                "CNPJ_EMIT": cnpj_emit,
                "UF_EMIT": buscar_tag('UF', emit),
                "CFOP": buscar_tag('CFOP', prod), "NCM": buscar_tag('NCM', prod),
                "VPROD": safe_float(buscar_tag('vProd', prod)),
                "CST-ICMS": orig + cst_p if cst_p else orig,
                "BC-ICMS": safe_float(buscar_tag('vBC', icms)), "VLR-ICMS": safe_float(buscar_tag('vICMS', icms)),
                "VAL-DIFAL": safe_float(buscar_tag('vICMSUFDest', imp)) + safe_float(buscar_tag('vFCPUFDest', imp)),
                "VLR-IBS": safe_float(buscar_tag('vIBS', ibs)), "VLR-CBS": safe_float(buscar_tag('vCBS', cbs)),
                "CLCLASS": buscar_tag('CLClass', prod) or buscar_tag('CLClass', imp)
            })
    except: pass

# --- 3. INTERFACE ---
st.markdown('<h1>📊 MATRIZ FISCAL</h1>', unsafe_allow_html=True)

st.markdown("""
<div class="instrucoes-card">
    <h3>📖 DIRETRIZES DE OPERAÇÃO</h3>
    <p>1. Configure o <b>CNPJ do Contribuinte</b> na barra lateral esquerda.</p>
    <p>2. Realize o upload dos arquivos <b>ZIP</b> ou <b>XML</b> no campo abaixo.</p>
    <p>3. Clique em <b>🚀 PROCESSAR MATRIZ</b> para consolidar a base de dados.</p>
</div>
""", unsafe_allow_html=True)

with st.sidebar:
    st.markdown("### ⚙️ PARÂMETROS")
    cnpj = st.text_input("CNPJ do Contribuinte:", placeholder="Somente números")
    st.markdown("---")
    st.info("Módulo de Extração de Dados XML.")

files = st.file_uploader("Upload de Repositórios XML", type=["xml", "zip"], accept_multiple_files=True)

if st.button("🚀 PROCESSAR MATRIZ"):
    if not files or not cnpj:
        st.error("Informe o CNPJ e anexe os arquivos.")
    else:
        lista = []
        with st.spinner("Consolidando dados..."):
            for f in files:
                if f.name.endswith('.zip'):
                    with zipfile.ZipFile(f) as z:
                        for n in z.namelist():
                            if n.lower().endswith('.xml'): ler_xml(z.read(n), lista, cnpj)
                else:
                    ler_xml(f.read(), lista, cnpj)
        
        if lista:
            df = pd.DataFrame(lista)
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                df.to_excel(writer, index=False)
            
            st.success(f"Matriz concluída: {len(df)} itens processados.")
            st.download_button("📥 BAIXAR MATRIZ FISCAL (EXCEL)", output.getvalue(), f"matriz_{cnpj}.xlsx")
