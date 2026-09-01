# Feature Specification: Status de Macros orientado à tarefa

**Feature Branch**: `fix/macros-user-facing-status`
**Created**: 2026-08-29
**Status**: Convergido localmente; aguardando PR/CI
**Input**: Issue #113: o status de Macros expõe o backend `X11/XRecord` ao usuário final.

## User Scenarios & Testing

### User Story 1 - Entender disponibilidade de gravação (Priority: P1)

Como usuário da página Macros, quero saber se posso gravar uma macro sem
precisar conhecer o backend gráfico usado pela aplicação.

**Why this priority**: A mensagem operacional é o primeiro feedback da página e
precisa orientar a tarefa, não funcionar como diagnóstico de implementação.

**Independent Test**: Renderizar `MacrosPage` com a capacidade disponível e
indisponível e verificar copy curta, clara e sem nomes de backend.

**Acceptance Scenarios**:

1. **Given** a captura está disponível, **When** a página sincroniza capacidades,
   **Then** mostra “Gravação de macros disponível” sem `X11`, `XRecord` ou API.
2. **Given** a captura está indisponível por falta de sessão gráfica, **When** a
   página sincroniza capacidades, **Then** mostra indisponibilidade e a
   consequência para o usuário sem expor o backend.

---

### User Story 2 - Receber feedback operacional legível (Priority: P2)

Como usuário que inicia ou não consegue iniciar uma gravação, quero mensagens
que descrevam a ação e o próximo passo em linguagem de produto.

**Why this priority**: Mensagens de progresso e falha também são superfície
normal da página e não devem reintroduzir o jargão removido do status.

**Independent Test**: Exercitar o início de gravação fake com sucesso e falha
que contenha o erro técnico `XRecord`, verificando a mensagem final exibida.

**Acceptance Scenarios**:

1. **Given** o usuário clica para gravar, **When** o handshake está em andamento,
   **Then** o status diz que a gravação está iniciando e aguarda a sessão
   gráfica, sem citar o backend.
2. **Given** o backend falha com uma mensagem técnica, **When** a operação
   termina, **Then** a UI explica que a gravação não pôde iniciar e a necessidade
   relevante sem repetir o nome interno.

## Edge Cases

- Uma causa de indisponibilidade que não seja a ausência de sessão gráfica deve
  continuar visível quando já for uma mensagem adequada, mas nomes de backend
  não podem escapar para a superfície operacional.
- A copy disponível e indisponível deve caber em desktop e 760×560 sem alterar
  os controles ou o fluxo de gravação.
- Logs, docstrings e diagnóstico interno podem continuar usando nomes técnicos;
  esta especificação cobre textos apresentados na página Macros.

## Requirements

### Functional Requirements

- **FR-001**: O status de capacidade disponível MUST comunicar somente que a
  gravação de macros está disponível, sem nome de backend.
- **FR-002**: O status de capacidade indisponível MUST comunicar a consequência
  para o usuário e não MUST expor `X11`, `XRecord`, `XTest` ou outro detalhe de
  implementação na mensagem operacional normal.
- **FR-003**: Mensagens de início, sucesso e falha exibidas por `MacrosPage` MUST
  seguir a mesma copy orientada à tarefa.
- **FR-004**: A disponibilidade real, o gating dos controles e a causa interna
  MUST permanecerem inalterados no core e no modelo de capacidades.
- **FR-005**: O texto deve caber nas capturas desktop e 760×560 sem refatoração
  de layout ou dependência nova.
- **FR-006**: Testes determinísticos MUST cobrir capacidade disponível, ausência
  de sessão gráfica e falha operacional com erro técnico.

### Key Entities

- **Macro capture capability**: capacidade avaliada pelo modelo e consumida pela
  página para habilitar ou desabilitar gravação.
- **Operational status**: texto visível que orienta o usuário, distinto do
  motivo técnico usado para diagnóstico.

## Success Criteria

### Measurable Outcomes

- **SC-001**: Nenhum texto operacional renderizado por `MacrosPage` contém
  `X11`, `XRecord`, `XTest` ou nome de backend.
- **SC-002**: Estados disponível e indisponível permanecem distinguíveis e
  explicam a ação ou consequência em uma linha curta.
- **SC-003**: Os fluxos fake de início, falha e cancelamento continuam passando;
  a falha técnica é apresentada sem jargão interno.
- **SC-004**: Capturas desktop e 760×560 são atualizadas, e os três checks reais
  do CI passam no commit final.

## Assumptions

- A capacidade `macro_capture_available` continua sendo a fonte de verdade e
  não será inferida pela UI.
- O detalhe técnico permanece disponível em logs, diagnóstico ou Informações do
  Sistema quando necessário, sem ser copiado para o status operacional.
- O PR será baseado em `main`; não depende dos PRs visuais ainda não integrados.
- A validação local usa fakes e não prova uma sessão X11 real.

## Out of Scope

- Alterar o backend de captura, X11, XRecord, XTest ou o serviço de automação.
- Alterar o modelo de capacidades ou a disponibilidade real da gravação.
- Padronizar copy de outras páginas fora do fluxo de Macros.
