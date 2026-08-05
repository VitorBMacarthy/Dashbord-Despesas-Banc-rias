import os
import tempfile
from flask import Flask, render_template, request, send_file
import pandas as pd
from utils.parser import processar_pdf

app = Flask(__name__)

# Usa a pasta temporária para evitar erros de permissão no Render
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

    if "pdf" not in request.files:
        return render_template("index.html", erro="Nenhum arquivo enviado.")

    arquivo = request.files["pdf"]
    if arquivo.filename == "":
        return render_template("index.html", erro="Selecione um arquivo PDF.")

    caminho_pdf = os.path.join(UPLOAD_FOLDER, arquivo.filename)

    try:
        arquivo.save(caminho_pdf)
        cliente, periodo, total, df = processar_pdf(caminho_pdf)

        if df.empty:
            return render_template("index.html",
                                   erro="Não foi possível identificar lançamentos de tarifas no PDF informado.")

        ULTIMO_DF = df

        # Agrupamento para Gráficos
        resumo_cat = df.groupby("Tarifa", as_index=False)["Valor"].sum()
        total_calculado = df["Valor"].sum()

        labels = resumo_cat["Tarifa"].tolist()
        valores = resumo_cat["Valor"].round(2).tolist()

        tabela = df.to_dict(orient="records")

        return render_template(
            "index.html",
            cliente=cliente,
            periodo=periodo,
            total=f"{total_calculado:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."),
            tabela=tabela,
            chart_labels=labels,
            chart_data=valores
        )

    except Exception as e:
        return render_template("index.html", erro=f"Erro no processamento do PDF: {str(e)}")
    finally:
        if os.path.exists(caminho_pdf):
            try:
                os.remove(caminho_pdf)
            except Exception:
                pass


@app.route("/exportar")
def exportar():
    global ULTIMO_DF
    if ULTIMO_DF is None or ULTIMO_DF.empty:
        return "Nenhum dado para exportar", 400

    caminho_excel = os.path.join(EXPORTS_FOLDER, "tarifas_bancarias.xlsx")

    df_export = ULTIMO_DF.copy()

    # Mapeamento para garantir retrocompatibilidade de nomes de colunas
    if "Categoria" not in df_export.columns and "Produto" in df_export.columns:
        df_export["Categoria"] = df_export["Produto"]
    if "Descricao" not in df_export.columns and "Tarifa" in df_export.columns:
        df_export["Descricao"] = df_export["Tarifa"]
    if "Conta" not in df_export.columns and "Ag.conta" in df_export.columns:
        df_export["Conta"] = df_export["Ag.conta"]
    if "Quantidade" not in df_export.columns and "Qtd" in df_export.columns:
        df_export["Quantidade"] = df_export["Qtd"]
    if "Mês" not in df_export.columns:
        df_export["Mês"] = "Janeiro"

    # Seleciona as colunas na ordem desejada incluindo 'Mês'
    colunas_finais = ["Data", "Categoria", "Descricao", "Conta", "Quantidade", "Valor", "Mês"]
    df_export = df_export[colunas_finais]

    with pd.ExcelWriter(caminho_excel, engine="openpyxl") as writer:
        df_export.to_excel(writer, sheet_name="Lançamentos", index=False)

        resumo = df_export.groupby("Categoria")["Valor"].agg(["sum", "count"]).rename(
            columns={"sum": "Total (R$)", "count": "Qtd Lançamentos"}
        )
        resumo.to_excel(writer, sheet_name="Resumo por Categoria")

    return send_file(caminho_excel, as_attachment=True, download_name="Tarifas_Bancarias.xlsx")


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)