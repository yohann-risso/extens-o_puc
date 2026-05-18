# Como acessar pelo celular ou pela web

## Opção 1: acessar pelo celular na mesma rede Wi-Fi

Essa é a forma mais simples para usar em sala, oficina, laboratório ou empresa.

1. No computador onde o app está salvo, dê dois cliques no arquivo `executar_app.bat`.
2. Aguarde a instalação das dependências e a abertura do Streamlit.
3. O terminal vai mostrar dois endereços:
   - `http://localhost:8501` para abrir no próprio computador.
   - `http://SEU-IP:8501` para abrir no celular.
4. No celular, conecte-se ao mesmo Wi-Fi do computador.
5. Abra o navegador do celular e digite o endereço com o IP mostrado.

Exemplo:

```text
http://192.168.0.10:8501
```

Se o celular não abrir, verifique:

- computador e celular estão no mesmo Wi-Fi;
- o firewall do Windows permitiu o acesso do Python/Streamlit;
- o terminal do app continua aberto.

## Opção 2: publicar como página web

Para deixar disponível pela internet, uma opção simples é publicar no Streamlit Cloud.

Passos gerais:

1. Criar uma conta no GitHub.
2. Criar um repositório com estes arquivos:
   - `app.py`
   - `requirements.txt`
   - `README.md`
   - `PRIVACIDADE_LGPD.md`
3. Acessar `https://share.streamlit.io`.
4. Conectar a conta do GitHub.
5. Escolher o repositório do app.
6. Informar que o arquivo principal é `app.py`.
7. Publicar.

Depois da publicação, o Streamlit gera um link web que pode ser aberto no computador ou no celular.

### Dados do usuário no Streamlit Cloud

O app não usa banco de dados. Os dados preenchidos ficam na sessão de uso do Streamlit Cloud e podem ser perdidos quando a sessão for encerrada ou reiniciada.

Para guardar as informações, o usuário deve:

1. Abrir a aba **Histórico**.
2. Baixar o arquivo Excel ou JSON.
3. Salvar o arquivo no próprio computador, celular ou dispositivo pessoal.
4. Se quiser continuar depois, carregar novamente o JSON salvo no app.

## Opção 3: arquivo instalável

Como este app foi feito em Streamlit, ele funciona melhor como app web. É possível criar um instalador para Windows, mas normalmente ele fica pesado e ainda abre uma página no navegador.

Para o uso educativo da Etapa 3, a opção mais prática é:

- usar o `executar_app.bat` em um computador da oficina; ou
- publicar no Streamlit Community Cloud para acesso por link.
