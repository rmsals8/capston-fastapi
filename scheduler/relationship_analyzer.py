# scheduler/relationship_analyzer.py (새 파일)
from .utils import parse_datetime
import logging
import datetime
import json
from typing import Dict, Any, List, Tuple, Optional
# 로깅 설정
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('relationship_analyzer')

def analyze_schedule_relationships(voice_input: str, schedules: Dict[str, Any]) -> Dict[str, Any]:
    """일정 간 관계를 분석하는 함수"""
    logger.info("일정 간 관계 분석 시작")
    
    all_schedules = schedules.get("fixedSchedules", []) + schedules.get("flexibleSchedules", [])
    logger.info(f"분석 대상 전체 일정 수: {len(all_schedules)}")
    
    relationships = {}
    
    # 관계 키워드 정의
    relation_keywords = {
        "중간에": "between",
        "전에": "before",
        "후에": "after",
        "이전에": "before",
        "이후에": "after",
        "다음에": "after"
    }
    logger.info(f"관계 키워드 설정: {relation_keywords}")
    
    # 음성 입력에서 관계 키워드 탐색
    found_keywords = []
    for keyword, relation_type in relation_keywords.items():
        if keyword in voice_input:
            found_keywords.append(keyword)
            logger.info(f"음성 입력에서 관계 키워드 '{keyword}' 발견")
            
            # 키워드 전후 컨텍스트 분석
            parts = voice_input.split(keyword)
            if len(parts) >= 2:
                before_context = parts[0].lower()
                after_context = parts[1].lower()
                logger.info(f"키워드 '{keyword}' 앞 컨텍스트: '{before_context[:20]}...'")
                logger.info(f"키워드 '{keyword}' 뒤 컨텍스트: '{after_context[:20]}...'")
                
                # 관련된 일정 찾기
                related_schedule = None
                for idx, schedule in enumerate(all_schedules):
                    schedule_name = schedule.get("name", "").lower()
                    schedule_words = [word for word in schedule_name.split() if len(word) > 1]
                    
                    # 키워드 다음에 나오는 내용에서 일정 이름 단어 찾기
                    if any(word in after_context for word in schedule_words):
                        related_schedule = schedule
                        logger.info(f"키워드 '{keyword}' 뒤 컨텍스트에서 일정 '{schedule_name}' 발견")
                        break
                
                if related_schedule:
                    logger.info(f"관계 키워드 '{keyword}'에 관련된 일정: '{related_schedule.get('name', '')}'")
                    
                    # "중간에" 키워드 처리
                    if relation_type == "between":
                        logger.info("'중간에' 관계 처리 시작")
                        # 앞뒤 일정 찾기
                        before_schedule = None
                        after_schedule = None
                        
                        # 앞 컨텍스트에서 일정 찾기
                        for idx, schedule in enumerate(all_schedules):
                            if schedule != related_schedule:
                                schedule_name = schedule.get("name", "").lower()
                                schedule_words = [word for word in schedule_name.split() if len(word) > 1]
                                
                                if any(word in before_context for word in schedule_words):
                                    before_schedule = schedule
                                    logger.info(f"앞 컨텍스트에서 일정 '{schedule_name}' 발견")
                                    break
                        
                        # 다른 뒤 컨텍스트에서 일정 찾기
                        for idx, schedule in enumerate(all_schedules):
                            if schedule != related_schedule and schedule != before_schedule:
                                schedule_name = schedule.get("name", "").lower()
                                schedule_words = [word for word in schedule_name.split() if len(word) > 1]
                                
                                # 아직 after_schedule이 설정되지 않은 경우에만
                                if not after_schedule and any(word in voice_input for word in schedule_words):
                                    after_schedule = schedule
                                    logger.info(f"다른 일정으로 '{schedule_name}' 발견")
                                    break
                        
                        # 관계 정보 저장
                        if before_schedule and after_schedule:
                            logger.info(f"완전한 'between' 관계 발견: '{before_schedule.get('name', '')}' - '{related_schedule.get('name', '')}' - '{after_schedule.get('name', '')}'")
                            relationships[related_schedule.get("id")] = {
                                "type": "between",
                                "before_id": before_schedule.get("id"),
                                "after_id": after_schedule.get("id")
                            }
                        elif before_schedule:
                            logger.info(f"부분 'after' 관계 발견: '{before_schedule.get('name', '')}' 다음에 '{related_schedule.get('name', '')}'")
                            relationships[related_schedule.get("id")] = {
                                "type": "after",
                                "reference_id": before_schedule.get("id")
                            }
                        else:
                            logger.info(f"관계를 확립할 수 있는 참조 일정을 찾지 못함")
                    else:
                        # 다른 관계 유형 처리 (before, after 등)
                        logger.info(f"'{relation_type}' 관계 처리")
                        reference_schedule = None
                        
                        # 참조 일정 찾기 (before일 경우 after_context에서, after일 경우 before_context에서)
                        search_context = after_context if relation_type == "before" else before_context
                        
                        for idx, schedule in enumerate(all_schedules):
                            if schedule != related_schedule:
                                schedule_name = schedule.get("name", "").lower()
                                schedule_words = [word for word in schedule_name.split() if len(word) > 1]
                                
                                if any(word in search_context for word in schedule_words):
                                    reference_schedule = schedule
                                    logger.info(f"참조 일정으로 '{schedule_name}' 발견")
                                    break
                        
                        if reference_schedule:
                            logger.info(f"'{relation_type}' 관계 확립: '{related_schedule.get('name', '')}' {relation_type} '{reference_schedule.get('name', '')}'")
                            relationships[related_schedule.get("id")] = {
                                "type": relation_type,
                                "reference_id": reference_schedule.get("id")
                            }
                else:
                    logger.info(f"키워드 '{keyword}'에 관련된 일정을 찾지 못함")
    
    if not found_keywords:
        logger.info("음성 입력에서 관계 키워드를 찾지 못함")
    
    logger.info(f"일정 간 관계 분석 완료: {len(relationships)}개 관계 발견")
    return relationships

