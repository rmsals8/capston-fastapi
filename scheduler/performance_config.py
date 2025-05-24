# scheduler/performance_config.py
import os
import logging
from typing import Dict, Any

class PerformanceConfig:
    """성능 최적화 설정"""
    
    def __init__(self):
        # 환경 변수 기반 설정
        self.environment = os.getenv("ENVIRONMENT", "development")
        self.debug_mode = os.getenv("DEBUG_MODE", "false").lower() == "true"
        
        # 로깅 설정
        self.log_level = os.getenv("LOG_LEVEL", "WARNING" if self.environment == "production" else "INFO")
        
        # API 호출 최적화 설정
        self.max_concurrent_requests = int(os.getenv("MAX_CONCURRENT_REQUESTS", "5"))
        self.api_timeout = int(os.getenv("API_TIMEOUT", "30"))
        self.enable_caching = os.getenv("ENABLE_CACHING", "true").lower() == "true"
        
        # 캐시 설정
        self.cache_ttl_short = int(os.getenv("CACHE_TTL_SHORT", "300"))  # 5분
        self.cache_ttl_medium = int(os.getenv("CACHE_TTL_MEDIUM", "1800"))  # 30분
        self.cache_ttl_long = int(os.getenv("CACHE_TTL_LONG", "3600"))  # 1시간
        
        # LLM 최적화 설정
        self.use_gpt4 = os.getenv("USE_GPT4", "false").lower() == "true"
        self.llm_max_tokens = int(os.getenv("LLM_MAX_TOKENS", "1500"))
        self.llm_temperature = float(os.getenv("LLM_TEMPERATURE", "0"))
        
        # 검색 최적화 설정
        self.max_search_retries = int(os.getenv("MAX_SEARCH_RETRIES", "2"))
        self.search_batch_size = int(os.getenv("SEARCH_BATCH_SIZE", "5"))
        self.skip_llm_for_simple_tasks = os.getenv("SKIP_LLM_FOR_SIMPLE", "true").lower() == "true"
        
        # Redis 설정
        self.redis_url = os.getenv("REDIS_URL", "svc.sel4.cloudtype.app")
        self.redis_port = int(os.getenv("REDIS_PORT", "31185"))
        
    def configure_logging(self):
        """로깅 설정 적용"""
        log_level = getattr(logging, self.log_level.upper())
        
        # 루트 로거 설정
        logging.getLogger().setLevel(log_level)
        
        # 특정 로거들 최적화
        if self.environment == "production":
            # 운영 환경에서는 중요한 로그만
            performance_loggers = [
                'scheduler',
                'google_places_tool', 
                'async_places_tool',
                'time_inference',
                'priority_analyzer',
                'relationship_analyzer'
            ]
            
            for logger_name in performance_loggers:
                logging.getLogger(logger_name).setLevel(logging.ERROR)
        
        # HTTP 라이브러리 로깅 최소화
        logging.getLogger('httpx').setLevel(logging.WARNING)
        logging.getLogger('httpcore').setLevel(logging.WARNING)
        logging.getLogger('urllib3').setLevel(logging.WARNING)
    
    def get_llm_config(self) -> Dict[str, Any]:
        """LLM 설정 반환"""
        return {
            "model_name": "gpt-4" if self.use_gpt4 else "gpt-3.5-turbo",
            "temperature": self.llm_temperature,
            "max_tokens": self.llm_max_tokens,
            "request_timeout": self.api_timeout
        }
    
    def should_skip_llm(self, task_complexity: str) -> bool:
        """LLM 호출을 생략할지 결정"""
        if not self.skip_llm_for_simple_tasks:
            return False
            
        # 간단한 작업의 경우 LLM 생략
        simple_tasks = ["single_schedule", "basic_priority", "minimal_schedules"]
        return task_complexity in simple_tasks
    
    def get_cache_ttl(self, cache_type: str) -> int:
        """캐시 유형별 TTL 반환"""
        cache_ttls = {
            "short": self.cache_ttl_short,
            "medium": self.cache_ttl_medium, 
            "long": self.cache_ttl_long
        }
        return cache_ttls.get(cache_type, self.cache_ttl_medium)

# 전역 설정 인스턴스
perf_config = PerformanceConfig()

# 로깅 설정 적용
perf_config.configure_logging()