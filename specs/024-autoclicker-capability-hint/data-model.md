# Data Model: Hint de capacidade do Auto-Clicker visível

## Domínio

Nenhuma entidade de domínio nova é introduzida. A feature somente expõe na UI um estado já existente.

## Elementos observáveis

| Elemento | Tipo | Entrada | Saída | Invariante |
|---|---|---|---|---|
| `CapabilityState` | estado imutável de capabilities | `is_available` e `reason_for` | provider da página | continua sendo a fonte única |
| `caps_hint` | `QLabel` existente | estado de `CapabilityState` | texto/colorização no layout | existe uma única instância no layout |
| `mc_status` | `QLabel` existente | estado do serviço de janela | contexto de foco/detecção | não é usado como causa de capability |
| controles do Auto-Clicker | widgets existentes | disponibilidade booleana | enabled/disabled | gating não muda |

## Transições

```text
CapabilityState indisponível
  -> _sync_caps()
  -> caps_hint = causa real + controles desabilitados

CapabilityState disponível
  -> _sync_caps()
  -> caps_hint = indicação disponível + controles habilitados
```

A mudança de estado atualiza o mesmo label. Não há persistência, cache novo ou evento adicional.

## Contratos

- `caps_provider()` pode continuar ausente (`None`), preservando o comportamento existente.
- Quando presente, o provider deve expor `is_available("autoclick_available")` e `reason_for(...)`, como já exige o fluxo atual.
- A feature não altera a forma ou o conteúdo do `CapabilityState`.
