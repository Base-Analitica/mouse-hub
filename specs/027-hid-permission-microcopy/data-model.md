# Modelo de dados: microcopy de permissões HID

Esta mudança não cria nem altera dados persistidos, entidades de domínio ou
contratos de hardware.

- `hid_info` é um `QLabel` informativo da `SettingsPage`; seu conteúdo é
  apresentação estática.
- `hid_available` continua vindo do modelo de capabilities e permanece a fonte
  de verdade para habilitar o fluxo de autorização.
- `_permission_btn` continua chamando `_grant_hid_access()` e o status continua
  refletindo os resultados reais de `_sync_permission_ui()`.
- Nenhuma regra udev, caminho hidraw, operação pkexec ou estado de configuração
  é alterado.
