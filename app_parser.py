import pandas as pd
import io
import zipfile
import xml.etree.ElementTree as ET
import re
import os

# --- FUNÇÕES DE APOIO ---
def safe_float(v):
    """Converte valores do XML para float de forma segura, mantendo precisão para auditoria."""
    if v is None or pd.isna(v): return 0.0
    txt = str(v).strip().upper()
    if txt in ['NT', '', 'N/A', 'ISENTO', 'NULL', 'ZERO', '-', ' ']: return 0.0
    try:
        txt = txt.replace('R$', '').replace(' ', '').replace('%', '').strip()
        if ',' in txt and '.' in txt: txt = txt.replace('.', '').replace(',', '.')
        elif ',' in txt: txt = txt.replace(',', '.')
        return round(float(txt), 4)
    except: return 0.0

def buscar_tag_recursiva(tag_alvo, no):
    """Busca tag ignorando namespace, essencial para diferentes versões de layout NFe."""
    if no is None: return ""
    for elemento in no.iter():
        tag_nome = elemento.tag.split('}')[-1]
        if tag_nome == tag_alvo: return elemento.text if elemento.text else ""
    return ""

# --- MOTOR DE EXTRAÇÃO XML ---
def processar_conteudo_xml(content, dados_lista, cnpj_empresa_auditada):
    try:
        xml_str = content.decode('utf-8', errors='replace')
        # Limpeza de namespaces para garantir que a busca recursiva seja precisa
        xml_str_limpa = re.sub(r'\sxmlns(:\w+)?="[^"]+"', '', xml_str) 
        root = ET.fromstring(xml_str_limpa)
        
        inf = root.find('.//infNFe')
        if inf is None: return 
        
        ide = root.find('.//ide')
        emit = root.find('.//emit')
        dest = root.find('.//dest')
        
        # Lógica de Classificação Fiscal
        cnpj_emit = re.sub(r'\D', '', buscar_tag_recursiva('CNPJ', emit))
        cnpj_alvo = re.sub(r'\D', '', str(cnpj_empresa_auditada))
        tipo_nf = buscar_tag_recursiva('tpNF', ide)
        tipo_operacao = "SAIDA" if (cnpj_emit == cnpj_alvo and tipo_nf == '1') else "ENTRADA"
        chave = inf.attrib.get('Id', '')[3:]

        for det in root.findall('.//det'):
            prod = det.find('prod')
            imp = det.find('imposto')
            
            # Nós de impostos atuais
            icms_no = det.find('.//ICMS')
            ipi_no = det.find('.//IPI')
            pis_no = det.find('.//PIS')
            cof_no = det.find('.//COFINS')
            
            # Novos nós da Reforma Tributária
            ibs_no = det.find('.//IBS')
            cbs_no = det.find('.//CBS')
            
            # Composição do CST-ICMS (Origem + CST/CSOSN)
            orig = buscar_tag_recursiva('orig', icms_no)
            cst_p = buscar_tag_recursiva('CST', icms_no) or buscar_tag_recursiva('CSOSN', icms_no)
            cst_icms_full = orig + cst_p if cst_p else orig

            linha = {
                # --- IDENTIFICAÇÃO (BASE) ---
                "CHAVE_ACESSO": str(chave).strip(),
                "NUM_NF": buscar_tag_recursiva('nNF', ide),
                "DATA_EMISSAO": buscar_tag_recursiva('dhEmi', ide) or buscar_tag_recursiva('dEmi', ide),
                "TIPO_SISTEMA": tipo_operacao,
                
                # --- FLUXO FISCAL ---
                "CNPJ_EMIT": cnpj_emit,
                "UF_EMIT": buscar_tag_recursiva('UF', emit),
                "CNPJ_DEST": re.sub(r'\D', '', buscar_tag_recursiva('CNPJ', dest)),
                "UF_DEST": buscar_tag_recursiva('UF', dest),
                "INDIEDEST": buscar_tag_recursiva('indIEDest', dest),
                
                # --- DADOS DO ITEM ---
                "CFOP": buscar_tag_recursiva('CFOP', prod),
                "NCM": buscar_tag_recursiva('NCM', prod),
                "VPROD": safe_float(buscar_tag_recursiva('vProd', prod)),
                
                # --- TRIBUTAÇÃO ATUAL (ICMS, IPI, PIS, COFINS) ---
                "ORIGEM": orig,
                "CST-ICMS": cst_icms_full,
                "BC-ICMS": safe_float(buscar_tag_recursiva('vBC', icms_no)),
                "ALQ-ICMS": safe_float(buscar_tag_recursiva('pICMS', icms_no)),
                "VLR-ICMS": safe_float(buscar_tag_recursiva('vICMS', icms_no)),
                "VAL-ICMS-ST": safe_float(buscar_tag_recursiva('vICMSST', icms_no)),
                "IE_SUBST": str(buscar_tag_recursiva('IEST', icms_no)).strip(),
                "VAL-DIFAL": safe_float(buscar_tag_recursiva('vICMSUFDest', imp)) + safe_float(buscar_tag_recursiva('vFCPUFDest', imp)),
                
                "CST-IPI": buscar_tag_recursiva('CST', ipi_no),
                "ALQ-IPI": safe_float(buscar_tag_recursiva('pIPI', ipi_no)),
                "VLR-IPI": safe_float(buscar_tag_recursiva('vIPI', ipi_no)),
                
                "CST-PIS": buscar_tag_recursiva('CST', pis_no),
                "VLR-PIS": safe_float(buscar_tag_recursiva('vPIS', pis_no)),
                
                "CST-COFINS": buscar_tag_recursiva('CST', cof_no),
                "VLR-COFINS": safe_float(buscar_tag_recursiva('vCOFINS', cof_no)),
                
                # --- REFORMA TRIBUTÁRIA (NOVAS COLUNAS AO FIM) ---
                "CLCLASS": buscar_tag_recursiva('CLClass', prod) or buscar_tag_recursiva('CLClass', imp),
                "CST-IBS": buscar_tag_recursiva('CST', ibs_no),
                "BC-IBS": safe_float(buscar_tag_recursiva('vBC', ibs_no)),
                "VLR-IBS": safe_float(buscar_tag_recursiva('vIBS', ibs_no)),
                "CST-CBS": buscar_tag_recursiva('CST', cbs_no),
                "BC-CBS": safe_float(buscar_tag_recursiva('vBC', cbs_no)),
                "VLR-CBS": safe_float(buscar_tag_recursiva('vCBS', cbs_no))
            }
            dados_lista.append(linha)
    except Exception:
        pass # Mantém processamento mesmo com erro em nota isolada

def disparar_extracao(arquivos, cnpj_auditado):
    """Gerencia a leitura de múltiplos arquivos e pastas."""
    lista_final = []
    for f in arquivos:
        if f.lower().endswith('.zip'):
            with zipfile.ZipFile(f, 'r') as z:
                for nome in z.namelist():
                    if nome.lower().endswith('.xml'):
                        processar_conteudo_xml(z.read(nome), lista_final, cnpj_auditado)
        elif f.lower().endswith('.xml'):
            with open(f, 'rb') as xml_file:
                processar_conteudo_xml(xml_file.read(), lista_final, cnpj_auditado)
    
    return pd.DataFrame(lista_final)

# --- EXECUÇÃO ---
if __name__ == "__main__":
    # Exemplo de uso local
    # df = disparar_extracao(['notas.zip'], '00000000000000')
    # df.to_excel('extracao_base.xlsx', index=False)
    pass
