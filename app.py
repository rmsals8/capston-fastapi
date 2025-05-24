import logging
import asyncio
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
import datetime
from dotenv import load_dotenv
from geopy.distance import geodesic
import math
import random
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
from scheduler.async_places_tool import AsyncGooglePlacesTool, AsyncGoogleDirectionsTool
from scheduler.cache_manager import cache_manager, cached_result
from scheduler.performance_config import perf_config

# 환경 변수 로드
load_dotenv()

# 성능 설정 적용
perf_config.configure_logging()

# API 키 설정
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY") 
GOOGLE_MAPS_API_KEY = os.getenv("GOOGLE_MAPS_API_KEY")

# FastAPI 앱 초기화
app = FastAPI(title="일정 추출 및 위치 정보 보강 API", 
              description="음성 입력에서 일정을 추출하고 위치 정보를 보강하는 API",
              version="2.0.0")

# CORS 미들웨어 설정
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ----- 모델 정의 -----
class ScheduleRequest(BaseModel):
    voice_input: str

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

class OptimizeScheduleRequest(BaseModel):
    fixedSchedules: List[FixedSchedule] = []
    flexibleSchedules: List[FlexibleSchedule] = []

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

# ----- 유틸리티 함수 (최적화됨) -----

@lru_cache(maxsize=1000)
def calculate_distance(lat1, lon1, lat2, lon2):
    """두 좌표 사이의 거리를 킬로미터 단위로 계산 (캐시됨)"""
    try:
        return geodesic((lat1, lon1), (lat2, lon2)).kilometers
    except:
        return math.sqrt((lat1 - lat2)**2 + (lon1 - lon2)**2) * 111

@lru_cache(maxsize=500)
def calculate_travel_time(distance):
    """거리를 기반으로 이동 시간을 초 단위로 계산 (캐시됨)"""
    average_speed_km_per_h = 30
    hours = distance / average_speed_km_per_h
    return int(hours * 3600)

@lru_cache(maxsize=100)
def get_place_category(place_name):
    """장소 이름에서 카테고리 유추 (캐시됨)"""
    name_lower = place_name.lower()
    
    if any(word in name_lower for word in ["식당", "음식", "레스토랑", "맛집"]):
        return "식당,음식점"
    elif any(word in name_lower for word in ["카페", "커피", "북카페"]):
        return "카페,디저트"
    elif any(word in name_lower for word in ["경기장", "스타디움", "월드컵"]):
        return "스포츠,오락>월드컵경기장"
    elif any(word in name_lower for word in ["대학", "캠퍼스"]):
        return "교육,학문>대학교"
    elif any(word in name_lower for word in ["도서관", "책"]):
        return "Library"
    elif any(word in name_lower for word in ["쇼핑", "마트", "백화점", "몰"]):
        return "쇼핑,마트"
    elif any(word in name_lower for word in ["공원", "정원"]):
        return "공원"
    else:
        return "기타"

@lru_cache(maxsize=100)
def generate_operating_hours(place_name):
    """장소 유형에 따른 예상 영업시간 생성 (캐시됨)"""
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
    """안전하게 JSON을 파싱하고, 필요한 경우 수정합니다."""
    try:
        return json.loads(json_str)
    except json.JSONDecodeError as e:
        # 따옴표 문제 수정 시도
        fixed_str = json_str
        fixed_str = re.sub(r'(\d+)-(\d+)-"(\d+)T(\d+):(\d+):(\d+)"', r'\1-\2-\3T\4:\5:\6', fixed_str)
        fixed_str = re.sub(r'(\d+)-(\d+)-(\d+)T"(\d+)":"(\d+)":"(\d+)"', r'\1-\2-\3T\4:\5:\6', fixed_str)
        fixed_str = re.sub(r',\s*}', '}', fixed_str)
        fixed_str = re.sub(r',\s*]', ']', fixed_str)
        
        try:
            return json.loads(fixed_str)
        except json.JSONDecodeError:
            return {"fixedSchedules": [], "flexibleSchedules": []}

def format_duration(minutes):
    """분 단위 시간을 PT1H 형식으로 변환"""
    hours = minutes // 60
    minutes = minutes % 60
    
    if minutes > 0:
        return f"PT{hours}H{minutes}M"
    else:
        return f"PT{hours}H"

