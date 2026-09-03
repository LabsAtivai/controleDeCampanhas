import pygsheets
import pandas as pd
import json
import httpx
from datetime import datetime, timedelta, date
from concurrent.futures import ThreadPoolExecutor, as_completed
from rotina import api
from db import crud
import warnings
warnings.simplefilter(action='ignore', category=FutureWarning)
import time
import threading

from rotina import acao
from datetime import datetime, timedelta

data_inicio = datetime(2026, 6, 22)
data_fim = datetime(2026, 6, 25)

data_atual = data_inicio

while data_atual <= data_fim:
    if data_atual.weekday() < 5:
        data_str = data_atual.strftime("%Y-%m-%d")
        print(f"\nProcessando data: {data_str}")
        acao.extrai_dia_anterior_custom(data_str)
    else:
        print(f"\nPulando fim de semana: {data_atual.strftime('%Y-%m-%d')}")

    data_atual += timedelta(days=1)

print("\nProcesso completo ate hoje finalizado.")