import logging
from concurrent.futures import ThreadPoolExecutor
from fastapi import FastAPI, HTTPException, Body
from pydantic import BaseModel, Field
from langchain_openai import ChatOpenAI
from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import JsonOutputParser
from langchain.chains import LLMChain
from typing import Dict, List, Any, Optional, Tuple, Set
import os
import json
import re
import time
import requests
import datetime
from dotenv import load_dotenv
from geopy.distance import geodesic
import math
import random
import logging
import aiohttp
import asyncio
from functools import lru_cache
from fastapi.middleware.cors import CORSMiddleware
from scheduler.utils import detect_and_resolve_time_conflicts
from scheduler import (
    create_schedule_chain, 
    create_enhancement_chain,
    apply_time_inference,
    apply_priorities,
    enhance_schedule_with_relationships,
    parse_datetime
)
# 환경 변수 로드
load_dotenv()

logger = logging.getLogger(__name__)
# API 키 설정 (실제 운영 환경에서는 환경 변수에서 불러오는 것이 좋습니다)
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY") 
GOOGLE_MAPS_API_KEY = os.getenv("GOOGLE_MAPS_API_KEY")

# FastAPI 앱 초기화
app = FastAPI(title="일정 추출 및 위치 정보 보강 API", 
              description="음성 입력에서 일정을 추출하고 위치 정보를 보강하는 API",
              version="1.0.0")

# CORS 미들웨어 설정
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 모든 오리진 허용 (프로덕션에서는 특정 오리진으로 제한하는 것이 좋음)
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ----- 모델 정의 (일정 추출 API) -----
async def run_sync_in_thread(func, *args, **kwargs):
    """동기 함수를 별도 스레드에서 비동기로 실행"""
    loop = asyncio.get_event_loop()
    with ThreadPoolExecutor() as executor:
        return await loop.run_in_executor(executor, func, *args, **kwargs)

class AsyncGooglePlacesTool:
    """비동기 Google Places API 클라이언트"""
    
    def __init__(self, api_key=None):
        self.api_key = api_key or GOOGLE_MAPS_API_KEY
        if not self.api_key:
            raise ValueError("Google Maps API 키가 필요합니다.")
        self.search_cache = {}
        self.logger = logging.getLogger('async_google_places_tool')
        self.default_timeout = 30
        self.max_retries = 2
        self.retry_delay = 1
    async def search_place_detailed(self, query: str, place_type: str = None) -> Optional[Dict]:
        """향상된 장소 검색 - 기존 메소드명 유지하면서 내부 로직 강화"""
        self.logger.info(f"향상된 장소 검색 시작: '{query}', 타입: {place_type or '없음'}")
        
        # 1단계: 기본 검색 시도
        result = await self._basic_place_search(query, place_type)
        
        if result and self.validate_address_quality(result.get('formatted_address', ''), query):
            self.logger.info(f"1단계 검색 성공 (고품질): {result.get('name')}")
            return result
        
        # 2단계: 자연어 분석 및 재검색
        if "근처" in query or "인근" in query or "주변" in query:
            self.logger.info("2단계: 자연어 분석 기반 재검색 시도")
            
            # GPT로 장소와 카테고리 추출
            extracted = self.extract_location_and_category(query)
            
            # 추출된 정확한 장소명으로 재검색
            if extracted.get('location') != query:
                improved_result = await self._basic_place_search(extracted['location'], place_type)
                
                if improved_result and self.validate_address_quality(improved_result.get('formatted_address', ''), extracted['location']):
                    self.logger.info(f"2단계 검색 성공: {improved_result.get('name')}")
                    return improved_result
        
        # 3단계: 주변 검색으로 대체
        if result and result.get('latitude') and result.get('longitude'):
            self.logger.info("3단계: 주변 검색으로 더 정확한 결과 찾기")
            
            # 기존 결과의 좌표를 기준으로 주변 검색
            center_coords = (result['latitude'], result['longitude'])
            
            # 카테고리 추출
            if place_type:
                search_type = place_type
                category = self._get_category_from_type(place_type)
            else:
                category = self._extract_category_from_query(query)
                search_type = get_place_type(category) or "point_of_interest"
            
            nearby_places = self.search_nearby_with_validation(center_coords, category, search_type, 1000)
            
            if nearby_places:
                # 가장 가까운 장소 선택
                best_place = nearby_places[0]
                self.logger.info(f"3단계 검색 성공 (주변 검색): {best_place.get('name')}")
                return best_place
        
        # 4단계: 원본 결과라도 반환 (완전 실패 방지)
        if result:
            self.logger.info(f"원본 검색 결과 반환: {result.get('name')}")
            return result
        
        self.logger.warning(f"모든 검색 단계 실패: '{query}'")
        return None
    
    async def _basic_place_search(self, query: str, place_type: str = None) -> Optional[Dict]:
        """기본 장소 검색 - 비동기 버전"""
        try:
            from urllib.parse import quote
            import aiohttp
            
            # URL 인코딩
            encoded_query = quote(query)
            
            # 기본 필드 설정
            fields = "name,formatted_address,geometry,place_id,types,address_components,rating"
            
            # Places API 호출
            url = f"https://maps.googleapis.com/maps/api/place/findplacefromtext/json?input={encoded_query}&inputtype=textquery&fields={fields}&language=ko&region=kr&key={self.api_key}"
            
            # 장소 유형이 지정된 경우 추가
            if place_type:
                url += f"&locationbias=type:{place_type}"
            
            self.logger.info(f"기본 Places API 요청: '{query}', 유형: {place_type or '없음'}")
            
            # requests 대신 aiohttp 사용
            timeout = aiohttp.ClientTimeout(total=30)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(url) as response:
                    if response.status != 200:
                        self.logger.warning(f"API 호출 실패: {response.status}")
                        return None
                    
                    data = await response.json()
                    
                    if data['status'] == 'OK' and data.get('candidates') and len(data['candidates']) > 0:
                        candidate = data['candidates'][0]
                        
                        # 주소 구성 요소를 사용하여 보다 구체적인 주소 생성
                        address_components = candidate.get('address_components', [])
                        formatted_address = candidate.get('formatted_address', '')
                        
                        # 한국 주소 형식으로 개선
                        if address_components:
                            improved_address = self._improve_korean_address(address_components, formatted_address)
                            if improved_address:
                                formatted_address = improved_address
                        
                        place_types = candidate.get('types', [])
                        self.logger.info(f"기본 검색 결과: {candidate.get('name')}, 유형: {place_types}")
                        
                        return {
                            'name': candidate.get('name', query),
                            'formatted_address': formatted_address,
                            'latitude': candidate['geometry']['location']['lat'],
                            'longitude': candidate['geometry']['location']['lng'],
                            'place_id': candidate.get('place_id', ''),
                            'types': place_types,
                            'rating': candidate.get('rating')
                        }
                    else:
                        self.logger.warning(f"검색 결과 없음: {data['status']}")
                        return None
                        
        except Exception as e:
            self.logger.error(f"기본 장소 검색 오류: {str(e)}")
            return None
    
    def _improve_korean_address(self, address_components: list, original_address: str) -> str:
        """한국 주소 형식 개선 (paste.txt 로직 참조)"""
        try:
            address_parts = {}
            for component in address_components:
                for type in component.get('types', []):
                    address_parts[type] = component.get('long_name')
            
            # 한국 주소 형식으로 구성
            if 'country' in address_parts and address_parts['country'] == '대한민국':
                if 'administrative_area_level_1' in address_parts:  # 시/도
                    province = address_parts['administrative_area_level_1']
                    if '서울' in province and '특별시' not in province:
                        province = '서울특별시'
                    
                    detailed_address = province
                    
                    if 'sublocality_level_1' in address_parts:  # 구
                        detailed_address += f" {address_parts['sublocality_level_1']}"
                    
                    if 'sublocality_level_2' in address_parts:  # 동
                        detailed_address += f" {address_parts['sublocality_level_2']}"
                    
                    if 'premise' in address_parts or 'street_number' in address_parts:
                        if 'route' in address_parts:  # 도로명
                            detailed_address += f" {address_parts['route']}"
                        
                        if 'street_number' in address_parts:  # 건물번호
                            detailed_address += f" {address_parts['street_number']}"
                        
                        if 'premise' in address_parts:  # 건물명/층
                            detailed_address += f" {address_parts['premise']}"
                    
                    # 더 구체적인 주소가 생성되면 사용
                    if len(detailed_address.split()) >= len(original_address.split()):
                        return detailed_address
            
            return original_address
        except Exception as e:
            self.logger.error(f"한국 주소 개선 오류: {str(e)}")
            return original_address
    
    def _get_category_from_type(self, place_type: str) -> str:
        """place_type에서 카테고리명 추출"""
        type_to_category = {
            "restaurant": "식당",
            "cafe": "카페", 
            "shopping_mall": "쇼핑몰",
            "hospital": "병원",
            "university": "대학교",
            "school": "학교",
            "park": "공원",
            "stadium": "경기장"
        }
        return type_to_category.get(place_type, "장소")
    
    def _extract_category_from_query(self, query: str) -> str:
        """쿼리에서 카테고리 추출"""
        query_lower = query.lower()
        if any(word in query_lower for word in ["식당", "음식", "밥"]):
            return "식당"
        elif any(word in query_lower for word in ["카페", "커피"]):
            return "카페"
        elif any(word in query_lower for word in ["쇼핑", "마트"]):
            return "쇼핑몰"
        else:
            return "장소"
    
    def search_nearby_detailed(self, query: str, location: str = "37.4980,127.0276", radius: int = 1000, place_type: str = None) -> Optional[Dict]:
        """기존 메소드 유지 - 호환성을 위해"""
        try:
            # URL 인코딩
            encoded_query = requests.utils.quote(query)
            
            # Nearby Search API 호출
            url = f"https://maps.googleapis.com/maps/api/place/nearbysearch/json?location={location}&radius={radius}&keyword={encoded_query}&language=ko&key={self.api_key}"
            
            # 장소 유형이 지정된 경우 추가
            if place_type:
                url += f"&type={place_type}"
            
            self.logger.info(f"Nearby API 요청: '{query}', 위치: {location}, 반경: {radius}m, 유형: {place_type or '없음'}")
            
            response = requests.get(url, timeout=120)
            if response.status_code != 200:
                self.logger.warning(f"Nearby Places API 호출 실패: {response.status_code}")
                return None
            
            data = response.json()
            
            if data['status'] == 'OK' and data.get('results') and len(data['results']) > 0:
                # 결과 중 첫 번째 장소 선택
                top_place = data['results'][0]
                
                # Place Details API를 통해 더 자세한 정보 가져오기
                if top_place.get('place_id'):
                    detailed_place = self.get_place_details(top_place.get('place_id'))
                    if detailed_place:
                        return detailed_place
                
                # 기본 정보 반환
                return {
                    'name': top_place.get('name', ''),
                    'formatted_address': top_place.get('vicinity', ''),
                    'latitude': top_place['geometry']['location']['lat'],
                    'longitude': top_place['geometry']['location']['lng'],
                    'place_id': top_place.get('place_id', ''),
                    'types': top_place.get('types', [])
                }
            else:
                self.logger.warning(f"주변 장소를 찾을 수 없음: {data['status']}")
                return None
                
        except Exception as e:
            self.logger.error(f"주변 장소 검색 중 오류 발생: {str(e)}")
            return None


# 2. 동기 함수를 비동기로 래핑하는 유틸리티
async def run_in_executor(func, *args, **kwargs):
    """동기 함수를 비동기로 실행"""
    loop = asyncio.get_event_loop()
    with ThreadPoolExecutor() as executor:
        return await loop.run_in_executor(executor, func, *args, **kwargs)

# 3. 비동기 위치 정보 보강 함수
async def enhance_location_data_async(schedule_data: Dict) -> Dict:
    """비동기 위치 정보 보강"""
    logger.info("비동기 위치 정보 보강 시작...")
    
    try:
        places_tool = AsyncGooglePlacesTool()
        enhanced_data = json.loads(json.dumps(schedule_data))
        
        # 병렬 처리를 위한 태스크 리스트
        tasks = []
        
        # 고정 일정 처리 (최대 5개, 병렬 처리)
        fixed_schedules = enhanced_data.get("fixedSchedules", [])[:5]
        
        async def process_fixed_schedule(schedule):
            """개별 고정 일정 처리"""
            place_name = schedule.get("name", "")
            if not place_name:
                return schedule
            
            try:
                place_info = await places_tool.search_place_detailed_async(place_name)
                
                if place_info and place_info.get("formatted_address"):
                    schedule["location"] = place_info["formatted_address"]
                    schedule["latitude"] = place_info["latitude"]
                    schedule["longitude"] = place_info["longitude"]
                    logger.info(f"비동기 위치 정보 업데이트 성공: {place_name}")
                else:
                    # fallback 사용
                    category = get_simple_category(place_name)
                    fallback_locations = {
                        "식당": {"latitude": 37.5665, "longitude": 126.9780, "address": "서울특별시 중구"},
                        "카페": {"latitude": 37.5665, "longitude": 126.9780, "address": "서울특별시 중구"},
                        "대학교": {"latitude": 37.5665, "longitude": 126.9780, "address": "서울특별시"},
                    }
                    
                    if category in fallback_locations:
                        fallback = fallback_locations[category]
                        schedule["latitude"] = fallback["latitude"]
                        schedule["longitude"] = fallback["longitude"]
                        logger.info(f"fallback 위치 사용: {place_name}")
                        
            except Exception as e:
                logger.error(f"비동기 장소 검색 오류: {place_name}, {str(e)}")
            
            return schedule
        
        # 모든 고정 일정을 병렬로 처리
        if fixed_schedules:
            tasks = [process_fixed_schedule(schedule) for schedule in fixed_schedules]
            
            # asyncio.gather로 병렬 실행, timeout 적용
            try:
                processed_schedules = await asyncio.wait_for(
                    asyncio.gather(*tasks, return_exceptions=True), 
                    timeout=120  # 2분 제한
                )
                
                # 결과 적용
                for i, result in enumerate(processed_schedules):
                    if not isinstance(result, Exception):
                        enhanced_data["fixedSchedules"][i] = result
                        
            except asyncio.TimeoutError:
                logger.warning("위치 정보 보강 시간 초과, 기본값 사용")
        
        # 유연 일정은 간단하게 처리 (fallback만 사용)
        flexible_schedules = enhanced_data.get("flexibleSchedules", [])
        fallback_locations = {
            "식당": {"latitude": 37.5665, "longitude": 126.9780, "address": "서울특별시 중구"},
            "카페": {"latitude": 37.5665, "longitude": 126.9780, "address": "서울특별시 중구"},
            "대학교": {"latitude": 37.5665, "longitude": 126.9780, "address": "서울특별시"},
        }
        
        for schedule in flexible_schedules:
            category = get_simple_category(schedule.get("name", ""))
            if category in fallback_locations:
                fallback = fallback_locations[category]
                schedule["latitude"] = fallback["latitude"]
                schedule["longitude"] = fallback["longitude"]
                schedule["location"] = fallback["address"]
        
        logger.info("비동기 위치 정보 보강 완료")
        return enhanced_data
        
    except Exception as e:
        logger.error(f"비동기 위치 정보 보강 실패: {str(e)}")
        return schedule_data

