"""Importa a aba "Avanços" (DATA | CLIENTE - SNOVIO | AVANÇO) de um ou mais
.xlsx de squad pra tabela avancos (data, conta, quantidade) do dadoscampanha.

Uso:
    python db/migrar_avancos_xlsx.py arquivo1.xlsx arquivo2.xlsx ...

Idempotente: upsert por (data, conta) — rodar o mesmo arquivo de novo não duplica,
só atualiza a quantidade.
"""
import sys
import unicodedata
from datetime import datetime, date

import openpyxl
from sqlalchemy import text

from db.session import get_engine, create_tables


def _normaliza(texto: str) -> str:
    texto = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode("ascii")
    return texto.strip().lower()


def _acha_aba_avancos(wb):
    for nome in wb.sheetnames:
        if "avanco" in _normaliza(nome):
            return wb[nome]
    return None


def _acha_colunas(ws):
    """Acha os índices das colunas DATA / CLIENTE / AVANÇO pelo cabeçalho da
    primeira linha (tolera variação de acento/maiúscula e nome exato da coluna)."""
    cabecalho = {}
    for cel in ws[1]:
        if cel.value is None:
            continue
        chave = _normaliza(str(cel.value))
        cabecalho[chave] = cel.column

    col_data = next((v for k, v in cabecalho.items() if k == "data"), None)
    col_conta = next((v for k, v in cabecalho.items() if "cliente" in k), None)
    col_avanco = next((v for k, v in cabecalho.items() if "avanco" in k), None)

    faltando = [nome for nome, col in [("DATA", col_data), ("CLIENTE", col_conta)] if col is None]
    if faltando:
        raise ValueError(f"não achei a(s) coluna(s) {faltando} no cabeçalho da aba de avanços")

    if col_avanco is None:
        # planilha sem cabeçalho na 3ª coluna (comum nos arquivos de squad) —
        # segue a convenção DATA | CLIENTE | AVANÇO: usa a coluna logo após CLIENTE
        col_avanco = col_conta + 1
    return col_data, col_conta, col_avanco


def _formata_data(valor) -> str | None:
    if valor is None or valor == "":
        return None
    if isinstance(valor, (datetime, date)):
        return valor.strftime("%Y-%m-%d")
    texto = str(valor).strip()
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y"):
        try:
            return datetime.strptime(texto, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return None


def importa_arquivo(caminho: str) -> tuple[int, int]:
    wb = openpyxl.load_workbook(caminho, data_only=True)
    ws = _acha_aba_avancos(wb)
    if ws is None:
        print(f"  [pular] {caminho}: nenhuma aba de avanços encontrada (abas: {wb.sheetnames})")
        return 0, 0

    col_data, col_conta, col_avanco = _acha_colunas(ws)

    linhas = []
    for row in ws.iter_rows(min_row=2):
        data_raw = row[col_data - 1].value
        conta_raw = row[col_conta - 1].value
        avanco_raw = row[col_avanco - 1].value

        if not conta_raw or avanco_raw is None:
            continue
        data_fmt = _formata_data(data_raw)
        if not data_fmt:
            continue
        try:
            quantidade = int(float(avanco_raw))
        except (TypeError, ValueError):
            continue

        linhas.append((data_fmt, str(conta_raw).strip(), quantidade))

    if not linhas:
        print(f"  {caminho}: nenhuma linha válida encontrada")
        return 0, 0

    agora = datetime.utcnow()
    payload = [
        {"data": data_fmt, "conta": conta, "quantidade": quantidade, "criado_em": agora}
        for data_fmt, conta, quantidade in linhas
    ]
    sql = text("""
        INSERT INTO avancos (data, conta, quantidade, criado_em)
        VALUES (:data, :conta, :quantidade, :criado_em)
        ON DUPLICATE KEY UPDATE quantidade = VALUES(quantidade)
    """)
    with get_engine().begin() as conn:
        resultado = conn.execute(sql, payload)

    # MySQL: rowcount conta 1 por INSERT novo e 2 por UPDATE (linha existente alterada)
    afetados = resultado.rowcount
    print(f"  {caminho}: {len(linhas)} linha(s) na planilha -> upsert de {len(payload)} registro(s) (rowcount={afetados})")
    return len(payload), 0


def main(caminhos: list[str]):
    create_tables()
    total_inseridos = total_atualizados = 0
    for caminho in caminhos:
        i, a = importa_arquivo(caminho)
        total_inseridos += i
        total_atualizados += a
    print(f"\n✅ Total: {total_inseridos} inserido(s), {total_atualizados} atualizado(s)")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("uso: python db/migrar_avancos_xlsx.py arquivo1.xlsx [arquivo2.xlsx ...]")
        sys.exit(1)
    main(sys.argv[1:])
