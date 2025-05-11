"""
Google Places API 검색 시 사용할 필터를 생성하는 모듈입니다.
"""

import os
import json
import logging
from .constants import VOICE_KEYWORD_TO_TYPES

logger = logging.getLogger(__name__)

class PlaceSearchFilter:
    """
    장소 검색 필터를 생성하는 클래스입니다.
    음성 명령어 분석 및 컨텍스트 기반으로 최적의 검색 필터를 생성합니다.
    """
    
    def __init__(self, config_path='place_types/config/filter_rules.json'):
        """
        필터 생성기를 초기화합니다.
        
        Args:
            config_path: 필터 규칙 설정 파일 경로
        """
        self.config_path = config_path
        self.keyword_to_types = dict(VOICE_KEYWORD_TO_TYPES)
        self.last_modified = 0
        
        # 설정 파일이 존재하면 로드
        self._load_from_file()
    
    def _load_from_file(self):
        """설정 파일에서 필터 규칙을 로드합니다."""
        if not os.path.exists(self.config_path):
            logger.warning(f"필터 규칙 설정 파일을 찾을 수 없습니다: {self.config_path}")
            return
        
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
            
            if 'keyword_to_types' in config:
                self.keyword_to_types.update(config['keyword_to_types'])
            
            # 파일 수정 시간 저장
            self.last_modified = os.path.getmtime(self.config_path)
            logger.info(f"필터 규칙 설정 파일을 로드했습니다: {self.config_path}")
            
        except Exception as e:
            logger.error(f"필터 규칙 설정 파일 로드 중 오류 발생: {str(e)}")
    
    def refresh_if_needed(self):
        """필요한 경우 설정을 다시 로드합니다."""
        if os.path.exists(self.config_path):
            current_modified = os.path.getmtime(self.config_path)
            if current_modified > self.last_modified:
                self._load_from_file()
                return True
        return False
    
    def create_filter_from_voice(self, voice_input):
        """
        음성 입력을 분석하여 검색 필터를 생성합니다.
        
        Args:
            voice_input: 사용자 음성 입력 문자열
            
        Returns:
            검색 필터 딕셔너리 {'includedTypes': [...], 'excludedTypes': [...]}
        """
        self.refresh_if_needed()
        voice_lower = voice_input.lower()
        
        included_types = set()
        excluded_types = set()
        
        # 음성 입력에서 키워드 탐색
        for keyword, filter_config in self.keyword_to_types.items():
            if keyword in voice_lower:
                # 포함할 유형 추가
                if 'includedTypes' in filter_config:
                    included_types.update(filter_config['includedTypes'])
                
                # 제외할 유형 추가
                if 'excludedTypes' in filter_config:
                    excluded_types.update(filter_config['excludedTypes'])
        
        # 포함 유형과 제외 유형 간 충돌 해결
        # 만약 동일한 유형이 포함과 제외 모두에 있다면, 포함 우선
        excluded_types = excluded_types - included_types
        
        result = {}
        if included_types:
            result['includedTypes'] = list(included_types)
        if excluded_types:
            result['excludedTypes'] = list(excluded_types)
        
        return result
    
    def get_type_filter_param(self, voice_input):
        """
        음성 입력을 분석하여 type 필터 파라미터 값을 생성합니다.
        (레거시 API용)
        
        Args:
            voice_input: 사용자 음성 입력 문자열
            
        Returns:
            type 파라미터에 사용할 값 (문자열) 또는 None
        """
        filter_config = self.create_filter_from_voice(voice_input)
        
        # 레거시 API는 하나의 type만 지원
        if 'includedTypes' in filter_config and filter_config['includedTypes']:
            # 첫 번째 유형만 반환
            return filter_config['includedTypes'][0]
        
        return None