def get_simple_category(place_name: str) -> str:
    """간단한 카테고리 분류"""
    name_lower = place_name.lower()
    if any(word in name_lower for word in ["식당", "음식", "레스토랑"]):
        return "식당"
    elif any(word in name_lower for word in ["카페", "커피"]):
        return "카페"
    elif any(word in name_lower for word in ["대학", "학교"]):
        return "대학교"
    else:
        return "기본"

# 4. 비동기 LLM 체인 처리
async def process_llm_chain_async(chain, input_data):
    """LLM 체인을 비동기로 처리"""
    try:
        # LLM 호출을 별도 스레드에서 실행 (동기 API이므로)
        result = await run_in_executor(
            lambda: chain.invoke(input_data)
        )
        return result
    except Exception as e:
        logger.error(f"비동기 LLM 처리 오류: {str(e)}")
        raise e
class ScheduleRequest(BaseModel):
    voice_input: str
# 5. 메인 비동기 처리 함수
async def process_schedule_with_timeout_async(request: ScheduleRequest) -> Dict[str, Any]:
    """비동기로 전체 일정 처리"""
    logger.info("비동기 일정 처리 시작")
    
    try:
        # 1. LLM 체인 생성 및 실행 (재시도 로직 포함)
        chain = create_schedule_chain()
        result = None
        
        for attempt in range(2):
            try:
                # LLM 호출을 비동기로 처리 (timeout 적용)
                result = await asyncio.wait_for(
                    process_llm_chain_async(chain, {"input": request.voice_input}),
                    timeout=60  # 1분 제한
                )
                break
            except asyncio.TimeoutError:
                logger.warning(f"LLM 호출 timeout (시도 {attempt + 1}/2)")
                if attempt == 1:
                    raise Exception("LLM 호출 최종 실패")
                await asyncio.sleep(1)
            except Exception as e:
                logger.warning(f"LLM 호출 실패 (시도 {attempt + 1}/2): {str(e)}")
                if attempt == 1:
                    raise e
                await asyncio.sleep(1)
        
        # 2. 결과 파싱
        if isinstance(result, str):
            json_match = re.search(r'({[\s\S]*})', result)
            if json_match:
                schedule_data = safe_parse_json(json_match.group(1))
            else:
                schedule_data = safe_parse_json(result)
        else:
            schedule_data = result
        
        # 3. 병렬 처리를 위한 태스크 생성
        tasks = []
        
        # 시간 추론 태스크
        async def apply_time_inference_async():
            try:
                enhancement_chains = create_enhancement_chain()
                return await run_in_executor(
                    apply_time_inference,
                    enhancement_chains["time_chain"],
                    request.voice_input,
                    schedule_data
                )
            except Exception as e:
                logger.warning(f"시간 추론 실패: {str(e)}")
                return schedule_data
        
        # 우선순위 분석 태스크
        async def apply_priorities_async(schedule_data_with_time):
            try:
                enhancement_chains = create_enhancement_chain()
                return await run_in_executor(
                    apply_priorities,
                    enhancement_chains["priority_chain"],
                    request.voice_input,
                    schedule_data_with_time
                )
            except Exception as e:
                logger.warning(f"우선순위 분석 실패: {str(e)}")
                return schedule_data_with_time
        
        # 4. 단계별 비동기 처리
        try:
            # 시간 추론
            schedule_data_with_time = await asyncio.wait_for(
                apply_time_inference_async(),
                timeout=60  # 1분 제한
            )
        except asyncio.TimeoutError:
            logger.warning("시간 추론 timeout, 원본 데이터 사용")
            schedule_data_with_time = schedule_data
        
        try:
            # 우선순위 분석
            enhanced_schedule_data = await asyncio.wait_for(
                apply_priorities_async(schedule_data_with_time),
                timeout=60  # 1분 제한
            )
        except asyncio.TimeoutError:
            logger.warning("우선순위 분석 timeout, 이전 단계 데이터 사용")
            enhanced_schedule_data = schedule_data_with_time
        
        try:
            # 충돌 해결 (동기 함수를 비동기로 실행)
            schedule_data_without_conflicts = await asyncio.wait_for(
                run_in_executor(detect_and_resolve_time_conflicts, enhanced_schedule_data),
                timeout=60  # 1분 제한
            )
        except asyncio.TimeoutError:
            logger.warning("충돌 해결 timeout, 이전 단계 데이터 사용")
            schedule_data_without_conflicts = enhanced_schedule_data
        
        try:
            # 관계 분석 (동기 함수를 비동기로 실행)
            final_enhanced_data = await asyncio.wait_for(
                run_in_executor(
                    enhance_schedule_with_relationships,
                    request.voice_input,
                    schedule_data_without_conflicts
                ),
                timeout=60  # 1분 제한
            )
        except asyncio.TimeoutError:
            logger.warning("관계 분석 timeout, 이전 단계 데이터 사용")
            final_enhanced_data = schedule_data_without_conflicts
        
        try:
            # 위치 정보 보강 (비동기 함수)
            location_enhanced_data = await asyncio.wait_for(
                enhance_location_data_async(final_enhanced_data),
                timeout=120  # 2분 제한
            )
        except asyncio.TimeoutError:
            logger.warning("위치 정보 보강 timeout, 이전 단계 데이터 사용")
            location_enhanced_data = final_enhanced_data
        
        # 5. 최종 데이터 정리
        all_schedules = []
        all_schedules.extend(location_enhanced_data.get("fixedSchedules", []))
        all_schedules.extend(location_enhanced_data.get("flexibleSchedules", []))
        
        fixed_schedules = [s for s in all_schedules if s.get("type") == "FIXED" and "startTime" in s and "endTime" in s]
        flexible_schedules = [s for s in all_schedules if s.get("type") != "FIXED" or "startTime" not in s or "endTime" not in s]
        
        final_data = location_enhanced_data.copy()
        final_data["fixedSchedules"] = fixed_schedules
        final_data["flexibleSchedules"] = flexible_schedules
        
        logger.info("비동기 일정 처리 완료")
        return final_data
        
    except Exception as e:
        logger.error(f"비동기 전체 처리 실패: {str(e)}")
        # 기본 응답 반환
        return {
            "fixedSchedules": [],
            "flexibleSchedules": []
        }
class GoogleMapsDirectionsTool:
    """Google Maps Directions API를 사용하여 실제 경로 정보를 검색하는 도구"""
    
    def __init__(self, api_key=None):
        self.api_key = api_key or GOOGLE_MAPS_API_KEY
        if not self.api_key:
            raise ValueError("Google Maps API 키가 필요합니다.")
        # 검색 결과 캐싱을 위한 딕셔너리
        self.directions_cache = {}
        # 로깅 설정
        self.logger = logging.getLogger('google_directions_tool')
        self.logger.setLevel(logging.INFO)
    
    @lru_cache(maxsize=100)
    def get_directions_cached(self, origin_lat, origin_lng, dest_lat, dest_lng, departure_time=None):
        """캐싱을 지원하는 경로 정보 검색 함수"""
        cache_key = f"{origin_lat}_{origin_lng}_{dest_lat}_{dest_lng}_{departure_time}"
        
        # 캐시에 있으면 반환
        if cache_key in self.directions_cache:
            self.logger.info(f"캐시에서 경로 결과 반환: '{cache_key}'")
            return self.directions_cache[cache_key]
        
        # 없으면 검색 실행
        result = self.get_directions(origin_lat, origin_lng, dest_lat, dest_lng, departure_time)
        
        # 결과가 있으면 캐시에 저장
        if result:
            self.directions_cache[cache_key] = result
            self.logger.info(f"경로 검색 결과 캐싱: '{cache_key}'")
        
        return result
    
    def get_directions(self, origin_lat, origin_lng, dest_lat, dest_lng, departure_time=None):
        """Google Directions API를 사용하여 경로 정보 검색"""
        try:
            # API URL 구성
            base_url = "https://maps.googleapis.com/maps/api/directions/json"
            params = {
                "origin": f"{origin_lat},{origin_lng}",
                "destination": f"{dest_lat},{dest_lng}",
                "key": self.api_key,
                "mode": "driving",  # 운전 모드
                "units": "metric",  # 미터 단위 사용
                "language": "ko"    # 한국어 응답
            }
            
            # 출발 시간 추가 (실시간 교통 정보 적용을 위해)
            if departure_time:
                if isinstance(departure_time, str):
                    # ISO 형식 문자열을 datetime으로 변환
                    dt = parse_datetime(departure_time)
                    if dt:
                        # 유닉스 타임스탬프로 변환 (초 단위)
                        params["departure_time"] = int(dt.timestamp())
                    else:
                        # 문자열 변환 실패 시 'now' 사용
                        params["departure_time"] = "now"
                elif departure_time.lower() == "now":
                    params["departure_time"] = "now"
                else:
                    # 기타 경우 현재 시간 타임스탬프 사용
                    params["departure_time"] = int(time.time())
            else:
                # 출발 시간이 지정되지 않으면 현재 시간 사용
                params["departure_time"] = "now"
            
            self.logger.info(f"Directions API 요청: {params}")
            
            # API 요청
            response = requests.get(base_url, params=params, timeout=120)
            
            # 응답 확인
            if response.status_code != 200:
                self.logger.warning(f"Google Directions API 호출 실패: {response.status_code}")
                return None
            
            # JSON 응답 파싱
            data = response.json()
            
            if data["status"] != "OK":
                self.logger.warning(f"경로를 찾을 수 없음: {data['status']}")
                return None
            
            # 첫 번째 경로 선택
            route = data["routes"][0]
            leg = route["legs"][0]  # 첫 번째 구간
            
            # 경로 정보 추출
            distance_meters = leg["distance"]["value"]  # 미터 단위
            distance_km = distance_meters / 1000  # 킬로미터로 변환
            
            duration_seconds = leg["duration"]["value"]  # 초 단위 (교통 상황 미고려)
            
            # 교통 상황 고려 시간 (출발 시간이 지정된 경우)
            if "duration_in_traffic" in leg:
                duration_in_traffic_seconds = leg["duration_in_traffic"]["value"]
                traffic_rate = duration_in_traffic_seconds / duration_seconds
            else:
                duration_in_traffic_seconds = duration_seconds
                traffic_rate = 1.0
            
            # 경로 단계 정보
            steps = []
            for step in leg["steps"]:
                steps.append({
                    "distance": step["distance"]["value"] / 1000,  # km
                    "duration": step["duration"]["value"],  # 초
                    "html_instructions": step.get("html_instructions", ""),
                    "travel_mode": step.get("travel_mode", "DRIVING"),
                    "start_location": step["start_location"],
                    "end_location": step["end_location"]
                })
            
            # 결과 구성
            result = {
                "distance": round(distance_km, 3),  # 3자리까지 반올림
                "duration": duration_seconds,
                "duration_in_traffic": duration_in_traffic_seconds,
                "traffic_rate": round(traffic_rate, 2),  # 2자리까지 반올림
                "steps": steps,
                "overview_polyline": route.get("overview_polyline", {}).get("points", ""),
                "start_address": leg.get("start_address", ""),
                "end_address": leg.get("end_address", "")
            }
            
            self.logger.info(f"경로 검색 성공: 거리 {result['distance']}km, 시간 {result['duration']}초, 교통 고려 시간 {result['duration_in_traffic']}초")
            
            return result
            
        except Exception as e:
            self.logger.error(f"경로 검색 중 오류 발생: {str(e)}")
            import traceback
            self.logger.error(traceback.format_exc())
            return None
    
    def get_traffic_data(self, origin_lat, origin_lng, dest_lat, dest_lng, departure_time=None):
        """교통 데이터 검색 (간소화된 결과 반환)"""
        directions = self.get_directions_cached(origin_lat, origin_lng, dest_lat, dest_lng, departure_time)
        
        if not directions:
            # 실패 시 기본 값 반환
            return {
                "distance": calculate_distance(origin_lat, origin_lng, dest_lat, dest_lng),  # 기존 직선 거리 계산 사용
                "estimated_time": calculate_travel_time(calculate_distance(origin_lat, origin_lng, dest_lat, dest_lng)),  # 기존 계산 사용
                "traffic_rate": 1.0,
                "has_traffic_data": False
            }
        
        return {
            "distance": directions["distance"],
            "estimated_time": directions["duration"],
            "estimated_time_in_traffic": directions["duration_in_traffic"],
            "traffic_rate": directions["traffic_rate"],
            "has_traffic_data": True,
            "steps": directions["steps"],
            "overview_polyline": directions["overview_polyline"]
        }
# 입력 모델 정의


# 일정 출력 모델 정의
class FixedSchedule(BaseModel):
    id: str
    name: str
    type: str = "FIXED"
    duration: int = 60
    priority: int = 1
    location: str = ""
    latitude: float = 37.5665
    longitude: float = 126.9780
    startTime: str
    endTime: str

class FlexibleSchedule(BaseModel):
    id: str
    name: str
    type: str = "FLEXIBLE"
    duration: int = 60
    priority: int = 3
    location: str = ""
    latitude: float = 37.5665
    longitude: float = 126.9780

class ExtractScheduleResponse(BaseModel):
    fixedSchedules: List[FixedSchedule] = []
    flexibleSchedules: List[FlexibleSchedule] = []

# ----- 모델 정의 (일정 최적화 API) -----

# 최적화 API 입력 모델
class OptimizeScheduleRequest(BaseModel):
    fixedSchedules: List[FixedSchedule] = []
    flexibleSchedules: List[FlexibleSchedule] = []

# 최적화 API 출력 모델
class Location(BaseModel):
    latitude: float = 0.0
    longitude: float = 0.0
    name: Optional[str] = None

class Constraints(BaseModel):
    earliestStartTime: Optional[str] = None
    latestEndTime: Optional[str] = None
    requiresWeekend: bool = False
    minimumDuration: int = 0
    maxTravelDistance: float = 0.0

class OptimizedSchedule(BaseModel):
    id: str
    name: str
    location: Location
    startTime: str
    endTime: str
    type: str
    priority: int
    category: Optional[str] = None
    estimatedDuration: int
    expectedCost: float = 0.0
    visitPreference: Optional[str] = None
    locationString: str
    constraints: Constraints
    duration: str
    flexible: bool

class RouteSegment(BaseModel):
    fromLocation: str
    toLocation: str
    distance: float
    estimatedTime: int
    trafficRate: float = 1.0
    recommendedRoute: Optional[Any] = None
    realTimeTraffic: Optional[Any] = None

