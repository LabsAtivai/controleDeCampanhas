"""Contrato JSON das rotas de dados — as chaves que o painel-frontend consome.
Compartilhado pelos testes SQLite, MySQL de teste e smoke só-leitura."""

CONTRATO_CAMPANHA_SQUAD = {
    "campaignId", "campanha", "conta", "data", "totalContacted", "emailsSent",
    "delivered", "emailOpens", "linkClicks", "emailReplies",
}

CONTRATO_CONTA_RESUMO = {
    "conta", "totalContacted", "emailsSent", "delivered", "emailOpens", "linkClicks",
    "emailReplies", "avancos", "ultimaColeta", "diasDisparos", "taxaAbertura",
    "taxaResposta", "statusAvanco",
}

CONTRATO_DIA_ANALISE = {
    "data", "totalContacted", "emailsSent", "delivered", "emailOpens", "linkClicks",
    "emailReplies", "avancos", "cumEmailsSent", "cumEmailOpens", "cumEmailReplies",
}

CONTRATO_AVANCO = {"id", "data", "conta", "quantidade"}

STATUS_AVANCO = {"verde", "amarelo", "vermelho"}
