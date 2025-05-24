# scheduler/priority_analyzer.py (최적화됨)

import logging
from typing import Dict, Any, List
import json 
from .cache_manager import cached_result

# 로깅 최적화
logger = logging.getLogger('priority_analyzer')

@cached_result("schedule_priority_format", expire_seconds=300)
def format_schedules_for_priority(schedules: Dict[str, Any]) -> str:
    """일정 정보를 우선순위 분석용으로 포맷팅 (캐시됨)"""
    schedule_info = []
    
    for s in schedules.get("fixedSchedules", []):
        detail = f"ID: {s.get('id', '')}, 이름: {s.get('name', '')}, 유형: 고정, 시간: {s.get('startTime', '')} ~ {s.get('endTime', '')}"
        schedule_info.append(detail)
    
    for s in schedules.get("flexibleSchedules", []):
        time_info = ""
        if "startTime" in s and "endTime" in s:
            time_info = f", 시간: {s.get('startTime', '')} ~ {s.get('endTime', '')}"
        
        detail = f"ID: {s.get('id', '')}, 이름: {s.get('name', '')}, 유형: 유연{time_info}"
        schedule_info.append(detail)
    
    return "\n".join(schedule_info)

def analyze_schedule_priorities(priority_chain, voice_input: str, extracted_schedules: Dict[str, Any]) -> Dict[str, Any]:
    """메시지와 추출된 일정을 분석하여 우선순위 결정 (최적화됨)"""
    # 일정이 적으면 LLM 호출 생략
    total_schedules = len(extracted_schedules.get("fixedSchedules", [])) + len(extracted_schedules.get("flexibleSchedules", []))
    if total_schedules <= 2:
        return {
            "schedule_priorities": [],
            "sequence_expressions": [],
            "reasoning": "일정 수가 적어 기본 우선순위 적용"
        }
    
    # 일정 정보 포맷팅 (캐시 활용)
    formatted_schedules = format_schedules_for_priority(extracted_schedules)
    
    # LLM 체인 실행
    try:
        result = priority_chain.invoke({
            "input": voice_input,
            "extracted_schedules": formatted_schedules
        })
        return result
    except Exception as e:
        logger.error(f"LLM 체인 호출 오류: {str(e)}")
        return {
            "schedule_priorities": [],
            "sequence_expressions": [],
            "reasoning": f"우선순위 분석 실패: {str(e)}"
        }

def apply_priorities(priority_chain, voice_input: str, extracted_schedules: Dict[str, Any]) -> Dict[str, Any]:
    """분석된 우선순위를 일정에 적용 (최적화됨)"""
    logger.info("우선순위 적용 시작")
    
    # 최적화된 순서 키워드 (핵심만)
    sequence_keywords = {
        "먼저": 1,
        "처음": 1,
        "그 다음": 2,
        "마지막": 5
    }
    
    # 고정 일정 처리 (시간순 우선순위)
    fixed_schedules = extracted_schedules.get("fixedSchedules", [])
    for i, schedule in enumerate(fixed_schedules):
        schedule["priority"] = i + 1
    
    # 유연 일정 처리
    flexible_schedules = extracted_schedules.get("flexibleSchedules", [])
    
    # 일정이 많을 때만 LLM 분석 사용
    if len(flexible_schedules) > 2:
        priority_info = analyze_schedule_priorities(priority_chain, voice_input, extracted_schedules)
        
        # 우선순위 정보를 딕셔너리로 변환
        priority_map = {}
        for item in priority_info.get("schedule_priorities", []):
            if "id" in item and "priority" in item:
                priority_map[item["id"]] = item["priority"]
        
        # LLM 분석 결과 적용
        for schedule in flexible_schedules:
            schedule_id = schedule.get("id")
            if schedule_id in priority_map:
                schedule["priority"] = priority_map[schedule_id]
    
    # 직접 텍스트 분석으로 보강 (최적화됨)
    voice_lower = voice_input.lower()
    
    # 키워드 기반 우선순위 설정
    for schedule in flexible_schedules:
        # 기본 우선순위가 그대로인 경우에만 처리
        if schedule.get("priority", 3) == 3:
            schedule_name = schedule.get("name", "").lower()
            
            # 간단한 키워드 매칭
            for keyword, priority_value in sequence_keywords.items():
                if keyword in voice_lower:
                    # 키워드 이후에 일정명이 언급되는지 확인
                    keyword_parts = voice_lower.split(keyword)
                    if len(keyword_parts) > 1:
                        after_keyword = keyword_parts[1]
                        schedule_words = [word for word in schedule_name.split() if len(word) > 1]
                        
                        if any(word in after_keyword for word in schedule_words):
                            schedule["priority"] = priority_value
                            break
    
    # 언급 순서 기반 우선순위 (간단화)
    voice_words = voice_lower.split()
    mentioned_order = []
    
    for schedule in flexible_schedules:
        if schedule.get("priority", 3) == 3:  # 아직 우선순위가 설정되지 않은 경우
            schedule_name = schedule.get("name", "").lower()
            words = [word for word in schedule_name.split() if len(word) > 1]
            
            # 첫 번째 매칭 위치 찾기
            first_mention_pos = float('inf')
            for word in words:
                try:
                    pos = voice_words.index(word)
                    first_mention_pos = min(first_mention_pos, pos)
                except ValueError:
                    continue
            
            if first_mention_pos < float('inf'):
                mentioned_order.append((first_mention_pos, schedule))
    
    # 언급 순서대로 우선순위 설정
    mentioned_order.sort(key=lambda x: x[0])
    start_priority = len(fixed_schedules) + 1
    
    for i, (_, schedule) in enumerate(mentioned_order):
        if schedule.get("priority", 3) == 3:
            schedule["priority"] = start_priority + i
    
    # 아직 우선순위가 설정되지 않은 일정들 처리
    used_priorities = set()
    for schedule in fixed_schedules + flexible_schedules:
        if schedule.get("priority") != 3:
            used_priorities.add(schedule.get("priority"))
    
    next_priority = max(used_priorities) + 1 if used_priorities else 1
    
    for schedule in flexible_schedules:
        if schedule.get("priority", 3) == 3:
            schedule["priority"] = next_priority
            next_priority += 1
    
    # 최종 순차 정렬 (1부터 시작)
    all_schedules = fixed_schedules + flexible_schedules
    all_schedules.sort(key=lambda s: s.get("priority", 999))
    
    for i, schedule in enumerate(all_schedules):
        schedule["priority"] = i + 1
    
    # 정렬된 일정을 다시 분리
    fixed_schedules = [s for s in all_schedules if s in fixed_schedules]
    flexible_schedules = [s for s in all_schedules if s in flexible_schedules]
    
    # 업데이트된 일정 반환
    updated_schedules = extracted_schedules.copy()
    updated_schedules["fixedSchedules"] = fixed_schedules
    updated_schedules["flexibleSchedules"] = flexible_schedules
    logger.info("우선순위 적용 완료")
    
    return updated_schedules    