# Especificação: copy acentuada na página de Perfis

**Issue:** #97
**Título:** [P3][UX] Corrigir textos sem acentuação na página de Perfis
**Status:** Implementação local concluída, entrega em validação
**Feature directory:** `specs/030-profile-copy-accents`

## Contexto

A `ProfilesPage` ainda exibe mensagens em português sem diacríticos e com concordância editorial inconsistente. Os textos aparecem nos estados de erro de leitura da configuração, falha de aplicação e falha ou sucesso de persistência do perfil. A inconsistência é visível ao usuário e contrasta com o restante da interface.

## Objetivo

Corrigir somente a copy visível da `ProfilesPage`, preservando exatamente a lógica de erro, os resultados confirmados, as chaves persistidas e o fluxo de mutação. A página deve apresentar português brasileiro consistente nos estados de leitura, aplicação e salvamento.

## Escopo

### Incluído

- Corrigir `Não`, `possível`, `configuração` e `NÃO` nas mensagens visíveis existentes.
- Preservar placeholders, nomes de perfil, mensagens de exceção e a semântica dos estados.
- Atualizar assertions que comparam as strings de usuário.
- Adicionar regressão cobrindo erro de leitura, falha de aplicação e falha de persistência, além da mensagem de sucesso.
- Regenerar as capturas oficiais afetadas pela mudança de copy.

### Não incluído

- Alterações em `mouse_hub/core/`, serviços de hardware, persistência ou chaves de configuração.
- Alterações em códigos de erro, resultados, controle de widgets ou fluxo de aplicação.
- Tradução de comentários, docstrings ou mensagens internas que não são exibidas ao usuário.
- Refatoração da `ProfilesPage` ou mudanças de layout não exigidas pela issue.

## Requisitos funcionais

- **FR-001:** O erro de leitura deve informar `Não foi possível ler os perfis`.
- **FR-002:** A confirmação de que o arquivo não foi alterado deve usar `O arquivo de configuração NÃO foi alterado.`.
- **FR-003:** A falha total de aplicação deve usar `Perfil '%s' NÃO aplicado`, mantendo os detalhes das duas falhas.
- **FR-004:** A falha de salvamento deve usar `Não foi possível salvar o perfil '%s'`, mantendo a mensagem de causa.
- **FR-005:** O sucesso de salvamento deve usar `Perfil '%s' salvo na configuração.`.
- **FR-006:** Mensagens de aplicação parcial, estados, placeholders e pontuação já consistente devem permanecer semanticamente inalterados.
- **FR-007:** Nenhuma lógica de domínio, chave persistida, código, comentário ou docstring deve ser alterada por esta correção de copy.
- **FR-008:** Os testes devem cobrir os estados de leitura, aplicação parcial/falha e persistência sem enfraquecer assertions existentes.

## Critérios de aceitação

- **SC-001:** Nenhuma das quatro formas sem acentuação permanece nas strings visíveis de `ProfilesPage`.
- **SC-002:** O estado de configuração corrompida ou ilegível continua visível, desabilita o formulário e não sobrescreve o arquivo.
- **SC-003:** Falha total e aplicação parcial continuam distinguíveis e não se tornam sucesso por causa da troca de texto.
- **SC-004:** Falha de salvamento continua sendo exibida como falha, e sucesso continua sendo exibido somente após resultado bem-sucedido.
- **SC-005:** Testes focados e regressões existentes passam, incluindo os cenários de aplicação pelos serviços reais com fakes.
- **SC-006:** As capturas oficiais `5_perfis.png`, `small_perfis.png` e `preview.png` refletem a copy corrigida e são reproduzíveis byte a byte.
- **SC-007:** Sintaxe, smoke da UI e pacote `.deb` passam. O diff de produção permanece limitado à copy prevista.
- **SC-008:** O PR referencia #97, possui os três checks reais verdes e permanece aberto, sem merge.

## Cenários

### Erro de leitura

Dado um `ProfileStore` com configuração corrompida ou ilegível, quando a página carrega, então mostra as mensagens acentuadas de leitura e integridade, mantém o arquivo intacto e desabilita o formulário.

### Aplicação parcial ou falha total

Dado um estado com serviços fakeáveis, quando DPI e sensibilidade são aplicados, então os estados parcial, sucesso e falha continuam usando a mesma semântica. Na falha total, o feedback contém `NÃO aplicado` e as causas originais.

### Persistência

Quando o salvamento falha, o feedback contém `Não foi possível salvar` e não afirma sucesso. Quando o salvamento é confirmado, o feedback contém `salvo na configuração.` e o perfil permanece persistido.

## Observabilidade e honestidade

A mudança é exclusivamente editorial. Nenhuma mensagem nova deve ocultar uma falha de hardware, de sistema ou de configuração. As validações locais serão identificadas como evidência de software, e o CI remoto será reportado separadamente.
