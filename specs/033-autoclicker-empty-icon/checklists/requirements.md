# Checklist de Requisitos: Issue #77

## Escopo

- [x] O diff de produção contém somente a projeção visual da `AutoClickerPage`.
- [x] `mouse_hub/core` e `mouse_hub/platform` permanecem sem alterações.
- [x] Nenhuma dependência, regra de domínio, capacidade ou persistência foi adicionada.

## Comportamento

- [x] O `status_frame` não cria nem adiciona `QLabel("")` como placeholder.
- [x] `status_title` e `status_sub` permanecem visíveis e alinhados em 1050×680.
- [x] `status_title` e `status_sub` permanecem visíveis e alinhados em 760×560.
- [x] Estados `stopped`, `running`, `blocked_by_focus` e `failed` permanecem textualmente corretos.
- [x] `_toggle()` funciona ao iniciar e parar sem `AttributeError`.
- [x] O gating de capacidade, CPS, seleção de botão e botão de início permanece inalterado.
- [x] Nenhum emoji ou glyph dependente de fonte foi criado.

## Testes e artefatos

- [x] O teste dedicado falhou no baseline por causa do placeholder/referências residuais.
- [x] O teste dedicado passou depois do fix.
- [x] Regressões do Auto-Clicker, capacidades e UI passaram.
- [x] `3_clicker.png`, `small_clicker.png` e `preview.png` foram regeneradas pelo capturador oficial quando necessário.
- [x] As 15 PNGs foram comparadas byte a byte em duas execuções.
- [x] Dimensões oficiais e bboxes do diff contra `origin/main` foram verificados.
- [x] Smoke Xvfb, compileall/imports, diff-check, pacote e suíte completa passaram.
- [ ] Revisão independente não deixou achado Critical/Important sem tratamento.
- [ ] Os três checks reais do CI passaram no HEAD final.

## Entrega

- [ ] A branch publicada é `fix/remove-autoclicker-empty-icon`.
- [ ] O PR contém `Closes #77`, descrição em pt-BR, testes e riscos.
- [ ] O PR está aberto, não é draft e não está merged.
- [x] A validação distingue evidência de software de validação física.
