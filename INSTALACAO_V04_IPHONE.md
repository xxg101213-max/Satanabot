> **Histórico v0.4. O guia atual é INSTALACAO_V05_IPHONE.md.**

# Instalar v0.4 no Satanabot usando somente iPhone

Seu repositório é https://github.com/xxg101213-max/Satanabot, e sua Railway já está conectada a ele. **Não crie outro bot ou serviço.**

1. Salve `Satanabe_AI_Builder_v0.4.zip` em Arquivos no iPhone.
2. No Safari, abra a raiz de Satanabot no GitHub, `Add file` > `Upload files`, e envie o ZIP.
3. Em `Code` > `Codespaces`, abra um Codespace em `main`. No terminal, execute:

```bash
unzip -o Satanabe_AI_Builder_v0.4.zip
cp -a satanabe-ai-builder-v0.4/. .
rm -rf satanabe-ai-builder-v0.4 Satanabe_AI_Builder_v0.4.zip
git add -A
git commit -m "Satanabe AI Builder v0.4"
git push
```

4. Railway deve disparar o deploy ao detectar a alteração no branch main. Verifique `Deployments` > logs e o status `Active`.
5. Preserve as variáveis atuais do Telegram e Groq. Se Groq mostrar 403 para `openai/gpt-oss-120b`, esta versão tenta `openai/gpt-oss-20b` automaticamente, desde que permitido à sua conta.
6. Abra Telegram e envie `/start`, `/statusia`, `/testaria`.

## Novos comandos

- `/extrair`: abra pacote .3105 suportado e devolva os arquivos em ZIP.
- `/construir Crie ESP com Box Skeleton nomes`: envie o Assembly ou um .3105, receba análise e, se o servidor conseguir compilar, uma DLL de geometria ESP e seu código-fonte. **A DLL não é injetada automaticamente no Assembly do jogo**.
- `/esp`: escolha funções e cores e clique Gerar; a versão agora tenta compilar a DLL além da configuração JSON.
- `/agente Inspecione e compile ESP`: envie o arquivo após o comando e permita que a IA Groq solicite ferramentas de inspeção/compilação permitidas.
- `/trocartexto texto antigo | texto novo`: envie um Assembly .NET gerenciado; o bot altera um único literal correspondente e entrega uma cópia atualizada.
- `/atualizar`: envie .3105 original modificado, depois Assembly atualizado e Assembly antigo original. Para .NET gerenciado, transfere apenas literais em métodos estruturalmente compatíveis.
- `/empacotar com.seu.aplicativo Documents/caminho/arquivo.bytes`: envie arquivo que substituirá este caminho, receba .3105 v3 criado e reaberto.

## Limitações técnicas

- Para IL2CPP e assets Unity nativos, a inspeção é possível, mas este pacote **não implementa** edição automática de hitboxes, ESP injetada ou alteração arbitrária em binários.
- Bibliotecas compiladas para .NET 8 não são automaticamente compatíveis com todas as versões de Unity/iOS. Exigem adaptador de runtime, referências e testes do aplicativo.
- Há um teste automático de build .NET no GitHub Actions. Testes de compilação no ambiente local de geração deste ZIP não estavam disponíveis por ausência de SDK .NET.
- `Dockerfile` utiliza SDK .NET 8 e Python, ficando maior que o anterior. Veja logs Railway se o build falhar por espaço/memória/tempo/restore NuGet.
- Para uso de patches reais, teste backup e restauração no aplicativo 3105; reabrir o arquivo no servidor não verifica sua aplicação no dispositivo.

Não envie tokens do Telegram ou da Groq em chats ou arquivos GitHub. 
