# 🧪 Teste Local - Correção de Permissões BI

## Ambiente

- **Frontend:** http://localhost:3005
- **Backend:** http://localhost:3001/api
- **Banco de dados:** (seu BD configurado)

## Pré-requisitos

1. ✅ Ambos os servidores rodando
2. ✅ Código atualizado com as correções
3. ✅ Browser com console aberto (F12)

## Teste Prático em 5 Minutos

### Teste 1: Criar Usuário com Restrição BI

**Passo 1: Acessar Admin**

```
http://localhost:3005/setores/ti/admin/usuarios
```

**Passo 2: Criar Novo Usuário**

```
Nome: Test User
Sobrenome: BI
Usuário: test.bi
Email: test.bi@company.com
Nível: Funcionário
Setor: ☑️ Portal de BI
Dashboard BI: ☑️ Selecione UM dashboard (ex: "Dashboard de Vendas")
Gere uma senha
```

**Passo 3: Clicar em Salvar**

- Deverá salvar sem erros
- Verifique o console do navegador (F12 > Console)

**Passo 4: Verificar Logs do Frontend**
Procure por uma dessas mensagens:

```
[ADMIN] Salvando usuário X com payload: {...}
[ADMIN] bi_subcategories saved as: ["dashboard-id"]
```

### Teste 2: Verificar Banco de Dados

**Abra um terminal e conecte ao banco:**

```bash
# Para PostgreSQL
psql -h localhost -U seu_user -d seu_db

# Para MySQL
mysql -u seu_user -p seu_db
```

**Execute a query:**

```sql
SELECT id, usuario, _bi_subcategories FROM user WHERE usuario = 'test.bi';
```

**Esperado:**

```
id  | usuario | _bi_subcategories
123 | test.bi | ["sales-dashboard"]
```

### Teste 3: Fazer Login com Novo Usuário

**Passo 1: Logout**

```
Clique em Logout no menu
```

**Passo 2: Login com Novo Usuário**

```
Usuário: test.bi
Senha: (a senha gerada)
```

**Passo 3: Acesse Portal de BI**

```
Menu > Setores > Portal de BI
```

**Esperado:**

- ✅ Ver APENAS o dashboard selecionado
- ❌ NÃO ver outros dashboards

**Verifique os logs do Frontend:**

```
[BI] 🔐 Filtrando dashboards por permissão do usuário: ["sales-dashboard"]
[BI] ✅ 1 dashboards após filtragem
```

### Teste 4: Verificar Logs do Backend

**Procure nos logs do backend por:**

```
[_set_bi_subcategories] Called with: ['sales-dashboard']
[_set_bi_subcategories] Setting _bi_subcategories to: ["sales-dashboard"]
[API] bi_subcategories parsed from '["sales-dashboard"]' -> ['sales-dashboard']
```

Se vir esses logs, significa que está funcionando! ✅

### Teste 5: Validação - Tentar Salvar Sem Dashboard

**Passo 1: Voltar para Admin**

```
Logout do test.bi
Login como Admin
Acesse admin de usuários
```

**Passo 2: Criar Novo Usuário**

```
Nome: Teste Validação
Setor: ☑️ Portal de BI
Dashboard BI: ❌ NÃO selecione nenhum
```

**Passo 3: Tente Clicar em Salvar**

**Esperado:**

```
⚠️ Você selecionou o setor Portal de BI mas não escolheu nenhum dashboard.
Por favor, selecione pelo menos um dashboard ou desmarque o setor BI.
```

Se esse aviso aparecer, a validação está funcionando! ✅

## Teste Avançado: API Debug

### Verificar Permissões via API

**Abra o terminal e execute:**

```bash
# Substituir {user_id} com o ID do usuário criado
curl "http://localhost:3001/api/usuarios/{user_id}/debug-bi"
```

**Exemplo Completo:**

```bash
# Supondo que o user_id é 123
curl "http://localhost:3001/api/usuarios/123/debug-bi"
```

**Resposta Esperada:**

```json
{
  "user_id": 123,
  "user_name": "Test User BI",
  "_bi_subcategories_raw": "[\"sales-dashboard\"]",
  "_bi_subcategories_parsed": ["sales-dashboard"],
  "note": "Check the _bi_subcategories_raw field in database"
}
```

