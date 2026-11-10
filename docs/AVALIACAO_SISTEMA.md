# Avaliação do sistema de controle de campanhas

Data: 10/11/2026. Código analisado: commit `d42f2ef`.

Este documento preserva o diagnóstico anterior às correções. Para o funcionamento
e os procedimentos atuais, consulte o README da raiz e o histórico de alterações
do Git. Os resultados aqui registrados descrevem a versão originalmente avaliada.

## Parecer

O sistema cobre coleta diária, reprocessamento, armazenamento, publicação em planilhas e análise por cliente/squad. Entretanto, o estado avaliado apresenta falhas de segurança, implantação e integridade que precisam ser corrigidas antes de considerar os indicadores e a operação confiáveis para produção.

As prioridades são revogar a chave exposta, corrigir a injeção de JavaScript no painel, recuperar a implantação da API e impedir que sincronizações parciais apaguem a lista completa de campanhas. Também é necessário tornar falhas de coleta visíveis e garantir unicidade dos registros no banco.

Este relatório avalia o repositório e comportamentos locais. Não atesta o estado atual do VPS, a validade das credenciais, a completude da base real ou a disponibilidade dos serviços externos.

## Escopo e método

- Leitura dos 16 arquivos Python, três telas HTML/JavaScript, Dockerfiles, arquivos Compose, modelos, clientes HTTP, scripts auxiliares e documentação de integração.
- Validação sintática dos 16 arquivos Python e dos scripts das três páginas.
- Testes com o cliente Flask, banco SQLite descartável, relógio controlado e serviços externos simulados.
- Execução da tela de análise em Chromium com Playwright. Todas as requisições foram interceptadas; os dados e o token usados eram fictícios.
- Verificação do comando de entrada da API em subprocesso sem `PYTHONPATH` e sem `DATABASE_URL`.
- Consulta à documentação oficial de Docker e Flask para conferir as observações de implantação.

Nenhum job real de extração, envio ou exclusão foi executado. Não houve alteração de banco, planilha ou serviço externo. O script auxiliar de validação ficou no diretório temporário do Windows, fora do código da aplicação.

Limitações: Docker Desktop sem daemon disponível; não foi possível construir/iniciar os contêineres. O Python disponível era 3.12.4, enquanto o projeto declara 3.13 e os contêineres usam 3.11. Os testes SQLite validam os comportamentos descritos, mas não substituem testes de concorrência, desempenho ou migração em MySQL. Não foi realizada auditoria de vulnerabilidades de todas as dependências transitivas, teste de carga, restauração de backup ou inspeção da configuração do servidor publicado.

## Arquitetura observada

| Parte | Responsabilidade | Dependências |
|---|---|---|
| `app.py` | Agenda a sequência diária de coleta e publicação | APScheduler, credenciais, Snov.io, MySQL, Sheets |
| `rotina/credentials_api.py` | Lista contas e busca credenciais | Sistema de credenciais, chave de API |
| `rotina/acao.py` | Orquestra campanhas, métricas e planilhas | Clientes HTTP, pandas, SQLAlchemy, pygsheets |
| `db/crud.py` e `db/models.py` | Persistência e consultas | MySQL |
| `db/dashboard.py` | Agregação por squad e cliente | Dois bancos MySQL e API de avanços |
| `db/avancos_api.py` | Mapeamento de clientes, avanços e semáforo | API externa, cache em memória |
| `painel-api/server.py` | Consulta de dados e execução manual de jobs | Flask, threads, token compartilhado |
| `painel-frontend/` | Operação, dashboard e análise | API, token no localStorage |

`main.py` é um reprocessamento de datas fixas; o agendador efetivo está em `app.py`. O arquivo `teste.py` também executa uma atualização real de planilhas ao ser importado/executado: não é uma suíte de testes.

## Achados críticos

### 1. Chave SendGrid exposta no código versionado

**Evidência:** `sendgrid.js:2` contém uma chave em texto claro e o arquivo consta em `git ls-files`. O valor não é reproduzido aqui. Não foi testado se a chave ainda é válida.

**Impacto:** quem obtiver o código pode tentar usar as permissões da chave. O próprio script utiliza a chave para exclusão de bloqueios e chama `main()` automaticamente.

**Correção:** revogar/rotacionar a chave no provedor, carregar a substituta por variável de ambiente, revisar permissões e acessos e remover o segredo do histórico conforme a política do repositório. Excluir apenas a linha atual não resolve a exposição de versões anteriores. Não executar o script durante testes genéricos.

