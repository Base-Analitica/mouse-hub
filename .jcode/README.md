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

## Spec Kit (SDD)

O projeto usa [Spec Kit](https://github.com/github/spec-kit) v1.0.1 para
Desenvolvimento Dirigido por Especificação. A CLI `specify` está
instalada no nível de usuário (`uv tool install specify-cli --from
git+https://github.com/github/spec-kit.git@v1.0.1`).

- Skills geradas em `.agents/skills/speckit-*/` — o Jcode as carrega
  nativamente (10 skills, comandos `/speckit-*`).
- Templates, scripts e workflows em `.specify/`.
- Fluxo: `/speckit-constitution` (uma vez) → `/speckit-specify` →
  `/speckit-plan` → `/speckit-tasks` → `/speckit-implement` →
  `/speckit-converge` até convergir.
- `specs/` contém uma pasta por feature (`specs/NNN-nome/spec.md`).
- `.specify/feature.json` é estado local por checkout e não vai ao git
  (ver `.specify/.gitignore`).

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
