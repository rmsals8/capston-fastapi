# scheduler/utils.py에 개선된 시간 충돌 감지 및 해결 함수

import datetime
import logging
from typing import Dict, Any, Optional, List, Tuple

logger = logging.getLogger('scheduler.utils')

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

def detect_and_resolve_time_conflicts(schedules: Dict[str, Any], min_gap_minutes=15) -> Dict[str, Any]:
    """
    개선된 일정 간 시간 충돌 감지 및 해결 함수.
    모든 일정 쌍을 검사하여 겹치는 시간이 있는지 확인하고 해결합니다.
    
    Args:
        schedules: 일정 데이터
        min_gap_minutes: 일정 사이에 필요한 최소 간격 (분)
    
    Returns:
        충돌이 해결된 일정 데이터
    """
    logger = logging.getLogger('time_conflict_resolver')
    logger.info("일정 간 시간 충돌 감지 및 해결 시작")
    
    # 모든 일정 수집 (시간이 지정된 일정만)
    all_timed_schedules = []
    
    # 시간이 지정된 고정 일정 수집
    for schedule in schedules.get("fixedSchedules", []):
        if "startTime" in schedule and "endTime" in schedule:
            all_timed_schedules.append(schedule)
            logger.info(f"고정 일정 시간 정보: {schedule.get('name')} - {schedule.get('startTime')} ~ {schedule.get('endTime')}")
    
    # 시간이 지정된 유연 일정 수집
    for schedule in schedules.get("flexibleSchedules", []):
        if "startTime" in schedule and "endTime" in schedule:
            all_timed_schedules.append(schedule)
            logger.info(f"유연 일정 시간 정보: {schedule.get('name')} - {schedule.get('startTime')} ~ {schedule.get('endTime')}")
    
    if not all_timed_schedules:
        logger.info("시간이 지정된 일정이 없음, 충돌 분석 생략")
        return schedules
    
    # 충돌 감지 및 해결을 위한 스케줄 정렬 (우선순위로 1차 정렬, 시작 시간으로 2차 정렬)
    all_timed_schedules.sort(key=lambda s: (s.get("priority", 999), parse_datetime(s.get("startTime", ""))))
    logger.info(f"우선순위 및 시간순 정렬 완료: {len(all_timed_schedules)}개 일정")
    
    # 충돌 감지 및 해결
    conflicts_resolved = 0
    checking_needed = True
    max_iterations = 10  # 무한 루프 방지용 최대 반복 횟수
    current_iteration = 0
    
    # 모든 충돌이 해결될 때까지 반복 (또는 최대 반복 횟수에 도달할 때까지)
    while checking_needed and current_iteration < max_iterations:
        current_iteration += 1
        checking_needed = False  # 이번 반복에서 충돌이 발견되지 않으면 종료
        
        # 모든 일정 쌍 검사
        for i in range(len(all_timed_schedules)):
            for j in range(i + 1, len(all_timed_schedules)):
                current = all_timed_schedules[j]
                previous = all_timed_schedules[i]
                
                # datetime 객체로 변환
                current_start = parse_datetime(current.get("startTime", ""))
                current_end = parse_datetime(current.get("endTime", ""))
                previous_start = parse_datetime(previous.get("startTime", ""))
                previous_end = parse_datetime(previous.get("endTime", ""))
                
                # 충돌 감지 (시간이 겹치는 경우)
                if (current_start and current_end and previous_start and previous_end and
                    ((current_start <= previous_end and current_start >= previous_start) or  # current가 previous 끝과 겹침
                     (current_end >= previous_start and current_end <= previous_end) or      # current가 previous 시작과 겹침
                     (current_start <= previous_start and current_end >= previous_end))):    # current가 previous를 완전히 포함
                    
                    logger.info(f"일정 충돌 감지: '{previous.get('name')}' ({previous_start}-{previous_end})와 '{current.get('name')}' ({current_start}-{current_end})")
                    checking_needed = True  # 충돌이 해결되었으므로 다시 한 번 검사 필요
                    
                    # 충돌 해결 전략 결정
                    # 1. 두 일정 모두 FIXED인 경우: 우선순위 높은 일정 유지, 낮은 일정 조정
                    # 2. 하나만 FIXED인 경우: FLEXIBLE 일정 조정
                    # 3. 둘 다 FLEXIBLE인 경우: 우선순위 낮은 일정 조정
                    
                    prev_is_fixed = previous.get("type") == "FIXED"
                    curr_is_fixed = current.get("type") == "FIXED"
                    prev_priority = previous.get("priority", 999)
                    curr_priority = current.get("priority", 999)
                    
                    # 어떤 일정을 조정할지 결정
                    adjust_prev = False
                    adjust_curr = False
                    
                    if prev_is_fixed and curr_is_fixed:
                        # 둘 다 고정 일정: 우선순위로 결정
                        if prev_priority <= curr_priority:
                            adjust_curr = True
                        else:
                            adjust_prev = True
                    elif prev_is_fixed:
                        # 이전 일정이 고정: 현재(유연) 일정 조정
                        adjust_curr = True
                    elif curr_is_fixed:
                        # 현재 일정이 고정: 이전(유연) 일정 조정
                        adjust_prev = True
                    else:
                        # 둘 다 유연: 우선순위로 결정
                        if prev_priority <= curr_priority:
                            adjust_curr = True
                        else:
                            adjust_prev = True
                    
                    # 일정 조정 실행
                    if adjust_curr:
                        # 현재 일정을 이전 일정 이후로 이동
                        new_start = previous_end + datetime.timedelta(minutes=min_gap_minutes)
                        duration_minutes = int((current_end - current_start).total_seconds() / 60)
                        new_end = new_start + datetime.timedelta(minutes=duration_minutes)
                        
                        logger.info(f"충돌 해결: '{current.get('name')}' 일정 이동 {current_start} → {new_start}")
                        
                        current["startTime"] = new_start.isoformat()
                        current["endTime"] = new_end.isoformat()
                        conflicts_resolved += 1
                        
                    elif adjust_prev:
                        # 이전 일정의 종료 시간을 현재 일정 시작 전으로 이동
                        new_end = current_start - datetime.timedelta(minutes=min_gap_minutes)
                        
                        # 이전 일정의 최소 지속 시간 보장 (30분)
                        min_duration = 30
                        required_start = new_end - datetime.timedelta(minutes=min_duration)
                        
                        if required_start >= previous_start:
                            # 최소 지속 시간 보장 가능
                            logger.info(f"충돌 해결: '{previous.get('name')}' 종료 시간 조정 {previous_end} → {new_end}")
                            previous["endTime"] = new_end.isoformat()
                            conflicts_resolved += 1
                        else:
                            # 최소 지속 시간 보장 불가능 - 대안으로 현재 일정 이동
                            new_start = previous_end + datetime.timedelta(minutes=min_gap_minutes)
                            duration_minutes = int((current_end - current_start).total_seconds() / 60)
                            new_end = new_start + datetime.timedelta(minutes=duration_minutes)
                            
                            logger.info(f"충돌 해결 대안: '{current.get('name')}' 일정 이동 {current_start} → {new_start}")
                            
                            current["startTime"] = new_start.isoformat()
                            current["endTime"] = new_end.isoformat()
                            conflicts_resolved += 1
    
    if current_iteration >= max_iterations:
        logger.warning(f"최대 반복 횟수({max_iterations})에 도달: 일부 충돌이 해결되지 않았을 수 있음")
    
    # 시간순 정렬 (최종)
    all_timed_schedules.sort(key=lambda s: parse_datetime(s.get("startTime", "")))
    
    # 각 일정의 최종 시간 로깅
    logger.info("충돌 해결 후 최종 일정:")
    for i, schedule in enumerate(all_timed_schedules):
        start_time = parse_datetime(schedule.get("startTime", ""))
        end_time = parse_datetime(schedule.get("endTime", ""))
        logger.info(f"일정 {i+1}: {schedule.get('name')}, {start_time} ~ {end_time}, 우선순위: {schedule.get('priority')}, 타입: {schedule.get('type')}")
    
    logger.info(f"충돌 해결 완료: {conflicts_resolved}개 충돌 해결됨")
    
    # 일정 타입에 따라 재분류
    fixed_schedules = [s for s in all_timed_schedules if s.get("type") == "FIXED"]
    flexible_schedules = []
    
    # 기존 유연 일정 중 시간이 없는 일정 보존
    for s in schedules.get("flexibleSchedules", []):
        if "startTime" not in s or "endTime" not in s:
            flexible_schedules.append(s)
        elif s.get("type") != "FIXED":
            flexible_schedules.append(s)
    
    logger.info(f"최종 분류: 고정 일정 {len(fixed_schedules)}개, 유연 일정 {len(flexible_schedules)}개")
    
    # 결과 반환
    result = schedules.copy()
    result["fixedSchedules"] = fixed_schedules
    result["flexibleSchedules"] = flexible_schedules
    
    return result