### 2. Injeção de JavaScript pelo nome de cliente

**Evidência:** `painel-frontend/analise.html:247` e `:276` interpolam `l.cliente` diretamente em um atributo `onclick`. Escapar apenas apóstrofos não protege o contexto HTML.

**Reprodução:** um nome fictício com aspas duplas introduziu um atributo de evento; o Chromium executou o marcador local ao disparar o evento. Nenhum dado foi transmitido. A presença desse conteúdo na fonte externa tornaria a falha persistente.

**Impacto:** código pode executar na origem do painel e ler o token de `localStorage`, dando acesso às ações protegidas pela mesma credencial.

**Correção:** criar as linhas com APIs DOM, preencher texto com `textContent` e associar eventos com `addEventListener`. Evitar inserir dados em código JavaScript de atributos HTML. Adotar CSP como proteção complementar e rever a persistência do token.

## Achados de prioridade alta

### 3. Implantação da API contém dois bloqueios independentes

**Evidência:** `.dockerignore:20` exclui `painel-api/`, mas `painel-api/Dockerfile:18` usa `COPY . .` e o comando final tenta executar `painel-api/server.py`. Não há arquivo de ignore específico desse Dockerfile que reintroduza o diretório.

Mesmo disponibilizando o arquivo, o comando `python -u painel-api/server.py` não configura a raiz como caminho de importação. A execução local sem `PYTHONPATH` terminou com `ModuleNotFoundError: No module named 'db'`.

**Impacto:** a implantação descrita não inicia corretamente em um ambiente limpo.

**Correção:** ajustar o contexto/ignore e o empacotamento; definir uma entrada por módulo ou uma aplicação WSGI com caminho de importação explícito. Validar a imagem a partir de um clone limpo. O bloqueio de cópia foi identificado estaticamente; não foi executado um build, pois o daemon Docker estava indisponível.

### 4. Sincronização seletiva substitui a lista completa da planilha mestre

**Evidência:** `rotina/acao.py:43` filtra as contas selecionadas, mas `:90` envia esse subconjunto para `atualiza_aba_campanhas_master()`. A função chama `aba.clear()` em `:117` e escreve somente o resultado recebido.

**Reprodução:** a planilha simulada recebeu `clear()` seguido de dados de uma única conta selecionada. Uma coleta completa com falhas parciais sofre o mesmo risco, pois as contas que falharam viram DataFrames vazios.

**Impacto:** contas não selecionadas ou com falha desaparecem dos dropdowns alimentados pela planilha mestre. A limpeza anterior à escrita também deixa a aba vazia se a escrita falhar.

**Correção:** publicar uma visão completa do banco após sincronização bem-sucedida, preservar contas não processadas e evitar a limpeza antes de ter uma substituição validada.

### 5. Coleta inteiramente malsucedida pode terminar como sucesso

**Evidência:** `rotina/acao.py:160` e `:255` capturam erros por campanha e retornam `None`. Esgotadas as tentativas, as funções persistem o que houver e retornam normalmente. `painel-api/server.py:99` trata qualquer retorno normal como sucesso.

**Reprodução:** todas as consultas de métricas falharam; após as tentativas simuladas, a rotina customizada retornou normalmente e enviou zero linhas para persistência.

**Impacto:** o operador recebe uma indicação positiva apesar de lacunas ou ausência total de dados. A execução agendada pode continuar publicando uma base desatualizada.

**Correção:** devolver totais esperados, coletados e falhos; distinguir sucesso, parcial e falha; propagar erro quando não houver coleta e registrar uma fila de reprocessamento.

### 6. Banco não garante unicidade por campanha e dia

**Evidência:** `db/models.py:7` possui apenas a chave primária artificial; `db/crud.py:12` faz consulta seguida de inserção. Não existe restrição única declarada para a chave de negócio usada pela rotina.

**Reprodução:** o esquema criado pelos modelos aceitou dois registros com o mesmo `id_conta` e `data`.

**Impacto:** execuções concorrentes podem duplicar métricas, e a atualização posterior com `.first()` não elimina a duplicata. `RUN_LOCK` da API não coordena o scheduler em outro processo/contêiner.

**Correção:** conferir a chave de negócio, tratar duplicatas existentes e criar restrição única por migração. Usar upsert atômico e coordenação de execução compartilhada. Não se verificou se a base de produção possui restrições adicionais criadas manualmente.

### 7. Avanço cadastrado pelo painel não entra nos indicadores

