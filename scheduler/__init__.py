# scheduler/__init__.py
import logging

logger = logging.getLogger('scheduler')

try:
    logger.info("✅ time_inference import 시작")
    from .time_inference import apply_time_inference
    logger.info("✅ time_inference import 성공")
except ImportError as e:
    logger.error(f"❌ time_inference import 실패: {e}")
    raise

try:
    logger.info("✅ priority_analyzer import 시작")
    from .priority_analyzer import apply_priorities
    logger.info("✅ priority_analyzer import 성공")
except ImportError as e:
    logger.error(f"❌ priority_analyzer import 실패: {e}")
    raise

try:
    logger.info("✅ chains import 시작")
    from .chains import create_schedule_chain, create_enhancement_chain
    logger.info("✅ chains import 성공")
except ImportError as e:
    logger.error(f"❌ chains import 실패: {e}")
    raise

try:
    logger.info("✅ relationship_analyzer import 시작")
    from .relationship_analyzer import enhance_schedule_with_relationships
    logger.info("✅ relationship_analyzer import 성공")
except ImportError as e:
    logger.error(f"❌ relationship_analyzer import 실패: {e}")
    raise

try:
    logger.info("✅ utils import 시작")
    from .utils import parse_datetime, detect_and_resolve_time_conflicts
    logger.info("✅ utils import 성공")
except ImportError as e:
    logger.error(f"❌ utils import 실패: {e}")
    raise

# 🔥 generate_multiple_options 추가
try:
    logger.info("✅ multiple_options import 시작")
    from .multiple_options import generate_multiple_options
    logger.info("✅ multiple_options import 성공")
except ImportError as e:
    logger.error(f"❌ multiple_options import 실패: {e}")
    logger.error(f"   multiple_options.py 파일이 있는지 확인하세요")
    raise

__all__ = [
    'apply_time_inference',
    'apply_priorities',
    'create_schedule_chain',
    'create_enhancement_chain',
    'enhance_schedule_with_relationships',
    'parse_datetime',
    'detect_and_resolve_time_conflicts',
    'generate_multiple_options'  # 🔥 추가
]

logger.info(f"📦 scheduler 모듈 초기화 완료, export: {len(__all__)}개 함수/클래스")