# Feature Specification: Microcopy de segurança do Auto-Clicker

**Feature Branch**: `028-autoclicker-security-copy`
**Created**: 2026-08-30
**Status**: Spec ready; implementation pending
**Issues**: #82, #83
**Input**: Tornar a explicação de segurança do Auto-Clicker neutra, acionável e livre de jargão de implementação.

## User Scenarios & Testing

### User Story 1 - Entender a proteção do Auto-Clicker (Priority: P1)

Como usuário do Auto-Clicker, quero entender rapidamente em que condição os cliques podem ocorrer e por que a proteção existe, sem interpretar detalhes internos como se fossem uma garantia de sucesso.

**Why this priority**: O texto fica na página de Configurações, uma superfície voltada à operação. Verde semântico e jargão de backend confundem a diferença entre explicação permanente e estado confirmado.

**Independent Test**: Construir a `SettingsPage` real com fakes determinísticos, obter o texto do grupo `Auto-Clicker — Segurança`, verificar linguagem sobre foco e ausência de cliques fora do jogo, confirmar estilo neutro e medir a contenção nos viewports 1050×680 e 760×560.

**Acceptance Scenarios**:

1. **Given** a seção de segurança é exibida, **When** o usuário lê o texto, **Then** entende que Minecraft/Lunar Client precisa estar em foco e que nenhum clique é realizado fora do jogo.
2. **Given** o texto é explicativo e permanente, **When** o usuário observa sua apresentação, **Then** ele usa cor neutra de leitura, não a cor semântica de sucesso.
3. **Given** o usuário não conhece a implementação, **When** lê a explicação, **Then** não precisa interpretar X11, XRecord, cache, TTL ou milissegundos para entender a proteção.
4. **Given** o Auto-Clicker é usado em qualquer viewport oficial, **When** a seção é renderizada, **Then** a mensagem permanece visível, contida e legível.

## Edge Cases

- A copy não pode afirmar que o motor está ativo ou que um clique específico foi realizado.
- A ausência de foco continua sendo bloqueio real do motor, não deve virar promessa de clique posterior.
- A indisponibilidade da automação e seus motivos continuam nos estados/capabilities existentes, fora desta alteração de copy.
- O texto deve permanecer em pt-BR e não pode depender de X11 real para o teste.

## Requirements

### Functional Requirements

- **FR-001**: O texto de segurança MUST explicar que o Auto-Clicker só funciona quando Minecraft/Lunar Client está em foco.
- **FR-002**: O texto MUST informar que nenhum clique é feito fora do jogo ou quando a condição de foco não é satisfeita.
- **FR-003**: O bloco explicativo MUST usar cor neutra de leitura (`text_secondary` ou equivalente), e NÃO `mc_green` como sinal de sucesso.
- **FR-004**: O texto MUST NOT expor X11, XRecord, cache, TTL, `500 ms`, xdotool ou outros detalhes de implementação na superfície operacional.
- **FR-005**: A alteração MUST preservar `AutoClickerEngine`, `WindowFocusChecker`, `focus_patterns()`, estados `running`/`blocked_by_focus`/`failed`, capability gating e controles existentes.
- **FR-006**: A mudança MUST ficar restrita à copy/estilo do bloco, testes, documentação e screenshots necessários, sem tocar core, plataforma, automação ou persistência.
- **FR-007**: As screenshots públicas de Configurações MUST ser regeneradas pelo pipeline determinístico na mesma branch.
- **FR-008**: Testes determinísticos MUST falhar contra a apresentação/copy atual e passar após a correção, sem sessão X11 ou hardware físico.

## Key Entities

- **Texto de segurança**: `QLabel` explicativo do grupo `Auto-Clicker — Segurança` em `SettingsPage`.
- **Estado de foco**: estado real produzido pelo serviço de automação e consumido pelo motor; não é alterado nesta feature.
- **Cor de leitura**: token `COLORS['text_secondary']`, usado para informação neutra.

## Success Criteria

- **SC-001**: O teste offscreen encontra foco de Minecraft/Lunar Client e a garantia de nenhum clique fora do jogo.
- **SC-002**: O teste rejeita `X11`, `XRecord`, `cache`, `TTL`, `500 ms` e xdotool no texto operacional.
- **SC-003**: O teste comprova uso de cor neutra e ausência da cor de sucesso no stylesheet do bloco.
- **SC-004**: A seção permanece contida e visível em 1050×680 e 760×560.
- **SC-005**: Estados, gating e segurança funcional permanecem cobertos pelas regressões existentes.
- **SC-006**: `6_settings.png`, `small_settings.png` e `preview.png` são reproduzidos duas vezes com bytes idênticos e diferenças restritas ao bloco de segurança.
- **SC-007**: Suíte completa, smoke Xvfb, compilação, diff check, pacote e os três jobs reais do CI passam no commit publicado.
- **SC-008**: Nenhum arquivo de core, plataforma, automação ou persistência é alterado.

## Assumptions

- O motor já consulta foco antes de emitir cada clique e falha fechado quando a fonte de foco está indisponível.
- A seção permanece um `QLabel` com word wrap; não é necessário componente novo.
- `text_secondary` é o token de leitura neutra já existente no tema.
- A validação de software não representa uma medição de segurança em uma sessão X11/hardware real.

## Scope Boundaries

- Não alterar `AutoClickerEngine`, `WindowFocusChecker`, `AutomationService` ou `focus_patterns()`.
- Não alterar o botão, o gating de capabilities, timers, cache interno ou mensagens de estado do motor fora do bloco explicativo.
- Não remover detalhes de diagnóstico de `Informações do Sistema` ou documentação interna, caso existam fora desta superfície.
- Não corrigir outras cores ou textos de Configurações nesta feature.

## Traceability

| Requisito | Verificação planejada |
| --- | --- |
| FR-001 / SC-001 | teste dedicado de foco permitido |
| FR-002 / SC-001 | teste dedicado de bloqueio fora do jogo |
| FR-003 / SC-003 | teste de stylesheet neutro |
| FR-004 / SC-002 | asserts negativos para jargão |
| FR-005 / SC-005 | regressões do motor/capabilities e diff de escopo |
| FR-006 / SC-008 | diff, compileall e revisão read-only |
| FR-007 / SC-006 | duas capturas oficiais e comparação byte a byte |
| FR-008 / SC-007 | RED/GREEN, suíte, smoke, pacote e CI real |

## Open Decisions

Não há decisões de produto pendentes. A copy inicial proposta é:

> O auto-clicker só funciona quando Minecraft/Lunar Client está em foco. O app verifica a janela ativa antes de clicar. Fora do jogo, nenhum clique é realizado.

Essa frase comunica a garantia observável sem expor o backend X11 ou o TTL do cache.
