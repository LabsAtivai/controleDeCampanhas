# Spec — Integração Painel de Campanhas × Sistema de Avanços × Sistema de Credenciais

Status: **proposta para aprovação. Nada deste spec foi aplicado nos dados nem nos sistemas.**
Data: 2026-10-23. Complementa `docs/INTEGRACAO_AVANCOS.md` (diagnóstico dos dois sistemas).

## 1. Decisões já tomadas

1. **Semáforo conta somente avanço do tipo `Interessado`**, nos dois sistemas (painel e sistema de avanços).
2. **O sistema de avanços passa a usar o sistema de credenciais** (`snov-am-api`) como cadastro de contas. A tabela `credenciais_clientes` do sistema de avanços deixa de ser fonte de verdade.
3. **Todo avanço cujo `cliente` é um nome passa a apontar para o e-mail da conta no sistema de credenciais.**
4. **Antes de marcar um avanço como `SEM SNOVIO`, o sistema tenta identificar a conta no sistema de credenciais por todas as regras da seção 4.4.** Só o que continuar sem conta depois disso aparece como `SEM SNOVIO`, e continua sendo contado.
5. **As contas chegam ao sistema de avanços automaticamente a partir do sistema de credenciais.** Ninguém recadastra cliente nem credencial no sistema de avanços (seção 3.2).
6. **Antes de qualquer correção, o resultado é mostrado e aprovado** (seção 5 e arquivo CSV de prévia).

Interpretação adotada no item 4: avanço sem conta não deve sumir nem ser forçado em conta errada; depois de esgotadas as tentativas de identificação, aparece rotulado `SEM SNOVIO`.

## 2. Estado atual e alvo

```
HOJE
 snov-am-api (contas)          credenciais_clientes (avanços)        listas_squad
        |                                |                                |
   scheduler painel                 sistema de avanços              painel (squad)
        |                                |                                |
   dadoscampanha.dados  <--- liga por nome/normalização --->  avancos.cliente (texto livre)

ALVO
                    snov-am-api  (única fonte de contas)
                     /                     \
        scheduler do painel         sistema de avanços (consulta contas, grava avanço com conta)
                     \                     /
        painel lê avanços por conta (snov_email), sem normalizar nome
```

## 3. Mudanças por sistema

### 3.1 Sistema de credenciais (`snov-am-api`)

- Criar uma API key dedicada ao sistema de avanços com escopo `accounts:read` (e `credentials:read` só se o módulo de relatório continuar buscando métricas do Snov.io).
- Confirmar qual campo guarda o nome do cliente (provavelmente `description`). Hoje o painel espelha `email` (e-mail do cliente, `*.ativa@gmail.com`), `snov_email` (login Snov.io, `*@ativa.ai`) e `status`. **A chave canônica proposta é `snov_email`**, porque é o valor gravado em `dadoscampanha.dados.conta`. O `id` da conta fica guardado junto para sobreviver a troca de e-mail.
- Opcional: campo `squad` na conta (seção 3.4).

### 3.2 Sistema de avanços

**Banco (`avancos`)**

| Mudança | Detalhe |
|---|---|
| Nova coluna `snov_email` (varchar 200, indexada) | Conta do avanço. Valor real do sistema de credenciais, ou `SEM SNOVIO` |
| Nova coluna `conta_id` (varchar 36, nula) | `id` da conta no sistema de credenciais, para auditoria |
| `cliente` | Continua existindo como texto de exibição, preenchido automaticamente a partir da conta. Deixa de ser digitado |
| `campanha` | Fica só com o nome da campanha. Sufixos como "[Geral]" saem do `cliente` |

**Backend**

