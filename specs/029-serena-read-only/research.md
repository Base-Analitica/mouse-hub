# Research: configuração Serena read-only

## Evidência observada

- `.serena/project.yml` já possui a chave documentada `read_only` na linha 148, atualmente com valor `false`.
- `scripts/agent/semantic-code.py` se descreve como ponte read-only e expõe somente os subcomandos `tools`, `overview`, `find`, `refs` e `diagnostics`.
- O launcher `scripts/agent/semantic-code` executa a ponte no venv local da Serena e não recebe argumentos de edição próprios.
- A configuração `read_only: true` é suportada pelo schema documentado no próprio arquivo.

## Decisão

Trocar somente o valor booleano para `true`. Não alterar a ponte, o runtime do Mouse Hub, os modos ou a lista implícita de ferramentas.

## Riscos e mitigação

| Risco | Mitigação |
| --- | --- |
| Serena rejeitar a configuração | teste de valor booleano e handshake real quando instalada |
| consultas deixarem de funcionar | preservar os subcomandos e executar `tools`/consultas |
| mudança contaminar o produto | teste de caminhos do diff e suíte completa |
| ambiente não possuir Serena | separar falha de instalação de sucesso de configuração |

## Fora de escopo

- `app/`, `mouse_hub/`, `.github/`, launchers e packaging do Mouse Hub.
- Adição de comandos de edição ou alteração da ponte semântica.
