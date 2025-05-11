"""
Google Places API 검색 결과를 강화하는 모듈입니다.
"""

import logging
from place_types import PlaceTypesMapper, PlaceSearchFilter

logger = logging.getLogger(__name__)

class PlaceSearchEnhancer:
    """
    장소 검색 결과를 강화하는 클래스입니다.
    장소 유형 정보를 활용하여 검색 결과를 보강합니다.
    """
    
    def __init__(self):
        """
        장소 검색 강화기를 초기화합니다.
        """
        self.place_types_mapper = PlaceTypesMapper()
        self.place_search_filter = PlaceSearchFilter()
    
    def enhance_place_data(self, place_data, voice_input=None):
        """
        장소 데이터를 강화합니다.
        장소 유형 정보를 활용하여 카테고리를 결정하고 관련 정보를 추가합니다.
        
        Args:
            place_data: Google Places API에서 반환한 장소 데이터
            voice_input: 원본 음성 입력 (선택 사항)
            
        Returns:
            강화된 장소 데이터
        """
        if not place_data:
            return place_data
        
        # 장소 유형이 있는 경우 카테고리 결정
        if 'types' in place_data and place_data['types']:
            category = self.place_types_mapper.determine_category_from_types(place_data['types'])
            place_data['category'] = category
        
        # 내부 시스템에 맞게 데이터 형식 조정
        self._adjust_data_format(place_data)
        
        return place_data
    
    def get_search_params(self, search_term, voice_input):
        """
        음성 입력을 분석하여 검색 파라미터를 생성합니다.
        
        Args:
            search_term: 검색어 
            voice_input: 원본 음성 입력
            
        Returns:
            검색 파라미터 딕셔너리
        """
        params = {"input": search_term}
        
        # 음성 입력이 있으면 필터 생성
        if voice_input:
            # 레거시 API용 type 파라미터
            type_filter = self.place_search_filter.get_type_filter_param(voice_input)
            if type_filter:
                params["type"] = type_filter
            
            # 신규 API용 포함/제외 필터
            filter_config = self.place_search_filter.create_filter_from_voice(voice_input)
            if 'includedTypes' in filter_config:
                params["includedTypes"] = filter_config['includedTypes']
            if 'excludedTypes' in filter_config:
                params["excludedTypes"] = filter_config['excludedTypes']
        
        return params
    
    def _adjust_data_format(self, place_data):
        """
        내부 시스템 형식에 맞게 데이터를 조정합니다.
        
        Args:
            place_data: 조정할 장소 데이터
        """
        # 필요한 경우 형식 변환이나 필드 추가 수행
        pass