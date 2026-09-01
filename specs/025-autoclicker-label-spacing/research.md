# Research: Espaçamento semântico dos botões do Auto-Clicker

## Contexto observado

`AutoClickerPage._build()` cria os três botões do seletor em `app/mouse_hub_app.py`. O loop recebe pares `(name, icon)`, mas cada `icon` é a string vazia. A construção atual `QPushButton(f"{icon}  {name}")` injeta dois espaços antes do nome, embora não exista ícone para ocupar esse espaço.

O mesmo bloco já define `btn_row.setSpacing(12)`, altura fixa de 44 px, estilo ativo/inativo e a conexão para `_set_button()`. O problema é exclusivamente a composição textual. O caminho de capacidade em `_sync_caps()` percorre a lista `btn_buttons`, portanto a lista e seus códigos precisam permanecer compatíveis.

## Decisão: usar somente o nome visível

- **Decision**: construir cada botão com o nome (`QPushButton(name)`) e remover a variável `icon` vazia do iterável do loop.
- **Rationale**: elimina a causa do whitespace fantasma, mantém o spacing no layout e não inventa uma metáfora visual ou dependência de fonte.
- **Alternatives considered**:
  - manter os espaços e ajustar alinhamento: rejeitado porque preserva o artefato invisível;
  - adicionar ícones vetoriais: rejeitado por ampliar o escopo de um issue P3 e exigir decisão visual separada;
  - alterar `setStyleSheet` ou padding: rejeitado porque o defeito nasce no texto e não no design do botão.

## Contratos preservados

- `btn_buttons` continua contendo `(widget, 1)`, `(widget, 2)` e `(widget, 3)`.
- `_set_button()` continua sendo o único caminho de atualização da escolha e dos estilos.
- `_sync_caps()` continua aplicando o gating aos mesmos widgets.
- O layout continua usando `setSpacing(12)` e a mesma altura.
- O Auto-Clicker continua sem depender de hardware real nos testes.

## Verificação planejada

O teste dedicado deve falhar no baseline porque os textos atuais começam com dois espaços. Depois da menor alteração, deve passar e também verificar estado ativo, clique, gating e geometria nos dois viewports. A captura oficial deve ser repetida duas vezes, comparando os três PNGs afetados e o preview.

## Escopo fora da feature

- Não alterar `CapabilityModel`, copy do hint, card de status, CPS, timer ou segurança.
- Não adicionar ícone, dependência, regra de domínio ou mudança em `mouse_hub/core/`.
- Não alegar validação física do G403 HERO ou de uma sessão X11 real.
