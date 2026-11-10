# Painel de Campanhas × Sistema de Avanços — documentação e plano de integração

Data da análise: 2026-10-23.

Este documento descreve os dois sistemas, compara como cada um registra um avanço e lista os ajustes recomendados para que os dois conversem com o mesmo padrão. Os números citados vieram de consultas reais feitas na API do sistema de avanços nesta data.

## 1. Os dois sistemas em resumo

| | Painel de Campanhas (este repo) | Sistema de Avanços |
|---|---|---|
| Pasta | `Ativa---Controle-de-Campanhas` | `Relatorios/avanços` |
| Para que serve | Acompanhar o disparo diário de e-mails por cliente (dados do Snov.io) e o semáforo de avanço | Registrar, tratar e reportar avanços comerciais (leads que avançaram), follow-up de SDR, gráficos, relatório PPTX |
| Backend | Python, Flask (`painel-api/server.py`), SQLAlchemy | NestJS, TypeORM (`avancos-backend`) |
| Frontend | HTML estático (`painel-frontend/*.html`) | Vue 3 + Vite (`avancos-frontend`) |
| Banco | MySQL `dadoscampanha` (host 207.244.249.157) | MySQL `avancos_comerciais` (mesmo host) |
| Autenticação da API | Header `X-API-Token` (`PAINEL_TOKEN`) | Nenhuma |
| Identifica o cliente por | Conta Snov.io (e-mail `@ativa.ai`) | Nome do cliente em texto livre |
| Portas | API 8000 | API 3098 (backend), 3099 (frontend via nginx) |

## 2. Painel de Campanhas

### 2.1 Fluxo de dados

1. O scheduler (`main.py`, `rotina/acao.py`) lê as contas ativas do sistema de credenciais (`snov-am-api`, via `rotina/credentials_api.py`) e puxa as métricas de campanha do Snov.io.
2. Grava em `dadoscampanha.dados`: uma linha por campanha, conta e dia, com contatados, enviados, entregues, aberturas, cliques e respostas.
3. `dadoscampanha.campanhas` guarda o cache das campanhas de cada conta.
4. O painel cruza `dados` com `relatoriolistas.listas_squad` (banco de outro sistema, acesso só de leitura) para separar por squad: Onboarding, SDR Remoto e Geral.

### 2.2 Telas

- `index.html`: configuração da conexão (URL da API e token) e disparo manual das rotinas.
- `dados.html`: números por squad. Desde esta data, agrupado por cliente.
- `analise.html`: análise por cliente, com visão resumida (cliente, enviados, avanços, status), visão detalhada e tela de um cliente com gráficos diários.

### 2.3 Endpoints principais (`painel-api/server.py`)

| Rota | Função |
|---|---|
| `GET /api/squads` | Campanhas do último dia coletado por squad, com `cliente` e `avancosHoje` |
| `GET /api/analise-contas?inicio&fim` | Resumo por cliente por squad no período, com avanços e semáforo |
| `GET /api/analise-cliente?cliente&inicio&fim` | Série diária de um cliente, com avanços por dia e `statusAvanco` |
| `GET/POST/DELETE /api/avancos` | **Registro manual local** (ver 2.4) |
| `POST /api/run/*` | Disparo manual das rotinas de extração |

### 2.4 Como o painel registra um avanço hoje

- Modal "Registrar avanço" em `dados.html` com três campos: data, conta (e-mail Snov.io) e quantidade.
- `POST /api/avancos` grava na tabela `dadoscampanha.avancos` (`data`, `conta`, `quantidade`, `criado_em`).
- É um contador manual por dia e por conta. Não identifica lead, tipo, responsável nem campanha.
- Essa tabela **não é mais usada** para os números exibidos: após a integração, o painel lê os avanços do sistema de avanços. O modal e a tabela viraram uma segunda fonte de verdade que ninguém consome.

## 3. Sistema de Avanços