# ----- 비즈니스 로직 함수 (최적화됨) -----

@cached_result("schedule_chain", expire_seconds=1800)
def create_schedule_chain():
    """LangChain을 사용한 일정 추출 체인 생성 (캐시됨)"""
    current_time = int(datetime.datetime.now().timestamp() * 1000)
    current_time_plus = current_time + 1
    current_time_plus_2 = current_time + 2
    current_time_plus_3 = current_time + 3
    
    today = datetime.datetime.now()
    tomorrow = today + datetime.timedelta(days=1)
    day_after_tomorrow = today + datetime.timedelta(days=2)
    next_week = today + datetime.timedelta(days=7)
    
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
    
    llm_config = perf_config.get_llm_config()
    llm = ChatOpenAI(
        openai_api_key=OPENAI_API_KEY,
        **llm_config
    )
    
    parser = JsonOutputParser()
    chain = prompt | llm | parser
    
    return chain

async def enhance_location_data_async(schedule_data: Dict) -> Dict:
    """비동기 위치 정보 보강 (대폭 최적화됨)"""
    logger = logging.getLogger('async_location_enhancer')
    if perf_config.environment != "production":
        logger.info("비동기 위치 정보 보강 시작...")
    
    enhanced_data = json.loads(json.dumps(schedule_data))
    
    # 모든 검색 쿼리를 미리 준비
    search_queries = []
    schedule_map = {}
    
    # 고정 일정 처리
    for schedule in enhanced_data.get("fixedSchedules", []):
        place_name = schedule.get("name", "")
        if place_name:
            query_info = {
                "query": place_name,
                "place_type": get_place_type_optimized(place_name),
                "region": extract_region_from_schedule(schedule)
            }
            search_queries.append(query_info)
            schedule_map[len(search_queries) - 1] = ("fixed", schedule)
    
    # 유연 일정 처리
    for schedule in enhanced_data.get("flexibleSchedules", []):
        category = schedule.get("name", "")
        if category:
            query_info = {
                "query": category,
                "place_type": get_place_type_optimized(category),
                "region": extract_region_from_schedule(schedule)
            }
            search_queries.append(query_info)
            schedule_map[len(search_queries) - 1] = ("flexible", schedule)
    
    # 배치 검색 실행
    async with AsyncGooglePlacesTool() as places_tool:
        search_results = await places_tool.search_places_batch(search_queries)
    
    # 결과 적용
    for i, result in enumerate(search_results):
        if i in schedule_map and result:
            schedule_type, schedule = schedule_map[i]
            
            # 주소 업데이트
            if result.get("formatted_address"):
                schedule["location"] = result["formatted_address"]
            
            # 좌표 업데이트
            if result.get("latitude") and result.get("longitude"):
                schedule["latitude"] = result["latitude"]
                schedule["longitude"] = result["longitude"]
            
            # 유연 일정의 경우 이름 업데이트
            if schedule_type == "flexible":
                original_name = schedule.get("name", "")
                schedule["name"] = f"{original_name} - {result.get('name', '')}"
    
    if perf_config.environment != "production":
        logger.info("비동기 위치 정보 보강 완료")
    
    return enhanced_data

@lru_cache(maxsize=500)
def get_place_type_optimized(place_name: str) -> Optional[str]:
    """최적화된 장소 유형 추론 (캐시됨)"""
    if not place_name:
        return None
    
    place_name_lower = place_name.lower()
    
    # 주요 패턴만 체크 (성능 최적화)
    patterns = [
        (["식당", "음식", "맛집", "레스토랑"], "restaurant"),
        (["카페", "커피"], "cafe"),
        (["대학교", "대학"], "university"),
        (["경기장", "스타디움"], "stadium"),
        (["마트", "슈퍼"], "supermarket"),
        (["병원", "의원"], "hospital"),
        (["공원"], "park"),
        (["호텔", "숙박"], "lodging"),
        (["은행"], "bank")
    ]
    
    for keywords, place_type in patterns:
        if any(keyword in place_name_lower for keyword in keywords):
            return place_type
    
    return "point_of_interest"

