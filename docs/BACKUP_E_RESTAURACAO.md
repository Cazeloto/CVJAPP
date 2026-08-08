# Backup e restauracao do CVJAPP

O GitHub Actions cria diariamente uma copia do banco Neon, restaura o arquivo
em um PostgreSQL 18 temporario, valida as tabelas essenciais e somente entao
armazena a copia criptografada por 30 dias.

Segredos necessarios no repositorio:

- `CVJAPP_DATABASE_URL`: conexao somente leitura usada pelo backup;
- `CVJAPP_BACKUP_KEY`: chave aleatoria de criptografia.

A primeira restauracao de uma copia deve sempre ocorrer em um banco novo e
isolado. Nunca use o banco de producao como primeiro destino de um teste.
