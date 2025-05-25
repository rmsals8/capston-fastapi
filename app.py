import logging
import asyncio
from concurrent.futures import ThreadPoolExecutor
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from langchain_openai import ChatOpenAI
from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import JsonOutputParser
from typing import Dict, List, Any, Optional
import os
import json
import re
import time
import datetime
from dotenv import load_dotenv
import aiohttp
import math
from openai import OpenAI

# 스케줄러 모듈 임포트
from scheduler.utils import detect_and_resolve_time_conflicts
from scheduler import (
    create_enhancement_chain,
    apply_time_inference,
    apply_priorities,
    enhance_schedule_with_relationships,
    parse_datetime
)

# 환경 변수 로드
load_dotenv()

# 로깅 설정
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# API 키 설정
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY") 
GOOGLE_MAPS_API_KEY = os.getenv("GOOGLE_MAPS_API_KEY")
KAKAO_REST_API_KEY = os.getenv("KAKAO_REST_API_KEY", "357d3401893dc5c9cbefc83bb65df4ee")
FOURSQUARE_API_KEY = os.getenv("FOURSQUARE_API_KEY", "fsq3VpVQLn5hZptfpIHLogZHRb7vAbteiSkiUlZT4QvpC8U=")

if not OPENAI_API_KEY:
    logger.error("❌ OPENAI_API_KEY가 설정되지 않았습니다!")
    raise ValueError("OPENAI_API_KEY를 환경변수에 설정해주세요.")

# OpenAI 클라이언트
openai_client = OpenAI(api_key=OPENAI_API_KEY)

# FastAPI 앱 초기화
app = FastAPI(title="3중 API 정확한 주소 검색 일정 추출 API", version="3.0.0")

# CORS 미들웨어 설정
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 한국 지역 정보
KOREA_REGIONS = {
    "서울특별시": {"강남구", "강동구", "강북구", "강서구", "관악구", "광진구", "구로구", "금천구",
               "노원구", "도봉구", "동대문구", "동작구", "마포구", "서대문구", "서초구", "성동구",
               "성북구", "송파구", "양천구", "영등포구", "용산구", "은평구", "종로구", "중구", "중랑구"},
    "부산광역시": {"강서구", "금정구", "기장군", "남구", "동구", "동래구", "부산진구", "북구", "사상구",
               "사하구", "서구", "수영구", "연제구", "영도구", "중구", "해운대구"},
    "대구광역시": {"남구", "달서구", "달성군", "동구", "북구", "서구", "수성구", "중구"},
    "인천광역시": {"강화군", "계양구", "남동구", "동구", "미추홀구", "부평구", "서구", "연수구", "옹진군", "중구"},
    "광주광역시": {"광산구", "남구", "동구", "북구", "서구"},
    "대전광역시": {"대덕구", "동구", "서구", "유성구", "중구"},
    "울산광역시": {"남구", "동구", "북구", "울주군", "중구"},
    "세종특별자치시": {"세종시"},
    "경기도": {"가평군", "고양시", "과천시", "광명시", "광주시", "구리시", "군포시", "김포시", "남양주시",
             "동두천시", "부천시", "성남시", "수원시", "시흥시", "안산시", "안성시", "안양시", "양주시",
             "양평군", "여주시", "연천군", "오산시", "용인시", "의왕시", "의정부시", "이천시", "파주시",
             "평택시", "포천시", "하남시", "화성시"},
    "강원특별자치도": {"강릉시", "고성군", "동해시", "삼척시", "속초시", "양구군", "양양군", "영월군", "원주시",
                  "인제군", "정선군", "철원군", "춘천시", "태백시", "평창군", "홍천군", "화천군", "횡성군"},
    "충청북도": {"괴산군", "단양군", "보은군", "영동군", "옥천군", "음성군", "제천시", "증평군", "진천군", "청주시", "충주시"},
    "충청남도": {"계룡시", "공주시", "금산군", "논산시", "당진시", "보령시", "부여군", "서산시", "서천군",
             "아산시", "예산군", "천안시", "청양군", "태안군", "홍성군"},
    "전북특별자치도": {"고창군", "군산시", "김제시", "남원시", "무주군", "부안군", "순창군", "완주군",
                  "익산시", "임실군", "장수군", "전주시", "정읍시", "진안군"},
    "전라남도": {"강진군", "고흥군", "곡성군", "광양시", "구례군", "나주시", "담양군", "목포시", "무안군",
             "보성군", "순천시", "신안군", "여수시", "영광군", "영암군", "완도군", "장성군", "장흥군",
             "진도군", "함평군", "해남군", "화순군"},
    "경상북도": {"경산시", "경주시", "고령군", "구미시", "군위군", "김천시", "문경시", "봉화군", "상주시",
             "성주군", "안동시", "영덕군", "영양군", "영주시", "영천시", "예천군", "울릉군", "울진군",
             "의성군", "청도군", "청송군", "칠곡군", "포항시"},
    "경상남도": {"거제시", "거창군", "고성군", "김해시", "남해군", "밀양시", "사천시", "산청군", "양산시",
             "의령군", "진주시", "창녕군", "창원시", "통영시", "하동군", "함안군", "함양군", "합천군"},
    "제주특별자치도": {"서귀포시", "제주시"}
}

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

