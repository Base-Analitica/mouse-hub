# Research: Empty state de Macros

**Feature**: [spec.md](./spec.md)
**Issue**: #105
**Data**: 2026-08-29

## Decision 1: Ajustar somente o ramo vazio da lista

- **Decision**: Manter a hierarquia atual da página e ajustar o estado vazio para
  iniciar no topo da região de lista, com padding vertical intencionalmente menor.
- **Rationale**: O problema observado é de posicionamento e densidade visual. O
  código já separa explicitamente o caso `not macros`, portanto não é necessário
  alterar o core, o store ou o fluxo de gravação.
- **Alternatives considered**: Novo card, novo CTA, remoção da área de rolagem ou
  refatoração geral da página. Essas opções ampliam o escopo e podem quebrar a
  relação com o card `Gravar Macro`.

## Decision 2: Provar o contrato por posição relativa

- **Decision**: Os testes comparam a geometria da mensagem à região de lista e
  verificam alinhamento superior, sem fixar coordenadas absolutas da janela.
- **Rationale**: O contrato precisa resistir aos tamanhos 1050×680 e 760×560 e às
  diferenças de fonte do ambiente de testes.
- **Alternatives considered**: Teste somente por screenshot ou coordenadas fixas.
  Ambos são menos diagnósticos e mais frágeis para uma regressão de layout.

## Decision 3: Fake de lista sem hardware

- **Decision**: O teste instancia a página real com um fake de `list_all()` que
  alterna entre vazio e uma macro conhecida.
- **Rationale**: Isso cobre a renderização real e a transição sem exigir mouse,
  X11 real, persistência ou qualquer nova dependência.
- **Alternatives considered**: Instanciar `MouseHubApp` completo ou substituir
  widgets por mocks. Essas opções adicionam ruído ou deixam de provar o layout
  efetivamente construído.

## Decision 4: Evidência visual gerada pelo pipeline existente

- **Decision**: Regenerar as imagens pelo `scripts/capture_screenshots.py`, sem
  edição manual ou nova ferramenta.
- **Rationale**: O pipeline já usa fakes determinísticos e produz as variantes
  desktop, small e preview usadas pela documentação.
- **Alternatives considered**: Capturas manuais ou deixar os arquivos antigos.
  Isso perderia reprodutibilidade ou manteria documentação divergente.