class Metrics(BaseModel):
    totalDistance: float
    totalTime: int
    totalScore: float = 0.0
    successRate: float = 0.0
    componentScores: Optional[Any] = None
    optimizationReasons: Optional[Any] = None

class Recommendation(BaseModel):
    crowdLevelStatus: str
    bestVisitTime: str
    estimatedDuration: str

class PlaceDetails(BaseModel):
    phoneNumber: str = ""
    address: str
    isOpen: bool
    operatingHours: Dict[str, str]
    name: str
    rating: float = 0.0
    recommendation: Recommendation
    location: Location
    id: str
    crowdLevel: float
    category: str

class ScheduleAnalysis(BaseModel):
    locationName: str
    bestTimeWindow: Optional[Any] = None
    crowdLevel: float
    placeDetails: PlaceDetails
    optimizationFactors: Optional[Any] = None
    visitRecommendation: Optional[Any] = None

class OptimizeScheduleResponse(BaseModel):
    optimizedSchedules: List[OptimizedSchedule]
    routeSegments: List[RouteSegment]
    metrics: Metrics
    alternativeOptions: Optional[Any] = None
    scheduleAnalyses: Dict[str, ScheduleAnalysis]

# ----- 프롬프트 템플릿 정의 -----

SCHEDULE_TEMPLATE = """다음 음성 메시지에서 일정 정보를 추출하여 JSON 형식으로 반환해주세요.

필요한 정보:
- 장소명(name): 방문할 장소의 정확한 이름 (예: "스타벅스 강남점", "서울숲공원")
- 일정 유형(type): "FIXED"(고정 일정) 또는 "FLEXIBLE"(유연한 일정)
- 소요 시간(duration): 분 단위 (언급이 없으면 60분으로 설정)
- 우선순위(priority): 1-5 사이 숫자 (언급이 없으면 1로 설정)
- 위치(location): 가능한 정확한 주소나 위치 설명 (예: "서울시 강남구 테헤란로 152")
- 시작 시간(startTime): ISO 8601 형식 "YYYY-MM-DDTHH:MM:SS" (예: "2023-12-01T10:00:00")
- 종료 시간(endTime): ISO 8601 형식 "YYYY-MM-DDTHH:MM:SS" (예: "2023-12-01T11:00:00")

상대적 시간 표현의 경우 다음과 같이 처리해주세요:
- "오늘": {today_date}
- "내일": {tomorrow_date}
- "모레": {day_after_tomorrow_date}
- "다음 주": 정확한 날짜로 변환해주세요 ({next_week_date})

다음 JSON 형식으로 반환해주세요:
{{
  "fixedSchedules": [
    {{
      "id": "{current_milliseconds}",
      "name": "장소명",
      "type": "FIXED",
      "duration": 60,
      "priority": 1,
      "location": "위치 상세",
      "latitude": 37.5665,
      "longitude": 126.9780,
      "startTime": "2023-12-01T10:00:00",
      "endTime": "2023-12-01T11:00:00"
    }}
  ],
  "flexibleSchedules": [
    {{
      "id": "{current_milliseconds_plus}",
      "name": "방문할 곳",
      "type": "FLEXIBLE",
      "duration": 60,
      "priority": 3,
      "location": "위치 상세",
      "latitude": 37.5665,
      "longitude": 126.9780
    }}
  ]
}}

주의사항:
1. 시간이 명확한 일정은 fixedSchedules에, 시간이 불명확한 일정은 flexibleSchedules에 포함시켜주세요.
2. 모든 날짜와 시간은 큰따옴표(" ")로 감싸고, 반드시 ISO 8601 형식(YYYY-MM-DDTHH:MM:SS)으로 작성해주세요.
3. JSON 내부의 따옴표는 큰따옴표(" ")만 사용하고, 작은따옴표(' ')는 사용하지 마세요.
4. 각 일정의 id는 현재 시간 기준 밀리초로 설정해주세요.
5. 오직 JSON 데이터만 반환하고, 다른 설명이나 텍스트는 포함하지 마세요.

음성 메시지에서 언급된 장소에 대한 정보:
- 날짜/시간 정보가 명확하게 언급된 장소는 "고정 일정"으로 분류해주세요.
- 그렇지 않은 장소는 "유연한 일정"으로 분류해주세요.
- 순서가 언급된 경우("그 다음에", "먼저" 등), 순서를 고려하여 우선순위를 설정해주세요.
- 장소가 언급된 지역 근처에 위치하도록 좌표값을 설정해주세요.

예시:
입력: "내일 오전 10시에 울산대학교에서 회의 있고, 점심에는 근처 식당에서 식사하고 싶어. 그 다음에는 문수월드컵경기장 갈거야. 중간에 카페에 들리고싶어."
출력:
{{
  "fixedSchedules": [
    {{
      "id": "{current_milliseconds}",
      "name": "울산대학교",
      "type": "FIXED",
      "duration": 60,
      "priority": 1,
      "location": "울산광역시 남구 대학로 93",
      "latitude": 35.539,
      "longitude": 129.2567,
      "startTime": "{tomorrow_date}T10:00:00",
      "endTime": "{tomorrow_date}T11:00:00"
    }}
  ],
  "flexibleSchedules": [
    {{
      "id": "{current_milliseconds_plus}",
      "name": "근처 식당",
      "type": "FLEXIBLE",
      "duration": 60,
      "priority": 3,
      "location": "울산대학교 인근",
      "latitude": 35.539,
      "longitude": 129.2567
    }},
    {{
      "id": "{current_milliseconds_plus_2}",
      "name": "카페",
      "type": "FLEXIBLE",
      "duration": 60,
      "priority": 3,
      "location": "울산대학교 인근",
      "latitude": 35.539,
      "longitude": 129.2567
    }},
    {{
      "id": "{current_milliseconds_plus_3}",
      "name": "문수월드컵경기장",
      "type": "FLEXIBLE",
      "duration": 60,
      "priority": 3,
      "location": "울산광역시 남구 삼산로 100",
      "latitude": 35.5394,
      "longitude": 129.3114
    }}
  ]
}}

음성 메시지: {input}
"""

# ----- 클래스 정의 -----

# 향상된 위치 정보 검색 클래스 (LangChain의 Tool 개념을 구현)
class GooglePlacesTool:
    """Google Places API를 사용하여 위치 정보를 검색하는 도구"""
    
    def __init__(self, api_key=None):
        self.api_key = api_key or GOOGLE_MAPS_API_KEY
        if not self.api_key:
            raise ValueError("Google Maps API 키가 필요합니다.")
        # 검색 결과 캐싱을 위한 딕셔너리
        self.search_cache = {}
        # 로깅 설정
        self.logger = logging.getLogger('google_places_tool')
        self.logger.setLevel(logging.INFO)
        
        # OpenAI 클라이언트 초기화 (주소 정제용)
        self.openai_client = ChatOpenAI(
            openai_api_key=OPENAI_API_KEY,
            model_name="gpt-3.5-turbo",
            temperature=0.1
        )
    
    def extract_location_and_category(self, natural_language: str) -> dict:
        """GPT를 활용한 장소와 카테고리 추출 (paste.txt에서 적용)"""
        prompt = f"""
다음 자연어에서 장소와 카테고리를 정확히 추출해주세요.

JSON 형식으로만 응답:
{{
  "location": "정확한 장소명 (예: 서울역, 울산대학교, 강남역)",
  "category": "카테고리명 (예: 식당, 카페, 쇼핑몰, 병원)",
  "search_type": "Google Places API type (restaurant, cafe, shopping_mall, hospital, etc.)",
  "radius": 적절한반경미터(500-2000)
}}

예시:
"서울역에서 밥먹고 싶어" → {{"location": "서울역", "category": "식당", "search_type": "restaurant", "radius": 1000}}
"울산대 근처 카페 가자" → {{"location": "울산대학교", "category": "카페", "search_type": "cafe", "radius": 800}}

입력: "{natural_language}"
"""

        try:
            self.logger.info(f"GPT로 장소/카테고리 추출 중: {natural_language}")
            
            response = self.openai_client.invoke([
                {"role": "system", "content": "당신은 한국어 자연어에서 장소와 카테고리를 정확히 추출하는 전문가입니다. JSON 형식으로만 응답해주세요."},
                {"role": "user", "content": prompt}
            ])

            content = response.content.strip()
            self.logger.info(f"GPT 응답: {content}")

            # JSON 파싱
            if content.startswith("```json"):
                content = content.replace("```json", "").replace("```", "").strip()
            
            extracted_data = json.loads(content)
            return extracted_data
            
        except Exception as e:
            self.logger.error(f"GPT 추출 실패: {str(e)}")
            # 기본값 반환
            return {
                "location": natural_language,
                "category": "장소",
                "search_type": "point_of_interest",
                "radius": 1000
            }
    
    def validate_address_quality(self, address: str, place_name: str) -> bool:
        """주소 품질 검증 (paste.txt 로직 적용)"""
        if not address:
            return False
            
        # 모호한 표현 체크
        vague_terms = ["인근", "근처", "주변", "근방", "부근", "일대"]
        if any(term in address for term in vague_terms):
            self.logger.info(f"모호한 주소 감지: {address}")
            return False
        
        # 한국 주소 형식 체크 (시/도 포함 여부)
        korean_regions = ["서울", "부산", "대구", "인천", "광주", "대전", "울산", "세종", "경기", "강원", "충북", "충남", "전북", "전남", "경북", "경남", "제주"]
        has_region = any(region in address for region in korean_regions)
        
        # 주소 구성 요소 개수 체크 (최소 3개 이상의 의미있는 단어)
        meaningful_parts = [part for part in address.split() if len(part) > 1]
        has_enough_parts = len(meaningful_parts) >= 3
        
        quality_score = has_region + has_enough_parts
        is_quality = quality_score >= 1
        
        self.logger.info(f"주소 품질 검증 - {address}: 지역포함={has_region}, 구성요소충분={has_enough_parts}, 품질점수={quality_score}, 통과={is_quality}")
        return is_quality
    
    def search_nearby_with_validation(self, center_coords: tuple, category: str, search_type: str, radius: int = 1000) -> list:
        """주변 검색 및 검증 (paste.txt의 _search_nearby_places 로직 적용)"""
        self.logger.info(f"주변 검색 시작: 중심점={center_coords}, 카테고리={category}, 타입={search_type}, 반경={radius}m")
        
        all_places = []
        lat, lng = center_coords
        
        # 1. 타입 기반 검색
        try:
            url = "https://maps.googleapis.com/maps/api/place/nearbysearch/json"
            params = {
                'location': f"{lat},{lng}",
                'radius': radius,
                'type': search_type,
                'language': 'ko',
                'key': self.api_key
            }
            
            self.logger.info(f"타입 기반 주변 검색: {search_type}")
            response = requests.get(url, params=params, timeout=30)
            
            if response.status_code == 200:
                data = response.json()
                if data.get('status') == 'OK':
                    results = data.get('results', [])
                    self.logger.info(f"타입 검색 결과: {len(results)}개")
                    
                    for place in results:
                        place_info = self.parse_nearby_place_result(place, center_coords)
                        if place_info:
                            all_places.append(place_info)
        except Exception as e:
            self.logger.error(f"타입 기반 검색 오류: {str(e)}")
        
        # 2. 키워드 기반 검색
        try:
            params = {
                'location': f"{lat},{lng}",
                'radius': radius,
                'keyword': category,
                'type': search_type,
                'language': 'ko',
                'key': self.api_key
            }
            
            self.logger.info(f"키워드 기반 주변 검색: {category}")
            response = requests.get(url, params=params, timeout=30)
            
            if response.status_code == 200:
                data = response.json()
                if data.get('status') == 'OK':
                    results = data.get('results', [])
                    self.logger.info(f"키워드 검색 결과: {len(results)}개")
                    
                    for place in results:
                        place_info = self.parse_nearby_place_result(place, center_coords)
                        if place_info:
                            all_places.append(place_info)
        except Exception as e:
            self.logger.error(f"키워드 기반 검색 오류: {str(e)}")
        
        # 중복 제거 (place_id 기준)
        unique_places = self.remove_duplicate_places(all_places)
        
        # 거리순 정렬
        unique_places.sort(key=lambda x: x.get('distance', float('inf')))
        
        self.logger.info(f"주변 검색 완료: {len(unique_places)}개 고유 장소")
        return unique_places[:5]  # 상위 5개만 반환
    
    def parse_nearby_place_result(self, place: dict, center_coords: tuple) -> dict:
        """Google Places 결과 파싱 (paste.txt 로직 적용)"""
        try:
            location = place['geometry']['location']
            place_lat, place_lng = location['lat'], location['lng']
            
            # 거리 계산 (하버사인 공식)
            distance = self.calculate_distance(center_coords[0], center_coords[1], place_lat, place_lng)
            
            return {
                'name': place.get('name', ''),
                'formatted_address': place.get('vicinity', ''),
                'latitude': place_lat,
                'longitude': place_lng,
                'place_id': place.get('place_id', ''),
                'types': place.get('types', []),
                'rating': place.get('rating'),
                'distance': distance
            }
        except Exception as e:
            self.logger.error(f"장소 결과 파싱 오류: {str(e)}")
            return None
    
    def calculate_distance(self, lat1: float, lng1: float, lat2: float, lng2: float) -> float:
        """거리 계산 (하버사인 공식) - paste.txt에서 적용"""
        import math
        
        earth_radius = 6371000  # 미터
        lat1_rad = math.radians(lat1)
        lat2_rad = math.radians(lat2)
        delta_lat_rad = math.radians(lat2 - lat1)
        delta_lng_rad = math.radians(lng2 - lng1)

        a = (math.sin(delta_lat_rad / 2) * math.sin(delta_lat_rad / 2) +
             math.cos(lat1_rad) * math.cos(lat2_rad) *
             math.sin(delta_lng_rad / 2) * math.sin(delta_lng_rad / 2))
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

        return earth_radius * c
    
    def remove_duplicate_places(self, places: list) -> list:
        """중복 제거 (place_id 기준) - paste.txt에서 적용"""
        seen = set()
        unique_places = []

        for place in places:
            place_id = place.get('place_id', '')
            if place_id and place_id not in seen:
                seen.add(place_id)
                unique_places.append(place)

        self.logger.info(f"중복 제거: {len(places)}개 → {len(unique_places)}개")
        return unique_places
    
    def build_search_query(self, query: str, place_type: str = None, region: str = None) -> str:
        """검색 쿼리 최적화 빌더 - 기존 메소드 유지"""
        components = []
        
        # 지역 정보가 있으면 추가 (query에 이미 포함되어 있지 않은 경우)
        if region and region not in query:
            components.append(region)
        
        # 원본 쿼리 추가
        components.append(query)
        
        # 최종 쿼리 생성
        final_query = " ".join(components)
        self.logger.info(f"빌드된 검색 쿼리: '{final_query}', 장소 유형: {place_type or '없음'}")
        
        return final_query
    
    @lru_cache(maxsize=100)
    def search_place_cached(self, query: str, place_type: str = None) -> Optional[Dict]:
        """캐싱을 지원하는 장소 검색 함수 - 기존 메소드 유지"""
        cache_key = f"{query}_{place_type}"
        
        # 캐시에 있으면 반환
        if cache_key in self.search_cache:
            self.logger.info(f"캐시에서 결과 반환: '{cache_key}'")
            return self.search_cache[cache_key]
        
        # 없으면 검색 실행
        result = self.search_place_detailed(query, place_type)
        
        # 결과가 있으면 캐시에 저장
        if result:
            self.search_cache[cache_key] = result
            self.logger.info(f"검색 결과 캐싱: '{cache_key}'")
        
        return result
 
 
    
    async def search_place_detailed(self, query: str, place_type: str = None) -> Optional[Dict]:
        """향상된 장소 검색 - 비동기 버전"""
        self.logger.info(f"향상된 장소 검색 시작: '{query}', 타입: {place_type or '없음'}")
        
        # 1단계: 기본 검색 시도
        result = await self._basic_place_search(query, place_type)
        
        if result and self.validate_address_quality(result.get('formatted_address', ''), query):
            self.logger.info(f"1단계 검색 성공 (고품질): {result.get('name')}")
            return result
        
        # 2단계: 자연어 분석 및 재검색
        if "근처" in query or "인근" in query or "주변" in query:
            self.logger.info("2단계: 자연어 분석 기반 재검색 시도")
            
            # GPT로 장소와 카테고리 추출 (동기 함수이므로 그대로)
            extracted = self.extract_location_and_category(query)
            
            # 추출된 정확한 장소명으로 재검색
            if extracted.get('location') != query:
                improved_result = await self._basic_place_search(extracted['location'], place_type)
                
                if improved_result and self.validate_address_quality(improved_result.get('formatted_address', ''), extracted['location']):
                    self.logger.info(f"2단계 검색 성공: {improved_result.get('name')}")
                    return improved_result
        
        # 3단계: 주변 검색으로 대체
        if result and result.get('latitude') and result.get('longitude'):
            self.logger.info("3단계: 주변 검색으로 더 정확한 결과 찾기")
            
            # 기존 결과의 좌표를 기준으로 주변 검색
            center_coords = (result['latitude'], result['longitude'])
            
            # 카테고리 추출
            if place_type:
                search_type = place_type
                category = self._get_category_from_type(place_type)
            else:
                category = self._extract_category_from_query(query)
                search_type = get_place_type(category) or "point_of_interest"
            
            nearby_places = await self.search_nearby_with_validation_async(center_coords, category, search_type, 1000)
            
            if nearby_places:
                # 가장 가까운 장소 선택
                best_place = nearby_places[0]
                self.logger.info(f"3단계 검색 성공 (주변 검색): {best_place.get('name')}")
                return best_place
        
        # 4단계: 원본 결과라도 반환 (완전 실패 방지)
        if result:
            self.logger.info(f"원본 검색 결과 반환: {result.get('name')}")
            return result
        
        self.logger.warning(f"모든 검색 단계 실패: '{query}'")
        return None
    
    def search_nearby_detailed(self, query: str, location: str = "37.4980,127.0276", radius: int = 1000, place_type: str = None) -> Optional[Dict]:
        """개선된 주변 장소 검색 기능 - 장소 유형 지원"""
        try:
            # URL 인코딩
            encoded_query = requests.utils.quote(query)
            
            # Nearby Search API 호출
            url = f"https://maps.googleapis.com/maps/api/place/nearbysearch/json?location={location}&radius={radius}&keyword={encoded_query}&language=ko&key={self.api_key}"
            
            # 장소 유형이 지정된 경우 추가
            if place_type:
                url += f"&type={place_type}"
            
            self.logger.info(f"Nearby API 요청: '{query}', 위치: {location}, 반경: {radius}m, 유형: {place_type or '없음'}")
            
            response = requests.get(url, timeout=120)
            if response.status_code != 200:
                self.logger.warning(f"Nearby Places API 호출 실패: {response.status_code}")
                return None
            
            data = response.json()
            
            if data['status'] == 'OK' and data.get('results') and len(data['results']) > 0:
                # 결과 중 첫 번째 장소 선택
                top_place = data['results'][0]
                
                # Place Details API를 통해 더 자세한 정보 가져오기
                if top_place.get('place_id'):
                    detailed_place = self.get_place_details(top_place.get('place_id'))
                    if detailed_place:
                        return detailed_place
                
                # 기본 정보 반환
                return {
                    'name': top_place.get('name', ''),
                    'formatted_address': top_place.get('vicinity', ''),
                    'latitude': top_place['geometry']['location']['lat'],
                    'longitude': top_place['geometry']['location']['lng'],
                    'place_id': top_place.get('place_id', ''),
                    'types': top_place.get('types', [])
                }
            else:
                self.logger.warning(f"주변 장소를 찾을 수 없음: {data['status']}")
                return None
                
        except Exception as e:
            self.logger.error(f"주변 장소 검색 중 오류 발생: {str(e)}")
            return None
    
    @lru_cache(maxsize=100)
    def get_place_details(self, place_id: str) -> Optional[Dict]:
        """기존 메소드 유지 - Place ID를 사용하여 장소의 상세 정보를 가져옵니다."""
        if not place_id:
            self.logger.warning("Place ID가 제공되지 않았습니다.")
            return None
            
        try:
            # Place Details API 호출
            url = f"https://maps.googleapis.com/maps/api/place/details/json?place_id={place_id}&fields=name,formatted_address,geometry,address_component,types&language=ko&key={self.api_key}"
            
            response = requests.get(url, timeout=120)
            if response.status_code != 200:
                self.logger.warning(f"Place Details API 호출 실패: {response.status_code}")
                return None
            
            data = response.json()
            
            if data['status'] == 'OK' and data.get('result'):
                result = data['result']
                
                return {
                    'name': result.get('name', ''),
                    'formatted_address': result.get('formatted_address', ''),
                    'latitude': result['geometry']['location']['lat'],
                    'longitude': result['geometry']['location']['lng'],
                    'place_id': place_id,
                    'types': result.get('types', [])
                }
            else:
                self.logger.warning(f"장소 상세 정보를 찾을 수 없음: {data['status']}")
                return None
                
        except Exception as e:
            self.logger.error(f"장소 상세 정보 검색 중 오류 발생: {str(e)}")
            return None

