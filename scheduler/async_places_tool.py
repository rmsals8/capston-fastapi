# scheduler/async_places_tool.py
import asyncio
import httpx
import logging
from typing import Optional, Dict, List, Any, Tuple
from .cache_manager import cached_method
import os

logger = logging.getLogger('async_places_tool')

class AsyncGooglePlacesTool:
    """비동기 Google Places API 도구"""
    
    def __init__(self, api_key=None):
        self.api_key = api_key or os.getenv("GOOGLE_MAPS_API_KEY")
        if not self.api_key:
            raise ValueError("Google Maps API 키가 필요합니다.")
        
        # HTTP 클라이언트 설정
        self.client = httpx.AsyncClient(
            timeout=httpx.Timeout(10.0),
            limits=httpx.Limits(max_connections=20, max_keepalive_connections=5)
        )
    
    async def __aenter__(self):
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.client.aclose()
    
    @cached_method("places_search", expire_seconds=3600)
    async def search_place_optimized(self, query: str, place_type: str = None, region: str = None) -> Optional[Dict]:
        """최적화된 장소 검색 - 스마트 전략 사용"""
        
        # 1단계: 가장 성공률 높은 방법부터 시도
        search_strategies = self._get_search_strategies(query, place_type, region)
        
        for strategy in search_strategies:
            try:
                result = await self._execute_search_strategy(strategy)
                if result:
                    logger.debug(f"검색 성공 ({strategy['name']}): {query}")
                    return result
            except Exception as e:
                logger.warning(f"검색 전략 실패 ({strategy['name']}): {str(e)}")
                continue
        
        logger.warning(f"모든 검색 전략 실패: {query}")
        return None
    
    def _get_search_strategies(self, query: str, place_type: str = None, region: str = None) -> List[Dict]:
        """검색 전략을 성공률 순으로 정렬하여 반환"""
        strategies = []
        
        # 전략 1: 정확한 이름 + 지역 검색 (성공률 높음)
        if region and region not in query.lower():
            strategies.append({
                "name": "exact_with_region",
                "query": f"{query} {region}",
                "place_type": place_type,
                "method": "findplacefromtext"
            })
        
        # 전략 2: 원본 쿼리 검색
        strategies.append({
            "name": "original_query",
            "query": query,
            "place_type": place_type,
            "method": "findplacefromtext"
        })
        
        # 전략 3: 유형 기반 검색 (place_type이 있는 경우)
        if place_type:
            strategies.append({
                "name": "type_based",
                "query": query,
                "place_type": place_type,
                "method": "findplacefromtext"
            })
        
        return strategies
    
    async def _execute_search_strategy(self, strategy: Dict) -> Optional[Dict]:
        """검색 전략 실행"""
        if strategy["method"] == "findplacefromtext":
            return await self._find_place_from_text(
                strategy["query"], 
                strategy.get("place_type")
            )
        elif strategy["method"] == "nearby":
            return await self._nearby_search(
                strategy["query"],
                strategy.get("location"),
                strategy.get("radius", 1000),
                strategy.get("place_type")
            )
        
        return None
    
    async def _find_place_from_text(self, query: str, place_type: str = None) -> Optional[Dict]:
        """Find Place From Text API 호출"""
        fields = "name,formatted_address,geometry,place_id,types,address_components"
        
        params = {
            "input": query,
            "inputtype": "textquery",
            "fields": fields,
            "language": "ko",
            "key": self.api_key
        }
        
        if place_type:
            params["locationbias"] = f"type:{place_type}"
        
        url = "https://maps.googleapis.com/maps/api/place/findplacefromtext/json"
        
        try:
            response = await self.client.get(url, params=params)
            response.raise_for_status()
            
            data = response.json()
            
            if data.get('status') == 'OK' and data.get('candidates'):
                candidate = data['candidates'][0]
                return self._format_place_data(candidate)
            
        except Exception as e:
            logger.error(f"Find Place API 호출 실패: {str(e)}")
        
        return None
    
    async def _nearby_search(self, query: str, location: str, radius: int, place_type: str = None) -> Optional[Dict]:
        """Nearby Search API 호출"""
        params = {
            "location": location,
            "radius": radius,
            "keyword": query,
            "language": "ko",
            "key": self.api_key
        }
        
        if place_type:
            params["type"] = place_type
        
        url = "https://maps.googleapis.com/maps/api/place/nearbysearch/json"
        
        try:
            response = await self.client.get(url, params=params)
            response.raise_for_status()
            
            data = response.json()
            
            if data.get('status') == 'OK' and data.get('results'):
                result = data['results'][0]
                return self._format_place_data(result)
                
        except Exception as e:
            logger.error(f"Nearby Search API 호출 실패: {str(e)}")
        
        return None
    
    def _format_place_data(self, place_data: Dict) -> Dict:
        """장소 데이터 포맷팅"""
        return {
            'name': place_data.get('name', ''),
            'formatted_address': place_data.get('formatted_address', place_data.get('vicinity', '')),
            'latitude': place_data['geometry']['location']['lat'],
            'longitude': place_data['geometry']['location']['lng'],
            'place_id': place_data.get('place_id', ''),
            'types': place_data.get('types', [])
        }
    
    @cached_method("places_batch", expire_seconds=3600)
    async def search_places_batch(self, queries: List[Dict]) -> List[Optional[Dict]]:
        """여러 장소를 배치로 검색"""
        tasks = []
        
        for query_info in queries:
            task = self.search_place_optimized(
                query_info.get('query', ''),
                query_info.get('place_type'),
                query_info.get('region')
            )
            tasks.append(task)
        
        # 동시 실행 (최대 5개씩 배치)
        results = []
        batch_size = 5
        
        for i in range(0, len(tasks), batch_size):
            batch = tasks[i:i + batch_size]
            batch_results = await asyncio.gather(*batch, return_exceptions=True)
            
            # 예외 처리
            for result in batch_results:
                if isinstance(result, Exception):
                    logger.error(f"배치 검색 오류: {str(result)}")
                    results.append(None)
                else:
                    results.append(result)
        
        return results

