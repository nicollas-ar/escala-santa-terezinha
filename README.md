# Escala Santa Terezinha

Aplicação exclusiva de **escalas e avisos** da Paróquia Santa Terezinha do Menino Jesus, em Flask.

## Recursos
- Página pública: próximas celebrações, escalas publicadas e avisos;
- Padre: cria/gerencia coordenadores e também administra escalas e avisos;
- Coordenadores: cadastram/ativam/desativam servidores (sem fotos), elaboram escalas, sorteiam e publicam;
- Servidores: não possuem conta nem senha; consultam a escala pública e pesquisam seu nome;
- Celebrações únicas ou recorrentes (semanais ou mensais), sorteio equilibrado, edição manual e compartilhamento por imagem no WhatsApp;
- Nenhum servidor ou coordenador pré-cadastrado; nada de quiz, finanças, liturgia ou outros módulos.

## Configuração
Python 3.11+.

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
python app.py
```

Configure **antes da primeira inicialização**:
- `PADRE_USER`: nome de usuário do padre;
- `PADRE_PASSWORD`: senha inicial **forte** do padre (mínimo 12 caracteres);
- `SECRET_KEY`: chave aleatória de sessão (ex.: gerada por `python -c "import secrets; print(secrets.token_hex(32))"`).
- `DATABASE_URL`: conexão com um **novo** banco PostgreSQL do Neon em produção. Opcional localmente: sem essa variável, usa SQLite.
- `PRODUCAO=1`: habilita cookie HTTPS e exige SECRET_KEY e armazenamento persistente.

Na primeira execução, o sistema cria **somente** o usuário do padre definido nas variáveis. Nenhum coordenador ou servidor é criado automaticamente. Depois que houver um padre criado, mudanças nas variáveis não sobrescrevem sua senha; atualizações de credenciais exigem ação administrativa.

### Render
- Build: `pip install -r requirements.txt`
- Start: `gunicorn app:app`
- Variáveis: `DATABASE_URL`, `SECRET_KEY`, `PADRE_USER`, `PADRE_PASSWORD`, `PRODUCAO=1`.
- `/saude`: retorna OK sem consultar o banco.
- **Use um banco Neon novo**: não vincule o banco do projeto original nem reutilize o banco contendo fotos/dados anteriores.

### Segurança e privacidade
- Senhas armazenadas com hash;
- Controle de acesso por perfil e checagem de CSRF nos formulários;
- Não publique senhas, chaves, arquivos `.env`, bancos SQLite ou dados de servidores no GitHub;
- Em produção, faça backup do banco e restrinja quem acessa as credenciais.

## Código
- `app.py`: rotas, autenticação, escala, publicação e avisos;
- `database.py`: SQLite local / PostgreSQL Neon;
- `templates/`: telas responsivas;
- `static/`: identidade visual e cartão WhatsApp.

O repositório anterior `nicollas-ar/novo-escala` permanece **inalterado**.

## Página pública
A página contém somente a apresentação da paróquia, os avisos e as escalas publicadas, com busca pelo nome do servidor. Apenas padre e coordenadores fazem login. Os servidores são registros internos de escala sem credenciais utilizáveis.
