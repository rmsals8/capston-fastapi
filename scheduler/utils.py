# scheduler/utils.py (최적화됨)

import datetime
import logging
from typing import Dict, Any, Optional, List
from functools import lru_cache

logger = logging.getLogger('scheduler.utils')

@lru_cache(maxsize=1000)
def parse_datetime(dt_str: str) -> Optional[datetime.datetime]:
    """날짜 문자열을 datetime 객체로 변환 (캐시됨)"""
    if not dt_str:
        return None
        
    try:
        return datetime.datetime.fromisoformat(dt_str.replace('Z', '+00:00'))
    except Exception:
        try:
            return datetime.datetime.strptime(dt_str, "%Y-%m-%dT%H:%M:%S")
        except Exception:
            return None

def detect_and_resolve_time_conflicts(schedules: Dict[str, Any], min_gap_minutes=15) -> Dict[str, Any]:
    """
    최적화된 일정 간 시간 충돌 감지 및 해결 함수
    
    Args:
        schedules: 일정 데이터
        min_gap_minutes: 일정 사이에 필요한 최소 간격 (분)
    
    Returns:
        충돌이 해결된 일정 데이터
    """
    logger.info("일정 간 시간 충돌 감지 및 해결 시작")
    
    # 시간이 지정된 일정만 수집
    all_timed_schedules = []
    
    for schedule in schedules.get("fixedSchedules", []):
        if "startTime" in schedule and "endTime" in schedule:
            all_timed_schedules.append(schedule)
    
    for schedule in schedules.get("flexibleSchedules", []):
        if "startTime" in schedule and "endTime" in schedule:
            all_timed_schedules.append(schedule)
    
    if len(all_timed_schedules) < 2:
        logger.info("시간이 지정된 일정이 2개 미만, 충돌 분석 생략")
        return schedules
    
    # 우선순위와 시간순으로 정렬
    all_timed_schedules.sort(key=lambda s: (s.get("priority", 999), parse_datetime(s.get("startTime", ""))))
    
    # 충돌 감지 및 해결 (최적화된 알고리즘)
    conflicts_resolved = 0
    
    # 한 번의 패스로 충돌 해결
    for i in range(len(all_timed_schedules) - 1):
        current = all_timed_schedules[i]
        next_schedule = all_timed_schedules[i + 1]
        
        current_start = parse_datetime(current.get("startTime", ""))
        current_end = parse_datetime(current.get("endTime", ""))
        next_start = parse_datetime(next_schedule.get("startTime", ""))
        next_end = parse_datetime(next_schedule.get("endTime", ""))
        
        # 충돌 검사
        if (current_start and current_end and next_start and next_end and 
            current_end > next_start):
            
            logger.info(f"충돌 감지: '{current.get('name')}' 와 '{next_schedule.get('name')}'")
            
            # 다음 일정을 현재 일정 이후로 이동 (간단한 해결)
            duration_minutes = int((next_end - next_start).total_seconds() / 60)
            new_start = current_end + datetime.timedelta(minutes=min_gap_minutes)
            new_end = new_start + datetime.timedelta(minutes=duration_minutes)
            
            next_schedule["startTime"] = new_start.isoformat()
            next_schedule["endTime"] = new_end.isoformat()
            conflicts_resolved += 1
            
            logger.info(f"충돌 해결: '{next_schedule.get('name')}' 시간 조정")
    
    # 일정 타입에 따라 재분류
    fixed_schedules = [s for s in all_timed_schedules if s.get("type") == "FIXED"]
    flexible_schedules = []
    
    # 기존 유연 일정 중 시간이 없는 일정 보존
    for s in schedules.get("flexibleSchedules", []):
        if "startTime" not in s or "endTime" not in s:
            flexible_schedules.append(s)
        elif s.get("type") != "FIXED":
            flexible_schedules.append(s)
    
    logger.info(f"충돌 해결 완료: {conflicts_resolved}개 충돌 해결됨")
    
    # 결과 반환
    result = schedules.copy()
    result["fixedSchedules"] = fixed_schedules
    result["flexibleSchedules"] = flexible_schedules
    
    return result