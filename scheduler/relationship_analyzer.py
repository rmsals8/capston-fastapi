# scheduler/relationship_analyzer.py (최적화됨)
from .utils import parse_datetime
import logging
import datetime
import json
from typing import Dict, Any, List, Optional
from .cache_manager import cached_result

# 로깅 최적화
logger = logging.getLogger('relationship_analyzer')

@cached_result("relationship_analysis", expire_seconds=600)
def analyze_schedule_relationships(voice_input: str, schedules: Dict[str, Any]) -> Dict[str, Any]:
    """일정 간 관계를 분석하는 함수 (최적화됨)"""
    all_schedules = schedules.get("fixedSchedules", []) + schedules.get("flexibleSchedules", [])
    
    # 일정이 적으면 관계 분석 생략
    if len(all_schedules) < 3:
        return {}
    
    relationships = {}
    
    # 핵심 관계 키워드만 (성능 최적화)
    relation_keywords = {
        "중간에": "between",
        "전에": "before", 
        "후에": "after",
        "다음에": "after"
    }
    
    voice_lower = voice_input.lower()
    
    # 관계 키워드 탐색 (최적화)
    for keyword, relation_type in relation_keywords.items():
        if keyword not in voice_lower:
            continue
            
        # 키워드 전후 컨텍스트 분석
        parts = voice_lower.split(keyword)
        if len(parts) < 2:
            continue
            
        before_context = parts[0]
        after_context = parts[1]
        
        # 관련된 일정 찾기 (첫 번째 매치만)
        related_schedule = None
        for schedule in all_schedules:
            schedule_name = schedule.get("name", "").lower()
            schedule_words = [word for word in schedule_name.split() if len(word) > 1]
            
            if any(word in after_context for word in schedule_words):
                related_schedule = schedule
                break
        
        if not related_schedule:
            continue
            
        # "중간에" 키워드 처리
        if relation_type == "between":
            # 앞뒤 일정 찾기
            before_schedule = None
            after_schedule = None
            
            # 앞 컨텍스트에서 일정 찾기
            for schedule in all_schedules:
                if schedule == related_schedule:
                    continue
                    
                schedule_name = schedule.get("name", "").lower()
                schedule_words = [word for word in schedule_name.split() if len(word) > 1]
                
                if any(word in before_context for word in schedule_words):
                    before_schedule = schedule
                    break
            
            # 다른 일정 찾기
            for schedule in all_schedules:
                if schedule not in [related_schedule, before_schedule]:
                    after_schedule = schedule
                    break
            
            # 관계 정보 저장
            if before_schedule and after_schedule:
                relationships[related_schedule.get("id")] = {
                    "type": "between",
                    "before_id": before_schedule.get("id"),
                    "after_id": after_schedule.get("id")
                }
            elif before_schedule:
                relationships[related_schedule.get("id")] = {
                    "type": "after",
                    "reference_id": before_schedule.get("id")
                }
        else:
            # 다른 관계 유형 처리
            reference_schedule = None
            search_context = after_context if relation_type == "before" else before_context
            
            for schedule in all_schedules:
                if schedule == related_schedule:
                    continue
                    
                schedule_name = schedule.get("name", "").lower()
                schedule_words = [word for word in schedule_name.split() if len(word) > 1]
                
                if any(word in search_context for word in schedule_words):
                    reference_schedule = schedule
                    break
            
            if reference_schedule:
                relationships[related_schedule.get("id")] = {
                    "type": relation_type,
                    "reference_id": reference_schedule.get("id")
                }
    
    return relationships

