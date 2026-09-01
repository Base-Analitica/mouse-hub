# Implementation Plan: Labels persistentes no formulário de Perfis

**Branch**: `fix/persistent-profile-field-labels-v2`
**Spec**: `specs/015-persistent-profile-field-labels/spec.md`
**Issue**: #114
**Status**: Em implementação

## Technical Context

- **Aplicação**: Python + PyQt5 5.15.11.
- **Superfície**: `ProfilesPage._build` em `app/mouse_hub_app.py`.
- **Layout atual**: `QGridLayout` com nome, DPI, Sensibilidade e ações em duas
  colunas, dentro do `QScrollArea` preparado pela correção da issue #100.
- **Problema**: os controles usam placeholder ou sufixo, que não permanece como
  identificação independente quando o usuário preenche os campos.
- **Teste**: Qt offscreen, `ProfileStore` em diretório temporário e
  `MouseController` sem hardware. Nenhuma operação física é necessária.
- **Dependência**: PR #134, baseado em `fix/profiles-responsive-grid`, deve ser
  integrado antes deste PR. Não duplicar a alteração de sizing no alvo `main`.
- **Dependências novas**: nenhuma.

## Problem and Goals

O formulário de Perfis precisa comunicar claramente qual valor cada controle
representa em todos os estados. O objetivo é adicionar labels persistentes e
associá-los semanticamente aos controles, sem alterar domínio, persistência ou
serviços.

Goals:

1. Exibir `Nome do perfil`, `DPI` e `Sensibilidade` como labels permanentes.
2. Associar cada label ao controle por buddy e nome acessível correspondente.
3. Manter `DPI` e `%` como unidades complementares dos spinboxes.
4. Preservar o layout de duas colunas e a rolagem vertical do PR #134.
5. Provar a mudança com teste dedicado, screenshots e CI.

## Design

### 1. Labels e associação semântica

Criar `name_label`, `dpi_label` e `sens_label` como `QLabel` nomeados na página.
Cada label recebe `setBuddy` para o respectivo input. Os três controles também
recebem `setAccessibleName` com o texto humano correspondente, sem introduzir
biblioteca ou abstração nova.

### 2. Grid responsivo

Manter o nome ocupando as duas colunas. Posicionar o label do nome em uma linha
própria e seu controle na linha seguinte. Posicionar os labels de DPI e
Sensibilidade na mesma linha, seguidos pelos spinboxes. Manter os botões na
última linha. Assim, os labels permanecem acima dos campos e o layout continua
compatível com a largura small e com o `QScrollArea` vertical existente.

### 3. Preservar domínio e comportamento

Não alterar `ProfileStore`, constantes de DPI/Sensibilidade, aplicação de
perfil, validação, tratamento de configuração corrompida ou ações dos botões.
O `ProfileStore` continua sendo a fonte de verdade, e a UI apenas apresenta os
controles existentes.

### 4. Teste first e prova visual

- Criar teste dedicado antes da implementação e confirmar RED pela ausência dos
  labels públicos.
- Implementar somente os labels, associações, nomes acessíveis e linhas do grid.
- Confirmar GREEN com os campos preenchidos, nas larguras 562 e 862.
- Executar o capturador oficial e conferir apenas `5_perfis.png`,
  `small_perfis.png` e previews realmente derivados.

## Constitution Compliance

| Princípio | Aplicação nesta mudança | Evidência planejada |
|---|---|---|
| I. Correção de Hardware em Primeiro Lugar | Nenhuma operação de hardware é alterada; o trabalho é exclusivamente de UI. | Regressões de Perfis e suíte completa continuam passando. |
| II. Honestidade de Estado | Labels esclarecem o significado dos valores sem transformar UI em fonte de verdade. | Teste de texto, preenchimento e associação. |
| III. Fakes no CI, Hardware Fora | A página é testada com `MouseController` sem dispositivo e `ProfileStore` temporário. | `tests/test_issue114_profiles_field_labels.py` em Qt offscreen. |
| IV. Regressão Com Teste Junto do Fix | O teste é escrito e executado antes do código, com RED confirmado. | Execuções RED e GREEN registradas nas tarefas. |
| V. Regras de Domínio Somente no Core | Nenhum limite, regra de perfil ou serviço é movido para a UI. | Diff restrito a apresentação e teste. |
| VI. Menor Mudança Completa | Reutiliza widgets e layout existentes, sem dependência nova ou refatoração. | Revisão do diff e `git diff --check`. |
| VII. Verificação Dupla | Checks locais e remotos provam software, não hardware físico. | Suíte, smoke, pacote e workflow do PR. |
| VIII. UX Honesta e Consistente | Textos pt-BR persistem, unidades continuam complementares e conteúdo small rola. | Testes de labels e screenshots. |

## Risks and Mitigations

- **Risco**: mais linhas tornam o conteúdo maior que a viewport small.
  **Mitigação**: o wrapper da issue #100 já fornece rolagem vertical e o teste
  verifica que os widgets ficam dentro da página.
- **Risco**: labels estreitos ou cortados no desktop.
  **Mitigação**: usar as duas colunas existentes e testar larguras small/desktop.
- **Risco**: duplicar o fix de sizing do PR #134.
  **Mitigação**: manter esta branch baseada no PR #134 e declarar a dependência
  no PR, sem reimplementar a correção.
- **Risco**: tratar unidade como label e remover contexto semântico.
  **Mitigação**: labels explícitos e sufixos preservados simultaneamente.

## Verification Plan

### Local

1. `QT_QPA_PLATFORM=offscreen python3 -m pytest tests/test_issue114_profiles_field_labels.py -q` em RED antes da implementação.
2. O mesmo teste em GREEN depois da implementação.
3. Teste focado de #114, #100 e regressões de Perfis.
4. `QT_QPA_PLATFORM=offscreen python3 -m pytest tests/ -q`.
5. `QT_QPA_PLATFORM=offscreen xvfb-run -a python3 -m unittest tests.smoke_ui_init`.
6. `python3 -m compileall -q mouse_hub tests app` e `git diff --check`.
7. `QT_QPA_PLATFORM=offscreen python3 scripts/capture_screenshots.py`.

### Remote

1. Revisar diff, forçar `.specify/feature.json` e criar commit convencional.
2. Push da branch e PR #114 com base em `fix/profiles-responsive-grid`.
3. Aguardar lint/testes determinísticos, pacote `.deb` e smoke Xvfb.
4. Registrar o workflow real na spec e manter o PR aberto para o mantenedor.

## Rollback

Reverter o commit do PR remove os labels e restaura o formulário anterior. Não
há migração, alteração de dados ou mudança de protocolo.