- **Sincronização automática das contas.** Um job do sistema de avanços (a cada 15 minutos e ao iniciar) lê o `snov-am-api` e mantém uma tabela local `contas_credenciais` (id da conta, `email`, `snov_email`, nome do cliente, status, `squad` quando existir). É só leitura e só cache: ninguém edita essa tabela nem recadastra cliente no sistema de avanços. Conta nova no sistema de credenciais aparece no formulário de avanços no próximo ciclo; conta desativada fica na tabela com o status, para o histórico continuar ligado.
- Só dados não secretos são sincronizados (sem `snov_id`, `snov_secret` nem senha). O módulo de relatório, que precisa do `snov_id`/`snov_secret` para buscar métricas no Snov.io, passa a buscá-los no `snov-am-api` no momento do uso (`credentials:read`), em vez de guardar cópia.
- A tela de cadastro de credenciais do sistema de avanços (`CredenciaisView`) e a tabela `credenciais_clientes` são removidas ao fim da migração. O cadastro passa a ser feito só no sistema de credenciais.
- Atenção: a listagem `GET /api/accounts` do `snov-am-api` perde contas na paginação quando há empate em `created_at` (nesta análise voltaram 466 de 547). O job de sincronização precisa do mesmo contorno de `rotina/credentials_api.py` (varrer com tamanhos de página diferentes) ou, melhor, o `snov-am-api` deve ganhar ordenação estável por `id`. A API também limita requisições (429) e derruba conexão em rajadas: o job deve ter retentativa.
- `POST/PUT /api/avancos`: `snovEmail` obrigatório. Valida que existe no sistema de credenciais, ou aceita o valor literal `SEM SNOVIO`.
- `GET /api/avancos`: novo filtro `snovEmail`, e o retorno inclui `snovEmail`.
- Novo `GET /api/avancos/resumo?dataInicio&dataFim` agrupado por `snovEmail` e dia, com contagem total e por tipo. Evita baixar o histórico página a página.
- Novo `GET /api/avancos/status?dias=3&excluirHoje=true` devolvendo o semáforo por `snovEmail` (regra da seção 4.1). **O painel e a tela do sistema de avanços usam este endpoint**, para as duas telas nunca divergirem.
- Autenticação por chave de API em todas as rotas e remoção de segredos/senhas do retorno de `credenciais` (hoje a API é pública e sem autenticação).

**Frontend (Vue)**

- Campo "Cliente" do modal vira seleção obrigatória das contas do sistema de credenciais (busca por nome ou e-mail), mais a opção `SEM SNOVIO`.
- Importação de CSV: coluna de cliente é resolvida para conta com o mesmo algoritmo da migração; linhas sem match entram como `SEM SNOVIO`. Forçar UTF-8 para acabar com nomes quebrados.
- Badge de semáforo por conta na listagem, usando `/status`.

### 3.3 Painel de Campanhas

- Passa a chamar `/api/avancos/resumo` e `/api/avancos/status`. Remove `resolve_cliente`, os aliases fixos e a normalização por nome de `db/avancos_api.py`.
- Remove o modal "Registrar avanço", as rotas `GET/POST/DELETE /api/avancos` e deixa `dadoscampanha.avancos` como histórico congelado.
- Botão "Registrar avanço" abre o sistema de avanços já com a conta pré-selecionada.
- Linha **SEM SNOVIO** nas telas de análise: um grupo à parte no fim da lista, com a soma dos avanços sem conta e o semáforo oculto (não há disparo para comparar). Clique abre a lista desses avanços para correção.
- Janela de dias calculada em `America/Sao_Paulo`.
- Se a API de avanços cair: mostrar o último valor em cache com aviso, em vez de erro.

### 3.4 Squad

`listas_squad` só cobre campanhas já mapeadas, e por isso clientes como Sindmóveis ficam fora do painel. Proposta: guardar o squad na conta (sistema de credenciais) e o painel usar esse campo, com `listas_squad` só como fallback enquanto a migração não termina. Depende de decisão (seção 7).

## 4. Regras

### 4.1 Semáforo

Janela: os 3 dias fechados anteriores a hoje (ontem, anteontem e 3 dias atrás). Hoje não conta. Conta apenas `tipo = 'Interessado'`.

| Interessados na janela | Cor |
|---|---|
| 2 ou mais | Verde |
| 1 | Amarelo |
| 0 | Vermelho |

Aplicada por conta (`snov_email`). Quando a tela agrupa por cliente com várias contas, soma os Interessados das contas do cliente antes de classificar.

**Efeito medido com os dados de 2026-10-20 a 2026-10-22** (111 avanços na janela: 38 Interessado, 58 Encaminhamento, 15 Apresentação):

| | Verde | Amarelo | Vermelho |
|---|---|---|---|
| Regra de hoje (todos os tipos), entre os 60 clientes com algum avanço | 31 | 29 | 0 |
| Nova regra (só Interessado), mesmos 60 clientes | 7 | 20 | 33 |

Ou seja, 43 dos 60 clientes mudam de cor, e o número de verdes cai de 31 para 7. Isso é esperado pela regra, mas muda bastante o que a equipe vai ver no primeiro dia.

### 4.2 Vínculo avanço → conta

- Todo avanço novo grava `snov_email` escolhido na tela. Sem match, grava `SEM SNOVIO`.
- Cliente com várias contas (ex.: Tonica = tonica2 e tonica3): o formulário pede **qual conta**. Na migração, avanços desses clientes ficam como "escolher conta" até alguém decidir (seção 5).

### 4.3 SEM SNOVIO

