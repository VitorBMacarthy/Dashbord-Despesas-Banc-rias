import os
import tempfile
from flask import Flask, render_template, request, send_file
import pandas as pd
from utils.parser import processar_pdf

app = Flask(__name__)

# Diretórios temporários para manipular uploads e arquivos exportados
UPLOAD_FOLDER = os.path.join(tempfile.gettempdir(), "uploads")
EXPORTS_FOLDER = os.path.join(tempfile.gettempdir(), "exports")

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(EXPORTS_FOLDER, exist_ok=True)

ULTIMO_DF = None


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/upload", methods=["POST"])
def upload():
    global ULTIMO_DF

    # Recebe múltiplos arquivos do input 'pdfs'
    arquivos = request.files.getlist("pdfs")
    if not arquivos or arquivos[0].filename == "":
        return render_template(
            "index.html", erro="Selecione ao menos um arquivo PDF."
        )

    todos_dfs = []
    cliente_nome = "Cliente Não Identificado"

    try:
        for arquivo in arquivos:
            if arquivo and arquivo.filename.endswith(".pdf"):
                caminho_pdf = os.path.join(UPLOAD_FOLDER, arquivo.filename)
                arquivo.save(caminho_pdf)

                # Processa o PDF individual
                cliente, periodo, total, df = processar_pdf(caminho_pdf)
                if not df.empty:
                    todos_dfs.append(df)
                    if cliente:
                        cliente_nome = cliente

                # Remove o arquivo temporário após a leitura
                if os.path.exists(caminho_pdf):
                    os.remove(caminho_pdf)

        if not todos_dfs:
            return render_template(
                "index.html",
                erro="Nenhum dado válido de tarifa foi encontrado nos PDFs enviados.",
            )

        # Consolidação de todos os DataFrames extraídos
        df_consolidado = pd.concat(todos_dfs, ignore_index=True)
        ULTIMO_DF = df_consolidado

        # Ordenação lógica dos meses
        ordem_meses = [
            "Janeiro",
            "Fevereiro",
            "Março",
            "Abril",
            "Maio",
            "Junho",
            "Julho",
            "Agosto",
            "Setembro",
            "Outubro",
            "Novembro",
            "Dezembro",
        ]

        # Filtra os meses que realmente existem nos PDFs enviados
        meses_presentes = [
            m for m in ordem_meses if m in df_consolidado["Mês"].unique()
        ]

        # Resumo da Evolução Mensal para o gráfico de linha (Ano Todo)
        evolucao = df_consolidado.groupby("Mês", as_index=False)["Valor"].sum()
        evolucao["Mês"] = pd.Categorical(
            evolucao["Mês"], categories=ordem_meses, ordered=True
        )
        evolucao = evolucao.sort_values("Mês")

        chart_evolucao = {
            "labels": evolucao["Mês"].astype(str).tolist(),
            "valores": evolucao["Valor"].round(2).tolist(),
        }

        total_calculado = df_consolidado["Valor"].sum()
        tabela = df_consolidado.to_dict(orient="records")

        return render_template(
            "index.html",
            cliente=cliente_nome,
            total=f"{total_calculado:,.2f}".replace(",", "X")
            .replace(".", ",")
            .replace("X", "."),
            tabela=tabela,
            meses_disponiveis=meses_presentes,
            chart_evolucao=chart_evolucao,
        )

    except Exception as e:
        return render_template(
            "index.html", erro=f"Erro ao processar os PDFs: {str(e)}"
        )


@app.route("/exportar")
def exportar():
    global ULTIMO_DF
    if ULTIMO_DF is None or ULTIMO_DF.empty:
        return "Nenhum dado para exportar", 400

    # Recebe o parâmetro ?mes= passados pela URL pelo JavaScript
    mes_filtro = request.args.get("mes", "TODOS")

    df_export = ULTIMO_DF.copy()

    # Aplica o filtro se um mês específico tiver sido selecionado
    if mes_filtro != "TODOS":
        df_export = df_export[
            df_export["Mês"].str.lower() == mes_filtro.lower()
        ]
        nome_arquivo = f"tarifas_bancarias_{mes_filtro.lower()}.xlsx"
        nome_aba_resumo = f"Resumo - {mes_filtro}"
    else:
        nome_arquivo = "tarifas_bancarias_anual.xlsx"
        nome_aba_resumo = "Resumo por Mês"

    if df_export.empty:
        return "Nenhum dado encontrado para o período selecionado.", 404

    caminho_excel = os.path.join(EXPORTS_FOLDER, nome_arquivo)

    colunas_finais = [
        "Data",
        "Categoria",
        "Descricao",
        "Conta",
        "Quantidade",
        "Valor",
        "Mês",
    ]
    df_export = df_export[colunas_finais]

    with pd.ExcelWriter(caminho_excel, engine="openpyxl") as writer:
        # Aba com os lançamentos detalhados
        df_export.to_excel(writer, sheet_name="Lançamentos", index=False)

        # Aba de resumo dinâmica
        if mes_filtro == "TODOS":
            resumo_mes = (
                df_export.groupby(["Mês", "Categoria"])["Valor"]
                .sum()
                .unstack(fill_value=0)
            )
            resumo_mes.to_excel(writer, sheet_name=nome_aba_resumo)
        else:
            resumo_cat = (
                df_export.groupby("Categoria")["Valor"]
                .agg(["sum", "count"])
                .rename(
                    columns={"sum": "Total (R$)", "count": "Qtd Lançamentos"}
                )
            )
            resumo_cat.to_excel(writer, sheet_name=nome_aba_resumo)

    return send_file(
        caminho_excel, as_attachment=True, download_name=nome_arquivo
    )


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)