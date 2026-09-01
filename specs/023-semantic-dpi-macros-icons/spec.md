# Feature Specification: Ícones sem metáforas de mídia para DPI e Macros

**Feature Branch**: `fix/semantic-dpi-macros-icons`

**Created**: 2026-08-29

**Status**: Aprovada para implementação

**Input**: Issue #111, `[P3][UI] Ícones de DPI e Macros usam metáforas visuais de mídia`

## User Scenarios & Testing

### User Story 1 - Identificar o controle de DPI (Priority: P1)

Quando a pessoa abre o Dashboard, a sidebar ou a página de DPI, o ícone de
DPI deve sugerir precisão, sensor ou foco, e não reprodução de mídia.

**Why this priority**: O ícone atual de fast-forward cria uma metáfora de
play/skip para uma função de configuração de hardware.

**Independent Test**: Construir os ícones sem hardware, verificar o mapeamento
para `focus-3-line` (U+ED4C), renderizar nos tamanhos de sidebar e heading e
confirmar pixels não transparentes.

**Acceptance Scenarios**:

1. **Given** a navegação ou a página de DPI, **When** o ícone é renderizado,
   **Then** ele é o glifo vetorial `focus-3-line` e não o fast-forward atual.
2. **Given** o ícone em 18 px ou 24 px, **When** a fonte embutida está
   disponível, **Then** o desenho permanece legível e não é substituído por
   tofu ou imagem vazia.

### User Story 2 - Identificar o controle de Macros (Priority: P1)

Quando a pessoa abre o Dashboard, a sidebar ou a página de Macros, o ícone de
Macros deve sugerir teclas e automação, e não uma filmstrip ou quadro de vídeo.

**Why this priority**: A filmstrip atual associa gravação de macros a vídeo,
sem representar as teclas que serão automatizadas.

**Independent Test**: Construir os ícones sem hardware, verificar o mapeamento
para `keyboard-line` (U+EE75), renderizar nos tamanhos de sidebar e heading e
confirmar pixels não transparentes.

**Acceptance Scenarios**:

1. **Given** a navegação ou a página de Macros, **When** o ícone é renderizado,
   **Then** ele é o glifo vetorial `keyboard-line` e não a filmstrip atual.
2. **Given** o ícone em 18 px ou 24 px, **When** a fonte embutida está
   disponível, **Then** o desenho permanece legível e não é substituído por
   tofu ou imagem vazia.

### User Story 3 - Preservar consistência e fallback (Priority: P2)

A alteração deve usar as chaves semânticas existentes, mantendo o mesmo ícone
entre sidebar e título de página e preservando o fallback para texto quando a
fonte não puder ser carregada.

**Why this priority**: A correção é visual e não deve alterar navegação,
capacidades, hardware ou a tolerância a uma fonte ausente.

**Independent Test**: Exercitar as chaves `dpi` e `macros` nos call sites reais,
forçar a indisponibilidade da fonte e executar o smoke da UI sem hardware.

**Acceptance Scenarios**:

1. **Given** os call sites da sidebar e dos headings, **When** a chave `dpi` ou
   `macros` é usada, **Then** ambos consomem a mesma entrada de `_CODEPOINTS`.
2. **Given** a fonte embutida ausente ou corrompida, **When** `icon()` ou
   `icon_label()` é chamado, **Then** a função retorna `None` sem derrubar a UI.
3. **Given** uma captura oficial em desktop, small e preview, **When** o
   material é regenerado, **Then** somente as superfícies afetadas exibem os
   novos ícones, sem emoji ou dependência nova.

## Edge Cases

- Se `remixicon-subset.ttf` não carregar, o fallback existente deve continuar
  retornando `None`; nenhum chamador pode assumir que sempre haverá um ícone.
- Um nome de ícone desconhecido deve continuar retornando `None`, sem usar um
  glypho arbitrário como substituto.
- O subset deve conter os dois novos codepoints e continuar contendo os
  codepoints usados pelas outras páginas.
- A mudança não deve alterar o texto, a ordem dos botões, o tamanho da janela,
  o estado de capacidades ou qualquer operação HID++.
- O teste e a captura devem funcionar com `QT_QPA_PLATFORM=offscreen`, sem
  mouse físico e sem sessão X11 real.

## Requirements

### Functional Requirements

- **FR-001**: O nome semântico `dpi` MUST mapear para `focus-3-line`, codepoint
  U+ED4C, no subset Remix embutido.
- **FR-002**: O nome semântico `macros` MUST mapear para `keyboard-line`,
  codepoint U+EE75, no subset Remix embutido.
- **FR-003**: Sidebar e heading de cada página MUST continuar usando a mesma
  chave semântica, sem duplicar codepoints nos call sites.
- **FR-004**: O subset TTF MUST conter U+ED4C e U+EE75, além dos glifos já
  usados pelo aplicativo.
- **FR-005**: `icon()` e `icon_label()` MUST manter o fallback `None` quando a
  fonte estiver indisponível ou o nome não for conhecido.
- **FR-006**: A implementação MUST não adicionar emoji, dependência de runtime,
  fonte completa ou lógica de hardware.
- **FR-007**: As screenshots oficiais de DPI e Macros, suas variantes small e o
  preview MUST ser regenerados no mesmo PR.
- **FR-008**: A mudança MUST preservar as dimensões e os tamanhos de renderização
  oficiais da aplicação, incluindo 18 px na sidebar e 24 px nos headings.

## Key Entities

Esta feature não introduz entidades de domínio, persistência ou dados novos.

| Elemento | Tipo existente | Papel | Invariante |
|---|---|---|---|
| `dpi` | Chave semântica | Identifica o ícone de DPI | Mapeia para U+ED4C em sidebar e heading |
| `macros` | Chave semântica | Identifica o ícone de Macros | Mapeia para U+EE75 em sidebar e heading |
| `remixicon-subset.ttf` | Asset de UI | Fornece glifos vetoriais embutidos | Contém os codepoints exigidos |

## Success Criteria

### Measurable Outcomes

- **SC-001**: Os dois mapeamentos deixam de usar U+F177 e U+ED21, e os testes
  verificam U+ED4C e U+EE75.
- **SC-002**: Os ícones DPI e Macros renderizam com pixels não transparentes em
  18 px e 24 px no ambiente offscreen.
- **SC-003**: A sidebar e os dois headings continuam iniciando sem erro quando
  a fonte é carregada e continuam em fallback seguro quando ela não é carregada.
- **SC-004**: A suíte determinística, o smoke Xvfb e o empacotamento do CI
  terminam com sucesso, sem hardware físico.
- **SC-005**: A captura oficial reproduz deterministicamente as imagens e
  altera somente `1_dpi.png`, `small_dpi.png`, `4_macros.png`,
  `small_macros.png` e `preview.png`.

## Assumptions

- O subset existente continua sendo a fonte de runtime e não será substituído
  pela fonte completa do qtawesome.
- A fonte local Remix Icon 2.5.0 será usada somente como insumo de geração do
  subset durante o desenvolvimento; ela não será adicionada como dependência.
- A API pública de `app.ui.icons` permanece inalterada.
- A validação física no Logitech G403 não é aplicável, porque a feature só muda
  assets e mapeamentos visuais.