class LocationAnalysis(BaseModel):
    place_name: str
    region: str
    district: str
    category: str
    search_keywords: List[str]

class PlaceResult(BaseModel):
    name: str
    address: str
    latitude: float
    longitude: float
    source: str  # foursquare, kakao, google
    rating: Optional[float] = None

# ----- 3중 위치 검색 서비스 -----
class TripleLocationSearchService:
    """Foursquare + Kakao + Google 3중 위치 검색 서비스"""
    
    @staticmethod
    async def analyze_location_with_gpt(text: str) -> LocationAnalysis:
        """GPT로 정확한 지역과 장소 분석"""
        
        # set을 list로 변환하여 JSON 직렬화 가능하게 만들기
        korea_regions_list = {region: list(districts) for region, districts in KOREA_REGIONS.items()}
        regions_text = json.dumps(korea_regions_list, ensure_ascii=False, indent=2)
        
        prompt = f"""
다음 텍스트에서 한국의 정확한 지역 정보와 장소를 분석해주세요.

텍스트: "{text}"

한국 지역 정보:
{regions_text}

JSON 형식으로 응답:
{{
  "place_name": "추출된 장소명 (예: 제주공항, 성산일출봉, 흑돼지 맛집)",
  "region": "시/도 (예: 제주특별자치도, 서울특별시)",
  "district": "시/군/구 (예: 제주시, 서귀포시, 강남구)",
  "category": "장소 카테고리 (예: 공항, 관광지, 식당, 카페)",
  "search_keywords": ["검색에 사용할 키워드들", "지역명+장소명", "카테고리명"]
}}

예시:
"제주공항" → {{"place_name": "제주공항", "region": "제주특별자치도", "district": "제주시", "category": "공항", "search_keywords": ["제주공항", "제주국제공항", "CJU"]}}
"성산일출봉 근처" → {{"place_name": "성산일출봉", "region": "제주특별자치도", "district": "서귀포시", "category": "관광지", "search_keywords": ["성산일출봉", "서귀포 성산일출봉", "일출봉"]}}
"""

        try:
            response = openai_client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "당신은 한국 지역 정보 전문가입니다. 텍스트에서 정확한 지역과 장소를 분석하여 JSON으로 응답하세요."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.1,
                max_tokens=300,
            )

            content = response.choices[0].message.content.strip()
            if content.startswith("```json"):
                content = content.replace("```json", "").replace("```", "").strip()
            
            data = json.loads(content)
            return LocationAnalysis(**data)
            
        except Exception as e:
            logger.error(f"❌ GPT 지역 분석 실패: {e}")
            # 기본값 반환
            return LocationAnalysis(
                place_name=text,
                region="서울특별시",
                district="중구",
                category="장소",
                search_keywords=[text]
            )

    @staticmethod
    async def search_foursquare(analysis: LocationAnalysis) -> Optional[PlaceResult]:
        """1순위: Foursquare API 검색"""
        if not FOURSQUARE_API_KEY:
            logger.warning("❌ Foursquare API 키가 없습니다")
            return None
            
        logger.info(f"🔍 1순위 Foursquare 검색: {analysis.place_name}")
        
        try:
            # 지역 좌표 기본값 설정
            region_coords = {
                "제주특별자치도": {"lat": 33.4996, "lng": 126.5312},
                "서울특별시": {"lat": 37.5665, "lng": 126.9780},
                "부산광역시": {"lat": 35.1796, "lng": 129.0756}
            }
            
            coords = region_coords.get(analysis.region, {"lat": 37.5665, "lng": 126.9780})
            
            url = "https://api.foursquare.com/v3/places/search"
            headers = {
                "Authorization": FOURSQUARE_API_KEY,
                "Accept": "application/json"
            }
            
            # 여러 키워드로 검색 시도
            for keyword in analysis.search_keywords:
                params = {
                    "query": keyword,
                    "ll": f"{coords['lat']},{coords['lng']}",
                    "radius": 50000,  # 50km
                    "limit": 5
                }
                
                async with aiohttp.ClientSession() as session:
                    async with session.get(url, headers=headers, params=params) as response:
                        if response.status == 200:
                            data = await response.json()
                            
                            if data.get("results"):
                                place = data["results"][0]
                                location = place.get("geocodes", {}).get("main", {})
                                
                                if location.get("latitude") and location.get("longitude"):
                                    result = PlaceResult(
                                        name=place.get("name", analysis.place_name),
                                        address=place.get("location", {}).get("formatted_address", ""),
                                        latitude=location["latitude"],
                                        longitude=location["longitude"],
                                        source="foursquare",
                                        rating=place.get("rating")
                                    )
                                    
                                    logger.info(f"✅ Foursquare 검색 성공: {result.name}")
                                    logger.info(f"   📍 주소: {result.address}")
                                    return result
                        else:
                            logger.warning(f"⚠️ Foursquare API 오류: {response.status}")
                            
        except Exception as e:
            logger.error(f"❌ Foursquare 검색 오류: {e}")
        
        return None

    @staticmethod
    async def search_kakao(analysis: LocationAnalysis) -> Optional[PlaceResult]:
        """2순위: Kakao API 검색 (교통시설 우선)"""
        if not KAKAO_REST_API_KEY:
            logger.warning("❌ Kakao API 키가 없습니다")
            return None
            
        # 교통시설은 카카오를 우선으로
        is_transport = any(word in analysis.place_name.lower() for word in 
                          ["역", "공항", "터미널", "정류장", "지하철", "기차"])
        
        if is_transport:
            logger.info(f"🚇 교통시설 우선 Kakao 검색: {analysis.place_name}")
        else:
            logger.info(f"🔍 2순위 Kakao 검색: {analysis.place_name}")
        
        try:
            url = "https://dapi.kakao.com/v2/local/search/keyword.json"
            headers = {"Authorization": f"KakaoAK {KAKAO_REST_API_KEY}"}
            
            # 지역 제한 검색
            region_filter = f"{analysis.region} {analysis.district}"
            
            for keyword in analysis.search_keywords:
                search_query = f"{region_filter} {keyword}"
                params = {
                    "query": search_query,
                    "size": 5
                }
                
                async with aiohttp.ClientSession() as session:
                    async with session.get(url, headers=headers, params=params) as response:
                        if response.status == 200:
                            data = await response.json()
                            
                            if data.get("documents"):
                                place = data["documents"][0]
                                
                                result = PlaceResult(
                                    name=place.get("place_name", analysis.place_name),
                                    address=place.get("road_address_name") or place.get("address_name", ""),
                                    latitude=float(place.get("y", 0)),
                                    longitude=float(place.get("x", 0)),
                                    source="kakao"
                                )
                                
                                logger.info(f"✅ Kakao 검색 성공: {result.name}")
                                logger.info(f"   📍 주소: {result.address}")
                                return result
                        else:
                            logger.warning(f"⚠️ Kakao API 오류: {response.status}")
                            
        except Exception as e:
            logger.error(f"❌ Kakao 검색 오류: {e}")
        
        return None

    @staticmethod
    async def search_google(analysis: LocationAnalysis) -> Optional[PlaceResult]:
        """3순위: Google Places API 검색"""
        if not GOOGLE_MAPS_API_KEY:
            logger.warning("❌ Google API 키가 없습니다")
            return None
            
        logger.info(f"🔍 3순위 Google 검색: {analysis.place_name}")
        
        try:
            url = "https://maps.googleapis.com/maps/api/place/findplacefromtext/json"
            
            for keyword in analysis.search_keywords:
                search_query = f"{analysis.region} {analysis.district} {keyword}"
                params = {
                    'input': search_query,
                    'inputtype': 'textquery',
                    'fields': 'name,formatted_address,geometry,rating',
                    'language': 'ko',
                    'region': 'kr',
                    'key': GOOGLE_MAPS_API_KEY
                }
                
                async with aiohttp.ClientSession() as session:
                    async with session.get(url, params=params) as response:
                        if response.status == 200:
                            data = await response.json()
                            
                            if data.get('status') == 'OK' and data.get('candidates'):
                                place = data['candidates'][0]
                                location = place['geometry']['location']
                                
                                result = PlaceResult(
                                    name=place.get('name', analysis.place_name),
                                    address=place.get('formatted_address', ''),
                                    latitude=location['lat'],
                                    longitude=location['lng'],
                                    source="google",
                                    rating=place.get('rating')
                                )
                                
                                logger.info(f"✅ Google 검색 성공: {result.name}")
                                logger.info(f"   📍 주소: {result.address}")
                                return result
                        else:
                            logger.warning(f"⚠️ Google API 오류: {response.status}")
                            
        except Exception as e:
            logger.error(f"❌ Google 검색 오류: {e}")
        
        return None

    @staticmethod
    async def search_triple_api(place_text: str) -> Optional[PlaceResult]:
        """3중 API 순차 검색 (교통시설은 Kakao 우선)"""
        logger.info(f"🎯 3중 API 검색 시작: {place_text}")
        
        # 1단계: GPT로 지역 분석
        analysis = await TripleLocationSearchService.analyze_location_with_gpt(place_text)
        logger.info(f"📊 분석 결과: {analysis.region} {analysis.district} - {analysis.place_name}")
        
        # 교통시설 체크
        is_transport = any(word in analysis.place_name.lower() for word in 
                          ["역", "공항", "터미널", "정류장", "지하철", "기차"])
        
        # 2단계: 검색 순서 결정
        if is_transport:
            # 교통시설: Kakao → Foursquare → Google
            search_methods = [
                ("Kakao (교통우선)", TripleLocationSearchService.search_kakao),
                ("Foursquare", TripleLocationSearchService.search_foursquare),
                ("Google", TripleLocationSearchService.search_google)
            ]
        else:
            # 일반시설: Foursquare → Kakao → Google
            search_methods = [
                ("Foursquare", TripleLocationSearchService.search_foursquare),
                ("Kakao", TripleLocationSearchService.search_kakao),
                ("Google", TripleLocationSearchService.search_google)
            ]
        
        for api_name, search_method in search_methods:
            try:
                result = await asyncio.wait_for(search_method(analysis), timeout=10)
                if result:
                    logger.info(f"🎉 {api_name}에서 검색 성공!")
                    return result
                else:
                    logger.info(f"⚠️ {api_name} 검색 결과 없음, 다음 API 시도...")
            except asyncio.TimeoutError:
                logger.warning(f"⏰ {api_name} 검색 타임아웃")
            except Exception as e:
                logger.error(f"❌ {api_name} 검색 오류: {e}")
        
        # 모든 API 실패 시 기본 좌표 반환
        logger.warning(f"⚠️ 모든 API 검색 실패, 기본 좌표 사용: {place_text}")
        region_defaults = {
            "제주": {"lat": 33.4996, "lng": 126.5312, "addr": "제주특별자치도"},
            "서울": {"lat": 37.5665, "lng": 126.9780, "addr": "서울특별시"},
            "부산": {"lat": 35.1796, "lng": 129.0756, "addr": "부산광역시"},
            "춘천": {"lat": 37.8817, "lng": 127.7297, "addr": "강원특별자치도 춘천시"}
        }
        
        for city, coords in region_defaults.items():
            if city in place_text:
                return PlaceResult(
                    name=place_text,
                    address=coords["addr"],
                    latitude=coords["lat"],
                    longitude=coords["lng"],
                    source="default"
                )
        
        return None

