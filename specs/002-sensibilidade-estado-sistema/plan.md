# Plan: Sensibilidade como estado do sistema (issue #102)

**Input**: `specs/002-sensibilidade-estado-sistema/spec.md`
**Constitution check**: `.specify/memory/constitution.md`

| Princípio | Status | Nota |
|---|---|---|
| I. Correção de hardware | PASS | Não toca em caminho HID de efeito; DPI permanece fail-closed |
| II. Honestidade de estado | PASS | Sensibilidade deixa de alegar leitura de hardware; leitura real do sistema |
| III. Fakes no CI | PASS | FakeSystemInput já cobre leitura; nenhum hardware |
| IV. Regressão com teste | PASS | Testes atualizados + novos (ver tasks) |
| V. Domínio no core | PASS | Leitura inicial vive no core (`MouseController.__init__`) |
| VI. Menor mudança completa | PASS | 1 linha de estado no core + copy da página |
| VII. Verificação dupla | PASS | Claim limitada a software; nada validado fisicamente |
| VIII. UX honesta | PASS | Objetivo da feature |

## Tech & Architecture

- `mouse_hub/core/mouse_controller.py`: `self._applied_sensitivity =
  self.get_sensitivity()` no fim do `__init__` — a fonte do valor inicial
  é o SystemInput (libinput), não o device HID.
- `app/mouse_hub_app.py`: constantes `_SENS_STATE_TEXT` /
  `_SENS_UNKNOWN_TEXT`; `SensitivityPage` passa a usá-las.
- Nenhuma operação (set/commit/slider/polling) muda.

## Data Model

Nenhum esquema novo. `applied_sensitivity` ganha semântica: "último valor
confirmado do sistema (lido ou aplicado)".
