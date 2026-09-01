# Implementation Plan: Espaçamento semântico dos botões do Auto-Clicker

**Branch**: `fix/autoclicker-label-spacing` | **Date**: 2026-08-29 | **Spec**: [spec.md](spec.md)

## Summary

O seletor de botão já possui nomes, códigos, estilos, gating e spacing de layout corretos. O plano remove somente o argumento de ícone vazio da construção dos `QPushButton`, mantém o nome puro e adiciona regressões que observam o texto, a seleção e a geometria real.

## Technical Context

**Language/Version**: Python 3.10+

**Primary Dependencies**: PyQt5 5.15.11 em runtime; pytest e Xvfb no desenvolvimento/CI.

**Storage**: N/A. Nenhum dado ou configuração é alterado.

**Testing**: pytest offscreen, smoke Xvfb, compileall, diff check, captura oficial e empacotamento `.deb`.

**Target Platform**: Linux Mint, aplicativo desktop nativo, viewports 1050×680 e 760×560.

**Project Type**: Aplicativo desktop Python/PyQt5.

**Performance Goals**: Nenhuma operação nova em runtime; a construção de três botões continua linear e sem dependência nova.

**Constraints**: Sem mudança em `mouse_hub/core/`, protocolo, dependências, capability gating, timer ou segurança. Não adicionar ícones neste issue.

**Scale/Scope**: Uma pequena alteração na montagem dos botões, testes focados, três screenshots afetadas e artifacts Spec Kit.

## Constitution Check

*GATE: Deve passar antes da implementação e ser reavaliado após a validação.*

| Princípio | Status pré-implementação | Evidência prevista |
|---|---|---|
| I. Correção de Hardware | N/A | O diff não toca HID++, udev, descoberta ou dispositivo. |
| II. Honestidade de Estado | PASS | A mudança não altera estado. O texto continua sendo apenas nome de botão. |
| III. Fakes no CI | PASS | Testes usam controlador fake, Qt offscreen e Xvfb, sem hardware. |
| IV. Regressão Com Teste | PASS planejado | O teste de texto exato falhará no baseline por causa dos dois espaços. |
| V. Domínio no Core | PASS | Nenhuma regra de domínio ou constante será criada. |
| VI. Menor Mudança Completa | PASS | Remove um artefato textual e reutiliza o layout/estilos existentes. |
| VII. Verificação Dupla | PASS planejado | Evidência de software será separada de qualquer alegação física. |
| VIII. UX Honesta e Consistente | PASS | O rótulo será legível, pt-BR e sem alinhamento por whitespace invisível. |

**Resultado do gate**: PASS. Não há violação constitucional prevista.

## Project Structure

```text
specs/025-autoclicker-label-spacing/
├── spec.md
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── checklists/requirements.md
└── tasks.md
```

```text
app/mouse_hub_app.py                              # montagem dos três QPushButton
tests/test_issue79_autoclicker_label_spacing.py  # texto, seleção e geometria
docs/screenshots/3_clicker.png                   # captura desktop afetada
docs/screenshots/small_clicker.png               # captura small afetada
docs/screenshots/preview.png                     # mosaico público afetado
```

**Structure Decision**: Continuar usando o loop e os estilos existentes. O teste observa widgets reais e o controlador fake, sem criar helper ou camada de apresentação.

## Design and Data Flow

1. `_build()` itera os três nomes na ordem esquerdo, meio e direito.
2. Cada nome é passado diretamente a `QPushButton`, sem prefixo de ícone vazio.
3. Os mesmos códigos 1, 2 e 3 continuam associados em `btn_buttons`.
4. O clique continua chamando `_set_button(código)`.
5. `_sync_caps()` continua controlando os mesmos widgets.
6. O capturador oficial atualiza as superfícies do Auto-Clicker e o preview se houver diferença.

## Test Strategy

- Criar primeiro o teste dedicado, antes da linha de produção, verificando textos exatos e a ausência de whitespace.
- Rodar o teste focado em RED. A falha esperada deve ser o texto com dois espaços, não erro de fixture/import.
- Alterar somente a construção do botão e a sequência de nomes.
- Cobrir estado ativo inicial, seleção de cada botão, gating e ausência de sobreposição nos dois viewports.
- Capturar duas vezes e comparar bytes das três imagens afetadas.
- Rodar compileall, diff check, smoke Xvfb, suíte completa e pacote `.deb`.
- Fazer revisão read-only na rota de swarm autorizada antes de abrir PR.

## Recheck after implementation

Será PASS somente se o teste dedicado e as regressões comprovarem os contratos, as capturas forem reproduzíveis, a suíte e o pacote passarem, e a revisão/CI não apontarem defeitos. A validação será registrada nos artifacts antes da entrega.

## Risks and Mitigations

- **Risco**: remover whitespace alterar o estado ativo. **Mitigação**: testar `ac.button`, estilos e clique para os três códigos.
- **Risco**: o botão escapar no viewport small. **Mitigação**: medir limites e ausência de overlap em 1050×680 e 760×560.
- **Risco**: o gating deixar de encontrar os widgets. **Mitigação**: manter `btn_buttons` e executar regressões de capabilities.
- **Risco**: introduzir ícone ou spacing manual como compensação. **Mitigação**: requisito explícito de nome puro e `setSpacing(12)` inalterado.
- **Risco**: alegar validação física indevida. **Mitigação**: registrar somente fakes, offscreen/Xvfb e package checks.

## Implementation Phases

### Phase 0: Spec and contract

- Completar estes artifacts sem placeholders.
- Criar teste antes de qualquer alteração em produção.

### Phase 1: Label composition

- Trocar a lista de pares `(name, icon)` por nomes simples.
- Construir o botão com o nome puro.
- Não alterar código de seleção, gating, timer ou estilos.

### Phase 2: Regression and visual evidence

- Rodar teste dedicado e regressões de UI/capabilities.
- Verificar os dois viewports e regenerar capturas oficiais.
- Rodar compileall, diff check, smoke, suíte e empacotamento.

### Phase 3: Delivery

- Atualizar artifacts com evidência real e reavaliar a constituição.
- Revisar diff, commitar em inglês, publicar branch e abrir PR com `Closes #79`.
- Confirmar os três checks reais do GitHub, PR aberto e `mergedAt == null`.
