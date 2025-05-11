# scheduler/utils.py 파일 추가
import datetime
import logging
from typing import Optional

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