## Checklist de Validação

Marque cada item conforme testar:

### Frontend ✅

- [ ] Console mostra `[ADMIN] Salvando usuário` ao salvar
- [ ] Console mostra `[ADMIN] bi_subcategories saved as`
- [ ] Validação impede salvar sem dashboard BI selecionado
- [ ] Mensagem de erro da validação aparece corretamente
- [ ] Após login, console mostra `[BI] 🔐 Filtrando dashboards`
- [ ] Usuário vê apenas dashboard selecionado

### Backend ✅

- [ ] Logs mostram `[_set_bi_subcategories]` ao salvar
- [ ] Logs mostram `[API] bi_subcategories parsed`
- [ ] Endpoint `/debug-bi` retorna dados corretos
- [ ] Query no banco mostra `_bi_subcategories` como JSON array

### Banco de Dados ✅

- [ ] `_bi_subcategories` armazenado como JSON string
- [ ] Valor é array: `["dashboard-id"]`, não NULL
- [ ] Query SELECT retorna valor correto

## Troubleshooting

### Problema: Vê todos os dashboards mesmo com restrição

**Causas Comuns:**

1. Cache do navegador
2. Não fez logout/login novamente
3. Erro ao salvar no banco

**Soluções:**

```
1. Ctrl + Shift + Del > Limpar cache
2. Logout e login novamente
3. Verificar logs do backend
4. Verificar banco: SELECT * FROM user WHERE usuario = 'test.bi'
```

### Problema: Vê mensagem de erro ao salvar

**Verifique:**

```
1. Os logs do backend (erros de SQL?)
2. Se o banco está acessível
3. Se a tabela user existe
4. Se a coluna _bi_subcategories existe
```

### Problema: Validação não aparece

**Verifique:**

```
1. Se o arquivo foi salvo: frontend/src/pages/sectors/ti/admin/usuarios/pages.tsx
2. Se o frontend foi recompilado (restart do dev server)
3. Se o browser recarregou (Ctrl+F5)
```

## Logs Importantes para Debug

### Console do Navegador (F12)

**Procure por:**

```javascript
[BI] 📥 Buscando dashboards
[BI] ✅ dashboards encontrados
[BI] 🔐 Filtrando dashboards por permissão
[BI] ✅ dashboards após filtragem
```

### Logs do Backend

**Procure por:**

```
[_set_bi_subcategories] Called with
[API] User updated successfully
[API] bi_subcategories parsed from
```

## Scenario Completo de Teste

### Roteiro Step-by-Step

```
1. Criar usuário:
   - Nome: João BI
   - Setor: Portal de BI
   - Dashboard: Sales Dashboard

2. Salvar e verificar logs

3. Logout

4. Login como João BI

5. Acessar Portal de BI

6. Verificar que vê APENAS Sales Dashboard

7. Voltar e editar João BI

8. Adicionar mais um dashboard (ex: Purchases)

9. Logout/Login novamente

10. Verificar que agora vê AMBOS os dashboards
```

## URLs Úteis

```
Admin Panel:        http://localhost:3005/setores/ti/admin/usuarios
Portal de BI:       http://localhost:3005/setores/bi
Debug API:          http://localhost:3001/api/usuarios/{id}/debug-bi
API Base:           http://localhost:3001/api
```

## Relatório Final

Se tudo passar, você pode relatar:

✅ **SUCESSO** - A correção está funcionando corretamente!

Cite:

- Dashboard selecionado é salvo e recuperado corretamente
- Usuário vê apenas dashboards permitidos
- Validação previne salvar sem dashboard
- Logs mostram filtragem correta
- Banco de dados armazena corretamente

❌ **FALHA** - Se algo não funcionar:

Capture:

- Print do console (F12)
- Logs do backend
- Query do banco de dados: `SELECT _bi_subcategories FROM user WHERE usuario = '...';`
- Erro exato da mensagem

---

**Tempo estimado:** 5-10 minutos

**Dúvidas?** Consulte `BUG_FIX_SUMMARY.md` e `TESTING_DEBUG_GUIDE.md`
