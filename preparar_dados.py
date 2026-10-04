import pandas as pd

# lê o CSV grande do P05; parse_dates converte time_stamp de texto para data e hora
df = pd.read_csv("data/continuous_factory_process.csv", parse_dates=["time_stamp"])

# monta a lista de colunas que o app vai usar
colunas = ["time_stamp"]
colunas += [c for c in df.columns if c.startswith("Stage1.Output")]
colunas += [c for c in df.columns
            if c.startswith(("Machine1.", "Machine2.", "Machine3."))
            and ("MaterialPressure" in c or "MaterialTemperature" in c)]

# grava só essas colunas num arquivo menor; index=False não grava o número da linha
df[colunas].to_csv("data/processo_app.csv", index=False)

print(len(colunas), "colunas,", len(df), "linhas")