def extract_region_from_schedule(schedule: Dict) -> Optional[str]:
    """일정에서 지역 정보 추출"""
    location = schedule.get("location", "")
    name = schedule.get("name", "")
    
    major_regions = ["서울", "부산", "대구", "인천", "광주", "대전", "울산"]
    
    for region in major_regions:
        if region in location or region in name:
            return region
    
    return None

async def calculate_routes_async(schedules: List[Dict]) -> List[Dict]:
    """비동기 경로 계산 (배치 처리)"""
    if len(schedules) < 2:
        return []
    
    route_requests = []
    for i in range(len(schedules) - 1):
        from_schedule = schedules[i]
        to_schedule = schedules[i + 1]
        
        route_requests.append({
            "origin_lat": from_schedule["latitude"],
            "origin_lng": from_schedule["longitude"],
            "dest_lat": to_schedule["latitude"],
            "dest_lng": to_schedule["longitude"],
            "departure_time": from_schedule.get("end_time", "").isoformat() if hasattr(from_schedule.get("end_time", ""), "isoformat") else from_schedule.get("end_time", "")
        })
    
    async with AsyncGoogleDirectionsTool() as directions_tool:
        route_results = await directions_tool.get_directions_batch(route_requests)
    
    # 결과 포맷팅
    route_segments = []
    for i, result in enumerate(route_results):
        from_schedule = schedules[i]
        to_schedule = schedules[i + 1]
        
        if result:
            route_segments.append({
                "fromLocation": from_schedule["name"],
                "toLocation": to_schedule["name"],
                "distance": result["distance"],
                "estimatedTime": result["duration"],
                "trafficRate": result.get("traffic_rate", 1.0),
                "recommendedRoute": None,
                "realTimeTraffic": True
            })
        else:
            # 폴백: 직선 거리 계산
            distance = calculate_distance(
                from_schedule["latitude"], from_schedule["longitude"],
                to_schedule["latitude"], to_schedule["longitude"]
            )
            route_segments.append({
                "fromLocation": from_schedule["name"],
                "toLocation": to_schedule["name"],
                "distance": distance,
                "estimatedTime": calculate_travel_time(distance),
                "trafficRate": 1.0,
                "recommendedRoute": None,
                "realTimeTraffic": False
            })
    
    return route_segments

def merge_schedule_data(time_priority_data: Dict, location_data: Dict) -> Dict:
    """시간/우선순위 데이터와 위치 데이터를 병합"""
    result = time_priority_data.copy()
    
    # 위치 정보만 업데이트
    for schedule_type in ["fixedSchedules", "flexibleSchedules"]:
        time_schedules = {s.get("id"): s for s in result.get(schedule_type, [])}
        location_schedules = {s.get("id"): s for s in location_data.get(schedule_type, [])}
        
        for schedule_id, location_schedule in location_schedules.items():
            if schedule_id in time_schedules:
                # 위치 정보만 업데이트
                time_schedules[schedule_id]["location"] = location_schedule.get("location", "")
                time_schedules[schedule_id]["latitude"] = location_schedule.get("latitude", 37.5665)
                time_schedules[schedule_id]["longitude"] = location_schedule.get("longitude", 126.9780)
                
                # 유연 일정의 경우 이름도 업데이트 (장소명 포함)
                if schedule_type == "flexibleSchedules" and " - " in location_schedule.get("name", ""):
                    time_schedules[schedule_id]["name"] = location_schedule.get("name", "")
    
    return result

async def generate_schedule_analysis(schedule: Dict) -> Dict:
    """개별 일정에 대한 분석 정보 생성 (비동기)"""
    # 장소 카테고리 유추
    category = get_place_category(schedule["name"])
    
    # 영업 시간 유추
    operating_hours = generate_operating_hours(schedule["name"])
    
    # 영업 여부 확인
    is_open = check_place_open(operating_hours, schedule["start_time"])
    
    # 혼잡도 임의 생성
    crowd_level = round(random.uniform(0.3, 0.7), 1)
    
    # 추천 정보 생성
    crowd_level_status = "보통"
    if crowd_level < 0.4:
        crowd_level_status = "여유"
    elif crowd_level > 0.6:
        crowd_level_status = "혼잡"
    
    best_visit_time = f"영업시간({operating_hours['open']}-{operating_hours['close']}) 중 방문 권장"
    estimated_duration = f"{schedule['duration'] // 60:02d}:{schedule['duration'] % 60:02d}"
    
    # 장소명 추출
    place_name = schedule['name'].split(' - ')[0] if ' - ' in schedule['name'] else schedule['name']
    
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
    
    return {
        "locationName": schedule["name"],
        "bestTimeWindow": None,
        "crowdLevel": crowd_level,
        "placeDetails": place_details,
        "optimizationFactors": None,
        "visitRecommendation": None
    }