def enhance_schedule_with_relationships(voice_input: str, schedules: Dict[str, Any]) -> Dict[str, Any]:
    """일정 간 관계 정보를 적용하여 일정 개선"""
    logger.info("일정 간 관계 정보 적용 시작")
    
    # 관계 분석
    relationships = analyze_schedule_relationships(voice_input, schedules)
    logger.info(f"분석된 관계 수: {len(relationships)}")
    
    # 관계 정보를 바탕으로 시간 및 우선순위 재조정
    if relationships:
        logger.info("관계 정보 기반 일정 조정 시작")
        flexible_schedules = schedules.get("flexibleSchedules", [])
        fixed_schedules = schedules.get("fixedSchedules", [])
        all_schedules = fixed_schedules + flexible_schedules
        logger.info(f"조정 대상: 고정 일정 {len(fixed_schedules)}개, 유연 일정 {len(flexible_schedules)}개")
        
        for schedule_id, relation_info in relationships.items():
            logger.info(f"ID '{schedule_id}'의 관계 정보 처리: {json.dumps(relation_info, ensure_ascii=False)}")
            
            # 해당 일정 찾기
            target_schedule = None
            for schedule in all_schedules:
                if schedule.get("id") == schedule_id:
                    target_schedule = schedule
                    logger.info(f"대상 일정 찾음: '{schedule.get('name', '')}'")
                    break
            
            if target_schedule:
                relation_type = relation_info.get("type")
                logger.info(f"관계 유형: {relation_type}")
                
                if relation_type == "between":
                    # "중간에" 관계인 경우 시간 및 우선순위 조정
                    logger.info("'between' 관계 처리")
                    before_id = relation_info.get("before_id")
                    after_id = relation_info.get("after_id")
                    
                    before_schedule = next((s for s in all_schedules if s.get("id") == before_id), None)
                    after_schedule = next((s for s in all_schedules if s.get("id") == after_id), None)
                    
                    if before_schedule and after_schedule:
                        logger.info(f"앞 일정: '{before_schedule.get('name', '')}', 뒤 일정: '{after_schedule.get('name', '')}'")
                        
                        # 두 일정 사이에 위치하도록 조정
                        before_end_str = before_schedule.get("endTime", "")
                        after_start_str = after_schedule.get("startTime", "")
                        
                        before_end = parse_datetime(before_end_str)
                        after_start = parse_datetime(after_start_str)
                        
                        logger.info(f"앞 일정 종료: {before_end}, 뒤 일정 시작: {after_start}")
                        
                        if before_end and after_start:
                            # 사이 시간 계산
                            middle_time = before_end + (after_start - before_end) / 2
                            logger.info(f"중간 시간 계산: {middle_time}")
                            
                            # 시간 설정
                            duration = target_schedule.get("duration", 60)
                            target_schedule["startTime"] = middle_time.isoformat()
                            end_time = middle_time + datetime.timedelta(minutes=duration)
                            target_schedule["endTime"] = end_time.isoformat()
                            logger.info(f"시간 설정: 시작={target_schedule['startTime']}, 종료={target_schedule['endTime']}")
                            
                            # 우선순위 설정 (사이 값)
                            before_priority = before_schedule.get("priority", 3)
                            after_priority = after_schedule.get("priority", 3)
                            new_priority = (before_priority + after_priority) / 2
                            old_priority = target_schedule.get("priority", "없음")
                            target_schedule["priority"] = new_priority
                            logger.info(f"우선순위 설정: {old_priority} -> {new_priority}")
                            
                            # 유연함 업데이트
                            if "startTime" in target_schedule and "endTime" in target_schedule:
                                old_type = target_schedule.get("type", "없음")
                                target_schedule["type"] = "FIXED"
                                logger.info(f"일정 유형 변경: {old_type} -> FIXED")
                        else:
                            logger.warning(f"시간 파싱 실패: before_end={before_end}, after_start={after_start}")
                    else:
                        logger.warning(f"관계 일정을 찾지 못함: before={before_id}, after={after_id}")
                
                elif relation_type in ["before", "after"]:
                    # "before" 또는 "after" 관계 처리
                    logger.info(f"'{relation_type}' 관계 처리")
                    reference_id = relation_info.get("reference_id")
                    reference_schedule = next((s for s in all_schedules if s.get("id") == reference_id), None)
                    
                    if reference_schedule:
                        logger.info(f"참조 일정: '{reference_schedule.get('name', '')}'")
                        
                        if relation_type == "before":
                            # 참조 일정 전에 위치
                            ref_start_str = reference_schedule.get("startTime")
                            ref_start = parse_datetime(ref_start_str)
                            
                            if ref_start:
                                duration = target_schedule.get("duration", 60)
                                # 30분 여유 두고 배치
                                end_time = ref_start - datetime.timedelta(minutes=30)
                                start_time = end_time - datetime.timedelta(minutes=duration)
                                
                                target_schedule["startTime"] = start_time.isoformat()
                                target_schedule["endTime"] = end_time.isoformat()
                                logger.info(f"시간 설정 (before): 시작={target_schedule['startTime']}, 종료={target_schedule['endTime']}")
                                
                                # 우선순위 설정 (참조 일정보다 높게)
                                ref_priority = reference_schedule.get("priority", 3)
                                old_priority = target_schedule.get("priority", "없음")
                                target_schedule["priority"] = max(1, ref_priority - 1)
                                logger.info(f"우선순위 설정: {old_priority} -> {target_schedule['priority']}")
                                
                                # 유형 업데이트
                                target_schedule["type"] = "FIXED"
                        
                        elif relation_type == "after":
                            # 참조 일정 후에 위치
                            ref_end_str = reference_schedule.get("endTime")
                            ref_end = parse_datetime(ref_end_str)
                            
                            if ref_end:
                                duration = target_schedule.get("duration", 60)
                                # 30분 여유 두고 배치
                                start_time = ref_end + datetime.timedelta(minutes=30)
                                end_time = start_time + datetime.timedelta(minutes=duration)
                                
                                target_schedule["startTime"] = start_time.isoformat()
                                target_schedule["endTime"] = end_time.isoformat()
                                logger.info(f"시간 설정 (after): 시작={target_schedule['startTime']}, 종료={target_schedule['endTime']}")
                                
                                # 우선순위 설정 (참조 일정보다 낮게)
                                ref_priority = reference_schedule.get("priority", 3)
                                old_priority = target_schedule.get("priority", "없음")
                                target_schedule["priority"] = min(5, ref_priority + 1)
                                logger.info(f"우선순위 설정: {old_priority} -> {target_schedule['priority']}")
                                
                                # 유형 업데이트
                                target_schedule["type"] = "FIXED"
                    else:
                        logger.warning(f"참조 일정을 찾지 못함: {reference_id}")
            else:
                logger.warning(f"대상 일정을 찾지 못함: {schedule_id}")
    else:
        logger.info("적용할 관계 정보가 없음")
    
    # 업데이트된 일정 로깅
    flexible_schedules = schedules.get("flexibleSchedules", [])
    for idx, schedule in enumerate(flexible_schedules):
        logger.info(f"최종 유연 일정 {idx+1}: {schedule.get('name', '')}, 타입: {schedule.get('type', 'N/A')}, 시간: {schedule.get('startTime', 'N/A')} ~ {schedule.get('endTime', 'N/A')}, 우선순위: {schedule.get('priority', 'N/A')}")
    
    logger.info("일정 간 관계 정보 적용 완료")
    return schedules