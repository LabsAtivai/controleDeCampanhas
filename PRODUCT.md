# Controle de Campanhas

<!-- impeccable:product-schema 1 -->

## Platform

web

## Stack

Vue, JavaScript, HTML e CSS, solicitados pelo usuário. Frontend compilado com Vite
e servido pelas rotas HTML existentes do Flask. A API não muda nesta tarefa.

## Users

Equipe da Ativa: pessoas que verificam os dados e trabalham a partir deles,
gestores que analisam resultados e redirecionam trabalhos, e responsáveis pela
operação das atualizações. Os três usos foram confirmados pelo usuário. Há
perfis de consulta e administrador no sistema existente.

## Product Purpose

Mostrar métricas de campanhas e avanços comerciais por cliente e squad, com
semáforo, análise diária e operação das coletas. A nova tarefa é uma substituição
visual completa, preservando as funcionalidades e métricas existentes.

## Operating Context

Dashboard de última coleta, análise por período e por cliente, operação de jobs,
login e administração da equipe. Conteúdo em português brasileiro. As datas são
apresentadas no fuso de São Paulo. Uso principal em computador, com acesso móvel.
Os três públicos precisam de caminhos próprios na mesma navegação. A frequência
exata de uso e o ambiente de iluminação não foram informados.

## Capabilities and Constraints

Preservar contatados, enviados, entregues, aberturas, cliques, respostas, avanços,
taxas existentes, dias de disparo, datas de coleta e acumulados. O semáforo é
recebido do backend: verde, amarelo, vermelho, sem vínculo e indisponível.
Indisponibilidade não representa zero. Não alterar regras, banco, jobs, API,
autenticação ou permissões. Manter as cinco rotas HTML atuais e seus fluxos.

## Brand Commitments

Nome Ativa e produto Controle de Campanhas. O usuário autoriza refazer toda a
apresentação, sem compromisso confirmado com a antiga paleta escura ou tipografia.

## Evidence on Hand

Código e contratos existentes em webapp.py, db/dashboard.py, db/crud.py e no
frontend anterior. Capturas do estado anterior em .impeccable/review/before-*.png.
Dados de teste em frontend/tests/fixtures.json são sintéticos e não entram no app.

## Product Principles

- Fidelidade aos dados e ao semáforo existentes.
- Localizar rapidamente cliente, squad, período e estado dos dados.
- Diferenciar resultado zero, ausência de vínculo e indisponibilidade.
- Preservar todas as ações autorizadas por perfil.
- Oferecer leitura acessível por teclado e em telas pequenas.
