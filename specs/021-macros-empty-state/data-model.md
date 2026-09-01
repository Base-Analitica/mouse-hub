# Data Model: Estado visual da lista de Macros

**Feature**: [spec.md](./spec.md)

Esta feature não cria nem altera entidades persistidas. O documento descreve
somente o estado visual derivado dos dados existentes para orientar os testes.

## Macro List State

Representa o resultado de `list_all()` usado pela página de Macros.

| Campo conceitual | Tipo lógico | Regras |
|---|---|---|
| `macros` | conjunto ordenado de macros | Vazio seleciona o empty state; um ou mais itens selecionam a lista preenchida. |
| `is_empty` | booleano derivado | Verdadeiro somente quando não há macros. Não é persistido. |
| `items` | coleção de itens de macro | Cada item mantém nome, contagem, data e controles existentes. |

## Empty State Message

- Conteúdo: `Nenhuma macro gravada ainda.` e a orientação para usar `Gravar Macro`.
- Visibilidade: somente quando `is_empty` é verdadeiro.
- Posição: no início da região destinada aos itens, imediatamente após o heading
  `Macros Salvas`.
- Ações: nenhuma. A criação continua pertencendo ao CTA do card de gravação.

## Populated Macro Item

- Visibilidade: somente quando `is_empty` é falso.
- Conteúdo: nome, quantidade/data já exibidos e controles Play/Excluir existentes.
- Transição: substituir integralmente o empty state quando a lista deixa de estar
  vazia; não deixar widgets antigos.

## State Transitions

```text
lista vazia ── atualização com macro ──> lista preenchida
lista preenchida ── exclusão do último ──> lista vazia
lista vazia ── redimensionamento ──> lista vazia (mesma relação espacial)
```

A transição não altera o store, o engine, as operações de captura/reprodução ou
as capacidades da plataforma.
