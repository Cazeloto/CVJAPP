# Seguranca do CVJAPP

Todas as telas exigem login. Administradores gerenciam usuarios, consultam a
auditoria e executam exportacao ou carga integral da base. Operadores usam as
funcoes normais de atendimento sem acesso a essas operacoes administrativas.

Depois de cinco erros consecutivos, a conta e bloqueada por 15 minutos em todos
os dispositivos. Um administrador pode desbloquea-la na tela `Usuarios`.

Cada sessao dura no maximo oito horas e e revalidada no Neon a cada 30
segundos. Desativar a conta ou redefinir sua senha encerra sessoes anteriores.

A auditoria registra acessos, gestao de usuarios, exportacao, carga e eventos
de sessao. Senhas, tokens, hashes e conteudo de documentos nao sao gravados.

As credenciais do Neon permanecem apenas no `.env` local e nos segredos do
GitHub usados pelo backup; nunca devem ser versionadas.
