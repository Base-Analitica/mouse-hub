# Data Model: configuração Serena read-only

Esta feature não cria entidades persistentes nem altera o modelo de domínio do Mouse Hub.

## Configuração

### `read_only`

- Arquivo: `.serena/project.yml`.
- Tipo: booleano YAML.
- Valor esperado: `true`.
- Efeito: desabilita ferramentas de edição da Serena neste projeto.

## Ponte semântica preservada

- `scripts/agent/semantic-code.py` continua oferecendo `tools`, `overview`, `find`, `refs` e `diagnostics`.
- `scripts/agent/semantic-code` continua apontando para o venv local.
- Nenhum estado de hardware, configuração de usuário ou dado do produto é alterado.
