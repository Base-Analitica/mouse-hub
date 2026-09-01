# Semanticização dos ícones de DPI e Macros: Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use TDD and verify every task before marking it complete.

**Goal:** Substituir os ícones fast-forward e filmstrip de DPI e Macros por
 glifos Remix semanticamente adequados, preservando fallback, layout e runtime.

**Architecture:** Manter a API e as chaves semânticas de `app.ui.icons`,
alterando somente os dois codepoints e o subset TTF embutido. A sidebar e os
headings continuam consumindo essas chaves existentes, e a suíte offscreen
prova presença dos glifos e o fallback quando a fonte não está disponível.

**Tech Stack:** Python 3.10+, PyQt5 5.15.11, pytest, FontTools somente como
ferramenta local de geração do subset, scripts oficiais de screenshots e CI
GitHub Actions.

**Spec:** [spec.md](spec.md)

## Global Constraints

- Sem mudança em `mouse_hub/core/` ou em operações HID++.
- Sem emoji, fonte completa no repositório ou dependência nova de runtime.
- `dpi` usa U+ED4C (`ri-focus-3-line`) e `macros` usa U+EE75 (`ri-keyboard-line`).
- O fallback de `icon()` e `icon_label()` continua retornando `None`.
- Testes e screenshots usam `QT_QPA_PLATFORM=offscreen` e fakes existentes.
- Commits em inglês, documentação e PR em pt-BR, branch `fix/<tema>`, sem merge.

---

## Summary

A sidebar e os headings já usam nomes semânticos compartilhados, mas seus
codepoints atuais desenham fast-forward para DPI e filmstrip para Macros. O
plano substitui os dois codepoints, amplia o subset Remix de 12 para 14 glifos,
e adiciona testes runtime que verificam o mapeamento, a presença do glypho no
TTF, a renderização nos tamanhos oficiais e o fallback.

## Technical Context

**Language/Version**: Python 3.10+

**Primary Dependencies**: PyQt5 5.15.11 em runtime; pytest no desenvolvimento.
FontTools não será dependência do projeto.

**Storage**: N/A. Nenhum dado ou configuração é alterado.

**Testing**: pytest offscreen, `QRawFont.supportsCharacter`, smoke Xvfb,
`compileall`, `git diff --check`, captura oficial e jobs reais de CI.

**Target Platform**: Linux Mint, aplicativo desktop nativo, viewports 1050×680 e
760×560.

**Project Type**: Aplicativo desktop Python/PyQt5.

**Performance Goals**: Nenhuma operação nova em runtime. O subset continua
pequeno e o carregamento da fonte mantém cache único.

**Constraints**: Alterar apenas `app/ui/icons.py`, o TTF subset, teste dedicado,
screenshots e documentação Spec Kit. Preservar as demais chaves e o fallback.

**Scale/Scope**: Dois mapeamentos, dois glifos no asset, um teste dedicado,
cinco PNGs afetados e artefatos Spec Kit.

## Constitution Check

*GATE: Deve passar antes da implementação e ser reavaliado após a captura.*

| Princípio | Status | Evidência planejada |
|---|---|---|
| I. Correção de Hardware | N/A | A mudança não toca HID++, udev ou dispositivo. |
| II. Honestidade de Estado | PASS | Ícones não afirmam capacidade nem estado de hardware. |
| III. Fakes no CI | PASS | Testes Qt offscreen e smoke sem hardware físico. |
| IV. Regressão Com Teste | PASS | Assert de codepoints e presença do subset falha no estado atual. |
| V. Domínio no Core | PASS | Nenhuma regra de domínio ou constante é criada. |
| VI. Menor Mudança Completa | PASS | Dois mapeamentos, dois glyphos, teste, PNGs e docs. |
| VII. Verificação Dupla | PASS | Claims limitadas à evidência de software, sem claim física. |
| VIII. UX Honesta e Consistente | PASS | DPI comunica precisão e Macros comunica teclas, em pt-BR. |

**Resultado do gate**: PASS. Não há violação constitucional ou complexidade
adicional necessária.

## Project Structure

### Documentation

```text
specs/023-semantic-dpi-macros-icons/
├── spec.md
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── checklists/requirements.md
└── tasks.md
```

Não há `contracts/`: a mudança não cria API externa, persistência ou contrato
de domínio.

