# Feature Specification: Microcopy de permissões HID

**Feature Branch**: `027-hid-permission-microcopy`
**Created**: 2026-08-29
**Status**: Spec ready; implementation pending
**Issue**: #81
**Input**: Atualizar a explicação de permissões HID para refletir o fluxo gráfico atual do Mouse Hub.

## User Scenarios & Testing

### User Story 1 - Entender e autorizar o acesso HID (Priority: P1)

Como usuário que precisa controlar o DPI físico, quero saber por que o acesso HID é necessário e o que o botão de autorização fará, sem receber instruções antigas de terminal ou uma frase incompleta.

**Why this priority**: A seção de Configurações é o ponto de recuperação quando a permissão de escrita está ausente. Copy conflitante pode levar o usuário a executar uma ação manual desnecessária ou não encontrar o fluxo suportado pelo aplicativo.

**Independent Test**: Construir `SettingsPage` com fakes determinísticos, inspecionar o texto introdutório em desktop e small viewport e verificar que o caminho gráfico, a finalidade do acesso e a ação do botão estão explícitos, sem instrução manual obsoleta nem pontuação órfã.

**Acceptance Scenarios**:

1. **Given** a seção de permissões HID é exibida, **When** o usuário lê o texto introdutório, **Then** entende que o acesso é necessário para controlar o DPI físico e que o Mouse Hub pode solicitar autorização administrativa para instalar a regra necessária.
2. **Given** o texto introdutório é renderizado, **When** o usuário procura o próximo passo, **Then** não encontra pedido para usar terminal, alterar permissões manualmente, criar uma regra por conta própria ou um `:` sem conteúdo subsequente.
3. **Given** o estado de capacidade do mouse pode variar, **When** a copy introdutória é atualizada, **Then** a distinção entre mouse detectado, acesso HID e DPI disponível permanece nos estados e no botão existentes.

---

### Edge Cases

- O texto deve caber nos viewports oficiais de 1050×680 e 760×560 com `setWordWrap(True)`.
- A copy não pode afirmar que o acesso foi concedido antes da confirmação real de `hid_available`.
- Estados de acesso já concedido, causa de indisponibilidade e autenticação em andamento continuam sendo controlados por `_sync_permission_ui()` e `_grant_hid_access()`.
- A mudança não deve alterar `fix_hid_permissions()`, polkit/pkexec, descoberta, capabilities, hardware ou a regra udev.
- O idioma da superfície permanece pt-BR, sem jargão de implementação desnecessário.

## Requirements

### Functional Requirements

- **FR-001**: O texto introdutório da seção `Permissões HID (DPI via Hardware)` MUST explicar que o acesso HID é necessário para controlar o DPI físico do mouse.
- **FR-002**: O texto MUST informar que o Mouse Hub usa um fluxo gráfico de autorização administrativa para instalar a regra necessária quando faltar permissão.
- **FR-003**: O texto MUST NOT instruir o usuário a usar terminal, alterar permissões manualmente ou criar uma regra udev por conta própria.
- **FR-004**: O texto MUST NOT terminar com pontuação órfã ou sugerir um bloco de instruções que não existe.
- **FR-005**: A alteração MUST preservar os estados reais de `hid_available`, o label do botão, o status de sucesso/atenção e o comportamento de `_grant_hid_access()`.
- **FR-006**: A mudança MUST ficar restrita à copy da seção HID e aos testes/documentação/capturas necessários, sem tocar em core, plataforma, persistência ou hardware.
- **FR-007**: As screenshots públicas de Configurações MUST ser regeneradas pelo pipeline determinístico do projeto na mesma branch.
- **FR-008**: A implementação MUST incluir teste determinístico que falhe com a copy atual e passe após a correção, sem hardware físico.

### Key Entities

- **Texto introdutório HID**: `QLabel` informativo da `SettingsPage` que explica finalidade e próximo passo do acesso HID.
- **Estado de capacidade**: evidência existente de `hid_available`, consumida por `_sync_permission_ui()`; não é alterada por esta issue.
- **Ação de autorização**: botão existente que chama `_grant_hid_access()` e inicia o prompt gráfico em thread dedicada.

## Success Criteria

### Measurable Outcomes

- **SC-001**: O teste offscreen encontra no texto a finalidade DPI físico, o Mouse Hub/aplicativo, autorização administrativa e instalação da regra necessária.
- **SC-002**: O teste rejeita `crie uma regra`, instruções de terminal, alteração manual de permissões e final `:` na copy introdutória.
- **SC-003**: O teste comprova que o botão continua com seu label e callback existentes e que os estados de sucesso/atenção permanecem distintos.
- **SC-004**: O texto fica contido nos layouts oficiais de 1050×680 e 760×560 sem exigir scroll horizontal ou alterar a hierarquia da página.
- **SC-005**: `6_settings.png`, `small_settings.png` e `preview.png` são regenerados duas vezes com bytes idênticos; as diferenças ficam restritas à seção de permissões HID.
- **SC-006**: Testes focados, suíte completa, smoke Xvfb, compilação, diff check, pacote `.deb` e os três jobs reais do CI passam no commit publicado.
- **SC-007**: Nenhum arquivo de core, plataforma, persistência, mecanismo de autorização ou regra udev é alterado.

## Assumptions

- O fluxo gráfico existente via `pkexec`/polkit é o caminho suportado pelo app e o botão já o inicia.
- `_sync_permission_ui()` continua sendo a fonte de verdade para estados de capacidade e não será reescrito.
- `hid_info` permanece um `QLabel` com word wrap, portanto a solução não precisa de componente novo.
- A validação usa PyQt5 5.15.11, fakes existentes, `QT_QPA_PLATFORM=offscreen` e o pipeline oficial de screenshots.
- A evidência de software não representa autorização real em uma máquina com hardware físico.

## Scope Boundaries

- Não alterar a lógica de `fix_hid_permissions()` nem o prompt de administrador.
- Não mudar o label, habilitação, callback ou estilos do botão nesta issue.
- Não mudar a descoberta do G403, o modelo de capabilities, HID++ ou a regra udev.
- Não corrigir outros textos de Configurações ou screenshots fora das imagens afetadas.

## Traceability

| Requisito | Verificação planejada |
| --- | --- |
| FR-001 / SC-001 | teste dedicado do texto introdutório |
| FR-002 / SC-001 | teste de termos do fluxo gráfico e botão existente |
| FR-003 / SC-002 | asserts de proibição de terminal, mudança manual e regra criada pelo usuário |
| FR-004 / SC-002 | assert de ausência de `:` final e conteúdo posterior inexistente |
| FR-005 / SC-003 | testes existentes de capabilities + teste de estados da `SettingsPage` |
| FR-006 / SC-007 | diff de escopo, compileall e revisão read-only |
| FR-007 / SC-005 | duas capturas oficiais e comparação byte a byte |
| FR-008 / SC-006 | RED/GREEN focado, suíte, smoke, pacote e CI real |

## Open Decisions

Não há decisões de produto pendentes. A copy recomendada é:

> Para controlar o DPI físico do mouse, o Mouse Hub precisa de acesso HID ao G403 HERO. Se faltar permissão de escrita, clique em “Conceder acesso ao hardware” para o aplicativo solicitar autorização administrativa e instalar a regra necessária.

Essa frase explica finalidade e próximo passo sem pedir terminal, sem prometer sucesso antecipado e sem pontuação órfã.
