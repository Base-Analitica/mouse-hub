# Feature Specification: Serena em modo somente leitura

**Feature Branch**: `029-serena-read-only`
**Created**: 2026-08-30
**Status**: Spec ready; implementation pending
**Issue**: #63
**Input**: Alinhar a configuração Serena ao uso somente leitura já exposto pela ponte semântica do projeto.

## User Scenarios & Testing

### User Story 1 - Consultar o projeto sem habilitar edição semântica (Priority: P1)

Como agente ou mantenedor que usa a navegação semântica do projeto, quero que a Serena seja iniciada em modo somente leitura, para que consultas locais não possam editar arquivos por engano.

**Why this priority**: A configuração contradiz a ponte `semantic-code`, que é documentada como somente leitura. Corrigir essa contradição reduz o risco operacional sem alterar o produto.

**Independent Test**: Ler a configuração YAML e a ponte, confirmar `read_only: true`, confirmar que os comandos `tools`, `overview`, `find`, `refs` e `diagnostics` continuam registrados e executar a ponte quando a instalação local estiver disponível.

**Acceptance Scenarios**:

1. **Given** o projeto está configurado para a Serena, **When** a configuração é carregada, **Then** o modo `read_only` é verdadeiro.
2. **Given** a ponte semântica é chamada, **When** o agente solicita ferramentas ou consulta símbolos, **Then** os comandos de consulta continuam disponíveis e não há comando de edição exposto pela ponte.
3. **Given** o runtime do Mouse Hub é executado, **When** a configuração Serena muda, **Then** nenhum módulo de `app/`, `mouse_hub/` ou launcher do produto é alterado.

## Edge Cases

- A configuração deve conter um booleano YAML real, não a string `"true"`.
- A alteração não pode remover ou renomear os modos, ferramentas e caminhos usados pela ponte.
- Se a Serena não estiver instalada no ambiente de teste, os testes estáticos ainda devem validar o contrato; a execução real deve ser reportada como bloqueada, não simulada como sucesso.
- O modo somente leitura deve impedir ferramentas de edição sem bloquear consultas semânticas.

## Requirements

### Functional Requirements

- **FR-001**: `.serena/project.yml` MUST definir `read_only: true` como booleano YAML.
- **FR-002**: A configuração MUST preservar as opções de ferramentas e os comandos de consulta `tools`, `overview`, `find`, `refs` e `diagnostics` da ponte `scripts/agent/semantic-code.py`.
- **FR-003**: A ponte MUST continuar sem operações de escrita próprias e MUST apontar para o projeto local correto.
- **FR-004**: A mudança MUST ficar restrita à configuração Serena, testes e documentação Spec Kit; nenhum runtime do Mouse Hub deve ser alterado.
- **FR-005**: O projeto MUST manter sua suíte determinística, smoke e empacotamento funcionando após a alteração.

## Key Entities

- **Configuração Serena**: `.serena/project.yml`, que define o modo de operação do projeto sem persistência do produto.
- **Ponte semântica**: `scripts/agent/semantic-code.py` e seu launcher, que oferecem somente consultas ao agente.

## Success Criteria

- **SC-001**: O YAML contém `read_only` booleano igual a `true` e o teste dedicado passa.
- **SC-002**: Os cinco comandos de consulta da ponte continuam presentes no parser e o handshake de ferramentas passa quando Serena está instalada.
- **SC-003**: `git diff` não contém arquivos de `app/`, `mouse_hub/`, launchers ou packaging do produto.
- **SC-004**: A suíte completa, smoke Xvfb, compilação, diff check e pacote Debian passam.
- **SC-005**: Os artefatos Spec Kit registram RED/GREEN, resultados observados e as limitações de execução local.
- **SC-006**: O PR fica aberto com CI real verde e sem merge automático.

## Assumptions

- A versão fixada da Serena aceita a chave `read_only` já presente no schema de `.serena/project.yml`.
- As ferramentas de consulta listadas pela ponte continuam sendo fornecidas pelo contexto `oaicompat-agent`.
- A segurança do runtime do Mouse Hub não depende da configuração Serena.

## Scope Boundaries

- Não alterar `app/`, `mouse_hub/`, `.github/`, launchers, packaging ou dependências do produto.
- Não adicionar ferramentas semânticas de escrita.
- Não alterar o comportamento da ponte além do necessário para confirmar o contrato existente.

## Traceability

| Requisito | Verificação planejada |
| --- | --- |
| FR-001 / SC-001 | teste dedicado de parsing/valor booleano |
| FR-002 / SC-002 | teste do parser da ponte e handshake `tools` |
| FR-003 / SC-002 | inspeção da ponte, launcher e execução real quando disponível |
| FR-004 / SC-003 | diff de caminhos e testes de runtime inalterado |
| FR-005 / SC-004 | suíte, smoke, compileall, diff check e pacote |

## Open Decisions

Não há decisões de produto pendentes. A alteração proposta é:

```yaml
read_only: true
```
