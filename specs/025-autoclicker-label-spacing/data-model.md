# Data Model: Espaçamento semântico dos botões do Auto-Clicker

## Resultado

Não existe mudança de modelo de dados. O issue corrige apenas a projeção de nomes já existentes em widgets PyQt5.

## Elementos observáveis

| Elemento | Origem | Tipo | Contrato |
|---|---|---|---|
| Nome `Esquerdo` | literal de UI já existente | `str` | texto exato do botão de código 1 |
| Nome `Meio` | literal de UI já existente | `str` | texto exato do botão de código 2 |
| Nome `Direito` | literal de UI já existente | `str` | texto exato do botão de código 3 |
| `btn_buttons` | `AutoClickerPage` | `list[tuple[QPushButton, int]]` | três widgets ordenados com códigos 1, 2 e 3 |
| `ac.button` | controlador | `int` | seleção ativa usada pelo estilo e pelo motor |

## Invariantes

1. A ordem dos widgets é esquerda, meio, direita.
2. Cada texto corresponde ao nome sem whitespace artificial.
3. O código inteiro associado não muda quando o texto é limpo.
4. O estilo ativo continua derivado de `ac.button`.
5. Nenhum estado é persistido ou criado por esta correção.

## Fluxo

```text
nome de UI -> QPushButton.text()
                         |
                         +-> clique -> _set_button(código)
                                          |
                                          +-> ac.button e estilos
```

A capacidade do ambiente continua sendo consumida separadamente por `_sync_caps()`. Ela não é derivada do texto dos botões.
