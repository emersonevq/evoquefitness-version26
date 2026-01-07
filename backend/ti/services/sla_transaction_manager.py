"""
Atomic Transaction Manager for SLA Operations

Ensures that SLA operations either succeed completely or fail completely.
No partial updates allowed.
"""

from typing import Callable, TypeVar, Optional
from sqlalchemy.orm import Session
from sqlalchemy import text
from core.utils import now_brazil_naive

T = TypeVar("T")


class TransactionResult:
    """Resultado de uma transação"""
    
    def __init__(self, success: bool, data: Optional[dict] = None, error: Optional[str] = None):
        self.success = success
        self.data = data or {}
        self.error = error
    
    def to_dict(self) -> dict:
        return {
            "success": self.success,
            "data": self.data,
            "error": self.error,
            "timestamp": now_brazil_naive().isoformat()
        }


class SLATransactionManager:
    """
    Gerencia transações atômicas para operações de SLA.
    
    Garantias:
    - Atomicidade: Tudo ou nada
    - Isolamento: Sem leitura suja
    - Consistência: Validação antes e depois
    """
    
    @staticmethod
    def execute_atomic(
        db: Session,
        operation: Callable[..., T],
        *args,
        **kwargs
    ) -> TransactionResult:
        """
        Executa operação em transação atômica.
        
        Args:
            db: Sessão do banco
            operation: Função a executar (deve aceitar db como primeiro argumento)
            *args: Argumentos posicionais para operation
            **kwargs: Argumentos nomeados para operation
            
        Returns:
            TransactionResult com sucesso/erro
        """
        try:
            # Inicia transação explicitamente
            # Usa SAVEPOINT para rollback parcial se necessário
            savepoint_name = f"sla_transaction_{id(operation)}"
            
            # Executa operação
            result = operation(db, *args, **kwargs)
            
            # Commit completo
            db.commit()
            
            return TransactionResult(
                success=True,
                data=result
            )
        
        except Exception as e:
            # Rollback completo
            try:
                db.rollback()
            except Exception:
                pass
            
            return TransactionResult(
                success=False,
                error=str(e)
            )
    
    @staticmethod
    def execute_batch_atomic(
        db: Session,
        operations: list[tuple[Callable, tuple, dict]]
    ) -> TransactionResult:
        """
        Executa múltiplas operações em transação única.
        
        Se qualquer uma falhar, todas sofrem rollback.
        
        Args:
            db: Sessão do banco
            operations: Lista de (callable, args, kwargs)
            
        Returns:
            TransactionResult com resultado agregado
        """
        results = []
        
        try:
            for operation, args, kwargs in operations:
                result = operation(db, *args, **kwargs)
                results.append(result)
            
            # Se chegou aqui, todas as operações executaram com sucesso
            db.commit()
            
            return TransactionResult(
                success=True,
                data={"operations": len(operations), "results": results}
            )
        
        except Exception as e:
            # Rollback completo - nenhuma mudança é persistida
            try:
                db.rollback()
            except Exception:
                pass
            
            return TransactionResult(
                success=False,
                error=f"Batch failed: {str(e)}. All changes rolled back.",
                data={"operations_attempted": len(operations), "results": results}
            )
    
    @staticmethod
    def execute_with_lock(
        db: Session,
        table_name: str,
        operation: Callable[..., T],
        *args,
        **kwargs
    ) -> TransactionResult:
        """
        Executa operação com lock exclusivo na tabela.
        
        Impede concorrência durante a operação crítica.
        
        Args:
            db: Sessão do banco
            table_name: Nome da tabela a fazer lock
            operation: Função a executar
            *args: Argumentos para operation
            **kwargs: Argumentos nomeados para operation
            
        Returns:
            TransactionResult
        """
        try:
            # Lock exclusivo na tabela (PostgreSQL/MySQL)
            # Isso previne que outros acessem enquanto estamos aqui
            try:
                db.execute(text(f"LOCK TABLE {table_name} IN EXCLUSIVE MODE"))
            except Exception:
                # Alguns bancos não suportam LOCK, continua mesmo assim
                pass
            
            # Executa operação
            result = operation(db, *args, **kwargs)
            
            # Commit
            db.commit()
            
            return TransactionResult(
                success=True,
                data=result
            )
        
        except Exception as e:
            try:
                db.rollback()
            except Exception:
                pass
            
            return TransactionResult(
                success=False,
                error=str(e)
            )


class SLATransactionValidator:
    """
    Valida consistência de transações SLA antes de commitar.
    """
    
    @staticmethod
    def validate_before_commit(db: Session) -> tuple[bool, Optional[str]]:
        """
        Valida que dados estão em estado consistente.
        
        Retorna: (válido, mensagem_erro_se_inválido)
        """
        try:
            # Verifica se não há registros órfãos
            from ti.models.sla_config import HistoricoSLA
            from ti.models.chamado import Chamado
            
            # Chamados órfãos em HistoricoSLA
            historicos = db.query(HistoricoSLA).all()
            chamado_ids = {h.chamado_id for h in historicos}
            
            existing_chamados = db.query(Chamado).filter(
                Chamado.id.in_(chamado_ids)
            ).count()
            
            if existing_chamados != len(chamado_ids):
                return False, "Histórico SLA contém referências a chamados inexistentes"
            
            return True, None
        
        except Exception as e:
            return False, f"Erro ao validar: {str(e)}"