# ----- 유틸리티 함수 -----

def calculate_distance(lat1, lon1, lat2, lon2):
    """두 좌표 사이의 거리를 킬로미터 단위로 계산"""
    try:
        return geodesic((lat1, lon1), (lat2, lon2)).kilometers
    except:
        # 좌표가 정확하지 않은 경우 대략적인 거리 계산
        return math.sqrt((lat1 - lat2)**2 + (lon1 - lon2)**2) * 111  # 1도 = 약 111km

def calculate_travel_time(distance):
    """거리를 기반으로 이동 시간을 초 단위로 계산 (평균 속도 30km/h 가정)"""
    average_speed_km_per_h = 30
    hours = distance / average_speed_km_per_h
    return int(hours * 3600)  # 초 단위로 변환

def parse_datetime(dt_str):
    """날짜 문자열을 datetime 객체로 변환"""
    try:
        return datetime.datetime.fromisoformat(dt_str.replace('Z', '+00:00'))
    except:
        try:
            return datetime.datetime.strptime(dt_str, "%Y-%m-%dT%H:%M:%S")
        except:
            return None

def format_duration(minutes):
    """분 단위 시간을 PT1H 형식으로 변환"""
    hours = minutes // 60
    minutes = minutes % 60
    
    if minutes > 0:
        return f"PT{hours}H{minutes}M"
    else:
        return f"PT{hours}H"

def get_place_categories():
    """장소 유형에 따른 카테고리 목록"""
    return {
        "restaurant": ["식당,음식점", "Restaurant", "음식점", "식당"],
        "cafe": ["카페,디저트", "Cafe", "카페,디저트>북카페", "디저트"],
        "stadium": ["스포츠,오락>월드컵경기장", "Stadium", "스포츠,오락"],
        "university": ["교육,학문>대학교", "University", "교육,학문"],
        "library": ["Library", "도서관"],
        "shopping": ["쇼핑,마트", "Shopping Mall", "쇼핑몰"],
        "park": ["공원", "Park", "자연,레저"],
    }

def get_place_category(place_name):
    """장소 이름에서 카테고리 유추"""
    name_lower = place_name.lower()
    categories = get_place_categories()
    
    if any(word in name_lower for word in ["식당", "음식", "레스토랑", "맛집"]):
        return categories["restaurant"][0]
    elif any(word in name_lower for word in ["카페", "커피", "북카페"]):
        return categories["cafe"][0]
    elif any(word in name_lower for word in ["경기장", "스타디움", "월드컵"]):
        return categories["stadium"][0]
    elif any(word in name_lower for word in ["대학", "캠퍼스"]):
        return categories["university"][0]
    elif any(word in name_lower for word in ["도서관", "책"]):
        return categories["library"][0]
    elif any(word in name_lower for word in ["쇼핑", "마트", "백화점", "몰"]):
        return categories["shopping"][0]
    elif any(word in name_lower for word in ["공원", "정원"]):
        return categories["park"][0]
    else:
        return "기타"

def generate_operating_hours(place_name):
    """장소 유형에 따른 예상 영업시간 생성"""
    name_lower = place_name.lower()
    
    if any(word in name_lower for word in ["식당", "음식", "레스토랑", "맛집"]):
        return {"open": "11:00", "close": "21:00"}
    elif any(word in name_lower for word in ["카페", "커피", "북카페"]):
        return {"open": "09:00", "close": "22:00"}
    elif any(word in name_lower for word in ["경기장", "스타디움", "월드컵"]):
        return {"open": "09:00", "close": "18:00"}
    elif any(word in name_lower for word in ["대학", "캠퍼스"]):
        return {"open": "09:00", "close": "18:00"}
    elif any(word in name_lower for word in ["도서관", "책"]):
        return {"open": "09:00", "close": "20:00"}
    elif any(word in name_lower for word in ["쇼핑", "마트", "백화점", "몰"]):
        return {"open": "10:00", "close": "22:00"}
    elif any(word in name_lower for word in ["공원", "정원"]):
        return {"open": "06:00", "close": "22:00"}
    else:
        return {"open": "09:00", "close": "18:00"}

def check_place_open(operating_hours, check_time):
    """주어진 시간에 장소가 영업 중인지 확인"""
    if not operating_hours or "open" not in operating_hours or "close" not in operating_hours:
        return True
    
    open_time = operating_hours["open"]
    close_time = operating_hours["close"]
    
    # 시간을 분으로 변환하여 비교
    def time_to_minutes(time_str):
        hours, minutes = map(int, time_str.split(":"))
        return hours * 60 + minutes
    
    check_hour = check_time.hour
    check_minute = check_time.minute
    check_minutes = check_hour * 60 + check_minute
    
    open_minutes = time_to_minutes(open_time)
    close_minutes = time_to_minutes(close_time)
    
    return open_minutes <= check_minutes <= close_minutes

def safe_parse_json(json_str):
    """
    안전하게 JSON을 파싱하고, 필요한 경우 수정합니다.
    """
    try:
        # 기본 파싱 시도
        return json.loads(json_str)
    except json.JSONDecodeError as e:
        print(f"JSON 파싱 오류: {str(e)}")
        
        # 1. 따옴표 문제 수정 시도
        fixed_str = json_str
        
        # 날짜 형식에서 따옴표 수정 (예: "2021-08-"11T10:00:00" -> "2021-08-11T10:00:00")
        fixed_str = re.sub(r'(\d+)-(\d+)-"(\d+)T(\d+):(\d+):(\d+)"', r'\1-\2-\3T\4:\5:\6', fixed_str)
        fixed_str = re.sub(r'(\d+)-(\d+)-(\d+)T"(\d+)":"(\d+)":"(\d+)"', r'\1-\2-\3T\4:\5:\6', fixed_str)
        
        # 후행 쉼표 제거
        fixed_str = re.sub(r',\s*}', '}', fixed_str)
        fixed_str = re.sub(r',\s*]', ']', fixed_str)
        
        print(f"수정된 JSON: {fixed_str}")
        
        try:
            return json.loads(fixed_str)
        except json.JSONDecodeError:
            # 2. 마지막 수단: 기본 구조 반환
            print("JSON 파싱 실패. 기본 구조 반환.")
            return {
                "fixedSchedules": [],
                "flexibleSchedules": []
            }

# ----- 비즈니스 로직 함수 -----

def create_schedule_chain():
    """LangChain을 사용한 일정 추출 체인 생성"""
    # 현재 시간 계산 (밀리초)
    current_time = int(datetime.datetime.now().timestamp() * 1000)
    current_time_plus = current_time + 1
    current_time_plus_2 = current_time + 2
    current_time_plus_3 = current_time + 3
    
    print(f"현재 생성된 ID: {current_time}, {current_time_plus}")
    
    # 날짜 계산
    today = datetime.datetime.now()
    tomorrow = today + datetime.timedelta(days=1)
    day_after_tomorrow = today + datetime.timedelta(days=2)
    next_week = today + datetime.timedelta(days=7)
    
    print(f"날짜 계산: 오늘={today.strftime('%Y-%m-%d')}, 내일={tomorrow.strftime('%Y-%m-%d')}")
    
    # 프롬프트 템플릿 생성
    prompt = PromptTemplate(
        template=SCHEDULE_TEMPLATE,
        input_variables=["input"],
        partial_variables={
            "current_milliseconds": str(current_time),
            "current_milliseconds_plus": str(current_time_plus),
            "current_milliseconds_plus_2": str(current_time_plus_2),
            "current_milliseconds_plus_3": str(current_time_plus_3),
            "today_date": today.strftime("%Y-%m-%d"),
            "tomorrow_date": tomorrow.strftime("%Y-%m-%d"),
            "day_after_tomorrow_date": day_after_tomorrow.strftime("%Y-%m-%d"),
            "next_week_date": next_week.strftime("%Y-%m-%d")
        }
    )
    
    # LLM 모델 생성 (성능 향상을 위해 temperature=0)
    llm = ChatOpenAI(
        openai_api_key=OPENAI_API_KEY,
        model_name="gpt-3.5-turbo",
        temperature=0
    )
    
    # JSON 출력 파서
    parser = JsonOutputParser()
    
    # 체인 생성
    chain = prompt | llm | parser
    
    return chain




