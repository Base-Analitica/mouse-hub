# Solução de problemas

Guia de orientação para os problemas mais comuns do Mouse Hub com o Logitech G403 HERO no Linux.

## Mouse nao detectado

Verifique se o cabo USB está firmemente conectado (ou se o receptor sem fio está em outra porta) e confirme que o dispositivo aparece em `lsusb`; em ambientes sem permissão de leitura ao hidraw, instale a regra udev de `docs/udev/99-logitech-g403-hidraw.rules` para que a descoberta HID++ funcione sem privilégios de root.

## DPI nao aplica

Confirme que o mouse foi detectado pelo aplicativo e que o perfil desejado está selecionado: o valor de DPI enviado por HID++ só é aplicado quando existe um device válido, então teste um preset da faixa suportada (100–25600, passos de 50) e observe o indicador do app para confirmar que o comando foi aceito.

## Macros nao gravam

Certifique-se de que a gravação foi iniciada (botão de gravar ativo) antes de executar a sequência desejada, pois eventos capturados fora do intervalo de gravação são descartados; verifique também se o perfil atual tem espaço para uma nova macro e interrompa a gravação para que ela seja salva e fique disponível para execução.
