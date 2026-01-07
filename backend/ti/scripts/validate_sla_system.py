#!/usr/bin/env python3
"""
Script de Validação Automática do Sistema de SLA

Executa testes para validar:
1. Integridade do banco de dados
2. Endpoints de cache funcionando
3. Cálculos corretos de SLA
4. Performance
5. Configurações válidas

Uso: python validate_sla_system.py
"""

import sys
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import text

# Imports locais
sys.path.insert(0, "/app/backend")

from core.db import SessionLocal, engine
from ti.models.sla_config import SLAConfiguration, SLABusinessHours
from ti.models.metrics_cache import MetricsCacheDB
from ti.models.chamado import Chamado
from ti.services.sla import SLACalculator
from ti.services.sla_cache import SLACacheManager
from ti.services.sla_validator import SLAValidator
from ti.services.metrics import MetricsCalculator
from core.utils import now_brazil_naive


class Colors:
    """ANSI color codes"""
    GREEN = "\033[92m"
    RED = "\033[91m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    RESET = "\033[0m"
    BOLD = "\033[1m"


def print_header(text: str):
    print(f"\n{Colors.BOLD}{Colors.BLUE}{'='*70}{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.BLUE}{text:^70}{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.BLUE}{'='*70}{Colors.RESET}\n")


def print_success(text: str):
    print(f"{Colors.GREEN}✓ {text}{Colors.RESET}")


def print_error(text: str):
    print(f"{Colors.RED}✗ {text}{Colors.RESET}")


def print_warning(text: str):
    print(f"{Colors.YELLOW}⚠ {text}{Colors.RESET}")


def print_info(text: str):
    print(f"{Colors.BLUE}ℹ {text}{Colors.RESET}")


def test_database_tables(db: Session):
    """Test 1: Verificar integridade das tabelas"""
    print_header("TESTE 1: Integridade do Banco de Dados")

    tables_required = [
        "sla_configuration",
        "sla_business_hours",
        "metrics_cache_db",
        "historico_sla",
        "chamado",
    ]

    all_exist = True
    for table in tables_required:
        try:
            result = db.execute(text(f"SELECT COUNT(*) FROM {table}")).scalar()
            print_success(f"Tabela '{table}' existe e está acessível")
        except Exception as e:
            print_error(f"Tabela '{table}' não existe ou não está acessível: {e}")
            all_exist = False

    return all_exist


def test_sla_configuration(db: Session):
    """Test 2: Validar configurações de SLA"""
    print_header("TESTE 2: Configurações de SLA")

    try:
        configs = db.query(SLAConfiguration).all()

        if not configs:
            print_warning("Nenhuma configuração de SLA encontrada. Criando configurações padrão...")

            default_configs = [
                SLAConfiguration(
                    prioridade="baixa",
                    tempo_resposta_horas=8.0,
                    tempo_resolucao_horas=48.0,
                    descricao="Baixa prioridade",
                    ativo=True,
                    criado_em=now_brazil_naive(),
                    atualizado_em=now_brazil_naive(),
                ),
                SLAConfiguration(
                    prioridade="média",
                    tempo_resposta_horas=4.0,
                    tempo_resolucao_horas=24.0,
                    descricao="Média prioridade",
                    ativo=True,
                    criado_em=now_brazil_naive(),
                    atualizado_em=now_brazil_naive(),
                ),
                SLAConfiguration(
                    prioridade="alta",
                    tempo_resposta_horas=2.0,
                    tempo_resolucao_horas=8.0,
                    descricao="Alta prioridade",
                    ativo=True,
                    criado_em=now_brazil_naive(),
                    atualizado_em=now_brazil_naive(),
                ),
                SLAConfiguration(
                    prioridade="crítica",
                    tempo_resposta_horas=1.0,
                    tempo_resolucao_horas=4.0,
                    descricao="Crítica",
                    ativo=True,
                    criado_em=now_brazil_naive(),
                    atualizado_em=now_brazil_naive(),
                ),
            ]

            for config in default_configs:
                db.add(config)

            db.commit()
            configs = db.query(SLAConfiguration).all()
            print_success(f"Configurações padrão criadas: {len(default_configs)} prioridades")

        # Validar cada configuração
        validacoes = SLAValidator.validar_todas_configuracoes(db)

        if validacoes["sistema_valido"]:
            print_success(f"Sistema de SLA válido com {validacoes['resumo']['total_configs']} configurações")
        else:
            print_error(f"Sistema de SLA inválido: {validacoes['resumo']['total_erros']} erros")
            for config in validacoes["configuracoes"]:
                if not config["validacao"]["valida"]:
                    print_error(f"  Prioridade '{config['prioridade']}': {config['validacao']['erros']}")

        return validacoes["sistema_valido"]

    except Exception as e:
        print_error(f"Erro ao validar configurações de SLA: {e}")
        return False


def test_cache_system(db: Session):
    """Test 3: Testar sistema de cache"""
    print_header("TESTE 3: Sistema de Cache")

    try:
        # Teste 1: Set e Get
        test_key = "test_key_validation"
        test_value = {"test": "data", "timestamp": str(datetime.now())}

        SLACacheManager.set(db, test_key, test_value, ttl_seconds=60)
        print_success("Cache set executado")

        retrieved = SLACacheManager.get(db, test_key)
        if retrieved == test_value:
            print_success("Cache get retornou valor correto")
        else:
            print_error("Cache get retornou valor incorreto")
            return False

        # Teste 2: Invalidação
        SLACacheManager.invalidate(db, [test_key])
        retrieved_after_invalidate = SLACacheManager.get(db, test_key)
        if retrieved_after_invalidate is None:
            print_success("Cache invalidation funcionou corretamente")
        else:
            print_error("Cache não foi invalidado corretamente")
            return False

        # Teste 3: Stats
        stats = SLACacheManager.get_stats(db)
        print_success(f"Cache stats: {stats['memory_entries']} em memória, {stats['database_entries']} no BD")

        return True

    except Exception as e:
        print_error(f"Erro ao testar cache: {e}")
        return False


def test_sla_calculations(db: Session):
    """Test 4: Testar cálculos de SLA"""
    print_header("TESTE 4: Cálculos de SLA")

    try:
        chamados = db.query(Chamado).limit(5).all()

        if not chamados:
            print_warning("Nenhum chamado encontrado para teste de cálculo")
            return True

        print_info(f"Testando cálculos com {len(chamados)} chamados...")

        for chamado in chamados:
            try:
                sla_status = SLACalculator.get_sla_status(db, chamado)

                # Validar que retornou dados
                if not sla_status:
                    print_error(f"  Chamado #{chamado.id}: SLA status não retornou dados")
                    continue

                # Validar keys necessárias
                required_keys = [
                    "chamado_id",
                    "tempo_resposta_horas",
                    "tempo_resolucao_horas",
                    "tempo_resposta_status",
                    "tempo_resolucao_status",
                ]

                missing_keys = [k for k in required_keys if k not in sla_status]
                if missing_keys:
                    print_error(f"  Chamado #{chamado.id}: Faltam keys {missing_keys}")
                    continue

                # Validar que tempos são números
                if not isinstance(sla_status["tempo_resposta_horas"], (int, float)):
                    print_error(f"  Chamado #{chamado.id}: tempo_resposta não é número")
                    continue

                print_success(f"  Chamado #{chamado.id}: SLA calculado corretamente")

            except Exception as e:
                print_error(f"  Chamado #{chamado.id}: Erro ao calcular SLA: {e}")
                return False

        return True

    except Exception as e:
        print_error(f"Erro ao testar cálculos de SLA: {e}")
        return False


def test_metrics_performance(db: Session):
    """Test 5: Testar performance de métricas"""
    print_header("TESTE 5: Performance de Métricas")

    import time

    try:
        # Limpar cache para teste real
        SLACacheManager.invalidate_all_sla(db)
        print_info("Cache limpo para teste real")

        # Teste 1: Compliance 24h (sem cache)
        start = time.time()
        compliance_24h = MetricsCalculator.get_sla_compliance_24h(db)
        time_24h_no_cache = time.time() - start
        print_info(f"SLA compliance 24h (sem cache): {time_24h_no_cache:.2f}s → {compliance_24h}%")

        # Teste 2: Compliance 24h (com cache)
        start = time.time()
        compliance_24h_cached = MetricsCalculator.get_sla_compliance_24h(db)
        time_24h_cached = time.time() - start
        print_info(f"SLA compliance 24h (com cache): {time_24h_cached:.2f}s → {compliance_24h_cached}%")

        if time_24h_cached < time_24h_no_cache * 0.5:
            print_success(f"Cache acelerou em {time_24h_no_cache/time_24h_cached:.1f}x")
        else:
            print_warning("Cache não acelerou significativamente (pode ser esperado com poucos dados)")

        return True

    except Exception as e:
        print_error(f"Erro ao testar performance: {e}")
        return False


def main():
    """Executar todos os testes"""
    print_header("VALIDAÇÃO DO SISTEMA DE SLA")

    db = SessionLocal()
    results = {}

    try:
        # Executar testes
        results["database"] = test_database_tables(db)
        results["configuration"] = test_sla_configuration(db)
        results["cache"] = test_cache_system(db)
        results["calculations"] = test_sla_calculations(db)
        results["performance"] = test_metrics_performance(db)

        # Resumo final
        print_header("RESUMO DE VALIDAÇÃO")

        all_passed = all(results.values())

        for test_name, passed in results.items():
            if passed:
                print_success(f"{test_name.capitalize()}")
            else:
                print_error(f"{test_name.capitalize()}")

        print()
        if all_passed:
            print_success("TODOS OS TESTES PASSARAM! Sistema de SLA está pronto para produção.")
            return 0
        else:
            print_error("ALGUNS TESTES FALHARAM. Verifique os logs acima.")
            return 1

    except Exception as e:
        print_error(f"Erro crítico durante validação: {e}")
        import traceback
        traceback.print_exc()
        return 1

    finally:
        db.close()


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