### 3.1 Módulos do backend (`avancos-backend/src`)

- `avancos`: CRUD de avanços, filtros, estatísticas, exportação, contagem de follow-ups, dados para PPTX.
- `credenciais`: tabela `credenciais_clientes` (cliente, e-mail do cliente, `client_id`/`client_secret` do Snov.io, `snov_email`, `snov_senha`, `ativo`).
- `import`: importação de CSV em dois passos (analisar, executar), com mapeamento de colunas salvo.
- `relatorio`: relatório com métricas do Snov.io e geração de gráficos e PPTX.

### 3.2 Modelo do avanço (tabela `avancos`)

| Campo | Tipo | Obrigatório | Observação |
|---|---|---|---|
| `cliente` | texto (200) | sim | Texto livre, com autocomplete dos nomes já usados |
| `tipo` | enum | sim | Interessado, Apresentação, Encaminhamento, Nutrição |
| `data_avanco` | data | sim | |
| `nome_lead`, `cargo`, `empresa` | texto | não | Dados do lead |
| `segmento`, `porte` | texto | não | |
| `campanha` | texto | não | Hoje usada de forma livre: muitas vezes só "Email", às vezes o nome da campanha |
| `responsavel` | texto | não | SDR responsável |
| `observacao`, `tratativa` | texto | não | |
| `data_followup` | data e hora | não | Alimenta o badge de follow-up do SDR |
| `importado_de` | texto | não | Origem do CSV |
| `criado_em`, `atualizado_em` | data e hora | automático | |

Cada linha é **um avanço de um lead**. A quantidade de avanços de um cliente é a contagem de linhas.

### 3.3 Endpoints usados na integração

| Rota | Uso |
|---|---|
| `GET /api/avancos` | Lista com filtros (`cliente` é busca parcial, `dataInicio`, `dataFim`, `tipo`, `page`, `limit`). **O limite máximo é 200 por página** |
| `GET /api/avancos/opcoes` | Valores distintos por campo, incluindo `clientes` com total de avanços de cada nome |
| `GET /api/avancos/estatisticas` | Totais por tipo, segmento etc. |
| `GET /api/credenciais` | Lista segura: cliente, `emailClient`, `clientId`, `snovEmail`, `ativo` |
| `POST /api/avancos` | Cria um avanço (DTO com `cliente`, `tipo` e `dataAvanco` obrigatórios) |

## 4. Comparação do registro de avanço

| Aspecto | Painel (manual) | Sistema de Avanços | Consequência |
|---|---|---|---|
| Granularidade | Quantidade por dia e conta | Uma linha por lead | Painel perde o detalhe e não consegue auditar o número |
| Identificação do cliente | E-mail da conta Snov.io digitado à mão | Nome em texto livre | Os dois não se encontram sem tradução |
| Tipo do avanço | Não existe | Obrigatório (4 valores) | Painel não distingue Interessado de Nutrição |
| Lead, empresa, cargo | Não existe | Existe | |
| Responsável / SDR | Não existe | Existe, com follow-up | |
| Campanha | Não existe | Livre | |
| Validação do cliente | Nenhuma | Nenhuma (autocomplete sugere, não obriga) | Qualquer um dos dois aceita nome ou conta inexistente |
| Edição | Só excluir | Editar e excluir | |
| Autenticação | Token | Nenhuma | Ver 5.4 |

Resumo: o registro do painel é um subconjunto pobre do registro do sistema de avanços, e hoje não alimenta mais nada. Manter os dois formulários cria duas fontes de verdade e números divergentes.

## 5. Estado atual da integração e problemas encontrados

### 5.1 O que já foi implementado (painel lê do sistema de avanços)

