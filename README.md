# Controle de Campanhas

Aplicação para coleta de campanhas Snov.io, análise por cliente/squad, publicação
em Google Sheets e operação por uma equipe com acessos individuais.

## Acesso local

Requisitos: Python 3.12 e [uv](https://docs.astral.sh/uv/).

```powershell
uv sync --frozen
uv run python tools/setup_env.py --admin-email labs.ativaai@gmail.com
uv run python tools/run_local.py
```

Abra **http://127.0.0.1:8000/login.html**. A senha inicial gerada fica no arquivo
local privado `data/primeiro-acesso.txt`, ignorado pelo Git. Não há senha padrão.
No primeiro acesso, o administrador pode cadastrar os colegas em **Equipe**.

O modo local cria `data/local.db`, separado do banco remoto, e inicia API e
executor. Não injeta dados fictícios, não inicia o scheduler e desabilita a
publicação Google Sheets. As integrações configuradas no `.env` são usadas
quando o administrador solicita uma coleta. Para parar, use Ctrl+C.

## Implantação para a equipe

1. Prepare `.env` com `tools/setup_env.py`; ele preserva credenciais existentes
   e pode incorporar variáveis da antiga `painel-api/.env` sem expor os valores.
2. Configure o MySQL principal, as integrações e o administrador conforme
   `.env.example`. O serviço MySQL precisa ser acessível pelos contêineres.
3. Para uma base existente, pare o scheduler antigo e a API antiga. Faça backup
   do banco antes da migração, preferencialmente também com a ferramenta do DBA.
4. Confira a configuração e inicie os serviços:

```bash
docker compose config --quiet
docker compose up -d --build
docker compose ps
docker compose logs --tail=100 migrate api worker scheduler
```

O Compose sobe migração, API, executor, agendador e backup. A API só publica
`127.0.0.1:8000` no host. As telas e a API usam a mesma origem; não é necessário
publicar o frontend em outro serviço. O servidor HTTP é Waitress, com execução
dos jobs fora das threads HTTP.

Com DNS apontando para o servidor, configure `PUBLIC_DOMAIN`, `TLS_EMAIL`,
`COOKIE_SECURE=true` e `TRUST_PROXY=true`, e execute:

```bash
docker compose --profile https up -d --build
```

O Caddy providencia HTTPS e encaminha as requisições à API. As portas 80 e 443
devem estar disponíveis. Se já houver proxy HTTPS no servidor, mantenha-o e
encaminhe para `127.0.0.1:8000`. Habilite `TRUST_PROXY` somente com proxy confiável.
Sem HTTPS, use apenas acesso local com `COOKIE_SECURE=false`.

Para um MySQL novo administrado pelo Compose, configure `MYSQL_PASSWORD` e
`MYSQL_ROOT_PASSWORD`, use `DATABASE_URL` com host `mysql` e inicie:

```bash
docker compose -f docker-compose.yml -f compose.local.yml up -d --build
```

Esse banco não publica sua porta no host. Para aproveitar o histórico existente,
use o banco atual em vez de criar uma base vazia.

## Configuração das integrações

| Variáveis | Uso |
|---|---|
| `DATABASE_URL` | Banco principal MySQL; SQLite somente para operação local/testes |
| `SECRET_KEY` | Assina as sessões, gerada pelo setup e preservada entre reinícios |
| `ADMIN_EMAIL`, `ADMIN_PASSWORD` | Criação inicial do administrador; não sobrescrevem usuário existente |
| `CREDENTIALS_API_URL`, `CREDENTIALS_API_KEY` | Listagem de contas e credenciais Snov.io |
| `AVANCOS_API_URL`, `AVANCOS_API_KEY` | API oficial de avanços; chave opcional conforme contrato da origem |
| `AVANCOS_API_KEY_HEADER` | Header da chave, padrão `X-API-Key` |
| `AVANCOS_FRONTEND_URL` | Destino do botão “Registrar avanço” |
| `SEMAFORO_TIPOS` | Tipos que contam, separados por vírgula; padrão `Interessado` |
| `LISTAS_SQUAD_DATABASE_URL` | Conexão opcional, somente leitura, para o cadastro externo de squads |
| `SQUAD_MAPPING_TABLE` | Tabela externa, padrão `relatoriolistas.listas_squad` |
| `GOOGLE_MASTER_SHEET_ID` | Identificador da planilha mestre existente |
| `GOOGLE_CREDENTIALS_HOST_PATH` | Arquivo Google no host, montado como segredo somente leitura |
| `GOOGLE_SHEETS_ENABLED` | Habilita a publicação das planilhas |
| `ALERT_WEBHOOK_URL` | Destino opcional para alerta de execução parcial ou com falha |

O arquivo Google pode ser a credencial OAuth já existente ou uma service account.
A conta deve ter acesso à planilha mestre e às planilhas de controle. O segredo
não entra no build. No Linux, o arquivo montado precisa permitir leitura ao UID
10001 do contêiner, com acesso restrito no host. URLs públicas das integrações devem usar HTTPS; conexões HTTP
em rede privada são aceitas. A exceção `ALLOW_INSECURE_INTEGRATIONS=true` é
explícita e deve ser usada apenas enquanto uma integração legada é adequadamente protegida.

O contrato consumido da API de avanços permanece o existente:
`/credenciais`, `/avancos` paginado e `/avancos/opcoes`. Esta entrega não altera o
backend externo. O painel envia a chave configurada; a proteção da origem deve
ser habilitada no próprio serviço externo.

Sem conexão externa de squads, a tabela `painel_squad_mapping` permite mapear
`campanha_id` para `squad`. Campanhas sem vínculo aparecem em **Sem squad**.
Clientes ligados a mais de um squad aparecem em **Multissquad**, uma única vez,
para não duplicar os avanços do cliente. Os aliases ficam em
`painel_client_aliases`; alterações de aliases refletem em até 60 segundos.

## Funcionamento e regras

- Perfis: **Consulta** acessa dashboard e análise; **Administrador** gerencia
  usuários, sincronização, histórico e reprocessamento.
- O painel usa sessão HttpOnly com CSRF. O antigo token compartilhado fica
  desabilitado; `ALLOW_LEGACY_TOKEN=true` serve apenas para compatibilidade explícita.
- As contas para seleção vêm do espelho local. No primeiro uso, rode **Extrair
  campanhas** para alimentar o cadastro; isso lê as contas ativas da origem.
- Às 01:00 de São Paulo, o scheduler enfileira o dia fechado anterior. Após
  reinício, recupera até sete datas de atraso desde a última data enfileirada.
  Atrasos maiores devem ser recuperados pela extração de intervalo.
- Jobs persistem no banco. O executor serializa a execução com trava compartilhada
  e, no MySQL, trava de conexão. Reinício inesperado marca trabalhos interrompidos
  após expiração da concessão; não repete publicações silenciosamente.
- Uma coleta falha ou parcial preserva os acertos e registra quais campanhas
  faltaram. A tela **Operação** oferece reprocessamento dos parâmetros originais.
- Campanhas pausadas permanecem disponíveis para recuperação histórica, desde
  que ainda haja credencial de acesso à conta. O cache só conhece campanhas já
  sincronizadas; campanhas apagadas antes da primeira sincronização dependem de
  recuperação na origem ou do histórico existente.
  Campanhas removidas e contas inativas não entram em novas consultas; seus
  dados históricos permanecem disponíveis no banco e nas análises.
- A chave única por campanha/data e o upsert tornam a reexecução idempotente.
- A planilha mestre é publicada a partir do cadastro completo no banco, nunca
  apenas da seleção. Substituições usam um único batch de valores, preservando
  o identificador da aba. Falhas parciais de sincronização não publicam a mestre.
- **Avanços vêm exclusivamente do sistema externo.** O formulário local antigo
  foi removido; suas rotas retornam 410. A tabela antiga é preservada como histórico.
- O semáforo considera os três dias fechados anteriores a hoje: dois ou mais
  Interessados = verde; um = amarelo; zero = vermelho. Tipos são configuráveis.
- As datas inicial e final são inclusivas. Últimos 30 dias usa exatamente 30
  datas. Dias de disparo contam a união de datas das contas do cliente.
- O dashboard mostra a última coleta de cada campanha e avisa quando as datas
  diferem ou estão atrasadas. Isso é diferente do resumo por período da análise.
- Se uma integração falhar, o último valor válido pode ser usado por até 24 horas
  com aviso e data. Sem cache, os avanços ficam indisponíveis, em vez de zero.

## Migração de dados

```bash
uv run python -m manage migrate
```

A versão `0001_integrity_and_operations` cria tabelas de operação, acessos,
auditoria, cache, aliases e restrições. Ela é repetível e não descarta duplicatas
silenciosamente. Se encontrar duplicatas, interrompe a criação das respectivas
restrições. Depois de conferir o backup, use explicitamente:

```bash
uv run python -m manage migrate --resolve-duplicates
```

Para cada campanha/data e conta/data de avanço legado, mantém o registro de maior
`id` e arquiva integralmente os anteriores em `painel_data_repairs`. Não soma
contadores de versões repetidas. Pare os escritores antigos antes da migração.
Em MySQL, DDL pode confirmar transações implicitamente; uma falha pode deixar
tabelas novas já criadas. Corrija a causa e reexecute a migração.

Para administração via terminal:

```bash
uv run python -m manage user pessoa@empresa.com --role viewer
uv run python -m manage user administrador@empresa.com --role admin
```

As senhas são solicitadas sem eco. Alterar acesso invalida as sessões anteriores.

## Backup e recuperação

O serviço de backup grava diariamente `backups/*.jsonl.gz`, com retenção local de
14 dias. Os arquivos contêm dados e hashes de senha; mantenha acesso restrito e
uma cópia externa ao servidor. O backup do aplicativo cobre suas tabelas no banco
principal; o cadastro externo de squads e o sistema de avanços exigem seus próprios backups.

```bash
uv run python -m manage backup backups/antes-da-atualizacao.jsonl.gz
uv run python -m manage restore backups/antes-da-atualizacao.jsonl.gz
```

A restauração exige esquema criado e banco vazio. Para substituir uma base
existente, pare os serviços escritores e acrescente `--replace` explicitamente.
Uma restauração invalida as sessões e marca jobs em execução como interrompidos.
Teste a restauração em uma base separada antes de depender do backup operacional.

## Verificação e monitoramento

O frontend é escrito em Vue 3, JavaScript e CSS em `frontend/`. As cinco rotas
HTML continuam sendo servidas pelo Flask. Os arquivos compilados em
`painel-frontend/` são incluídos na entrega para manter o servidor Python sem
dependência de Node em produção. Para editar e recompilar a interface:

```bash
npm ci --prefix frontend
npm --prefix frontend run dev
npm --prefix frontend test
npm --prefix frontend run build
```

O servidor de desenvolvimento encaminha `/api` para `127.0.0.1:8000`. O build usa
fontes e ícones locais e mantém a política de segurança de scripts do servidor.
Os dados de `frontend/tests/fixtures.json` são exclusivamente de teste e não são
importados pela aplicação nem incluídos como demonstração nas telas reais.

```bash
uv run pytest -q -m "not browser and not mysql"
uv run playwright install --no-shell chromium
uv run pytest -q -m browser
uv run python tools/check_secrets.py
uv run pip-audit --disable-pip --no-deps --require-hashes -r requirements.txt
```

Para testes MySQL, defina `MYSQL_TEST_URL` apontando para uma base **descartável**
cujo nome termine em `_test`, e rode `uv run pytest -q -m mysql`. Esse teste limpa
somente a base de teste informada. O CI também executa os testes, a auditoria e o build.

`/api/health` informa vivacidade e `/api/ready` verifica banco e migração.
`/api/jobs`, `/api/logs` e `/api/audit` exigem administrador. Os logs usam cursor
monotônico e permanecem disponíveis após reinício. Configure um monitor externo
para prontidão, armazenamento dos backups e jobs sem conclusão. A prontidão HTTP
não comprova o funcionamento das APIs externas: confira os avisos e os resultados
de uma coleta real controlada antes de liberar os relatórios para toda a equipe.

## Segredos e histórico

Os segredos foram retirados do código atual e são carregados do ambiente/arquivos
montados. Nenhuma credencial foi revogada. O histórico Git anterior não foi
reescrito e ainda pode conter a chave antiga. `tools/check_secrets.py` verifica
padrões de chave SendGrid e chaves privadas no código atual, não todo tipo possível
de segredo nem o histórico completo.
