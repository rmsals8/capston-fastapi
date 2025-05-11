# scheduler/priority_analyzer.py
import json
from typing import Dict, Any, List

def format_schedules_for_priority(schedules: Dict[str, Any]) -> str:
    """일정 정보를 우선순위 분석용으로 포맷팅"""
    schedule_info = []
    
    for s in schedules.get("fixedSchedules", []):
        schedule_info.append(
            f"ID: {s.get('id', '')}, 이름: {s.get('name', '')}, "
            f"유형: 고정, 시간: {s.get('startTime', '')} ~ {s.get('endTime', '')}"
        )
    
    for s in schedules.get("flexibleSchedules", []):
        time_info = ""
        if "startTime" in s and "endTime" in s:
            time_info = f", 시간: {s.get('startTime', '')} ~ {s.get('endTime', '')}"
        
        schedule_info.append(
            f"ID: {s.get('id', '')}, 이름: {s.get('name', '')}, "
            f"유형: 유연{time_info}"
        )
    
    return "\n".join(schedule_info)

def analyze_schedule_priorities(priority_chain, voice_input: str, extracted_schedules: Dict[str, Any]) -> Dict[str, Any]:
    """
    메시지와 추출된 일정을 분석하여 우선순위 결정
    """
    # 일정 정보 포맷팅
    formatted_schedules = format_schedules_for_priority(extracted_schedules)
    
    # LLM 체인 실행
    result = priority_chain.invoke({
        "input": voice_input,
        "extracted_schedules": formatted_schedules
    })
    
    return result

def apply_priorities(priority_chain, voice_input: str, extracted_schedules: Dict[str, Any]) -> Dict[str, Any]:
    """
    분석된 우선순위를 일정에 적용
    """
    priority_info = analyze_schedule_priorities(
        priority_chain, 
        voice_input, 
        extracted_schedules
    )
    
    # 우선순위 정보를 딕셔너리로 변환 (id -> priority)
    priority_map = {}
    for item in priority_info.get("schedule_priorities", []):
        if "id" in item and "priority" in item:
            priority_map[item["id"]] = item["priority"]
    
    # 고정 일정 우선순위 업데이트
    fixed_schedules = extracted_schedules.get("fixedSchedules", [])
    for schedule in fixed_schedules:
        if schedule.get("id") in priority_map:
            schedule["priority"] = priority_map[schedule.get("id")]
    
    # 유연 일정 우선순위 업데이트
    flexible_schedules = extracted_schedules.get("flexibleSchedules", [])
    for schedule in flexible_schedules:
        if schedule.get("id") in priority_map:
            schedule["priority"] = priority_map[schedule.get("id")]
    
    # 업데이트된 일정 반환
    updated_schedules = extracted_schedules.copy()
    updated_schedules["fixedSchedules"] = fixed_schedules
    updated_schedules["flexibleSchedules"] = flexible_schedules
    
    return updated_schedules