import pandas as pd
import io
import zipfile
import xml.etree.ElementTree as ET
import re
import streamlit as st

# --- 1. CONFIGURAÇÃO DE LAYOUT PREMIUM (RIHANNA STYLE) ---
def configurar_layout_premium(titulo="CORE FISCAL PARSER", icone="💎"):
    st.set_page_config(page_title=titulo, layout="wide", page_icon=icone)

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

        div.stButton > button {
            color: #6C757D !important; 
            background-color: #FFFFFF !important; 
            border: 1px solid #DEE2E6 !important;
            border-radius: 15px !important;
            font-family: 'Montserrat', sans-serif !important;
            font-weight: 800 !important;
            height: 60px !important;
            text-transform: uppercase;
            transition: all 0.4s ease !important;
            width: 100% !important;
        }

        div.stButton > button:hover {
            transform: translateY(-3px) !important;
            box-shadow: 0 10px 20px rgba(255,105,180,0.1) !important;
            border-color: #FF69B4 !important;
            color: #FF69B4 !important;
        }

        [data-testid="stFileUploader"] { 
            border: 2px dashed #FF69B4 !important; 
            border-radius: 20px !important;
            background: #FFFFFF !important;
            padding: 20px !important;
        }

        div.stDownloadButton > button {
            background-color: #FF69B4 !important; 
            color: white !important; 
            font-weight: 700 !important;
            border-radius: 15px !important;
            text-transform: uppercase;
            width: 100% !important;
            height: 60px !important;
        }

        h1, h2, h3 {
            font-family: 'Montserrat', sans-serif;
            font-weight: 800;
            color: #FF69B4 !important;
        }

        .instrucoes-card {
            background-color: rgba(255, 255, 255, 0.8);
            border-radius: 20px;
            padding: 25px;
            border-left: 8px solid #FF69B4;
            margin-bottom: 25px;
            box-shadow: 0 10px 30px rgba(0,0,0,0.05);
        }

        .beneficios-grid {
            display: flex;
            gap: 20px;
            margin-bottom: 20px;
        }

        .item-beneficio {
            flex: 1;
            background: white;
            padding: 15px;
            border-radius: 12px;
            text-align: center;
            border: 1px solid #FFDEEF;
        }
        </style>
    """, unsafe_allow_html=True)

configurar_layout_premium()

# --- 2. MOTOR DE PROCESSAMENTO (MANTIDO ÍNTEGRO) ---
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

# --- 3. INTERFACE PRINCIPAL ---

st.markdown('<h1 style="text-align: center;">💎 CORE FISCAL PARSER</h1>', unsafe_allow_html=True)

# CARD DE INSTRUÇÕES
st.markdown("""
<div class="instrucoes-card">
    <h3>📖 MANUAL DE OPERAÇÃO</h3>
    <p>1. Informe o <b>CNPJ da Empresa Auditada</b> na barra lateral esquerda.</p>
    <p>2. Arraste suas pastas <b>ZIP</b> (com XMLs dentro) ou arquivos <b>XML</b> avulsos para o campo de upload.</p>
    <p>3. Clique em <b>🚀 PROCESSAR</b> e aguarde a extração inteligente.</p>
    <p>4. O sistema organizará automaticamente o que é <b>ENTRADA</b> e o que é <b>SAÍDA</b>.</p>
</div>
""", unsafe_allow_html=True)

# O QUE SERÁ CONSEGUIDO
st.markdown("### 🎯 ENTREGÁVEIS DA EXTRAÇÃO")
st.markdown("""
<div class="beneficios-grid">
    <div class="item-beneficio"><b>📂 Unificação</b><br>Transforma milhares de XMLs em uma única linha por item.</div>
    <div class="item-beneficio"><b>⚖️ Reforma</b><br>Extração nativa de IBS, CBS e CLClass para 2026.</div>
    <div class="item-beneficio"><b>🔍 Auditoria</b><br>Base pronta para cruzamento de ICMS, PIS/COFINS e IPI.</div>
</div>
""", unsafe_allow_html=True)

with st.sidebar:
    st.markdown("### ⚙️ CONFIGURAÇÃO")
    cnpj = st.text_input("CNPJ Auditado (só números):", placeholder="Ex: 00123456000188")
    st.markdown("---")
    st.write("📌 **Nota:** A identificação de Entrada/Saída depende da exatidão deste CNPJ.")

files = st.file_uploader("Upload de Arquivos", type=["xml", "zip"], accept_multiple_files=True)

if st.button("🚀 PROCESSAR E GERAR PLANILHA"):
    if not files or not cnpj:
        st.error("❌ Erro: Preencha o CNPJ e anexe os arquivos.")
    else:
        lista = []
        with st.spinner("💎 Rihanna Style: Processando com elegância..."):
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
            
            st.success(f"✨ Concluído! {len(df)} itens extraídos com perfeição.")
            st.download_button("📥 BAIXAR PLANILHA DE AUDITORIA", output.getvalue(), f"extracao_{cnpj}.xlsx")
        else:
            st.error("⚠️ Nenhum dado válido encontrado. Verifique se os XMLs estão no formato NF-e.")
