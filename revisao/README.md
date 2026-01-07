# Arquivos de SLA - Revisão Completa

Pasta contendo todos os arquivos relacionados ao cálculo e gerenciamento de SLA do sistema.

## 📋 Conteúdo

### Backend - Cálculos e Lógica

#### `backend_ti_services_sla.py`

- **Classe**: `SLACalculator`
- **Responsabilidades principais**:
  - `calculate_business_hours()` - Calcula horas úteis entre duas datas
  - `calculate_business_hours_excluding_paused()` - Calcula horas úteis excluindo períodos em "Em análise"
  - `get_sla_status()` - Retorna status SLA completo de um chamado (resposta + resolução)
  - `record_sla_history()` - Persiste histórico de SLA
  - `is_frozen()` - Verifica se chamado está congelado
  - `get_sla_config_by_priority()` - Obtém config de SLA por prioridade

- **Linhas**: 383
- **Linguagem**: Python

#### `backend_ti_services_sla_cache.py`

- **Classe**: `SLACacheManager`
- **Responsabilidades principais**:
  - `get()` / `set()` - Cache em memória + banco de dados
  - `invalidate()` - Remove múltiplas chaves de cache
  - `invalidate_by_chamado()` - Invalida caches relacionados a um chamado
  - `invalidate_all_sla()` - Invalida todos os caches SLA
  - `clear_expired()` - Limpa caches expiradosss
  - `get_stats()` - Retorna estatísticas do cache

- **TTLs configurados**:
  - `sla_compliance_24h`: 5 minutos
  - `sla_compliance_mes`: 15 minutos
  - `sla_distribution`: 15 minutos
  - `tempo_resposta_*`: 5-15 minutos
  - `chamado_sla_status`: 2 minutos

- **Linhas**: 302
- **Linguagem**: Python

#### `backend_ti_services_metrics.py`

- **Classe**: `MetricsCalculator`
- **Responsabilidades principais**:
  - `get_sla_compliance_24h()` / `_calculate_sla_compliance_24h()` - % SLA das últimas 24h
  - `get_sla_compliance_mes()` / `_calculate_sla_compliance_mes()` - % SLA do mês
  - `get_sla_distribution()` - Distribuição dentro/fora SLA
  - `get_abertos_agora()` - Chamados ativos no momento
  - `get_chamados_abertos_hoje()` - Chamados abertos hoje
  - `get_dashboard_metrics()` - Agregação de todas as métricas

- **Otimizações**:
  - Carrega configs de SLA uma única vez (sem N+1)
  - Pré-carrega todos os históricos em bulk
  - Usa cache local para evitar queries

- **Linhas**: 371
- **Linguagem**: Python

#### `backend_ti_services_sla_validator.py`

- **Classe**: `SLAValidator`
- **Responsabilidades principais**:
  - `validar_configuracao()` - Valida config de SLA individual
  - `validar_horario_comercial()` - Valida horários comerciais
  - `validar_todas_configuracoes()` - Valida todas as configs do banco
  - `validar_dados_chamado()` - Valida dados de um chamado específico

- **Validações**:
  - Tempo de resposta: 30 minutos - 72 horas
  - Tempo de resolução: 1 hora - 168 horas
  - Sequência de datas
  - Horários válidos (HH:MM)

- **Linhas**: 265
- **Linguagem**: Python

## 🔗 Relacionamentos

```
SLACalculator (cálculos)
    ↓
SLACacheManager (cache/performance)
    ↓
MetricsCalculator (agregação)
    ↓
API endpoints → Frontend
```

## 📊 Fluxo de Dados

1. **Cálculo de SLA** (SLACalculator)
   - Recebe chamado
   - Calcula horas úteis
   - Valida contra config SLA
   - Retorna status (ok/vencido/em_andamento/congelado)

2. **Cache** (SLACacheManager)
   - Armazena resultados em memória
   - Persiste em banco de dados
   - TTL por tipo de métrica
   - Invalidação inteligente por chamado

3. **Métricas** (MetricsCalculator)
   - Tenta cache primeiro
   - Calcula em bulk (otimizado)
   - Armazena resultado em cache
   - Retorna para dashboard

## 🎯 Pontos Críticos

- **Business Hours**: Exclui fins de semana e fora do horário comercial
- **Pausa em Análise**: Desconta tempo quando chamado está em "Em análise"
- **Cache Inteligente**: Invalida apenas caches relacionados ao chamado
- **Bulk Operations**: Carrega dados uma única vez para evitar N+1

## 📝 Notas

- Todos os cálculos de tempo usam **horas de negócio** (não clock time)
- Cache em memória + banco = resiliência em caso de restart
- Validação prévia evita cálculos incorretos
- Histórico persiste para auditoria

## 🔧 Arquivo para Revisão

Recomendações para revisão:

1. Verificar lógica de exclusão de "Em análise" em `calculate_business_hours_excluding_paused()`
2. Validar TTLs de cache versus frequência de atualizações
3. Testar performance com grandes volumes (1000+ chamados)
4. Revisar invalidações para garantir consistência