**Evidência:** `painel-api/server.py:194` grava via `crud.cria_avanco()` na tabela local. `db/dashboard.py` e `crud.get_analise_cliente()` leem avanços por `db/avancos_api.py`, sem consumir essa tabela. O frontend recarrega a lista local, mas os KPIs continuam vindo da integração externa.

**Impacto:** o formulário confirma o registro, porém os totais e o semáforo não refletem essa inclusão. Há duas fontes independentes para a mesma operação aparente.

**Correção:** definir a fonte oficial e conectar o fluxo a ela. Se o sistema externo for a fonte, direcionar o cadastro para ele e tratar os registros locais como histórico. A documentação existente já registra essa dívida; a proposta de migração ainda se declara não aplicada.

### 8. Sincronização preserva campanhas removidas e dificulta recuperar histórico

**Evidência:** `db/crud.py:107` apenas insere/atualiza contas presentes; campanhas ausentes não são desativadas e contas ausentes não recebem status inativo. `get_campanhas_ativas()` filtra apenas o status da campanha.

**Reprodução:** sincronizar uma campanha ativa e depois uma lista vazia para a mesma conta manteve a campanha disponível como ativa.

Além disso, `extrai_dia_anterior_custom()` usa as campanhas **atualmente ativas** (`rotina/acao.py:229`). Uma campanha que teve atividade na data escolhida e depois foi pausada não entra no reprocessamento.

**Impacto:** cache divergente da origem e recuperação histórica incompleta.

**Correção:** diferenciar resposta vazia válida de falha de coleta, reconciliar ausências somente após uma coleta completa e usar cadastro histórico adequado para backfill.

### 9. Segredo do Google pode ser incorporado às imagens

**Evidência:** o arquivo local `sheets.googleapis.com-python.json` existe e está ignorado pelo Git, mas não por `.dockerignore`. Os dois Dockerfiles usam `COPY . .`. O scheduler já possui montagem de credencial em volume somente leitura.

**Impacto:** uma construção com esse arquivo presente o incorpora à imagem e potencialmente ao registro de imagens. Ignorar no Git não protege o contexto Docker.

**Correção:** excluir a credencial do build, usar montagem de segredo em ambos os serviços e revisar imagens já distribuídas. Não foi construída nem inspecionada uma imagem existente nesta avaliação.

## Achados de prioridade média

### 10. Falha na API de avanços derruba consultas, apesar do cache

`db/avancos_api.py:28` mantém valores por 60 segundos; quando expiram, qualquer falha da origem é propagada. O comportamento foi reproduzido com relógio controlado. As rotas de dashboard retornam 500, inclusive quando as métricas MySQL estão disponíveis.

O cliente usa HTTP sem autenticação no código, com endereço público como fallback em `:24`. Isso não comprova a configuração efetiva de produção, mas revela ausência de suporte explícito a uma credencial nessa integração.

**Correção:** separar indisponibilidade de zero avanços, servir último valor conhecido com data e aviso quando apropriado, usar transporte protegido e uma credencial dedicada, limitar o cache e aplicar retentativa controlada. O cache atual não remove entradas antigas de filtros distintos e existe apenas por processo.

### 11. Validação de entradas permite dados inválidos e erros 500

No cliente Flask, `POST /api/avancos` aceitou `quantidade=-3` com status 201 e converteu `1.9` para `1`. Data numérica e JSON em lista produziram 500. `/api/logs?since=abc` também produziu 500.

`run_custom()` e a rota de seleção também pressupõem determinados tipos de JSON. Não há validação robusta de conta, limites de quantidade ou tamanho da seleção.

**Correção:** validar objeto JSON, tipos exatos, datas canônicas, limites e valores permitidos antes de converter/persistir. Dados inválidos devem produzir 400/422 com mensagem útil.

### 12. Filtros e contagem de dias podem gerar análises incorretas

- `db/crud.py:199` e `db/dashboard.py:110` só filtram métricas quando **ambas** as datas estão preenchidas; a integração de avanços aplica cada limite separadamente. No teste, pedir início em 09/11 também devolveu métricas de 01/11.
- `db/dashboard.py:142` usa o maior número de dias entre contas, em vez da união dos dias do cliente. Duas contas com um dia distinto cada resultaram em um dia, quando o correto seria dois.
- O botão “Últimos 30 dias” usa hoje menos 30 dias até hoje, inclusivamente, o que corresponde a 31 datas.

**Correção:** adotar validação e semântica de período únicas, aplicar limites independentemente ou rejeitar intervalo incompleto e contar datas distintas após agrupar as contas do cliente.

