# scheduler/cache_manager.py
import redis
import json
import hashlib
import logging
from typing import Optional, Dict, Any
from functools import wraps
import pickle
import os

logger = logging.getLogger('cache_manager')

class CacheManager:
    def __init__(self):
        self.redis_client = None
        self.local_cache = {}
        self.max_local_cache_size = 1000
        self._initialize_redis()
    
    def _initialize_redis(self):
        """Redis 연결 초기화"""
        try:
            redis_url = os.getenv('REDIS_URL', 'svc.sel4.cloudtype.app')
            redis_port = int(os.getenv('REDIS_PORT', '31185'))
            
            self.redis_client = redis.Redis(
                host=redis_url,
                port=redis_port,
                decode_responses=True,
                socket_timeout=2,
                socket_connect_timeout=2,
                retry_on_timeout=False
            )
            
            # 연결 테스트
            self.redis_client.ping()
            logger.info(f"Redis 연결 성공: {redis_url}:{redis_port}")
            
        except Exception as e:
            logger.warning(f"Redis 연결 실패, 로컬 캐시만 사용: {str(e)}")
            self.redis_client = None
    
    def _generate_cache_key(self, prefix: str, **kwargs) -> str:
        """캐시 키 생성"""
        # kwargs를 정렬된 문자열로 변환
        key_data = f"{prefix}:" + ":".join([f"{k}={v}" for k, v in sorted(kwargs.items())])
        
        # 긴 키는 해시로 변환
        if len(key_data) > 200:
            return f"{prefix}:{hashlib.md5(key_data.encode()).hexdigest()}"
        
        return key_data
    
    def get(self, prefix: str, **kwargs) -> Optional[Dict[Any, Any]]:
        """캐시에서 데이터 조회"""
        cache_key = self._generate_cache_key(prefix, **kwargs)
        
        # 1. 로컬 캐시 확인
        if cache_key in self.local_cache:
            logger.debug(f"로컬 캐시 히트: {cache_key}")
            return self.local_cache[cache_key]
        
        # 2. Redis 캐시 확인
        if self.redis_client:
            try:
                cached_data = self.redis_client.get(cache_key)
                if cached_data:
                    data = json.loads(cached_data)
                    # 로컬 캐시에도 저장
                    self._add_to_local_cache(cache_key, data)
                    logger.debug(f"Redis 캐시 히트: {cache_key}")
                    return data
            except Exception as e:
                logger.warning(f"Redis 조회 실패: {str(e)}")
        
        return None
    
    def set(self, prefix: str, data: Dict[Any, Any], expire_seconds: int = 3600, **kwargs):
        """캐시에 데이터 저장"""
        cache_key = self._generate_cache_key(prefix, **kwargs)
        
        # 1. 로컬 캐시에 저장
        self._add_to_local_cache(cache_key, data)
        
        # 2. Redis에 저장
        if self.redis_client:
            try:
                self.redis_client.setex(
                    cache_key, 
                    expire_seconds, 
                    json.dumps(data, ensure_ascii=False)
                )
                logger.debug(f"Redis 캐시 저장: {cache_key}")
            except Exception as e:
                logger.warning(f"Redis 저장 실패: {str(e)}")
    
    def _add_to_local_cache(self, key: str, data: Dict[Any, Any]):
        """로컬 캐시에 데이터 추가 (LRU 방식)"""
        # 캐시 크기 제한
        if len(self.local_cache) >= self.max_local_cache_size:
            # 가장 오래된 항목 제거 (간단한 구현)
            oldest_key = next(iter(self.local_cache))
            del self.local_cache[oldest_key]
        
        self.local_cache[key] = data
    
    def delete(self, prefix: str, **kwargs):
        """캐시에서 데이터 삭제"""
        cache_key = self._generate_cache_key(prefix, **kwargs)
        
        # 로컬 캐시에서 삭제
        if cache_key in self.local_cache:
            del self.local_cache[cache_key]
        
        # Redis에서 삭제
        if self.redis_client:
            try:
                self.redis_client.delete(cache_key)
            except Exception as e:
                logger.warning(f"Redis 삭제 실패: {str(e)}")

# 전역 캐시 매니저 인스턴스
cache_manager = CacheManager()

def cached_result(prefix: str, expire_seconds: int = 3600):
    """함수 결과를 캐시하는 데코레이터"""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            # 캐시 키 생성용 파라미터 추출
            cache_params = {}
            
            # 함수 인자들을 캐시 키에 포함
            if args:
                cache_params['args'] = str(args)
            if kwargs:
                cache_params.update(kwargs)
            
            # 캐시에서 조회
            cached_data = cache_manager.get(prefix, **cache_params)
            if cached_data:
                return cached_data
            
            # 캐시 미스 시 함수 실행
            result = func(*args, **kwargs)
            
            # 결과를 캐시에 저장 (None이 아닌 경우에만)
            if result is not None:
                cache_manager.set(prefix, result, expire_seconds, **cache_params)
            
            return result
        return wrapper
    return decorator

def cached_method(prefix: str, expire_seconds: int = 3600):
    """클래스 메서드 결과를 캐시하는 데코레이터"""
    def decorator(func):
        @wraps(func)
        def wrapper(self, *args, **kwargs):
            # 캐시 키 생성용 파라미터 추출
            cache_params = {}
            
            # self는 제외하고 나머지 인자들만 캐시 키에 포함
            if args:
                cache_params['args'] = str(args)
            if kwargs:
                cache_params.update(kwargs)
            
            # 캐시에서 조회
            cached_data = cache_manager.get(prefix, **cache_params)
            if cached_data:
                return cached_data
            
            # 캐시 미스 시 메서드 실행
            result = func(self, *args, **kwargs)
            
            # 결과를 캐시에 저장 (None이 아닌 경우에만)
            if result is not None:
                cache_manager.set(prefix, result, expire_seconds, **cache_params)
            
            return result
        return wrapper
    return decorator