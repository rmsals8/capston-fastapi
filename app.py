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
def clean_korean_text(text: str) -> str:
    import re
    cleaned = re.sub(r'[^\w\s가-힣ㄱ-ㅎㅏ-ㅣ.,()-]', '', text)
    return cleaned.strip()
# ----- 모델 정의 -----
class ScheduleRequest(BaseModel):
    voice_input: str

class UnicodeJSONResponse(JSONResponse):
    def render(self, content) -> bytes:
        return json.dumps(
            content,
            ensure_ascii=False,  # 👈 핵심! 한글을 유니코드 그대로 출력
            separators=(',', ':'),
            indent=None
        ).encode('utf-8')  # 👈 UTF-8로 인코딩
    
class FixedSchedule(BaseModel):
    id: str
    name: str
    type: str = "FIXED"
    duration: int = 60
    priority: float  = 1.0
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
    priority: float  = 3.0
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


def safe_parse_json(json_str):
    """안전한 JSON 파싱 - 한글 지원"""
    try:
        if isinstance(json_str, str):
            # 한글 인코딩 문제 해결
            return json.loads(json_str, strict=False)
        else:
            return json_str
    except (json.JSONDecodeError, UnicodeDecodeError) as e:
        logger.error(f"JSON 파싱 오류 (한글 포함): {str(e)}")
        return {
            "fixedSchedules": [],
            "flexibleSchedules": []
        }

def normalize_priorities(schedules_data: Dict[str, Any]) -> Dict[str, Any]:
    """우선순위를 정수로 정규화"""
    logger.info("🔢 우선순위 정수 변환 시작")
    
    all_schedules = []
    all_schedules.extend(schedules_data.get("fixedSchedules", []))
    all_schedules.extend(schedules_data.get("flexibleSchedules", []))
    
    # 우선순위로 정렬
    all_schedules.sort(key=lambda s: s.get("priority", 999))
    
    # 1부터 시작하는 정수로 재할당
    for i, schedule in enumerate(all_schedules):
        old_priority = schedule.get("priority", "없음")
        new_priority = i + 1
        schedule["priority"] = new_priority
        logger.info(f"우선순위 정규화: '{schedule.get('name', '')}' {old_priority} → {new_priority}")
    
    # 다시 분류
    fixed_schedules = [s for s in all_schedules if s.get("type") == "FIXED" and "startTime" in s]
    flexible_schedules = [s for s in all_schedules if s.get("type") != "FIXED" or "startTime" not in s]
    
    logger.info(f"✅ 우선순위 정규화 완료: 고정 {len(fixed_schedules)}개, 유연 {len(flexible_schedules)}개")
    
    return {
        "fixedSchedules": fixed_schedules,
        "flexibleSchedules": flexible_schedules
    }
# ----- 주소 완전성 검증 및 재검색 시스템 -----
class AddressQualityChecker:
    """주소 완전성 검증 및 재검색 시스템"""
    
    @staticmethod
    def is_complete_address(address: str) -> bool:
        """주소 완전성 검증"""
        if not address or address.strip() == "":
            return False
        
        # 기본 검증
        address_lower = address.lower()
        
        # 1. 너무 짧은 주소 (단어 2개 이하)
        words = [word for word in address.split() if len(word) > 1]
        if len(words) <= 2:
            logger.info(f"❌ 주소 너무 짧음: {address} ({len(words)}개 단어)")
            return False
        
        # 2. 모호한 표현 체크
        vague_terms = ["근처", "인근", "주변", "근방", "부근", "일대", "동네"]
        if any(term in address for term in vague_terms):
            logger.info(f"❌ 모호한 주소 표현: {address}")
            return False
        
        # 3. 한국 주소 필수 요소 체크
        korean_regions = ["서울", "부산", "대구", "인천", "광주", "대전", "울산", "세종", "경기", "강원", "충북", "충남", "전북", "전남", "경북", "경남", "제주"]
        has_region = any(region in address for region in korean_regions)
        
        # 4. 상세 주소 요소 체크 (구/시/군 + 동/읍/면)
        detail_keywords = ["구", "시", "군", "동", "읍", "면", "로", "길", "가"]
        has_detail = any(keyword in address for keyword in detail_keywords)
        
        # 5. 건물명이나 번지수 체크
        import re
        has_number = bool(re.search(r'\d+', address))
        
        quality_score = has_region + has_detail + has_number
        is_complete = quality_score >= 2  # 3점 만점에 2점 이상
        
        logger.info(f"📊 주소 품질 점수: {quality_score}/3 - {address}")
        logger.info(f"   지역포함: {has_region}, 상세요소: {has_detail}, 번지포함: {has_number}")
        logger.info(f"   완전성: {'✅ 완전' if is_complete else '❌ 불완전'}")
        
        return is_complete
    
    @staticmethod
    def get_category_keywords(place_name: str) -> List[str]:
        """장소명에서 카테고리 키워드 추출"""
        name_lower = place_name.lower()
        keywords = []
        
        # 카테고리별 키워드 매핑
        category_map = {
            "카페": ["카페", "커피", "coffee", "dessert", "디저트", "베이커리"],
            "식당": ["식당", "맛집", "음식점", "레스토랑", "restaurant", "food"],
            "회의": ["회의실", "오피스", "사무실", "컨퍼런스", "meeting"],
            "회식": ["술집", "bar", "pub", "호프", "이자카야", "restaurant"],
            "쇼핑": ["쇼핑몰", "백화점", "마트", "상점", "mall"],
            "숙박": ["호텔", "모텔", "펜션", "게스트하우스", "리조트"]
        }
        
        for category, words in category_map.items():
            if any(word in name_lower for word in words):
                keywords.extend(words)
                logger.info(f"🏷️ 카테고리 '{category}' 감지: {words}")
                break
        
        # 기본 키워드가 없으면 장소명 그대로 사용
        if not keywords:
            keywords = [place_name]
        
        return list(set(keywords))  # 중복 제거
