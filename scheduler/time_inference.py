# scheduler/time_inference.py에서 개선
import datetime
import json
import logging
from typing import Dict, Any, List, Tuple, Optional
from .utils import parse_datetime
# 로깅 설정
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('time_inference')

def parse_datetime(dt_str: str) -> Optional[datetime.datetime]:
    """날짜 문자열을 datetime 객체로 변환"""
    logger.info(f"날짜 문자열 변환 시도: {dt_str}")
    try:
        dt = datetime.datetime.fromisoformat(dt_str.replace('Z', '+00:00'))
        logger.info(f"날짜 변환 성공: {dt}")
        return dt
    except Exception as e:
        logger.error(f"날짜 변환 실패: {str(e)}")
        try:
            dt = datetime.datetime.strptime(dt_str, "%Y-%m-%dT%H:%M:%S")
            logger.info(f"대체 형식으로 변환 성공: {dt}")
            return dt
        except Exception as e2:
            logger.error(f"대체 형식으로도 변환 실패: {str(e2)}")
            return None

def format_schedules_for_prompt(schedules: List[Dict[str, Any]]) -> str:
    """일정 목록을 프롬프트용 문자열로 포맷팅"""
    logger.info(f"일정 프롬프트 포맷팅 시작: {len(schedules)}개 일정")
    if not schedules:
        logger.info("일정이 없음, '없음' 반환")
        return "없음"
    
    schedule_details = []
    for idx, s in enumerate(schedules):
        detail = f"일정명: {s.get('name', '')}, 시작: {s.get('startTime', '')}, 종료: {s.get('endTime', '')}"
        schedule_details.append(detail)
        logger.info(f"일정 {idx+1} 포맷팅: {detail}")
    
    formatted = "\n".join(schedule_details)
    logger.info(f"포맷팅 완료: {len(formatted)}자")
    return formatted

def infer_time_expressions(time_chain, voice_input: str, current_schedules: List[Dict[str, Any]]) -> Dict[str, Any]:
    """음성 입력에서 시간 표현을 추출하고 구체적인 시간으로 변환"""
    logger.info(f"시간 표현 추론 시작: 입력 길이={len(voice_input)}")
    
    # 현재 날짜/시간 정보
    now = datetime.datetime.now()
    current_date = now.strftime("%Y-%m-%d")
    current_time = now.strftime("%H:%M:%S")
    logger.info(f"현재 날짜/시간: {current_date} {current_time}")
    
    # 이전 일정 정보 포맷팅
    previous_schedules = format_schedules_for_prompt(current_schedules)
    logger.info(f"이전 일정 정보: {previous_schedules}")
    
    # LLM 체인 실행
    logger.info("LLM 체인 호출 시작")
    try:
        result = time_chain.invoke({
            "input": voice_input, 
            "current_date": current_date, 
            "current_time": current_time,
            "previous_schedules": previous_schedules
        })
        logger.info(f"LLM 체인 응답 수신: {json.dumps(result, ensure_ascii=False)[:200]}...")
        return result
    except Exception as e:
        logger.error(f"LLM 체인 호출 오류: {str(e)}")
        # 오류 시 기본 응답 반환
        return {
            "time_expressions": [],
            "inferred_times": [],
            "reasoning": f"시간 추론 실패: {str(e)}"
        }