def enhance_schedule_with_relationships(voice_input: str, schedules: Dict[str, Any]) -> Dict[str, Any]:
    """일정 간 관계 정보를 적용하여 일정 개선 (최적화됨)"""
    logger.info("일정 간 관계 정보 적용 시작")
    
    # 관계 분석 (캐시 활용)
    relationships = analyze_schedule_relationships(voice_input, schedules)
    
    if not relationships:
        logger.info("적용할 관계 정보가 없음")
        return schedules
    
    # 관계 정보를 바탕으로 시간 및 우선순위 재조정
    flexible_schedules = schedules.get("flexibleSchedules", [])
    fixed_schedules = schedules.get("fixedSchedules", [])
    all_schedules = fixed_schedules + flexible_schedules
    
    for schedule_id, relation_info in relationships.items():
        # 해당 일정 찾기
        target_schedule = None
        for schedule in all_schedules:
            if schedule.get("id") == schedule_id:
                target_schedule = schedule
                break
        
        if not target_schedule:
            continue
            
        relation_type = relation_info.get("type")
        
        if relation_type == "between":
            # "중간에" 관계 처리
            before_id = relation_info.get("before_id")
            after_id = relation_info.get("after_id")
            
            before_schedule = next((s for s in all_schedules if s.get("id") == before_id), None)
            after_schedule = next((s for s in all_schedules if s.get("id") == after_id), None)
            
            if before_schedule and after_schedule:
                # 시간 조정
                before_end_str = before_schedule.get("endTime", "")
                after_start_str = after_schedule.get("startTime", "")
                
                before_end = parse_datetime(before_end_str)
                after_start = parse_datetime(after_start_str)
                
                if before_end and after_start:
                    # 사이 시간 계산
                    middle_time = before_end + (after_start - before_end) / 2
                    duration = target_schedule.get("duration", 60)
                    
                    target_schedule["startTime"] = middle_time.isoformat()
                    end_time = middle_time + datetime.timedelta(minutes=duration)
                    target_schedule["endTime"] = end_time.isoformat()
                    
                    # 우선순위 설정
                    before_priority = before_schedule.get("priority", 3)
                    after_priority = after_schedule.get("priority", 3)
                    target_schedule["priority"] = (before_priority + after_priority) / 2
                    
                    # 타입 업데이트
                    target_schedule["type"] = "FIXED"
        
        elif relation_type in ["before", "after"]:
            # "before" 또는 "after" 관계 처리
            reference_id = relation_info.get("reference_id")
            reference_schedule = next((s for s in all_schedules if s.get("id") == reference_id), None)
            
            if reference_schedule:
                duration = target_schedule.get("duration", 60)
                
                if relation_type == "before":
                    # 참조 일정 전에 위치
                    ref_start_str = reference_schedule.get("startTime")
                    ref_start = parse_datetime(ref_start_str)
                    
                    if ref_start:
                        end_time = ref_start - datetime.timedelta(minutes=30)
                        start_time = end_time - datetime.timedelta(minutes=duration)
                        
                        target_schedule["startTime"] = start_time.isoformat()
                        target_schedule["endTime"] = end_time.isoformat()
                        target_schedule["priority"] = max(1, reference_schedule.get("priority", 3) - 1)
                        target_schedule["type"] = "FIXED"
                
                elif relation_type == "after":
                    # 참조 일정 후에 위치
                    ref_end_str = reference_schedule.get("endTime")
                    ref_end = parse_datetime(ref_end_str)
                    
                    if ref_end:
                        start_time = ref_end + datetime.timedelta(minutes=30)
                        end_time = start_time + datetime.timedelta(minutes=duration)
                        
                        target_schedule["startTime"] = start_time.isoformat()
                        target_schedule["endTime"] = end_time.isoformat()
                        target_schedule["priority"] = min(5, reference_schedule.get("priority", 3) + 1)
                        target_schedule["type"] = "FIXED"
    
    # 일정 배열 재구성 (타입 변경 후 적절한 배열로 이동)
    final_fixed_schedules = []
    final_flexible_schedules = []
    
    for schedule in schedules.get("fixedSchedules", []):
        final_fixed_schedules.append(schedule)
    
    for schedule in schedules.get("flexibleSchedules", []):
        if schedule.get("type") == "FIXED" and "startTime" in schedule and "endTime" in schedule:
            final_fixed_schedules.append(schedule)
        else:
            schedule["type"] = "FLEXIBLE"  # 보장
            final_flexible_schedules.append(schedule)
    
    # 수정된 일정 배열 반환
    updated_schedules = schedules.copy()
    updated_schedules["fixedSchedules"] = final_fixed_schedules
    updated_schedules["flexibleSchedules"] = final_flexible_schedules
    
    logger.info("일정 간 관계 정보 적용 완료")
    return updated_schedules