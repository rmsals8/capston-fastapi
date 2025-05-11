# scheduler/time_inference.py
import datetime
import json
from typing import Dict, Any, List

def format_schedules_for_prompt(schedules: List[Dict[str, Any]]) -> str:
    """일정 목록을 프롬프트용 문자열로 포맷팅"""
    if not schedules:
        return "없음"
    
    schedule_details = []
    for s in schedules:
        schedule_details.append(
            f"일정명: {s.get('name', '')}, "
            f"시작: {s.get('startTime', '')}, "
            f"종료: {s.get('endTime', '')}"
        )
    return "\n".join(schedule_details)

def infer_time_expressions(time_chain, voice_input: str, current_schedules: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    음성 입력에서 시간 표현을 추출하고 구체적인 시간으로 변환
    """
    # 현재 날짜/시간 정보
    now = datetime.datetime.now()
    current_date = now.strftime("%Y-%m-%d")
    current_time = now.strftime("%H:%M:%S")
    
    # 이전 일정 정보 포맷팅
    previous_schedules = format_schedules_for_prompt(current_schedules)
    
    # LLM 체인 실행
    result = time_chain.invoke({
        "input": voice_input, 
        "current_date": current_date, 
        "current_time": current_time,
        "previous_schedules": previous_schedules
    })
    
    return result

def apply_time_inference(time_chain, voice_input: str, extracted_schedules: Dict[str, Any]) -> Dict[str, Any]:
    """
    추론된 시간 정보를 추출된 일정에 적용
    """
    time_info = infer_time_expressions(
        time_chain, 
        voice_input, 
        extracted_schedules.get("fixedSchedules", [])
    )
    
    # 고정 일정은 이미 시간이 지정되어 있으므로 유연 일정만 처리
    flexible_schedules = extracted_schedules.get("flexibleSchedules", [])
    updated_flexible = []
    
    # 시간 표현과 추론된 시간을 매핑
    time_expr_map = {}
    for expr, time_data in zip(
        time_info.get("time_expressions", []), 
        time_info.get("inferred_times", [])
    ):
        time_expr_map[expr.lower()] = time_data
    
    for schedule in flexible_schedules:
        schedule_name = schedule.get("name", "").lower()
        
        # 일정명이 시간 표현에 직접 포함된 경우 (예: '점심 식사')
        for expr, time_data in time_expr_map.items():
            if expr in schedule_name or schedule_name in expr:
                if "start" in time_data and "end" in time_data:
                    schedule["startTime"] = time_data["start"]
                    schedule["endTime"] = time_data["end"]
                    
                    # 충분히 구체적인 시간이 있으면 FIXED로 변경
                    schedule["type"] = "FIXED"
                    break
        
        # 시간이 지정되지 않은 경우, 맥락 상 가장 관련 있는 시간 찾기
        if "startTime" not in schedule:
            # 여기서 추가적인 맥락 분석 가능
            pass
            
        updated_flexible.append(schedule)
    
    # 업데이트된 일정 반환
    updated_schedules = extracted_schedules.copy()
    updated_schedules["flexibleSchedules"] = updated_flexible
    
    return updated_schedules