class TripleLocationSearchService:
    """Foursquare + Kakao + Google 3중 위치 검색 서비스"""
    
    @staticmethod
    async def analyze_location_with_gpt(text: str, reference_location: Optional[str] = None) -> LocationAnalysis:
        """GPT로 정확한 지역과 장소 분석 - 참조 위치 추가"""
        
        # set을 list로 변환하여 JSON 직렬화 가능하게 만들기
        korea_regions_list = {region: list(districts) for region, districts in KOREA_REGIONS.items()}
        regions_text = json.dumps(korea_regions_list, ensure_ascii=False, indent=2)
        
        # 참조 위치 정보 추가
        reference_context = ""
        if reference_location:
            reference_context = f"\n참조 위치 (이전 일정): {reference_location}"
            reference_context += "\n'근처', '주변' 같은 표현이 있으면 이 참조 위치 근처에서 검색하세요."
        
        prompt = f"""
다음 텍스트에서 한국의 정확한 지역 정보와 장소를 분석해주세요.

텍스트: "{text}"{reference_context}

한국 지역 정보:
{regions_text}

**중요**: 
1. "근처", "주변" 같은 표현이 있으면 참조 위치와 같은 지역으로 설정하세요.
2. 모호한 표현("카페", "식당")도 참조 위치 근처에서 검색하도록 지역을 설정하세요.
3. 구체적인 장소명(예: 울산대학교, 문수월드컵경기장)은 정확한 위치를 우선하세요.

JSON 형식으로 응답:
{{
  "place_name": "추출된 장소명",
  "region": "시/도 (참조 위치 고려)",
  "district": "시/군/구 (참조 위치 고려)",
  "category": "장소 카테고리",
  "search_keywords": ["검색에 사용할 키워드들", "지역명+장소명", "카테고리명"]
}}
"""

        try:
            response = openai_client.chat.completions.create(
                model="gpt-4-turbo",
                messages=[
                    {"role": "system", "content": "당신은 한국 지역 정보 전문가입니다. 참조 위치를 고려하여 '근처', '주변' 표현을 정확하게 해석하세요."},
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
            # 참조 위치가 있으면 같은 지역으로 기본값 설정
            if reference_location:
                # 참조 위치에서 지역 추출 시도
                for region in ["울산", "서울", "부산", "대구", "인천", "광주", "대전"]:
                    if region in reference_location:
                        return LocationAnalysis(
                            place_name=text,
                            region=f"{region}광역시" if region != "서울" else "서울특별시",
                            district="중구",  # 기본값
                            category="장소",
                            search_keywords=[f"{region} {text}", text]
                        )
            
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
        """1순위: Foursquare API 검색 - 카테고리 필터링 강화"""
        if not FOURSQUARE_API_KEY:
            logger.warning("❌ Foursquare API 키가 없습니다")
            return None
            
        logger.info(f"🔍 1순위 Foursquare 검색: {analysis.place_name}")
        
        try:
            # 지역 좌표 (기존과 동일)
            region_coords = {
                # 특별시·광역시
                "서울특별시": {"lat": 37.5665, "lng": 126.9780},
                "부산광역시": {"lat": 35.1796, "lng": 129.0756},
                "대구광역시": {"lat": 35.8714, "lng": 128.6014},
                "인천광역시": {"lat": 37.4563, "lng": 126.7052},
                "광주광역시": {"lat": 35.1595, "lng": 126.8526},
                "대전광역시": {"lat": 36.3504, "lng": 127.3845},
                "울산광역시": {"lat": 35.5384, "lng": 129.3114},
                
                # 특별자치시·특별자치도
                "세종특별자치시": {"lat": 36.4800, "lng": 127.2890},
                "제주특별자치도": {"lat": 33.4996, "lng": 126.5312},
                
                # 경기도 및 하위 시·군
                "경기도": {"lat": 37.4138, "lng": 127.5183},
                "가평군": {"lat": 37.8313, "lng": 127.5109},
                "고양시": {"lat": 37.6584, "lng": 126.8320},
                "과천시": {"lat": 37.4292, "lng": 126.9876},
                "광명시": {"lat": 37.4784, "lng": 126.8664},
                "광주시": {"lat": 37.4297, "lng": 127.2550},
                "구리시": {"lat": 37.5943, "lng": 127.1296},
                "군포시": {"lat": 37.3614, "lng": 126.9350},
                "김포시": {"lat": 37.6150, "lng": 126.7158},
                "남양주시": {"lat": 37.6369, "lng": 127.2165},
                "동두천시": {"lat": 37.9036, "lng": 127.0606},
                "부천시": {"lat": 37.5036, "lng": 126.7660},
                "성남시": {"lat": 37.4201, "lng": 127.1262},
                "수원시": {"lat": 37.2636, "lng": 127.0286},
                "시흥시": {"lat": 37.3803, "lng": 126.8030},
                "안산시": {"lat": 37.3236, "lng": 126.8219},
                "안성시": {"lat": 37.0078, "lng": 127.2797},
                "안양시": {"lat": 37.3943, "lng": 126.9568},
                "양주시": {"lat": 37.7853, "lng": 127.0456},
                "양평군": {"lat": 37.4916, "lng": 127.4874},
                "여주시": {"lat": 37.2982, "lng": 127.6376},
                "연천군": {"lat": 38.0960, "lng": 127.0751},
                "오산시": {"lat": 37.1499, "lng": 127.0776},
                "용인시": {"lat": 37.2411, "lng": 127.1776},
                "의왕시": {"lat": 37.3448, "lng": 126.9687},
                "의정부시": {"lat": 37.7381, "lng": 127.0339},
                "이천시": {"lat": 37.2724, "lng": 127.4349},
                "파주시": {"lat": 37.7598, "lng": 126.7800},
                "평택시": {"lat": 36.9921, "lng": 127.1127},
                "포천시": {"lat": 37.8950, "lng": 127.2003},
                "하남시": {"lat": 37.5394, "lng": 127.2147},
                "화성시": {"lat": 37.1996, "lng": 126.8310},
                
                # 강원특별자치도 및 하위 시·군
                "강원특별자치도": {"lat": 37.8228, "lng": 128.1555},
                "강릉시": {"lat": 37.7519, "lng": 128.8761},
                "고성군": {"lat": 38.3806, "lng": 128.4678},
                "동해시": {"lat": 37.5244, "lng": 129.1144},
                "삼척시": {"lat": 37.4501, "lng": 129.1649},
                "속초시": {"lat": 38.2070, "lng": 128.5918},
                "양구군": {"lat": 38.1065, "lng": 127.9897},
                "양양군": {"lat": 38.0759, "lng": 128.6190},
                "영월군": {"lat": 37.1839, "lng": 128.4617},
                "원주시": {"lat": 37.3422, "lng": 127.9202},
                "인제군": {"lat": 38.0695, "lng": 128.1707},
                "정선군": {"lat": 37.3801, "lng": 128.6607},
                "철원군": {"lat": 38.1465, "lng": 127.3134},
                "춘천시": {"lat": 37.8813, "lng": 127.7298},
                "태백시": {"lat": 37.1641, "lng": 128.9856},
                "평창군": {"lat": 37.3708, "lng": 128.3897},
                "홍천군": {"lat": 37.6971, "lng": 127.8888},
                "화천군": {"lat": 38.1063, "lng": 127.7082},
                "횡성군": {"lat": 37.4916, "lng": 127.9856},
                
                # 충청북도 및 하위 시·군
                "충청북도": {"lat": 36.4919, "lng": 127.7417},
                "괴산군": {"lat": 36.8154, "lng": 127.7874},
                "단양군": {"lat": 36.9845, "lng": 128.3659},
                "보은군": {"lat": 36.4894, "lng": 127.7293},
                "영동군": {"lat": 36.1750, "lng": 127.7764},
                "옥천군": {"lat": 36.3061, "lng": 127.5721},
                "음성군": {"lat": 36.9433, "lng": 127.6864},
                "제천시": {"lat": 37.1326, "lng": 128.1909},
                "증평군": {"lat": 36.7848, "lng": 127.5814},
                "진천군": {"lat": 36.8565, "lng": 127.4335},
                "청주시": {"lat": 36.4919, "lng": 127.7417},
                "충주시": {"lat": 36.9910, "lng": 127.9259},
                
                # 충청남도 및 하위 시·군
                "충청남도": {"lat": 36.5184, "lng": 126.8000},
                "계룡시": {"lat": 36.2742, "lng": 127.2489},
                "공주시": {"lat": 36.4464, "lng": 127.1248},
                "금산군": {"lat": 36.1088, "lng": 127.4881},
                "논산시": {"lat": 36.1872, "lng": 127.0985},
                "당진시": {"lat": 36.8934, "lng": 126.6292},
                "보령시": {"lat": 36.3334, "lng": 126.6127},
                "부여군": {"lat": 36.2756, "lng": 126.9098},
                "서산시": {"lat": 36.7848, "lng": 126.4503},
                "서천군": {"lat": 36.0805, "lng": 126.6919},
                "아산시": {"lat": 36.7898, "lng": 127.0019},
                "예산군": {"lat": 36.6826, "lng": 126.8503},
                "천안시": {"lat": 36.8151, "lng": 127.1139},
                "청양군": {"lat": 36.4590, "lng": 126.8025},
                "태안군": {"lat": 36.7456, "lng": 126.2983},
                "홍성군": {"lat": 36.6012, "lng": 126.6608},
                
                # 전북특별자치도 및 하위 시·군
                "전북특별자치도": {"lat": 35.7175, "lng": 127.1530},
                "고창군": {"lat": 35.4346, "lng": 126.7017},
                "군산시": {"lat": 35.9678, "lng": 126.7368},
                "김제시": {"lat": 35.8033, "lng": 126.8805},
                "남원시": {"lat": 35.4163, "lng": 127.3906},
                "무주군": {"lat": 36.0073, "lng": 127.6610},
                "부안군": {"lat": 35.7318, "lng": 126.7332},
                "순창군": {"lat": 35.3748, "lng": 127.1374},
                "완주군": {"lat": 35.9058, "lng": 127.1649},
                "익산시": {"lat": 35.9483, "lng": 126.9575},
                "임실군": {"lat": 35.6176, "lng": 127.2896},
                "장수군": {"lat": 35.6477, "lng": 127.5217},
                "전주시": {"lat": 35.8242, "lng": 127.1480},
                "정읍시": {"lat": 35.5700, "lng": 126.8557},
                "진안군": {"lat": 35.7917, "lng": 127.4244},
                
                # 전라남도 및 하위 시·군
                "전라남도": {"lat": 34.8679, "lng": 126.9910},
                "강진군": {"lat": 34.6417, "lng": 126.7669},
                "고흥군": {"lat": 34.6111, "lng": 127.2855},
                "곡성군": {"lat": 35.2818, "lng": 127.2914},
                "광양시": {"lat": 34.9406, "lng": 127.5956},
                "구례군": {"lat": 35.2020, "lng": 127.4632},
                "나주시": {"lat": 35.0160, "lng": 126.7107},
                "담양군": {"lat": 35.3214, "lng": 126.9882},
                "목포시": {"lat": 34.8118, "lng": 126.3922},
                "무안군": {"lat": 34.9900, "lng": 126.4816},
                "보성군": {"lat": 34.7712, "lng": 127.0800},
                "순천시": {"lat": 34.9507, "lng": 127.4872},
                "신안군": {"lat": 34.8267, "lng": 126.1063},
                "여수시": {"lat": 34.7604, "lng": 127.6622},
                "영광군": {"lat": 35.2773, "lng": 126.5120},
                "영암군": {"lat": 34.8000, "lng": 126.6968},
                "완도군": {"lat": 34.3105, "lng": 126.7551},
                "장성군": {"lat": 35.3017, "lng": 126.7886},
                "장흥군": {"lat": 34.6816, "lng": 126.9066},
                "진도군": {"lat": 34.4867, "lng": 126.2636},
                "함평군": {"lat": 35.0666, "lng": 126.5168},
                "해남군": {"lat": 34.5736, "lng": 126.5986},
                "화순군": {"lat": 35.0648, "lng": 126.9855},
                
                # 경상북도 및 하위 시·군
                "경상북도": {"lat": 36.4919, "lng": 128.8889},
                "경산시": {"lat": 35.8251, "lng": 128.7411},
                "경주시": {"lat": 35.8562, "lng": 129.2247},
                "고령군": {"lat": 35.7284, "lng": 128.2634},
                "구미시": {"lat": 36.1196, "lng": 128.3441},
                "군위군": {"lat": 36.2393, "lng": 128.5717},
                "김천시": {"lat": 36.1395, "lng": 128.1137},
                "문경시": {"lat": 36.5866, "lng": 128.1866},
                "봉화군": {"lat": 36.8932, "lng": 128.7327},
                "상주시": {"lat": 36.4107, "lng": 128.1590},
                "성주군": {"lat": 35.9186, "lng": 128.2829},
                "안동시": {"lat": 36.5684, "lng": 128.7294},
                "영덕군": {"lat": 36.4153, "lng": 129.3655},
                "영양군": {"lat": 36.6666, "lng": 129.1124},
                "영주시": {"lat": 36.8056, "lng": 128.6239},
                "영천시": {"lat": 35.9733, "lng": 128.9386},
                "예천군": {"lat": 36.6580, "lng": 128.4517},
                "울릉군": {"lat": 37.4845, "lng": 130.9058},
                "울진군": {"lat": 36.9930, "lng": 129.4004},
                "의성군": {"lat": 36.3526, "lng": 128.6974},
                "청도군": {"lat": 35.6477, "lng": 128.7363},
                "청송군": {"lat": 36.4359, "lng": 129.0572},
                "칠곡군": {"lat": 35.9951, "lng": 128.4019},
                "포항시": {"lat": 36.0190, "lng": 129.3435},
                
                # 경상남도 및 하위 시·군
                "경상남도": {"lat": 35.4606, "lng": 128.2132},
                "거제시": {"lat": 34.8804, "lng": 128.6212},
                "거창군": {"lat": 35.6869, "lng": 127.9095},
                "고성군": {"lat": 34.9735, "lng": 128.3229},
                "김해시": {"lat": 35.2342, "lng": 128.8899},
                "남해군": {"lat": 34.8375, "lng": 127.8926},
                "밀양시": {"lat": 35.5040, "lng": 128.7469},
                "사천시": {"lat": 35.0036, "lng": 128.0645},
                "산청군": {"lat": 35.4150, "lng": 127.8736},
                "양산시": {"lat": 35.3350, "lng": 129.0371},
                "의령군": {"lat": 35.3219, "lng": 128.2618},
                "진주시": {"lat": 35.1800, "lng": 128.1076},
                "창녕군": {"lat": 35.5444, "lng": 128.4924},
                "창원시": {"lat": 35.2281, "lng": 128.6811},
                "통영시": {"lat": 34.8544, "lng": 128.4331},
                "하동군": {"lat": 35.0675, "lng": 127.7514},
                "함안군": {"lat": 35.2730, "lng": 128.4069},
                "함양군": {"lat": 35.5203, "lng": 127.7252},
                "합천군": {"lat": 35.5666, "lng": 128.1655},
            }
                        
            coords = region_coords.get(analysis.region, {"lat": 37.5665, "lng": 126.9780})
            
            url = "https://api.foursquare.com/v3/places/search"
            headers = {
                "Authorization": FOURSQUARE_API_KEY,
                "Accept": "application/json"
            }
            
            # 카테고리별 필터링 추가
            category_filters = {
                "대학교": ["대학교", "대학", "university", "college"],
                "경기장": ["경기장", "stadium", "스포츠", "축구"],
                "식당": ["식당", "레스토랑", "restaurant", "음식", "맛집"],
                "카페": ["카페", "커피", "coffee", "cafe", "디저트"]
            }
            
            # 검색 전략 개선
            search_strategies = []
            
            # 1) 구체적인 장소명 (대학교, 경기장 등)
            if any(keyword in analysis.place_name.lower() for keyword in ['대학교', '경기장', '월드컵', '공항', '역']):
                search_strategies.append(analysis.place_name)
            
            # 2) 지역명 + 장소명
            region_name = analysis.region.replace('특별시', '').replace('광역시', '')
            search_strategies.append(f"{region_name} {analysis.place_name}")
            
            # 3) 카테고리별 특화 검색
            place_lower = analysis.place_name.lower()
            if "식당" in place_lower or "restaurant" in analysis.category.lower():
                search_strategies.extend([
                    f"{region_name} 맛집",
                    f"{region_name} 식당",
                    f"{region_name} restaurant"
                ])
            elif "카페" in place_lower or "cafe" in analysis.category.lower():
                search_strategies.extend([
                    f"{region_name} 카페",
                    f"{region_name} 커피",
                    f"{region_name} cafe"
                ])
            
            logger.info(f"🔍 검색 전략: {search_strategies}")
            
            for strategy in search_strategies:
                try:
                    params = {
                        "query": strategy,
                        "ll": f"{coords['lat']},{coords['lng']}",
                        "radius": 15000,
                        "limit": 15,
                        "sort": "DISTANCE"
                    }
                    
                    logger.info(f"🔍 Foursquare 검색어: '{strategy}'")
                    
                    async with aiohttp.ClientSession() as session:
                        async with session.get(url, headers=headers, params=params) as response:
                            if response.status == 200:
                                data = await response.json()
                                
                                if data.get("results"):
                                    logger.info(f"✅ Foursquare 결과 {len(data['results'])}개 발견")
                                    
                                    # 카테고리 일치 점수 계산 강화
                                    for i, place in enumerate(data["results"]):
                                        location = place.get("geocodes", {}).get("main", {})
                                        address = place.get("location", {}).get("formatted_address", "")
                                        place_name = place.get("name", "")
                                        
                                        logger.info(f"   후보 {i+1}: {place_name} - {address}")
                                        
                                        if not (location.get("latitude") and location.get("longitude")):
                                            continue
                                        
                                        # 지역 일치 확인
                                        region_keywords = [
                                            analysis.region.replace('특별시', '').replace('광역시', ''),
                                            analysis.district
                                        ]
                                        region_match = any(keyword in address for keyword in region_keywords if keyword)
                                        
                                        # 장소명 유사도 확인 (강화)
                                        name_similarity = 0
                                        search_terms = analysis.place_name.lower().split()
                                        place_terms = place_name.lower().split()
                                        
                                        for term in search_terms:
                                            if len(term) > 1:
                                                if any(term in pt for pt in place_terms):
                                                    name_similarity += 1
                                        
                                        # 카테고리 일치 확인 (새로 추가)
                                        category_match = 0
                                        for category, keywords in category_filters.items():
                                            if category in analysis.place_name.lower():
                                                for keyword in keywords:
                                                    if keyword in place_name.lower():
                                                        category_match += 1
                                                        break
                                        
                                        # 부정적인 카테고리 필터링 (학원, 병원 등 제외)
                                        negative_keywords = ["학원", "병원", "의원", "클리닉", "academy", "hospital"]
                                        is_negative = any(neg in place_name.lower() for neg in negative_keywords)
                                        
                                        # 종합 점수 계산
                                        score = (1 if region_match else 0) + (name_similarity * 0.5) + (category_match * 0.3)
                                        
                                        # 부정적 키워드가 있으면 점수 대폭 감소
                                        if is_negative:
                                            score = max(0, score - 1.0)
                                        
                                        logger.info(f"     지역일치: {region_match}, 이름유사도: {name_similarity}, 카테고리매치: {category_match}, 부정적: {is_negative}, 점수: {score}")
                                        
                                        # 최소 점수 기준 상향 조정
                                        if score >= 1.0:  # 0.5 → 1.0으로 상향
                                            result = PlaceResult(
                                                name=place_name,
                                                address=address,
                                                latitude=location["latitude"],
                                                longitude=location["longitude"],
                                                source="foursquare",
                                                rating=place.get("rating")
                                            )
                                            
                                            logger.info(f"✅ Foursquare 검색 성공: {result.name}")
                                            logger.info(f"   📍 주소: {result.address}")
                                            return result
                                    
                                    logger.info(f"⚠️ 검색어 '{strategy}' - 적절한 결과 없음")
                                else:
                                    logger.info(f"⚠️ 검색어 '{strategy}' - 결과 없음")
                            else:
                                logger.warning(f"⚠️ Foursquare API 오류: {response.status}")
                                
                except Exception as e:
                    logger.error(f"❌ 검색어 '{strategy}' 오류: {e}")
                    continue
                    
        except Exception as e:
            logger.error(f"❌ Foursquare 검색 전체 오류: {e}")
        
        logger.warning(f"⚠️ Foursquare 모든 검색 실패: {analysis.place_name}")
        return None

    @staticmethod
    async def enhanced_search_with_quality_check(place_text: str) -> Optional[PlaceResult]:
        """주소 완전성 검증과 재검색을 포함한 향상된 검색"""
        logger.info(f"🔍 향상된 품질 검증 검색 시작: {place_text}")
        
        # 1단계: 기본 3중 API 검색
        result = await TripleLocationSearchService.search_triple_api(place_text)
        
        # 2단계: 주소 완전성 검증
        if result and AddressQualityChecker.is_complete_address(result.address):
            logger.info(f"✅ 1차 검색 성공 (완전한 주소): {result.address}")
            return result
        
        logger.warning(f"⚠️ 1차 검색 결과 불완전: {result.address if result else 'None'}")
        
        # 3단계: 재검색 전략
        analysis = await TripleLocationSearchService.analyze_location_with_gpt(place_text)
        category_keywords = AddressQualityChecker.get_category_keywords(place_text)
        
        logger.info(f"🔄 재검색 시작 - 카테고리 키워드: {category_keywords}")
        
        # 4단계: 확장 검색 (반경 확대 + 카테고리 키워드)
        for radius in [1000, 2000, 5000, 10000]:  # 1km → 10km까지 확대
            logger.info(f"🔍 확장 검색 (반경 {radius}m)")
            
            for keyword in category_keywords:
                enhanced_query = f"{analysis.region} {analysis.district} {keyword}"
                
                # Kakao 확장 검색
                kakao_result = await TripleLocationSearchService.search_kakao_enhanced(
                    analysis, enhanced_query, radius
                )
                
                if kakao_result and AddressQualityChecker.is_complete_address(kakao_result.address):
                    logger.info(f"✅ Kakao 확장 검색 성공: {kakao_result.address}")
                    return kakao_result
                
                # Google 확장 검색
                google_result = await TripleLocationSearchService.search_google_enhanced(
                    analysis, enhanced_query
                )
                
                if google_result and AddressQualityChecker.is_complete_address(google_result.address):
                    logger.info(f"✅ Google 확장 검색 성공: {google_result.address}")
                    return google_result
        
        # 5단계: 모든 검색 실패시 기본값 반환 (주소가 완전하지 않더라도)
        if result:
            logger.warning(f"⚠️ 확장 검색 실패, 1차 결과 사용: {result.address}")
            return result
        
        logger.error(f"❌ 모든 검색 실패: {place_text}")
        return None

    @staticmethod
    async def search_kakao_enhanced(analysis: LocationAnalysis, query: str, radius: int) -> Optional[PlaceResult]:
        """Kakao API 확장 검색"""
        if not KAKAO_REST_API_KEY:
            return None
            
        try:
            url = "https://dapi.kakao.com/v2/local/search/keyword.json"
            headers = {"Authorization": f"KakaoAK {KAKAO_REST_API_KEY}"}
            
            params = {
                "query": query,
                "size": 10,  # 더 많은 결과 가져오기
                "radius": radius
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers, params=params) as response:
                    if response.status == 200:
                        data = await response.json()
                        
                        if data.get("documents"):
                            # 가장 완전한 주소를 가진 결과 선택
                            for place in data["documents"]:
                                address = place.get("road_address_name") or place.get("address_name", "")
                                
                                if AddressQualityChecker.is_complete_address(address):
                                    return PlaceResult(
                                        name=place.get("place_name", analysis.place_name),
                                        address=address,
                                        latitude=float(place.get("y", 0)),
                                        longitude=float(place.get("x", 0)),
                                        source="kakao_enhanced"
                                    )
                                    
        except Exception as e:
            logger.error(f"❌ Kakao 확장 검색 오류: {e}")
        
        return None

    @staticmethod
    async def search_google_enhanced(analysis: LocationAnalysis, query: str) -> Optional[PlaceResult]:
        """Google Places API 확장 검색 - 수정된 버전"""
        if not GOOGLE_MAPS_API_KEY:
            return None
            
        try:
            url = "https://maps.googleapis.com/maps/api/place/findplacefromtext/json"
            
            # 지역 제한 강화
            region_query = f"{analysis.region.replace('특별시', '').replace('광역시', '')} {analysis.district} {query}"
            
            params = {
                'input': region_query,
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
                            for place in data['candidates']:
                                address = place.get('formatted_address', '')
                                
                                # 지역 일치 확인 강화
                                region_match = any(region_name in address for region_name in 
                                                 [analysis.region.replace('특별시', '').replace('광역시', ''), 
                                                  analysis.district])
                                
                                if AddressQualityChecker.is_complete_address(address) and region_match:
                                    location = place['geometry']['location']
                                    return PlaceResult(
                                        name=place.get('name', analysis.place_name),
                                        address=address,
                                        latitude=location['lat'],
                                        longitude=location['lng'],
                                        source="google_enhanced",
                                        rating=place.get('rating')
                                    )
                                    
        except Exception as e:
            logger.error(f"❌ Google 확장 검색 오류: {e}")
        
        return None


    @staticmethod
    async def search_kakao(analysis: LocationAnalysis) -> Optional[PlaceResult]:
        """1순위: Kakao API 검색 - 강화된 버전"""
        if not KAKAO_REST_API_KEY:
            logger.warning("❌ Kakao API 키가 없습니다")
            return None
            
        logger.info(f"🔍 1순위 Kakao 검색: {analysis.place_name}")
        
        try:
            url = "https://dapi.kakao.com/v2/local/search/keyword.json"
            headers = {"Authorization": f"KakaoAK {KAKAO_REST_API_KEY}"}
            
            # 검색 전략 - 구체적인 것부터 일반적인 것까지
            search_strategies = []
            
            # 1) 구체적 장소명 (대학교, 경기장 등)
            if any(keyword in analysis.place_name.lower() for keyword in ['대학교', '경기장', '월드컵', '공항', '역']):
                search_strategies.append(analysis.place_name)
                search_strategies.append(f"{analysis.region.replace('광역시', '').replace('특별시', '')} {analysis.place_name}")
            
            # 2) 카테고리별 검색
            place_lower = analysis.place_name.lower()
            region_name = analysis.region.replace('광역시', '').replace('특별시', '')
            
            if any(word in place_lower for word in ['식당', 'restaurant', '맛집']):
                search_strategies.extend([
                    f"{region_name} {analysis.district} 맛집",
                    f"{region_name} {analysis.district} 식당",
                    f"{region_name} 맛집",
                    f"{region_name} 식당"
                ])
            elif any(word in place_lower for word in ['카페', 'cafe', '커피']):
                search_strategies.extend([
                    f"{region_name} {analysis.district} 카페",
                    f"{region_name} {analysis.district} 커피",
                    f"{region_name} 카페",
                    f"{region_name} 커피숍"
                ])
            else:
                # 일반 검색
                search_strategies.extend([
                    f"{region_name} {analysis.place_name}",
                    f"{region_name} {analysis.district} {analysis.place_name}"
                ])
            
            logger.info(f"🔍 Kakao 검색 전략: {search_strategies}")
            
            for strategy in search_strategies:
                try:
                    params = {
                        "query": strategy,
                        "size": 15,  # 더 많은 결과
                        "sort": "accuracy"  # 정확도순
                    }
                    
                    logger.info(f"🔍 Kakao 검색어: '{strategy}'")
                    
                    async with aiohttp.ClientSession() as session:
                        async with session.get(url, headers=headers, params=params) as response:
                            if response.status == 200:
                                data = await response.json()
                                
                                if data.get("documents"):
                                    logger.info(f"✅ Kakao 결과 {len(data['documents'])}개 발견")
                                    
                                    for i, place in enumerate(data["documents"]):
                                        place_name = place.get("place_name", "")
                                        address = place.get("road_address_name") or place.get("address_name", "")
                                        category = place.get("category_name", "")
                                        
                                        logger.info(f"   후보 {i+1}: {place_name} - {address} ({category})")
                                        
                                        if not address.strip():
                                            continue
                                        
                                        # 지역 일치 확인
                                        region_keywords = [
                                            analysis.region.replace('광역시', '').replace('특별시', ''),
                                            analysis.district
                                        ]
                                        region_match = any(keyword in address for keyword in region_keywords if keyword)
                                        
                                        # 카테고리 적합성 확인
                                        category_match = False
                                        if "식당" in analysis.place_name.lower() or "restaurant" in analysis.category.lower():
                                            category_match = any(word in category for word in ["음식점", "식당", "레스토랑", "한식", "중식", "일식", "양식", "카페"])
                                        elif "카페" in analysis.place_name.lower() or "cafe" in analysis.category.lower():
                                            category_match = any(word in category for word in ["카페", "커피", "디저트", "베이커리"])
                                        elif "대학교" in analysis.place_name.lower():
                                            category_match = any(word in category for word in ["대학교", "학교", "교육"])
                                        elif "경기장" in analysis.place_name.lower():
                                            category_match = any(word in category for word in ["스포츠", "경기장", "체육"])
                                        else:
                                            category_match = True  # 기타는 일단 허용
                                        
                                        # 부정적 키워드 필터
                                        negative_keywords = ["학원", "병원", "의원", "클리닉", "약국"]
                                        is_negative = any(neg in place_name for neg in negative_keywords)
                                        
                                        # 점수 계산
                                        score = 0
                                        if region_match:
                                            score += 2
                                        if category_match:
                                            score += 1
                                        if is_negative:
                                            score -= 2
                                        
                                        logger.info(f"     지역일치: {region_match}, 카테고리적합: {category_match}, 부정적: {is_negative}, 점수: {score}")
                                        
                                        if score >= 1:  # 최소 점수
                                            result = PlaceResult(
                                                name=place_name,
                                                address=address,
                                                latitude=float(place.get("y", 0)),
                                                longitude=float(place.get("x", 0)),
                                                source="kakao"
                                            )
                                            
                                            logger.info(f"✅ Kakao 검색 성공: {result.name}")
                                            logger.info(f"   📍 주소: {result.address}")
                                            logger.info(f"   🏷️ 카테고리: {category}")
                                            return result
                                    
                                    logger.info(f"⚠️ Kakao 검색어 '{strategy}' - 적절한 결과 없음")
                                else:
                                    logger.info(f"⚠️ Kakao 검색어 '{strategy}' - 결과 없음")
                            else:
                                logger.warning(f"⚠️ Kakao API 오류: {response.status}")
                                
                except Exception as e:
                    logger.error(f"❌ Kakao 검색어 '{strategy}' 오류: {e}")
                    continue
                    
        except Exception as e:
            logger.error(f"❌ Kakao 검색 전체 오류: {e}")
        
        logger.warning(f"⚠️ Kakao 모든 검색 실패: {analysis.place_name}")
        return None

    @staticmethod
    async def search_google(analysis: LocationAnalysis) -> Optional[PlaceResult]:
        """2순위: Google Places API 검색 - 강화된 버전"""
        if not GOOGLE_MAPS_API_KEY:
            logger.warning("❌ Google API 키가 없습니다")
            return None
            
        logger.info(f"🔍 2순위 Google 검색: {analysis.place_name}")
        
        try:
            url = "https://maps.googleapis.com/maps/api/place/findplacefromtext/json"
            
            # 검색 전략
            region_name = analysis.region.replace('광역시', '').replace('특별시', '')
            search_strategies = []
            
            # 구체적 장소명
            if any(keyword in analysis.place_name.lower() for keyword in ['대학교', '경기장', '월드컵']):
                search_strategies.extend([
                    f"{region_name} {analysis.place_name}",
                    analysis.place_name
                ])
            
            # 카테고리별 검색
            place_lower = analysis.place_name.lower()
            if any(word in place_lower for word in ['식당', 'restaurant']):
                search_strategies.extend([
                    f"{region_name} {analysis.district} restaurant",
                    f"{region_name} 맛집"
                ])
            elif any(word in place_lower for word in ['카페', 'cafe']):
                search_strategies.extend([
                    f"{region_name} {analysis.district} cafe",
                    f"{region_name} 카페"
                ])
            
            logger.info(f"🔍 Google 검색 전략: {search_strategies}")
            
            for strategy in search_strategies:
                try:
                    params = {
                        'input': strategy,
                        'inputtype': 'textquery',
                        'fields': 'name,formatted_address,geometry,rating,types',
                        'language': 'ko',
                        'region': 'kr',
                        'key': GOOGLE_MAPS_API_KEY
                    }
                    
                    logger.info(f"🔍 Google 검색어: '{strategy}'")
                    
                    async with aiohttp.ClientSession() as session:
                        async with session.get(url, params=params) as response:
                            if response.status == 200:
                                data = await response.json()
                                
                                if data.get('status') == 'OK' and data.get('candidates'):
                                    logger.info(f"✅ Google 결과 {len(data['candidates'])}개 발견")
                                    
                                    for i, place in enumerate(data['candidates']):
                                        place_name = place.get('name', '')
                                        address = place.get('formatted_address', '')
                                        types = place.get('types', [])
                                        
                                        logger.info(f"   후보 {i+1}: {place_name} - {address}")
                                        logger.info(f"     타입: {types}")
                                        
                                        # 지역 일치 확인
                                        region_keywords = [region_name, analysis.district]
                                        region_match = any(keyword in address for keyword in region_keywords if keyword)
                                        
                                        # 타입 적합성 확인
                                        type_match = False
                                        if "식당" in analysis.place_name.lower():
                                            type_match = any(t in types for t in ["restaurant", "food", "meal_takeaway"])
                                        elif "카페" in analysis.place_name.lower():  
                                            type_match = any(t in types for t in ["cafe", "bakery"])
                                        elif "대학교" in analysis.place_name.lower():
                                            type_match = any(t in types for t in ["university", "school"])
                                        elif "경기장" in analysis.place_name.lower():
                                            type_match = any(t in types for t in ["stadium", "gym"])
                                        else:
                                            type_match = True
                                        
                                        score = (1 if region_match else 0) + (1 if type_match else 0)
                                        logger.info(f"     지역일치: {region_match}, 타입적합: {type_match}, 점수: {score}")
                                        
                                        if score >= 1:
                                            location = place['geometry']['location']
                                            result = PlaceResult(
                                                name=place_name,
                                                address=address,
                                                latitude=location['lat'],
                                                longitude=location['lng'],
                                                source="google",
                                                rating=place.get('rating')
                                            )
                                            
                                            logger.info(f"✅ Google 검색 성공: {result.name}")
                                            logger.info(f"   📍 주소: {result.address}")
                                            return result
                                    
                                    logger.info(f"⚠️ Google 검색어 '{strategy}' - 적절한 결과 없음")
                                else:
                                    logger.info(f"⚠️ Google API 응답: {data.get('status', 'UNKNOWN')}")
                            else:
                                logger.warning(f"⚠️ Google API 오류: {response.status}")
                                
                except Exception as e:
                    logger.error(f"❌ Google 검색어 '{strategy}' 오류: {e}")
                    continue
                    
        except Exception as e:
            logger.error(f"❌ Google 검색 전체 오류: {e}")
        
        logger.warning(f"⚠️ Google 모든 검색 실패: {analysis.place_name}")
        return None

    @staticmethod
    async def search_triple_api(place_text: str) -> Optional[PlaceResult]:
        """3중 API 순차 검색 - 카카오 우선으로 변경"""
        logger.info(f"🎯 3중 API 검색 시작: {place_text}")
        
        # 1단계: GPT로 지역 분석
        analysis = await TripleLocationSearchService.analyze_location_with_gpt(place_text)
        logger.info(f"📊 분석 결과: {analysis.region} {analysis.district} - {analysis.place_name}")
        
        # 2단계: 검색 순서 결정 - 카카오 우선!
        search_methods = [
            ("Kakao (1순위)", TripleLocationSearchService.search_kakao),
            ("Google (2순위)", TripleLocationSearchService.search_google),
            ("Foursquare (3순위)", TripleLocationSearchService.search_foursquare)
        ]
        
        for api_name, search_method in search_methods:
            try:
                result = await asyncio.wait_for(search_method(analysis), timeout=10)
                if result and result.address and result.address.strip():
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
        return None

# ----- 비동기 위치 정보 보강 -----
async def enhance_locations_with_triple_api(schedule_data: Dict) -> Dict:
    """3중 API로 위치 정보 보강 - 참조 위치 활용"""
    logger.info("🚀 3중 API 위치 정보 보강 시작")
    
    try:
        enhanced_data = json.loads(json.dumps(schedule_data))
        
        # 모든 일정 수집 (순서대로)
        all_schedules = []
        all_schedules.extend(enhanced_data.get("fixedSchedules", []))
        all_schedules.extend(enhanced_data.get("flexibleSchedules", []))
        
        # 순차적으로 처리하여 이전 일정의 위치를 참조로 활용
        processed_schedules = []
        
        for i, schedule in enumerate(all_schedules):
            # 이전 처리된 일정들을 참조로 전달
            enhanced_schedule = await enhance_single_schedule_triple(schedule, processed_schedules)
            processed_schedules.append(enhanced_schedule)
        
        logger.info(f"✅ 3중 API 위치 보강 완료: {len(processed_schedules)}개 처리")
        
        return enhanced_data
        
    except Exception as e:
        logger.error(f"❌ 3중 API 위치 보강 실패: {e}")
        return schedule_data

def _is_reasonable_distance(address1: str, address2: str) -> bool:
    """두 주소가 합리적인 거리 내에 있는지 확인"""
    try:
        # 시/도 단위 비교
        regions1 = ["서울", "부산", "대구", "인천", "광주", "대전", "울산", "세종", "경기", "강원", "충북", "충남", "전북", "전남", "경북", "경남", "제주"]
        
        region1 = None
        region2 = None
        
        for region in regions1:
            if region in address1:
                region1 = region
            if region in address2:
                region2 = region
        
        # 같은 광역시/도면 OK
        if region1 == region2:
            return True
        
        # 인접 지역 허용 (예: 서울-경기, 부산-경남 등)
        adjacent_regions = {
            "서울": ["경기"],
            "경기": ["서울", "강원", "충북", "충남"],
            "부산": ["경남"],
            "경남": ["부산", "경북"],
            "울산": ["경남", "경북"],
            "대구": ["경북", "경남"]
        }
        
        if region1 in adjacent_regions and region2 in adjacent_regions[region1]:
            return True
        if region2 in adjacent_regions and region1 in adjacent_regions[region2]:
            return True
            
        # 그 외는 너무 멀다고 판단
        logger.info(f"📏 거리 체크: {region1} vs {region2} - 너무 멀음")
        return False
        
    except Exception:
        return True  # 오류 시 허용
    
async def enhance_single_schedule_triple(schedule: Dict, reference_schedules: List[Dict] = None):
    """단일 일정의 3중 API + 품질 검증 위치 검색 - 카카오 우선"""
    place_name = schedule.get("name", "")
    if not place_name:
        return schedule
    
    logger.info(f"🎯 품질 검증 위치 검색: {place_name}")
    
    # 참조 위치 찾기
    reference_location = None
    if reference_schedules:
        for ref_schedule in reference_schedules:
            if ref_schedule.get("location") and ref_schedule["location"].strip():
                reference_location = ref_schedule["location"]
                logger.info(f"📍 참조 위치 설정: {reference_location}")
                break
    
    try:
        # 참조 위치를 고려한 분석
        analysis = await TripleLocationSearchService.analyze_location_with_gpt(place_name, reference_location)
        
        # 카카오 우선 검색 순서
        search_methods = [
            ("Kakao", TripleLocationSearchService.search_kakao),
            ("Google", TripleLocationSearchService.search_google),
            ("Foursquare", TripleLocationSearchService.search_foursquare)
        ]
        
        for api_name, search_method in search_methods:
            try:
                result = await asyncio.wait_for(search_method(analysis), timeout=10)
                if result and result.address and result.address.strip():
                    # 참조 위치와의 거리 체크
                    if reference_location and not _is_reasonable_distance(reference_location, result.address):
                        logger.warning(f"⚠️ {api_name} 결과가 참조 위치와 너무 멀어서 제외: {result.address}")
                        continue
                    
                    schedule["location"] = result.address
                    schedule["latitude"] = result.latitude
                    schedule["longitude"] = result.longitude
                    
                    logger.info(f"✅ {api_name} 위치 업데이트 완료: {place_name}")
                    logger.info(f"   📍 주소: {result.address}")
                    return schedule
                    
            except Exception as e:
                logger.error(f"❌ {api_name} 검색 오류: {e}")
        
        logger.warning(f"⚠️ 모든 API 검색 실패: {place_name}")
            
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
        model_name="gpt-4-turbo",
        temperature=0
    )
    
    parser = JsonOutputParser()
    chain = prompt | llm | parser
    
    return chain

# ----- 메인 엔드포인트 -----
@app.get("/")
async def root():
    return {"message": "3중 API (Foursquare+Kakao+Google) 정확한 주소 검색 일정 추출 API v3.0", "status": "running"}

# app.py에서 AddressQualityChecker 클래스 뒤에 추가 (클래스 밖에!)

# ----- 유틸리티 함수들 -----
def normalize_priorities(schedules_data: Dict[str, Any]) -> Dict[str, Any]:
    """우선순위를 정수로 정규화"""
    logger.info("🔢 우선순위 정수 변환 시작")
    
    all_schedules = []
    all_schedules.extend(schedules_data.get("fixedSchedules", []))
    all_schedules.extend(schedules_data.get("flexibleSchedules", []))
    
    # 우선순위로 정렬
    all_schedules.sort(key=lambda s: s.get("priority", 999))
    
    # 1부터 시작하는 정수로 재할당
    for i, schedule in enumerate(all_schedules):
        old_priority = schedule.get("priority", "없음")
        new_priority = i + 1
        schedule["priority"] = new_priority
        logger.info(f"우선순위 정규화: '{schedule.get('name', '')}' {old_priority} → {new_priority}")
    
    # 다시 분류
    fixed_schedules = [s for s in all_schedules if s.get("type") == "FIXED" and "startTime" in s]
    flexible_schedules = [s for s in all_schedules if s.get("type") != "FIXED" or "startTime" not in s]
    
    logger.info(f"✅ 우선순위 정규화 완료: 고정 {len(fixed_schedules)}개, 유연 {len(flexible_schedules)}개")
    
    return {
        "fixedSchedules": fixed_schedules,
        "flexibleSchedules": flexible_schedules
    }



# extract_schedule 함수에서 사용
@app.post("/extract-schedule")
async def extract_schedule(request: ScheduleRequest):
    """3중 API로 정확한 주소를 검색하는 일정 추출 API - 한글 인코딩 지원"""
    start_time = time.time()
    logger.info(f"🎯 3중 API 일정 추출 시작: {request.voice_input}")
    
    try:
        # ... 기존 로직 동일 ...
        
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
            return UnicodeJSONResponse(
                content={"fixedSchedules": [], "flexibleSchedules": []},
                status_code=200
            )
        
        # 🔥 2. 결과 파싱
        schedule_data = result if isinstance(result, dict) else safe_parse_json(str(result))
        
        # 🔥 3. 3중 API 위치 정보 보강
        location_start = time.time()
        enhanced_data = await asyncio.wait_for(
            enhance_locations_with_triple_api(schedule_data),
            timeout=60
        )
        logger.info(f"✅ 3중 API 위치 검색 완료: {time.time() - location_start:.2f}초")
        
        # 🔥 4. 모든 스케줄러 모듈 활용
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
            
            # 일정 간 관계 분석
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
        
        # 🔥 5. 우선순위 정규화
        logger.info("🔢 우선순위 정규화 시작")
        enhanced_data = normalize_priorities(enhanced_data)
        
        # 🔥 6. 최종 데이터 정리
        fixed_schedules = enhanced_data.get("fixedSchedules", [])
        flexible_schedules = enhanced_data.get("flexibleSchedules", [])
        
        # 한글 데이터 정제 (특수문자 제거)
        def clean_korean_text(text: str) -> str:
            """한글 텍스트 정제"""
            if not text or not isinstance(text, str):
                return ""
            # 불필요한 특수문자 제거하되 한글은 유지
            import re
            # 한글, 영문, 숫자, 공백, 기본 특수문자만 허용
            cleaned = re.sub(r'[^\w\s가-힣ㄱ-ㅎㅏ-ㅣ.,()-]', '', text)
            return cleaned.strip()
        
        # 모든 스케줄 데이터의 한글 텍스트 정제
        for schedule in fixed_schedules + flexible_schedules:
            if schedule.get("name"):
                schedule["name"] = clean_korean_text(schedule["name"])
            if schedule.get("location"):
                schedule["location"] = clean_korean_text(schedule["location"])
        
        final_data = {
            "fixedSchedules": fixed_schedules,
            "flexibleSchedules": flexible_schedules
        }
        
        total_time = time.time() - start_time
        logger.info(f"🎉 3중 API 전체 처리 완료: {total_time:.2f}초")
        logger.info(f"   📊 결과: 고정 {len(fixed_schedules)}개, 유연 {len(flexible_schedules)}개")
        
        # 결과 상세 로깅 (한글 확인)
        for i, schedule in enumerate(fixed_schedules):
            logger.info(f"   🔒 고정 {i+1}: {schedule.get('name')} (우선순위: {schedule.get('priority')}) - {schedule.get('location')}")
        for i, schedule in enumerate(flexible_schedules):
            logger.info(f"   🔄 유연 {i+1}: {schedule.get('name')} (우선순위: {schedule.get('priority')}) - {schedule.get('location')}")
        
        # 한글을 깨뜨리지 않는 JSON 응답
        return UnicodeJSONResponse(content=final_data, status_code=200)
            
    except Exception as e:
        logger.error(f"❌ 전체 처리 오류: {str(e)}")
        return UnicodeJSONResponse(
            content={"fixedSchedules": [], "flexibleSchedules": []},
            status_code=200
        )

# 서버 시작
if __name__ == "__main__":
    import uvicorn
    
    # UTF-8 인코딩으로 서버 시작
    uvicorn.run(
        "app:app", 
        host="0.0.0.0", 
        port=8081, 
        reload=True,
        # 한글 지원을 위한 추가 설정
        access_log=True,
        log_config={
            "version": 1,
            "disable_existing_loggers": False,
            "formatters": {
                "default": {
                    "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
                },
            },
            "handlers": {
                "default": {
                    "formatter": "default",
                    "class": "logging.StreamHandler",
                    "stream": "ext://sys.stdout",
                },
            },
            "root": {
                "level": "INFO",
                "handlers": ["default"],
            },
        }
    )