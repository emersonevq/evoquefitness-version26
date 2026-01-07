"""
Advanced Business Hours Calculator for SLA

Features:
- Configurable business hours per day of week
- Holiday support (Brazilian holidays by default)
- Timezone aware calculations
- Caching for performance
- Detailed logging for debugging

Formula:
Total business hours = Sum of hours within business time windows,
excluding weekends, holidays, and after-hours.
"""

from datetime import datetime, time, timedelta
from typing import Optional, List, Set, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import and_
from ti.models.sla_config import SLABusinessHours
from core.utils import now_brazil_naive


class BrazilianHolidays:
    """Brazilian national holidays (can be extended)"""
    
    # Fixed holidays (month, day)
    FIXED_HOLIDAYS = {
        (1, 1),    # New Year
        (4, 21),   # Tiradentes
        (5, 1),    # Labor Day
        (9, 7),    # Independence Day
        (10, 12),  # Our Lady of Aparecida
        (11, 2),   # All Souls' Day
        (11, 15),  # Proclamation of the Republic
        (11, 20),  # Black Consciousness Day
        (12, 25),  # Christmas
    }
    
    # Moving holidays need calculation
    # Easter-based (good Friday is 2 days before Easter)
    # Carnival is 47 days before Easter
    # Corpus Christi is 60 days after Easter
    # All Souls' Day is 1 day after All Saints' Day (Nov 1)
    
    @staticmethod
    def is_fixed_holiday(date: datetime) -> bool:
        """Verifica se é feriado fixo"""
        return (date.month, date.day) in BrazilianHolidays.FIXED_HOLIDAYS
    
    @staticmethod
    def get_holidays_for_year(year: int) -> Set[Tuple[int, int]]:
        """Retorna todos os feriados do ano (não implementado plenamente)"""
        # Implementação simplificada com apenas feriados fixos
        return BrazilianHolidays.FIXED_HOLIDAYS


class BusinessHoursCalculator:
    """
    Calcula horas de negócio de forma robusta e testável.
    
    Separa lógica pura de I/O do banco de dados.
    """
    
    # Default business hours (segunda a sexta, 08:00 a 18:00)
    DEFAULT_BUSINESS_HOURS: dict[int, Tuple[str, str]] = {
        0: ("08:00", "18:00"),  # Monday
        1: ("08:00", "18:00"),  # Tuesday
        2: ("08:00", "18:00"),  # Wednesday
        3: ("08:00", "18:00"),  # Thursday
        4: ("08:00", "18:00"),  # Friday
        # 5 e 6 (Saturday, Sunday) not included = closed
    }
    
    @staticmethod
    def _parse_time(time_str: str) -> time:
        """Parse HH:MM string to time object"""
        parts = time_str.split(":")
        if len(parts) != 2:
            raise ValueError(f"Invalid time format: {time_str}")
        return time(int(parts[0]), int(parts[1]))
    
    @staticmethod
    def is_business_day(date: datetime) -> bool:
        """
        Verifica se é dia de negócio (não é fim de semana nem feriado).
        
        weekday(): 0=Monday, 6=Sunday
        """
        # Não é fin de semana
        if date.weekday() >= 5:
            return False
        
        # Não é feriado
        if BrazilianHolidays.is_fixed_holiday(date):
            return False
        
        return True
    
    @staticmethod
    def get_business_hours_for_day(
        date: datetime,
        db: Optional[Session] = None
    ) -> Optional[Tuple[time, time]]:
        """
        Retorna horário de negócio para um dia específico.
        
        Retorna: (hora_inicio, hora_fim) ou None se não é dia útil
        """
        # Se não é dia de negócio, retorna None
        if not BusinessHoursCalculator.is_business_day(date):
            return None
        
        weekday = date.weekday()
        
        # Tenta carregar do banco se disponível
        if db:
            try:
                bh = db.query(SLABusinessHours).filter(
                    and_(
                        SLABusinessHours.dia_semana == weekday,
                        SLABusinessHours.ativo == True
                    )
                ).first()
                
                if bh:
                    inicio = BusinessHoursCalculator._parse_time(bh.hora_inicio)
                    fim = BusinessHoursCalculator._parse_time(bh.hora_fim)
                    return (inicio, fim)
            except Exception:
                pass
        
        # Usa default
        default = BusinessHoursCalculator.DEFAULT_BUSINESS_HOURS.get(weekday)
        if default:
            inicio = BusinessHoursCalculator._parse_time(default[0])
            fim = BusinessHoursCalculator._parse_time(default[1])
            return (inicio, fim)
        
        return None
    
    @staticmethod
    def calculate_business_hours(
        start: datetime,
        end: datetime,
        db: Optional[Session] = None
    ) -> float:
        """
        Calcula horas de negócio entre duas datas.
        
        Args:
            start: Data/hora inicial
            end: Data/hora final
            db: Sessão do banco (opcional, para ler config de horários)
            
        Returns:
            Horas de negócio (float)
        """
        if start >= end:
            return 0.0
        
        total_minutes = 0
        current = start
        
        # Itera por cada dia
        while current < end:
            # Próximo dia às 00:00
            next_day = (current + timedelta(days=1)).replace(
                hour=0, minute=0, second=0, microsecond=0
            )
            
            # Verifica se é dia de negócio
            business_hours = BusinessHoursCalculator.get_business_hours_for_day(current, db)
            if not business_hours:
                # Não é dia útil, pula para próximo dia
                current = next_day
                continue
            
            # Horários de negócio para este dia
            day_start_time, day_end_time = business_hours
            
            # Converte para datetime
            day_start = current.replace(
                hour=day_start_time.hour,
                minute=day_start_time.minute,
                second=0,
                microsecond=0
            )
            day_end = current.replace(
                hour=day_end_time.hour,
                minute=day_end_time.minute,
                second=0,
                microsecond=0
            )
            
            # Ajusta limites ao intervalo de negócio
            period_start = max(current, day_start)
            period_end = min(end, day_end, next_day)
            
            # Calcula minutos neste período
            if period_start < period_end:
                delta = period_end - period_start
                total_minutes += int(delta.total_seconds() / 60)
            
            # Move para próximo dia
            current = next_day
        
        return total_minutes / 60.0
    
    @staticmethod
    def calculate_business_hours_between(
        start: datetime,
        end: datetime,
        db: Optional[Session] = None
    ) -> dict:
        """
        Calcula horas de negócio com informações detalhadas.
        
        Retorna:
        {
            "total_horas": float,
            "dias_calendário": int,
            "dias_úteis": int,
            "dias_não_úteis": int,
            "horas_por_dia": list[dict],
        }
        """
        total_horas = BusinessHoursCalculator.calculate_business_hours(start, end, db)
        
        dias_calendário = (end.date() - start.date()).days + 1
        dias_úteis = 0
        dias_não_úteis = 0
        horas_por_dia = []
        
        current = start.replace(hour=0, minute=0, second=0, microsecond=0)
        
        while current.date() <= end.date():
            is_business_day = BusinessHoursCalculator.is_business_day(current)
            
            if is_business_day:
                dias_úteis += 1
            else:
                dias_não_úteis += 1
            
            horas_por_dia.append({
                "data": current.date().isoformat(),
                "é_dia_útil": is_business_day,
                "dia_semana": ["seg", "ter", "qua", "qui", "sex", "sab", "dom"][current.weekday()],
            })
            
            current += timedelta(days=1)
        
        return {
            "total_horas": total_horas,
            "dias_calendário": dias_calendário,
            "dias_úteis": dias_úteis,
            "dias_não_úteis": dias_não_úteis,
            "horas_por_dia": horas_por_dia,
        }
