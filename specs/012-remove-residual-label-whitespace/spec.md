# Feature Specification: Remover whitespace residual das labels

**Feature Branch**: `fix/remove-residual-label-whitespace`

**Created**: 2026-08-29

**Status**: Convergido localmente; aguardando commit/PR

**Input**: Issue #89 — espaços prefixados e sequências artificiais de espaços
restaram nas labels depois das mudanças visuais, criando desalinhamentos e
comparações frágeis baseadas no texto.

## User Scenarios & Testing

### User Story 1 — Copy alinhada (Priority: P1)

Como usuário, quero que labels, botões e títulos comecem no conteúdo visível,
sem caracteres invisíveis usados como mecanismo de layout.

**Independent Test**: construir a janela real com fakes offscreen, percorrer
as páginas e rejeitar texto visível com whitespace inicial ou sequências
artificiais de espaços, além de auditar os literais conhecidos no código.

### User Story 2 — Playback estável (Priority: P1)

Como usuário, quero que os botões de macro continuem alternando entre `Play` e
`Cancel` pelo estado real do playback, mesmo depois da limpeza do texto.

**Independent Test**: renderizar uma macro com fake de serviço, sincronizar os
estados parado/em execução e verificar os rótulos dos botões.

## Acceptance Scenarios

1. **Given** uma label, botão, título ou status de uma página, **When** ela é
   renderizada, **Then** seu conteúdo não começa com whitespace de apresentação
   nem contém sequências artificiais de espaços.
2. **Given** os nomes de preset, macro, perfil e configuração, **When** são
   exibidos, **Then** o conteúdo semântico permanece igual, sem padding textual.
3. **Given** uma macro salva, **When** o playback está parado ou em execução,
   **Then** cada botão correspondente exibe exatamente `Play` ou `Cancel` e a
   ação continua sincronizada com o estado real.
4. **Given** a janela desktop ou pequena, **When** as páginas são capturadas,
   **Then** o layout usa os espaçamentos dos widgets, sem depender de
   whitespace invisível no texto.

## Requirements

### Functional Requirements

- **FR-001**: Labels, botões, títulos de grupos, status e título da janela MUST
  remover whitespace prefixado usado para apresentação.
- **FR-002**: Copy visível MUST não conter sequências artificiais de múltiplos
  espaços; separadores textuais devem usar espaçamento simples ou layout.
- **FR-003**: A limpeza MUST preservar o conteúdo semântico e a persistência de
  DPI, macros, perfis e configurações.
- **FR-004**: A sincronização de playback MUST comparar e escrever os estados
  limpos `Play` e `Cancel`, sem regressão funcional.
- **FR-005**: O teste MUST auditar texto renderizado com fakes e proteger os
  pontos conhecidos no código-fonte.
- **FR-006**: Screenshots de DPI, Macros, Perfis e Configurações MUST ser
  regeneradas nas variantes desktop, pequena e preview quando alteradas.
- **FR-007**: A documentação não MUST alterar ou declarar requisitos de ícones;
  esta feature trata somente de whitespace e layout textual.

## Scope

Inclui strings visíveis em `app/mouse_hub_app.py`: presets de DPI, controles e
status de Macros, metadados de Perfis, grupos/status de Configurações, título
da janela e separadores de copy afetados. Não inclui redesenho de componentes,
troca de ícones/emoji, mudança de fonte ou alteração de lógica de hardware.
Um espaço único exigido pela API de unidade de um `QSpinBox` pode permanecer
como separador entre número e sufixo.

## Edge Cases

- O nome de uma macro/perfil pode conter espaços internos legítimos; somente
  padding textual introduzido pela UI é proibido.
- Textos multilinha devem começar diretamente no conteúdo, sem recuo manual em
  cada linha.
- `Play` e `Cancel` são valores de estado e não devem depender de um espaço
  para serem encontrados pelo código.
- Espaços simples ao redor de um separador podem permanecer quando fazem parte
  da copy, mas não podem ser repetidos como padding visual.

## Success Criteria

- Nenhum texto visível auditado começa com whitespace de apresentação.
- Nenhum texto conhecido de preset, macro, perfil ou configuração contém
  padding textual ou múltiplos espaços artificiais.
- Os botões de playback continuam sincronizados com `stopped` e `running`.
- Teste dedicado, suíte existente, smoke UI e screenshots passam.
- CI verde no PR.

## Key Entities

- Copy visível de `QLabel`, `QPushButton`, `QGroupBox` e título da janela.
- Estados de playback `Play` e `Cancel`.
- Layouts Qt responsáveis por margins e spacing, em vez de padding textual.

## Review & Acceptance Checklist

- [ ] Whitespace de apresentação removido.
- [ ] Conteúdo semântico e estados Play/Cancel preservados.
- [ ] Testes offscreen cobrem runtime e fonte.
- [ ] Screenshots atualizadas/verificadas.
- [ ] CI verde.
