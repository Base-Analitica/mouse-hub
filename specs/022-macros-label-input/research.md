# Research: Label visual do nome da macro

## Contexto observado

`MacrosPage._build()` cria `QLabel("Nome da macro:")` e, logo abaixo,
`QLineEdit("minha_macro")`. O campo recebe estilo explícito de input, mas o
label não recebe estilo próprio. A issue #104 registra que a composição é
interpretada como dois inputs empilhados.

## Decisão

Manter o texto e o layout existentes e aplicar ao label um stylesheet explícito
com tokens já disponíveis:

- `COLORS["text_secondary"]` para texto de formulário legível;
- `TYPE_SCALE["body"]` para o tamanho padrão;
- `background: transparent` e `padding: 0`;
- nenhum `border` ou raio.

## Alternativas rejeitadas

1. Remover o label e usar placeholder no campo: perde contexto quando o campo
   recebe foco ou valor.
2. Alterar o texto para um placeholder: mantém a ambiguidade e mistura
   instrução com valor editável.
3. Criar um componente de formulário novo: seria uma abstração sem necessidade
   para uma correção de um único label.

## Verificação

O teste runtime deve exigir a transparência explícita e a existência de um único
`QLineEdit` nos dois viewports oficiais. O teste deve falhar no estado atual
porque o label tem stylesheet vazio, antes da alteração de produção.
