import os
from flask import Flask, render_template, request, send_file
import pandas as pd
from utils.parser import processar_pdf

app = Flask(__name__)
UPLOAD_FOLDER = "uploads"
EXPORTS_FOLDER = "exports"

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

    caminho_pdf = os.path.join(app.config["UPLOAD_FOLDER"], arquivo.filename)
    arquivo.save(caminho_pdf)

    try:
        cliente, periodo, total, df = processar_pdf(caminho_pdf)

        if df.empty:
            return render_template("index.html",
                                   erro="Não foi possível identificar lançamentos de tarifas no PDF informado.")

        ULTIMO_DF = df

        # Agrupamento para os Gráficos por Tarifa
        resumo_cat = df.groupby("Tarifa", as_index=False)["Valor"].sum()
        total_calculado = df["Valor"].sum()

        labels = resumo_cat["Tarifa"].tolist()
        valores = resumo_cat["Valor"].round(2).tolist()

        # Converte garantindo as 7 colunas exatas
        tabela = df[["Data", "Tarifa", "Produto", "Ag.conta", "Qtd", "Valor", "Mês"]].to_dict(orient="records")

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
        return render_template("index.html", erro=f"Erro ao processar o PDF: {str(e)}")


@app.route("/exportar")
def exportar():
    global ULTIMO_DF
    if ULTIMO_DF is None or ULTIMO_DF.empty:
        return "Nenhum dado para exportar", 400

    caminho_excel = os.path.join(EXPORTS_FOLDER, "tarifas_bancarias.xlsx")

    colunas_exportacao = ["Data", "Tarifa", "Produto", "Ag.conta", "Qtd", "Valor", "Mês"]
    df_export = ULTIMO_DF[colunas_exportacao]

    with pd.ExcelWriter(caminho_excel, engine="openpyxl") as writer:
        df_export.to_excel(writer, sheet_name="Banco do Brasil", index=False)

        resumo = ULTIMO_DF.groupby("Tarifa")["Valor"].agg(["sum", "count"]).rename(
            columns={"sum": "Total (R$)", "count": "Qtd Lançamentos"}
        )
        resumo.to_excel(writer, sheet_name="Resumo por Tarifa")

    return send_file(caminho_excel, as_attachment=True, download_name="Tarifas_Bancarias.xlsx")


if __name__ == "__main__":
    app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
    app.run(debug=True)