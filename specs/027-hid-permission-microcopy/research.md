# Pesquisa: microcopy de permissões HID

## Escopo confirmado

A issue #81 é uma correção de copy na `SettingsPage`. Em
`app/mouse_hub_app.py`, o `QLabel` `hid_info` ainda diz para o usuário criar uma
regra udev permanente e alterar permissões manualmente, embora o próprio app
já exponha o botão `Conceder acesso ao hardware  (senha de administrador)` e
chame `_grant_hid_access()`.

## Decisão: explicar o fluxo gráfico no texto introdutório

- **Decision**: usar uma frase em pt-BR que explica finalidade, condição e ação
  do botão, sem alterar o botão nem o fluxo de autorização.
- **Rationale**: a mensagem precisa orientar a próxima ação real do usuário,
  não repetir o procedimento histórico de terminal.
- **Alternatives considered**: remover toda a explicação e deixar apenas o
  botão reduziria contexto; manter a instrução de udev contradiz a UI atual;
  criar um novo componente seria desnecessário para um `QLabel` com word wrap.

## Decisão de copy

Texto planejado:

> Para controlar o DPI físico do mouse, o Mouse Hub precisa de acesso HID ao G403 HERO. Se faltar permissão de escrita, clique em “Conceder acesso ao hardware” para o aplicativo solicitar autorização administrativa e instalar a regra necessária.

A formulação não diz que a permissão já existe, não pede terminal e termina com
pontuação completa.

## Invariantes preservados

- `_sync_permission_ui()` continua a decidir status, cor, habilitação e label do
  botão a partir de `hid_available`.
- `_grant_hid_access()` continua usando thread e prompt gráfico.
- `fix_hid_permissions()`, polkit/pkexec, descoberta, regra udev e hardware não
  serão alterados.
- O teste usa a página real e fakes existentes, sem mouse físico.
