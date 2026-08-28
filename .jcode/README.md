# Jcode — configuração do agente responsável pelo Mouse Hub

Este diretório substitui o antigo `.prime/` (Prime Agent). O Jcode é o
agente de código responsável por este repositório a partir de
2026-08-28.

## Conteúdo

- [`skills/token-efficient-shell/`](skills/token-efficient-shell/) — saída
  comprimida de shell via `scripts/agent/rtk` (opcional; setup com
  `scripts/agent/bootstrap-rtk`).
- [`skills/semantic-code/`](skills/semantic-code/) — navegação semântica
  via bridge Serena read-only (`scripts/agent/semantic-code`).
- [`skills/find-skills/`](skills/find-skills/) — descoberta e instalação
  de skills do ecossistema público (skills.sh / `npx skills`), com nota
  de adaptação para instalação project-local neste repo.

## Camadas de prompt que o Jcode lê neste repositório

1. `AGENTS.md` (raiz) — convenções do projeto, regras para agentes e
   arquitetura. Fonte primária de verdade; as skills complementam.
2. `.jcode/skills/<nome>/SKILL.md` — carregadas sob demanda (semântica
   ou via `skill_manage`).

## Notas de migração

- `.prime/agent/skills/*` → `.jcode/skills/*` (mesma semântica, formato
  idêntico de frontmatter YAML).
- `AGENTS.md` e `scripts/agent/*` foram atualizados para referenciar
  `.jcode/`; `.prime/` foi removido do repositório.
- As ferramentas (`rtk`, `semantic-code`) continuam em `scripts/agent/`
  e não dependem de nenhum agente específico.