- `db/avancos_api.py` busca avanços e credenciais por HTTP (`AVANCOS_API_URL`, padrão `http://207.244.249.157:3098/api`). Cache de 60 segundos.
- O painel liga cliente a conta usando `credenciais_clientes` (`cliente` ↔ `snovEmail`).
- Semáforo por cliente: ontem, anteontem e 3 dias atrás (o dia atual não conta). 2 ou mais avanços: verde. 1: amarelo. 0: vermelho.
- Aba Dados e Análise agrupam por cliente, somando as contas e campanhas do cliente.

### 5.2 O nome do cliente não é um identificador

O campo `cliente` do avanço é texto livre. Medição em 2026-10-23, em 2.078 nomes distintos e 41.222 avanços:

- 302 nomes batem exatamente com um cliente cadastrado nas credenciais.
- 777 nomes só batem depois de normalizar (acento, maiúsculas, sufixo de campanha). Exemplos: "Sindmóveis [Geral]", "Made Logística - Reativação", "Link Mochilas [Automotivo]".
- 999 nomes **não batem com nenhuma credencial**, somando 20.455 avanços, quase metade do total. Exemplos: "Brainlaw:" (333), "Tech CD" (328), "Rubrum" (286), "Evoque" (263), "Krav" (231).

Parte desses é de clientes que realmente não têm conta cadastrada nas credenciais, parte é grafia diferente. Para esses clientes o painel mostra 0 avanço e semáforo vermelho, mesmo que existam avanços. Hoje a normalização do painel (`resolve_cliente`) cobre os casos conhecidos e tem 2 aliases fixos no código (`linkmochilas`, `madelogstica`), o que não escala.

Há também nomes com **encoding quebrado** na base ("Made Log�­stica"), o que indica importação de CSV em charset errado.

Além disso, o nome do cliente muitas vezes carrega a campanha ("Sindmóveis [Varejo]"), misturando dois conceitos que já têm campo próprio (`cliente` e `campanha`).

### 5.3 Três cadastros diferentes da mesma entidade "cliente/conta"

| Cadastro | Onde | Chave |
|---|---|---|
| Contas do Snov.io | `snov-am-api` (FastAPI + Postgres), lido pelo scheduler do painel | e-mail da conta |
| `credenciais_clientes` | Banco do sistema de avanços | `cliente` + `snov_email` |
| Squads | `relatoriolistas.listas_squad` (sistema de listas) | `campanha_id` |

Não existe vínculo formal entre eles. Exemplos reais do efeito: Sindmóveis tem 379 linhas de dados de campanha (até 2026-10-12) e avanços, mas não aparece no painel porque nenhuma campanha dele está em `listas_squad`; "Link Mochilas" não tem credencial e compartilha a conta `linkpromocional2@ativa.ai` com "Link Promocional".

### 5.4 Segurança

A API do sistema de avanços está exposta em IP público (porta 3098), **sem autenticação**, com CORS aberto (`origin: '*'`). `GET /api/credenciais?completo=true` retorna credenciais visíveis, incluindo senhas do Snov.io, segundo o código do controller (`findAllCompleto`), e `GET /api/credenciais/buscar?cliente=` inclui `clientSecret` e `snovSenha`. Isso deve ser tratado como prioridade, independente da integração. Não executei essas duas rotas.

### 5.5 Outros pontos técnicos

- **Desempenho:** a API só pagina de 200 em 200 e não tem um endpoint de resumo. O histórico completo tem cerca de 200 páginas por 41 mil avanços; a visão "Geral" só funciona rápido porque usa o total por nome do `opcoes`.
- **Fuso horário:** o painel calcula "ontem" com a data do servidor; `data_avanco` é só data. Se o servidor rodar em UTC, a janela de 3 dias vira na hora errada para o Brasil.
- **Tipos de avanço:** o semáforo conta todos os tipos igualmente, inclusive Nutrição. Falta decidir se Nutrição deve contar.
- **Falha de disponibilidade:** se a API de avanços cair, o painel responde erro em vez de mostrar o último valor conhecido.

## 6. Ajustes recomendados

Ordem sugerida, do que mais reduz risco ao que mais melhora o padrão.

### 6.1 Urgente

