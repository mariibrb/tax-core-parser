import pandas as pd
import io
import zipfile
import xml.etree.ElementTree as ET
import re
import streamlit as st

# --- 1. APARÊNCIA PREMIUM (SIDEBAR, TÍTULOS EM NEGRITO E CORES TRAVADAS) ---
def aplicar_estilo_premium():
    st.set_page_config(page_title="MATRIZ FISCAL | Diamond", layout="wide", page_icon="💎")

    st.markdown("""
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Montserrat:wght@400;800&family=Plus+Jakarta+Sans:wght@400;700&display=swap');

        header, [data-testid="stHeader"] { display: none !important; }
        
        .stApp { 
            background: radial-gradient(circle at top right, #FFDEEF 0%, #F8F9FA 100%) !important; 
        }

        /* SIDEBAR IGUAL AO DIAMOND TAX */
        [data-testid="stSidebar"] {
            background-color: #FFFFFF !important;
            border-right: 1px solid #FFDEEF !important;
            min-width: 400px !important;
            max-width: 400px !important;
        }

        [data-testid="stSidebar"] div.stButton > button { width: 100% !important; }

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
        }

        div.stButton > button:hover {
            transform: translateY(-5px) !important;
            box-shadow: 0 10px 20px rgba(255,105,180,0.2) !important;
            border-color: #FF69B4 !important;
            color: #FF69B4 !important;
        }

        /* FILE UPLOADER COM BOTÃO ROSA E CONTORNO BRANCO */
        [data-testid="stFileUploader"] { 
            border: 2px dashed #FF69B4 !important; 
            border-radius: 20px !important;
            background: #FFFFFF !important;
            padding: 20px !important;
        }

        section[data-testid="stFileUploader"] button {
            background-color: #FF69B4 !important;
            color: white !important;
            border: 2px solid #FFFFFF !important;
            font-weight: 700 !important;
            border-radius: 15px !important;
            box-shadow: 0 0 15px rgba(255, 105, 180, 0.3) !important;
            text-transform: uppercase;
            width: 100% !important;
        }

        /* TÍTULOS EM NEGRITO (IGUAL AO DIAMOND TAX) */
        h1, h2, h3 {
            font-family: 'Montserrat', sans-serif;
            font-weight: 800 !important; /* Forçando o negrito máximo */
            color: #FF69B4 !important;
            text-align: center;
        }

        .stTextInput>div>div>input {
            border: 2px solid #FFDEEF !important;
            border-radius: 10px !important;
            padding: 10px !important;
        }

        .instrucoes-card {
            background-color: rgba(255, 255, 255, 0.7);
            border-radius: 15px;
            padding: 20px;
            border-left: 5px solid #FF69B4;
            margin-bottom: 20px;
            min-height: 280px;
        }

        div.stDownloadButton > button {
            background-color: #FF69B4 !important; 
            color: white !important; 
            border: 2px solid #FFFFFF !important;
            font-weight: 700 !important;
            border-radius: 15px !important;
            box-shadow: 0 0 15px rgba(255, 105, 180, 0.3) !important;
            text-transform: uppercase;
            width: 100% !important;
        }
        </style>
    """, unsafe_allow_html=True)

aplicar_estilo_premium()

# --- 2. SEU MOTOR ORIGINAL (34 COLUNAS - ÍNTEGRO) ---
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
                "TIPO_SISTEMA": tipo_op, "CNPJ_EMIT": cnpj_emit, "UF_EMIT": buscar_tag('UF', emit),
                "CNPJ_DEST": re.sub(r'\D', '', buscar_tag('CNPJ', dest)), "UF_DEST": buscar_tag('UF', dest),
                "INDIEDEST": buscar_tag('indIEDest', dest), "CFOP": buscar_tag('CFOP', prod), "NCM": buscar_tag('NCM', prod),
                "VPROD": safe_float(buscar_tag('vProd', prod)), "ORIGEM": orig, "CST-ICMS": orig + cst_p if cst_p else orig,
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

# CARDS FIXOS NO TOPO
with st.container():
    m_col1, m_col2 = st.columns(2)
    with m_col1:
        st.markdown('<div class="instrucoes-card"><h3>📖 Manual de Uso</h3><ol><li><b>Configuração:</b> Informe o CNPJ na lateral para liberar o painel.</li><li><b>Upload:</b> Arraste arquivos XML ou ZIP para o campo rosa.</li><li><b>Processamento:</b> Extração automática das 34 colunas.</li></ol></div>', unsafe_allow_html=True)
    with m_col2:
        st.markdown('<div class="instrucoes-card"><h3>🎯 Dados Obtidos</h3><ul><li><b>Mapeamento Total:</b> 34 colunas fiscais extraídas.</li><li><b>Reforma 2026:</b> Tags de IBS, CBS e CLClass incluídas.</li><li><b>Inteligência:</b> Separação automática entre Entradas e Saídas.</li></ul></div>', unsafe_allow_html=True)

st.markdown("---")

# MECANISMO DE LIBERAÇÃO (SESSION STATE)
if 'confirmado' not in st.session_state: st.session_state['confirmado'] = False

with st.sidebar:
    st.markdown("### 🔍 Configuração")
    cnpj_input = st.text_input("CNPJ DO CLIENTE", placeholder="00.000.000/0001-00")
    cnpj_limpo = "".join(filter(str.isdigit, cnpj_input))
    
    if cnpj_input and len(cnpj_limpo) != 14:
        st.error("⚠️ O CNPJ deve ter 14 números.")
    
    if len(cnpj_limpo) == 14:
        if st.button("✅ LIBERAR OPERAÇÃO"):
            st.session_state['confirmado'] = True
    
    st.divider()
    if st.button("🗑️ RESETAR SISTEMA"):
        st.session_state.clear()
        st.rerun()

# CONTEÚDO PRINCIPAL (SÓ APARECE APÓS LIBERAR)
if st.session_state['confirmado']:
    st.info(f"🏢 Empresa Liberada: {cnpj_limpo}")
    files = st.file_uploader("Arraste seus arquivos XML ou ZIP aqui", type=["xml", "zip"], accept_multiple_files=True)

    if st.button("🚀 PROCESSAR MATRIZ FISCAL"):
        if not files:
            st.error("Esqueceu os arquivos!")
        else:
            lista_final = []
            with st.spinner("💎 Rihanna Style: Brilhando nos dados..."):
                for f in files:
                    if f.name.endswith('.zip'):
                        with zipfile.ZipFile(f) as z:
                            for n in z.namelist():
                                if n.lower().endswith('.xml'): ler_xml(z.read(n), lista_final, cnpj_limpo)
                    else: ler_xml(f.read(), lista_final, cnpj_limpo)
            
            if lista_final:
                df = pd.DataFrame(lista_final)
                output = io.BytesIO()
                with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                    df.to_excel(writer, index=False)
                st.success(f"✨ Sucesso! {len(df)} itens organizados.")
                st.download_button("📥 BAIXAR MATRIZ DIAMANTE", output.getvalue(), f"matriz_{cnpj_limpo}.xlsx")
else:
    st.warning("👈 Insira o CNPJ na barra lateral e clique em 'Liberar Operação' para começar.")