# ----- 비동기 위치 정보 보강 -----
async def enhance_locations_with_triple_api(schedule_data: Dict) -> Dict:
    """3중 API로 위치 정보 보강"""
    logger.info("🚀 3중 API 위치 정보 보강 시작")
    
    try:
        enhanced_data = json.loads(json.dumps(schedule_data))
        
        # 병렬 처리할 작업들
        tasks = []
        
        # 모든 일정 처리
        all_schedules = []
        all_schedules.extend(enhanced_data.get("fixedSchedules", []))
        all_schedules.extend(enhanced_data.get("flexibleSchedules", []))
        
        for schedule in all_schedules:
            task = enhance_single_schedule_triple(schedule)
            tasks.append(task)
        
        # 병렬 실행
        if tasks:
            results = await asyncio.gather(*tasks, return_exceptions=True)
            success_count = len([r for r in results if not isinstance(r, Exception)])
            logger.info(f"✅ 3중 API 위치 보강 완료: {success_count}/{len(tasks)}개 성공")
        
        return enhanced_data
        
    except Exception as e:
        logger.error(f"❌ 3중 API 위치 보강 실패: {e}")
        return schedule_data

async def enhance_single_schedule_triple(schedule: Dict):
    """단일 일정의 3중 API 위치 검색"""
    place_name = schedule.get("name", "")
    if not place_name:
        return schedule
    
    logger.info(f"🎯 3중 API 검색: {place_name}")
    
    try:
        result = await TripleLocationSearchService.search_triple_api(place_name)
        
        if result:
            schedule["location"] = result.address
            schedule["latitude"] = result.latitude
            schedule["longitude"] = result.longitude
            
            logger.info(f"✅ 위치 업데이트 완료: {place_name}")
            logger.info(f"   🏢 이름: {result.name}")
            logger.info(f"   📍 주소: {result.address}")
            logger.info(f"   🌍 좌표: {result.latitude}, {result.longitude}")
            logger.info(f"   🔗 출처: {result.source}")
        else:
            logger.warning(f"⚠️ 위치 검색 실패: {place_name}")
            
    except Exception as e:
        logger.error(f"❌ 위치 검색 오류: {place_name}, {e}")
    
    return schedule

