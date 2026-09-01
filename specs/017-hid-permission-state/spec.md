# Feature Specification: CTA de permissão HID como estado contextual

**Feature Branch**: `fix/hid-permission-status`
**Created**: 2026-08-29
**Status**: Convergido localmente; aguardando PR/CI
**Input**: Issue #116: não representar “Acesso HID já concedido” como botão desabilitado.

## User Scenarios & Testing

### User Story 1 - Reconhecer acesso HID concedido (Priority: P1)

Como usuário com acesso HID já confirmado, quero ver um status compacto e não
interativo para entender que o controle de DPI físico está disponível sem
confundir um estado concluído com uma ação desabilitada.

**Why this priority**: O estado de sucesso é o caminho principal da página de
Configurações e a apresentação atual usa um controle interativo sem ação.

**Independent Test**: Criar a `SettingsPage` com `hid_available` confirmado e
verificar que o texto de sucesso permanece visível, enquanto a CTA de concessão
não aparece.

**Acceptance Scenarios**:

1. **Given** o core confirma `hid_available`, **When** a página é construída ou
   sincronizada, **Then** o status verde informa que o acesso HID está ativo e a
   CTA de concessão fica oculta.
2. **Given** a página volta a ser sincronizada após uma concessão bem-sucedida,
   **When** o re-probe termina, **Then** nenhum botão desabilitado é usado como
   decoração do estado concluído.

---

### User Story 2 - Resolver ausência de permissão (Priority: P1)

Como usuário sem a regra udev necessária, quero uma ação clara para conceder o
acesso pelo fluxo gráfico de polkit, sem perder a causa real da indisponibilidade.

**Why this priority**: Sem esse caminho o usuário não consegue habilitar o DPI
físico sem recorrer ao terminal.

**Independent Test**: Criar a página com uma causa classificada por
`is_hid_permission_issue`, verificar CTA visível e habilitada, e executar o fake
do fluxo de concessão.

**Acceptance Scenarios**:

1. **Given** `hid_available` está indisponível por falta de permissão, **When** a
   página é sincronizada, **Then** a causa aparece e a CTA fica visível e
   habilitada.
2. **Given** a CTA foi acionada, **When** a autenticação está em andamento,
   **Then** o botão fica temporariamente desabilitado para impedir concorrência,
   e **when** a operação termina, **Then** o status é atualizado sem alterar o
   fluxo polkit existente.

---

### User Story 3 - Não prometer uma correção que não existe (Priority: P2)

Como usuário cuja falha HID não é resolvível pela regra udev, quero ver a causa
real sem receber uma CTA que não pode corrigir o problema.

**Why this priority**: Evita tentativas inúteis e mantém a distinção entre
permissão, endpoint ausente e estado ainda desconhecido.

**Independent Test**: Sincronizar a página com uma causa não acionável ou sem
`MouseCoreState` e verificar que o motivo permanece visível e a CTA não aparece.

**Acceptance Scenarios**:

1. **Given** a causa é diferente de um problema de permissão, **When** a página
   é sincronizada, **Then** o motivo é exibido e a CTA fica oculta.
2. **Given** não existe estado de hardware disponível, **When** a página é
   sincronizada, **Then** o aviso de estado indisponível permanece visível e a
   CTA fica oculta.

---

## Edge Cases

- Uma falha ou cancelamento do polkit deve preservar a mensagem de resultado e
  permitir nova tentativa somente quando a causa continuar acionável.
- Durante o trabalho assíncrono a CTA pode permanecer visível, mas deve ficar
  desabilitada até a thread terminar.
- Uma nova sincronização após hotplug ou re-probe deve aplicar novamente a
  visibilidade correta, sem depender do texto anterior do botão.
- A solução depende do PR #129/#84 para remover glifos de status; este PR não
  reintroduz caracteres dependentes de fonte.

## Requirements

### Functional Requirements

- **FR-001**: A página MUST manter um texto de status explicativo para os
  estados conhecido, desconhecido e de falha.
- **FR-002**: Quando `hid_available` estiver confirmado, a página MUST ocultar a
  CTA de concessão em vez de mostrá-la desabilitada.
- **FR-003**: Quando a causa for reconhecida por `is_hid_permission_issue`, a
  página MUST mostrar a CTA habilitada e manter o fluxo polkit existente.
- **FR-004**: Quando o estado estiver ausente, a causa não for acionável ou a
  operação já estiver em andamento, a CTA MUST não oferecer uma ação enganosa;
  durante uma operação em andamento ela pode permanecer visível e desabilitada
  apenas para impedir um segundo acionamento.
- **FR-005**: A sincronização MUST ser idempotente e restaurar `show()` ou
  `hide()` quando a capacidade mudar entre estados.
- **FR-006**: A mudança MUST permanecer na camada de apresentação, sem alterar a
  evidência de hardware, o domínio do core ou a política de polkit.
- **FR-007**: A UI e as capturas públicas MUST respeitar a remoção de glifos de
  status provida pela dependência do issue #84.

### Key Entities

- **CapabilityState**: evidência cacheada pelo core sobre `hid_available` e sua
  causa, consumida pela UI sem ser criada por ela.
- **Permission CTA**: botão de concessão de regra udev via polkit, exibido apenas
  quando a ação é legítima.
- **Permission status**: texto não interativo que descreve o estado atual e sua
  causa.

## Success Criteria

### Measurable Outcomes

- **SC-001**: Nos estados granted, não acionável e desconhecido, a CTA não é
  visível e o texto de status continua presente.
- **SC-002**: No estado de falta de permissão, a CTA é visível e habilitada antes
  do clique, e o teste fake confirma que o fluxo de concessão continua sendo
  chamado.
- **SC-003**: As capturas desktop e 760×560 mostram uma seção de permissões sem
  botão de sucesso desabilitado.
- **SC-004**: Os testes determinísticos, o smoke de UI e os três jobs reais do CI
  passam sem hardware físico.

## Assumptions

- `SettingsPage` continua recebendo `MouseCoreState` e usando
  `capability_state()` como fonte de verdade.
- A classificação `is_hid_permission_issue()` continua sendo o contrato para
  distinguir a ação polkit de outras causas.
- O PR será baseado em `fix/vector-status-icons` para manter a dependência do
  issue #84 explícita e evitar duplicar sua mudança.
- A validação local prova apenas o comportamento do software com fakes; não é
  validação física de um G403 real.

## Out of Scope

- Alterar a regra udev, o comando polkit/pkexec ou a descoberta HID.
- Criar um novo componente de design system ou modificar outros CTAs.
- Inferir permissão por texto na UI em vez da capacidade do core.
