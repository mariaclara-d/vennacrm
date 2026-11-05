# CRM VENNA

Aplicação Flask para a área comercial da VENNA Mármores e Revestimentos. Duas ou mais contas convidadas usam a mesma carteira de leads e orçamentos. O login é por e-mail e senha da própria aplicação. Os dados e os PDFs exigem sessão autenticada.

## Rodar localmente no Windows

Extraia a pasta do ZIP, abra-a no VS Code e use o terminal do PowerShell. Os comandos usam o executável do ambiente virtual diretamente.

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
$env:VENNA_SECRET_KEY = (.\.venv\Scripts\python.exe -c "import secrets; print(secrets.token_hex(32))")
$env:VENNA_LOCAL_HTTP = "1"
$env:VENNA_BASE_URL = "http://127.0.0.1:8000"
.\.venv\Scripts\python.exe -m flask --app venna init-db
.\.venv\Scripts\python.exe -m flask --app venna invite
.\.venv\Scripts\python.exe -m flask --app venna run --host 127.0.0.1 --port 8000
```

O comando de convite pede o e-mail e o nome da pessoa e imprime um link individual. Abra esse link para definir a senha e entrar. Para o segundo perfil, execute `invite` em outro terminal configurado com as mesmas variáveis. Os convites expiram em 24 horas e cada link funciona uma vez. O banco SQLite local fica em `instance/venna.sqlite3`. A chave gerada fica no ambiente do terminal. Use uma chave estável e armazenada com segurança para preservar sessões entre reinicializações.

## Fluxo de trabalho

1. Cadastre um lead, selecione uma responsável e informe a data do próximo retorno.
2. Abra **Novo orçamento** na ficha do lead ou use **Simulador** para começar pelos valores e vincular ao lead antes de salvar.
3. Adicione materiais em m² e serviços por unidade. Informe explicitamente zero para frete gratuito. Campo vazio aparece como **A confirmar** e o total fica identificado como **Total sem frete**.
4. Salve a proposta e baixe o PDF. Use **Registrar envio** depois de enviar a proposta pelo seu canal comercial. O CRM registra a ação no histórico.
5. Use **Criar revisão** quando valores ou condições mudarem. A revisão anterior fica disponível com os dados do cliente, itens e valores da emissão original.

O servidor recalcula os itens em centavos, arredonda cada linha e soma o subtotal e o frete. A proposta inclui somente os dados comerciais digitados para aquela versão. Notas internas ficam na ficha do lead. O status do orçamento e a etapa do lead têm controles próprios. Registrar o envio avança um lead novo ou em atendimento para **Orçamento enviado**.

## Hospedar com login próprio

Implante em uma hospedagem que execute o aplicativo Python ou o Dockerfile e ofereça HTTPS. Use um PostgreSQL persistente e configure estas variáveis antes da primeira execução.

| Variável | Configuração |
| --- | --- |
| `VENNA_SECRET_KEY` | Chave aleatória estável e exclusiva da aplicação. Gere com `python -c "import secrets; print(secrets.token_hex(32))"` e coloque nas variáveis secretas da hospedagem. |
| `VENNA_DATABASE_URL` | URL do PostgreSQL no formato `postgresql+psycopg://usuario:senha@host:5432/banco`. Configure TLS conforme a hospedagem. |
| `VENNA_BASE_URL` | Origem HTTPS do CRM, por exemplo `https://crm.suaempresa.com.br`. |
| `VENNA_LOCAL_HTTP` | Use `1` somente no ambiente de desenvolvimento em loopback. Em produção, deixe ausente. |

Execute `python -m flask --app venna init-db` uma vez na hospedagem. Aponte o proxy HTTPS para a porta 8000 e use o comando do Dockerfile ou o equivalente com Gunicorn. Execute `python -m flask --app venna invite` para cada conta, usando os e-mails confirmados. A pessoa responsável pela implantação entrega cada convite diretamente à sua destinatária. Para redefinir a senha, emita um novo convite com `invite --reset`. Para revogar uma conta, use `python -m flask --app venna disable-account email@exemplo.com`.

As rotas do CRM verificam a sessão no servidor. Contas convidadas têm acesso compartilhado à carteira comercial. Administração de contas é feita no terminal da implantação. A versão do simulador destinada ao site de clientes será uma etapa separada.

## Testes

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```