# ----- 유틸리티 함수 -----
async def run_in_executor(func, *args, **kwargs):
    """동기 함수를 비동기로 실행"""
    loop = asyncio.get_event_loop()
    with ThreadPoolExecutor(max_workers=4) as executor:
        return await loop.run_in_executor(executor, func, *args, **kwargs)

def safe_parse_json(json_str):
    """안전한 JSON 파싱"""
    try:
        return json.loads(json_str)
    except json.JSONDecodeError as e:
        logger.error(f"JSON 파싱 오류: {str(e)}")
        return {
            "fixedSchedules": [],
            "flexibleSchedules": []
        }

def create_schedule_chain():
    """LangChain을 사용한 일정 추출 체인 생성 - 3개 일정 강제 추출"""
    current_time = int(datetime.datetime.now().timestamp() * 1000)
    
    today = datetime.datetime.now()
    tomorrow = today + datetime.timedelta(days=1)
    day_after_tomorrow = today + datetime.timedelta(days=2)
    
    template = """다음 음성 메시지에서 **모든 일정 정보**를 빠짐없이 추출하여 JSON 형식으로 반환해주세요.

음성 메시지: {input}

현재 날짜: {today_date}
내일: {tomorrow_date}
모레: {day_after_tomorrow_date}

**중요**: 메시지에 언급된 모든 장소와 활동을 개별 일정으로 추출하세요!

예시 입력: "제주공항에서 만나고, 성산일출봉에서 모임하고, 흑돼지 맛집에서 회식할거야"
→ 3개 일정: 1) 제주공항 2) 성산일출봉 3) 흑돼지 맛집 회식

다음 JSON 형식으로 반환:
{{
  "fixedSchedules": [
    {{
      "id": "{current_time}",
      "name": "첫 번째 장소명",
      "type": "FIXED",
      "duration": 60,
      "priority": 1,
      "location": "",
      "latitude": 33.5,
      "longitude": 126.5,
      "startTime": "2025-05-26T10:00:00",
      "endTime": "2025-05-26T11:00:00"
    }},
    {{
      "id": "{current_time_2}",
      "name": "두 번째 장소명",
      "type": "FIXED",
      "duration": 60,
      "priority": 2,
      "location": "",
      "latitude": 33.4,
      "longitude": 126.9,
      "startTime": "2025-05-26T12:00:00",
      "endTime": "2025-05-26T13:00:00"
    }},
    {{
      "id": "{current_time_3}",
      "name": "세 번째 장소명 (회식/식사/모임)",
      "type": "FIXED",
      "duration": 120,
      "priority": 3,
      "location": "",
      "latitude": 33.3,
      "longitude": 126.8,
      "startTime": "2025-05-26T18:00:00",
      "endTime": "2025-05-26T20:00:00"
    }}
  ],
  "flexibleSchedules": []
}}

주의사항:
1. **모든 언급된 장소를 개별 일정으로 추출**
2. 회식/식사는 duration을 120분으로 설정
3. 시간 간격을 두고 배치 (최소 1시간 간격)
4. "주말"은 토요일(26일)로 해석
5. JSON만 반환하고 다른 텍스트 포함 금지
"""
    
    prompt = PromptTemplate(
        template=template,
        input_variables=["input"],
        partial_variables={
            "current_time": str(current_time),
            "current_time_2": str(current_time + 1),
            "current_time_3": str(current_time + 2),
            "today_date": today.strftime("%Y-%m-%d"),
            "tomorrow_date": tomorrow.strftime("%Y-%m-%d"),
            "day_after_tomorrow_date": day_after_tomorrow.strftime("%Y-%m-%d")
        }
    )
    
    llm = ChatOpenAI(
        openai_api_key=OPENAI_API_KEY,
        model_name="gpt-3.5-turbo",
        temperature=0
    )
    
    parser = JsonOutputParser()
    chain = prompt | llm | parser
    
    return chain

