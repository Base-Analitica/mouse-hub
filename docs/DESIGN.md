# DESIGN.md — Mouse Hub

> Fonte de verdade visual. Gerado pelo fluxo `document` da skill
> impeccable. Se um valor visual não está aqui (ou em
> `app/ui/theme.py`), é bug — não invente, adicione como token.

## Modo da superfície

**Operate** — app de tarefa. Scanability, consistência e estados
honestos acima de expressão. Cor é SEMÂNTICA (estado), nunca
decoração.

## Runtime

PyQt5 desktop, stylesheet global construído por
`app/ui/theme.py::build_app_stylesheet()`. **Nunca** use seletor
genérico `QFrame {` em stylesheet de componente — `QLabel` herda de
`QFrame` e o estilo vaza pros filhos (bug histórico). Escope por
`#objectName`.

## Tokens (`app/ui/theme.py`)

- **Cores**: `COLORS` (30+ tokens). Regras de uso:
  - texto de leitura: `text_primary` / `text_secondary` (≥4.5:1);
  - `text_muted` / `text_dim`: SÓ estado desabilitado/decoração;
  - valores hero sobre card: `accent_light` (6.5:1), não `accent`;
  - claros extras: `accent_lighter`, `danger_light`, `danger_lighter`.
- **Tipografia**: `TYPE_SCALE` — 8 passos (11, 12, 13, 14, 16, 20,
  24, 44). Título de página: 24/900. Corpo: 13. Nada fora da escala
  (há teste de invariante).
- **Espaço**: `SPACE` base 4 (4/8/12/16/24/32). Margem de página:
  (24, 16, 24, 16).
- **Raios**: `RADIUS` (6/8/10/12/18).

## Componentes nomeados

`AccentButton`/`DangerButton` (gradiente com todos os stops ≥4.5:1
sobre branco + estado `:disabled` legível), `StatCard`
(expansível: label pequeno + valor 30px + ícone), `SidebarButton`,
cards com `#objectName` (`statCard`, `dpiDisplay`, `sensDisplay`,
`clickerStatus`, `recFrame`, `macroItem`, `sidebar`,
`statusIndicator`), `ProfileCard`.

## Layout responsivo

- Toda página vive em `QScrollArea` frameless
  (`MouseHubApp._wrap_scrollable`); todo `QLabel` com wordWrap;
- Janela mínima **720×520**; grid de stats 2×2; presets DPI 3
  colunas; perfis 3 colunas; **nenhum** `setFixed*` que some >482px
  de largura mínima por linha;
- Invariantes garantidos por `tests/test_issue66_ui_craft.py`
  (sem sobreposição de irmãos e sem conteúdo mais largo que o
  viewport no tamanho mínimo — roda na suíte).

## Estados honestos (issue #7)

- Valor não lido do hardware: `—` + legenda de estado
  ("AGUARDANDO LEITURA DO HARDWARE"), nunca um chute;
- Capacidade indisponível: explicada com a causa (ex.: Polling
  Rate), botões desabilitados executam NADA;
- Acesso HID: botão de permissão reflete a evidência real
  ("✔ Acesso HID já concedido" quando ativo).

## Microinterações

Hover muda borda/fundo (sem glow). Sem animação que trave input;
transições curtas se existirem (120–250ms, OutCubic).