def apply_time_inference(time_chain, voice_input: str, extracted_schedules: Dict[str, Any]) -> Dict[str, Any]:
    """시간 추론 결과를 일정에 적용하는 함수 개선"""
    logger.info("시간 추론 적용 시작")
    logger.info(f"입력 일정 데이터: 고정={len(extracted_schedules.get('fixedSchedules', []))}개, 유연={len(extracted_schedules.get('flexibleSchedules', []))}개")
    
    # 현재 시간 및 고정 일정 정보 획득
    now = datetime.datetime.now()
    logger.info(f"현재 시간: {now}")
    
    fixed_schedules = extracted_schedules.get("fixedSchedules", [])
    logger.info(f"고정 일정 수: {len(fixed_schedules)}")
    
    # 시간 추론 결과 획득
    time_info = infer_time_expressions(time_chain, voice_input, fixed_schedules)
    logger.info(f"시간 추론 결과: 표현={len(time_info.get('time_expressions', []))}개, 추론={len(time_info.get('inferred_times', []))}개")
    
    # 추론된 시간 정보 로깅
    for expr, times in zip(time_info.get('time_expressions', []), time_info.get('inferred_times', [])):
        logger.info(f"시간 표현: '{expr}' -> 시작: {times.get('start', 'N/A')}, 종료: {times.get('end', 'N/A')}, 신뢰도: {times.get('confidence', 0)}")
    
    # 유연 일정 처리
    flexible_schedules = extracted_schedules.get("flexibleSchedules", [])
    logger.info(f"유연 일정 수: {len(flexible_schedules)}")
    
    # 참조 시간 생성 (고정 일정 끝나는 시간 또는 현재 시간)
    reference_time = now
    if fixed_schedules:
        try:
            last_fixed = max(fixed_schedules, key=lambda x: parse_datetime(x.get("endTime", "")) or now)
            reference_end_time = parse_datetime(last_fixed.get("endTime", ""))
            if reference_end_time:
                reference_time = reference_end_time
                logger.info(f"참조 시간 설정 (마지막 고정 일정): {reference_time}")
            else:
                logger.info(f"참조 시간 설정 실패, 현재 시간 사용: {reference_time}")
        except Exception as e:
            logger.error(f"참조 시간 계산 오류: {str(e)}, 현재 시간 사용")
    else:
        logger.info(f"고정 일정 없음, 현재 시간 사용: {reference_time}")

    # 상대적 시간 표현 처리 (더 상세한 매핑)
    time_keywords = {
        "점심": {
            "start": reference_time.replace(hour=12, minute=0), 
            "end": reference_time.replace(hour=13, minute=30),
            "duration": 90,
            "confidence": 0.8
        },
        "그 다음": {
            "start": reference_time + datetime.timedelta(minutes=120),  # 더 늦게 시작
            "end": reference_time + datetime.timedelta(minutes=180),  # 시간 간격 확장
            "duration": 60,
            "confidence": 0.7
        },
        "중간에": {
            "sequence": "middle",
            "confidence": 0.7
        },
        "오후": {
            "start": reference_time.replace(hour=14, minute=0), 
            "end": reference_time.replace(hour=16, minute=0),
            "duration": 120,
            "confidence": 0.6
        },
        "저녁": {
            "start": reference_time.replace(hour=18, minute=0), 
            "end": reference_time.replace(hour=19, minute=30),
            "duration": 90,
            "confidence": 0.7
        },
    }
    
    logger.info(f"기본 시간 키워드 설정: {list(time_keywords.keys())}")
    
    # 시간 추론 결과와 키워드 매핑 통합
    for expr, time_data in zip(time_info.get('time_expressions', []), time_info.get('inferred_times', [])):
        expr_lower = expr.lower()
        logger.info(f"시간 표현 매핑: '{expr_lower}' -> {json.dumps(time_data, ensure_ascii=False)}")
        time_keywords[expr_lower] = time_data
    
    logger.info(f"최종 시간 키워드 맵: {list(time_keywords.keys())}")
    
    # "그 다음" 관련 일정 식별
    next_schedules = []
    for idx, schedule in enumerate(flexible_schedules):
        schedule_name = schedule.get("name", "").lower()
        # "그 다음" 이후에 언급된 일정 확인
        if "그 다음" in voice_input.lower():
            parts = voice_input.lower().split("그 다음")
            if len(parts) > 1:
                after_part = parts[1]
                # 일정명의 단어가 "그 다음" 이후에 있는지 확인
                words = [word for word in schedule_name.split() if len(word) > 1]
                for word in words:
                    if word in after_part:
                        next_schedules.append((idx, schedule, words))
                        logger.info(f"'그 다음' 이후 일정으로 '{schedule_name}' 식별됨")
                        break
    
    # 마지막 할당 시간 추적 (순차적 할당용)
    last_assigned_time = reference_time
    
    # 시간 할당 로직 강화
    for idx, schedule in enumerate(flexible_schedules):
        logger.info(f"유연 일정 {idx+1} 처리: {schedule.get('name', '이름 없음')}")
        schedule_text = voice_input.lower() + " " + schedule.get("name", "").lower()
        
        # 관련된 시간 표현 찾기
        matched_keyword = None
        for keyword, time_data in time_keywords.items():
            if keyword in schedule_text:
                logger.info(f"일정 '{schedule.get('name', '')}' 에서 키워드 '{keyword}' 발견")
                matched_keyword = keyword
                
                if "start" in time_data and "end" in time_data:
                    start_time = time_data.get("start")
                    end_time = time_data.get("end")
                    
                    # "그 다음" 키워드를 위한 특별 처리
                    if keyword == "그 다음" and any(s[1].get("id") == schedule.get("id") for s in next_schedules):
                        # 마지막 할당된 시간 이후로 30분 더 추가
                        logger.info(f"'그 다음' 일정에 대한 특별 시간 조정")
                        start_time = last_assigned_time + datetime.timedelta(minutes=30)
                        duration = schedule.get("duration", 60)
                        end_time = start_time + datetime.timedelta(minutes=duration)
                    
                    if isinstance(start_time, datetime.datetime):
                        start_str = start_time.isoformat()
                    else:
                        start_str = start_time
                    
                    if isinstance(end_time, datetime.datetime):
                        end_str = end_time.isoformat()
                    else:
                        end_str = end_time
                    
                    logger.info(f"시간 할당: 시작={start_str}, 종료={end_str}")
                    
                    schedule["startTime"] = start_str
                    schedule["endTime"] = end_str
                    
                    # 할당 시간 업데이트
                    if isinstance(end_time, datetime.datetime):
                        last_assigned_time = end_time
                        logger.info(f"마지막 할당 시간 업데이트: {last_assigned_time}")
                    
                    # 신뢰도가 충분히 높으면 FIXED로 변경
                    confidence = time_data.get("confidence", 0.5)
                    logger.info(f"시간 신뢰도: {confidence}")
                    if confidence > 0.8:  # 0.7에서 0.8로 상향 조정
                        logger.info(f"유연 일정을 고정 일정으로 변환 (신뢰도: {confidence})")
                        schedule["type"] = "FIXED"
                    break
                elif "sequence" in time_data:
                    logger.info(f"시퀀스 정보 발견: {time_data.get('sequence')}")
                    # 시퀀스 정보는 나중에 별도 처리
                    break
        
        if matched_keyword:
            logger.info(f"일정 '{schedule.get('name', '')}' 매칭된 키워드: {matched_keyword}")
        else:
            logger.info(f"일정 '{schedule.get('name', '')}' 시간 키워드 매칭 없음")
    
    # "그 다음" 일정들에 대한 특별 시간 처리
    for idx, schedule, words in next_schedules:
        # 이미 시간이 할당되어 있지만 "그 다음" 관계를 더 명확하게 하기 위해 조정
        if "startTime" in schedule and "endTime" in schedule:
            # 다른 일정들보다 뒤에 위치하도록 조정
            new_start = last_assigned_time + datetime.timedelta(minutes=30)
            duration = schedule.get("duration", 60)
            new_end = new_start + datetime.timedelta(minutes=duration)
            
            old_start = schedule.get("startTime", "N/A")
            old_end = schedule.get("endTime", "N/A")
            
            logger.info(f"'그 다음' 일정 시간 재조정: '{schedule.get('name', '')}' {old_start}-{old_end} -> {new_start.isoformat()}-{new_end.isoformat()}")
            
            schedule["startTime"] = new_start.isoformat()
            schedule["endTime"] = new_end.isoformat()
            
            # 마지막 할당 시간 업데이트
            last_assigned_time = new_end
            logger.info(f"마지막 할당 시간 업데이트: {last_assigned_time}")
    
    # 시간이 할당되지 않은 일정에 대한 연속 시간 할당
    logger.info("할당되지 않은 일정 처리 시작")
    updated_count = 0
    
    for idx, schedule in enumerate(flexible_schedules):
        if "startTime" not in schedule or "endTime" not in schedule:
            duration = schedule.get("duration", 60)
            logger.info(f"일정 '{schedule.get('name', '')}' 시간 할당: 시작={last_assigned_time}, 기간={duration}분")
            
            schedule["startTime"] = last_assigned_time.isoformat()
            end_time = last_assigned_time + datetime.timedelta(minutes=duration)
            schedule["endTime"] = end_time.isoformat()
            
            # 다음 일정 시간 계산 (30분 이동 시간 추가)
            last_assigned_time = end_time + datetime.timedelta(minutes=30)
            logger.info(f"다음 일정 시작 시간 설정: {last_assigned_time}")
            updated_count += 1
    
    logger.info(f"할당되지 않은 {updated_count}개 일정 처리 완료")
    
    # 업데이트된 일정 로깅
    logger.info("시간 추론 적용 결과:")
    for idx, schedule in enumerate(flexible_schedules):
        logger.info(f"유연 일정 {idx+1}: {schedule.get('name', '')}, 시간: {schedule.get('startTime', 'N/A')} ~ {schedule.get('endTime', 'N/A')}")
    
    # 업데이트된 일정 반환
    updated_schedules = extracted_schedules.copy()
    updated_schedules["flexibleSchedules"] = flexible_schedules
    logger.info("시간 추론 적용 완료")
    
    return updated_schedules