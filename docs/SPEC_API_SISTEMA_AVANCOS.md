# Especificação: API de avanços para o Painel de Campanhas

Status: proposta técnica baseada na inspeção local do sistema de avanços em `C:\Users\HP\relatorios\avanços`. Nenhum endpoint foi criado ou alterado por esta especificação.

## Objetivo

Permitir que o Painel de Campanhas consulte avanços comerciais por cliente e período, calcule o semáforo de forma igual nos dois sistemas e abra o sistema de avanços para o trabalho operacional. O painel é consumidor somente de leitura: registros continuam sendo criados e corrigidos no sistema de avanços.

O relatório Snov.io de 2026 é uma integração separada. Ele usa `CREDENTIALS_API_URL` e `CREDENTIALS_API_KEY` para buscar contas/credenciais e grava métricas em `dadoscampanha`. A API descrita aqui fornece os avanços usados no semáforo e nas métricas de avanço; ela não substitui a API de credenciais nem o acesso Snov.io.

## O que existe hoje

Inspecionados `avancos-backend/src/main.ts`, `src/app.module.ts`, `src/avancos/avancos.controller.ts`, `src/avancos/avancos.service.ts`, entidades e DTOs.

| Recurso atual | Uso possível | Limite para o painel |
|---|---|---|
| `GET /api/avancos` | Consulta registros com filtros, paginação e datas | Páginas não são um contrato eficiente para série diária e exigem baixar registros detalhados |
| `GET /api/avancos/estatisticas` | Contagem por tipo, segmento, cargo, mês e ano; aceita cliente(s), tipo e intervalo | Não devolve agrupamento por cliente e dia; a rota aceita até 100 clientes |
| `GET /api/avancos/opcoes` | Opções para filtros | Não é cadastro canônico de contas Snov |
| `GET /api/avancos/pptx` | Agregação por tipo para um cliente aproximado e intervalo | Usa `LIKE '%cliente%'`, que pode misturar nomes e não é adequado como chave do painel |
| `GET /api/credenciais` | Campos considerados seguros pela implementação: cliente, emailClient, clientId, snovEmail e ativo | `clientId` continua sendo dado sensível operacional; o endpoint completo também retorna `clientSecret` e senhas |

O `main.ts` atual habilita CORS com `origin: '*'`. Não foi encontrado guard de autenticação global nem por rota. Portanto, a API atual não deve ser exposta ao painel pela internet antes de autenticação, HTTPS e restrição de CORS. O endpoint `/api/credenciais?completo=true`, `/api/credenciais/buscar` e `/api/credenciais/:id` precisam ser tratados como rotas de alto risco porque podem retornar segredos.

## Contrato proposto

Base: `AVANCOS_API_URL=https://<host>`; autenticação exclusiva de serviço por `X-API-Key: <chave>` (ou nome de header configurável). A chave deve ser dedicada ao painel, armazenada em segredo de ambiente e comparada em tempo constante. Rotas de escrita e de credenciais não são autorizadas por essa chave.

### `GET /api/integracoes/painel/v1/resumo`

Parâmetros obrigatórios: `dataInicio=YYYY-MM-DD`, `dataFim=YYYY-MM-DD`. Intervalo inclusivo; limitar a 366 dias por requisição. `cliente` pode ser repetido para filtrar exatos (`?cliente=A&cliente=B`); sem filtro, devolver todos os clientes. `cursor` opcional para paginação estável quando o conjunto ultrapassar o limite.

Resposta:

```json
{
  "dataInicio": "2026-01-01",
  "dataFim": "2026-12-31",
  "geradoEm": "2026-11-10T12:00:00Z",
  "proximaPagina": null,
  "dias": [
    {"cliente": "Cliente exemplo", "data": "2026-01-02", "total": 3,
     "porTipo": {"Interessado": 1, "Apresentação": 1, "Encaminhamento": 1, "Nutrição": 0}}
  ]
}
```

Semântica: `cliente` tem correspondência exata conforme o valor cadastrado no sistema de avanços; `total` e `porTipo` contam registros por `data_avanco`; omitir combinações sem registros; `total` é sempre igual à soma de `porTipo`. Não retornar lead, observação, responsável, follow-up ou outros dados pessoais. Ordenar por `data`, depois `cliente`, com cursor estável. Valores numéricos são inteiros não negativos.

