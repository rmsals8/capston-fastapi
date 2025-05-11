# scheduler/priority_analyzer.py 수정

import json
import logging
from typing import Dict, Any, List, Optional

# 로깅 설정
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('priority_analyzer')

def format_schedules_for_priority(schedules: Dict[str, Any]) -> str:
    """일정 정보를 우선순위 분석용으로 포맷팅"""
    logger.info("우선순위 분석용 일정 포맷팅 시작")
    schedule_info = []
    
    for s in schedules.get("fixedSchedules", []):
        detail = f"ID: {s.get('id', '')}, 이름: {s.get('name', '')}, 유형: 고정, 시간: {s.get('startTime', '')} ~ {s.get('endTime', '')}"
        schedule_info.append(detail)
        logger.info(f"고정 일정 포맷팅: {detail}")
    
    for s in schedules.get("flexibleSchedules", []):
        time_info = ""
        if "startTime" in s and "endTime" in s:
            time_info = f", 시간: {s.get('startTime', '')} ~ {s.get('endTime', '')}"
        
        detail = f"ID: {s.get('id', '')}, 이름: {s.get('name', '')}, 유형: 유연{time_info}"
        schedule_info.append(detail)
        logger.info(f"유연 일정 포맷팅: {detail}")
    
    formatted = "\n".join(schedule_info)
    logger.info(f"포맷팅 완료: {len(schedule_info)}개 일정, {len(formatted)}자")
    return formatted

def analyze_schedule_priorities(priority_chain, voice_input: str, extracted_schedules: Dict[str, Any]) -> Dict[str, Any]:
    """메시지와 추출된 일정을 분석하여 우선순위 결정"""
    logger.info("일정 우선순위 분석 시작")
    
    # 일정 정보 포맷팅
    formatted_schedules = format_schedules_for_priority(extracted_schedules)
    logger.info(f"포맷팅된 일정: {len(formatted_schedules)}자")
    
    # LLM 체인 실행
    logger.info("LLM 체인 호출 시작")
    try:
        result = priority_chain.invoke({
            "input": voice_input,
            "extracted_schedules": formatted_schedules
        })
        logger.info(f"LLM 체인 응답 수신: {json.dumps(result, ensure_ascii=False)[:200]}...")
        return result
    except Exception as e:
        logger.error(f"LLM 체인 호출 오류: {str(e)}")
        # 오류 시 기본 응답 반환
        return {
            "schedule_priorities": [],
            "sequence_expressions": [],
            "reasoning": f"우선순위 분석 실패: {str(e)}"
        }

