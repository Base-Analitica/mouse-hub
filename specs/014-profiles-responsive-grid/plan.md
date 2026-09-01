# Implementation Plan: Grid responsivo da página de Perfis

**Branch**: `fix/profiles-responsive-grid`
**Spec**: `specs/014-profiles-responsive-grid/spec.md`
**Issue**: #100
**Status**: Concluído, CI verde

## Technical Context

- **Aplicação**: Python + PyQt5.
- **Superfície**: `ProfilesPage` em `app/mouse_hub_app.py`, envolvida pelo
  `QScrollArea` criado em `MouseHubApp._wrap_scrollable`.
- **Regressão observada**: após a transição desktop para 760×560, o widget da
  página é forçado à altura da viewport apesar de seu layout exigir mais
  espaço. O `QGridLayout` recebe uma altura menor que duas rows de 185 px,
  posiciona a segunda row sobre a primeira e deixa uma barra horizontal visível
  mesmo sem alcance horizontal.
- **Teste**: Qt offscreen, configuração `ProfileStore` isolada e fakes do
  capturador oficial. Nenhum hardware é necessário.
- **Dependências**: nenhuma nova.

## Problem and Goals

O container rolável atual não preserva a altura mínima do conteúdo de Perfis.
A correção deve permitir que o conteúdo seja maior que a viewport e role
verticalmente, em vez de comprimir a grade. A barra horizontal deve ser
explicitamente desabilitada porque os controles cabem na largura útil.

Goals:

1. Reservar a altura real do layout antes de o page widget ser colocado no
   `QScrollArea`.
2. Impedir que cards e formulário compartilhem a mesma região em 760×560.
3. Manter o reflow desktop e a largura útil dos cards.
4. Garantir uma regressão automatizada de geometria e scrollbar.
5. Regenerar somente `5_perfis.png` e `small_perfis.png`.

## Design

### 1. Preservar altura mínima do conteúdo

Em `MouseHubApp._wrap_scrollable`, depois que os labels recebem `wordWrap`,
ativar o layout e aplicar ao page widget a altura mínima calculada pelo layout.
A largura não será fixada, porque deve continuar acompanhando a viewport do
scroll. Dessa forma, quando o conteúdo for maior que a viewport, o
`QScrollArea` conserva a página alta e oferece rolagem vertical.

### 2. Remover scrollbar horizontal espúria

Configurar o `QScrollArea` com `Qt.ScrollBarAlwaysOff` para a barra horizontal.
A decisão é segura porque a largura mínima dos widgets de Perfis cabe na área
útil em 760×560 e o teste também verifica que nenhum card sai dos limites do
page widget.

### 3. Não alterar domínio nem comportamento

`ProfileStore`, quantidade de colunas, ações dos cards, formulário e serviços
de aplicação permanecem inalterados. O fix atua somente no sizing do container.

### 4. Teste first e screenshots

- Reproduzir o fluxo oficial desktop → small no teste novo.
- Confirmar RED com interseção entre cards e barra horizontal visível.
- Aplicar a alteração mínima no wrapper.
- Confirmar GREEN com cards separados, heading após a grade, controles no page
  e somente rolagem vertical.
- Capturar imagens oficiais e conferir os dois arquivos esperados.

## Constitution Compliance

| Princípio | Aplicação nesta mudança | Evidência planejada |
|---|---|---|
| I. Correção de Hardware em Primeiro Lugar | Nenhuma operação de hardware é alterada; o fix é exclusivamente de geometria. | Testes existentes de serviços continuam passando. |
| II. Honestidade de Estado | Nenhum conteúdo é escondido para simular que cabe; a página continua rolável. | Teste de separação e screenshot small. |
| III. Fakes no CI, Hardware Fora | O teste usa configuração isolada, fakes e Qt offscreen. | `tests/test_issue100_profiles_responsive.py`. |
| IV. Regressão Com Teste Junto do Fix | O teste falha no código anterior e passa com o sizing corrigido. | Execuções RED e GREEN registradas. |
| V. Regras de Domínio Somente no Core | Não há mudança de domínio, persistência ou regra de hardware. | Diff restrito ao wrapper e teste de UI. |
| VI. Menor Mudança Completa | Uma alteração no wrapper resolve a causa comum sem redesenhar Perfis. | Revisão do diff e `git diff --check`. |
| VII. Verificação Dupla | Checks locais e CI serão tratados como evidência de software, sem alegar hardware. | Suíte, smoke, pacote e workflow remoto. |
| VIII. UX Honesta e Consistente | Cards, ações e formulário permanecem legíveis em pt-BR sem overlap. | Geometria automatizada e screenshots. |

## Risks and Mitigations

- **Risco**: uma página diferente ficar alta demais no desktop.
  **Mitigação**: a altura mínima só aumenta o conteúdo quando o layout exige;
  desktop continua com viewport maior e a suíte completa cobre as outras telas.
- **Risco**: a largura mínima de algum widget criar corte horizontal.
  **Mitigação**: manter largura responsiva e testar bounds dos cards e controles;
  a barra horizontal é desligada somente com alcance máximo zero.
- **Risco**: o teste depender da configuração pessoal do desenvolvedor.
  **Mitigação**: patch de `ConfigPaths.xdg` para diretório temporário e perfil
  customizado criado pelo próprio teste.

## Verification Plan

### Local

1. `QT_QPA_PLATFORM=offscreen python3 -m pytest tests/test_issue100_profiles_responsive.py -q` em RED antes do fix.
2. O mesmo teste em GREEN após o fix.
3. Testes de Perfis existentes em `tests/test_issue6_profiles_polling.py`.
4. `QT_QPA_PLATFORM=offscreen python3 -m pytest tests/ -q`.
5. `QT_QPA_PLATFORM=offscreen xvfb-run -a python3 -m unittest tests.smoke_ui_init`.
6. `python3 -m compileall -q mouse_hub tests app` e `git diff --check`.
7. `QT_QPA_PLATFORM=offscreen python3 scripts/capture_screenshots.py`.

### Remote

1. Push de branch `fix/profiles-responsive-grid` e PR vinculado ao #100.
2. Aguardar lint/testes determinísticos, pacote `.deb` e smoke Xvfb.
3. Registrar workflow verde na spec e manter o PR aberto para o mantenedor.

## Verification Results (remote)

- Workflow `33253419583`: lint e testes determinísticos, pacote `.deb` e smoke
  da UI com Xvfb passaram.
- PR: [#134](https://github.com/Base-Analitica/mouse-hub/pull/134), aberto e
  não mergeado.

## Rollback

Reverter o commit do PR restaura o comportamento anterior. Não há migração,
alteração de dados ou mudança de protocolo.

## Verification Results (local)

- RED confirmado pelo teste dedicado: cards `minecraft` e `default` se
  intersectavam e a scrollbar horizontal estava visível.
- GREEN confirmado pelo mesmo teste após o fix, com quatro presets e um perfil
  customizado em configuração isolada.
- Suíte completa, smoke Xvfb, `compileall` e `git diff --check` passaram.
- O capturador oficial atualizou a prova small. `5_perfis.png` foi regenerada
  e permaneceu byte-identical, pois a alteração só afeta o conteúdo comprimido
  quando a viewport é pequena.
