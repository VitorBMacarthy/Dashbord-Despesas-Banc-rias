import re
import pdfplumber
import pandas as pd
from datetime import datetime

# Mapeamento dos meses em português
MESES_PT = {
    1: "Janeiro", 2: "Fevereiro", 3: "Março", 4: "Abril",
    5: "Maio", 6: "Junho", 7: "Julho", 8: "Agosto",
    9: "Setembro", 10: "Outubro", 11: "Novembro", 12: "Dezembro"
}


def moeda_para_float(valor_str):
    """Converte valores como '3,08', '3.08', '3.439,56' para float (3.08)."""
    if not valor_str:
        return 0.0
    limpo = re.sub(r"[^\d.,-]", "", valor_str)

    if "." in limpo and "," in limpo:
        limpo = limpo.replace(".", "").replace(",", ".")
    elif "," in limpo:
        limpo = limpo.replace(",", ".")

    try:
        return float(limpo)
    except ValueError:
        return 0.0


def extrair_tarifa_produto(texto):
    """Extrai o nome da Tarifa e do Produto a partir do bloco de texto."""
    t = texto.upper()

    if "COBRANÇA" in t:
        return "Débito Serviço Cobrança", "Cobrança Bancária"
    elif "PIX" in t:
        return "Tarifa Pix Recebido QR Code", "Recebimento de Pix"
    elif "EXTRATO" in t or "MAGNETICO" in t or "MEIO MAGNÉTICO" in t:
        return "Tarifa Extrato Meio Magnético", "Conta Corrente"
    elif "SWIFT" in t:
        return "Tarifa Extrato Padrão Swift", "Outros"
    elif "PACOTE" in t:
        return "Tarifa de Pacote de Serviços", "Outros"
    elif "RELACIONAMENTO" in t or "PROGRAMA RELAC" in t:
        return "Tarifa Mensal Programa Relac", "Outros"
    elif "DEPÓSITO" in t or "DEPOSITO" in t:
        return "Depósito Identificado", "Outros"
    elif "CHEQUE" in t:
        return "Tarifa Cheque Ouro Manutenção", "Outros"
    elif "CENTRALIZA" in t:
        return "Tarifa de Centralização de Saldos", "Centralização Saldo"
    elif "INFORMAÇÃO CADASTRAL" in t or "CADASTRAL" in t:
        return "Tarifa de Informação Cadastral", "Outros"

    return "Outras Tarifas", "Outros"


def obter_nome_mes(data_str):
    """Retorna o nome do mês a partir da data DD/MM/AAAA."""
    try:
        dt = datetime.strptime(data_str, "%d/%m/%Y")
        return MESES_PT.get(dt.month, "")
    except Exception:
        return ""


def processar_pdf(caminho_pdf):
    texto_completo = ""
    with pdfplumber.open(caminho_pdf) as pdf:
        for pagina in pdf.pages:
            t = pagina.extract_text()
            if t:
                texto_completo += t + "\n"

    linhas = [l.strip() for l in texto_completo.split("\n") if l.strip()]

    cliente = "Não identificado"
    periodo = "Não identificado"
    total_fatura = 0.0

    # Extração simples do Cabeçalho
    for i, l in enumerate(linhas):
        if "CLIENTE:" in l.upper() and i + 1 < len(linhas):
            cliente = linhas[i + 1].strip()
        elif "PERÍODO:" in l.upper() or "PERIODO:" in l.upper():
            periodo = l.replace("PERÍODO:", "").replace("PERIODO:", "").strip()
        elif "TOTAL DO PERÍODO:" in l.upper():
            m = re.search(r"R\$\s*([\d.,]+)", l)
            if m:
                total_fatura = moeda_para_float(m.group(1))

    dados = []

    # Agrupamento de linhas por Data (DD/MM/AAAA)
    regex_data = re.compile(r"^(\d{2}/\d{2}/\d{4})")

    blocos = []
    bloco_atual = []

    for linha in linhas:
        if regex_data.match(linha):
            if bloco_atual:
                blocos.append(bloco_atual)
                bloco_atual = []
        bloco_atual.append(linha)
    if bloco_atual:
        blocos.append(bloco_atual)

    for b in blocos:
        texto_bloco = " ".join(b)

        # Procura a Data no início
        match_data = regex_data.match(b[0])
        if not match_data:
            continue
        data = match_data.group(1)

        # Procura por Valor Monetário no bloco
        match_valor = re.findall(r"R\$\s*([\d.,]+)", texto_bloco)
        if not match_valor:
            continue
        valor = moeda_para_float(match_valor[-1])

        # Procura a Conta (ex: 3168/4505)
        match_conta = re.search(r"(\d{3,5}\s*/\s*\d{3,6})", texto_bloco)
        ag_conta = match_conta.group(1).replace(" ", "") if match_conta else "-"

        # Procura a Quantidade
        match_qtd = re.findall(r"(?:\|\s*|\s+)(\d+)\s+(?:\|\s*)?R\$", texto_bloco)
        qtd = int(match_qtd[-1]) if match_qtd else 1

        tarifa, produto = extrair_tarifa_produto(texto_bloco)
        mes = obter_nome_mes(data)

        dados.append({
            "Data": data,
            "Tarifa": tarifa,
            "Produto": produto,
            "Ag.conta": ag_conta,
            "Qtd": qtd,
            "Valor": valor,
            "Mês": mes
        })

    df = pd.DataFrame(dados)
    return cliente, periodo, total_fatura, df