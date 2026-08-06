import re
import pdfplumber
import pandas as pd


def moeda_para_float(valor_str):
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


def extrair_mes_nome(data_str):
    meses = {
        "01": "Janeiro", "02": "Fevereiro", "03": "Março", "04": "Abril",
        "05": "Maio", "06": "Junho", "07": "Julho", "08": "Agosto",
        "09": "Setembro", "10": "Outubro", "11": "Novembro", "12": "Dezembro"
    }
    partes = data_str.split("/")
    if len(partes) >= 2 and partes[1] in meses:
        return meses[partes[1]]
    return "Janeiro"


def categorizar(texto):
    t = texto.upper()
    if "COBRANÇA" in t:
        return "Cobrança Bancária"
    elif "PIX" in t:
        return "Serviços PIX"
    elif "EXTRATO" in t or "MAGNETICO" in t or "MEIO MAGNÉTICO" in t or "SWIFT" in t:
        return "Extratos"
    elif "PACOTE" in t or "MENSALIDADE" in t:
        return "Pacote de Serviços"
    elif "RELACIONAMENTO" in t or "PROGRAMA RELAC" in t:
        return "Tarifa Relacionamento"
    elif "DEPÓSITO" in t or "DEPOSITO" in t:
        return "Depósitos"
    elif "CHEQUE" in t:
        return "Cheques"
    elif "CENTRALIZAÇÃO" in t or "CENTRALIZA" in t:
        return "Centralização de Saldos"
    elif "INFORMAÇÃO CADASTRAL" in t or "CADASTRAL" in t:
        return "Cadastro"
    return "Outras Tarifas"


def processar_pdf(caminho_pdf):
    texto_completo = ""
    with pdfplumber.open(caminho_pdf) as pdf:
        for pagina in pdf.pages:
            t = pagina.extract_text()
            if t:
                texto_completo += t + "\n"

    linhas = [l.strip() for l in texto_completo.split("\n") if l.strip()]

    cliente = "STIHL FERRAMENTAS MOTORIZADAS LTDA."
    periodo = "Período do PDF"
    total_fatura = 0.0

    for i, l in enumerate(linhas):
        if "CLIENTE:" in l.upper() and i + 1 < len(linhas):
            cliente = linhas[i + 1].strip()
        elif "PERÍODO:" in l.upper() or "PERIODO:" in l.upper():
            periodo = l.replace("PERÍODO:", "").replace("PERIODO:", "").strip()

    dados = []
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

        match_data = regex_data.match(b[0])
        if not match_data:
            continue
        data = match_data.group(1)
        mes_nome = extrair_mes_nome(data)

        match_valor = re.findall(r"R\$\s*([\d.,]+)", texto_bloco)
        if not match_valor:
            continue
        valor = moeda_para_float(match_valor[-1])

        match_conta = re.search(r"(\d{3,5}\s*/\s*\d{3,6})", texto_bloco)
        conta = match_conta.group(1).replace(" ", "") if match_conta else "-"

        match_qtd = re.findall(r"(?:\|\s*|\s+)(\d+)\s+(?:\|\s*)?R\$", texto_bloco)
        qtd = int(match_qtd[-1]) if match_qtd else 1

        cat = categorizar(texto_bloco)

        dados.append({
            "Data": data,
            "Tarifa": cat,
            "Produto": cat,
            "Categoria": cat,
            "Descricao": texto_bloco,
            "Conta": conta,
            "Ag.conta": conta,
            "Quantidade": qtd,
            "Qtd": qtd,
            "Valor": valor,
            "Mês": mes_nome
        })

    df = pd.DataFrame(dados)
    return cliente, periodo, total_fatura, df