# ----- 엔드포인트 정의 -----

@app.get("/")
async def root():
    return {"message": "일정 추출 및 최적화 API가 실행 중입니다. POST /extract-schedule 또는 POST /api/v1/schedules/optimize-1 엔드포인트를 사용하세요."}

@app.post("/extract-schedule", response_model=ExtractScheduleResponse)
async def extract_schedule(request: ScheduleRequest):
    """음성 입력에서 일정을 추출하고 위치 정보를 보강합니다. (최적화됨)"""
    logger = logging.getLogger('extract_schedule_optimized')
    
    try:
        if perf_config.environment != "production":
            logger.info(f"일정 추출 요청: 입력 길이={len(request.voice_input)}")
        
        # 1. LangChain을 사용한 일정 추출
        chain = create_schedule_chain()
        result = chain.invoke({"input": request.voice_input})
        
        # 2. 결과 처리
        if isinstance(result, str):
            json_match = re.search(r'({[\s\S]*})', result)
            if json_match:
                schedule_data = safe_parse_json(json_match.group(1))
            else:
                schedule_data = safe_parse_json(result)
        else:
            schedule_data = result
        
        # 3. 비동기 처리를 위한 태스크 생성
        async def process_enhancements():
            tasks = []
            
            # 3.1 위치 정보 보강 (비동기)
            location_task = enhance_location_data_async(schedule_data)
            tasks.append(location_task)
            
            # 3.2 시간 및 우선순위 강화 (동기 - 빠름)
            try:
                # 간단한 작업인지 확인
                total_schedules = len(schedule_data.get("fixedSchedules", [])) + len(schedule_data.get("flexibleSchedules", []))
                
                if perf_config.should_skip_llm("minimal_schedules" if total_schedules <= 2 else "complex_schedules"):
                    # LLM 생략하고 기본 처리만
                    final_enhanced = schedule_data
                else:
                    # LLM 체인 사용
                    enhancement_chains = create_enhancement_chain()
                    time_chain = enhancement_chains["time_chain"]
                    priority_chain = enhancement_chains["priority_chain"]
                    
                    # 시간 추론
                    schedule_with_time = apply_time_inference(time_chain, request.voice_input, schedule_data)
                    
                    # 시간 충돌 해결
                    schedule_without_conflicts = detect_and_resolve_time_conflicts(schedule_with_time, min_gap_minutes=15)
                    
                    # 우선순위 분석
                    enhanced_schedule = apply_priorities(priority_chain, request.voice_input, schedule_without_conflicts)
                    
                    # 관계 분석
                    final_enhanced = enhance_schedule_with_relationships(request.voice_input, enhanced_schedule)
                
            except Exception as e:
                if perf_config.environment != "production":
                    logger.error(f"시간/우선순위 강화 오류: {str(e)}")
                final_enhanced = schedule_data
            
            # 위치 정보 보강 결과 대기
            try:
                location_enhanced = await tasks[0]
                
                # 시간/우선순위 정보와 위치 정보 병합
                merged_data = merge_schedule_data(final_enhanced, location_enhanced)
                
            except Exception as e:
                if perf_config.environment != "production":
                    logger.error(f"위치 정보 보강 오류: {str(e)}")
                merged_data = final_enhanced
            
            return merged_data
        
        # 비동기 처리 실행
        final_data = await process_enhancements()
        
        # 4. 일정 분류 및 정리
        all_schedules = []
        all_schedules.extend(final_data.get("fixedSchedules", []))
        all_schedules.extend(final_data.get("flexibleSchedules", []))
        
        fixed_schedules = [s for s in all_schedules if s.get("type") == "FIXED" and "startTime" in s and "endTime" in s]
        flexible_schedules = [s for s in all_schedules if s.get("type") != "FIXED" or "startTime" not in s or "endTime" not in s]
        
        result_data = {
            "fixedSchedules": fixed_schedules,
            "flexibleSchedules": flexible_schedules
        }
        
        # 5. Pydantic 모델로 변환
        try:
            response = ExtractScheduleResponse(**result_data)
            return response
        except Exception as e:
            if perf_config.environment != "production":
                logger.error(f"Pydantic 변환 오류: {str(e)}")
            from fastapi.responses import JSONResponse
            return JSONResponse(
                content=result_data,
                media_type="application/json; charset=utf-8"
            )
            
    except Exception as e:
        logger.error(f"일정 처리 오류: {str(e)}")
        raise HTTPException(status_code=500, detail=f"일정 처리 중 오류 발생: {str(e)}")

