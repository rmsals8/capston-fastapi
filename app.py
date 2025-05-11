import logging
from fastapi import FastAPI, HTTPException, Body
from pydantic import BaseModel, Field
from langchain_openai import ChatOpenAI
from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import JsonOutputParser
from langchain.chains import LLMChain
from typing import Dict, List, Optional, Any, Union
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
from fastapi.middleware.cors import CORSMiddleware

from scheduler import (
    create_schedule_chain, 
    create_enhancement_chain,
    apply_time_inference,
    apply_priorities,
    enhance_schedule_with_relationships
)
# 환경 변수 로드
load_dotenv()

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

# 입력 모델 정의
class ScheduleRequest(BaseModel):
    voice_input: str

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
    
    def search_place_detailed(self, query: str) -> Dict:
        """더 상세한 장소 검색 기능"""
        try:
            # URL 인코딩
            encoded_query = requests.utils.quote(query)
            
            # Places API 호출 - 추가 필드로 상세 정보 요청
            url = f"https://maps.googleapis.com/maps/api/place/findplacefromtext/json?input={encoded_query}&inputtype=textquery&fields=name,formatted_address,geometry,place_id,types,address_components&language=ko&key={self.api_key}"
            
            response = requests.get(url, timeout=5)
            if response.status_code != 200:
                print(f"Google Places API 호출 실패: {response.status_code}")
                return None
            
            data = response.json()
            
            if data['status'] == 'OK' and data.get('candidates') and len(data['candidates']) > 0:
                candidate = data['candidates'][0]
                
                # 주소 구성 요소를 사용하여 보다 구체적인 주소 생성
                address_components = candidate.get('address_components', [])
                formatted_address = candidate.get('formatted_address', '')
                
                # 주소 구성 요소가 있으면 더 구체적인 주소 생성 시도
                if address_components:
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
                            if len(detailed_address.split()) >= len(formatted_address.split()):
                                formatted_address = detailed_address
                
                return {
                    'name': candidate.get('name', query),
                    'formatted_address': formatted_address,
                    'latitude': candidate['geometry']['location']['lat'],
                    'longitude': candidate['geometry']['location']['lng'],
                    'place_id': candidate.get('place_id', ''),
                    'types': candidate.get('types', [])
                }
            else:
                print(f"장소를 찾을 수 없음: {data['status']}")
                return None
                
        except Exception as e:
            print(f"장소 검색 중 오류 발생: {str(e)}")
            return None
    
    def search_nearby_detailed(self, query: str, location: str = "37.4980,127.0276", radius: int = 1000) -> Dict:
        """개선된 주변 장소 검색 기능"""
        try:
            # URL 인코딩
            encoded_query = requests.utils.quote(query)
            
            # Nearby Search API 호출
            url = f"https://maps.googleapis.com/maps/api/place/nearbysearch/json?location={location}&radius={radius}&keyword={encoded_query}&language=ko&key={self.api_key}"
            
            response = requests.get(url, timeout=5)
            if response.status_code != 200:
                print(f"Nearby Places API 호출 실패: {response.status_code}")
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
                    'place_id': top_place.get('place_id', '')
                }
            else:
                print(f"주변 장소를 찾을 수 없음: {data['status']}")
                return None
                
        except Exception as e:
            print(f"주변 장소 검색 중 오류 발생: {str(e)}")
            return None
    
    def get_place_details(self, place_id: str) -> Dict:
        """Place ID를 사용하여 장소의 상세 정보를 가져옵니다."""
        if not place_id:
            print("Place ID가 제공되지 않았습니다.")
            return None
            
        try:
            # Place Details API 호출
            url = f"https://maps.googleapis.com/maps/api/place/details/json?place_id={place_id}&fields=name,formatted_address,geometry,address_component&language=ko&key={self.api_key}"
            
            response = requests.get(url, timeout=5)
            if response.status_code != 200:
                print(f"Place Details API 호출 실패: {response.status_code}")
                return None
            
            data = response.json()
            
            if data['status'] == 'OK' and data.get('result'):
                result = data['result']
                
                return {
                    'name': result.get('name', ''),
                    'formatted_address': result.get('formatted_address', ''),
                    'latitude': result['geometry']['location']['lat'],
                    'longitude': result['geometry']['location']['lng'],
                    'place_id': place_id
                }
            else:
                print(f"장소 상세 정보를 찾을 수 없음: {data['status']}")
                return None
                
        except Exception as e:
            print(f"장소 상세 정보 검색 중 오류 발생: {str(e)}")
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
    
    수정사항:
    - 지역 접두사 목록 대신 단계적 하이브리드 접근법 적용
    - 컨텍스트 기반 단일 검색을 먼저 시도하고 실패 시에만 추가 검색
    - 장소명에 지역명이 이미 포함되어 있는지 확인하는 로직 추가
    """
    print("위치 정보 보강 시작...")
    
    # GooglePlacesTool 초기화
    places_tool = GooglePlacesTool()
    
    # 복사본 생성하여 원본 데이터 보존
    enhanced_data = json.loads(json.dumps(schedule_data))
    
    # 주요 지역 목록 (fallback 검색용)
    major_regions = ["서울", "부산", "대구", "인천", "광주", "대전", "울산"]
    
    # 지역명이 장소명에 포함되어 있는지 확인하는 함수
    def contains_region(place_name: str) -> (bool, str):
        """장소명에 지역명이 포함되어 있는지 확인하고, 포함된 지역명 반환"""
        for region in major_regions:
            if region in place_name:
                return True, region
        return False, ""
    
    # 고정 일정을 통해 주요 지역 컨텍스트 파악
    primary_region = None
    if "fixedSchedules" in enhanced_data and enhanced_data["fixedSchedules"]:
        main_fixed_schedule = enhanced_data["fixedSchedules"][0]
        place_name = main_fixed_schedule.get("name", "")
        location = main_fixed_schedule.get("location", "")
        
        # 장소명이나 위치에서 지역 추출
        has_region, region = contains_region(place_name)
        if has_region:
            primary_region = region
        else:
            for region in major_regions:
                if region in location:
                    primary_region = region
                    break
    
    print(f"주요 지역 컨텍스트: {primary_region or '없음'}")
    
    # 고정 일정 처리
    if "fixedSchedules" in enhanced_data and isinstance(enhanced_data["fixedSchedules"], list):
        for i, schedule in enumerate(enhanced_data["fixedSchedules"]):
            print(f"고정 일정 {i+1} 처리 중: {schedule.get('name', '이름 없음')}")
            
            place_name = schedule.get("name", "")
            if not place_name:
                continue
            
            # 장소 검색 시도
            found_place = None
            
            # 단계 1: 컨텍스트 기반 단일 검색 (주요 로직 변경)
            search_term = place_name  # 기본값은 장소명 그대로
            
            # 장소명에 지역이 이미 포함되어 있는지 확인
            has_region_in_name, region_in_name = contains_region(place_name)
            
            if has_region_in_name:
                # 이미 지역명이 포함되어 있으면 그대로 사용
                print(f"장소명에 지역({region_in_name})이 이미 포함됨")
                search_term = place_name
            elif primary_region:
                # 주요 지역 컨텍스트가 있으면 추가
                search_term = f"{primary_region} {place_name}"
                print(f"컨텍스트 기반 검색 시도: '{search_term}'")
            else:
                # 컨텍스트가 없으면 장소명 그대로 사용
                print(f"기본 검색 시도: '{search_term}'")
            
            # 첫 번째 검색 실행
            place_info = places_tool.search_place_detailed(search_term)
            
            # 결과 확인
            if place_info and place_info.get("formatted_address"):
                found_place = place_info
                print(f"장소 찾음: {place_info.get('name')} - {place_info.get('formatted_address')}")
            else:
                # 단계 2: 첫 검색 실패 시 추가 전략 시도
                print(f"첫 검색 실패, 추가 전략 시도...")
                
                # 2-1: 장소명에 지역명이 포함된 경우, 지역명 제거 후 검색
                if has_region_in_name:
                    # 지역명 제거한 깨끗한 장소명 생성
                    clean_name = place_name.replace(region_in_name, "").strip()
                    if clean_name:  # 비어있지 않으면
                        print(f"지역명 제거 후 검색 시도: '{clean_name}'")
                        place_info = places_tool.search_place_detailed(clean_name)
                        if place_info and place_info.get("formatted_address"):
                            found_place = place_info
                            print(f"장소 찾음: {place_info.get('name')} - {place_info.get('formatted_address')}")
                
                # 2-2: 그래도 실패하면 주요 지역 접두사 시도 (최대 3개)
                if not found_place:
                    # 컨텍스트와 다른 몇 개의 주요 도시만 시도
                    fallback_regions = []
                    if primary_region:
                        # 주요 지역이 이미 있으면 다른 주요 도시 2개만 추가
                        for region in major_regions:
                            if region != primary_region and len(fallback_regions) < 2:
                                fallback_regions.append(region)
                    else:
                        # 주요 지역이 없으면 상위 3개 주요 도시 시도
                        fallback_regions = major_regions[:3]
                    
                    for region in fallback_regions:
                        search_term = f"{region} {place_name}"
                        print(f"대체 지역 검색 시도: '{search_term}'")
                        place_info = places_tool.search_place_detailed(search_term)
                        if place_info and place_info.get("formatted_address"):
                            found_place = place_info
                            print(f"장소 찾음: {place_info.get('name')} - {place_info.get('formatted_address')}")
                            break
            
            # 장소를 찾았으면 정보 업데이트
            if found_place:
                # 주소 업데이트
                if found_place.get("formatted_address"):
                    original_location = schedule.get("location", "")
                    new_location = found_place["formatted_address"]
                    
                    # 주소가 충분히 구체적인지 확인
                    if len(new_location.split()) > 2:  # 최소 3개 단어 이상의 주소
                        print(f"주소 업데이트: '{original_location}' -> '{new_location}'")
                        schedule["location"] = new_location
                    else:
                        print(f"주소가 너무 일반적임: '{new_location}', 검색 계속")
                        # 더 구체적인 주소 검색 시도 (place_id 이용)
                        detailed_place = places_tool.get_place_details(found_place.get("place_id", ""))
                        if detailed_place and detailed_place.get("formatted_address"):
                            print(f"상세 주소 찾음: '{detailed_place['formatted_address']}'")
                            schedule["location"] = detailed_place["formatted_address"]
                
                # 좌표 업데이트
                if found_place.get("latitude") and found_place.get("longitude"):
                    schedule["latitude"] = found_place["latitude"]
                    schedule["longitude"] = found_place["longitude"]
                    print(f"좌표 업데이트: [{found_place['latitude']}, {found_place['longitude']}]")
            else:
                print(f"'{place_name}'에 대한 정확한 장소 정보를 찾을 수 없음")
    
    # 유연 일정 처리
    if "flexibleSchedules" in enhanced_data and isinstance(enhanced_data["flexibleSchedules"], list):
        for i, schedule in enumerate(enhanced_data["flexibleSchedules"]):
            print(f"유연 일정 {i+1} 처리 중: {schedule.get('name', '이름 없음')}")
            
            # 유연 일정의 경우 카테고리 기반 검색
            category = schedule.get("name", "")
            
            # 기존 위치 정보가 있으면 인근 검색 (고정 일정 기준)
            existing_location = None
            if "fixedSchedules" in enhanced_data and enhanced_data["fixedSchedules"]:
                for fixed in enhanced_data["fixedSchedules"]:
                    if fixed.get("latitude") and fixed.get("longitude"):
                        existing_location = f"{fixed['latitude']},{fixed['longitude']}"
                        print(f"인근 검색 기준점: {fixed.get('name', '')} ({existing_location})")
                        break
            
            # 검색 쿼리 구성
            search_queries = []
            if "식사" in category or "식당" in category or "밥" in category:
                search_queries = ["맛집", "레스토랑", "식당"]
            elif "카페" in category or "커피" in category:
                search_queries = ["카페", "커피숍", "스타벅스"]
            elif "쇼핑" in category or "마트" in category:
                search_queries = ["쇼핑몰", "마트", "백화점"]
            else:
                search_queries = [category]
            
            # 여러 검색어로 시도하여 가장 적합한 결과 찾기
            found_place = None
            
            # 중복 검색 방지를 위한 집합
            attempted_searches = set()
            
            for query in search_queries:
                # 검색 쿼리 생성 (인근 검색 또는 컨텍스트 기반 검색)
                if existing_location:
                    # 인근 장소 검색
                    search_term = query
                    if search_term in attempted_searches:
                        continue
                    
                    attempted_searches.add(search_term)
                    print(f"인근 '{search_term}' 검색 중...")
                    place_info = places_tool.search_nearby_detailed(search_term, existing_location)
                else:
                    # 일반 지역 검색 (컨텍스트 기반)
                    if primary_region:
                        # 지역 컨텍스트가 있는 경우
                        search_term = f"{primary_region} {query}"
                    else:
                        # 기본 지역 (서울) 사용
                        search_term = f"서울 {query}"
                    
                    if search_term in attempted_searches:
                        continue
                    
                    attempted_searches.add(search_term)
                    print(f"'{search_term}' 지역 검색 중...")
                    place_info = places_tool.search_place_detailed(search_term)
                
                if place_info and place_info.get("formatted_address"):
                    found_place = place_info
                    print(f"장소 찾음: {place_info.get('name')} - {place_info.get('formatted_address')}")
                    break
            
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
                    
                    print(f"주소 업데이트: '{schedule.get('location', '')}' -> '{new_location}'")
                    schedule["location"] = new_location
                
                # 좌표 업데이트
                if found_place.get("latitude") and found_place.get("longitude"):
                    schedule["latitude"] = found_place["latitude"]
                    schedule["longitude"] = found_place["longitude"]
                    print(f"좌표 업데이트: [{found_place['latitude']}, {found_place['longitude']}]")
            else:
                print(f"'{category}'에 대한 적합한 장소를 찾을 수 없음")
    
    print("위치 정보 보강 완료")
    return enhanced_data

# ----- 엔드포인트 정의 -----

@app.get("/")
async def root():
    return {"message": "일정 추출 및 최적화 API가 실행 중입니다. POST /extract-schedule 또는 POST /api/v1/schedules/optimize-1 엔드포인트를 사용하세요."}

@app.post("/extract-schedule", response_model=ExtractScheduleResponse)
async def extract_schedule(request: ScheduleRequest):
    """
    음성 입력에서 일정을 추출하고 위치 정보를 보강합니다.
    """
    # 로깅 설정
    logger = logging.getLogger('extract_schedule')
    logger.setLevel(logging.INFO)
    
    try:
        # 인코딩 테스트 함수
        def test_encoding(text):
            """한글 인코딩 테스트 함수"""
            logger.info(f"원본 텍스트: {text}")
            
            # 다양한 인코딩으로 변환 테스트
            encodings = ['utf-8', 'euc-kr', 'cp949']
            for enc in encodings:
                try:
                    encoded = text.encode(enc)
                    decoded = encoded.decode(enc)
                    logger.info(f"{enc} 인코딩 변환 결과: {decoded}, 변환 성공: {text == decoded}")
                except Exception as e:
                    logger.error(f"{enc} 인코딩 변환 실패: {str(e)}")
            
            # JSON 직렬화/역직렬화 테스트
            try:
                json_str = json.dumps({"text": text}, ensure_ascii=False)
                json_obj = json.loads(json_str)
                logger.info(f"JSON 변환 결과: {json_obj['text']}, 변환 성공: {text == json_obj['text']}")
            except Exception as e:
                logger.error(f"JSON 변환 실패: {str(e)}")
        
        # 시스템 인코딩 정보 확인
        import sys
        import locale
        logger.info(f"시스템 기본 인코딩: {sys.getdefaultencoding()}")
        logger.info(f"로케일 인코딩: {locale.getpreferredencoding()}")
        logger.info(f"파이썬 파일 기본 인코딩: {sys.getfilesystemencoding()}")
        
        # 요청 처리 시작
        logger.info(f"일정 추출 요청 받음: 음성 입력 길이={len(request.voice_input)}")
        
        # 입력 텍스트 인코딩 테스트
        logger.info(f"음성 입력 인코딩 테스트:")
        test_encoding(request.voice_input)
        logger.info(f"음성 입력 받음: '{request.voice_input}'")
        
        # 1. LangChain을 사용한 일정 추출
        logger.info("LangChain 일정 추출 체인 생성 시작")
        chain = create_schedule_chain()
        logger.info("LangChain 체인 생성 완료")
        
        # 2. 체인 실행
        result = None
        try:
            # 입력 데이터 인코딩 확인
            input_data = {"input": request.voice_input}
            input_json = json.dumps(input_data, ensure_ascii=False)
            logger.info(f"LangChain 입력 JSON: {input_json}")
            
            logger.info("LangChain 체인 실행 시작")
            result = chain.invoke(input_data)
            logger.info("LangChain 체인 실행 완료")
            
            # 결과 타입 확인
            logger.info(f"LangChain 응답 타입: {type(result)}")
            
            # 결과 인코딩 테스트
            if isinstance(result, dict):
                result_json = json.dumps(result, ensure_ascii=False)
                logger.info(f"LangChain 응답 JSON: {result_json[:200]}...")
                
                # 결과 한글 데이터 인코딩 테스트
                if "fixedSchedules" in result and result["fixedSchedules"]:
                    first_fixed = result["fixedSchedules"][0]
                    if "name" in first_fixed:
                        logger.info(f"고정 일정 이름 인코딩 테스트:")
                        test_encoding(first_fixed["name"])
                    if "location" in first_fixed:
                        logger.info(f"고정 일정 위치 인코딩 테스트:")
                        test_encoding(first_fixed["location"])
                
                if "flexibleSchedules" in result and result["flexibleSchedules"]:
                    first_flexible = result["flexibleSchedules"][0]
                    if "name" in first_flexible:
                        logger.info(f"유연 일정 이름 인코딩 테스트:")
                        test_encoding(first_flexible["name"])
                    if "location" in first_flexible:
                        logger.info(f"유연 일정 위치 인코딩 테스트:")
                        test_encoding(first_flexible["location"])
            else:
                logger.info(f"LangChain 응답 (문자열): {result[:200]}...")
                
        except Exception as e:
            logger.error(f"LangChain 처리 중 오류: {str(e)}")
            # 오류 발생 시 문자열 추출 시도
            if hasattr(e, 'response') and hasattr(e.response, 'content'):
                try:
                    # UTF-8로 명시적 디코딩
                    content = e.response.content.decode('utf-8')
                    logger.info(f"오류 응답 디코딩 (UTF-8): {content[:200]}...")
                except UnicodeDecodeError:
                    # UTF-8 디코딩 실패 시 다른 인코딩 시도
                    try:
                        content = e.response.content.decode('cp949')
                        logger.info(f"오류 응답 디코딩 (CP949): {content[:200]}...")
                    except Exception as e2:
                        try:
                            content = e.response.content.decode('euc-kr')
                            logger.info(f"오류 응답 디코딩 (EUC-KR): {content[:200]}...")
                        except Exception as e3:
                            # 마지막 수단: 바이너리 출력
                            content = str(e.response.content)
                            logger.info(f"오류 응답 (바이너리): {content[:200]}...")
                
                json_match = re.search(r'({[\s\S]*})', content)
                if json_match:
                    json_str = json_match.group(1)
                    logger.info(f"추출된 JSON 문자열: {json_str[:200]}...")
                    # JSON 문자열 인코딩 테스트
                    try:
                        logger.info(f"JSON 문자열 인코딩 테스트:")
                        test_encoding(json_str[:100]) # 첫 100자만 테스트
                    except Exception as e4:
                        logger.error("JSON 문자열 인코딩 테스트 실패")
                    
                    result = safe_parse_json(json_str)
                else:
                    logger.error("JSON 추출 실패")
                    raise HTTPException(status_code=500, detail=f"LLM 응답 처리 실패: {str(e)}")
            else:
                logger.error("오류 응답에서 콘텐츠를 찾을 수 없음")
                raise HTTPException(status_code=500, detail=f"LLM 처리 중 오류 발생: {str(e)}")
        
        # 3. 결과가 문자열인 경우 안전하게 JSON 파싱
        schedule_data = None
        if isinstance(result, str):
            logger.info("응답이 문자열 형태입니다. JSON 추출 시도...")
            # 문자열 인코딩 테스트
            try:
                logger.info(f"응답 문자열 인코딩 테스트 (처음 100자):")
                test_encoding(result[:100])
            except Exception as e:
                logger.error("응답 문자열 인코딩 테스트 실패")
            
            # 정규식으로 JSON 추출
            json_match = re.search(r'({[\s\S]*})', result)
            if json_match:
                json_str = json_match.group(1)
                logger.info(f"정규식으로 추출한 JSON: {json_str[:200]}...")
                # 추출된 JSON 인코딩 테스트
                try:
                    logger.info(f"추출된 JSON 인코딩 테스트 (처음 100자):")
                    test_encoding(json_str[:100])
                except Exception as e:
                    logger.error("추출된 JSON 인코딩 테스트 실패")
                
                schedule_data = safe_parse_json(json_str)
            else:
                logger.info("정규식으로 JSON 추출 실패, 전체 문자열로 시도")
                schedule_data = safe_parse_json(result)
        else:
            # 이미 파싱된 객체를 인코딩 이슈 방지를 위해 다시 직렬화/역직렬화
            try:
                result_json = json.dumps(result, ensure_ascii=False)
                logger.info(f"결과 직렬화 성공: {result_json[:200]}...")
                schedule_data = json.loads(result_json)
                logger.info("결과 역직렬화 성공")
            except Exception as e:
                logger.error(f"결과 직렬화/역직렬화 실패: {str(e)}")
                # 실패 시 원본 사용
                schedule_data = result
        
        # 스케줄 데이터 구조 확인
        logger.info(f"스케줄 데이터 구조:")
        logger.info(f"고정 일정 수: {len(schedule_data.get('fixedSchedules', []))}")
        logger.info(f"유연 일정 수: {len(schedule_data.get('flexibleSchedules', []))}")
        
        # 각 일정 데이터 인코딩 테스트
        if "fixedSchedules" in schedule_data and schedule_data["fixedSchedules"]:
            first_fixed = schedule_data["fixedSchedules"][0]
            logger.info(f"첫 번째 고정 일정 인코딩 테스트:")
            if "name" in first_fixed:
                logger.info(f"이름: {first_fixed['name']}")
                test_encoding(first_fixed["name"])
            if "location" in first_fixed:
                logger.info(f"위치: {first_fixed['location']}")
                test_encoding(first_fixed["location"])
        
        if "flexibleSchedules" in schedule_data and schedule_data["flexibleSchedules"]:
            first_flexible = schedule_data["flexibleSchedules"][0]
            logger.info(f"첫 번째 유연 일정 인코딩 테스트:")
            if "name" in first_flexible:
                logger.info(f"이름: {first_flexible['name']}")
                test_encoding(first_flexible["name"])
            if "location" in first_flexible:
                logger.info(f"위치: {first_flexible['location']}")
                test_encoding(first_flexible["location"])
        
        # 4. LangChain으로 시간 및 우선순위 강화
        logger.info("시간 및 우선순위 강화 시작...")
        try:
            # LangChain 체인 생성
            logger.info("강화 체인 생성 시작")
            enhancement_chains = create_enhancement_chain()
            time_chain = enhancement_chains["time_chain"]
            priority_chain = enhancement_chains["priority_chain"]
            logger.info("강화 체인 생성 완료")
            
            # 시간 추론 적용
            logger.info("시간 추론 적용 시작")
            schedule_data_with_time = apply_time_inference(
                time_chain, 
                request.voice_input, 
                schedule_data
            )
            logger.info("시간 추론 적용 완료")
            
            # 시간 추론 적용 결과 로깅
            logger.info("시간 추론 적용 결과 요약:")
            for idx, schedule in enumerate(schedule_data_with_time.get("flexibleSchedules", [])):
                logger.info(f"유연 일정 {idx+1}: {schedule.get('name', '')}, 시작: {schedule.get('startTime', 'N/A')}, 종료: {schedule.get('endTime', 'N/A')}")
            
            # 우선순위 분석 적용
            logger.info("우선순위 분석 적용 시작")
            enhanced_schedule_data = apply_priorities(
                priority_chain, 
                request.voice_input, 
                schedule_data_with_time
            )
            logger.info("우선순위 분석 적용 완료")
            
            # 우선순위 분석 적용 결과 로깅
            logger.info("우선순위 분석 적용 결과 요약:")
            for idx, schedule in enumerate(enhanced_schedule_data.get("flexibleSchedules", [])):
                logger.info(f"유연 일정 {idx+1}: {schedule.get('name', '')}, 우선순위: {schedule.get('priority', 'N/A')}")
            
            # 일정 간 관계 분석 적용
            logger.info("일정 간 관계 분석 적용 시작")
            final_enhanced_data = enhance_schedule_with_relationships(
                request.voice_input,
                enhanced_schedule_data
            )
            logger.info("일정 간 관계 분석 적용 완료")
            
            # 관계 분석 적용 결과 로깅
            logger.info("관계 분석 적용 결과 요약:")
            for idx, schedule in enumerate(final_enhanced_data.get("flexibleSchedules", [])):
                logger.info(f"유연 일정 {idx+1}: {schedule.get('name', '')}, 타입: {schedule.get('type', 'N/A')}, 시간: {schedule.get('startTime', 'N/A')} ~ {schedule.get('endTime', 'N/A')}, 우선순위: {schedule.get('priority', 'N/A')}")
            
            logger.info("시간, 우선순위, 관계 강화 완료")
            
        except Exception as e:
            logger.error(f"시간 및 우선순위 강화 중 오류: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())
            # 오류 발생 시 원본 데이터 사용
            logger.info("오류로 인해 원본 데이터 사용")
            final_enhanced_data = schedule_data
        
        # 5. 향상된 위치 정보 보강
        logger.info(f"위치 정보 보강 시작...")
        location_enhanced_data = None
        try:
            logger.info("위치 정보 보강 함수 호출")
            location_enhanced_data = enhance_location_data(final_enhanced_data)
            
            # 보강된 데이터 인코딩 테스트
            enhanced_json = json.dumps(location_enhanced_data, ensure_ascii=False)
            logger.info(f"보강된 데이터 직렬화 성공, 길이: {len(enhanced_json)}")
            logger.info(f"보강된 데이터 JSON 샘플: {enhanced_json[:200]}...")
            
            # 한 번 더 직렬화/역직렬화로 인코딩 문제 방지
            location_enhanced_data = json.loads(enhanced_json)
            logger.info("보강된 데이터 역직렬화 성공")
            
            # 보강된 데이터 인코딩 테스트
            if "fixedSchedules" in location_enhanced_data and location_enhanced_data["fixedSchedules"]:
                first_fixed = location_enhanced_data["fixedSchedules"][0]
                logger.info(f"보강된 첫 번째 고정 일정 인코딩 테스트:")
                if "name" in first_fixed:
                    logger.info(f"이름: {first_fixed['name']}")
                    test_encoding(first_fixed["name"])
                if "location" in first_fixed:
                    logger.info(f"위치: {first_fixed['location']}")
                    test_encoding(first_fixed["location"])
            
            if "flexibleSchedules" in location_enhanced_data and location_enhanced_data["flexibleSchedules"]:
                first_flexible = location_enhanced_data["flexibleSchedules"][0]
                logger.info(f"보강된 첫 번째 유연 일정 인코딩 테스트:")
                if "name" in first_flexible:
                    logger.info(f"이름: {first_flexible['name']}")
                    test_encoding(first_flexible["name"])
                if "location" in first_flexible:
                    logger.info(f"위치: {first_flexible['location']}")
                    test_encoding(first_flexible["location"])
            
            logger.info(f"위치 정보 보강 완료")
        except Exception as e:
            logger.error(f"위치 정보 보강 중 오류 발생: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())
            # 오류 발생 시 원본 데이터 사용
            logger.info("위치 정보 보강 오류로 인해 강화 데이터 사용")
            location_enhanced_data = final_enhanced_data
        
        # 6. Pydantic 모델로 변환하여 응답 검증
        try:
            logger.info(f"Pydantic 모델 변환 시작...")
            
            # 모델 변환 전 인코딩 확인을 위해 두 번 직렬화-역직렬화
            final_json = json.dumps(location_enhanced_data, ensure_ascii=False)
            final_data = json.loads(final_json)
            logger.info(f"최종 데이터 직렬화/역직렬화 성공, 길이: {len(final_json)}")
            
            # 변환 전 최종 데이터 구조 로깅
            logger.info(f"최종 데이터 구조:")
            logger.info(f"고정 일정 수: {len(final_data.get('fixedSchedules', []))}")
            logger.info(f"유연 일정 수: {len(final_data.get('flexibleSchedules', []))}")
            
            # 최종 데이터의 각 일정 로깅
            logger.info("최종 고정 일정:")
            for idx, schedule in enumerate(final_data.get("fixedSchedules", [])):
                logger.info(f"고정 일정 {idx+1}: {schedule.get('name', '')}, 위치: {schedule.get('location', 'N/A')}, 시간: {schedule.get('startTime', 'N/A')} ~ {schedule.get('endTime', 'N/A')}, 우선순위: {schedule.get('priority', 'N/A')}")
            
            logger.info("최종 유연 일정:")
            for idx, schedule in enumerate(final_data.get("flexibleSchedules", [])):
                logger.info(f"유연 일정 {idx+1}: {schedule.get('name', '')}, 위치: {schedule.get('location', 'N/A')}, 시간: {schedule.get('startTime', 'N/A')} ~ {schedule.get('endTime', 'N/A')}, 우선순위: {schedule.get('priority', 'N/A')}")
            
            # Pydantic 모델로 변환
            logger.info("Pydantic 모델 변환 시도")
            response = ExtractScheduleResponse(**final_data)
            logger.info("Pydantic 모델 변환 성공")
            
            # 응답 데이터 샘플 출력
            if response.fixedSchedules:
                logger.info(f"응답 고정 일정 첫 항목 이름: {response.fixedSchedules[0].name}")
                test_encoding(response.fixedSchedules[0].name)
                logger.info(f"응답 고정 일정 첫 항목 위치: {response.fixedSchedules[0].location}")
                test_encoding(response.fixedSchedules[0].location)
            
            if response.flexibleSchedules:
                logger.info(f"응답 유연 일정 첫 항목 이름: {response.flexibleSchedules[0].name}")
                test_encoding(response.flexibleSchedules[0].name)
                logger.info(f"응답 유연 일정 첫 항목 위치: {response.flexibleSchedules[0].location}")
                test_encoding(response.flexibleSchedules[0].location)
            
            logger.info("최종 응답 준비 완료")
            # Pydantic 모델 직접 반환
            return response
            
        except Exception as e:
            logger.error(f"Pydantic 모델 변환 오류: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())
            
            # 마지막 수단: 직접 JSONResponse 반환
            from fastapi.responses import JSONResponse
            logger.info("JSONResponse로 대체 응답 생성")
            
            # 직접 직렬화
            final_json = json.dumps(location_enhanced_data, ensure_ascii=False)
            logger.info(f"직접 직렬화 성공, 길이: {len(final_json)}")
            
            # JSON으로 다시 파싱
            final_data = json.loads(final_json)
            logger.info("직접 역직렬화 성공")
            
            logger.info("JSONResponse 반환")
            return JSONResponse(
                content=final_data,
                media_type="application/json; charset=utf-8"
            )
            
    except Exception as e:
        logger.error(f"일정 처리 전체 오류: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"일정 처리 중 오류 발생: {str(e)}")

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
            
            distance = calculate_distance(
                from_schedule["latitude"], from_schedule["longitude"],
                to_schedule["latitude"], to_schedule["longitude"]
            )
            
            estimated_time = calculate_travel_time(distance)
            
            # 경로 정보 추가
            route_segments.append({
                "fromLocation": from_schedule["name"],
                "toLocation": to_schedule["name"],
                "distance": round(distance, 3),
                "estimatedTime": estimated_time,
                "trafficRate": 1.0,
                "recommendedRoute": None,
                "realTimeTraffic": None
            })
            
            # 총 거리와 시간 누적
            total_distance += distance
            total_time += estimated_time
        
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