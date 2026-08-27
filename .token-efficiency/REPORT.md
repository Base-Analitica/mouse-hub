# Relatório de eficiência de tokens — mouse-hub

Data: 2026-08-27 · Escopo: camada project-local para sessões Prime Agent; nenhuma instalação global.

## Componentes

| Componente | Status | Evidência / decisão |
|---|---|---|
| Princípios ponytail | enabled | Regras curtas em `AGENTS.md` ("Código mínimo"); nenhum plugin instalado. |
| Comunicação enxuta | enabled | `AGENTS.md` ("Comunicação enxuta") — concisão profissional, não "caveman speak". Skills globais `ponytail`/`caveman` do usuário seguem disponíveis sob demanda. |
| RTK (Rust Token Killer) | enabled | Release oficial `v0.46.0` com SHA-256 fixado em `scripts/agent/bootstrap-rtk`; binário e estado (config/tee/histórico) em `.tools/rtk/` dentro do checkout. Smoke: `--version`, `git log`, `git status`, `rg`, `gain`. |
| EcoTokens | skipped | Sobrepõe RTK como filtro de shell; nenhuma evidência de cobertura/compatibilidade melhor justificando filtro duplo. |
| Serena | enabled (bridge local) | `serena-agent==1.7.0` + `mcp==1.28.1` fixados, venv project-local em `.tools/serena/venv`, stdio apenas, dashboard desativado, sem porta pública. `.serena/project.yml` declara Python. Smoke: `tools`, `overview`, `find`, `refs`. |
| Fallback semântico | enabled | `rg` + leitura direcionada permanecem o caminho se Serena falhar. |
| Compaction (Prime Agent) | enabled | Nativa; orientação de uso em `AGENTS.md` ("Compaction"). Nenhum sistema de memória extra. |
| Tokscale | skipped | Telemetria nativa do Prime Agent (`/usage`, skill `compact`) já mede tokens/contexto; sem dependência extra de upload. |
| Instalação global | none | `rtk` do usuário em `~/.local/bin` foi autorizado explicitamente pelo mantenedor antes desta camada; tudo criado aqui é 100% project-local. |

## Benchmark (project-local, via `scripts/agent/rtk`)

| Operação | Nativo | RTK | Redução | Overhead |
|---|---:|---:|---:|---:|
| `git log -12` | 2.855 B | 1.449 B | **49,2 %** | +11 ms |
| `rg "def test" tests/` | 34.405 B | 18.788 B | **45,4 %** | +13 ms |
| `git status --short --branch` | 115 B | 114 B | 0,9 % (saída já mínima) | +14 ms |

Nota: redução medida em bytes capturados, proxy do custo de contexto; contabilidade exata no `/usage` do Prime Agent. Saídas pequenas não se beneficiam — usar o comando nativo (regra em `AGENTS.md`).

## Limitações

- `rtk git log` não comprime quando recebe `--stat` (passthrough); para histórico com arquivos, usar `git log --stat` nativo quando o detalhe for necessário.
- `rg`/`grep` só comprimem acima de um limiar de tamanho de saída.
- Serena precisa de `uv` e de primeiro bootstrap por checkout (`scripts/agent/bootstrap-serena`); cache do uv fica em `.cache/agent-tools/` (ignorado pelo git).
- O bridge Serena é somente leitura; edições usam os mecanismos normais do Prime Agent.