@app.post("/api/v1/schedules/optimize-1", response_model=OptimizeScheduleResponse)
async def optimize_schedules(request: OptimizeScheduleRequest):
    """추출된 일정을 최적화하고 경로 정보를 생성합니다. (최적화됨)"""
    try:
        logger = logging.getLogger('optimize_schedules')
        if perf_config.environment != "production":
            logger.info(f"일정 최적화 요청: 고정 {len(request.fixedSchedules)}개, 유연 {len(request.flexibleSchedules)}개")
        
        # 1. 모든 일정을 수집하여 최적화 준비
        all_schedules = []
        
        # 고정 일정 처리
        for schedule in request.fixedSchedules:
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
                "start_time": None,
                "end_time": None,
                "duration": schedule.duration,
                "priority": schedule.priority,
                "latitude": schedule.latitude,
                "longitude": schedule.longitude,
                "location": schedule.location,
                "type": schedule.type,
                "flexible": True
            })
        
        # 2. 일정 최적화 (시간 할당)
        fixed_schedules = [s for s in all_schedules if not s["flexible"]]
        flexible_schedules = [s for s in all_schedules if s["flexible"]]
        
        # 고정 일정을 시간순으로 정렬
        fixed_schedules.sort(key=lambda x: x["start_time"])
        
        # 유연 일정을 우선순위순으로 정렬
        flexible_schedules.sort(key=lambda x: x["priority"])
        
        # 최적화된 일정 목록
        optimized_schedules = fixed_schedules.copy()
        
        # 유연 일정에 시간 할당
        if fixed_schedules:
            current_time = fixed_schedules[-1]["end_time"]
        else:
            current_time = datetime.datetime.now()
        
        for schedule in flexible_schedules:
            start_time = current_time
            end_time = start_time + datetime.timedelta(minutes=schedule["duration"])
            
            schedule["start_time"] = start_time
            schedule["end_time"] = end_time
            current_time = end_time
            
            optimized_schedules.append(schedule)
        
        # 시간순으로 재정렬
        optimized_schedules.sort(key=lambda x: x["start_time"])
        
        # 3. 경로 정보 계산 (비동기)
        route_segments = await calculate_routes_async(optimized_schedules)
        
        # 메트릭 계산
        total_distance = sum(segment["distance"] for segment in route_segments)
        total_time = sum(segment["estimatedTime"] for segment in route_segments)
        
        # 4. 일정 분석 정보 생성 (병렬 처리)
        schedule_analyses = {}
        analysis_tasks = []
        
        for schedule in optimized_schedules:
            analysis_tasks.append(generate_schedule_analysis(schedule))
        
        # 분석 결과 병렬 처리
        analysis_results = await asyncio.gather(*analysis_tasks, return_exceptions=True)
        
        for i, analysis in enumerate(analysis_results):
            if not isinstance(analysis, Exception):
                schedule_name = optimized_schedules[i]["name"]
                schedule_analyses[schedule_name] = analysis
        
        # 5. 응답 구성
        optimized_schedules_response = []
        
        for schedule in optimized_schedules:
            # 위치 정보 구성
            location_string = schedule["location"]
            if schedule["flexible"] and " - " in schedule["name"]:
                # 유연 일정은 JSON 형태로 위치 정보 저장
                place_name = schedule["name"].split(" - ")[1] if " - " in schedule["name"] else schedule["name"]
                location_info = {
                    "address": schedule["location"],
                    "distance": round(random.uniform(300, 700), 6),
                    "latitude": schedule["latitude"],
                    "name": place_name,
                    "rating": round(random.uniform(3.5, 4.5), 1),
                    "source": "foursquare",
                    "longitude": schedule["longitude"]
                }
                location_string = json.dumps(location_info, ensure_ascii=False, separators=(',', ':'))
            
            # 시간 포맷팅
            start_time_str = schedule["start_time"].isoformat()
            end_time_str = schedule["end_time"].isoformat()
            
            # 이름 처리
            display_name = schedule["name"].split(" - ")[0] if " - " in schedule["name"] else schedule["name"]
            
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
        
        # 최종 응답
        response = {
            "optimizedSchedules": optimized_schedules_response,
            "routeSegments": route_segments,
            "metrics": metrics,
            "alternativeOptions": None,
            "scheduleAnalyses": schedule_analyses
        }
        
        # JSON 응답 반환
        from fastapi.responses import JSONResponse
        return JSONResponse(
            content=response,
            media_type="application/json; charset=utf-8"
        )
        
    except Exception as e:
        logger.error(f"일정 최적화 오류: {str(e)}")
        raise HTTPException(status_code=500, detail=f"일정 최적화 중 오류 발생: {str(e)}")