1. **Proteger a API de avanços** (chave de API ou rede interna) e remover senhas e segredos do retorno de `GET /api/credenciais` e `buscar`. O painel passa a enviar a chave por header, como já faz o resto do ecossistema (`X-API-Key`).

### 6.2 Um único registro de avanço

2. **Aposentar o registro manual do painel.** Remover o modal "Registrar avanço", as rotas `POST/DELETE/GET /api/avancos` e deixar a tabela `dadoscampanha.avancos` só como histórico migrado. O botão passa a abrir o formulário do sistema de avanços.
3. **Se for necessário registrar pelo painel**, usar exatamente o mesmo formulário e o mesmo DTO (`cliente`, `tipo`, `dataAvanco` obrigatórios; lead, empresa, cargo, segmento, porte, campanha, responsável, observação, follow-up opcionais), enviando para `POST /api/avancos` do sistema de avanços por meio do `painel-api` (o token fica no servidor). Nada é gravado localmente.

### 6.3 Identificador de cliente confiável (resolve a maior parte das divergências)

4. **No formulário do sistema de avanços, trocar o campo livre por seleção obrigatória** dos clientes de `credenciais_clientes`. O nome da campanha vai no campo `campanha`, nunca no `cliente`.
5. **Guardar a conta no avanço:** adicionar a coluna `snov_email` (ou `credencial_id`) em `avancos`, preenchida pelo formulário a partir do cliente escolhido. O painel passa a casar por conta, sem depender de nome.
6. **Backfill:** rodar a normalização do painel (`resolve_cliente`) sobre os 41 mil avanços para preencher `snov_email` onde há match. Gerar uma lista dos 999 nomes sem match para a equipe decidir caso a caso: cadastrar credencial, corrigir a grafia ou aceitar como cliente sem conta Snov.io.
7. **Corrigir o encoding** dos nomes quebrados na base e na importação de CSV (forçar UTF-8 no `import.service`).

### 6.4 Endpoints que simplificam a leitura do painel

8. No sistema de avanços, criar `GET /api/avancos/resumo?dataInicio&dataFim&agrupar=cliente,dia` retornando `{cliente|snovEmail, data, total, por_tipo}`. O painel deixa de baixar página por página e de normalizar nomes.
9. Publicar a regra do semáforo em um único lugar. Hoje ela existe só no painel; se o sistema de avanços passar a exibir o status, os dois precisam concordar. Sugestão: `GET /api/avancos/status?dias=3&excluirHoje=true`.

### 6.5 Cadastros e squad

10. Escolher **uma fonte** para a lista de clientes ativos (sugestão: o `snov-am-api`, que já alimenta a extração) e sincronizar `credenciais_clientes` a partir dela, em vez de manter cadastro duplo.
11. Incluir o squad no cadastro de cliente e deixar de depender de `listas_squad` para decidir onde o cliente aparece. Enquanto isso não existir, clientes como Sindmóveis continuam fora do painel.

### 6.6 Robustez do painel

12. Calcular a janela de 3 dias no fuso `America/Sao_Paulo`.
13. Se a API de avanços falhar, mostrar o último valor em cache com aviso, em vez de erro.
14. Mover os dois aliases fixos de `avancos_api.py` para uma tabela de aliases cliente → conta (item 6 elimina a necessidade).

## 7. Decisões que dependem de vocês

- Nutrição conta para o semáforo? E Apresentação, Encaminhamento e Interessado, todos com o mesmo peso?
- O registro de avanço fica só no sistema de avanços (recomendado) ou o painel também precisa registrar?
- Cliente sem conta Snov.io (sem disparo) deve aparecer no painel? Hoje não aparece, e só entra se houver dados de campanha.
- Quem corrige os 999 nomes sem match, e em qual prazo.
- O painel será publicado no VPS? Nesse caso `AVANCOS_API_URL` e a chave do item 1 precisam estar no ambiente dele.
