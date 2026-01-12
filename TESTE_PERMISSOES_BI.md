# Teste de Diagnóstico - Permissões BI

## O Que Vamos Fazer

Vamos rastrear EXATAMENTE o que está acontecendo quando você:
1. Seleciona 1 dashboard para um usuário
2. Salva
3. Verifica se foi realmente salvo no banco
4. Faz login e tenta acessar BI

## Passo 1: Identificar um User ID

Você precisa de um user_id para testar. Pode ser qualquer usuário existente.

Se não souber, execute este comando no banco:
```sql
SELECT id, usuario, email FROM user LIMIT 5;
```

Copie um `id` dele. Vamos usar como `{USER_ID}` nos exemplos abaixo.

## Passo 2: Verificar o Estado Inicial

Faça uma requisição para ver o estado ATUAL das permissões:

```bash
curl http://localhost:8000/api/test/bi-check/{USER_ID}
```

Exemplo resposta:
```json
{
  "user_id": 5,
  "usuario": "admin",
  "email": "admin@example.com",
  "_bi_subcategories_raw": null,
  "_bi_subcategories_parsed": null
}
```

**Anote** se está `null` ou se tem algum valor.

## Passo 3: Usar o Teste Automático

Vamos forçar salvar as permissões corretamente usando o endpoint de teste:

```bash
curl -X POST http://localhost:8000/api/test/bi-fix/{USER_ID} \
  -H "Content-Type: application/json" \
  -d '{"dashboard_ids": ["dashboard_123"]}'
```

**Substitua `dashboard_123` por um ID real de dashboard!**

Para saber que dashboard IDs existem, acesse:
```bash
curl http://localhost:8000/api/powerbi/db/dashboards
```

Copie um `dashboard_id` real e use no comando acima.

### Exemplo Completo (suponha que exista dashboard com ID "power-bi-dashboard-001"):

```bash
curl -X POST http://localhost:8000/api/test/bi-fix/5 \
  -H "Content-Type: application/json" \
  -d '{"dashboard_ids": ["power-bi-dashboard-001"]}'
```

**Resposta esperada:**
```json
{
  "status": "ok",
  "user_id": 5,
  "saved_to_db": "\"[\\\"power-bi-dashboard-001\\\"]\"",
  "parsed": ["power-bi-dashboard-001"],
  "message": "Salvo com sucesso. Agora faça login e verifique se as permissões aparecem."
}
```

## Passo 4: Verificar se Foi Salvo

Execute novamente o check:

```bash
curl http://localhost:8000/api/test/bi-check/5
```

Resposta esperada:
```json
{
  "user_id": 5,
  "_bi_subcategories_raw": "[\"power-bi-dashboard-001\"]",
  "_bi_subcategories_parsed": ["power-bi-dashboard-001"]
}
```

**Se ainda estiver `null`, há um problema de salvamento.**

## Passo 5: Fazer Login

1. Deslogue de qualquer conta
2. Faça login COM ESSE USUÁRIO (id=5 no exemplo)
3. Vá para o Portal de BI
4. **Deveria ver APENAS 1 dashboard**

Se ver TODOS os dashboards = **o problema está no frontend ou na lógica de autenticação.**

## Passo 6: Consultar os Logs do Backend

Enquanto você estiver testando, olhe os logs do backend para mensagens com:
- `[API-UPDATE]` - Logs da atualização
- `[_set_bi_subcategories]` - Logs do salvamento
- `[AUTH]` - Logs de autenticação

## Se Algo Estiver Errado

Se no Passo 4 `_bi_subcategories_raw` ainda estiver `null`:
1. Abra o backend em modo debug
2. Execute o POST do Passo 3 novamente
3. Procure por `[TEST-BI-FIX]` nos logs
4. Envie os logs para diagnóstico

Se no Passo 5 ainda ver todos os dashboards:
1. Abra o navegador (F12)
2. Console do navegador deve mostrar logs com `[BI]`
3. Procure por `[BI] 🔐 Filtrando dashboards`
4. Verifique se `bi_subcategories` está preenchido

## Resumo Rápido dos Testes

```bash
# 1. Check inicial
curl http://localhost:8000/api/test/bi-check/5

# 2. Forçar salvar (substitua dashboard_123)
curl -X POST http://localhost:8000/api/test/bi-fix/5 \
  -H "Content-Type: application/json" \
  -d '{"dashboard_ids": ["dashboard_123"]}'

# 3. Verificar se salvou
curl http://localhost:8000/api/test/bi-check/5

# 4. Se salvou, fazer login como esse usuário
# 5. Ir para BI Portal
# 6. Deve ver APENAS 1 dashboard
```

## Importante

- Os endpoints de teste acima não alteram nada via interface gráfica
- Eles salvam DIRETO no banco
- Use para testar se o salvamento/carregamento funciona em geral

Se o teste automático funciona mas o admin interface não funciona, o problema está especificamente na UI de admin.
