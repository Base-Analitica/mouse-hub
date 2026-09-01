# Checklist de requisitos: issue #97

## Escopo

- [x] A issue oficial #97 foi consultada.
- [x] A mudança está limitada à copy visível de `ProfilesPage`.
- [x] Não há alteração planejada em core, hardware, persistência, chaves, lógica ou layout.
- [x] Comentários e docstrings ficam fora do escopo.

## Copy

- [x] `Não foi possível ler os perfis` está presente no erro de leitura.
- [x] `O arquivo de configuração NÃO foi alterado.` está presente no erro de leitura.
- [x] A falha total usa `NÃO aplicado`.
- [x] A falha de salvamento usa `Não foi possível salvar`.
- [x] O sucesso usa `salvo na configuração.`.
- [x] Não restam as formas sem acentuação nas strings visíveis alvo.

## Estados e regressão

- [x] Erro de leitura permanece visível, bloqueia mutação e preserva o arquivo.
- [x] Aplicação parcial permanece explícita.
- [x] Falha total não vira sucesso.
- [x] Falha de persistência não vira sucesso.
- [x] Sucesso só aparece depois de persistência confirmada.
- [x] Assertions existentes foram atualizadas sem enfraquecimento.

## Qualidade e entrega

- [x] Teste novo foi visto falhar antes da produção.
- [ ] Testes focados passam.
- [ ] Suíte completa passa.
- [ ] Smoke Xvfb passa.
- [ ] `compileall` e `git diff --check` passam.
- [ ] Pacote `.deb` passa.
- [ ] Capturas oficiais têm dimensões corretas e são determinísticas.
- [ ] Revisão read-only não encontrou defeitos sem tratamento.
- [ ] PR referencia #97, está aberto, não merged e tem os três checks reais verdes.