# ----- 메인 엔드포인트 -----
@app.get("/")
async def root():
    return {"message": "3중 API (Foursquare+Kakao+Google) 정확한 주소 검색 일정 추출 API v3.0", "status": "running"}

@app.post("/extract-schedule", response_model=ExtractScheduleResponse)
async def extract_schedule(request: ScheduleRequest):
    """
    3중 API로 정확한 주소를 검색하는 일정 추출 API
    우선순위: Foursquare → Kakao → Google
    """
    start_time = time.time()
    logger.info(f"🎯 3중 API 일정 추출 시작: {request.voice_input}")
    
    try:
        # 🔥 1. 기본 일정 추출 (LLM 호출)
        llm_start = time.time()
        chain = create_schedule_chain()
        
        try:
            result = await asyncio.wait_for(
                run_in_executor(lambda: chain.invoke({"input": request.voice_input})),
                timeout=20
            )
            logger.info(f"✅ LLM 추출 완료: {time.time() - llm_start:.2f}초")
        except asyncio.TimeoutError:
            logger.error("❌ LLM 호출 타임아웃")
            return ExtractScheduleResponse(fixedSchedules=[], flexibleSchedules=[])
        
        # 🔥 2. 결과 파싱
        schedule_data = result if isinstance(result, dict) else safe_parse_json(str(result))
        
        # 🔥 3. 3중 API 위치 정보 보강 (가장 중요!)
        location_start = time.time()
        enhanced_data = await asyncio.wait_for(
            enhance_locations_with_triple_api(schedule_data),
            timeout=60  # 1분 타임아웃 (3개 API 순차 검색)
        )
        logger.info(f"✅ 3중 API 위치 검색 완료: {time.time() - location_start:.2f}초")
        
        # 🔥 4. 모든 스케줄러 모듈 활용 (기타 강화 작업들)
        try:
            # 시간 추론
            chains = create_enhancement_chain()
            enhanced_data = await asyncio.wait_for(
                run_in_executor(
                    apply_time_inference,
                    chains["time_chain"],
                    request.voice_input,
                    enhanced_data
                ),
                timeout=15
            )
            
            # 우선순위 분석
            enhanced_data = await asyncio.wait_for(
                run_in_executor(
                    apply_priorities,
                    chains["priority_chain"],
                    request.voice_input,
                    enhanced_data
                ),
                timeout=15
            )
            
            # 일정 간 관계 분석 (추가!)
            enhanced_data = await asyncio.wait_for(
                run_in_executor(
                    enhance_schedule_with_relationships,
                    request.voice_input,
                    enhanced_data
                ),
                timeout=10
            )
            
            # 충돌 해결
            enhanced_data = await asyncio.wait_for(
                run_in_executor(detect_and_resolve_time_conflicts, enhanced_data),
                timeout=10
            )
            
        except Exception as e:
            logger.warning(f"⚠️ 기타 강화 작업 스킵: {e}")
        
        # 🔥 5. 최종 데이터 정리
        all_schedules = []
        all_schedules.extend(enhanced_data.get("fixedSchedules", []))
        all_schedules.extend(enhanced_data.get("flexibleSchedules", []))
        
        fixed_schedules = [
            s for s in all_schedules 
            if s.get("type") == "FIXED" and "startTime" in s and "endTime" in s
        ]
        flexible_schedules = [
            s for s in all_schedules 
            if s.get("type") != "FIXED" or "startTime" not in s or "endTime" not in s
        ]
        
        final_data = {
            "fixedSchedules": fixed_schedules,
            "flexibleSchedules": flexible_schedules
        }
        
        total_time = time.time() - start_time
        logger.info(f"🎉 3중 API 전체 처리 완료: {total_time:.2f}초")
        logger.info(f"   📊 결과: 고정 {len(fixed_schedules)}개, 유연 {len(flexible_schedules)}개")
        
        # 결과 상세 로깅
        for i, schedule in enumerate(fixed_schedules):
            logger.info(f"   🔒 고정 {i+1}: {schedule.get('name')} - {schedule.get('location')}")
        for i, schedule in enumerate(flexible_schedules):
            logger.info(f"   🔄 유연 {i+1}: {schedule.get('name')} - {schedule.get('location')}")
        
        return ExtractScheduleResponse(**final_data)
            
    except Exception as e:
        logger.error(f"❌ 전체 처리 오류: {str(e)}")
        return ExtractScheduleResponse(fixedSchedules=[], flexibleSchedules=[])

# 서버 시작
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="0.0.0.0", port=8081, reload=True)