def enhance_location_data(schedule_data: Dict) -> Dict:
    """
    일정 데이터의 위치 정보를 Google Places API를 사용하여 보강합니다.
    보다 정확하고 완전한 주소 정보와 좌표를 제공합니다.
    
    개선사항:
    - 장소 유형 매핑 테이블을 활용한 유형 기반 검색
    - 검색 쿼리 최적화 (지역명+장소명+유형)
    - 검색 결과 캐싱으로 API 호출 최소화
    - 점진적 검색 전략 (정확한 검색→유형 기반→위치 기반)
    """
    logger = logging.getLogger('location_enhancer')
    logger.info("위치 정보 보강 시작...")
    
    # GooglePlacesTool 초기화
    places_tool = GooglePlacesTool()
    
    # 복사본 생성하여 원본 데이터 보존
    enhanced_data = json.loads(json.dumps(schedule_data))
    
    # 주요 지역 목록 (fallback 검색용)
    major_regions = ["서울", "부산", "대구", "인천", "광주", "대전", "울산"]
    
    # 이미 사용된 장소를 추적하기 위한 집합
    already_used_places = set()
    
    # 지역명이 장소명에 포함되어 있는지 확인하는 함수
    def contains_region(place_name: str) -> Tuple[bool, str]:
        """장소명에 지역명이 포함되어 있는지 확인하고, 포함된 지역명 반환"""
        for region in major_regions:
            if region in place_name:
                return True, region
        return False, ""
    
    # 고정 일정을 통해 주요 지역 컨텍스트 파악
    primary_region = None
    primary_location = None
    
    if "fixedSchedules" in enhanced_data and enhanced_data["fixedSchedules"]:
        main_fixed_schedule = enhanced_data["fixedSchedules"][0]
        place_name = main_fixed_schedule.get("name", "")
        location = main_fixed_schedule.get("location", "")
        
        # 기본 위치 정보 저장
        if main_fixed_schedule.get("latitude") and main_fixed_schedule.get("longitude"):
            primary_location = (main_fixed_schedule.get("latitude"), main_fixed_schedule.get("longitude"))
            logger.info(f"주요 위치 좌표: {primary_location}")
        
        # 장소명이나 위치에서 지역 추출
        has_region, region = contains_region(place_name)
        if has_region:
            primary_region = region
        else:
            for region in major_regions:
                if region in location:
                    primary_region = region
                    break
    
    logger.info(f"주요 지역 컨텍스트: {primary_region or '없음'}")
    
    # 고정 일정 처리
    if "fixedSchedules" in enhanced_data and isinstance(enhanced_data["fixedSchedules"], list):
        for i, schedule in enumerate(enhanced_data["fixedSchedules"]):
            logger.info(f"고정 일정 {i+1} 처리 중: {schedule.get('name', '이름 없음')}")
            
            place_name = schedule.get("name", "")
            if not place_name:
                continue
            
            # 장소 검색 시도
            found_place = None
            
            # 유형 유추
            place_type = get_place_type(place_name)
            logger.info(f"고정 일정 '{place_name}'의 유추된 유형: {place_type or '없음'}")
            
            # 단계 1: 컨텍스트 기반 단일 검색 (주요 로직 변경)
            search_term = place_name  # 기본값은 장소명 그대로
            
            # 장소명에 지역이 이미 포함되어 있는지 확인
            has_region_in_name, region_in_name = contains_region(place_name)
            
            if has_region_in_name:
                # 이미 지역명이 포함되어 있으면 그대로 사용
                logger.info(f"장소명에 지역({region_in_name})이 이미 포함됨")
                search_term = place_name
                context_region = region_in_name
            elif primary_region:
                # 주요 지역 컨텍스트가 있으면 추가
                search_term = place_name
                context_region = primary_region
                logger.info(f"컨텍스트 기반 검색 시도: '{search_term}', 지역: {context_region}")
            else:
                # 컨텍스트가 없으면 장소명 그대로 사용
                search_term = place_name
                context_region = None
                logger.info(f"기본 검색 시도: '{search_term}'")
            
            # 첫 번째 검색 실행 (최적화된 검색)
            place_info = search_place_with_retry(places_tool, search_term, place_type, context_region)
            
            # 결과 확인
            if place_info and place_info.get("formatted_address"):
                found_place = place_info
                logger.info(f"장소 찾음: {place_info.get('name')} - {place_info.get('formatted_address')}")
            else:
                # 단계 2: 첫 검색 실패 시 추가 전략 시도
                logger.info(f"첫 검색 실패, 추가 전략 시도...")
                
                # 2-1: 장소명에 지역명이 포함된 경우, 지역명 제거 후 검색
                if has_region_in_name:
                    # 지역명 제거한 깨끗한 장소명 생성
                    clean_name = place_name.replace(region_in_name, "").strip()
                    if clean_name:  # 비어있지 않으면
                        logger.info(f"지역명 제거 후 검색 시도: '{clean_name}'")
                        place_info = search_place_with_retry(places_tool, clean_name, place_type, region_in_name)
                        if place_info and place_info.get("formatted_address"):
                            found_place = place_info
                            logger.info(f"장소 찾음: {place_info.get('name')} - {place_info.get('formatted_address')}")
                
                # 2-2: 그래도 실패하면 대체 검색 로직 사용
                if not found_place:
                    logger.info(f"대체 검색 전략 시도...")
                    found_place = find_alternative_place(
                        places_tool, 
                        place_name,
                        already_used_places, 
                        primary_location,
                        primary_region
                    )
                    
                    if found_place:
                        logger.info(f"대체 검색으로 장소 찾음: {found_place.get('name')} - {found_place.get('formatted_address')}")
            
            # 장소를 찾았으면 정보 업데이트
            if found_place:
                # 주소 업데이트
                if found_place.get("formatted_address"):
                    original_location = schedule.get("location", "")
                    new_location = found_place["formatted_address"]
                    
                    # 주소가 충분히 구체적인지 확인
                    if len(new_location.split()) > 2:  # 최소 3개 단어 이상의 주소
                        logger.info(f"주소 업데이트: '{original_location}' -> '{new_location}'")
                        schedule["location"] = new_location
                    else:
                        logger.info(f"주소가 너무 일반적임: '{new_location}', 검색 계속")
                        # 더 구체적인 주소 검색 시도 (place_id 이용)
                        detailed_place = places_tool.get_place_details(found_place.get("place_id", ""))
                        if detailed_place and detailed_place.get("formatted_address"):
                            logger.info(f"상세 주소 찾음: '{detailed_place['formatted_address']}'")
                            schedule["location"] = detailed_place["formatted_address"]
                
                # 좌표 업데이트
                if found_place.get("latitude") and found_place.get("longitude"):
                    schedule["latitude"] = found_place["latitude"]
                    schedule["longitude"] = found_place["longitude"]
                    logger.info(f"좌표 업데이트: [{found_place['latitude']}, {found_place['longitude']}]")
                
                # 사용된 장소 추적
                if found_place.get("place_id"):
                    already_used_places.add(found_place.get("place_id"))
            else:
                logger.info(f"'{place_name}'에 대한 정확한 장소 정보를 찾을 수 없음")
    
    # 유연 일정 처리
    if "flexibleSchedules" in enhanced_data and isinstance(enhanced_data["flexibleSchedules"], list):
        for i, schedule in enumerate(enhanced_data["flexibleSchedules"]):
            logger.info(f"유연 일정 {i+1} 처리 중: {schedule.get('name', '이름 없음')}")
            
            # 유연 일정의 경우 카테고리 기반 검색
            category = schedule.get("name", "")
            
            # 카테고리에서 장소 유형 유추
            place_type = get_place_type(category)
            logger.info(f"유연 일정 '{category}'의 유추된 유형: {place_type or '없음'}")
            
            # 기존 위치 정보가 있으면 인근 검색 (고정 일정 기준)
            existing_location = None
            if "fixedSchedules" in enhanced_data and enhanced_data["fixedSchedules"]:
                for fixed in enhanced_data["fixedSchedules"]:
                    if fixed.get("latitude") and fixed.get("longitude"):
                        existing_location = (fixed['latitude'], fixed['longitude'])
                        logger.info(f"인근 검색 기준점: {fixed.get('name', '')} ({existing_location[0]},{existing_location[1]})")
                        break
            
            # 점진적 검색 전략 적용
            found_place = None
            
            # 1. 인근 위치 기반 검색
            if existing_location:
                # 탐색할 유형 후보를 장소 카테고리에 따라 결정
                search_types = []
                search_queries = []
                
                # 장소 유형과 카테고리에 따라 검색 쿼리 결정
                if place_type:
                    search_types.append(place_type)
                
                # 카테고리별 검색어 설정
                if "식" in category or "음식" in category or "식당" in category:
                    search_queries = ["맛집", "레스토랑", "식당"]
                    if not search_types:
                        search_types = ["restaurant", "food"]
                elif "카페" in category or "커피" in category:
                    search_queries = ["카페", "커피숍", "디저트"]
                    if not search_types:
                        search_types = ["cafe", "coffee_shop"]
                elif "쇼핑" in category or "마트" in category:
                    search_queries = ["쇼핑몰", "마트", "백화점"]
                    if not search_types:
                        search_types = ["shopping_mall", "department_store"]
                else:
                    search_queries = [category]
                    if not search_types:
                        # 기본 장소 유형 (검색어 기반으로 유추)
                        default_type = get_place_type(category)
                        if default_type:
                            search_types.append(default_type)
                        else:
                            search_types.append("point_of_interest")
                
                # 기본 검색 쿼리가 없으면 추가
                if category not in search_queries:
                    search_queries.insert(0, category)
                
                # 중복 검색 방지를 위한 추적
                attempted_searches = set()
                
                # 1.1 유형 기반 위치 주변 검색
                for search_type in search_types:
                    if found_place:
                        break
                        
                    logger.info(f"유형 '{search_type}' 기반 인근 검색 시도")
                    
                    for radius in [1000, 2000, 3000]:
                        location_str = f"{existing_location[0]},{existing_location[1]}"
                        
                        try:
                            search_place = places_tool.search_nearby_detailed(
                                category,  # 일반 카테고리명 사용
                                location=location_str,
                                radius=radius,
                                place_type=search_type
                            )
                            
                            # 이미 사용된 장소면 건너뜀
                            if search_place and search_place.get("place_id") in already_used_places:
                                logger.info(f"이미 사용된 장소 발견: {search_place.get('name')}, 다음 검색 시도...")
                                continue
                            
                            if search_place and search_place.get("formatted_address"):
                                found_place = search_place
                                logger.info(f"유형 기반 장소 찾음: {search_place.get('name')} - {search_place.get('formatted_address')}")
                                break
                        except Exception as e:
                            logger.error(f"유형 기반 인근 검색 오류 (반경 {radius}m): {str(e)}")
                
                # 1.2 키워드 기반 주변 검색
                if not found_place:
                    for query in search_queries:
                        if found_place:
                            break
                            
                        search_key = f"{query}_{primary_region or ''}"
                        if search_key in attempted_searches:
                            continue
                            
                        attempted_searches.add(search_key)
                        logger.info(f"인근 '{query}' 검색 중...")
                        
                        for radius in [1000, 2000, 3000]:
                            location_str = f"{existing_location[0]},{existing_location[1]}"
                            
                            try:
                                search_place = places_tool.search_nearby_detailed(
                                    query,
                                    location=location_str,
                                    radius=radius,
                                    place_type=place_type
                                )
                                
                                # 이미 사용된 장소면 대체 검색 시도
                                if search_place and search_place.get("place_id") in already_used_places:
                                    logger.info(f"이미 사용된 장소 발견: {search_place.get('name')}, 대체 검색 시도...")
                                    
                                    # 중복 방지를 위한 대체 검색 함수 호출
                                    alt_place = find_alternative_place(
                                        places_tool,
                                        query, 
                                        already_used_places,
                                        existing_location,
                                        primary_region
                                    )
                                    
                                    if alt_place:
                                        search_place = alt_place
                                    else:
                                        # 대체 검색 실패, 다음 쿼리로 넘어감
                                        continue
                                
                                if search_place and search_place.get("formatted_address"):
                                    found_place = search_place
                                    logger.info(f"장소 찾음: {search_place.get('name')} - {search_place.get('formatted_address')}")
                                    # 사용된 장소 추적
                                    if search_place.get("place_id"):
                                        already_used_places.add(search_place.get("place_id"))
                                    break
                            except Exception as e:
                                logger.error(f"인근 검색 오류 (쿼리: {query}, 반경: {radius}m): {str(e)}")
            
            # 2. 인근 검색 실패 시 지역 기반 검색
            if not found_place:
                logger.info("인근 검색 실패, 지역 기반 검색 시도")
                
                # 검색 지역 설정
                search_region = primary_region or "서울"
                logger.info(f"지역 기반 검색 지역: {search_region}")
                
                # 검색 유형 후보
                if place_type:
                    search_types = [place_type]
                else:
                    search_types = []
                    # 카테고리별 기본 유형 설정
                    if "식" in category or "음식" in category or "식당" in category:
                        search_types = ["restaurant", "food"]
                    elif "카페" in category or "커피" in category:
                        search_types = ["cafe", "coffee_shop"] 
                    elif "쇼핑" in category or "마트" in category:
                        search_types = ["shopping_mall", "department_store"]
                    else:
                        default_type = get_place_type(category)
                        if default_type:
                            search_types = [default_type]
                        else:
                            search_types = ["point_of_interest"]
                
                # 검색 쿼리 생성
                search_queries = []
                if "식" in category or "음식" in category or "식당" in category:
                    search_queries = [f"{search_region} 맛집", f"{search_region} 식당", f"{search_region} 레스토랑"]
                elif "카페" in category or "커피" in category:
                    search_queries = [f"{search_region} 카페", f"{search_region} 커피숍"]
                elif "쇼핑" in category or "마트" in category:
                    search_queries = [f"{search_region} 쇼핑몰", f"{search_region} 백화점"]
                else:
                    search_queries = [f"{search_region} {category}"]
                
                # 중복 검색 방지
                attempted_searches = set()
                
                # 지역 + 유형 기반 검색
                for search_type in search_types:
                    if found_place:
                        break
                        
                    for query in search_queries:
                        search_key = f"{query}_{search_type}"
                        if search_key in attempted_searches:
                            continue
                            
                        attempted_searches.add(search_key)
                        logger.info(f"'{query}' 지역 검색 중 (유형: {search_type})...")
                        
                        try:
                            search_place = search_place_with_retry(places_tool, query, search_type)
                            
                            # 이미 사용된 장소면 대체 검색 시도
                            if search_place and search_place.get("place_id") in already_used_places:
                                logger.info(f"이미 사용된 장소 발견: {search_place.get('name')}, 대체 검색 시도...")
                                
                                alt_place = find_alternative_place(
                                    places_tool,
                                    query, 
                                    already_used_places,
                                    primary_location,
                                    search_region
                                )
                                
                                if alt_place:
                                    search_place = alt_place
                                else:
                                    # 대체 검색 실패, 다음 쿼리로 넘어감
                                    continue
                            
                            if search_place and search_place.get("formatted_address"):
                                found_place = search_place
                                logger.info(f"장소 찾음: {search_place.get('name')} - {search_place.get('formatted_address')}")
                                # 사용된 장소 추적
                                if search_place.get("place_id"):
                                    already_used_places.add(search_place.get("place_id"))
                                break
                        except Exception as e:
                            logger.error(f"지역 검색 오류 (쿼리: {query}): {str(e)}")
            
            # 3. 마지막 시도: 대체 검색 로직
            if not found_place:
                logger.info("모든 기본 검색 실패, 대체 검색 로직 시도")
                
                found_place = find_alternative_place(
                    places_tool,
                    category, 
                    already_used_places,
                    primary_location,
                    primary_region
                )
                
                if found_place:
                    logger.info(f"대체 검색으로 장소 찾음: {found_place.get('name')} - {found_place.get('formatted_address')}")
                    # 사용된 장소 추적
                    if found_place.get("place_id"):
                        already_used_places.add(found_place.get("place_id"))
            
            # 장소를 찾았으면 정보 업데이트
            if found_place:
                # 이름 업데이트 - 원래 카테고리 보존
                original_name = schedule.get("name", "")
                schedule["name"] = f"{original_name} - {found_place.get('name', '')}"
                
                # 주소 업데이트
                if found_place.get("formatted_address"):
                    # 주소가 충분히 구체적인지 확인
                    new_location = found_place["formatted_address"]
                    
                    # 한국 주소 형식에 맞게 정리
                    if "서울" in new_location and "특별시" not in new_location:
                        new_location = new_location.replace("서울", "서울특별시")
                    elif "대한민국" in new_location and "서울" not in new_location:
                        if "강남" in new_location:
                            new_location = f"서울특별시 {new_location}"
                    
                    logger.info(f"주소 업데이트: '{schedule.get('location', '')}' -> '{new_location}'")
                    schedule["location"] = new_location
                
                # 좌표 업데이트
                if found_place.get("latitude") and found_place.get("longitude"):
                    schedule["latitude"] = found_place["latitude"]
                    schedule["longitude"] = found_place["longitude"]
                    logger.info(f"좌표 업데이트: [{found_place['latitude']}, {found_place['longitude']}]")
            else:
                logger.info(f"'{category}'에 대한 적합한 장소를 찾을 수 없음")
    
    logger.info("위치 정보 보강 완료")
    return enhanced_data