### `GET /api/integracoes/painel/v1/status`

Query: `dias=3` (permitir 1–30), `excluirHoje=true` como padrão. Calcular datas segundo `America/Sao_Paulo`. Contar somente `tipo=Interessado`. Para cada cliente, somar os dias fechados anteriores; `verde` para 2 ou mais, `amarelo` para 1, `vermelho` para 0. Clientes sem vínculo com uma conta Snov recebem `sem_vinculo`; falha de consulta nunca deve ser convertida em vermelho/zero. Retornar `geradoEm`, `inicio`, `fim` e registros `{cliente, interessados, status}`. Se o mesmo cliente representar mais de uma conta, o resumo do cliente soma as contas uma vez; a resposta não duplica total por squad.

### `GET /api/integracoes/painel/v1/health`

Autenticado. Retorna apenas `{status:"ok", versao, geradoEm}` e não expõe configuração, SQL, host do banco ou segredos. A prontidão de banco pode ser `503` sem detalhes internos.

## Segurança e operação

- Exigir HTTPS no endpoint público; permitir HTTP somente em rede Docker privada entre serviços.
- Criar chave de serviço separada, rotacionável, com escopo somente leitura e somente para essas três rotas. Responder `401` para chave ausente/inválida e `403` para escopo insuficiente.
- Remover `origin: '*'`; permitir apenas origens web necessárias. CORS não substitui autenticação.
- Não colocar chave em query string, navegador, logs, mensagens de erro ou URL. O painel chama a API pelo backend Python, nunca pelo Vue.
- Limitar requisições e payloads; validar datas reais e intervalo; suportar `429` com `Retry-After`; respostas de erro sem stack trace.
- Definir timeout de conexão/leitura, retentativas limitadas para `429`/`5xx`, cache curto (60s) e fallback para cache expirado com aviso visível. Erro sem cache deve aparecer como indisponibilidade, jamais como `0`.
- Não alterar o CRUD do sistema de avanços nem a importação. A chave do painel não pode criar, alterar, excluir avanços, acessar credenciais ou emitir token Snov.

## Compatibilidade e estratégia

1. Implementar os dois endpoints de resumo/status no NestJS, reutilizando a entidade `Avanco` e SQL parametrizado no MySQL.
2. Adicionar autenticação dedicada de serviço e testes negativos de acesso, mantendo o uso atual da interface web após definir a autenticação humana apropriada.
3. Testar agregações com cliente exato, cliente sem registros, cada tipo de avanço, limites de data, ano bissexto, timezone São Paulo, múltiplas contas, cliente com nomes semelhantes, paginação, chave ausente e indisponibilidade.
4. No painel, adaptar `db/avancos_api.py` para os endpoints novos, validar schema da resposta, cachear e preservar `null` em indisponibilidade.
5. Executar carga histórica de métricas Snov de 2026 separadamente por fila de jobs e persistir cada dia/campanha concluído no MySQL `dadoscampanha`; registrar progresso e falhas, com retomada idempotente. Não publicar planilhas durante o backfill salvo configuração explícita.

## Critérios de aceite

- Uma chamada do painel para o ano selecionado retorna resumo diário de todos os clientes sem expor campos pessoais.
- Totais por dia/tipo conferem com uma consulta de referência no banco; intervalos são inclusivos e estáveis em `America/Sao_Paulo`.
- O semáforo nas telas do painel e do sistema de avanços usa a mesma definição, datas e tipos; cliente multi-squad não duplica avanços.
- Chave inválida não lê dados; chave válida não acessa CRUD nem credenciais; ausência do serviço não é exibida como zero/vermelho.
- Backfill retomável não duplica `(id_conta, data)`, preserva coletas já existentes e expõe por job datas concluídas/pendentes e erros por conta/campanha sem segredo.

## Fora do escopo desta API

As seis métricas Snov (`total_contacted`, `emails_sent`, `delivered`, `email_opens`, `link_clicks`, `email_replies`) são buscadas diretamente pelo coletor do painel via Snov.io, usando credenciais obtidas pela API de credenciais. Esta API de avanços fornece contagens comerciais e status. Também não deve ser criada cópia de banco, escrita de avanços pelo painel, sincronização de segredos nem um agrupamento "Multissquad".
