from rotina import acao
from db.session import create_tables

create_tables()

print("Inicio do relatório de Campanhas")

for data in ['2026-06-16', '2026-06-17', '2026-06-18', '2026-06-19', '2026-06-20', '2026-06-21', '2026-06-22']:
    print(f"\n=== Processando {data} ===")
    acao.extrai_dia_anterior_custom(data)

acao.atualiza_planilhas_controle()

print("Conclusão do relatório de Campanhas")