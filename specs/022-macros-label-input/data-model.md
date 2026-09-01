# Data Model: Label visual do nome da macro

Esta feature não introduz dados, persistência ou contrato de domínio.

## Elementos observáveis

| Elemento | Tipo existente | Papel | Invariante |
|---|---|---|---|
| `Nome da macro:` | `QLabel` | Instrução não editável | Não possui aparência de input. |
| `name_input` | `QLineEdit` | Entrada do nome | Mantém `minha_macro`, limite 32 e foco/habilitação atuais. |
| `record_btn` | `DangerButton` | CTA de gravação | Continua no mesmo fluxo e posição relativa. |

## Relações

- O label aparece imediatamente antes de `name_input` no layout vertical.
- Só `name_input` recebe a superfície global de `QLineEdit`.
- A alteração não modifica `AutomationService`, `MacroStore` ou capacidades.
