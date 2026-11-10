---
name: Ativa — Controle de Campanhas
description: Estação de supervisão operacional com dados densos, contexto persistente e estados explícitos.
colors:
  canvas: "#f5f7fa"
  surface: "#fff"
  surface-soft: "#f8fafc"
  ink: "#18283c"
  body-ink: "#253347"
  muted: "#647287"
  line: "#e3e8ef"
  blue: "#2b5ed7"
  blue-hover: "#214db5"
  blue-soft: "#edf2fe"
  navy: "#14263e"
  success: "#19734c"
  success-bg: "#edf8f1"
  warning: "#8a590c"
  warning-bg: "#fff5df"
  danger: "#b43e47"
  danger-bg: "#fceef0"
  neutral: "#59677b"
  neutral-bg: "#edf0f5"
typography:
  headline:
    fontFamily: "Public Sans Variable, Public Sans, system-ui, sans-serif"
    fontSize: "27px"
    fontWeight: 650
    lineHeight: 1.3
    letterSpacing: "-0.035em"
  title:
    fontFamily: "Public Sans Variable, Public Sans, system-ui, sans-serif"
    fontSize: "14px"
    fontWeight: 600
    lineHeight: 1.45
    letterSpacing: "-0.015em"
  body:
    fontFamily: "Public Sans Variable, Public Sans, system-ui, sans-serif"
    fontSize: "14px"
    lineHeight: 1.5
  label:
    fontFamily: "Public Sans Variable, Public Sans, system-ui, sans-serif"
    fontSize: "11px"
    fontWeight: 500
    lineHeight: 1.4
  metric:
    fontFamily: "Public Sans Variable, Public Sans, system-ui, sans-serif"
    fontSize: "26px"
    fontWeight: 600
    lineHeight: 1.2
    letterSpacing: "-0.035em"
  log:
    fontFamily: "ui-monospace, SFMono-Regular, Consolas, monospace"
    fontSize: "11px"
    lineHeight: 1.9
rounded:
  small: "4px"
  badge: "5px"
  control: "6px"
  notice: "7px"
  toast: "8px"
  panel: "9px"
spacing:
  inline-small: "6px"
  inline: "8px"
  control: "12px"
  inset-small: "18px"
  inset: "24px"
  page-inline: "36px"
components:
  button-primary:
    backgroundColor: "{colors.blue}"
    textColor: "{colors.surface}"
    rounded: "{rounded.control}"
    padding: "9px 13px"
  button-primary-hover:
    backgroundColor: "{colors.blue-hover}"
  button-secondary:
    backgroundColor: "{colors.surface}"
    textColor: "#3d4d64"
    rounded: "{rounded.control}"
    padding: "9px 13px"
  button-quiet:
    backgroundColor: "transparent"
    textColor: "#52647b"
    rounded: "{rounded.control}"
    padding: "9px 13px"
  input:
    backgroundColor: "{colors.surface}"
    textColor: "#304a66"
    rounded: "{rounded.control}"
    padding: "11px 12px"
  status-success:
    backgroundColor: "{colors.success-bg}"
    textColor: "{colors.success}"
    rounded: "{rounded.badge}"
    padding: "5px 8px"
  panel:
    backgroundColor: "{colors.surface}"
    rounded: "{rounded.panel}"
  traffic-selected:
    backgroundColor: "{colors.blue-soft}"
    textColor: "#204da8"
    rounded: "{rounded.control}"
    padding: "8px 10px"
---

# Design System: Ativa — Controle de Campanhas

## Overview

**Creative North Star: "Estação de supervisão operacional"**

O sistema construído combina navegação navy persistente, canvas claro frio e instrumentos brancos delimitados por linhas finas. A leitura prioriza comparação: números tabulares, títulos compactos e métricas agrupadas na mesma superfície.

Azul identifica ações, seleção e avanços destacados. Cores semânticas comunicam estados junto de texto e sinais gráficos. A densidade operacional permanece legível em telas pequenas por reorganização dos controles e rolagem local das tabelas, sem converter dados ausentes em zero.

**Key Characteristics:**
- Navegação escura e superfícies de trabalho claras.
- Métricas alinhadas e números tabulares.
- Estado semântico acompanhado por texto.
- Bordas discretas e profundidade localizada.