# 애플리케이션 시작 시 초기화
@app.on_event("startup")
async def startup_event():
    """애플리케이션 시작 시 초기화 작업"""
    logger = logging.getLogger('app_startup')
    logger.info("일정 추출 및 최적화 API 시작")
    
    # 캐시 매니저 초기화 확인
    if cache_manager.redis_client:
        logger.info("Redis 캐시 연결 성공")
    else:
        logger.warning("Redis 연결 실패, 로컬 캐시만 사용")
    
    # 성능 설정 로깅
    logger.info(f"환경: {perf_config.environment}")
    logger.info(f"캐싱 활성화: {perf_config.enable_caching}")
    logger.info(f"최대 동시 요청: {perf_config.max_concurrent_requests}")
    logger.info(f"LLM 모델: {perf_config.get_llm_config()['model_name']}")

@app.on_event("shutdown")
async def shutdown_event():
    """애플리케이션 종료 시 정리 작업"""
    logger = logging.getLogger('app_shutdown')
    logger.info("일정 추출 및 최적화 API 종료")
    
    # Redis 연결 정리
    if cache_manager.redis_client:
        try:
            cache_manager.redis_client.close()
            logger.info("Redis 연결 정리 완료")
        except Exception as e:
            logger.error(f"Redis 연결 정리 오류: {str(e)}")

# 헬스 체크 엔드포인트
@app.get("/health")
async def health_check():
    """애플리케이션 상태 확인"""
    health_status = {
        "status": "healthy",
        "timestamp": datetime.datetime.now().isoformat(),
        "environment": perf_config.environment,
        "cache_enabled": perf_config.enable_caching,
        "redis_connected": cache_manager.redis_client is not None
    }
    
    # Redis 연결 상태 확인
    if cache_manager.redis_client:
        try:
            cache_manager.redis_client.ping()
            health_status["redis_status"] = "connected"
        except Exception:
            health_status["redis_status"] = "disconnected"
            health_status["redis_connected"] = False
    else:
        health_status["redis_status"] = "not_configured"
    
    return health_status

# 캐시 상태 확인 엔드포인트 (개발/테스트용)
@app.get("/cache/stats")
async def cache_stats():
    """캐시 통계 정보 (개발/테스트용)"""
    if perf_config.environment == "production":
        raise HTTPException(status_code=404, detail="Not found")
    
    stats = {
        "local_cache_size": len(cache_manager.local_cache),
        "max_local_cache_size": cache_manager.max_local_cache_size,
        "redis_connected": cache_manager.redis_client is not None
    }
    
    # Redis 통계 추가
    if cache_manager.redis_client:
        try:
            redis_info = cache_manager.redis_client.info()
            stats["redis_stats"] = {
                "used_memory": redis_info.get("used_memory_human"),
                "connected_clients": redis_info.get("connected_clients"),
                "total_commands_processed": redis_info.get("total_commands_processed")
            }
        except Exception as e:
            stats["redis_error"] = str(e)
    
    return stats

# 서버 시작 코드
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app:app", 
        host="0.0.0.0", 
        port=8081, 
        reload=perf_config.environment == "development",
        log_level=perf_config.log_level.lower()
    )