class AsyncGoogleDirectionsTool:
    """비동기 Google Directions API 도구"""
    
    def __init__(self, api_key=None):
        self.api_key = api_key or os.getenv("GOOGLE_MAPS_API_KEY")
        if not self.api_key:
            raise ValueError("Google Maps API 키가 필요합니다.")
        
        self.client = httpx.AsyncClient(
            timeout=httpx.Timeout(15.0),
            limits=httpx.Limits(max_connections=10, max_keepalive_connections=3)
        )
    
    async def __aenter__(self):
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.client.aclose()
    
    @cached_method("directions", expire_seconds=1800)
    async def get_directions_batch(self, route_requests: List[Dict]) -> List[Optional[Dict]]:
        """여러 경로를 배치로 계산"""
        tasks = []
        
        for request in route_requests:
            task = self._get_single_direction(
                request['origin_lat'],
                request['origin_lng'],
                request['dest_lat'],
                request['dest_lng'],
                request.get('departure_time')
            )
            tasks.append(task)
        
        # 동시 실행 (최대 3개씩 - Directions API는 더 무거움)
        results = []
        batch_size = 3
        
        for i in range(0, len(tasks), batch_size):
            batch = tasks[i:i + batch_size]
            batch_results = await asyncio.gather(*batch, return_exceptions=True)
            
            for result in batch_results:
                if isinstance(result, Exception):
                    logger.error(f"경로 계산 오류: {str(result)}")
                    results.append(None)
                else:
                    results.append(result)
        
        return results
    
    async def _get_single_direction(self, origin_lat: float, origin_lng: float, 
                                  dest_lat: float, dest_lng: float, 
                                  departure_time: str = None) -> Optional[Dict]:
        """단일 경로 계산"""
        params = {
            "origin": f"{origin_lat},{origin_lng}",
            "destination": f"{dest_lat},{dest_lng}",
            "key": self.api_key,
            "mode": "driving",
            "units": "metric",
            "language": "ko"
        }
        
        if departure_time:
            params["departure_time"] = departure_time
        
        url = "https://maps.googleapis.com/maps/api/directions/json"
        
        try:
            response = await self.client.get(url, params=params)
            response.raise_for_status()
            
            data = response.json()
            
            if data.get("status") == "OK" and data.get("routes"):
                route = data["routes"][0]
                leg = route["legs"][0]
                
                return {
                    "distance": leg["distance"]["value"] / 1000,  # km
                    "duration": leg["duration"]["value"],  # 초
                    "duration_in_traffic": leg.get("duration_in_traffic", {}).get("value", leg["duration"]["value"]),
                    "traffic_rate": leg.get("duration_in_traffic", {}).get("value", leg["duration"]["value"]) / leg["duration"]["value"],
                    "overview_polyline": route.get("overview_polyline", {}).get("points", ""),
                    "start_address": leg.get("start_address", ""),
                    "end_address": leg.get("end_address", "")
                }
                
        except Exception as e:
            logger.error(f"Directions API 호출 실패: {str(e)}")
        
        return None