# 장소 유형 매핑 테이블 (구글 문서 기반으로 개선)
def get_place_type_mapping() -> Dict[str, List[str]]:
    """장소 유형 매핑 테이블 제공"""
    return {
        # 음식점 관련
        "식당": ["restaurant", "food"],
        "맛집": ["restaurant", "food"],
        "음식점": ["restaurant", "food"],
        "레스토랑": ["restaurant"],
        "한식": ["restaurant"],
        "중식": ["chinese_restaurant"],
        "일식": ["japanese_restaurant"],
        "양식": ["restaurant"],
        "분식": ["restaurant", "food"],
        "치킨": ["meal_takeaway", "restaurant"],
        "피자": ["pizza_restaurant"],
        "햄버거": ["hamburger_restaurant"],
        "카페": ["cafe", "coffee_shop"],
        "커피": ["cafe", "coffee_shop"],
        "디저트": ["bakery", "cafe", "dessert_shop"],
        "베이커리": ["bakery"],
        "아이스크림": ["ice_cream_shop"],
        "케이크": ["bakery", "dessert_shop"],
        "빵집": ["bakery"],
        "도넛": ["donut_shop"],
        "주점": ["bar", "pub"],
        "술집": ["bar", "pub"],
        "와인바": ["wine_bar"],
        
        # 학교 관련
        "대학교": ["university"],
        "대학": ["university"],
        "학교": ["school"],
        "초등학교": ["primary_school"],
        "중학교": ["secondary_school"],
        "고등학교": ["secondary_school"],
        "유치원": ["preschool"],
        
        # 스포츠 및 레저
        "경기장": ["stadium"],
        "월드컵": ["stadium"],
        "축구장": ["stadium"],
        "야구장": ["stadium"],
        "체육관": ["gym", "stadium"],
        "수영장": ["swimming_pool"],
        "공원": ["park"],
        "놀이공원": ["amusement_park"],
        "워터파크": ["water_park"],
        "식물원": ["botanical_garden"],
        "동물원": ["zoo"],
        "수족관": ["aquarium"],
        "볼링장": ["bowling_alley"],
        "영화관": ["movie_theater"],
        "극장": ["movie_theater", "performing_arts_theater"],
        "미술관": ["art_gallery", "museum"],
        "박물관": ["museum"],
        "노래방": ["karaoke"],
        
        # 쇼핑
        "쇼핑몰": ["shopping_mall"],
        "마트": ["supermarket", "grocery_store"],
        "백화점": ["department_store"],
        "편의점": ["convenience_store"],
        "시장": ["market"],
        "아울렛": ["shopping_mall", "store"],
        "가구점": ["furniture_store"],
        "전자제품": ["electronics_store"],
        "서점": ["book_store"],
        "문구점": ["store"],
        "의류매장": ["clothing_store"],
        "신발가게": ["shoe_store"],
        "화장품": ["store"],
        "보석가게": ["jewelry_store"],
        "장난감": ["store"],
        "스포츠용품": ["sporting_goods_store"],
        
        # 교통
        "공항": ["airport"],
        "국제공항": ["international_airport"],
        "기차역": ["train_station"],
        "버스터미널": ["bus_station"],
        "버스정류장": ["bus_stop"],
        "지하철역": ["subway_station"],
        "택시정류장": ["taxi_stand"],
        "주차장": ["parking"],
        "휴게소": ["rest_stop"],
        
        # 숙박
        "호텔": ["hotel", "lodging"],
        "펜션": ["lodging"],
        "리조트": ["resort_hotel", "lodging"],
        "모텔": ["motel", "lodging"],
        "게스트하우스": ["guest_house", "lodging"],
        "민박": ["lodging"],
        "캠핑장": ["campground"],
        
        # 의료
        "병원": ["hospital"],
        "의원": ["doctor"],
        "치과": ["dentist", "dental_clinic"],
        "약국": ["pharmacy"],
        "동물병원": ["veterinary_care"],
        "한의원": ["doctor"],
        "보건소": ["doctor", "hospital"],
        
        # 금융
        "은행": ["bank"],
        "ATM": ["atm"],
        "증권사": ["finance"],
        "보험사": ["insurance_agency"],
        
        # 서비스
        "미용실": ["hair_salon"],
        "네일샵": ["nail_salon"],
        "피부관리실": ["skin_care_clinic"],
        "세탁소": ["laundry"],
        "부동산": ["real_estate_agency"],
        "이사": ["moving_company"],
        "변호사": ["lawyer"],
        "경찰서": ["police"],
        "소방서": ["fire_station"],
        "우체국": ["post_office"],
        "시청": ["city_hall"],
        "구청": ["local_government_office"],
        "대사관": ["embassy"],
        
        # 종교
        "교회": ["church"],
        "성당": ["church"],
        "사찰": ["place_of_worship"],
        "절": ["place_of_worship"],
        "사원": ["hindu_temple"],
        "모스크": ["mosque"],
        "신사": ["place_of_worship"],
        
        # 교육문화
        "도서관": ["library"],
        "독서실": ["library"],
        "문화센터": ["cultural_center"],
        "전시관": ["museum", "art_gallery"],
        "과학관": ["museum"],
        "콘서트홀": ["concert_hall"],
        "공연장": ["performing_arts_theater"],
        
        # 기타
        "관광지": ["tourist_attraction"],
        "명소": ["tourist_attraction"],
        "해변": ["beach"],
        "온천": ["spa"],
        "산": ["natural_feature"],
        "광장": ["plaza"],
        "전망대": ["observation_deck"],
        "역사유적": ["historical_landmark"]
    }


# 장소 이름에서 가장 적합한 구글 장소 유형을 유추하는 향상된 함수
def get_place_type(place_name: str) -> Optional[str]:
    """장소 이름에서 가장 적합한 구글 장소 유형을 유추"""
    logger = logging.getLogger('place_type_detector')
    
    # 입력이 없으면 None 반환
    if not place_name:
        return None
    
    place_name_lower = place_name.lower()
    type_mapping = get_place_type_mapping()
    
    # 1. 직접 매칭 - 장소명에 유형 키워드가 있는지 확인
    for keyword, types in type_mapping.items():
        if keyword in place_name_lower:
            logger.info(f"'{place_name}' 장소에서 '{keyword}' 키워드 발견, 유형: {types[0]}")
            return types[0]
    
    # 2. 패턴 기반 유추 - 일반적인 패턴 확인
    
    # 음식 관련
    if re.search(r'(식당|음식|맛집|레스토랑|밥집|먹거리)', place_name_lower):
        return "restaurant"
    elif re.search(r'(카페|커피|디저트|cake|coffee)', place_name_lower):
        return "cafe"
    elif re.search(r'(빵|베이커리|bakery)', place_name_lower):
        return "bakery"
    elif re.search(r'(치킨|통닭|프라이드)', place_name_lower):
        return "meal_takeaway"
    elif re.search(r'(피자|pizza)', place_name_lower):
        return "pizza_restaurant"
    elif re.search(r'(햄버거|burger)', place_name_lower):
        return "hamburger_restaurant"
    elif re.search(r'(주점|술집|포차|bar|pub)', place_name_lower):
        return "bar"
    
    # 교육 관련
    elif re.search(r'(대학교|대학|캠퍼스|university)', place_name_lower):
        return "university"
    elif re.search(r'(초등학교|중학교|고등학교|학교)', place_name_lower):
        return "school"
    elif re.search(r'(도서관|library)', place_name_lower):
        return "library"
    
    # 스포츠/레저 관련
    elif re.search(r'(경기장|구장|월드컵|야구장|축구장|stadium)', place_name_lower):
        return "stadium"
    elif re.search(r'(수영장|pool)', place_name_lower):
        return "swimming_pool"
    elif re.search(r'(공원|park)', place_name_lower):
        return "park"
    elif re.search(r'(놀이공원|테마파크|amusement)', place_name_lower):
        return "amusement_park"
    elif re.search(r'(동물원|zoo)', place_name_lower):
        return "zoo"
    elif re.search(r'(극장|영화관|시네마|cinema)', place_name_lower):
        return "movie_theater"
    elif re.search(r'(박물관|museum)', place_name_lower):
        return "museum"
    elif re.search(r'(미술관|갤러리|gallery)', place_name_lower):
        return "art_gallery"
    
    # 쇼핑 관련
    elif re.search(r'(쇼핑|mall|백화점|몰)', place_name_lower):
        return "shopping_mall"
    elif re.search(r'(마트|슈퍼|market|마켓)', place_name_lower):
        return "supermarket"
    elif re.search(r'(편의점|store)', place_name_lower):
        return "convenience_store"
    
    # 교통 관련
    elif re.search(r'(공항|airport)', place_name_lower):
        return "airport"
    elif re.search(r'(역|station|기차|철도)', place_name_lower):
        return "train_station"
    elif re.search(r'(버스|터미널|정류장)', place_name_lower):
        return "bus_station"
    elif re.search(r'(지하철)', place_name_lower):
        return "subway_station"
    
    # 숙박 관련
    elif re.search(r'(호텔|hotel|숙박|모텔|펜션|리조트|resort)', place_name_lower):
        return "lodging"
    
    # 의료 관련
    elif re.search(r'(병원|의원|clinic|hospital)', place_name_lower):
        return "hospital"
    elif re.search(r'(약국|pharmacy|drug)', place_name_lower):
        return "pharmacy"
    elif re.search(r'(치과|dental)', place_name_lower):
        return "dentist"
    
    # 기타
    elif re.search(r'(은행|bank)', place_name_lower):
        return "bank"
    elif re.search(r'(관광|명소|tourist|attraction)', place_name_lower):
        return "tourist_attraction"
    elif re.search(r'(교회|성당|church)', place_name_lower):
        return "church"
    elif re.search(r'(사찰|절|temple)', place_name_lower):
        return "hindu_temple"
    elif re.search(r'(미용|헤어|hair)', place_name_lower):
        return "hair_salon"
    elif re.search(r'(사무실|office)', place_name_lower):
        return "corporate_office"
    elif re.search(r'(온천|spa|목욕탕)', place_name_lower):
        return "spa"
    
    # 3. 특정 대상 이름 패턴 (한국 특화)
    if "롯데월드" in place_name_lower or "에버랜드" in place_name_lower:
        return "amusement_park"
    elif "스타벅스" in place_name_lower or "투썸" in place_name_lower or "이디야" in place_name_lower:
        return "cafe"
    elif "롯데마트" in place_name_lower or "이마트" in place_name_lower or "홈플러스" in place_name_lower:
        return "supermarket"
    elif "CGV" in place_name_lower or "롯데시네마" in place_name_lower or "메가박스" in place_name_lower:
        return "movie_theater"
    elif "신세계" in place_name_lower or "롯데백화점" in place_name_lower or "현대백화점" in place_name_lower:
        return "department_store"
    
    # 4. 장소명이 짧은 일반명사인 경우 (한국어)
    if len(place_name_lower) < 5:
        if place_name_lower in ["숲", "공원", "산"]:
            return "park"
        elif place_name_lower in ["식당", "밥집"]:
            return "restaurant"
        elif place_name_lower in ["카페"]:
            return "cafe"
        elif place_name_lower in ["마트"]:
            return "supermarket"
        elif place_name_lower in ["학교"]:
            return "school"
    
    # 5. 대표적인 장소 유형 추론 (지역 특성)
    if re.search(r'(강남|명동|홍대|이태원|가로수길)', place_name_lower):
        # 유명 상권 지역은 음식점/카페 가능성이 높음
        return "restaurant"
    elif re.search(r'(산|봉|계곡|천|강|호수|바다)', place_name_lower):
        # 자연 지형 관련 이름
        return "natural_feature"
    
    # 기본값: 일반 관심장소 (POI)
    logger.info(f"'{place_name}' 장소에서 유형을 유추할 수 없음, 일반 POI 적용")
    return "point_of_interest"