def apply_priorities(priority_chain, voice_input: str, extracted_schedules: Dict[str, Any]) -> Dict[str, Any]:
    """분석된 우선순위를 일정에 적용"""
    logger.info("우선순위 적용 시작")
    logger.info(f"입력 일정 데이터: 고정=1개, 유연=3개")
    
    # LLM 응답 개선을 위한 프롬프트 강화
    sequence_keywords = {
        "먼저": 1,
        "처음": 1,
        "그 다음": 2,
        "중간": 3,
        "마지막": 5
    }
    logger.info(f"순서 키워드 설정: {sequence_keywords}")
    
    # 우선순위 정보 획득
    priority_info = analyze_schedule_priorities(priority_chain, voice_input, extracted_schedules)
    logger.info(f"우선순위 분석 결과: {json.dumps(priority_info, ensure_ascii=False)[:200]}...")
    
    # 고정 일정 처리 (이미 시간순으로 정렬되므로 가장 높은 우선순위)
    fixed_schedules = extracted_schedules.get("fixedSchedules", [])
    for i, schedule in enumerate(fixed_schedules):
        old_priority = schedule.get("priority", "없음")
        new_priority = i + 1  # 시간순으로 가장 높은 우선순위
        schedule["priority"] = new_priority
        logger.info(f"고정 일정 '{schedule.get('name', '')}' 우선순위 설정: {old_priority} -> {new_priority}")
    
    # 우선순위 정보를 딕셔너리로 변환 (id -> priority)
    priority_map = {}
    for item in priority_info.get("schedule_priorities", []):
        if "id" in item and "priority" in item:
            priority_map[item["id"]] = item["priority"]
    
    logger.info(f"우선순위 맵 생성: {len(priority_map)}개 항목")
    
    # 유연 일정 처리 (1단계: LLM 분석 결과 적용)
    flexible_schedules = extracted_schedules.get("flexibleSchedules", [])
    llm_applied_count = 0
    for schedule in flexible_schedules:
        schedule_id = schedule.get("id")
        if schedule_id in priority_map:
            old_priority = schedule.get("priority", "없음")
            new_priority = priority_map[schedule_id]
            schedule["priority"] = new_priority
            logger.info(f"LLM 우선순위 적용: '{schedule.get('name', '')}' {old_priority} -> {new_priority}")
            llm_applied_count += 1
    
    logger.info(f"LLM 우선순위 적용 완료: {llm_applied_count}개 일정")
    
    # 2단계: 직접 텍스트 분석으로 보강
    text_applied_count = 0
    # 키워드 관련 우선순위를 저장할 임시 목록
    keyword_priorities = []
    
    for idx, schedule in enumerate(flexible_schedules):
        # LLM 분석 결과가 이미 적용된 일정은 건너뜀
        schedule_id = schedule.get("id")
        if schedule_id in priority_map:
            continue
        
        schedule_name = schedule.get("name", "").lower()
        logger.info(f"텍스트 분석 시작: '{schedule_name}'")
        
        # 직접 키워드 분석
        for keyword, priority_value in sequence_keywords.items():
            # 음성 입력에서 키워드를 찾고, 해당 키워드 이후에 일정명이 언급되었는지 확인
            if keyword in voice_input.lower():
                keyword_parts = voice_input.lower().split(keyword)
                if len(keyword_parts) > 1:
                    after_keyword = keyword_parts[1]
                    # 일정명 단어가 키워드 이후에 있는지 확인
                    schedule_words = [word for word in schedule_name.split() if len(word) > 1]  # 의미있는 단어만
                    for word in schedule_words:
                        if word in after_keyword:
                            old_priority = schedule.get("priority", "없음")
                            # 우선순위 정보 저장 (나중에 처리)
                            keyword_priorities.append({
                                "index": idx,
                                "schedule": schedule,
                                "keyword": keyword,
                                "priority": priority_value,
                                "old_priority": old_priority
                            })
                            logger.info(f"키워드 '{keyword}' 이후에 '{word}' 발견: 임시 우선순위 {priority_value} 저장")
                            text_applied_count += 1
                            break
    
    # 3단계: 언급 순서 기반 우선순위 설정 및 중복 피하기
    mentioned_schedule_indices = []
    schedule_words_list = []
    
    # 각 일정의 주요 단어 추출
    for i, schedule in enumerate(flexible_schedules):
        schedule_name = schedule.get("name", "").lower()
        words = [word for word in schedule_name.split() if len(word) > 1]  # 의미있는 단어만
        schedule_words_list.append((i, words))
        logger.info(f"일정 {i+1} '{schedule_name}' 주요 단어: {words}")
    
    # 음성 입력에서 각 단어 찾기
    voice_words = voice_input.lower().split()
    logger.info(f"음성 입력 단어 수: {len(voice_words)}")
    
    for word_idx, word in enumerate(voice_words):
        for i, words in schedule_words_list:
            if i not in mentioned_schedule_indices and any(w == word for w in words):
                mentioned_schedule_indices.append(i)
                logger.info(f"음성 입력 {word_idx+1}번째 단어 '{word}'에서 일정 {i+1} 발견")
    
    logger.info(f"언급 순서 분석 결과: {mentioned_schedule_indices}")
    
    # 4단계: 우선순위 설정 (중복 방지)
    # 이미 사용된 우선순위를 추적
    used_priorities = set()
    
    # 고정 일정의 우선순위를 사용된 목록에 추가
    for schedule in fixed_schedules:
        used_priorities.add(schedule.get("priority"))
    
    # 키워드 기반 우선순위 먼저 적용 (키워드 우선순위값 기준 정렬)
    keyword_priorities.sort(key=lambda x: x["priority"])
    
    for item in keyword_priorities:
        schedule = item["schedule"]
        priority_value = item["priority"]
        
        # 이미 사용된 우선순위면 다음 가용 우선순위 찾기
        while priority_value in used_priorities:
            priority_value += 1
        
        # 우선순위 적용
        schedule["priority"] = priority_value
        used_priorities.add(priority_value)
        logger.info(f"키워드 '{item['keyword']}' 기반 우선순위 설정: '{schedule.get('name', '')}' {item['old_priority']} -> {priority_value}")
    
    # 언급 순서에 따라 우선순위 설정 (아직 우선순위가 설정되지 않은 일정에 대해)
    mention_applied_count = 0
    start_priority = len(fixed_schedules) + 1
    
    for mention_idx, schedule_idx in enumerate(mentioned_schedule_indices):
        if schedule_idx < len(flexible_schedules):
            schedule = flexible_schedules[schedule_idx]
            # 우선순위가 기본값(3)인 경우에만 적용
            if schedule.get("priority") == 3:
                old_priority = schedule.get("priority", "없음")
                new_priority = start_priority + mention_idx
                
                # 이미 사용된 우선순위면 다음 가용 우선순위 찾기
                while new_priority in used_priorities:
                    new_priority += 1
                
                schedule["priority"] = new_priority
                used_priorities.add(new_priority)
                logger.info(f"언급 순서에 따른 우선순위 설정: '{schedule.get('name', '')}' {old_priority} -> {new_priority}")
                mention_applied_count += 1
    
    # 5단계: 기본값(3)으로 남아있는 일정의 우선순위를 고유값으로 설정
    next_priority = max(used_priorities) + 1 if used_priorities else len(fixed_schedules) + 1
    default_applied_count = 0
    
    for schedule in flexible_schedules:
        if schedule.get("priority") == 3:
            old_priority = schedule.get("priority", "없음")
            schedule["priority"] = next_priority
            used_priorities.add(next_priority)
            logger.info(f"기본 우선순위 설정: '{schedule.get('name', '')}' {old_priority} -> {next_priority}")
            next_priority += 1
            default_applied_count += 1
    
    logger.info(f"텍스트 분석 우선순위 적용 완료: {text_applied_count}개 일정")
    logger.info(f"언급 순서 우선순위 적용 완료: {mention_applied_count}개 일정")
    logger.info(f"기본 우선순위 적용 완료: {default_applied_count}개 일정")
    
    # 최종 확인: 중복 우선순위 체크
    all_priorities = {}
    for schedule in fixed_schedules + flexible_schedules:
        priority = schedule.get("priority")
        if priority in all_priorities:
            # 중복된 우선순위 발견, 조정 필요
            logger.warning(f"중복 우선순위 발견: {priority}, '{schedule.get('name', '')}'와 '{all_priorities[priority]}'")
            # 다음 가용 우선순위 찾기
            new_priority = max(all_priorities.keys()) + 1
            logger.info(f"우선순위 조정: '{schedule.get('name', '')}' {priority} -> {new_priority}")
            schedule["priority"] = new_priority
            all_priorities[new_priority] = schedule.get("name", "")
        else:
            all_priorities[priority] = schedule.get("name", "")
    
    # 업데이트된 일정 로깅
    logger.info("우선순위 적용 결과:")
    for idx, schedule in enumerate(fixed_schedules):
        logger.info(f"고정 일정 {idx+1}: {schedule.get('name', '')}, 우선순위: {schedule.get('priority', 'N/A')}")
    
    for idx, schedule in enumerate(flexible_schedules):
        logger.info(f"유연 일정 {idx+1}: {schedule.get('name', '')}, 우선순위: {schedule.get('priority', 'N/A')}")
    
    # 업데이트된 일정 반환
    updated_schedules = extracted_schedules.copy()
    updated_schedules["fixedSchedules"] = fixed_schedules
    updated_schedules["flexibleSchedules"] = flexible_schedules
    logger.info("우선순위 적용 완료")
    
    return updated_schedules

