# Registro de execução da corrida CI x review

Fixture do teste V2.1.3 rodada 2 (ciclo de falha de CI): registro documental da corrida entre a conclusão das checks obrigatórias de CI e o despertar da lane de revisão.

## Janela observada

Na corrida desta rodada, o card de implementação chegou à lane de revisão enquanto as checks obrigatórias do SHA recém-pusheado ainda estavam pendentes, configurando a janela em que o revisor pode acordar antes do veredicto do CI. O protocolo V2.1.3 trata essa janela explicitamente: o card pode ser estacionado em WAITING_CI (estado `blocked` não-terminal) até a chegada do evento `check_suite.completed success` para o SHA atual, sem que o dev reenvie ou duplique trabalho.

## Resultado

O resultado observado é que a corrida se resolve sem intervenção extra do implementador: quando o check suite completa com sucesso no SHA vigente, o ingress desbloqueia o MESMO card e o dispatcher re-acorda o revisor, mantendo a provenance (pr/issue/head_sha) registrada no metadata. Em caso de falha de CI no SHA, o ciclo `cifix:<SHA>` assume a correção e gera um SHA novo, tornando o card anterior obsoleto por design.
