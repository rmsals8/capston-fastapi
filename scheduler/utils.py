# scheduler/utils.py에 개선된 시간 충돌 감지 및 해결 함수

import datetime
import logging
from typing import Dict, Any, Optional, List, Tuple
import math
import aiohttp
import asyncio
import os
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

 
class TravelTimeCalculator:
    """Google Maps API + 카카오 API를 활용한 이동시간 계산 클래스"""
    
    def __init__(self):
        # API 키들
        self.google_api_key = os.getenv("GOOGLE_MAPS_API_KEY")
        self.kakao_api_key = os.getenv("KAKAO_REST_API_KEY")
        
        # 기본 설정
        self.default_travel_time = 30  # 기본 이동시간 (분)
        self.max_api_timeout = 15  # API 타임아웃 (초)
        
        logger.info(f"🚗 이동시간 계산기 초기화 (Google + 카카오)")
        logger.info(f"   Google Maps API: {'✅ 사용가능' if self.google_api_key else '❌ 키 없음'}")
        logger.info(f"   카카오 API: {'✅ 사용가능' if self.kakao_api_key else '❌ 키 없음'}")

    async def calculate_travel_time(self, origin: str, destination: str, mode: str = "transit") -> int:
        """
        두 위치 간 이동시간 계산 (분 단위)
        
        Args:
            origin: 출발지 주소
            destination: 도착지 주소  
            mode: 교통 수단 ("transit", "driving", "walking")
            
        Returns:
            이동시간 (분)
        """
        if not origin or not destination:
            logger.warning("출발지 또는 도착지가 없음")
            return self.default_travel_time
        
        if origin == destination:
            logger.info("출발지와 도착지가 동일")
            return 5  # 같은 장소 내 이동
        
        logger.info(f"🚗 이동시간 계산 시작: {origin} → {destination} ({mode})")
        
        # 1순위: Google Distance Matrix API (모든 교통수단 지원)
        google_time = await self._google_distance_matrix(origin, destination, mode)
        if google_time:
            logger.info(f"✅ Google API 결과: {google_time}분")
            return google_time
        
        # 2순위: 카카오 길찾기 API (자동차만 지원하지만 시도)
        if mode == "driving":
            kakao_time = await self._kakao_directions(origin, destination)
            if kakao_time:
                logger.info(f"✅ 카카오 API 결과: {kakao_time}분")
                return kakao_time
        
        # 3순위: 좌표 기반 직선거리 추정
        estimated_time = await self._estimate_by_coordinates(origin, destination, mode)
        if estimated_time:
            logger.info(f"✅ 좌표 추정 결과: {estimated_time}분")
            return estimated_time
        
        # 4순위: 하드코딩 매트릭스 (최후의 수단)
        fallback_time = self._fallback_hardcoded_matrix(origin, destination, mode)
        logger.warning(f"⚠️ 하드코딩 매트릭스 사용: {fallback_time}분")
        
        return fallback_time

    async def _google_distance_matrix(self, origin: str, destination: str, mode: str) -> Optional[int]:
        """Google Distance Matrix API 호출 - 모든 교통수단 지원"""
        if not self.google_api_key:
            logger.warning("Google API 키가 없음")
            return None
        
        try:
            # 교통수단 매핑
            travel_mode_map = {
                "transit": "transit",      # 대중교통
                "driving": "driving",      # 자동차
                "walking": "walking",      # 도보
                "bicycling": "bicycling"   # 자전거
            }
            
            travel_mode = travel_mode_map.get(mode, "transit")
            
            url = "https://maps.googleapis.com/maps/api/distancematrix/json"
            params = {
                "origins": origin,
                "destinations": destination,
                "mode": travel_mode,
                "language": "ko",
                "region": "kr",
                "key": self.google_api_key,
                "units": "metric"
            }
            
            # 대중교통인 경우 현재 시간 기준으로 검색
            if travel_mode == "transit":
                import time
                params["departure_time"] = int(time.time())
                # 대중교통 옵션 추가
                params["transit_mode"] = "bus|subway|train"  # 버스, 지하철, 기차
                params["transit_routing_preference"] = "less_walking"  # 적은 도보
            
            logger.info(f"🔍 Google Distance Matrix API 호출: {travel_mode} 모드")
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params, timeout=self.max_api_timeout) as response:
                    if response.status == 200:
                        data = await response.json()
                        
                        logger.info(f"   Google API 응답 상태: {data.get('status')}")
                        
                        if data.get("status") == "OK":
                            rows = data.get("rows", [])
                            if rows and rows[0].get("elements"):
                                element = rows[0]["elements"][0]
                                
                                logger.info(f"   요소 상태: {element.get('status')}")
                                
                                if element.get("status") == "OK":
                                    # 기본 소요시간
                                    duration = element.get("duration", {})
                                    duration_seconds = duration.get("value", 0)
                                    duration_minutes = max(1, round(duration_seconds / 60))
                                    
                                    # 교통체증 고려 시간 (있는 경우)
                                    if "duration_in_traffic" in element:
                                        traffic_duration = element["duration_in_traffic"]
                                        traffic_seconds = traffic_duration.get("value", 0)
                                        traffic_minutes = max(1, round(traffic_seconds / 60))
                                        
                                        logger.info(f"   기본 시간: {duration.get('text', 'N/A')} ({duration_minutes}분)")
                                        logger.info(f"   교통체증 고려: {traffic_duration.get('text', 'N/A')} ({traffic_minutes}분)")
                                        
                                        return traffic_minutes  # 교통체증 고려 시간 사용
                                    else:
                                        logger.info(f"   소요시간: {duration.get('text', 'N/A')} ({duration_minutes}분)")
                                        return duration_minutes
                                    
                                elif element.get("status") == "ZERO_RESULTS":
                                    logger.warning(f"   Google: 경로 없음 ({travel_mode})")
                                elif element.get("status") == "NOT_FOUND":
                                    logger.warning(f"   Google: 주소 찾을 수 없음")
                                else:
                                    logger.warning(f"   Google 요소 오류: {element.get('status')}")
                        elif data.get("status") == "ZERO_RESULTS":
                            logger.warning(f"   Google: 전체 결과 없음")
                        else:
                            logger.warning(f"   Google API 오류: {data.get('status')}")
                    else:
                        logger.warning(f"   Google HTTP 오류: {response.status}")
                        
        except asyncio.TimeoutError:
            logger.warning(f"   Google API 타임아웃 ({self.max_api_timeout}초)")
        except Exception as e:
            logger.error(f"❌ Google API 오류: {e}")
        
        return None

    async def _kakao_directions(self, origin: str, destination: str) -> Optional[int]:
        """카카오 길찾기 API 호출 - 자동차 경로만 지원"""
        if not self.kakao_api_key:
            logger.warning("카카오 API 키가 없음")
            return None
        
        try:
            # 1단계: 주소를 좌표로 변환
            origin_coords = await self._geocode_kakao(origin)
            dest_coords = await self._geocode_kakao(destination)
            
            if not (origin_coords and dest_coords):
                logger.warning("카카오용 좌표 변환 실패")
                return None
            
            # 2단계: 카카오모빌리티 길찾기 API
            url = "https://apis-navi.kakaomobility.com/v1/directions"
            headers = {
                "Authorization": f"KakaoAK {self.kakao_api_key}",
                "Content-Type": "application/json"
            }
            
            params = {
                "origin": f"{origin_coords['lng']},{origin_coords['lat']}",
                "destination": f"{dest_coords['lng']},{dest_coords['lat']}",
                "summary": "true"
            }
            
            logger.info(f"🚗 카카오 길찾기 API 호출")
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers, params=params, timeout=self.max_api_timeout) as response:
                    if response.status == 200:
                        data = await response.json()
                        
                        routes = data.get("routes", [])
                        if routes:
                            # 첫 번째 경로의 소요시간
                            first_route = routes[0]
                            summary = first_route.get("summary", {})
                            
                            duration_seconds = summary.get("duration", 0)
                            duration_minutes = max(1, round(duration_seconds / 60))
                            
                            distance_meters = summary.get("distance", 0)
                            distance_km = round(distance_meters / 1000, 1)
                            
                            logger.info(f"   카카오 결과: {duration_minutes}분, {distance_km}km")
                            return duration_minutes
                        else:
                            logger.warning("   카카오: 경로 없음")
                    elif response.status == 401:
                        logger.warning("   카카오: API 키 인증 실패")
                    else:
                        logger.warning(f"   카카오 HTTP 오류: {response.status}")
                        
        except asyncio.TimeoutError:
            logger.warning(f"   카카오 API 타임아웃 ({self.max_api_timeout}초)")
        except Exception as e:
            logger.error(f"❌ 카카오 API 오류: {e}")
        
        return None

    async def _geocode_kakao(self, address: str) -> Optional[Dict[str, float]]:
        """카카오 지오코딩으로 주소를 좌표로 변환"""
        if not self.kakao_api_key:
            return None
        
        try:
            url = "https://dapi.kakao.com/v2/local/search/address.json"
            headers = {"Authorization": f"KakaoAK {self.kakao_api_key}"}
            params = {"query": address}
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers, params=params, timeout=5) as response:
                    if response.status == 200:
                        data = await response.json()
                        
                        documents = data.get("documents", [])
                        if documents:
                            first_result = documents[0]
                            coords = {
                                "lat": float(first_result.get("y", 0)),
                                "lng": float(first_result.get("x", 0))
                            }
                            logger.info(f"   좌표 변환: {address} → {coords['lat']:.4f}, {coords['lng']:.4f}")
                            return coords
                        else:
                            # 키워드 검색으로 재시도
                            return await self._geocode_kakao_keyword(address)
                    else:
                        logger.warning(f"   카카오 지오코딩 오류: {response.status}")
                        
        except Exception as e:
            logger.error(f"❌ 카카오 지오코딩 오류: {e}")
        
        return None

    async def _geocode_kakao_keyword(self, keyword: str) -> Optional[Dict[str, float]]:
        """카카오 키워드 검색으로 좌표 획득"""
        try:
            url = "https://dapi.kakao.com/v2/local/search/keyword.json"
            headers = {"Authorization": f"KakaoAK {self.kakao_api_key}"}
            params = {"query": keyword, "size": 1}
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers, params=params, timeout=5) as response:
                    if response.status == 200:
                        data = await response.json()
                        
                        documents = data.get("documents", [])
                        if documents:
                            first_result = documents[0]
                            coords = {
                                "lat": float(first_result.get("y", 0)),
                                "lng": float(first_result.get("x", 0))
                            }
                            logger.info(f"   키워드 검색: {keyword} → {coords['lat']:.4f}, {coords['lng']:.4f}")
                            return coords
                        
        except Exception as e:
            logger.error(f"❌ 카카오 키워드 검색 오류: {e}")
        
        return None

    async def _estimate_by_coordinates(self, origin: str, destination: str, mode: str) -> Optional[int]:
        """좌표 기반 직선거리로 이동시간 추정"""
        try:
            origin_coords = await self._geocode_kakao(origin)
            dest_coords = await self._geocode_kakao(destination)
            
            if not (origin_coords and dest_coords):
                logger.warning("좌표 추정용 지오코딩 실패")
                return None
            
            # 직선거리 계산 (하버사인 공식)
            distance_km = self._haversine_distance(
                origin_coords["lat"], origin_coords["lng"],
                dest_coords["lat"], dest_coords["lng"]
            )
            
            # 교통수단별 속도 및 계수 (실제 경로는 직선거리보다 길다)
            if mode == "walking":
                speed_kmh = 4        # 도보 4km/h
                route_factor = 1.2   # 실제 경로는 1.2배
            elif mode == "driving":
                speed_kmh = 25       # 시내 운전 25km/h (신호, 정체 고려)
                route_factor = 1.4   # 실제 경로는 1.4배
            elif mode == "transit":
                speed_kmh = 20       # 대중교통 20km/h (환승, 대기시간 고려)
                route_factor = 1.3   # 실제 경로는 1.3배
            else:
                speed_kmh = 20       # 기본값
                route_factor = 1.3
            
            # 실제 이동거리 및 시간 계산
            actual_distance = distance_km * route_factor
            travel_time_hours = actual_distance / speed_kmh
            travel_time_minutes = max(5, round(travel_time_hours * 60))
            
            logger.info(f"   좌표 추정:")
            logger.info(f"     직선거리: {distance_km:.1f}km")
            logger.info(f"     실제거리: {actual_distance:.1f}km (×{route_factor})")
            logger.info(f"     평균속도: {speed_kmh}km/h ({mode})")
            logger.info(f"     예상시간: {travel_time_minutes}분")
            
            return travel_time_minutes
            
        except Exception as e:
            logger.error(f"❌ 좌표 추정 오류: {e}")
        
        return None

    def _haversine_distance(self, lat1: float, lng1: float, lat2: float, lng2: float) -> float:
        """하버사인 공식으로 두 좌표 간 직선거리 계산 (km)"""
        # 지구 반지름 (km)
        R = 6371.0
        
        # 라디안 변환
        lat1_rad = math.radians(lat1)
        lng1_rad = math.radians(lng1)
        lat2_rad = math.radians(lat2)
        lng2_rad = math.radians(lng2)
        
        # 차이 계산
        dlat = lat2_rad - lat1_rad
        dlng = lng2_rad - lng1_rad
        
        # 하버사인 공식
        a = math.sin(dlat/2)**2 + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(dlng/2)**2
        c = 2 * math.asin(math.sqrt(a))
        distance = R * c
        
        return distance

    def _fallback_hardcoded_matrix(self, origin: str, destination: str, mode: str) -> int:
        """하드코딩된 이동시간 매트릭스 (최후의 수단) - 교통수단별 차별화"""
        
        def extract_region_info(address: str) -> Dict[str, str]:
            """주소에서 지역 정보 추출"""
            # 광역시/도 매핑
            regions = {
                "서울": "서울특별시", "부산": "부산광역시", "대구": "대구광역시",
                "인천": "인천광역시", "광주": "광주광역시", "대전": "대전광역시",
                "울산": "울산광역시", "세종": "세종특별자치시"
            }
            
            # 서울 구 매핑
            seoul_districts = [
                "중구", "종로구", "서대문구", "마포구", "용산구", "성동구", 
                "광진구", "강동구", "송파구", "강남구", "서초구", "관악구",
                "영등포구", "구로구", "금천구", "양천구", "강서구", "은평구",
                "노원구", "도봉구", "강북구", "성북구", "동대문구", "중랑구", "동작구"
            ]
            
            result = {"region": "서울특별시", "district": "중구"}  # 기본값
            
            # 지역 찾기
            for short_name, full_name in regions.items():
                if short_name in address:
                    result["region"] = full_name
                    break
            
            # 구 찾기 (서울만)
            if result["region"] == "서울특별시":
                for district in seoul_districts:
                    if district in address:
                        result["district"] = district
                        break
            
            return result
        
        origin_info = extract_region_info(origin)
        dest_info = extract_region_info(destination)
        
        logger.info(f"   하드코딩 매트릭스 사용:")
        logger.info(f"     출발: {origin_info}")
        logger.info(f"     도착: {dest_info}")
        logger.info(f"     교통수단: {mode}")
        
        # 교통수단별 기본 시간 계수
        mode_multiplier = {
            "walking": 2.5,    # 도보는 2.5배 더 오래 걸림
            "driving": 1.0,    # 기준
            "transit": 1.3,    # 대중교통은 1.3배
            "bicycling": 0.6   # 자전거는 0.6배
        }.get(mode, 1.0)
        
        # 같은 지역 내 이동
        if origin_info["region"] == dest_info["region"]:
            if origin_info["region"] == "서울특별시":
                # 서울 내 구간별 이동시간 (자동차 기준)
                seoul_matrix = {
                    # 같은 구
                    ("중구", "중구"): 10, ("강남구", "강남구"): 10, ("영등포구", "영등포구"): 10,
                    
                    # 중심부 간 이동
                    ("중구", "종로구"): 15, ("중구", "서대문구"): 20, ("중구", "마포구"): 25,
                    ("중구", "용산구"): 15, ("중구", "성동구"): 20,
                    
                    # 중심부 ↔ 강남권
                    ("중구", "강남구"): 30, ("중구", "서초구"): 35, ("중구", "송파구"): 40,
                    
                    # 중심부 ↔ 외곽
                    ("중구", "강동구"): 45, ("중구", "강서구"): 40, ("중구", "은평구"): 35,
                    
                    # 영등포권
                    ("영등포구", "중구"): 20, ("영등포구", "강남구"): 25, 
                    ("영등포구", "강동구"): 50, ("영등포구", "마포구"): 20,
                    
                    # 강남권 내부
                    ("강남구", "서초구"): 15, ("강남구", "송파구"): 20,
                }
                
                # 양방향 검색
                base_time = (seoul_matrix.get((origin_info["district"], dest_info["district"])) or 
                           seoul_matrix.get((dest_info["district"], origin_info["district"])) or 30)
            else:
                # 다른 광역시 내 이동
                base_time = 25
        else:
            # 광역시 간 이동
            intercity_matrix = {
                ("서울특별시", "인천광역시"): 60,
                ("서울특별시", "대전광역시"): 180,
                ("서울특별시", "부산광역시"): 300,
                ("서울특별시", "대구광역시"): 240,
                ("부산광역시", "울산광역시"): 60,
                ("대구광역시", "부산광역시"): 120,
            }
            
            base_time = (intercity_matrix.get((origin_info["region"], dest_info["region"])) or
                        intercity_matrix.get((dest_info["region"], origin_info["region"])) or 120)
        
        # 교통수단별 시간 조정
        final_time = max(5, round(base_time * mode_multiplier))
        
        logger.info(f"     기본시간: {base_time}분")
        logger.info(f"     교통수단 계수: ×{mode_multiplier}")
        logger.info(f"     최종시간: {final_time}분")
        
        return final_time