Registro extraído de `frontend/src/styles.css`, `main.js`, componentes e telas Vue; o código construído prevalece sobre intenções do contrato. A fonte Public Sans é distribuída pelo pacote local `@fontsource-variable/public-sans`. A direção foi construída diretamente em código; não houve composição visual aprovada. As capturas de revisão usam dados sintéticos explicitamente identificados e não comprovam métricas reais.

## Colors

A paleta separa orientação, ação e estado semântico; os valores normativos estão no frontmatter.

### Primary
- **Azul de ação** (`blue`): botões principais, seleção de squad, links e avanços destacados; `blue-hover` acompanha interação e `blue-soft` preenche seleção de filtro.
- **Navy de orientação** (`navy`): navegação lateral, menu móvel e área institucional do login.

### Secondary
- **Verde de acompanhamento** (`success`, `success-bg`): estado Em dia e jobs concluídos.
- **Âmbar de atenção** (`warning`, `warning-bg`): estado Atenção e conclusão parcial.
- **Vermelho de ocorrência** (`danger`, `danger-bg`): estado Sem avanço e falhas operacionais.

### Neutral
- **Canvas frio** (`canvas`), **superfície branca** (`surface`) e **superfície suave** (`surface-soft`): camadas de leitura.
- **Tinta navy** (`ink`), **texto de corpo** (`body-ink`) e **texto secundário** (`muted`): hierarquia textual.
- **Linha fria** (`line`): bordas e separação estrutural.
- **Estado neutro** (`neutral`, `neutral-bg`): Sem vínculo e Indisponível, diferenciados pelo texto e ícone.

**The Estado explícito Rule.** Cor de semáforo sempre acompanha rótulo; Sem vínculo e Indisponível permanecem identificáveis mesmo compartilhando a paleta neutra.

## Typography

**Display Font:** Public Sans Variable, com Public Sans e fontes de sistema como fallback.
**Body Font:** A mesma família, em pesos e tamanhos contidos.
**Label/Mono Font:** Public Sans para rótulos; ui-monospace, SFMono-Regular, Consolas e monospace para logs.

### Hierarchy
- **Headline:** título de página; reduz para (25px) até o breakpoint móvel.
- **Title:** cabeçalhos de painel e seção.
- **Body:** base global; tabelas e controles usam predominantemente (12px), com metadados em (11px).
- **Label:** rótulos de métricas e estados. Não há transformação global para caixa alta.
- **Metric:** valores principais; variantes responsivas usam (23–25px), e valores longos reduzem para (17–18px).
- **Login:** título institucional próprio em (39px), peso (520), entrelinha (1.35), com reduções para (34px), (29px) e (24px).

**The Colunas legíveis Rule.** Valores de métricas, tabelas, contagens e eixos usam números tabulares. O tracking compacto das métricas permanece em (-0.035em).

## Layout

O shell desktop usa lateral fixa (216px), barra superior (66px) e conteúdo com largura máxima (1640px). O conteúdo usa padding (31px 36px 45px), com pilha de seções espaçadas em (25px). A lateral reduz para (190px) até (1000px).

Breakpoints reais: mínimo (1650px) amplia respiros; máximos (1200px) e (1000px) reduzem espaçamentos e reorganizam grades; máximo (760px) troca a lateral por menu em dialog, barra de (59px), padding de conteúdo (24px 18px 32px) e pilha de (22px). O corpo suporta largura mínima de (320px).

A faixa de métricas usa uma coluna por item no desktop, quatro colunas até (1000px) e três no móvel; a faixa de cinco itens usa duas colunas no móvel. O último item ocupa a linha final. Tabelas mantêm suas colunas e rolam horizontalmente dentro do painel. Login usa divisão (45%/55%), (43%/57%) até (1000px) e empilhamento no móvel.

## Elevation & Depth

A profundidade depende principalmente de contraste tonal e bordas de um pixel. Painéis de dados ficam sem sombra. Sombras discretas pertencem a botões, seleção segmentada, tooltip e notificações. Foco visível é contorno azul de (3px), afastado (3px); campos usam borda e halo próprios.

