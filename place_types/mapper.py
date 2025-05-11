"""
Google Places API의 장소 유형과 내부 카테고리 간 매핑을 처리하는 모듈입니다.
"""

import os
import json
import logging
from .constants import (
    DEFAULT_GOOGLE_TO_INTERNAL, 
    DEFAULT_INTERNAL_TO_GOOGLE,
    TYPE_PRIORITY
)

logger = logging.getLogger(__name__)

class PlaceTypesMapper:
    """
    장소 유형 매핑을 관리하는 클래스입니다.
    Google Places API의 types와 내부 시스템의 카테고리 간 변환을 담당합니다.
    """
    
    def __init__(self, config_path='place_types/config/type_mappings.json'):
        """
        매퍼를 초기화합니다.
        
        Args:
            config_path: 매핑 설정 파일 경로
        """
        self.config_path = config_path
        self.google_to_internal = dict(DEFAULT_GOOGLE_TO_INTERNAL)
        self.internal_to_google = dict(DEFAULT_INTERNAL_TO_GOOGLE)
        self.type_priority = dict(TYPE_PRIORITY)
        self.last_modified = 0
        
        # 설정 파일이 존재하면 로드
        self._load_from_file()
    
    def _load_from_file(self):
        """설정 파일에서 매핑 정보를 로드합니다."""
        if not os.path.exists(self.config_path):
            logger.warning(f"매핑 설정 파일을 찾을 수 없습니다: {self.config_path}")
            return
        
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
            
            # 설정 파일에서 매핑 정보 업데이트
            if 'google_to_internal' in config:
                self.google_to_internal.update(config['google_to_internal'])
            
            if 'internal_to_google' in config:
                self.internal_to_google.update(config['internal_to_google'])
            
            if 'type_priority' in config:
                self.type_priority.update(config['type_priority'])
            
            # 파일 수정 시간 저장
            self.last_modified = os.path.getmtime(self.config_path)
            logger.info(f"매핑 설정 파일을 로드했습니다: {self.config_path}")
            
        except Exception as e:
            logger.error(f"매핑 설정 파일 로드 중 오류 발생: {str(e)}")
    
    def refresh_if_needed(self):
        """필요한 경우 설정을 다시 로드합니다."""
        if os.path.exists(self.config_path):
            current_modified = os.path.getmtime(self.config_path)
            if current_modified > self.last_modified:
                self._load_from_file()
                return True
        return False
    
    def get_internal_category(self, google_type):
        """
        Google 장소 유형을 내부 카테고리로 변환합니다.
        
        Args:
            google_type: Google Places API의 장소 유형
            
        Returns:
            내부 카테고리 문자열
        """
        self.refresh_if_needed()
        return self.google_to_internal.get(google_type, "기타")
    
    def get_google_types(self, internal_category):
        """
        내부 카테고리를 Google 장소 유형 목록으로 변환합니다.
        
        Args:
            internal_category: 내부 카테고리 문자열
            
        Returns:
            Google 장소 유형 목록
        """
        self.refresh_if_needed()
        
        # 정확한 매칭 먼저 시도
        if internal_category in self.internal_to_google:
            return self.internal_to_google[internal_category]
        
        # 부분 매칭 시도
        for category, types in self.internal_to_google.items():
            if category in internal_category:
                return types
        
        # 매칭 실패 시 빈 목록 반환
        return []
    
    def determine_category_from_types(self, types_list):
        """
        Google 장소 유형 목록에서 가장 적합한 내부 카테고리를 결정합니다.
        
        Args:
            types_list: Google Places API의 장소 유형 목록
            
        Returns:
            내부 카테고리 문자열
        """
        if not types_list:
            return "기타"
        
        self.refresh_if_needed()
        
        # 우선순위가 가장 높은 유형 찾기
        matched_types = []
        for type_name in types_list:
            if type_name in self.google_to_internal:
                priority = self.type_priority.get(type_name, 0)
                matched_types.append((type_name, priority))
        
        if matched_types:
            # 우선순위 기준으로 정렬
            matched_types.sort(key=lambda x: x[1], reverse=True)
            # 가장 우선순위가 높은 유형의 카테고리 반환
            return self.google_to_internal[matched_types[0][0]]
        
        return "기타"