### 13. Logs deixam de atualizar depois de 5.000 entradas

`painel-api/server.py:22` usa `deque(maxlen=5000)`. A rota `:136` trata `since` como índice desse buffer e retorna seu comprimento como cursor. Quando ele fica cheio, o cursor permanece em 5000, embora as linhas continuem sendo substituídas.

**Reprodução:** após uma nova entrada no buffer cheio, `since=5000` retornou `lines=[]` e `total=5000`.

**Correção:** usar identificadores monotônicos de log independentes do tamanho do buffer, informar perda de linhas e tratar reinício do servidor. Persistir histórico de execução e erros fora da memória.

### 14. Jobs e estado não sobrevivem a reinícios nem coordenam serviços

`painel-api/server.py:81` inicia uma thread daemon e guarda locks, estado e logs em memória. Reiniciar o serviço interrompe o trabalho e perde o histórico. Vários processos WSGI terão locks e estados diferentes. O scheduler separado pode executar simultaneamente.

**Correção:** usar execução durável com estado persistente e trava compartilhada ou um executor único. Trocar apenas o servidor HTTP por vários workers não resolve o modelo de jobs atual.

O `/api/health` retorna sucesso fixo e não demonstra disponibilidade das dependências; convém separar vivacidade do processo de prontidão para operar.

### 15. Visões podem omitir clientes ou misturar datas diferentes

`db/dashboard.py:37` e `:98` usam `JOIN` obrigatório com `listas_squad`; contas sem mapeamento não aparecem. O resumo principal usa a última data **por campanha**, podendo somar números de dias diferentes em uma mesma linha e exibir a maior data como referência.

**Impacto:** totais podem parecer completos e atuais mesmo com contas ausentes ou campanhas sem coleta recente. Um cliente presente em vários squads recebe o total externo de avanços em cada grupo; uma consolidação entre squads precisa evitar dupla contagem.

**Correção:** explicitar a cobertura, exibir grupos sem mapeamento e a idade das coletas, escolher uma data comum ou identificar claramente a mistura de datas e definir atribuição de avanços por squad.

### 16. Migração XLSX não tem a idempotência prometida pelo esquema

`db/migrar_avancos_xlsx.py:110` usa `ON DUPLICATE KEY UPDATE` por suposto conflito de data/conta. `Avanco` não declara uma chave única para esses campos e o insert não fornece `id`. No esquema criado pelo código, cada importação pode inserir novas linhas.

**Correção:** confirmar se a regra é um total por dia/conta ou múltiplos lançamentos, criar a restrição apropriada por migração e validar reimportação no MySQL. Não foi executada importação real.

### 17. Implantação e dependências não são reproduzíveis

- Python declarado: 3.13; imagens: 3.11; ambiente local: 3.12.
- `uv.lock`, `requirements.txt` e listas de instalação nos Dockerfiles não compartilham uma única fonte de verdade. As imagens usam limites mínimos sem versões exatas.
- Flask é usado pela API, mas não está nas dependências do projeto nem em `requirements.txt`. `requests` e `openpyxl` também não estão declarados diretamente, embora sejam usados; sua disponibilidade depende de instalação externa/transitiva.
- A imagem da API não instala explicitamente `cryptography`; o impacto depende do método de autenticação/configuração do MySQL.
- A API usa `app.run()` com porta publicada em todas as interfaces. O servidor de desenvolvimento não é indicado para produção, mesmo atrás de proxy.
- O Compose de MySQL traz senhas triviais e publica 3306 em todas as interfaces; não há demonstração de que esse arquivo seja usado em produção.
- Não há migrações versionadas: `create_all()` cria tabelas, mas não entrega a evolução controlada das restrições de tabelas existentes.

**Correção:** alinhar versão de Python e dependências, construir com lock, escolher servidor WSGI e modelo de jobs compatíveis, restringir publicação de portas e criar migrações verificáveis.

## Manutenção, operação e experiência