# scheduler/relationship_analyzer.py 수정

import logging
import datetime
import json
from typing import Dict, Any, List, Tuple, Optional
from .utils import parse_datetime

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
                            time_diff = after_start - before_end
                            middle_time = before_end + time_diff / 2
                            logger.info(f"중간 시간 계산: {middle_time}")
                            
                            # 시간 설정
                            duration = target_schedule.get("duration", 60)
                            target_schedule["startTime"] = middle_time.isoformat()
                            end_time = middle_time + datetime.timedelta(minutes=duration)
                            target_schedule["endTime"] = end_time.isoformat()
                            logger.info(f"시간 설정: 시작={target_schedule['startTime']}, 종료={target_schedule['endTime']}")
                            
                            # 우선순위 설정 (중복 방지)
                            # before_schedule과 after_schedule 사이의 우선순위 설정
                            before_priority = before_schedule.get("priority")
                            after_priority = after_schedule.get("priority")
                            
                            # 전체 일정의 현재 우선순위 수집
                            used_priorities = set()
                            for schedule in all_schedules:
                                if schedule != target_schedule:  # 현재 처리 중인 일정 제외
                                    used_priorities.add(schedule.get("priority"))
                            
                            # 사이 값 계산
                            if before_priority < after_priority:
                                # 사이 값 찾기
                                between_priority = before_priority + 1
                                while between_priority < after_priority and between_priority in used_priorities:
                                    between_priority += 1
                                
                                if between_priority < after_priority:
                                    # 사이에 빈 우선순위가 있음
                                    new_priority = between_priority
                                else:
                                    # 사이에 빈 우선순위가 없음, 모든 우선순위를 조정해야 함
                                    # 일단 after_priority 이후의 첫 빈 우선순위 사용
                                    new_priority = after_priority
                                    while new_priority in used_priorities:
                                        new_priority += 1
                            else:
                                # after_priority가 before_priority보다 작거나 같은 경우
                                # (이 경우는 정상적이지 않음)
                                # after_priority 이후의 첫 빈 우선순위 사용
                                new_priority = max(before_priority, after_priority) + 1
                                while new_priority in used_priorities:
                                    new_priority += 1
                            
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
                                
                                # 우선순위 설정 (중복 방지)
                                # 전체 일정의 현재 우선순위 수집
                                used_priorities = set()
                                for schedule in all_schedules:
                                    if schedule != target_schedule:  # 현재 처리 중인 일정 제외
                                        used_priorities.add(schedule.get("priority"))
                                
                                # 참조 일정보다 낮은 가장 큰 우선순위 찾기
                                ref_priority = reference_schedule.get("priority")
                                new_priority = ref_priority - 1
                                
                                # 이미 사용 중인 우선순위면 다른 값 찾기
                                while new_priority > 0 and new_priority in used_priorities:
                                    new_priority -= 1
                                
                                # 적절한 값을 찾지 못하면 가장 큰 우선순위 + 1 사용
                                if new_priority <= 0 or new_priority in used_priorities:
                                    new_priority = max(used_priorities) + 1
                                
                                old_priority = target_schedule.get("priority", "없음")
                                target_schedule["priority"] = new_priority
                                logger.info(f"우선순위 설정: {old_priority} -> {new_priority}")
                                
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
                                
                                # 우선순위 설정 (중복 방지)
                                # 전체 일정의 현재 우선순위 수집
                                used_priorities = set()
                                for schedule in all_schedules:
                                    if schedule != target_schedule:  # 현재 처리 중인 일정 제외
                                        used_priorities.add(schedule.get("priority"))
                                
                                # 참조 일정보다 높은 가장 작은 우선순위 찾기
                                ref_priority = reference_schedule.get("priority")
                                new_priority = ref_priority + 1
                                
                                # 이미 사용 중인 우선순위면 다른 값 찾기
                                while new_priority in used_priorities:
                                    new_priority += 1
                                
                                old_priority = target_schedule.get("priority", "없음")
                                target_schedule["priority"] = new_priority
                                logger.info(f"우선순위 설정: {old_priority} -> {new_priority}")
                                
                                # 유형 업데이트
                                target_schedule["type"] = "FIXED"
                    else:
                        logger.warning(f"참조 일정을 찾지 못함: {reference_id}")
            else:
                logger.warning(f"대상 일정을 찾지 못함: {schedule_id}")
        
        # 최종 확인: 중복 우선순위 체크 및 해결
        priority_map = {}
        priority_conflicts = []
        
        # 우선순위 중복 확인
        for schedule in all_schedules:
            priority = schedule.get("priority")
            if priority in priority_map:
                # 중복 발견
                logger.warning(f"중복 우선순위 발견: {priority}, '{schedule.get('name')}' 및 '{priority_map[priority].get('name')}'")
                priority_conflicts.append(schedule)
            else:
                priority_map[priority] = schedule
        
        # 중복 해결
        if priority_conflicts:
            logger.info(f"{len(priority_conflicts)}개의 우선순위 중복 발견, 해결 중...")
            max_priority = max(priority_map.keys()) if priority_map else 0
            
            for conflict_schedule in priority_conflicts:
                max_priority += 1
                old_priority = conflict_schedule.get("priority")
                conflict_schedule["priority"] = max_priority
                logger.info(f"우선순위 중복 해결: '{conflict_schedule.get('name')}' {old_priority} -> {max_priority}")
    else:
        logger.info("적용할 관계 정보가 없음")
    
    # 업데이트된 일정 로깅
    logger.info("최종 일정 요약:")
    for idx, schedule in enumerate(schedules.get("fixedSchedules", [])):
        logger.info(f"고정 일정 {idx+1}: {schedule.get('name', '')}, 타입: {schedule.get('type', 'N/A')}, 시간: {schedule.get('startTime', 'N/A')} ~ {schedule.get('endTime', 'N/A')}, 우선순위: {schedule.get('priority', 'N/A')}")
    
    for idx, schedule in enumerate(schedules.get("flexibleSchedules", [])):
        logger.info(f"유연 일정 {idx+1}: {schedule.get('name', '')}, 타입: {schedule.get('type', 'N/A')}, 시간: {schedule.get('startTime', 'N/A')} ~ {schedule.get('endTime', 'N/A')}, 우선순위: {schedule.get('priority', 'N/A')}")
    
    logger.info("일정 간 관계 정보 적용 완료")
    return schedules