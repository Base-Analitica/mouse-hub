# Serena em modo somente leitura: plano de implementação

**Branch**: `fix/serena-read-only-config` | **Date**: 2026-08-30 | **Spec**: [spec.md](spec.md)

**Goal**: Corrigir a única opção `read_only` de `.serena/project.yml` de `false` para `true`, provar que a ponte semântica continua oferecendo somente consultas e não tocar o runtime do Mouse Hub.

## Technical Context

**Language/Version**: YAML de configuração, Python 3.10+ para testes e ponte
**Primary Dependencies**: Serena Agent 1.7.0 (quando instalada), MCP 1.28.1, pytest
**Storage**: N/A; `.serena/project.yml` é configuração de ferramentas, não dados do produto
**Testing**: pytest estático/offline, handshake da ponte quando Serena estiver instalada, suíte do projeto, smoke Xvfb e pacote `.deb`
**Target Platform**: Linux, ambiente de desenvolvimento do projeto
**Project Type**: aplicativo desktop com tooling local
**Constraints**: menor diff possível; nenhuma mudança em `app/`, `mouse_hub/`, launchers ou packaging

## Constitution Check

| Princípio | Status | Nota |
| --- | --- | --- |
| I. Correção de Hardware em Primeiro Lugar | N/A | Não há hardware nem protocolo nesta issue. |
| II. Honestidade de Estado (UI Não Simula) | N/A | Não há UI do produto alterada. |
| III. Fakes no CI, Hardware Fora | PASS | Os testes da configuração não dependem de hardware. |
| IV. Regressão Com Teste Junto do Fix | PASS | O teste dedicado falha com `read_only: false` e passa com `true`. |
| V. Regras de Domínio Somente no Core | N/A | Nenhuma regra de domínio é tocada. |
| VI. Menor Mudança Completa | PASS | Uma chave YAML, teste, Spec Kit e validações. |
| VII. Verificação Dupla (Software e Realidade) | PASS | O contrato estático e o handshake real da ponte foram executados separadamente; os diagnósticos retornados foram registrados sem mascarar avisos existentes. |
| VIII. UX Honesta e Consistente | N/A | Não há superfície de usuário alterada. |

## Project Structure

```text
.serena/project.yml                              # única configuração de produção do tooling
scripts/agent/semantic-code.py                   # ponte de consultas, não será alterada
scripts/agent/semantic-code                    # launcher da ponte, não será alterado
tests/test_issue63_serena_read_only.py            # contrato da configuração e parser
specs/029-serena-read-only/                       # artefatos Spec Kit
.specify/feature.json                             # ponte para a feature
```

## Design Decisions

1. Alterar somente `read_only: false` para `read_only: true`.
2. Não fixar uma lista manual de ferramentas, pois a Serena já fornece as consultas pelo contexto configurado.
3. Testar o contrato do parser da ponte sem depender do pacote opcional e tentar o handshake real separadamente.
4. Tratar ausência de instalação local como bloqueio observável, nunca como sucesso sintético.

## Traceability Matrix

| Requisito | Implementação | Verificação |
| --- | --- | --- |
| FR-001 / SC-001 | `read_only: true` | teste dedicado e parser YAML |
| FR-002 / SC-002 | configuração e ponte preservadas | parser, inspeção e handshake real |
| FR-003 / SC-002 | ponte sem escrita | inspeção de subcomandos e launcher |
| FR-004 / SC-003 | diff só em `.serena/`, `tests/`, docs | diff de caminhos |
| FR-005 / SC-004 | nenhuma alteração no produto | suíte, smoke, compileall, pacote e CI |

## Validation Gates

- Baseline completo registrado antes da implementação.
- RED do teste dedicado observada com `read_only: false`.
- GREEN após a troca da chave.
- Handshake `tools`, `overview`, `find`, `refs` e `diagnostics` executado se Serena estiver disponível.
- Suíte, smoke, compileall, diff check e pacote validados.
- PR aberto com `Closes #63`, três jobs reais verdes e sem merge.

## Observed Traceability (2026-08-30)

| Requisito/saída | Verificação executada | Resultado observado |
| --- | --- | --- |
| FR-001 / SC-001: `read_only` booleano verdadeiro | `tests/test_issue63_serena_read_only.py` | **PASS**: RED teve 2 falhas e 2 aprovações com `false`; GREEN teve 4 aprovações e confirmou `read_only: true` no arquivo versionado. |
| FR-002 / SC-002: consultas preservadas | parser estático + `semantic-code tools`, `overview`, `find`, `refs` e `diagnostics` | **PASS**: todos os cinco comandos retornaram exit code 0; `find` localizou `SettingsPage` e `refs` retornou referências. |
| FR-003 / SC-002: ponte sem escrita e projeto local | AST do parser + inspeção do launcher + handshake real | **PASS**: nenhum subcomando de edição; launcher usa o venv local e o `--project` aponta para `ROOT`. |
| FR-004 / SC-003: escopo fora do produto | `git diff --name-status` e teste dedicado | **PASS**: alterações de produção restritas a `.serena/project.yml`; teste e docs são os únicos demais arquivos da feature. |
| FR-005 / SC-004: regressão do projeto | suíte, smoke Xvfb, compileall, diff check e pacote Debian | **PASS**: baseline 544, pós-mudança 548, smoke 1 teste, compileall, diff check e staging Debian passaram; SHA do app empacotado coincide com o worktree. |
| SC-005: evidência Spec Kit | RED/GREEN, baseline, handshake, gates locais e esta matriz | **PASS**: evidências locais e limitações dos diagnósticos estão registradas; PR/CI são o gate remoto separado. |
| SC-006: entrega remota | PR com `Closes #63` e três jobs reais | **PENDENTE**: branch ainda não publicada. |
