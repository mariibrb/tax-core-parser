import pandas as pd
import io
import zipfile
import xml.etree.ElementTree as ET
import re
import streamlit as st

# --- UTILITÁRIOS DE TRATAMENTO ---
def safe_float(v):
    """Garante conversão numérica sem quebrar o processamento."""
    if v is None or pd.isna(v): return 0.0
    txt = str(v).strip().upper()
    if txt in ['NT', '', 'N/A', 'ISENTO', 'NULL', 'ZERO', '-', ' ']: return 0.0
    try:
        txt = txt.replace('R$', '').replace(' ', '').replace('%', '').strip()
        if ',' in txt and '.' in txt: txt = txt.replace('.', '').replace(',', '.')
        elif ',' in txt: txt = txt.replace(',', '.')
        return round(float(txt), 4)
    except: return 0.0

def buscar_tag_fiscal(tag_alvo, no):
    """Busca tag de forma recursiva ignorando namespaces do XML."""
    if no is None: return ""
    for elemento in no.iter():
        tag_nome = elemento.tag.split('}')[-1]
        if tag_nome == tag_alvo: return elemento.text if elemento.text else ""
    return ""

# --- MOTOR DE LEITURA (CORE PARSER) ---
def processar_xml_fiscal(content, dados_lista, cnpj_auditado):
    try:
        # Limpeza de namespaces para evitar falha na busca de tags
        xml_str = content.decode('utf-8', errors='replace')
        xml_str_limpa = re.sub(r'\sxmlns(:\w+)?="[^"]+"', '', xml_str) 
        root = ET.fromstring(xml_str_limpa)
        
        inf = root.find('.//infNFe')
        if inf is None: return 
        
        ide = root.find('.//ide'); emit = root.find('.//emit'); dest = root.find('.//dest')
        cnpj_emit = re.sub(r'\D', '', buscar_tag_fiscal('CNPJ', emit))
        cnpj_alvo = re.sub(r'\D', '', str(cnpj_auditado))
        tipo_nf = buscar_tag_fiscal('tpNF', ide)
        
        # Define se é ENTRADA ou SAÍDA comparando com o CNPJ informado
        operacao = "SAIDA" if (cnpj_emit == cnpj_alvo and tipo_nf == '1') else "ENTRADA"
        chave = inf.attrib.get('Id', '')[3:]

        for det in root.findall('.//det'):
            prod = det.find('prod'); imp = det.find('imposto')
            icms = det.find('.//ICMS'); ipi = det.find('.//IPI')
            pis = det.find('.//PIS'); cof = det.find('.//COFINS')
            ibs = det.find('.//IBS'); cbs = det.find('.//CBS') # Reforma Tributária
            
            orig = buscar_tag_fiscal('orig', icms)
            cst_p = buscar_tag_fiscal('CST', icms) or buscar_tag_fiscal('CSOSN', icms)

            # Estrutura final da planilha (Gabarito para os futuros módulos)
            dados_lista.append({
                "CHAVE_ACESSO": str(chave).strip(),
                "NUM_NF": buscar_tag_fiscal('nNF', ide),
                "DATA_EMISSAO": buscar_tag_fiscal('dhEmi', ide) or buscar_tag_fiscal('dEmi', ide),
                "TIPO_SISTEMA": operacao,
                "CNPJ_EMIT": cnpj_emit,
                "UF_EMIT": buscar_tag_fiscal('UF', emit),
                "CNPJ_DEST": re.sub(r'\D', '', buscar_tag_fiscal('CNPJ', dest)),
                "UF_DEST": buscar_tag_fiscal('UF', dest),
                "INDIEDEST": buscar_tag_fiscal('indIEDest', dest),
                "CFOP": buscar_tag_fiscal('CFOP', prod),
                "NCM": buscar_tag_fiscal('NCM', prod),
                "VPROD": safe_float(buscar_tag_fiscal('vProd', prod)),
                "ORIGEM": orig,
                "CST-ICMS": orig + cst_p if cst_p else orig,
                "BC-ICMS": safe_float(buscar_tag_fiscal('vBC', icms)),
                "ALQ-ICMS": safe_float(buscar_tag_fiscal('pICMS', icms)),
                "VLR-ICMS": safe_float(buscar_tag_fiscal('vICMS', icms)),
                "VAL-ICMS-ST": safe_float(buscar_tag_fiscal('vICMSST', icms)),
                "IE_SUBST": buscar_tag_fiscal('IEST', icms),
                "VAL-DIFAL": safe_float(buscar_tag_fiscal('vICMSUFDest', imp)) + safe_float(buscar_tag_fiscal('vFCPUFDest', imp)),
                "CST-IPI": buscar_tag_fiscal('CST', ipi),
                "ALQ-IPI": safe_float(buscar_tag_fiscal('pIPI', ipi)),
                "VLR-IPI": safe_float(buscar_tag_fiscal('vIPI', ipi)),
                "CST-PIS": buscar_tag_fiscal('CST', pis),
                "VLR-PIS": safe_float(buscar_tag_fiscal('vPIS', pis)),
                "CST-COFINS": buscar_tag_fiscal('CST', cof),
                "VLR-COFINS": safe_float(buscar_tag_fiscal('vCOFINS', cof)),
                # --- COLUNAS DA REFORMA TRIBUTÁRIA (Sempre ao fim) ---
                "CLCLASS": buscar_tag_fiscal('CLClass', prod) or buscar_tag_fiscal('CLClass', imp),
                "CST-IBS": buscar_tag_fiscal('CST', ibs),
                "BC-IBS": safe_float(buscar_tag_fiscal('vBC', ibs)),
                "VLR-IBS": safe_float(buscar_tag_fiscal('vIBS', ibs)),
                "CST-CBS": buscar_tag_fiscal('CST', cbs),
                "BC-CBS": safe_float(buscar_tag_fiscal('vBC', cbs)),
                "VLR-CBS": safe_float(buscar_tag_fiscal('vCBS', cbs))
            })
    except:
        pass # Ignora erros em notas específicas para não parar o lote

