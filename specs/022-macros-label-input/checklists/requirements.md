# Requirements Checklist: Issue #104

## Escopo

- [x] A issue #104 e os critérios de aceite foram transcritos para `spec.md`.
- [x] O escopo está limitado ao label do formulário de Macros.
- [x] Persistência, serviço de gravação e hardware estão fora da mudança.

## UX

- [x] O label será texto de formulário, sem fundo ou borda de input.
- [x] O campo real continua sendo o único `QLineEdit`.
- [x] Desktop e small preservam ordem e espaçamento.

## Qualidade

- [x] O teste runtime será escrito antes do código de produção.
- [x] O teste usa QApplication offscreen e fake, sem hardware.
- [x] As três screenshots oficiais foram regeneradas e revisadas em desktop, small e preview.
- [x] Regressões focadas, suíte completa (548 testes), smoke Xvfb, compileall e diff check passaram.
- [x] CI real verde foi registrado no workflow `33268985103`, com lint/testes determinísticos, pacote `.deb` e smoke Xvfb aprovados.
- [x] PR #142 está aberto e não mesclado.