def search_place_with_retry(places_tool, query: str, place_type: str = None, region: str = None, retries: int = 2, delay: float = 0.5) -> Optional[Dict]:
    """
    재시도 로직을 포함한 장소 검색 함수
    
    Args:
        places_tool: GooglePlacesTool 인스턴스
        query: 검색 쿼리
        place_type: 장소 유형 (restaurant, cafe 등)
        region: 지역 컨텍스트 (서울, 부산 등)
        retries: 재시도 횟수
        delay: 재시도 간 지연 시간(초)
        
    Returns:
        장소 정보 딕셔너리 또는 None (실패 시)
    """
    logger = logging.getLogger('place_search')
    
    # 검색 쿼리 최적화
    optimized_query = places_tool.build_search_query(query, place_type, region)
    cache_key = f"{optimized_query}_{place_type or ''}"
    
    # 캐시 확인
    if hasattr(places_tool, 'search_cache') and cache_key in places_tool.search_cache:
        logger.info(f"캐시에서 '{cache_key}' 검색 결과 반환")
        return places_tool.search_cache[cache_key]
    
    # 재시도 로직
    for attempt in range(retries):
        try:
            # Places API 매개변수 최적화
            if place_type:
                result = places_tool.search_place_detailed(optimized_query, place_type)
            else:
                result = places_tool.search_place_detailed(optimized_query)
                
            if result:
                logger.info(f"'{optimized_query}' 검색 성공 (시도 {attempt+1}/{retries})")
                
                # 캐시에 저장
                if hasattr(places_tool, 'search_cache'):
                    places_tool.search_cache[cache_key] = result
                    logger.info(f"'{cache_key}' 검색 결과 캐싱")
                
                return result
                
            logger.warning(f"'{optimized_query}' 검색 실패 (시도 {attempt+1}/{retries})")
        except Exception as e:
            logger.error(f"검색 시도 {attempt+1}/{retries} 실패: {str(e)}")
        
        if attempt < retries - 1:
            # 마지막 시도 전이면 일시 지연 후 재시도
            time.sleep(delay)
    
    # 모든 시도 실패 후 None 반환
    logger.warning(f"'{optimized_query}' 검색이 {retries}번 모두 실패")
    return None


def find_alternative_place(places_tool, original_query: str, used_places: Set[str], primary_location: Optional[Tuple[float, float]] = None, region: str = None) -> Optional[Dict]:
    """
    이미 사용된 장소를 피해 대안 찾기
    
    Args:
        places_tool: GooglePlacesTool 인스턴스
        original_query: 원본 검색 쿼리
        used_places: 이미 사용된 장소 ID 집합
        primary_location: 기준 위치 좌표 (위도, 경도)
        region: 지역 컨텍스트 (서울, 부산 등)
        
    Returns:
        장소 정보 딕셔너리 또는 None (실패 시)
    """
    logger = logging.getLogger('alternative_search')
    logger.info(f"'{original_query}'에 대한 대체 장소 검색 시작")
    
    # 이미 시도한 쿼리 추적
    attempted_queries = set()
    
    # 원본 쿼리에서 장소 유형 추출
    place_type = get_place_type(original_query)
    logger.info(f"유추된 장소 유형: {place_type or '없음'}")
    
    # 검색 변형 전략 1: 쿼리 변형
    query_variants = []
    
    # 기본 변형
    query_variants.extend([
        f"{original_query} 인근",
        f"{original_query} 근방",
        f"{original_query} 주변",
        f"다른 {original_query}"
    ])
    
    # 장소 유형별 키워드 추가
    if place_type:
        type_mapping = get_place_type_mapping()
        
        # 유형에 따른 대체 키워드 찾기
        for keyword, types in type_mapping.items():
            if place_type in types:
                if keyword not in original_query:
                    # 'restaurant' 유형이면 '식당', '레스토랑' 등을 추가
                    if region:
                        query_variants.append(f"{region} {keyword}")
                    else:
                        query_variants.append(keyword)
    
    # 검색 변형 전략 2: 지역 기반 변형
    if region:
        for district in ["중구", "남구", "북구", "동구", "서구"]:
            if district not in original_query:
                query_variants.append(f"{region} {district} {original_query}")
    
    # 쿼리 변형 중복 제거 및 로그
    query_variants = list(set(query_variants))
    logger.info(f"검색 쿼리 변형: {query_variants}")
    
    # 쿼리 변형으로 검색
    for variant in query_variants:
        if variant in attempted_queries:
            continue
        
        attempted_queries.add(variant)
        logger.info(f"변형 쿼리 '{variant}' 검색 시도")
        
        result = search_place_with_retry(places_tool, variant, place_type, region)
        
        if result and result.get("place_id") not in used_places:
            logger.info(f"대체 검색 성공: '{variant}' -> {result.get('name')}")
            return result
    
    # 검색 전략 3: 주변 검색 (좌표가 있는 경우)
    if primary_location:
        logger.info(f"위치 기반 검색 시도: {primary_location}")
        
        # 다양한 반경으로 시도
        for radius in [1000, 2000, 3000, 5000]:
            try:
                # 유형이 없으면 기본 쿼리로 검색
                search_term = original_query
                if search_term in attempted_queries:
                    search_term = f"near {original_query}"
                
                attempted_queries.add(search_term)
                location_str = f"{primary_location[0]},{primary_location[1]}"
                
                result = places_tool.search_nearby_detailed(
                    search_term, 
                    location=location_str, 
                    radius=radius,
                    place_type=place_type
                )
                
                if result and result.get("place_id") not in used_places:
                    logger.info(f"위치 기반 대체 검색 성공 (반경 {radius}m): {result.get('name')}")
                    return result
                
                # 유형 기반 장소 찾기 시도
                if place_type:
                    # 지역명을 접두사로 사용하여 더 관련성 높은 결과 찾기
                    type_name = "장소"  # 기본값
                    for keyword, types in get_place_type_mapping().items():
                        if place_type in types:
                            type_name = keyword
                            break
                    
                    logger.info(f"유형 기반 주변 검색 시도: {type_name}, 반경 {radius}m")
                    search_term = f"{region or ''} {type_name}"
                    
                    if search_term.strip() in attempted_queries:
                        continue
                    
                    attempted_queries.add(search_term.strip())
                    
                    result = places_tool.search_nearby_detailed(
                        search_term,
                        location=location_str, 
                        radius=radius,
                        place_type=place_type
                    )
                    
                    if result and result.get("place_id") not in used_places:
                        logger.info(f"유형 기반 주변 검색 성공 (반경 {radius}m): {result.get('name')}")
                        return result
            except Exception as e:
                logger.error(f"위치 기반 대체 검색 실패 (반경 {radius}m): {str(e)}")
    
    # 모든 시도 실패 시 대체 유형으로 시도
    if place_type:
        alt_types = get_alternative_types(place_type)
        logger.info(f"대체 유형으로 검색 시도: {alt_types}")
        
        for alt_type in alt_types:
            if region:
                search_term = f"{region} {original_query}"
            else:
                search_term = original_query
                
            if f"{search_term}_{alt_type}" in attempted_queries:
                continue
                
            attempted_queries.add(f"{search_term}_{alt_type}")
            logger.info(f"대체 유형 '{alt_type}' 검색 시도: '{search_term}'")
            
            result = search_place_with_retry(places_tool, search_term, alt_type, region)
            
            if result and result.get("place_id") not in used_places:
                logger.info(f"대체 유형 검색 성공: '{search_term}' ({alt_type}) -> {result.get('name')}")
                return result
    
    # 모든 시도 실패
    logger.warning(f"'{original_query}'에 대한 모든 대체 검색 실패")
    return None


def get_alternative_types(place_type: str) -> List[str]:
    """주어진 장소 유형에 대한 대체 유형 목록 반환"""
    # 유형별 대체 유형 맵핑
    alt_types_map = {
        "restaurant": ["food", "meal_takeaway", "cafe"],
        "cafe": ["coffee_shop", "restaurant", "bakery"],
        "stadium": ["sports_complex", "arena"],
        "university": ["school", "secondary_school"],
        "shopping_mall": ["department_store", "store", "clothing_store"],
        "supermarket": ["grocery_store", "convenience_store"],
        "hospital": ["doctor", "pharmacy"],
        "park": ["tourist_attraction", "natural_feature"],
        "hotel": ["lodging", "resort_hotel"],
        "bank": ["atm", "finance"],
        "bar": ["pub", "restaurant"],
        "movie_theater": ["entertainment", "performing_arts_theater"],
        # 기본 대체 유형
        "default": ["point_of_interest", "establishment"]
    }
    
    # 주어진 유형에 대한 대체 유형 반환 (없으면 기본값)
    if place_type in alt_types_map:
        return alt_types_map[place_type]
    else:
        return alt_types_map["default"]
    
def calculate_route_with_traffic(origin_lat, origin_lng, dest_lat, dest_lng, departure_time=None):
    """교통 상황을 고려한, 실제 도로망 기반 경로 계산"""
    try:
        # Google Maps Directions 도구 인스턴스 생성
        directions_tool = GoogleMapsDirectionsTool()
        
        # 교통 데이터 조회
        traffic_data = directions_tool.get_traffic_data(origin_lat, origin_lng, dest_lat, dest_lng, departure_time)
        
        if traffic_data["has_traffic_data"]:
            # 교통 데이터가 있으면 해당 데이터 사용
            return {
                "distance": traffic_data["distance"],
                "estimatedTime": traffic_data["estimated_time_in_traffic"],
                "trafficRate": traffic_data["traffic_rate"],
                "recommendedRoute": traffic_data["steps"],
                "realTimeTraffic": True,
                "polyline": traffic_data["overview_polyline"]
            }
        else:
            # 교통 데이터가 없으면 기본 계산 사용
            return {
                "distance": traffic_data["distance"],
                "estimatedTime": traffic_data["estimated_time"],
                "trafficRate": 1.0,
                "recommendedRoute": None,
                "realTimeTraffic": False,
                "polyline": None
            }
    except Exception as e:
        print(f"경로 계산 중 오류 발생: {str(e)}")
        # 오류 발생 시 기본 직선 거리 계산 사용
        distance = calculate_distance(origin_lat, origin_lng, dest_lat, dest_lng)
        return {
            "distance": distance,
            "estimatedTime": calculate_travel_time(distance),
            "trafficRate": 1.0,
            "recommendedRoute": None,
            "realTimeTraffic": False,
            "polyline": None
        }
# ----- 엔드포인트 정의 -----

@app.get("/")
async def root():
    return {"message": "일정 추출 및 최적화 API가 실행 중입니다. POST /extract-schedule 또는 POST /api/v1/schedules/optimize-1 엔드포인트를 사용하세요."}

@app.post("/extract-schedule", response_model=ExtractScheduleResponse)
async def extract_schedule(request: ScheduleRequest):  # 메소드 이름 그대로!
    """
    음성 입력에서 일정을 추출하고 위치 정보를 보강합니다.
    """
    # 로깅 설정
    logger = logging.getLogger('extract_schedule')
    logger.setLevel(logging.INFO)
    
    try:
        logger.info(f"일정 추출 요청 받음: 음성 입력 길이={len(request.voice_input)}")
        
        # 🔥 1. LLM 체인 실행을 비동기로 (timeout 적용)
        chain = create_schedule_chain()
        
        try:
            result = await asyncio.wait_for(
                run_sync_in_thread(lambda: chain.invoke({"input": request.voice_input})),
                timeout=60  # 1분 제한
            )
        except asyncio.TimeoutError:
            logger.error("LLM 호출 timeout")
            return ExtractScheduleResponse(fixedSchedules=[], flexibleSchedules=[])
        
        # 🔥 2. 결과 파싱 (기존 코드와 동일)
        schedule_data = None
        if isinstance(result, str):
            json_match = re.search(r'({[\s\S]*})', result)
            if json_match:
                schedule_data = safe_parse_json(json_match.group(1))
            else:
                schedule_data = safe_parse_json(result)
        else:
            try:
                result_json = json.dumps(result, ensure_ascii=False)
                schedule_data = json.loads(result_json)
            except Exception as e:
                schedule_data = result
        
        # 🔥 3. 각 강화 단계를 비동기로 실행 (각각 timeout 적용)
        
        # 시간 추론
        try:
            enhancement_chains = create_enhancement_chain()
            schedule_data = await asyncio.wait_for(
                run_sync_in_thread(
                    apply_time_inference,
                    enhancement_chains["time_chain"],
                    request.voice_input,
                    schedule_data
                ),
                timeout=30  # 30초 제한
            )
        except asyncio.TimeoutError:
            logger.warning("시간 추론 timeout, 원본 데이터 사용")
        except Exception as e:
            logger.warning(f"시간 추론 실패: {str(e)}")
        
        # 충돌 해결
        try:
            schedule_data = await asyncio.wait_for(
                run_sync_in_thread(detect_and_resolve_time_conflicts, schedule_data),
                timeout=30
            )
        except asyncio.TimeoutError:
            logger.warning("충돌 해결 timeout")
        except Exception as e:
            logger.warning(f"충돌 해결 실패: {str(e)}")
        
        # 우선순위 분석
        try:
            enhancement_chains = create_enhancement_chain()
            schedule_data = await asyncio.wait_for(
                run_sync_in_thread(
                    apply_priorities,
                    enhancement_chains["priority_chain"],
                    request.voice_input,
                    schedule_data
                ),
                timeout=30
            )
        except asyncio.TimeoutError:
            logger.warning("우선순위 분석 timeout")
        except Exception as e:
            logger.warning(f"우선순위 분석 실패: {str(e)}")
        
        # 관계 분석
        try:
            schedule_data = await asyncio.wait_for(
                run_sync_in_thread(
                    enhance_schedule_with_relationships,
                    request.voice_input,
                    schedule_data
                ),
                timeout=30
            )
        except asyncio.TimeoutError:
            logger.warning("관계 분석 timeout")
        except Exception as e:
            logger.warning(f"관계 분석 실패: {str(e)}")
        
        # 🔥 4. 위치 정보 보강 (기존 함수를 비동기로 실행)
        try:
            schedule_data = await asyncio.wait_for(
                run_sync_in_thread(enhance_location_data, schedule_data),
                timeout=120  # 2분 제한
            )
        except asyncio.TimeoutError:
            logger.warning("위치 정보 보강 timeout")
        except Exception as e:
            logger.warning(f"위치 정보 보강 실패: {str(e)}")
        
        # 🔥 5. 최종 데이터 정리 (기존 코드와 동일)
        all_schedules = []
        all_schedules.extend(schedule_data.get("fixedSchedules", []))
        all_schedules.extend(schedule_data.get("flexibleSchedules", []))
        
        fixed_schedules = [s for s in all_schedules if s.get("type") == "FIXED" and "startTime" in s and "endTime" in s]
        flexible_schedules = [s for s in all_schedules if s.get("type") != "FIXED" or "startTime" not in s or "endTime" not in s]
        
        final_data = {
            "fixedSchedules": fixed_schedules,
            "flexibleSchedules": flexible_schedules
        }
        
        # Pydantic 모델로 변환
        try:
            response = ExtractScheduleResponse(**final_data)
            return response
        except Exception as e:
            logger.error(f"Pydantic 모델 변환 오류: {str(e)}")
            from fastapi.responses import JSONResponse
            return JSONResponse(
                content=final_data,
                media_type="application/json; charset=utf-8"
            )
            
    except Exception as e:
        logger.error(f"일정 처리 전체 오류: {str(e)}")
        return ExtractScheduleResponse(fixedSchedules=[], flexibleSchedules=[])

