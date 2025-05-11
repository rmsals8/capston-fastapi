"""
장소 검색 결과를 강화하고 개선하는 기능을 제공하는 모듈입니다.
"""

import logging
import re
from datetime import datetime
from typing import Dict, List, Any, Optional, Tuple

logger = logging.getLogger(__name__)

class PlaceSearchEnhancer:
    """
    장소 검색 결과를 강화하고 개선하는 클래스입니다.
    음성 입력 분석, 검색 파라미터 생성, 결과 데이터 보강 등의 기능을 제공합니다.
    """
    
    def __init__(self, place_types_mapper=None, place_filter=None):
        """
        강화기를 초기화합니다.
        
        Args:
            place_types_mapper: 장소 유형 매핑을 처리하는 매퍼 객체
            place_filter: 장소 필터링을 처리하는 필터 객체
        """
        self.place_types_mapper = place_types_mapper
        self.place_filter = place_filter
    
    def get_search_params(self, search_term: str, voice_input: str) -> Dict[str, Any]:
        """
        음성 입력을 분석하여 검색 파라미터를 생성합니다.
        
        Args:
            search_term: 기본 검색어
            voice_input: 사용자 음성 입력 문자열
            
        Returns:
            검색 파라미터 딕셔너리
        """
        params = {
            "query": search_term
        }
        
        # 필터 객체가 있으면 필터 적용
        if self.place_filter:
            filter_config = self.place_filter.create_filter_from_voice(voice_input)
            if filter_config:
                params.update(filter_config)
        
        # 추가 컨텍스트 분석
        voice_lower = voice_input.lower()
        
        # 거리 관련 키워드 추출 (예: 100미터 이내, 3km 근처)
        radius = self._extract_radius(voice_lower)
        if radius:
            params["radius"] = radius
        
        # 지역 컨텍스트 추출 (예: 서울에서, 부산 근처)
        region = self._extract_region(voice_lower)
        if region:
            params["region"] = region
        
        # 개수 제한 추출 (예: 5개, 10곳)
        limit = self._extract_limit(voice_lower)
        if limit:
            params["limit"] = limit
        
        # 정렬 기준 추출 (예: 별점순, 거리순)
        sort_by = self._extract_sort_criteria(voice_lower)
        if sort_by:
            params["sort_by"] = sort_by
        
        # 개장 여부 추출 (예: 지금 열려있는, 영업중)
        is_open = self._is_open_now_requested(voice_lower)
        if is_open:
            params["open_now"] = True
        
        logger.debug(f"생성된 검색 파라미터: {params}")
        return params
    
    def enhance_place_data(self, place_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        장소 데이터에 추가 정보를 보강합니다.
        
        Args:
            place_data: 장소 데이터 딕셔너리
            
        Returns:
            보강된 장소 데이터 딕셔너리
        """
        if not place_data:
            return place_data
        
        # 복사본 생성하여 원본 데이터 보존
        enhanced_data = dict(place_data)
        
        # types 정보가 있으면 카테고리 정보 추가
        if 'types' in enhanced_data and enhanced_data['types'] and self.place_types_mapper:
            types_list = enhanced_data['types']
            category = self.place_types_mapper.determine_category_from_types(types_list)
            enhanced_data['category'] = category
        
        # 영업 시간 데이터 개선
        if 'opening_hours' in enhanced_data:
            enhanced_data['opening_hours'] = self._enhance_opening_hours(enhanced_data['opening_hours'])
        
        # 주소 데이터 개선
        if 'formatted_address' in enhanced_data:
            enhanced_data['formatted_address'] = self._enhance_address(enhanced_data['formatted_address'])
        
        # 전화번호 형식 개선
        if 'formatted_phone_number' in enhanced_data:
            enhanced_data['formatted_phone_number'] = self._enhance_phone_number(enhanced_data['formatted_phone_number'])
        
        # 가격 수준 문자열 추가
        if 'price_level' in enhanced_data:
            enhanced_data['price_level_text'] = self._get_price_level_text(enhanced_data['price_level'])
        
        # 별점 표시 개선
        if 'rating' in enhanced_data:
            enhanced_data['rating_display'] = self._get_rating_display(enhanced_data['rating'])
        
        # 위도/경도 값 확인 및 보정
        if 'geometry' in enhanced_data and 'location' in enhanced_data['geometry']:
            enhanced_data['geometry']['location'] = self._validate_coordinates(
                enhanced_data['geometry']['location']
            )
        
        return enhanced_data
    
    def rank_and_merge_results(self, results: List[Dict[str, Any]], voice_input: str) -> List[Dict[str, Any]]:
        """
        검색 결과를 음성 의도에 맞게 순위를 부여하고 병합합니다.
        
        Args:
            results: 검색 결과 목록
            voice_input: 사용자 음성 입력 문자열
            
        Returns:
            순위가 부여된 검색 결과 목록
        """
        if not results:
            return []
        
        # 각 검색 결과에 점수 부여
        scored_results = []
        voice_lower = voice_input.lower()
        
        for result in results:
            # 기본 점수
            score = 0
            
            # types 매칭 점수
            if 'types' in result and result['types'] and self.place_types_mapper:
                for place_type in result['types']:
                    # 우선순위가 높은 유형에 더 높은 점수 부여
                    priority = self.place_types_mapper.type_priority.get(place_type, 0)
                    score += priority / 10  # 0~10 범위의 점수로 정규화
            
            # 이름 매칭 점수
            if 'name' in result:
                name = result['name'].lower()
                # 이름이 완전히 일치할 경우 높은 점수
                if search_term := self._extract_search_term(voice_lower):
                    if search_term.lower() == name:
                        score += 20
                    elif search_term.lower() in name:
                        score += 10
                
                # 관련 키워드 포함 시 추가 점수
                for keyword in self._extract_keywords(voice_lower):
                    if keyword in name:
                        score += 5
            
            # 평점 점수 (높은 평점에 추가 점수)
            if 'rating' in result:
                score += result['rating'] * 2
            
            # 인기도 점수
            if 'user_ratings_total' in result:
                # 리뷰 수가 많을수록 더 높은 점수 (로그 스케일로 정규화)
                import math
                score += min(10, math.log(result['user_ratings_total'] + 1, 10) * 3)
            
            # 거리 점수 (가까울수록 점수 높음)
            if 'distance' in result:
                # 거리에 반비례하는 점수 (최대 10점)
                distance_km = result['distance'] / 1000
                if distance_km < 0.5:
                    score += 10
                elif distance_km < 1:
                    score += 8
                elif distance_km < 2:
                    score += 6
                elif distance_km < 5:
                    score += 4
                elif distance_km < 10:
                    score += 2
            
            scored_results.append((result, score))
        
        # 점수 기준으로 내림차순 정렬
        scored_results.sort(key=lambda x: x[1], reverse=True)
        
        # 결과 배열 반환 (점수 제외)
        return [item[0] for item in scored_results]
    
    def process_search_results(self, results: List[Dict[str, Any]], voice_input: str) -> List[Dict[str, Any]]:
        """
        검색 결과를 처리하고 강화합니다.
        
        Args:
            results: 원본 검색 결과 목록
            voice_input: 사용자 음성 입력 문자열
            
        Returns:
            처리된 검색 결과 목록
        """
        # 결과가 없으면 빈 리스트 반환
        if not results:
            return []
        
        # 각 결과 강화
        enhanced_results = [self.enhance_place_data(result) for result in results]
        
        # 결과 랭킹 및 병합
        ranked_results = self.rank_and_merge_results(enhanced_results, voice_input)
        
        return ranked_results
    
    def _extract_radius(self, voice_input: str) -> Optional[int]:
        """
        음성 입력에서 검색 반경 추출
        
        Args:
            voice_input: 음성 입력 문자열
            
        Returns:
            검색 반경(미터) 또는 None
        """
        # 거리 정규식 패턴 (예: 500m, 1km, 2키로, 반경 3km 등)
        patterns = [
            r'(\d+)\s*미터',
            r'(\d+)\s*m',
            r'(\d+)\s*[키킬]로',
            r'(\d+)\s*km',
            r'반경\s*(\d+)\s*미터',
            r'반경\s*(\d+)\s*m',
            r'반경\s*(\d+)\s*[키킬]로',
            r'반경\s*(\d+)\s*km',
            r'(\d+)\s*미터\s*[이내안]',
            r'(\d+)\s*m\s*[이내안]',
            r'(\d+)\s*[키킬]로\s*[이내안]',
            r'(\d+)\s*km\s*[이내안]'
        ]
        
        for pattern in patterns:
            match = re.search(pattern, voice_input)
            if match:
                distance = int(match.group(1))
                if '로' in pattern or 'km' in pattern:
                    # 킬로미터를 미터로 변환
                    return distance * 1000
                return distance
        
        return None
    
    def _extract_region(self, voice_input: str) -> Optional[str]:
        """
        음성 입력에서 지역 정보 추출
        
        Args:
            voice_input: 음성 입력 문자열
            
        Returns:
            지역 문자열 또는 None
        """
        # 주요 도시 및 지역 목록
        regions = [
            '서울', '부산', '인천', '대구', '광주', '대전', '울산', '세종',
            '경기', '강원', '충북', '충남', '전북', '전남', '경북', '경남', '제주',
            '강남', '송파', '마포', '종로', '중구', '서초', '용산', '영등포'
        ]
        
        # 지역 뒤에 올 수 있는 조사 또는 단어 패턴
        patterns = [
            r'({})[에서의]',
            r'({})[에있는의]',
            r'({})[에있는]',
            r'({})[지역의에]',
            r'({})[근처인근주변]',
            r'({})[의]'
        ]
        
        for region in regions:
            for pattern in patterns:
                match = re.search(pattern.format(region), voice_input)
                if match:
                    return match.group(1)
            
            # 단순히 지역명이 포함된 경우
            if region in voice_input:
                return region
        
        return None
    
    def _extract_limit(self, voice_input: str) -> Optional[int]:
        """
        음성 입력에서 결과 개수 제한 추출
        
        Args:
            voice_input: 음성 입력 문자열
            
        Returns:
            결과 제한 개수 또는 None
        """
        # 개수 정규식 패턴
        patterns = [
            r'(\d+)\s*개',
            r'(\d+)\s*곳',
            r'(\d+)\s*군데',
            r'(\d+)\s*장소',
            r'(\d+)\s*개\s*[만보여줘알려줘찾아]',
            r'(\d+)\s*곳\s*[만보여줘알려줘찾아]',
            r'(\d+)\s*군데\s*[만보여줘알려줘찾아]',
            r'(\d+)\s*장소\s*[만보여줘알려줘찾아]'
        ]
        
        for pattern in patterns:
            match = re.search(pattern, voice_input)
            if match:
                limit = int(match.group(1))
                # 합리적인 범위로 제한
                return min(max(1, limit), 20)
        
        return None
    
    def _extract_sort_criteria(self, voice_input: str) -> Optional[str]:
        """
        음성 입력에서 정렬 기준 추출
        
        Args:
            voice_input: 음성 입력 문자열
            
        Returns:
            정렬 기준 문자열 또는 None
        """
        # 거리순
        if any(keyword in voice_input for keyword in ['가까운', '거리순', '근처', '주변']):
            return 'distance'
        
        # 평점순
        if any(keyword in voice_input for keyword in ['평점순', '별점순', '높은평점', '좋은평점', '리뷰좋은']):
            return 'rating'
        
        # 인기순
        if any(keyword in voice_input for keyword in ['인기순', '인기있는', '유명한', '방문많은', '리뷰많은']):
            return 'popularity'
        
        # 가격순 (낮은 가격순)
        if any(keyword in voice_input for keyword in ['저렴한', '싼', '가격저렴', '가격낮은']):
            return 'price_asc'
        
        # 가격순 (높은 가격순)
        if any(keyword in voice_input for keyword in ['비싼', '고급', '가격높은']):
            return 'price_desc'
        
        return None
    
    def _is_open_now_requested(self, voice_input: str) -> bool:
        """
        현재 영업중인 장소를 요청했는지 확인
        
        Args:
            voice_input: 음성 입력 문자열
            
        Returns:
            현재 영업중 필터 적용 여부
        """
        open_now_keywords = [
            '지금 열려있는', '영업중인', '영업중', '영업시간인', 
            '문연', '오픈한', '열린', '여는', '영업하는'
        ]
        
        return any(keyword in voice_input for keyword in open_now_keywords)
    
    def _extract_search_term(self, voice_input: str) -> Optional[str]:
        """
        음성 입력에서 주요 검색어 추출
        
        Args:
            voice_input: 음성 입력 문자열
            
        Returns:
            주요 검색어 또는 None
        """
        # 검색어를 나타내는 패턴
        patterns = [
            r'(.+)[을를]\s*찾아',
            r'(.+)[을를]\s*검색',
            r'(.+)[은는]\s*어디',
            r'(.+)[\s위치장소]',
            r'(.+)[이가]\s*있는',
            r'(.+)[을를]\s*보여',
            r'(.+)[을를]\s*알려'
        ]
        
        for pattern in patterns:
            match = re.search(pattern, voice_input)
            if match:
                return match.group(1).strip()
        
        return None
    
    def _extract_keywords(self, voice_input: str) -> List[str]:
        """
        음성 입력에서 관련 키워드 추출
        
        Args:
            voice_input: 음성 입력 문자열
            
        Returns:
            관련 키워드 목록
        """
        # 일반적인 키워드 제외 (조사, 일반 동사 등)
        exclude_words = ['을', '를', '은', '는', '이', '가', '에', '서', '의', '에서', '로', '으로', 
                         '있는', '찾아', '보여', '알려', '주는', '가는', '주변', '근처', '내']
        
        # 입력을 단어로 분리
        words = re.findall(r'\w+', voice_input)
        
        # 제외 단어 필터링 및 중복 제거
        return [word for word in words if word not in exclude_words]
    
    def _enhance_opening_hours(self, opening_hours: Dict[str, Any]) -> Dict[str, Any]:
        """
        영업 시간 데이터 개선
        
        Args:
            opening_hours: 영업 시간 데이터
            
        Returns:
            개선된 영업 시간 데이터
        """
        if not opening_hours:
            return opening_hours
        
        # 복사본 생성
        enhanced = dict(opening_hours)
        
        # 현재 시간 기준 영업 상태 확인
        if 'open_now' in enhanced:
            enhanced['status_text'] = '영업 중' if enhanced['open_now'] else '영업 종료'
        
        # 오늘의 영업 시간 추출
        if 'periods' in enhanced:
            today_idx = datetime.now().weekday()
            for period in enhanced['periods']:
                if period.get('open', {}).get('day', -1) == today_idx:
                    open_time = period.get('open', {}).get('time', '')
                    close_time = period.get('close', {}).get('time', '')
                    
                    if open_time and close_time:
                        # "0930"을 "09:30"으로 변환
                        open_formatted = f"{open_time[:2]}:{open_time[2:]}"
                        close_formatted = f"{close_time[:2]}:{close_time[2:]}"
                        enhanced['today_hours'] = f"{open_formatted} - {close_formatted}"
                    break
        
        return enhanced
    
    def _enhance_address(self, address: str) -> str:
        """
        주소 데이터 개선
        
        Args:
            address: 주소 문자열
            
        Returns:
            개선된 주소 문자열
        """
        if not address:
            return address
        
        # 주소 개선 로직 (예: 불필요한 세부 정보 제거, 지역 정보 보강 등)
        # 대한민국 제거 (반복적)
        address = address.replace('대한민국 ', '')
        
        # 시도 약어 통일
        address = address.replace('서울시', '서울특별시')
        address = address.replace('서울 ', '서울특별시 ')
        address = address.replace('서울특별시특별시', '서울특별시')  # 중복 수정
        
        # 기타 주소 형식 개선 로직 추가 가능
        
        return address
    
    def _enhance_phone_number(self, phone_number: str) -> str:
        """
        전화번호 형식 개선
        
        Args:
            phone_number: 전화번호 문자열
            
        Returns:
            개선된 전화번호 문자열
        """
        if not phone_number:
            return phone_number
        
        # 한국 전화번호 형식 적용
        # 국가 코드 처리 (+82 → 0)
        if phone_number.startswith('+82 '):
            phone_number = '0' + phone_number[4:]
        
        # '-' 구분자 추가 (없는 경우)
        if '-' not in phone_number:
            # 전화번호 패턴에 따라 하이픈 추가
            digits = re.sub(r'\D', '', phone_number)
            if len(digits) == 10:  # 지역번호 2자리 (02-XXXX-XXXX)
                if digits.startswith('02'):
                    phone_number = f'02-{digits[2:6]}-{digits[6:]}'
                else:  # 휴대폰 번호 (010-XXX-XXXX)
                    phone_number = f'{digits[:3]}-{digits[3:7]}-{digits[7:]}'
            elif len(digits) == 11:  # 지역번호 3자리 또는 휴대폰 (0XX-XXXX-XXXX)
                phone_number = f'{digits[:3]}-{digits[3:7]}-{digits[7:]}'
        
        return phone_number
    
    def _get_price_level_text(self, price_level: int) -> str:
        """
        가격 수준 정수를 문자열로 변환
        
        Args:
            price_level: 가격 수준 (0-4)
            
        Returns:
            가격 수준 문자열
        """
        price_texts = {
            0: '무료',
            1: '저렴',
            2: '보통',
            3: '고급',
            4: '매우 고급'
        }
        
        return price_texts.get(price_level, '정보 없음')
    
    def _get_rating_display(self, rating: float) -> str:
        """
        별점을 표시 문자열로 변환
        
        Args:
            rating: 별점 (0-5)
            
        Returns:
            별점 표시 문자열
        """
        if not rating:
            return '평점 없음'
        
        # 소수점 한 자리로 반올림
        rounded_rating = round(rating, 1)
        
        # ★ 기호를 사용한 시각적 표현
        stars = '★' * int(rounded_rating)
        half_star = '☆' if rounded_rating % 1 >= 0.5 else ''
        
        return f"{stars}{half_star} ({rounded_rating})"
    
    def _validate_coordinates(self, location: Dict[str, float]) -> Dict[str, float]:
        """
        위도/경도 값 확인 및 보정
        
        Args:
            location: 위치 좌표 딕셔너리 {'lat': float, 'lng': float}
            
        Returns:
            검증된 위치 좌표 딕셔너리
        """
        if not location:
            # 기본값: 서울시청
            return {'lat': 37.5665, 'lng': 126.9780}
        
        # 복사본 생성
        validated = dict(location)
        
        # 위도 범위 검증 (-90 ~ 90)
        if 'lat' in validated:
            validated['lat'] = max(-90, min(90, validated['lat']))
        
        # 경도 범위 검증 (-180 ~ 180)
        if 'lng' in validated:
            validated['lng'] = max(-180, min(180, validated['lng']))
        
        return validated