# 전역 인스턴스 생성
travel_calculator = TravelTimeCalculator()

async def calculate_travel_time(location1: str, location2: str, mode: str = "transit") -> int:
    """
    두 위치 간 예상 이동 시간 계산 (분) - Google + 카카오 API 활용
    
    Args:
        location1: 출발지 주소
        location2: 도착지 주소
        mode: 교통수단 ("transit", "driving", "walking", "bicycling")
    
    Returns:
        이동시간 (분)
    """
    return await travel_calculator.calculate_travel_time(location1, location2, mode)

def calculate_travel_time_sync(location1: str, location2: str, mode: str = "transit") -> int:
    """동기 버전 이동시간 계산 - 이벤트 루프 오류 해결"""
    if not location1 or not location2:
        logger.warning("출발지 또는 도착지가 없음")
        return travel_calculator.default_travel_time
    
    if location1 == location2:
        logger.info("출발지와 도착지가 동일")
        return 5
    
    logger.info(f"🚗 동기 이동시간 계산: {location1} → {location2} ({mode})")
    
    try:
        # 🔥 방법 1: 새 이벤트 루프 생성하여 실행
        import asyncio
        import threading
        
        # 현재 스레드에 루프가 있는지 확인
        try:
            current_loop = asyncio.get_running_loop()
            logger.info("   기존 실행 중인 루프 감지됨")
            
            # 🔥 새 스레드에서 실행
            result_container = {"result": None, "error": None}
            
            def run_in_new_thread():
                try:
                    new_loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(new_loop)
                    try:
                        result = new_loop.run_until_complete(
                            travel_calculator.calculate_travel_time(location1, location2, mode)
                        )
                        result_container["result"] = result
                    finally:
                        new_loop.close()
                except Exception as e:
                    result_container["error"] = e
            
            thread = threading.Thread(target=run_in_new_thread)
            thread.start()
            thread.join(timeout=20)  # 20초 타임아웃
            
            if result_container["error"]:
                raise result_container["error"]
            elif result_container["result"] is not None:
                logger.info(f"   ✅ 새 스레드에서 계산 성공: {result_container['result']}분")
                return result_container["result"]
            else:
                logger.warning("   ⚠️ 스레드 타임아웃")
                
        except RuntimeError:
            # 실행 중인 루프가 없는 경우
            logger.info("   실행 중인 루프 없음, 새 루프 생성")
            
            # 🔥 방법 2: 새 루프 직접 생성
            new_loop = asyncio.new_event_loop()
            asyncio.set_event_loop(new_loop)
            
            try:
                result = new_loop.run_until_complete(
                    travel_calculator.calculate_travel_time(location1, location2, mode)
                )
                logger.info(f"   ✅ 새 루프에서 계산 성공: {result}분")
                return result
            finally:
                new_loop.close()
                
    except Exception as e:
        logger.error(f"❌ 이동시간 계산 오류: {e}")
        
        # 🔥 방법 3: 하드코딩 매트릭스 직접 사용 (최후의 수단)
        logger.info("   API 실패, 하드코딩 매트릭스 사용")
        return travel_calculator._fallback_hardcoded_matrix(location1, location2, mode)


