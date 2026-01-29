import pandas as pd
import io
import zipfile
import xml.etree.ElementTree as ET
import re
import streamlit as st

# --- 1. ESTILO RIHANNA (FOFO + NEON GLOW TRAVADO) ---
def aplicar_estilo_rihanna():
    st.set_page_config(page_title="MATRIZ FISCAL", layout="wide", page_icon="💎")

    st.markdown("""
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Montserrat:wght@400;800&family=Plus+Jakarta+Sans:wght@400;700&display=swap');

        header, [data-testid="stHeader"] { display: none !important; }
        
        .stApp { 
            background: radial-gradient(circle at top right, #FFDEEF 0%, #F8F9FA 100%) !important; 
        }

        [data-testid="stSidebar"] {
            background-color: #FFFFFF !important;
            border-right: 1px solid #FFDEEF !important;
            min-width: 350px !important;
        }

        /* --- BOTÃO PRINCIPAL E BOTÃO DO UPLOADER COM NEON --- */
        div.stButton > button, 
        section[data-testid="stFileUploader"] button {
            color: #FF69B4 !important; 
            background-color: #FFFFFF !important; 
            border: 2px solid #FF69B4 !important;
            border-radius: 20px !important;
            font-family: 'Montserrat', sans-serif !important;
            font-weight: 800 !important;
            height: 50px !important;
            text-transform: uppercase;
            transition: all 0.4s ease-in-out !important;
            width: 100% !important;
            box-shadow: 0 0 10px rgba(255, 105, 180, 0.2) !important;
        }

        div.stButton > button:hover, 
        section[data-testid="stFileUploader"] button:hover {
            background-color: #FF69B4 !important;
            color: #FFFFFF !important;
            box-shadow: 0 0 20px rgba(255, 105, 180, 0.6), 0 0 40px rgba(255, 105, 180, 0.4) !important;
            transform: scale(1.02) !important;
            border-color: #FFFFFF !important;
        }

        /* ÁREA DE UPLOAD ROSA NEON */
        [data-testid="stFileUploader"] { 
            border: 2px dashed #FF69B4 !important; 
            border-radius: 20px !important;
            background: #FFFFFF !important;
            padding: 20px !important;
            box-shadow: inset 0 0 15px rgba(255, 105, 180, 0.05) !important;
        }

        /* BOTÃO DOWNLOAD ROSA SÓLIDO */
        div.stDownloadButton > button {
            background-color: #FF69B4 !important; 
            color: white !important; 
            font-weight: 800 !important;
            border-radius: 15px !important;
            text-transform: uppercase;
            width: 100% !important;
            height: 60px !important;
            border: none !important;
            box-shadow: 0 0 15px rgba(255, 105, 180, 0.5) !important;
        }

        h1, h2, h3 {
            font-family: 'Montserrat', sans-serif;
            font-weight: 800;
            color: #FF69B4 !important;
            text-align: center;
        }

        .instrucoes-card {
            background-color: rgba(255, 255, 255, 0.8);
            border-radius: 20px;
            padding: 25px;
            border-left: 8px solid #FF69B4;
            margin-bottom: 25px;
            box-shadow: 0 10px 30px rgba(0,0,0,0.05);
            min-height: 250px;
        }
        </style>
    """, unsafe_allow_html=True)

aplicar_estilo_rihanna()

# --- 2. MOTOR DE LEITURA (34 COLUNAS) ---
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

def buscar_tag(tag, no):
    if no is None: return ""
    for el in no.iter():
        if el.tag.split('}')[-1] == tag: return el.text if el.text else ""
    return ""

