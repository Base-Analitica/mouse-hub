# Feature Specification: Screenshots públicos com caminhos neutros

**Feature Branch**: `fix/neutral-screenshot-paths`

**Created**: 2026-08-29

**Status**: Draft

**Input**: User description: "Issue #109 — `6_settings.png`,
`small_settings.png` e `preview.png` exibem
`Config: /home/pedro/...` em Informações do Sistema. Artefato público
não pode variar por HOME/username do ambiente de captura."

## Correção

- **Apenas o fixture de captura** (`scripts/capture_screenshots.py`)
  passa a rodar com `XDG_CONFIG_HOME`/`XDG_DATA_HOME` apontando para um
  diretório fake neutro (`/home/user/.config`-like via tmp do
  ambiente): o texto exibido fica determinístico e sem username —
  `Config: /home/user/.config/mouse-hub/config.json`.
- **Nenhuma mudança no comportamento do usuário local**: a página de
  Informações do Sistema continua lendo `ConfigPaths.xdg()` reais.
- O diretório fake não toca dados do usuário e não é lido por nada que
  persista (o pipeline nunca grava config: NeverDpiPersister, engine
  fake de macros, sem `save`).

## Acceptance Criteria

- dois ambientes com HOME diferente produzem o mesmo texto no bloco
  Informações do Sistema;
- nenhum PNG em `docs/screenshots/` contém `/home/pedro` (ou qualquer
  username real);
- `6_settings.png`, `small_settings.png` e `preview.png` regeneradas;
- teste fixa o caminho exibido sem acessar dados reais;
- CI verde.

## Principles Check

| Princípio | Aplicação |
| --- | --- |
| Dupla verificação | teste compara o texto do bloco entre HOMEs |
| Menor mudança completa | só o fixture de captura |
| Estado honesto | usuário local continua vendo seus caminhos reais |