- Só recebe esse valor o avanço que **esgotou todas as regras de identificação da seção 4.4**.
- Valor literal e fixo em `snov_email`. Nunca nulo, para os filtros e relatórios funcionarem.
- Entra nos totais gerais de avanços, mas **não entra no semáforo** nem em ranking por conta.
- Não é definitivo: **a cada sincronização de contas, os avanços `SEM SNOVIO` são reavaliados** com as regras da seção 4.4. Cliente que ganhar conta no sistema de credenciais passa a ter os avanços antigos ligados a ela automaticamente (casos de alta confiança) ou entra na fila de revisão. Também dá para corrigir manualmente.

### 4.4 Como o sistema tenta identificar a conta

Ordem de tentativa, parando na primeira que achar. O nome do avanço é comparado sem acento, sem maiúsculas e sem pontuação, primeiro inteiro e depois sem o sufixo de campanha ("[Geral]", "- Reativação").

| # | Regra | Resultado |
|---|---|---|
| 1 | Nome igual à descrição (nome do cliente) da conta no sistema de credenciais | OK, ligação automática |
| 2 | Nome igual ao e-mail da conta (parte antes do `@`), do e-mail do cliente ou do `snov_email` | OK |
| 3 | Mesmas comparações ignorando número final (`tonica` → `tonica2`, `tonica3`) | OK se for uma conta só. Se forem várias, ESCOLHER CONTA |
| 4 | Ligação curada que já existia em `credenciais_clientes` (cliente → `snov_email`), usada uma única vez na migração | OK |
| 5 | Nome é prefixo do nome da conta, ou o nome do avanço começa com o nome da conta | REVISAR (humano confirma) |
| 6 | Nome parecido (similaridade de pelo menos 0,86) | REVISAR |
| 7 | Nome aparece em campanha de alguma conta em `dadoscampanha.dados` (ex.: "ARV" em campanhas de `arvsystems` e `arvis`) | REVISAR |
| 8 | Nenhuma das anteriores | `SEM SNOVIO` |

Só as regras 1 a 4 gravam sozinhas. As regras 5 a 7 são sugestões: a equipe aprova em lote numa tela de revisão, e a aprovação fica registrada para virar regra (alias) quando o mesmo nome se repetir.

## 5. Prévia do resultado (nada foi alterado)

Arquivo completo para revisão: **`docs/preview_mapeamento_avancos.csv`** (uma linha por nome distinto de cliente, com quantidade de avanços, conta proposta, como casou e situação).

A prévia usa a listagem do `snov-am-api` (descrições das contas) completada pelo espelho `contas_snovio` do painel (545 contas, sincronizado em 2026-10-23 04:15), porque a listagem do `snov-am-api` voltou só 466 das 547 contas por causa do problema de paginação descrito na seção 3.2.

Resumo sobre 2.078 nomes distintos e 41.223 avanços, aplicando as regras 1 a 7 da seção 4.4:

| Situação | Nomes | Avanços | O que acontece |
|---|---|---|---|
| OK (regras 1 a 4) | 504 | 14.338 | Recebe a conta automaticamente |
| REVISAR (regras 5 a 7) | 648 | 6.563 | Há sugestão de conta; a equipe confirma |
| ESCOLHER CONTA (cliente com várias contas) | 68 | 1.095 | Alguém escolhe a conta |
| SEM SNOVIO | 858 | 19.227 (47%) | Nenhuma regra achou conta |

Exemplos reais:

| Nome hoje no sistema de avanços | Avanços | Conta proposta | Situação |
|---|---|---|---|
| AKSUM | 532 | `aksum@ativa.ai` | OK |
| Pé de feijão | 397 | `pedefeijao3@ativa.ai` | OK |
| Sindmóveis [Geral] | 9 | `sindmoveis@ativa.ai` | OK |
| Krav | 231 | `kravconsultoria@ativa.ai` | REVISAR (prefixo) |
| Disrupt | 60 | `disrupt-ct@ativa.ai` | REVISAR (prefixo) |
| Actionpay | 181 | `actionresult@ativa.ai` | REVISAR; a sugestão provavelmente está errada, o que mostra por que as regras 5 a 7 não gravam sozinhas |
| Tonica | 181 | `tonica2@ativa.ai` ou `tonica3@ativa.ai` | ESCOLHER CONTA |
| Coopercarga | 187 | `coopercarga@ativa.ai` ou `coopercarga2@ativa.ai` | ESCOLHER CONTA |
| Brainlaw: | 333 | SEM SNOVIO | Sem conta nem campanha com esse nome |
| Tech CD | 328 | SEM SNOVIO | Sem conta nem campanha com esse nome |

Pontos que a prévia deixa claros:

