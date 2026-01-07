# 🔍 Guia de Teste e Debug - Permissões BI

## Endpoint de Debug

Existe um endpoint especial para verificar o status das permissões de um usuário:

```
GET /api/usuarios/{user_id}/debug-bi
```

**Exemplo:**

```bash
curl "http://localhost:8000/api/usuarios/5/debug-bi"
```

**Resposta Esperada:**

```json
{
  "user_id": 5,
  "user_name": "João Silva",
  "_bi_subcategories_raw": "[\"dashboard-id-1\", \"dashboard-id-2\"]",
  "_bi_subcategories_parsed": ["dashboard-id-1", "dashboard-id-2"],
  "note": "Check the _bi_subcategories_raw field in database"
}
```

## Verificações Passo a Passo

### 1. Criar Usuário com Permissões Restringidas

#### Passo 1: Acessar Admin Panel

```
http://seu-app/setores/ti/admin/usuarios
```

#### Passo 2: Criar Novo Usuário

- Nome: João Silva
- Setor: Marque "Portal de BI"
- Dashboard BI: Selecione apenas "Dashboard de Vendas" (ex: `sales-dashboard`)
- Clique em "Salvar"

#### Passo 3: Verificar Database

```sql
-- Substitua 'user_id' com o ID do usuário criado
SELECT id, usuario, _bi_subcategories FROM user WHERE usuario = 'seu_usuario';
```

**Esperado:**

```
id  | usuario  | _bi_subcategories
5   | joao     | ["sales-dashboard"]
```

#### Passo 4: Verificar via API

```bash
curl "http://localhost:8000/api/usuarios/5/debug-bi"
```

**Esperado:**

```json
{
  "_bi_subcategories_raw": "[\"sales-dashboard\"]",
  "_bi_subcategories_parsed": ["sales-dashboard"]
}
```

#### Passo 5: Fazer Login com Novo Usuário

- Logout do admin
- Login com o novo usuário
- Acesse "Portal de BI"
- Verifique que consegue ver **apenas** "Dashboard de Vendas"

### 2. Editar Usuário e Adicionar Mais Dashboards

#### Passo 1: Editar Usuário Existente

- Abra o painel de admin
- Clique em "Editar" para o usuário criado

#### Passo 2: Adicionar Mais Dashboard

- No setor BI, marque também "Dashboard de Compras" (ex: `purchases-dashboard`)
- Clique em "Salvar"

#### Passo 3: Verificar

```sql
SELECT _bi_subcategories FROM user WHERE usuario = 'seu_usuario';
```

**Esperado:**

```
["sales-dashboard", "purchases-dashboard"]
```

#### Passo 4: Login e Verificar

- Logout
- Login novamente
- Deveria ver AMBOS os dashboards no BI

### 3. Teste de Validação (Erro Esperado)

#### Passo 1: Tentar Salvar sem Dashboard

- Edite um usuário
- Marque setor "Portal de BI"
- NÃO marque nenhum dashboard
- Tente clicar em "Salvar"

#### Passo 2: Verificar Aviso

**Esperado:**

```
⚠️ Você selecionou o setor Portal de BI mas não escolheu nenhum dashboard.
Por favor, selecione pelo menos um dashboard ou desmarque o setor BI.
```

## Checagem de Logs

### Logs do Frontend

Abra o Console do Navegador (F12 > Console) e procure por:

```
[BI] 🔐 Filtrando dashboards por permissão do usuário: ["dashboard-id"]
[BI] ✅ 1 dashboards após filtragem
```

Ou se houver restrição:

```
[BI] 🔒 Usuário tem setor BI mas sem dashboards selecionados - acesso negado
```

### Logs do Backend

Nos logs do backend, procure por:

```
[_set_bi_subcategories] Called with: ['sales-dashboard']
[_set_bi_subcategories] Setting _bi_subcategories to: ["sales-dashboard"]
[API] bi_subcategories parsed from '["sales-dashboard"]' -> ['sales-dashboard']
```

## Histórico de Estados

| Estado              | \_bi_subcategories  | Comportamento                          |
| ------------------- | ------------------- | -------------------------------------- |
| `NULL`              | NULL                | Sem restrição, mostra todos dashboards |
| `[]` (array vazio)  | `[]`                | Com setor BI mas acesso negado a todos |
| `["dash1"]`         | `["dash1"]`         | Acesso apenas a dashboard específico   |
| `["dash1","dash2"]` | `["dash1","dash2"]` | Acesso a múltiplos dashboards          |

## Troubleshooting

### Problema: Dashboard vazio mesmo após atribuir permissões

**Possíveis causas:**

1. Cache do navegador não foi limpo
2. Usuário ainda não fez logout/login novamente
3. Erro ao salvar no banco de dados

**Soluções:**

```bash
# 1. Limpar cache do navegador (Ctrl+Shift+Delete)
# 2. Fazer logout e login novamente
# 3. Verificar logs do backend
# 4. Verificar database:
SELECT _bi_subcategories FROM user WHERE usuario = 'seu_usuario';
```

### Problema: Ver todos os dashboards mesmo com restrição

**Debug:**

```bash
# 1. Verificar via API
curl "http://localhost:8000/api/usuarios/{user_id}"

# 2. Procurar no log por:
# [BI] 🔐 Filtrando dashboards
# ou
# [BI] 📚 Usuário sem restrições

# 3. Verifique database
SELECT id, usuario, _bi_subcategories FROM user LIMIT 10;
```

## Query SQL Úteis

### Ver todos os usuários com permissões BI

```sql
SELECT id, usuario, _bi_subcategories
FROM user
WHERE _bi_subcategories IS NOT NULL;
```

### Ver usuários COM setor BI mas SEM dashboard selecionado

```sql
SELECT id, usuario, _bi_subcategories
FROM user
WHERE _bi_subcategories = '[]';
```

### Atualizar permissões via SQL (se necessário)

```sql
-- Dar acesso a um dashboard específico
UPDATE user
SET _bi_subcategories = '["sales-dashboard"]'
WHERE usuario = 'seu_usuario';

-- Remover todas as permissões BI
UPDATE user
SET _bi_subcategories = NULL
WHERE usuario = 'seu_usuario';
```

## Verificação Final

Após implementar a correção, verifique:

- [ ] Backend compilou sem erros
- [ ] Frontend compilou sem erros
- [ ] Consegue criar usuário com setor BI
- [ ] Consegue editar permissões de BI
- [ ] Consegue fazer login com novo usuário
- [ ] Novo usuário vê apenas dashboards permitidos
- [ ] Logs mostram filtragem correta
- [ ] Database armazena `_bi_subcategories` corretamente
- [ ] Validação previne salvar sem dashboard selecionado

---

Se precisar de mais ajuda, consulte o arquivo `BUG_FIX_SUMMARY.md` para mais detalhes técnicos.
