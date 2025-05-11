# scheduler/priority_analyzer.py에서 개선

import logging
from typing import Dict, Any, List, Tuple
import json 
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
    logger.info(f"입력 일정 데이터: 고정={len(extracted_schedules.get('fixedSchedules', []))}개, 유연={len(extracted_schedules.get('flexibleSchedules', []))}개")
    
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
    
    # 6단계: 최종 우선순위 순차 정렬 (1부터 시작하는 연속된 값)
    # 전체 일정 (고정 + 유연)을 우선순위로 정렬
    all_schedules = fixed_schedules + flexible_schedules
    priority_ordered_schedules = sorted(all_schedules, key=lambda s: s.get("priority", 999))
    
    # 1부터 시작하는 순차적 우선순위 재할당
    for i, schedule in enumerate(priority_ordered_schedules):
        old_priority = schedule.get("priority", "없음")
        new_priority = i + 1
        schedule["priority"] = new_priority
        logger.info(f"최종 순차 우선순위 설정: '{schedule.get('name', '')}' {old_priority} -> {new_priority}")
    
    # 정렬된 일정을 다시 고정/유연으로 분리
    fixed_schedules = [s for s in priority_ordered_schedules if s in fixed_schedules]
    flexible_schedules = [s for s in priority_ordered_schedules if s in flexible_schedules]
    
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