# --- INTERFACE STREAMLIT ---
st.set_page_config(page_title="Core Fiscal Parser", layout="wide")
st.title("📂 Core Fiscal Parser")
st.subheader("Extração de Dados XML: Legado + Reforma Tributária")

cnpj_auditado = st.text_input("CNPJ da Empresa Auditada (apenas números):")
u_files = st.file_uploader("Upload de XMLs ou Pastas ZIP", type=["xml", "zip"], accept_multiple_files=True)

if st.button("PROCESSAR E GERAR PLANILHA", type="primary", use_container_width=True):
    if not cnpj_auditado or not u_files:
        st.warning("⚠️ Forneça o CNPJ e os arquivos para continuar.")
    else:
        lista_resultados = []
        with st.spinner("Lendo ficheiros..."):
            for f in u_files:
                if f.name.endswith('.zip'):
                    with zipfile.ZipFile(f) as z:
                        for name in z.namelist():
                            if name.lower().endswith('.xml'):
                                processar_xml_fiscal(z.read(name), lista_resultados, cnpj_auditado)
                else:
                    processar_xml_fiscal(f.read(), lista_resultados, cnpj_auditado)
        
        if lista_resultados:
            df = pd.DataFrame(lista_resultados)
            
            # Conversão para Excel em memória
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                df.to_excel(writer, index=False, sheet_name='DADOS_FISCAIS')
            
            st.success(f"✅ Extração concluída: {len(df)} itens processados.")
            st.download_button(
                label="📥 BAIXAR PLANILHA EXCEL",
                data=output.getvalue(),
                file_name=f"extracao_{cnpj_auditado}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True
            )
        else:
            st.error("❌ Nenhum dado válido encontrado nos arquivos enviados.")