@app.post("/api/v1/schedules/optimize-1", response_model=OptimizeScheduleResponse)
async def optimize_schedules(request: OptimizeScheduleRequest):
    """
    추출된 일정을 최적화하고 경로 정보를 생성합니다.
    """
    try:
        # 인코딩 테스트 함수
        def test_encoding(text):
            """한글 인코딩 테스트 함수"""
            print(f"원본 텍스트: {text}")
            
            # 다양한 인코딩으로 변환 테스트
            encodings = ['utf-8', 'euc-kr', 'cp949']
            for enc in encodings:
                try:
                    encoded = text.encode(enc)
                    decoded = encoded.decode(enc)
                    print(f"{enc} 인코딩 변환 결과: {decoded}, 변환 성공: {text == decoded}")
                except Exception as e:
                    print(f"{enc} 인코딩 변환 실패: {str(e)}")
            
            # JSON 직렬화/역직렬화 테스트
            try:
                json_str = json.dumps({"text": text}, ensure_ascii=False)
                json_obj = json.loads(json_str)
                print(f"JSON 변환 결과: {json_obj['text']}, 변환 성공: {text == json_obj['text']}")
            except Exception as e:
                print(f"JSON 변환 실패: {str(e)}")

        # 시스템 인코딩 정보 확인
        import sys
        import locale
        print(f"시스템 기본 인코딩: {sys.getdefaultencoding()}")
        print(f"로케일 인코딩: {locale.getpreferredencoding()}")
        print(f"파이썬 파일 기본 인코딩: {sys.getfilesystemencoding()}")

        print(f"일정 최적화 요청 받음: 고정 일정 {len(request.fixedSchedules)}개, 유연 일정 {len(request.flexibleSchedules)}개")
        
        # 입력 데이터 인코딩 테스트
        if request.fixedSchedules:
            first_fixed = request.fixedSchedules[0]
            print("\n첫 번째 고정 일정 인코딩 테스트:")
            test_encoding(first_fixed.name)
            test_encoding(first_fixed.location)
        
        if request.flexibleSchedules:
            first_flexible = request.flexibleSchedules[0]
            print("\n첫 번째 유연 일정 인코딩 테스트:")
            test_encoding(first_flexible.name)
            test_encoding(first_flexible.location)
        
        # 1. 모든 일정을 수집 (고정 일정 + 유연 일정)
        all_schedules = []
        fixed_schedule_map = {}
        
        # 고정 일정 처리
        for schedule in request.fixedSchedules:
            fixed_schedule_map[schedule.id] = schedule
            all_schedules.append({
                "id": schedule.id,
                "name": schedule.name,
                "start_time": parse_datetime(schedule.startTime),
                "end_time": parse_datetime(schedule.endTime),
                "duration": schedule.duration,
                "priority": schedule.priority,
                "latitude": schedule.latitude,
                "longitude": schedule.longitude,
                "location": schedule.location,
                "type": schedule.type,
                "flexible": False
            })
        
        # 유연 일정 처리
        for schedule in request.flexibleSchedules:
            all_schedules.append({
                "id": schedule.id,
                "name": schedule.name,
                "start_time": None,  # 아직 시간이 정해지지 않음
                "end_time": None,
                "duration": schedule.duration,
                "priority": schedule.priority,
                "latitude": schedule.latitude,
                "longitude": schedule.longitude,
                "location": schedule.location,
                "type": schedule.type,
                "flexible": True
            })
        
        # 수집한 데이터 인코딩 테스트
        if all_schedules:
            print("\n첫 번째 수집 일정 인코딩 테스트:")
            test_encoding(all_schedules[0]["name"])
            test_encoding(all_schedules[0]["location"])
        
        # 2. 일정 최적화
        
        # 고정 일정을 시간순으로 정렬
        fixed_schedules = [s for s in all_schedules if not s["flexible"]]
        fixed_schedules.sort(key=lambda x: x["start_time"])
        
        # 유연 일정을 우선순위순으로 정렬
        flexible_schedules = [s for s in all_schedules if s["flexible"]]
        flexible_schedules.sort(key=lambda x: x["priority"])
        
        # 최적화된 일정 목록
        optimized_schedules = []
        
        # 고정 일정 먼저 추가
        optimized_schedules.extend(fixed_schedules)
        
        # 가장 늦은 고정 일정을 기준으로 유연 일정 시간 할당
        if fixed_schedules:
            # 마지막 고정 일정 시간 이후로 배치
            last_fixed = fixed_schedules[-1]
            current_time = last_fixed["end_time"]
            
            # 유연 일정에 시간 배정
            for schedule in flexible_schedules:
                start_time = current_time
                end_time = start_time + datetime.timedelta(minutes=schedule["duration"])
                
                schedule["start_time"] = start_time
                schedule["end_time"] = end_time
                
                # 다음 일정의 시작 시간 설정
                current_time = end_time
                
                # 최적화된 일정에 추가
                optimized_schedules.append(schedule)
        else:
            # 고정 일정이 없는 경우, 현재 시간부터 시작
            current_time = datetime.datetime.now()
            
            # 유연 일정에 시간 배정
            for schedule in flexible_schedules:
                start_time = current_time
                end_time = start_time + datetime.timedelta(minutes=schedule["duration"])
                
                schedule["start_time"] = start_time
                schedule["end_time"] = end_time
                
                # 다음 일정의 시작 시간 설정
                current_time = end_time
                
                # 최적화된 일정에 추가
                optimized_schedules.append(schedule)
        
        # 시간순으로 재정렬
        optimized_schedules.sort(key=lambda x: x["start_time"])
        
        # 최적화된 일정 인코딩 테스트
        if optimized_schedules:
            print("\n최적화된 첫 번째 일정 인코딩 테스트:")
            test_encoding(optimized_schedules[0]["name"])
            test_encoding(optimized_schedules[0]["location"])
        
        # 3. 경로 정보 계산
        route_segments = []
        total_distance = 0.0
        total_time = 0
        
        for i in range(len(optimized_schedules) - 1):
            from_schedule = optimized_schedules[i]
            to_schedule = optimized_schedules[i+1]
            
            # 교통 상황을 고려한 경로 계산
            # 출발 시간을 현재 일정의 종료 시간으로 설정
            departure_time = from_schedule["end_time"].isoformat() if hasattr(from_schedule["end_time"], "isoformat") else from_schedule["end_time"]
            
            route_data = calculate_route_with_traffic(
                from_schedule["latitude"], from_schedule["longitude"],
                to_schedule["latitude"], to_schedule["longitude"],
                departure_time
            )
            
            # 경로 정보 추가
            route_segments.append({
                "fromLocation": from_schedule["name"],
                "toLocation": to_schedule["name"],
                "distance": route_data["distance"],
                "estimatedTime": route_data["estimatedTime"],
                "trafficRate": route_data["trafficRate"],
                "recommendedRoute": route_data["recommendedRoute"],
                "realTimeTraffic": route_data["realTimeTraffic"]
            })
            
            # 총 거리와 시간 누적
            total_distance += route_data["distance"]
            total_time += route_data["estimatedTime"]
        
        # 경로 정보 인코딩 테스트
        if route_segments:
            print("\n경로 정보 인코딩 테스트:")
            test_encoding(route_segments[0]["fromLocation"])
            test_encoding(route_segments[0]["toLocation"])
        
        # 4. 일정 분석 정보 생성
        schedule_analyses = {}
        
        for schedule in optimized_schedules:
            # 장소 카테고리 유추
            category = get_place_category(schedule["name"])
            
            # 영업 시간 유추
            operating_hours = generate_operating_hours(schedule["name"])
            
            # 영업 여부 확인
            is_open = check_place_open(operating_hours, schedule["start_time"])
            
            # 혼잡도 임의 생성 (0.3~0.7 사이)
            crowd_level = round(random.uniform(0.3, 0.7), 1)
            
            # 추천 정보 생성
            crowd_level_status = "보통"
            if crowd_level < 0.4:
                crowd_level_status = "여유"
            elif crowd_level > 0.6:
                crowd_level_status = "혼잡"
            
            best_visit_time = f"영업시간({operating_hours['open']}-{operating_hours['close']}) 중 방문 권장"
            estimated_duration = f"{schedule['duration'] // 60:02d}:{schedule['duration'] % 60:02d}"
            
            # 장소명 추출 (인코딩 테스트)
            place_name_parts = schedule['name'].split(' - ')
            if len(place_name_parts) > 0:
                place_name = place_name_parts[0]
                print(f"\n장소명 분리 테스트 ('{schedule['name']}' -> '{place_name}')")
                test_encoding(place_name)
            else:
                place_name = schedule['name']
            
            # 장소 상세 정보
            place_details = {
                "phoneNumber": "",
                "address": schedule["location"],
                "isOpen": is_open,
                "operatingHours": operating_hours,
                "name": f"<b>{place_name}</b>",
                "rating": 0.0,
                "recommendation": {
                    "crowdLevelStatus": crowd_level_status,
                    "bestVisitTime": best_visit_time,
                    "estimatedDuration": estimated_duration
                },
                "location": {
                    "latitude": schedule["latitude"],
                    "longitude": schedule["longitude"],
                    "name": place_name
                },
                "id": "null",
                "crowdLevel": crowd_level,
                "category": category
            }
            
            # 일정 분석 정보 추가
            schedule_analyses[schedule["name"]] = {
                "locationName": schedule["name"],
                "bestTimeWindow": None,
                "crowdLevel": crowd_level,
                "placeDetails": place_details,
                "optimizationFactors": None,
                "visitRecommendation": None
            }
        
        # 일정 분석 정보 인코딩 테스트
        if schedule_analyses:
            first_key = next(iter(schedule_analyses))
            print("\n일정 분석 정보 인코딩 테스트:")
            test_encoding(first_key)
            test_encoding(schedule_analyses[first_key]["locationName"])
            test_encoding(schedule_analyses[first_key]["placeDetails"]["name"])
            test_encoding(schedule_analyses[first_key]["placeDetails"]["address"])
        
        # 5. 응답 구성
        
        # 최적화된 일정 목록
        optimized_schedules_response = []
        
        for schedule in optimized_schedules:
            # LocationString 생성 - 인코딩 테스트 추가
            if schedule["flexible"]:
                # 유연 일정은 JSON 형태로 위치 정보 저장
                location_info = {
                    "address": schedule["location"],
                    "distance": round(random.uniform(300, 700), 6),
                    "latitude": schedule["latitude"],
                    "name": schedule["name"].split(" - ")[1] if " - " in schedule["name"] else schedule["name"],
                    "rating": round(random.uniform(3.5, 4.5), 1),
                    "source": "foursquare",
                    "longitude": schedule["longitude"]
                }
                
                # locationString 인코딩 테스트
                print(f"\nlocationString JSON 인코딩 테스트:")
                test_encoding(location_info["name"])
                test_encoding(location_info["address"])
                
                # 수정된 부분: ensure_ascii=False와 separators 옵션 추가
                location_string = json.dumps(location_info, ensure_ascii=False, separators=(',', ':'))
                
                # 직렬화 결과 확인
                print(f"locationString 직렬화 결과 샘플: {location_string[:100]}...")
                
                # 역직렬화 테스트
                try:
                    decoded_location = json.loads(location_string)
                    print(f"locationString 역직렬화 성공: {decoded_location['name']}")
                except Exception as e:
                    print(f"locationString 역직렬화 실패: {str(e)}")
            else:
                # 고정 일정은 주소만 저장
                location_string = schedule["location"]
                print(f"\n고정 일정 locationString: {location_string}")
                test_encoding(location_string)
            
            # 시간 포맷팅
            start_time_str = schedule["start_time"].isoformat()
            end_time_str = schedule["end_time"].isoformat()
            
            # 이름 분리 테스트
            name_parts = schedule["name"].split(" - ")
            display_name = name_parts[0] if " - " in schedule["name"] else schedule["name"]
            print(f"\n일정 이름 분리 테스트: '{schedule['name']}' -> '{display_name}'")
            test_encoding(display_name)
            
            optimized_schedule = {
                "id": schedule["id"],
                "name": schedule["name"],
                "location": {
                    "latitude": schedule["latitude"],
                    "longitude": schedule["longitude"],
                    "name": display_name
                },
                "startTime": start_time_str,
                "endTime": end_time_str,
                "type": schedule["type"],
                "priority": schedule["priority"],
                "category": None,
                "estimatedDuration": schedule["duration"],
                "expectedCost": 0.0,
                "visitPreference": None,
                "locationString": location_string,
                "constraints": {
                    "earliestStartTime": None,
                    "latestEndTime": None,
                    "requiresWeekend": False,
                    "minimumDuration": 0,
                    "maxTravelDistance": 0.0
                },
                "duration": format_duration(schedule["duration"]),
                "flexible": schedule["flexible"]
            }
            
            optimized_schedules_response.append(optimized_schedule)
        
        # 메트릭 정보
        metrics = {
            "totalDistance": round(total_distance, 3),
            "totalTime": total_time,
            "totalScore": 0.0,
            "successRate": 0.0,
            "componentScores": None,
            "optimizationReasons": None
        }
        
        # 최종 응답 구성
        response = {
            "optimizedSchedules": optimized_schedules_response,
            "routeSegments": route_segments,
            "metrics": metrics,
            "alternativeOptions": None,
            "scheduleAnalyses": schedule_analyses
        }
        
        # 최종 응답 인코딩 테스트
        print("\n최종 응답 직렬화 테스트:")
        try:
            # FastAPI의 기본 JSON 인코딩이 아닌 직접 직렬화 테스트
            response_json = json.dumps(response, ensure_ascii=False, separators=(',', ':'))
            print(f"응답 직렬화 성공, 길이: {len(response_json)}")
            print(f"응답 JSON 샘플: {response_json[:200]}...")
            
            # 역직렬화 테스트
            test_obj = json.loads(response_json)
            if test_obj["optimizedSchedules"]:
                first_schedule = test_obj["optimizedSchedules"][0]
                print(f"역직렬화된 첫 번째 일정 이름: {first_schedule['name']}")
                print(f"역직렬화 성공!")
        except Exception as e:
            print(f"응답 직렬화/역직렬화 오류: {str(e)}")
            import traceback
            print(traceback.format_exc())
        
        # FastAPI의 기본 JSON 인코딩 대신 직접 JSON 응답 반환
        from fastapi.responses import JSONResponse
        return JSONResponse(
            content=response,
            media_type="application/json; charset=utf-8"
        )
        
    except Exception as e:
        print(f"일정 최적화 중 오류 발생: {str(e)}")
        import traceback
        print(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"일정 최적화 중 오류 발생: {str(e)}")
# 서버 시작 코드
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="0.0.0.0", port=8081, reload=True)