### Source Code

```text
app/ui/icons.py                         # mapeamentos semânticos e fallback
app/ui/fonts/remixicon-subset.ttf       # subset Remix embutido
tests/test_issue111_semantic_icons.py   # contrato runtime dos dois glifos
app/mouse_hub_app.py                    # call sites existentes, sem mudança
scripts/capture_screenshots.py          # pipeline oficial, sem mudança
docs/screenshots/1_dpi.png              # captura desktop afetada
docs/screenshots/small_dpi.png          # captura small afetada
docs/screenshots/4_macros.png           # captura desktop afetada
docs/screenshots/small_macros.png       # captura small afetada
docs/screenshots/preview.png            # mosaico público afetado
```

**Structure Decision**: Reutilizar o módulo e o asset existentes. O teste
observa `app.ui.icons` diretamente e verifica os call sites textualmente, sem
criar camada ou helper de produção.

## Design and Data Flow

1. `_CODEPOINTS["dpi"]` passa de U+F177 para U+ED4C.
2. `_CODEPOINTS["macros"]` passa de U+ED21 para U+EE75.
3. O subset é regenerado a partir dos 12 codepoints atuais mais os dois novos.
4. `SidebarButton` continua renderizando cada chave em 18 px.
5. `DPIPage` e `MacrosPage` continuam renderizando a mesma chave em 24 px.
6. Se `_family()` não carregar a fonte, as APIs retornam `None` como antes.
7. O capturador oficial atualiza as duas páginas, variantes small e preview.

## Test Strategy

- Escrever primeiro `tests/test_issue111_semantic_icons.py` com asserts de
  codepoint, presença via `QRawFont.supportsCharacter`, renderização em 18/24
  px e fallback. Rodar o teste e registrar RED causado pelos codepoints ausentes.
- Gerar o subset e alterar somente `_CODEPOINTS`; rodar GREEN focado.
- Rodar regressões de craft/UI e o smoke para provar que sidebar, headings e
  fallback continuam inicializando.
- Capturar todas as telas oficiais e verificar que somente cinco PNGs mudaram.
- Rodar suíte completa, compileall, diff check e empacotamento no CI.
- Fazer revisão read-only usando somente rota de swarm autorizada e corrigir
  achados antes do PR.

## Implementation Phases

### Phase 0: Spec and contract

- Manter os documentos Spec Kit preenchidos e sem placeholders.
- Criar o teste dedicado antes de qualquer alteração em produção ou no TTF.

### Phase 1: Semantic glyphs

- Regenerar o subset com U+ED4C e U+EE75.
- Atualizar os dois valores em `_CODEPOINTS` e manter API/fallback inalterados.

### Phase 2: Visual evidence and regressions

- Rodar testes focados e regressões de UI.
- Regenerar/revisar PNGs desktop, small e preview.
- Rodar suíte, smoke, compileall e diff check.

### Phase 3: Delivery

- Atualizar checklist e registros de validação.
- Revisar diff read-only, commitar em inglês, publicar branch e abrir PR com
  `Closes #111`.
- Aguardar os três checks reais do GitHub e confirmar PR aberto e não merged.

## Risks and Mitigations

- **Risco**: subset não conter um novo codepoint. **Mitigação**:
  `QRawFont.supportsCharacter()` e teste GREEN no asset real.
- **Risco**: glifo ficar ilegível em sidebar. **Mitigação**: teste nos tamanhos
  18/24 e inspeção das cinco capturas oficiais.
- **Risco**: fallback quebrar quando a fonte está ausente. **Mitigação**:
  teste forçando `_FONT_FAMILY = ""` e smoke de UI.
- **Risco**: alteração indireta em hardware ou layout. **Mitigação**: diff
  restrito a arquivos previstos, regressões e nenhum arquivo de core.
- **Risco**: claim física indevida. **Mitigação**: registrar somente evidência
  determinística de software; nenhum teste simula medição física do G403.

## Complexity Tracking

Nenhuma violação constitucional ou complexidade adicional prevista.

## Validation Record (pre-implementation)

O baseline do worktree em `origin/main` passou a suíte determinística completa
antes de qualquer alteração. Os registros RED, GREEN, capturas, revisão e CI
serão adicionados ao documento à medida que cada gate for executado, sem
antecipar resultados.