# 환경변수 설정 가이드를 위한 함수
def setup_travel_api_keys():
    """교통 API 키 설정 가이드"""
    logger.info("🔧 교통 API 설정 가이드:")
    logger.info("   1. Google Maps API:")
    logger.info("      - https://console.cloud.google.com/")
    logger.info("      - Distance Matrix API 활성화")
    logger.info("      - 환경변수: GOOGLE_MAPS_API_KEY")
    logger.info("   2. 카카오 REST API:")
    logger.info("      - https://developers.kakao.com/")
    logger.info("      - 환경변수: KAKAO_REST_API_KEY")

# 기존 함수명 호환성 유지
def detect_and_resolve_time_conflicts(schedules: Dict[str, Any], min_gap_minutes=15) -> Dict[str, Any]:
    """
    개선된 일정 간 시간 충돌 감지 및 해결 함수.
    Google + 카카오 API를 활용하여 실제 이동시간을 고려한 충돌 해결.
    """
    logger.info("🚗 Google + 카카오 API 기반 충돌 해결 시작")
    
    # 모든 시간 지정 일정 수집
    all_timed_schedules = []
    for schedule in schedules.get("fixedSchedules", []):
        if "startTime" in schedule and "endTime" in schedule:
            all_timed_schedules.append(schedule)
    
    for schedule in schedules.get("flexibleSchedules", []):
        if "startTime" in schedule and "endTime" in schedule:
            all_timed_schedules.append(schedule)
    
    if len(all_timed_schedules) < 2:
        logger.info("충돌 검사할 일정이 2개 미만")
        return schedules
    
    # 우선순위 및 시간순 정렬
    all_timed_schedules.sort(key=lambda s: (s.get("priority", 999), parse_datetime(s.get("startTime", ""))))
    logger.info(f"정렬된 일정 {len(all_timed_schedules)}개")
    
    # 🔥 실제 이동시간 고려 충돌 해결
    adjusted_count = 0
    
    for i in range(len(all_timed_schedules) - 1):
        current = all_timed_schedules[i]
        next_schedule = all_timed_schedules[i + 1]
        
        current_end = parse_datetime(current.get("endTime", ""))
        next_start = parse_datetime(next_schedule.get("startTime", ""))
        
        if not (current_end and next_start):
            continue
        
        # 🔥 실제 이동 시간 계산 (동기 버전 사용)
        required_travel_time = calculate_travel_time_sync(
            current.get("location", ""),
            next_schedule.get("location", ""),
            "transit"  # 기본적으로 대중교통 기준
        )
        
        current_gap = int((next_start - current_end).total_seconds() / 60)
        
        logger.info(f"이동 시간 검사:")
        logger.info(f"  {current.get('name')} → {next_schedule.get('name')}")
        logger.info(f"  위치: {current.get('location', 'N/A')} → {next_schedule.get('location', 'N/A')}")
        logger.info(f"  필요 시간: {required_travel_time}분, 현재 간격: {current_gap}분")
        
        # 🔥 이동 시간이 부족하면 조정
        if current_gap < required_travel_time:
            logger.info(f"⚠️ 이동 시간 부족! {current_gap}분 → {required_travel_time}분 조정 필요")
            
            # 다음 일정을 이동 시간만큼 뒤로 이동 (10분 여유 추가)
            buffer_time = 10
            new_start = current_end + datetime.timedelta(minutes=required_travel_time + buffer_time)
            
            # 기존 일정 지속시간 유지
            old_start = next_start
            old_end = parse_datetime(next_schedule.get("endTime", ""))
            if old_end:
                duration = int((old_end - old_start).total_seconds() / 60)
                new_end = new_start + datetime.timedelta(minutes=duration)
            else:
                new_end = new_start + datetime.timedelta(minutes=60)  # 기본 1시간
            
            # 시간 업데이트
            next_schedule["startTime"] = new_start.isoformat()
            next_schedule["endTime"] = new_end.isoformat()
            
            logger.info(f"✅ 조정 완료: {old_start.strftime('%H:%M')} → {new_start.strftime('%H:%M')}")
            logger.info(f"   이동시간: {required_travel_time}분 + 여유시간: {buffer_time}분 = 총 {required_travel_time + buffer_time}분")
            
            adjusted_count += 1
        else:
            logger.info(f"✅ 이동 시간 충분: {current_gap}분 >= {required_travel_time}분")
    
    logger.info(f"🎯 Google + 카카오 API 기반 충돌 해결 완료: {adjusted_count}개 일정 조정")
    
    # 최종 일정 타입별 재분류
    fixed_schedules = [s for s in all_timed_schedules if s.get("type") == "FIXED"]
    flexible_schedules = []
    
    # 기존 유연 일정 중 시간이 없는 일정 보존
    for s in schedules.get("flexibleSchedules", []):
        if "startTime" not in s or "endTime" not in s:
            flexible_schedules.append(s)
        elif s.get("type") != "FIXED":
            flexible_schedules.append(s)
    
    logger.info(f"최종 분류: 고정 일정 {len(fixed_schedules)}개, 유연 일정 {len(flexible_schedules)}개")
    
    # 최종 일정 로깅
    logger.info("🕐 최종 일정 순서:")
    for i, schedule in enumerate(fixed_schedules):
        start_time = parse_datetime(schedule.get("startTime", ""))
        end_time = parse_datetime(schedule.get("endTime", ""))
        location = schedule.get("location", "위치 없음")
        logger.info(f"  {i+1}. {schedule.get('name')}")
        logger.info(f"     ⏰ {start_time.strftime('%H:%M') if start_time else 'N/A'} ~ {end_time.strftime('%H:%M') if end_time else 'N/A'}")
        logger.info(f"     📍 {location}")
        
        # 다음 일정과의 이동시간 표시
        if i < len(fixed_schedules) - 1:
            next_schedule = fixed_schedules[i + 1]
            travel_time = calculate_travel_time_sync(
                schedule.get("location", ""),
                next_schedule.get("location", ""),
                "transit"
            )
            logger.info(f"     🚗 다음 일정까지 이동시간: {travel_time}분")
    
    # 결과 반환
    result = schedules.copy()
    result["fixedSchedules"] = fixed_schedules
    result["flexibleSchedules"] = flexible_schedules
    
    return result