### Shadow Vocabulary
- **Ação principal** (`0 2px 3px #173d8820`): botão principal.
- **Ação secundária** (`0 1px 2px #1c355407`): botão secundário.
- **Segmento selecionado** (`0 1px 3px #26394b13`): opção ativa de período.
- **Tooltip** (`0 6px 20px #21375514`): leitura sobre o gráfico.
- **Notificação** (`0 8px 25px #142f4d14`): toast sobre o conteúdo.

**The Plano de leitura Rule.** Painéis comparativos se separam por bordas e superfícies; suas sombras não devem competir com overlays e sinais de interação.

## Shapes

Painéis compartilham cantos discretos pelo token `panel`; controles usam `control`, badges usam `badge` e pequenos contadores usam `small`. Avatares e pontos de estado são circulares. O arredondamento maior do ícone de login é localizado e não altera a regra dos painéis. Ícones são SVG, incluindo a marca própria e os ícones Lucide.

## Components

### Buttons
Botões compactos com ícone opcional, espaçamento interno estável e mínimo de altura (37px). Primário azul, secundário branco com borda fria, quiet transparente. Hover escurece o primário e tinge os demais; desabilitado usa opacidade (0.5). Transições de cor, fundo e borda duram (160ms) com `cubic-bezier(0.2, 0.7, 0.3, 1)`. Não há animação de entrada. Login usa botão de altura mínima (44px).

### Chips
Badges de estado unem ponto ou SVG ao rótulo. A versão pequena reduz padding para (4px 7px). O filtro de semáforo é um botão próprio: contagem tabular, estado `aria-pressed` e seleção azul com borda e linha interna. Sua seleção filtra os estados fornecidos pelo sistema.

### Cards / Containers
Painéis brancos, borda fria e cantos compartilhados. O painel de tabela recorta os cantos, preservando rolagem em um contêiner interno; gráficos usam padding (22px 24px 17px), reduzido no móvel. A faixa de métricas mantém valores em células separadas por divisórias.

### Inputs / Fields
Campos brancos com borda fria, padding (11px 12px) e tipografia (12px). Foco usa borda `#93b0ed` e halo `0 0 0 3px #e6edfc`. Pesquisa tem altura (35px), (39px) no móvel, ícone e foco no contêiner. Inputs do login usam fonte (16px) no móvel. Erros usam texto e tratamento vermelho.

### Navigation
Links compactos com SVG, texto e cantos de controle. Hover ilumina a tinta e o fundo navy; ativo combina fundo `#273d5b`, borda `#3a5272` e texto branco. Grupos separam acompanhamento e administração conforme acesso. No móvel, a navegação entra em dialog lateral (285px), limitado a `calc(100% - 50px)`, com backdrop.

### Faixa de métricas e gráficos
A faixa apresenta rótulo antes do número, contexto secundário e azul para avanços. Loading usa skeleton sem pulsação. Valor desconhecido aparece como travessão; gráficos deixam lacunas para indisponibilidade, em vez de desenhar zero ou conectar dias ausentes. Legendas permitem alternar séries e há controle de dia acessível por teclado. O indicador de atualização gira apenas durante atividade; movimento reduzido encurta animações e transições para (0.01ms).

## Do's and Don'ts

### Do:
- **Do** manter números tabulares nas comparações e contagens.
- **Do** acompanhar o semáforo com texto e distinguir os dois estados neutros por rótulo e ícone.
- **Do** preservar foco visível e rolagem horizontal local das tabelas.
- **Do** representar valor desconhecido com travessão e lacuna nos gráficos.

### Don't:
- **Don't** reutilizar cores de estado como decoração sem significado operacional.
- **Don't** converter indisponibilidade em zero visual.
- **Don't** transformar as sombras localizadas de interação em sombra geral dos painéis.

Não canonizado: rótulos de grupo da navegação com tracking (0.055em) são um detalhe de agrupamento existente, não uma autorização para criar kickers ou eyebrows em novas telas. Nenhum defeito foi reparado neste registro; o verdict final recebido aprovou apenas os achados listados e não equivale a auditoria exaustiva. Não há rasters publicados para documentar; as capturas sintéticas são evidência de revisão, não ativos do sistema visual.
