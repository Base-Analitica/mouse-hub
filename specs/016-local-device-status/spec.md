# Feature Specification: Status local inequívoco do dispositivo

**Feature Branch**: `fix/local-device-status`

**Created**: 2026-08-29

**Status**: Em implementação

**Input**: Issue #115 — `[P2][UX] Status global “Online” é vago para um dispositivo local`

## User Scenarios & Testing *(mandatory)*

### User Story 1 - A sidebar identifica o estado local (Priority: P2)

Ao abrir o Mouse Hub, o usuário deve entender imediatamente se o G403 foi
conectado, apenas detectado sem acesso HID, ou não foi detectado. O indicador não
deve usar linguagem de serviço web para descrever um dispositivo local.

**Why this priority**: `Online` não informa se representa descoberta, endpoint
HID, DPI ou apenas o processo. Isso força o usuário a abrir outras telas para
interpretar um estado básico.

**Independent Test**: Montar `MouseHubApp` com `CapabilityState` fake para cada
combinação de `mouse_detected` e `hid_available`, chamar a atualização da
sidebar e verificar texto e cor.

**Acceptance Scenarios**:

1. **Given** `mouse_detected=True` e `hid_available=True`, **When** a sidebar é
   atualizada, **Then** ela mostra `G403 conectado`.
2. **Given** `mouse_detected=True` e `hid_available=False`, **When** a sidebar é
   atualizada, **Then** ela mostra `Mouse detectado`.
3. **Given** `mouse_detected=False`, **When** a sidebar é atualizada, **Then**
   ela mostra `Mouse não detectado`.

### User Story 2 - Capacidades não são colapsadas (Priority: P2)

O texto da sidebar deve comunicar conexão local, enquanto as páginas de DPI e
outras capacidades continuam mostrando seus próprios estados. DPI indisponível
não pode transformar um mouse conectado em “não conectado”, e mouse detectado
sem HID não pode ser apresentado como acesso HID confirmado.

**Independent Test**: Usar modelos com `hardware_dpi_available` e
`sensitivity_available` variados, mantendo a matriz de conexão da sidebar, e
confirmar que o texto depende apenas das duas capacidades previstas para o
indicador.

**Acceptance Scenarios**:

1. **Given** o mouse detectado e HID acessível, mas DPI indisponível, **When** a
   sidebar é atualizada, **Then** ela continua mostrando `G403 conectado`.
2. **Given** o mouse detectado sem HID, **When** DPI ou Sensibilidade também
   estão indisponíveis, **Then** ela mostra `Mouse detectado`, não `Online`.

### User Story 3 - Copy permanece compacta e comprovada (Priority: P2)

Os textos novos devem caber na sidebar em desktop e em 760×560. As capturas
públicas que exibem o indicador devem refletir o estado local com fakes
reprodutíveis.

**Independent Test**: Renderizar a aplicação no capturador oficial em tamanho
desktop e small, conferir a largura do texto e comparar os caminhos de imagem
alterados.

**Acceptance Scenarios**:

1. **Given** a janela desktop ou small, **When** a sidebar é exibida, **Then** o
   texto não cria overflow horizontal nem desloca a navegação.
2. **Given** o capturador com G403 fake, **When** as screenshots são regeneradas,
   **Then** a sidebar mostra `G403 conectado` nas imagens afetadas.

## Edge Cases

- `mouse_detected=True` e `hid_available=False` é um estado válido, não falha de
  descoberta, e deve permanecer distinguível.
- `hardware_dpi_available=False` não deve alterar o texto de conexão da sidebar.
- Um estado sem mouse deve mostrar a causa de conexão local no texto sem declarar
  que o processo do aplicativo está offline.
- O texto deve continuar legível no layout small sem substituir a rolagem ou
  esconder controles.
- Hotplug deve reutilizar a mesma matriz e atualizar o texto após refresh, sem
  introduzir polling adicional.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: A sidebar MUST exibir `G403 conectado` quando
  `mouse_detected` e `hid_available` forem confirmados.
- **FR-002**: A sidebar MUST exibir `Mouse detectado` quando apenas
  `mouse_detected` for confirmado.
- **FR-003**: A sidebar MUST exibir `Mouse não detectado` quando
  `mouse_detected` não for confirmado.
- **FR-004**: O texto do indicador MUST depender somente de conexão local e acesso
  HID, sem usar `hardware_dpi_available` como sinônimo de conexão.
- **FR-005**: As cores existentes de sucesso, warning e muted MUST continuar
  correspondendo aos três estados, sem criar estado visual falso.
- **FR-006**: O contrato MUST ser coberto por testes determinísticos com fakes,
  incluindo atualização após troca de página e hotplug.
- **FR-007**: Screenshots desktop, small e preview que exibem a sidebar MUST ser
  regeneradas no mesmo PR, sem hardware real.
- **FR-008**: O PR MUST passar testes determinísticos, smoke Xvfb e empacotamento
  `.deb`, permanecendo aberto para revisão do mantenedor.

### Key Entities

- `MouseHubApp._update_sidebar_status`: projeta a matriz de capacidades na copy
  curta da sidebar.
- `CapabilityState`: evidência imutável de capacidades do core consumida pela UI.
- `_status_text` e `_status_dot`: widgets visuais do indicador global.
- `MouseHubApp._on_device_changed`: caminho de atualização após hotplug.

## Out of Scope

- Alterar detecção, probe HID++, descoberta, permissões ou o modelo de
  capacidades no core.
- Expor jargão de implementação, caminhos hidraw ou detalhes de protocolo na
  sidebar.
- Fazer `hardware_dpi_available` controlar o texto de conexão.
- Adicionar polling periódico ou mudar o comportamento de hotplug.
- Declarar validação física do G403 HERO; a prova é de software com fakes, Qt e
  CI.

## Review & Acceptance Checklist

- [ ] `G403 conectado` identifica mouse detectado com HID acessível
- [ ] `Mouse detectado` identifica mouse sem HID acessível
- [ ] `Mouse não detectado` identifica ausência do mouse
- [ ] DPI indisponível não é confundido com mouse desconectado
- [ ] Textos cabem em desktop e small
- [ ] Testes dedicados reproduzem RED antes do fix e GREEN depois
- [ ] Hotplug e troca de página permanecem corretos
- [ ] Screenshots afetadas foram regeneradas
- [ ] Suíte local, smoke, compileall e `git diff --check` passam
- [ ] CI real está verde
- [ ] PR aberto e não mergeado