def ler_xml(content, dados_lista, cnpj_cliente):
    try:
        xml_str = re.sub(r'\sxmlns(:\w+)?="[^"]+"', '', content.decode('utf-8', errors='replace'))
        root = ET.fromstring(xml_str)
        inf = root.find('.//infNFe')
        if inf is None: return 

        ide, emit, dest = root.find('.//ide'), root.find('.//emit'), root.find('.//dest')
        cnpj_emit = re.sub(r'\D', '', buscar_tag('CNPJ', emit))
        tipo_op = "SAIDA" if (cnpj_emit == re.sub(r'\D', '', str(cnpj_cliente)) and buscar_tag('tpNF', ide) == '1') else "ENTRADA"

        for det in root.findall('.//det'):
            prod, imp = det.find('prod'), det.find('imposto')
            icms, ipi, pis, cof = det.find('.//ICMS'), det.find('.//IPI'), det.find('.//PIS'), det.find('.//COFINS')
            ibs, cbs = det.find('.//IBS'), det.find('.//CBS')
            
            orig = buscar_tag('orig', icms)
            cst_p = buscar_tag('CST', icms) or buscar_tag('CSOSN', icms)
            
            dados_lista.append({
                "CHAVE_ACESSO": inf.attrib.get('Id', '')[3:],
                "NUM_NF": buscar_tag('nNF', ide),
                "DATA_EMISSAO": buscar_tag('dhEmi', ide) or buscar_tag('dEmi', ide),
                "TIPO_SISTEMA": tipo_op,
                "CNPJ_EMIT": cnpj_emit,
                "UF_EMIT": buscar_tag('UF', emit),
                "CNPJ_DEST": re.sub(r'\D', '', buscar_tag('CNPJ', dest)),
                "UF_DEST": buscar_tag('UF', dest),
                "INDIEDEST": buscar_tag('indIEDest', dest),
                "CFOP": buscar_tag('CFOP', prod), "NCM": buscar_tag('NCM', prod),
                "VPROD": safe_float(buscar_tag('vProd', prod)),
                "ORIGEM": orig, "CST-ICMS": orig + cst_p if cst_p else orig,
                "BC-ICMS": safe_float(buscar_tag('vBC', icms)), "ALQ-ICMS": safe_float(buscar_tag('pICMS', icms)), "VLR-ICMS": safe_float(buscar_tag('vICMS', icms)),
                "VAL-ICMS-ST": safe_float(buscar_tag('vICMSST', icms)), "IE_SUBST": buscar_tag('IEST', icms),
                "VAL-DIFAL": safe_float(buscar_tag('vICMSUFDest', imp)) + safe_float(buscar_tag('vFCPUFDest', imp)),
                "CST-IPI": buscar_tag('CST', ipi), "ALQ-IPI": safe_float(buscar_tag('pIPI', ipi)), "VLR-IPI": safe_float(buscar_tag('vIPI', ipi)),
                "CST-PIS": buscar_tag('CST', pis), "VLR-PIS": safe_float(buscar_tag('vPIS', pis)),
                "CST-COFINS": buscar_tag('CST', cof), "VLR-COFINS": safe_float(buscar_tag('vCOFINS', cof)),
                "CLCLASS": buscar_tag('CLClass', prod) or buscar_tag('CLClass', imp),
                "CST-IBS": buscar_tag('CST', ibs), "BC-IBS": safe_float(buscar_tag('vBC', ibs)), "VLR-IBS": safe_float(buscar_tag('vIBS', ibs)),
                "CST-CBS": buscar_tag('CST', cbs), "BC-CBS": safe_float(buscar_tag('vBC', cbs)), "VLR-CBS": safe_float(buscar_tag('vCBS', cbs))
            })
    except: pass

# --- 3. INTERFACE ---
st.markdown("<h1>💎 MATRIZ FISCAL</h1>", unsafe_allow_html=True)

col1, col2 = st.columns(2)
with col1:
    st.markdown("""
    <div class="instrucoes-card">
        <h3>📖 Manual de Uso</h3>
        <p>1. <b>Configuração:</b> Digite o CNPJ na barra lateral.</p>
        <p>2. <b>Upload:</b> Arraste seus arquivos para o campo rosa.</p>
        <p>3. <b>Extração:</b> Clique em "Processar" para brilhar.</p>
    </div>
    """, unsafe_allow_html=True)
with col2:
    st.markdown("""
    <div class="instrucoes-card">
        <h3>🎯 Dados Obtidos</h3>
        <p>✓ <b>Mapeamento:</b> 34 colunas fiscais completas.</p>
        <p>✓ <b>Reforma:</b> Tags de IBS, CBS e CLClass incluídas.</p>
        <p>✓ <b>Audit:</b> Separação nativa de Entradas e Saídas.</p>
    </div>
    """, unsafe_allow_html=True)

with st.sidebar:
    st.markdown("### ⚙️ Ajustes")
    cnpj_input = st.text_input("CNPJ do Cliente:", placeholder="00.000.000/0001-00")
    if st.button("🔄 REINICIAR TUDO"):
        st.session_state.clear()
        st.rerun()

files = st.file_uploader("Solte seus arquivos aqui!", type=["xml", "zip"], accept_multiple_files=True)

if st.button("🚀 PROCESSAR MATRIZ FISCAL"):
    if not files or not cnpj_input:
        st.error("Ops! Esqueceu o CNPJ ou os arquivos.")
    else:
        lista_final = []
        with st.spinner("💎 Rihanna Style: Brilhando nos dados..."):
            for f in files:
                if f.name.endswith('.zip'):
                    with zipfile.ZipFile(f) as z:
                        for n in z.namelist():
                            if n.lower().endswith('.xml'): ler_xml(z.read(n), lista_final, cnpj_input)
                else: ler_xml(f.read(), lista_final, cnpj_input)
        
        if lista_final:
            df = pd.DataFrame(lista_final)
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                df.to_excel(writer, index=False)
            st.success(f"✨ Sucesso! {len(df)} itens organizados.")
            st.download_button("📥 BAIXAR MATRIZ DIAMANTE", output.getvalue(), f"matriz_{cnpj_input}.xlsx")
