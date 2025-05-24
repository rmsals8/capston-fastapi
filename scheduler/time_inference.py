# scheduler/time_inference.py (최적화됨)
import datetime
import json
import logging
from typing import Dict, Any, List, Optional
from .utils import parse_datetime
from .cache_manager import cached_result

# 로깅 최적화
logger = logging.getLogger('time_inference')

@cached_result("schedule_formatting", expire_seconds=300)
def format_schedules_for_prompt(schedules: List[Dict[str, Any]]) -> str:
    """일정 목록을 프롬프트용 문자열로 포맷팅 (캐시됨)"""
    if not schedules:
        return "없음"
    
    schedule_details = []
    for s in schedules:
        detail = f"일정명: {s.get('name', '')}, 시작: {s.get('startTime', '')}, 종료: {s.get('endTime', '')}"
        schedule_details.append(detail)
    
    return "\n".join(schedule_details)

def infer_time_expressions(time_chain, voice_input: str, current_schedules: List[Dict[str, Any]]) -> Dict[str, Any]:
    """음성 입력에서 시간 표현을 추출하고 구체적인 시간으로 변환 (최적화됨)"""
    # 현재 날짜/시간 정보
    now = datetime.datetime.now()
    current_date = now.strftime("%Y-%m-%d")
    current_time = now.strftime("%H:%M:%S")
    
    # 이전 일정 정보 포맷팅 (캐시 활용)
    previous_schedules = format_schedules_for_prompt(current_schedules)
    
    # LLM 체인 실행
    try:
        result = time_chain.invoke({
            "input": voice_input, 
            "current_date": current_date, 
            "current_time": current_time,
            "previous_schedules": previous_schedules
        })
        return result
    except Exception as e:
        logger.error(f"LLM 체인 호출 오류: {str(e)}")
        return {
            "time_expressions": [],
            "inferred_times": [],
            "reasoning": f"시간 추론 실패: {str(e)}"
        }

def apply_time_inference(time_chain, voice_input: str, extracted_schedules: Dict[str, Any]) -> Dict[str, Any]:
    """시간 추론 결과를 일정에 적용하는 함수 (최적화됨)"""
    logger.info("시간 추론 적용 시작")
    
    # 현재 시간 및 고정 일정 정보 획득
    now = datetime.datetime.now()
    fixed_schedules = extracted_schedules.get("fixedSchedules", [])
    
    # 시간 추론 결과 획득 (LLM 호출은 필요시에만)
    flexible_schedules = extracted_schedules.get("flexibleSchedules", [])
    if not flexible_schedules:
        logger.info("유연 일정이 없어 시간 추론 생략")
        return extracted_schedules
    
    time_info = infer_time_expressions(time_chain, voice_input, fixed_schedules)
    
    # 참조 시간 생성 (고정 일정 끝나는 시간 또는 현재 시간)
    reference_time = now
    if fixed_schedules:
        try:
            last_fixed = max(fixed_schedules, key=lambda x: parse_datetime(x.get("endTime", "")) or now)
            reference_end_time = parse_datetime(last_fixed.get("endTime", ""))
            if reference_end_time:
                reference_time = reference_end_time
        except Exception:
            pass
    
    # 최적화된 시간 키워드 매핑 (자주 사용되는 것만)
    time_keywords = {
        "점심": {
            "start": reference_time.replace(hour=12, minute=0), 
            "end": reference_time.replace(hour=13, minute=30),
            "confidence": 0.8
        },
        "그 다음": {
            "start": reference_time + datetime.timedelta(minutes=120),
            "end": reference_time + datetime.timedelta(minutes=180),
            "confidence": 0.7
        },
        "오후": {
            "start": reference_time.replace(hour=14, minute=0), 
            "end": reference_time.replace(hour=16, minute=0),
            "confidence": 0.6
        },
        "저녁": {
            "start": reference_time.replace(hour=18, minute=0), 
            "end": reference_time.replace(hour=19, minute=30),
            "confidence": 0.7
        }
    }
    
    # 시간 추론 결과와 키워드 매핑 통합
    for expr, time_data in zip(time_info.get('time_expressions', []), time_info.get('inferred_times', [])):
        expr_lower = expr.lower()
        time_keywords[expr_lower] = time_data
    
    # "그 다음" 관련 일정 식별 (최적화)
    next_schedules = []
    if "그 다음" in voice_input.lower():
        voice_parts = voice_input.lower().split("그 다음")
        if len(voice_parts) > 1:
            after_part = voice_parts[1]
            for idx, schedule in enumerate(flexible_schedules):
                schedule_name = schedule.get("name", "").lower()
                words = [word for word in schedule_name.split() if len(word) > 1]
                if any(word in after_part for word in words):
                    next_schedules.append((idx, schedule, words))
                    break  # 첫 번째 매치만 사용
    
    # 마지막 할당 시간 추적
    last_assigned_time = reference_time
    
    # 시간 할당 로직 (최적화됨)
    for idx, schedule in enumerate(flexible_schedules):
        schedule_text = voice_input.lower() + " " + schedule.get("name", "").lower()
        
        # 키워드 매칭 (첫 번째 매치만 사용)
        matched_keyword = None
        for keyword, time_data in time_keywords.items():
            if keyword in schedule_text:
                matched_keyword = keyword
                
                if "start" in time_data and "end" in time_data:
                    start_time = time_data.get("start")
                    end_time = time_data.get("end")
                    
                    # "그 다음" 특별 처리
                    if keyword == "그 다음" and any(s[1].get("id") == schedule.get("id") for s in next_schedules):
                        start_time = last_assigned_time + datetime.timedelta(minutes=30)
                        duration = schedule.get("duration", 60)
                        end_time = start_time + datetime.timedelta(minutes=duration)
                    
                    # 시간 설정
                    schedule["startTime"] = start_time.isoformat() if hasattr(start_time, 'isoformat') else start_time
                    schedule["endTime"] = end_time.isoformat() if hasattr(end_time, 'isoformat') else end_time
                    
                    # 할당 시간 업데이트
                    if hasattr(end_time, 'isoformat'):
                        last_assigned_time = end_time
                    
                    # 신뢰도가 높으면 FIXED로 변경
                    confidence = time_data.get("confidence", 0.5)
                    if confidence > 0.8:
                        schedule["type"] = "FIXED"
                    break
        
        # 매칭되지 않은 일정은 순차 할당
        if not matched_keyword and "startTime" not in schedule:
            duration = schedule.get("duration", 60)
            schedule["startTime"] = last_assigned_time.isoformat()
            end_time = last_assigned_time + datetime.timedelta(minutes=duration)
            schedule["endTime"] = end_time.isoformat()
            
            # 다음 일정 시간 계산 (30분 간격)
            last_assigned_time = end_time + datetime.timedelta(minutes=30)
    
    # 업데이트된 일정 반환
    updated_schedules = extracted_schedules.copy()
    updated_schedules["flexibleSchedules"] = flexible_schedules
    logger.info("시간 추론 적용 완료")
    
    return updated_schedules