- **Sem suíte automatizada ou CI versionada:** não foram encontrados testes de regressão e configuração de integração contínua. Os scripts com datas fixas e efeitos na importação precisam ser separados dos testes.
- **Documentação inicial insuficiente:** `README.md` raiz está vazio e a descrição do pacote é provisória. Faltam instruções locais completas, requisitos de ambiente, contratos, recuperação de falhas e restauração.
- **Custo desnecessário de credenciais:** `/api/clientes` chama `get_active_clients()`, que busca e descriptografa credenciais de todas as contas, embora devolva apenas metadados. Isso amplia acesso a segredos e latência sem necessidade para essa tela.
- **Cliente Snov.io frágil:** faltam verificações consistentes de status HTTP e formato do retorno. Tokens são guardados durante a coleta sem controle de expiração; uma falha de autenticação pode repetir o token inválido nas retentativas.
- **Fuso na coleta:** `date.today()` usa o fuso do processo, ao contrário do cálculo explícito de São Paulo na integração de avanços. Docker configura o fuso; execução fora dele pode coletar outra data.
- **Consultas crescem com o histórico:** não há índices explícitos nos filtros frequentes de `dados`, e há consultas por linha e leitura integral de listas/histórico. Medir no MySQL antes de dimensionar; não foi feito teste de carga.
- **Permissões:** um único token autoriza consulta, exclusão e disparo de jobs. Não há identificação individual nem trilha persistida de quem executou cada ação. CORS com `*` não substitui autenticação nem autorização.
- **Responsividade:** com viewport de 390 px, a tela de análise mediu 494 px de largura de documento no teste, causando rolagem horizontal da página. Há eventos em linhas/divs sem equivalência clara de teclado e modais sem gerenciamento explícito de foco, Escape e atributos de acessibilidade.
- **Concorrência no frontend:** mudanças rápidas de filtros podem renderizar respostas antigas; faltam cancelamento ou controle da versão da requisição. As ações de job têm pouca indicação de progresso e dependem dos logs em memória.

## Regras documentadas que exigem alinhamento

`docs/SPEC_INTEGRACAO_AVANCOS.md` se declara proposta ainda não aplicada, mas registra como decisão a contagem apenas do tipo `Interessado`. O código atual conta `Interessado`, `Apresentação` e `Encaminhamento`, excluindo apenas `Nutrição`; isso foi confirmado localmente.

Não se deve tratar toda a proposta como requisito já implantado. É necessário confirmar qual regra está vigente e atualizar código, interface e documentação em conjunto. A divergência atual é relevante porque altera as cores do semáforo.

## Aspectos positivos verificados

- Rotas protegidas rejeitaram token ausente/incorreto com 401 e aceitaram token correto com 200. A comparação usa `secrets.compare_digest` e token ausente no servidor não libera acesso.
- O retorno de `/api/clientes` seleciona campos não secretos para o frontend.
- Consultas usam ORM ou parâmetros SQL para os filtros de data; não foi identificada interpolação direta de entrada do usuário no SQL analisado.
- Há limites de tempo em chamadas importantes, retentativas na API de credenciais e um contorno explícito para o problema de paginação da origem.
- Conexões principais usam `pool_pre_ping` e reciclagem; várias operações delimitam sessões e transações.
- O semáforo já calcula sua janela de dias em São Paulo.
- Sintaxe válida nos 16 arquivos Python e nos scripts das três telas. Isso valida parsing, não a integridade dos fluxos.

## Ordem recomendada de correção

1. **Conter exposição:** revogar chave SendGrid, corrigir XSS e impedir inclusão de credenciais em imagens.
2. **Recuperar implantação:** corrigir ignore/importação, alinhar dependências e validar build/inicialização em ambiente limpo.
3. **Proteger dados:** impedir substituição parcial da planilha, criar restrições/migrações após examinar duplicatas e coordenar scheduler/API.
4. **Tornar a coleta verificável:** reportar falhas e resultados parciais, corrigir logs, persistir execuções e permitir reprocessamento de campanhas históricas.
5. **Alinhar indicadores:** unificar avanços, datas, dias de disparo, cobertura de squads e regra do semáforo.
6. **Consolidar operação:** testes de regressão dos cenários acima, CI, backup/restauração testados, monitoramento, acessibilidade e desempenho medido.

Critérios mínimos de aceite: imagem inicia de clone limpo; credenciais ficam fora das imagens; nomes de clientes não executam código; coleta com falhas não aparece como sucesso total; seleção preserva demais campanhas; reexecução não duplica métricas; avanço cadastrado aparece na fonte e nos indicadores corretos; filtros e dias batem com dados conhecidos; logs continuam após a rotação; indisponibilidade externa aparece explicitamente.

## Referências técnicas

- [Docker: contexto de build e arquivos ignorados](https://docs.docker.com/build/concepts/context/).
- [Flask: implantação em produção](https://flask.palletsprojects.com/en/stable/deploying/index.html).

As conclusões funcionais e de segurança deste documento se baseiam no código local e nas reproduções descritas, não em uma inspeção de produção.
