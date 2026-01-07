# 🐛 Bug Fix: BI Dashboard Permissions Not Being Saved

## Problema Identificado

Quando um administrador criava um usuário e tentava limitar o acesso a dashboards BI específicos, as permissões não eram salvas corretamente. O usuário conseguia acessar TODOS os dashboards BI mesmo quando deveria ter acesso apenas a um.

### Raiz do Problema

A lógica de filtragem de dashboards no frontend (`useDashboards.ts`) tinha uma falha:

**Código Original:**

```typescript
if (
  user &&
  user.bi_subcategories &&
  Array.isArray(user.bi_subcategories) &&
  user.bi_subcategories.length > 0
) {
  // Filtrar por dashboards selecionados
  filteredDashboards = dashboards.filter((dash) =>
    user.bi_subcategories.includes(dash.dashboard_id),
  );
} else {
  // ❌ BUG: Se bi_subcategories está vazio/null, MOSTRAVA TODOS!
  filteredDashboards = dashboards;
}
```

**Cenário do Bug:**

1. ✅ Admin cria usuário COM setor BI
2. ❌ Admin não seleciona nenhum dashboard específico (ou seleciona e depois desmarca tudo)
3. ✅ Admin salva → `_bi_subcategories = null` no banco
4. ❌ Quando usuário loga → Vê **TODOS** os dashboards (deveria ver **NENHUM**)

## Soluções Implementadas

### 1. **Frontend: Corrigir Lógica de Filtragem** ✅

**Arquivo:** `frontend/src/pages/sectors/bi/hooks/useDashboards.ts`

Nova lógica:

```typescript
if (user && Array.isArray(user.bi_subcategories)) {
  if (user.bi_subcategories.length > 0) {
    // Filtrar por dashboards específicos
    filteredDashboards = dashboards.filter((dash) =>
      user.bi_subcategories.includes(dash.dashboard_id),
    );
  } else {
    // ✅ CORREÇÃO: Array vazio = acesso negado a NENHUM dashboard
    filteredDashboards = [];
  }
} else {
  // Se bi_subcategories é null/undefined, mostrar todos (compatibilidade)
  filteredDashboards = dashboards;
}
```

**Diferenças:**

- `null/undefined` → Mostrar todos os dashboards (sem restrição)
- `[]` (array vazio) → Mostrar NENHUM dashboard (usuário tem setor BI mas sem acesso)
- `["dash1", "dash2"]` → Filtrar apenas esses dashboards

### 2. **Frontend: Validação no Formulário de Edição** ✅

**Arquivo:** `frontend/src/pages/sectors/ti/admin/usuarios/pages.tsx`

Adicionada validação antes de salvar:

- Se admin marca setor "Portal de BI", deve selecionar pelo menos um dashboard
- Se não selecionar nenhum, mostra aviso e impede salvamento

```typescript
const hasBiSector = editSetores.includes(normalize("Portal de BI"));
if (hasBiSector && (!editBiSubcategories || editBiSubcategories.length === 0)) {
  alert(
    "⚠️ Você selecionou o setor Portal de BI mas não escolheu nenhum dashboard...",
  );
  return;
}
```

### 3. **Frontend: Validação no Formulário de Criação** ✅

**Arquivo:** `frontend/src/pages/sectors/ti/admin/usuarios/pages.tsx`

Mesma validação aplicada ao criar novo usuário.

### 4. **Backend: Diferenciar NULL vs Array Vazio** ✅

**Arquivo:** `backend/ti/services/users.py`

Modificada função `_set_bi_subcategories` para:

- Se recebe array COM items → Armazena como JSON string: `"['dash1', 'dash2']"`
- Se recebe array VAZIO `[]` → Armazena como JSON string vazio: `"[]"`
- Se recebe `null` → Armazena como NULL no banco

Isso permite distinguir entre:

- Usuário SEM restrição BI (NULL)
- Usuário COM restrição BI mas sem nenhum dashboard (array vazio JSON)

### 5. **Backend: Melhorar Logs para Debug** ✅

**Arquivo:** `backend/ti/api/usuarios.py`

Adicionados logs detalhados no endpoint PUT para rastrear:

- O que foi enviado no payload
- O que foi salvo no banco
- Como foi parseado ao retornar

## Como Testar a Correção

### Teste 1: Criar Usuário com Permissões BI Restritas

1. ✅ Acesse o painel administrativo
2. ✅ Crie um novo usuário
3. ✅ Marque o setor "Portal de BI"
4. ✅ Marque **apenas um** dashboard BI (ex: "Dashboard Vendas")
5. ✅ Salve o usuário
6. ✅ Logout
7. ✅ Faça login com esse novo usuário
8. ✅ Acesse "Portal de BI" → Deveria ver **apenas** o dashboard selecionado

### Teste 2: Editar Usuário e Alterar Permissões

1. ✅ Crie um usuário COM BI setor e um dashboard
2. ✅ Edite o usuário
3. ✅ Adicione outro dashboard no setor BI
4. ✅ Salve
5. ✅ Logout e login novamente
6. ✅ Verifique se consegue acessar AMBOS os dashboards

### Teste 3: Tentar Salvar sem Dashboard Selecionado

1. ✅ Crie um usuário SEM setor BI
2. ✅ Edite o usuário
3. ✅ Marque o setor "Portal de BI"
4. ✅ NÃO marque nenhum dashboard
5. ✅ Tente salvar
6. ✅ Deveria mostrar um aviso "⚠️ Você selecionou o setor Portal de BI mas não escolheu nenhum dashboard"

### Teste 4: Verificar Database Diretamente (Opcional)

Para usuários que querem verificar o banco de dados:

```sql
-- Ver permissões BI de um usuário
SELECT id, usuario, _bi_subcategories FROM user WHERE usuario = 'seu_usuario';
```

Possíveis valores de `_bi_subcategories`:

- `NULL` → Sem restrição BI
- `[]` → Com setor BI mas sem dashboards permitidos
- `["dashboard-id-1", "dashboard-id-2"]` → Com acesso a dashboards específicos

## Checklist de Verificação

- [ ] Usuário criado com 1 dashboard BI consegue acessar apenas esse dashboard
- [ ] Usuário editado para adicionar mais dashboards consegue acessar todos
- [ ] Usuário editado para remover um dashboard não consegue acessar mais
- [ ] Sistema previne salvar com BI setor mas sem dashboard selecionado
- [ ] Logs mostram corretamente `bi_subcategories` sendo salvo e retornado
- [ ] Dashboard vazio de um usuário BI mostra mensagem apropriada

## Arquivos Modificados

1. `frontend/src/pages/sectors/bi/hooks/useDashboards.ts` - Lógica de filtragem
2. `frontend/src/pages/sectors/ti/admin/usuarios/pages.tsx` - Validações
3. `backend/ti/services/users.py` - Diferenciação entre NULL e array vazio
4. `backend/ti/api/usuarios.py` - Logs melhorados

## Notas

- As mudanças são **retroativas**: Usuários existentes com `_bi_subcategories = NULL` continuarão vendo todos os dashboards (sem restrição)
- Novos usuários criados/editados terão `_bi_subcategories` como array JSON explícito
- Recomenda-se rerevisar permissões de usuários antigos do sistema

---

Se encontrar problemas, verifique:

1. Os logs do backend (procure por `[API]` e `[_set_bi_subcategories]`)
2. O banco de dados: `SELECT _bi_subcategories FROM user`
3. Verifique se o navegador está usando cache antigo (Ctrl+Shift+Delete)
