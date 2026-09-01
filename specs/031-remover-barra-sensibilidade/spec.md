# Especificação: remover a barra decorativa de Sensibilidade

**Issue:** #91  
**Título:** [P2][UI] Remover a barra decorativa sem estado da tela de Sensibilidade  
**Status:** Implementação local em validação  
**Feature directory:** `specs/031-remover-barra-sensibilidade`

## Contexto

A `SensitivityPage` renderiza um `QFrame` horizontal chamado `speedBar` depois
 do slider e das labels `Lento`/`Rápido`. Esse frame tem aparência de barra de
progresso, mas nunca é atualizado, não tem preenchimento e não representa o
valor confirmado pelo sistema. Ele ocupa espaço e pode ser interpretado como
uma segunda fonte de verdade.

A issue pede remover esse elemento ou transformá-lo em um indicador real sem
duplicar o slider. Como o slider já é o controle primário e a barra não possui
estado verificável, a menor mudança completa é removê-la.

## Objetivo

Eliminar o `speedBar` estático sem alterar o slider de sensibilidade, a leitura e
a aplicação do estado do sistema, o gating por capacidade, a seção de polling ou
qualquer regra de hardware e domínio.

## Cenários de usuário e testes

### História 1: Sensibilidade sem indicador duplicado (P1)

O usuário abre a página de Sensibilidade em uma janela desktop ou small. Ele vê
o valor confirmado, o slider e as labels de orientação, mas não vê uma segunda
barra com aparência de indicador desconectado.

**Teste independente:** construir `SensitivityPage` offscreen com as fakes do
projeto e verificar que não existe `QFrame#speedBar`, que o slider continua sendo
um `QSlider` horizontal com faixa 0–100 e que `Lento`/`Rápido` continuam no layout.

**Cenários de aceite:**

1. **Dado** o layout desktop, **quando** a página é construída, **então** o
   `speedBar` não existe e o slider permanece utilizável conforme sua capacidade.
2. **Dado** o layout small, **quando** a página é construída, **então** o
   resultado não introduz barra residual, clipping ou erro de construção.
3. **Dado** um estado conhecido ou desconhecido, **quando** a página é construída,
   **então** o valor e o estado do sistema continuam sendo renderizados pelas
   mesmas fontes, sem indicador visual falso.

### História 2: Material visual atualizado (P2)

As capturas públicas da Sensibilidade devem refletir a remoção da barra em
`2_sens.png`, `small_sens.png` e `preview.png`, mantendo as dimensões oficiais e
sem alterações não relacionadas.

**Teste independente:** executar o capturador oficial duas vezes e comparar as
imagens geradas com as versões esperadas, verificando dimensões e bytes.

## Casos de borda

- Se o dispositivo ou a capacidade de sensibilidade não estiver disponível, o
  estado existente continua sendo exibido e o slider continua seguindo o gating
  já implementado. A remoção da barra não pode fabricar disponibilidade.
- Se a janela for small, o layout pode ficar mais curto, mas nenhum widget do
  polling ou do estado do sistema pode ser removido por engano.
- Alterações futuras de estado não devem reintroduzir um indicador decorativo
  sem contrato de atualização verificável.

## Requisitos funcionais

- **FR-001:** `SensitivityPage` MUST deixar de criar e adicionar o widget
  `QFrame#speedBar` estático.
- **FR-002:** O slider de sensibilidade MUST permanecer horizontal, com mínimo 0,
  máximo 100 e os mesmos sinais e callbacks de preview/commit.
- **FR-003:** As labels `Lento` e `Rápido`, o valor exibido, o estado do sistema,
  o `caps_hint` e o gating existente MUST permanecer semanticamente inalterados.
- **FR-004:** A seção de polling rate e suas mensagens MUST continuar presentes e
  com os mesmos estados, sem alteração de lógica de domínio.
- **FR-005:** Nenhum arquivo em `mouse_hub/core/` ou `mouse_hub/platform/` pode
  ser alterado por esta feature.
- **FR-006:** A correção MUST incluir teste offscreen que falhe enquanto o
  `speedBar` existir e confirme a preservação do slider e do layout essencial.
- **FR-007:** As capturas oficiais MUST ser regeneradas, mantendo dimensões
  1050×680, 760×560 e 2130×2770 e registrando as diferenças esperadas.
- **FR-008:** Suíte completa, smoke Xvfb, `compileall`, `git diff --check`, pacote
  `.deb`, revisão independente e os três checks reais do CI MUST passar.

## Critérios de aceite

- **SC-001:** Não existe `QFrame#speedBar` nem stylesheet residual do indicador.
- **SC-002:** O slider continua sendo o único controle visual de sensibilidade e
  conserva faixa, orientação, sinais e gating.
- **SC-003:** Labels, valor/estado do sistema, `caps_hint` e polling continuam
  renderizados nos dois viewports oficiais.
- **SC-004:** O diff de produção fica limitado à remoção do widget decorativo.
- **SC-005:** O teste dedicado falha no baseline e passa após a remoção, e as
  regressões existentes continuam passando.
- **SC-006:** As três capturas afetadas mostram a remoção, conservam dimensões
  oficiais e não têm alterações fora das regiões esperadas.
- **SC-007:** A suíte, smoke, compilação, diff check e pacote Debian passam.
- **SC-008:** O PR referencia #91, tem os três checks reais verdes, permanece
  aberto e não é mesclado pelo agente.

## Limites

Incluído: remoção do frame estático, teste de regressão, capturas e artefatos
Spec Kit. Não incluído: criar outro indicador, alterar o modelo de sensibilidade,
modificar HID++, refatorar a página ou alterar o polling rate.

## Observabilidade e honestidade

Esta é uma mudança visual. Os testes offscreen provam o comportamento do código e
do layout sob fakes, não a medição física do G403. Nenhum resultado será descrito
como validação de hardware real.