- **47% dos avanços (19.227 de 41.223) continuam SEM SNOVIO** mesmo depois de todas as tentativas. Conferi os maiores nomes (Brainlaw, Tech CD, Evoque, Demandy Gifts, KN Waagen, Technotrans, Troca, Costodio, Novos Titans, CCBC, Handit) no sistema de credenciais e nas campanhas de `dados`: não há conta nem campanha com esse nome. São clientes que, até agora, não têm conta Snov.io cadastrada, então o rótulo SEM SNOVIO é o correto para eles.
- Se um desses clientes ganhar conta, a reavaliação automática da seção 4.3 liga os avanços antigos sem retrabalho.
- As regras 5 a 7 sugerem, mas não gravam: a sugestão para "Actionpay" (`actionresult`) mostra o risco de gravar sozinho.
- O `email` da conta no sistema de credenciais é, na maioria, um Gmail (`aksum.fernando@gmail.com`), enquanto `dados.conta` e o painel usam o `snov_email` (`aksum@ativa.ai`). O CSV mostra os dois.

## 6. Plano de execução

| Fase | Entrega | Reversível | Depende de |
|---|---|---|---|
| 0 | Fechar as decisões da seção 7 e revisar o CSV de prévia | — | Equipe |
| 1 | Proteger a API de avanços (chave de API, retirar segredos do retorno) | Sim | — |
| 2 | Criar API key do `snov-am-api` para o sistema de avanços e implementar o job de sincronização automática de contas (tabela `contas_credenciais`, retentativa e contorno da paginação) | Sim | Fase 1 |
| 3 | Migration `snov_email` e `conta_id` em `avancos` (colunas novas, sem apagar nada) e backup da tabela | Sim (backup) | Fase 0 |
| 4 | Backfill: gravar `snov_email` nos casos OK e `SEM SNOVIO` nos demais; REVISAR e ESCOLHER CONTA ficam pendentes. Registrar em tabela de log cada alteração (id, valor anterior, valor novo) | Sim (log) | Fases 2 e 3 |
| 5 | Endpoints `/resumo` e `/status` no sistema de avanços, com a regra "só Interessado" | Sim | Fase 3 |
| 6 | Formulário e importação do sistema de avanços com seleção obrigatória de conta e opção SEM SNOVIO | Sim | Fases 2 e 3 |
| 7 | Painel passa a consumir `/resumo` e `/status`, mostra o grupo SEM SNOVIO e remove o registro manual e a normalização por nome | Sim | Fases 4 e 5 |
| 8 | Revisão guiada dos pendentes (REVISAR e ESCOLHER CONTA) pela equipe, em tela do sistema de avanços. Reavaliação automática periódica dos SEM SNOVIO (seção 4.3) | — | Fase 6 |
| 9 | Limpeza: remover `credenciais_clientes`, rota e tabela antigas do painel | Não | Fase 8 concluída |

Cada fase pode ser entregue e validada sozinha. A fase 4 só roda depois de a equipe aprovar o CSV.

## 7. Decisões em aberto

1. **Chave da conta:** `snov_email` (`*@ativa.ai`, como está em `dados.conta`) ou o `email` do cliente (`*.ativa@gmail.com`)? A proposta usa `snov_email`.
2. **Cliente com várias contas** (Tonica, Track Techno, Buzz…): o avanço aponta para uma conta específica (proposta) ou para um grupo "cliente" com várias contas? No segundo caso é preciso um cadastro de cliente no sistema de credenciais.
3. **Squad:** guardar na conta do sistema de credenciais (proposta) ou continuar em `listas_squad`?
4. **SEM SNOVIO:** confirmar a interpretação da seção 1 (rótulo visível, fora do semáforo, corrigível depois).
5. **Revisão dos pendentes:** quem aprova os 648 nomes REVISAR e escolhe conta nos 68 ESCOLHER CONTA, e em que prazo? Sugestão: começar pelos 50 maiores por volume.
6. **Histórico:** o semáforo novo vale só daqui para frente ou também recalcula relatórios antigos?
7. **Painel publicado no VPS:** qual rede/URL usa para falar com o sistema de avanços e com o `snov-am-api`, e onde fica a chave.

## 8. Riscos

- Contagem de verdes cai bastante com a regra de só Interessado (seção 4.1). Avisar a equipe antes de ativar.
- O `snov-am-api` hoje limita requisições (429), derruba conexão em rajada e perde contas na paginação; o job de sincronização precisa ser tolerante a isso.
- O backfill mexe em 41 mil linhas. Mitigação: backup, log por linha e execução só depois do CSV aprovado.
- Dependência de rede: o sistema de avanços passa a depender do `snov-am-api` para listar contas. Mitigar com cache e com a opção SEM SNOVIO como saída quando a API estiver fora.
- Nomes de cliente com encoding quebrado na base continuam sem match até o texto ser corrigido na origem.
