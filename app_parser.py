import pandas as pd
import io
import zipfile
import xml.etree.ElementTree as ET
import re
import streamlit as st

# --- 1. CONFIGURAÇÃO DE ESTILO (PADRÃO RIHANNA COM NEON) ---
def aplicar_estilo_rihanna(titulo="MATRIZ FISCAL", icone="📊"):
    st.set_page_config(page_title=titulo, layout="wide", page_icon=icone)

    st.markdown("""
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Montserrat:wght@400;800&family=Plus+Jakarta+Sans:wght@400;700&display=swap');

        header, [data-testid="stHeader"] { display: none !important; }
        
        .stApp { 
            background: radial-gradient(circle at top right, #FDF2F7 0%, #F8F9FA 100%) !important; 
        }

        [data-testid="stSidebar"] {
            background-color: #FFFFFF !important;
            border-right: 2px solid #FFDEEF !important;
        }

        div.stButton > button {
            color: #FF69B4 !important; 
            background-color: #FFFFFF !important; 
            border: 2px solid #FF69B4 !important;
            border-radius: 15px !important;
            font-family: 'Montserrat', sans-serif !important;
            font-weight: 800 !important;
            height: 60px !important;
            text-transform: uppercase;
            transition: all 0.4s ease-in-out !important;
            width: 100% !important;
            box-shadow: 0 0 5px rgba(255, 105, 180, 0.2) !important;
        }

        div.stButton > button:hover {
            background-color: #FF69B4 !important;
            color: #FFFFFF !important;
            box-shadow: 0 0 20px rgba(255, 105, 180, 0.6), 0 0 40px rgba(255, 105, 180, 0.4) !important;
            transform: scale(1.02) !important;
        }

        [data-testid="stFileUploader"] { 
            border: 2px dashed #FF69B4 !important; 
            border-radius: 20px !important;
            background: #FFFFFF !important;
            padding: 20px !important;
            box-shadow: inset 0 0 10px rgba(255, 105, 180, 0.1) !important;
        }

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
            color: #343A40 !important;
        }

        .card-rihanna {
            background-color: white;
            border-radius: 20px;
            padding: 25px;
            border-left: 8px solid #FF69B4;
            box-shadow: 0 10px 30px rgba(0,0,0,0.05);
            margin-bottom: 20px;
        }
        </style>
    """, unsafe_allow_html=True)

aplicar_estilo_rihanna()

# --- LÓGICA DE REINICIALIZAÇÃO ---
def reiniciar_sistema():
    st.session_state.clear()
    st.rerun()

# --- 2. LÓGICA DE EXTRAÇÃO (MAPEAMENTO TOTAL DE TAGS) ---
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

        ide = root.find('.//ide'); emit = root.find('.//emit'); dest = root.find('.//dest')
        cnpj_emit = re.sub(r'\D', '', buscar_tag('CNPJ', emit))
        cnpj_alvo = re.sub(r'\D', '', str(cnpj_cliente))
        tipo_op = "SAIDA" if (cnpj_emit == cnpj_alvo and buscar_tag('tpNF', ide) == '1') else "ENTRADA"

        for det in root.findall('.//det'):
            prod = det.find('prod'); imp = det.find('imposto')
            icms = det.find('.//ICMS'); ipi = det.find('.//IPI'); pis = det.find('.//PIS'); cof = det.find('.//COFINS')
            ibs = det.find('.//IBS'); cbs = det.find('.//CBS') 
            
            orig = buscar_tag('orig', icms)
            cst_p = buscar_tag('CST', icms) or buscar_tag('CSOSN', icms)
            
            # DICIONÁRIO COMPLETO COM TODAS AS TAGS SOLICITADAS
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
                "CFOP": buscar_tag('CFOP', prod), 
                "NCM": buscar_tag('NCM', prod),
                "VPROD": safe_float(buscar_tag('vProd', prod)),
                "ORIGEM": orig, 
                "CST-ICMS": orig + cst_p if cst_p else orig,
                "BC-ICMS": safe_float(buscar_tag('vBC', icms)), 
                "ALQ-ICMS": safe_float(buscar_tag('pICMS', icms)), 
                "VLR-ICMS": safe_float(buscar_tag('vICMS', icms)),
                "VAL-ICMS-ST": safe_float(buscar_tag('vICMSST', icms)), 
                "IE_SUBST": buscar_tag('IEST', icms),
                "VAL-DIFAL": safe_float(buscar_tag('vICMSUFDest', imp)) + safe_float(buscar_tag('vFCPUFDest', imp)),
                "CST-IPI": buscar_tag('CST', ipi), 
                "ALQ-IPI": safe_float(buscar_tag('pIPI', ipi)), 
                "VLR-IPI": safe_float(buscar_tag('vIPI', ipi)),
                "CST-PIS": buscar_tag('CST', pis), 
                "VLR-PIS": safe_float(buscar_tag('vPIS', pis)),
                "CST-COFINS": buscar_tag('CST', cof), 
                "VLR-COFINS": safe_float(buscar_tag('vCOFINS', cof)),
                # --- NOVAS TAGS REFORMA TRIBUTÁRIA AO FINAL ---
                "CLCLASS": buscar_tag('CLClass', prod) or buscar_tag('CLClass', imp),
                "CST-IBS": buscar_tag('CST', ibs), 
                "BC-IBS": safe_float(buscar_tag('vBC', ibs)), 
                "VLR-IBS": safe_float(buscar_tag('vIBS', ibs)),
                "CST-CBS": buscar_tag('CST', cbs), 
                "BC-CBS": safe_float(buscar_tag('vBC', cbs)), 
                "VLR-CBS": safe_float(buscar_tag('vCBS', cbs))
            })
    except: pass

# --- 3. INTERFACE ---
st.markdown('<h1 style="text-align: center; color: #FF69B4 !important;">📊 MATRIZ FISCAL</h1>', unsafe_allow_html=True)

st.markdown("""
<div class="card-rihanna">
    <h3 style="color: #FF69B4 !important; margin-top:0;">DIRETRIZES</h3>
    <p>1. Informe o CNPJ do cliente na barra lateral.</p>
    <p>2. Suba os arquivos XML ou ZIP abaixo.</p>
    <p>3. Processe a matriz para gerar o Excel consolidado com <b>todas as colunas fiscais</b>.</p>
</div>
""", unsafe_allow_html=True)

if "uploader_key" not in st.session_state:
    st.session_state["uploader_key"] = 0

with st.sidebar:
    st.markdown("### ⚙️ PARÂMETROS")
    cnpj = st.text_input("CNPJ Contribuinte:", placeholder="00.000.000/0001-00")
    st.markdown("---")
    if st.button("🔄 NOVA ANÁLISE"):
        st.session_state["uploader_key"] += 1
        reiniciar_sistema()

files = st.file_uploader("Upload de Repositórios XML", type=["xml", "zip"], accept_multiple_files=True, key=f"uploader_{st.session_state['uploader_key']}")

if st.button("🚀 PROCESSAR MATRIZ"):
    if not files or not cnpj:
        st.error("Preencha o CNPJ e anexe os arquivos.")
    else:
        lista = []
        with st.spinner("Extraindo todas as tags fiscais..."):
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
            st.success(f"Matriz consolidada com {len(df)} itens e todas as colunas mapeadas.")
            st.download_button("📥 BAIXAR MATRIZ FISCAL COMPLETA", output.getvalue(), f"matriz_completa_{cnpj}.xlsx")
        else:
            st.error("Nenhum dado encontrado nos XMLs.")
