from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger
from rotina import acao
from db.session import create_tables
import pytz

tz = pytz.timezone('America/Sao_Paulo')

create_tables()

print("Sistema Iniciado")

def tarefa_cron():
    acao.extrai_campanhas()
    acao.extrai_dia_anterior() 
    acao.atualiza_planilhas_controle()


if __name__ == "__main__":
    scheduler = BlockingScheduler(timezone=tz)

    scheduler.add_job(tarefa_cron, CronTrigger(hour=6, minute=0))
    
    print("Scheduler iniciado. Pressione CTRL+C para sair.")
    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        print("Encerrando scheduler...")