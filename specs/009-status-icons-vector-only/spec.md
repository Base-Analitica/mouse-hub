# Feature Specification: Status sem glifos dependentes de fonte

**Feature Branch**: `fix/vector-status-icons`

**Created**: 2026-08-29

**Status**: Convergido localmente; aguardando CI do PR

**Input**: Issue #84 — eliminar `✔` e `⚠` usados como iconografia de
status em `app/mouse_hub_app.py`, preservando estados honestos e a
consistência vector-only da UI.

## User Scenarios & Testing

### User Story 1 — Status consistente em qualquer máquina (Priority: P1)

Como usuário do Mouse Hub, quero que sucesso, atenção e falha tenham a mesma
aparência em diferentes fontes e plataformas, para que a mensagem não mude de
significado por causa do fallback de fonte.

**Independent Test**: varrer o código da UI e construir os estados relevantes
em modo offscreen; nenhum `✔` ou `⚠` pode ser renderizado como texto.

**Acceptance Scenarios**:

1. **Given** uma mensagem de sucesso, parcial, atenção ou falha, **When** ela
   aparece na UI, **Then** sua semântica permanece explícita no texto e na cor,
   sem prefixo Unicode ornamental.
2. **Given** o status de erro do Auto-Clicker, **When** ele é exibido, **Then**
   o alerta grande usa o ícone vetorial `alert` do subset existente; se o
   subset não estiver disponível, a mensagem textual continua completa e a UI
   não falha.
3. **Given** a tela de Perfis ou Configurações, **When** um estado confirmado
   ou negado é exibido, **Then** o texto permanece compreensível sem depender
   de `✔` ou `⚠`.

### User Story 2 — Regressão protegida no CI (Priority: P1)

Como mantenedor, quero uma verificação determinística sem hardware que impeça
um novo glifo de status de voltar à UI.

**Independent Test**: `pytest tests/test_issue84_no_status_glyphs.py` em modo
offscreen, seguido da suíte existente.

## Requirements

### Functional Requirements

- **FR-001**: `app/mouse_hub_app.py` MUST conter zero ocorrências de `✔` e `⚠`
  usadas pela UI.
- **FR-002**: Mensagens de sucesso, parcial, atenção e falha MUST continuar
  distinguíveis por texto e tokens de cor existentes.
- **FR-003**: O status de erro do Auto-Clicker MUST manter seu destaque visual
  com o ícone vetorial sem dependência de emoji ou glifo de fonte do sistema.
- **FR-004**: Falha ou ausência do subset vetorial MUST degradar para texto
  completo, sem crash e sem substituir o ícone por outro emoji.
- **FR-005**: A lógica funcional de Auto-Clicker, Macros, Perfis e Configurações
  MUST permanecer inalterada.
- **FR-006**: A correção MUST incluir teste determinístico que falhe quando
  `✔`/`⚠` retornarem à UI.
- **FR-007**: Screenshots públicas afetadas MUST ser regeneradas no mesmo PR.

## Scope

Inclui os status listados no issue em `app/mouse_hub_app.py` e a verificação
regressiva correspondente. Não inclui redesenho de mensagens, troca de tokens
de cor, nem migração de iconografia fora dos status citados.

## Edge Cases

- O subset de ícones pode não carregar: o contrato existente de
  `app/ui/icons.py` retorna `None`; nesse caso o texto puro é o fallback.
- Um texto pode conter pontuação Unicode legítima em prosa; fora de escopo é
  proibir Unicode em toda a UI. A regra desta feature é especificamente não
  usar `✔`/`⚠` como iconografia de status.
- O ambiente CI não possui mouse físico nem sessão X11; os testes devem usar
  leitura estática e fakes/offscreen.

## Success Criteria

- Zero ocorrências de `✔`/`⚠` em `app/mouse_hub_app.py` após a mudança.
- 100% dos testes dedicados da issue passam no CI sem hardware.
- A suíte existente permanece verde, sem alteração de thresholds ou remoção
  de testes.
- O estado de erro do Auto-Clicker continua tendo um indicador visual
  vetorial quando o subset está disponível e texto explicativo sempre.

## Key Entities

- `ui_icons.icon`: contrato de ícone vetorial com fallback `None`.
- `AutoClickerPage.status_icon`: indicador visual do estado do motor.
- Mensagens de status de Macros, Perfis e Configurações: copy com cor
  semântica, sem prefixos dependentes de fonte.

## Review & Acceptance Checklist

- [ ] Nenhum `✔`/`⚠` na UI.
- [ ] O alerta do Auto-Clicker usa o subset vetorial e tem fallback seguro.
- [ ] Texto e cores continuam honestos.
- [ ] Teste dedicado falha antes e passa depois do fix.
- [ ] Screenshots afetadas foram regeneradas.
- [ ] CI (test + ui_smoke) verde.
