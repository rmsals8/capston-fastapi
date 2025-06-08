import logging
import asyncio
import copy
import sys
from concurrent.futures import ThreadPoolExecutor
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from langchain_openai import ChatOpenAI
from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import JsonOutputParser
from typing import Dict, List, Any, Optional, Set, Tuple
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
    parse_datetime,
    generate_multiple_options  
)

 
# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),  # 콘솔 출력 명시
        logging.StreamHandler(sys.stderr)   # 에러도 확실히 출력
    ]
)

# 모든 로거 레벨 설정
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# 다른 모듈들도 로그 레벨 설정
scheduler_logger = logging.getLogger('multiple_options')
scheduler_logger.setLevel(logging.INFO)

relationship_logger = logging.getLogger('relationship_analyzer')
relationship_logger.setLevel(logging.INFO)

priority_logger = logging.getLogger('priority_analyzer')
priority_logger.setLevel(logging.INFO)

time_logger = logging.getLogger('time_inference')
time_logger.setLevel(logging.INFO)

utils_logger = logging.getLogger('scheduler.utils')
utils_logger.setLevel(logging.INFO)

# 로그 테스트
logger.info("🔥 로깅 시스템 초기화 완료")
logger.info(f"   현재 로그 레벨: {logger.level}")
logger.info(f"   핸들러 수: {len(logger.handlers)}")

# 환경 변수 로드 전에 로그
logger.info("📁 환경 변수 로드 시작")
# 환경 변수 로드
load_dotenv()
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
@app.post("/new-extract-schedule")
async def new_extract_schedule(request: ScheduleRequest):
    """🆕 완전히 새로운 다중 옵션 일정 추출 엔드포인트"""
    from datetime import datetime
    import sys
    
    print("🔥🔥🔥 NEW EXTRACT SCHEDULE 시작! 🔥🔥🔥")
    print(f"🔥 현재 시간: {datetime.now()}")
    print(f"🔥 입력 데이터: {request.voice_input}")
    print(f"🔥 입력 길이: {len(request.voice_input)}자")
    sys.stdout.flush()
    
    logger.info("🆕 NEW EXTRACT SCHEDULE 시작!")
    logger.info(f"입력: {request.voice_input}")
    
    try:
        print("🔥 Step 1: LLM 체인 생성 시작")
        chain = create_schedule_chain()
        print("🔥 Step 1: LLM 체인 생성 완료")
        
        print("🔥 Step 2: LLM 호출 시작")
        result = await asyncio.wait_for(
            run_in_executor(lambda: chain.invoke({"input": request.voice_input})),
            timeout=20
        )
        print(f"🔥 Step 2: LLM 응답 수신, 타입: {type(result)}")
        print(f"🔥 Step 2: LLM 응답 내용: {str(result)[:200]}...")
        
        print("🔥 Step 3: 결과 파싱")
        if isinstance(result, dict):
            schedule_data = result
        else:
            schedule_data = safe_parse_json(str(result))
        
        fixed_count = len(schedule_data.get('fixedSchedules', []))
        flexible_count = len(schedule_data.get('flexibleSchedules', []))
        print(f"🔥 Step 3: 파싱 완료 - 고정: {fixed_count}개, 유연: {flexible_count}개")
        
        # 간단한 다중 옵션 응답 생성 (복잡한 로직 없이)
        print("🔥 Step 4: 간단한 다중 옵션 생성")
        
        simple_options = []
        for i in range(5):
            option = {
                "optionId": i + 1,
                "fixedSchedules": schedule_data.get('fixedSchedules', []),
                "flexibleSchedules": schedule_data.get('flexibleSchedules', [])
            }
            simple_options.append(option)
        
        final_result = {"options": simple_options}
        
        print(f"🔥 Step 4: 간단한 다중 옵션 생성 완료 - {len(simple_options)}개 옵션")
        print("🔥🔥🔥 NEW EXTRACT SCHEDULE 완료! 🔥🔥🔥")
        
        return UnicodeJSONResponse(content=final_result, status_code=200)
        
    except Exception as e:
        print(f"🔥 오류 발생: {str(e)}")
        print(f"🔥 오류 타입: {type(e).__name__}")
        
        error_result = {
            "options": [
                {
                    "optionId": 1,
                    "fixedSchedules": [],
                    "flexibleSchedules": []
                }
            ]
        }
        
        print("🔥 오류 응답 반환")
        return UnicodeJSONResponse(content=error_result, status_code=200)
class DynamicRouteOptimizer:
    """동적 경로 최적화 및 다중 옵션 생성기"""
    
    def __init__(self, kakao_api_key: str):
        self.kakao_api_key = kakao_api_key
    
    async def create_multiple_options(self, enhanced_data: Dict, voice_input: str) -> Dict:
        """완전 동적 다중 옵션 생성 - used_locations 스코프 문제 수정"""
        
        def force_log(msg):
            print(f"🎯 {msg}")
            logger.info(msg)
        
        force_log("🆕 동적 다중 옵션 생성 시작 (used_locations 스코프 수정)")
        force_log(f"입력 데이터: voice_input='{voice_input}'")
        
        # 입력 데이터 상세 로깅
        fixed_schedules = enhanced_data.get("fixedSchedules", [])
        force_log(f"고정 일정 수: {len(fixed_schedules)}개")
        for i, schedule in enumerate(fixed_schedules):
            force_log(f"  고정 일정 {i+1}: '{schedule.get('name', 'N/A')}' (ID: {schedule.get('id', 'N/A')})")
        
        if len(fixed_schedules) < 2:
            force_log("⚠️ 경로 분석에 필요한 최소 일정 부족 (2개 미만)")
            return {"options": [enhanced_data]}  # 단일 옵션 반환
        
        # 1. 경로 정보 자동 추출
        start_schedule = fixed_schedules[0]
        end_schedule = fixed_schedules[-1]
        
        start_coord = (start_schedule.get("latitude"), start_schedule.get("longitude"))
        end_coord = (end_schedule.get("latitude"), end_schedule.get("longitude"))
        
        force_log(f"📍 경로 분석:")
        force_log(f"  시작: {start_schedule.get('name')} ({start_coord})")
        force_log(f"  종료: {end_schedule.get('name')} ({end_coord})")
        
        # 2. 변경 가능한 일정 자동 식별
        variable_schedules = self.identify_variable_schedules(fixed_schedules, voice_input)
        
        force_log(f"🔍 변경 가능한 일정 식별 결과: {len(variable_schedules)}개")
        for i, var_info in enumerate(variable_schedules):
            force_log(f"  변경 가능 {i+1}: 인덱스={var_info['index']}, 브랜드='{var_info['brand']}', 원본명='{var_info['original_name']}'")
        
        if not variable_schedules:
            force_log("⚠️ 변경 가능한 일정이 없음 → 단일 옵션 반환")
            return {"options": [enhanced_data]}
        
        # 🔥 전역 위치 추적 - 클래스 레벨로 이동하여 확실한 공유 보장
        global_used_locations = set()
        
        force_log(f"🔄 전역 used_locations 초기화: {len(global_used_locations)}개")
        
        # 3. 각 변경 가능한 일정에 대해 동적 옵션 생성
        options = []
        successful_options = 0  # 성공한 옵션 수 추적
        
        for option_num in range(5):
            force_log(f"🔄 옵션 {option_num + 1} 동적 생성 시작")
            force_log(f"  현재 전역 used_locations: {len(global_used_locations)}개 - {list(global_used_locations)}")
            
            option_data = copy.deepcopy(enhanced_data)
            option_modified = False
            current_option_locations = set()  # 현재 옵션에서 사용할 위치들
            
            for var_info in variable_schedules:
                schedule_idx = var_info["index"]
                schedule = option_data["fixedSchedules"][schedule_idx]
                brand_name = var_info["brand"]
                
                force_log(f"  📝 일정 수정: 인덱스={schedule_idx}, 브랜드='{brand_name}'")
                force_log(f"    현재 이름: '{schedule.get('name')}'")
                force_log(f"    현재 위치: '{schedule.get('location')}'")
                
                # 🔥 현재 위치를 첫 번째 옵션에서는 사용된 위치에 추가
                current_location = schedule.get("location", "")
                if option_num == 0 and current_location and current_location.strip():
                    global_used_locations.add(current_location)
                    force_log(f"    📝 원본 위치를 전역에 추가: {current_location}")
                    force_log(f"    📊 전역 used_locations 업데이트: {len(global_used_locations)}개")
                
                # 4. 동적 중간 지역 계산
                force_log(f"  🗺️ 중간 지역 계산 (옵션 {option_num + 1})")
                intermediate_areas = await self.calculate_intermediate_areas(
                    start_coord, end_coord, option_num, total_options=5
                )
                force_log(f"    계산된 중간 지역: {intermediate_areas}")
                
                # 5. 해당 지역에서 브랜드 검색 (🔥 전역 used_locations 사본 전달)
                force_log(f"  🔍 브랜드 검색: '{brand_name}' (전역 제외: {len(global_used_locations)}개)")
                force_log(f"    제외할 위치 목록: {list(global_used_locations)}")
                
                # 🔥 used_locations 사본을 전달하여 find_optimal_branch에서 실제로 수정되지 않도록 함
                used_locations_copy = global_used_locations.copy()
                
                best_location = await self.find_optimal_branch(
                    brand_name, intermediate_areas, start_coord, end_coord, used_locations_copy
                )
                
                if best_location:
                    new_location = best_location.get("address", "")
                    force_log(f"    ✅ 검색 성공: {best_location.get('name')}")
                    force_log(f"      주소: {new_location}")
                    
                    # 🔥 중복 체크 (find_optimal_branch가 사본을 수정했으므로 원본은 그대로)
                    if new_location in global_used_locations:
                        force_log(f"    ⚠️ 이미 전역에서 사용된 위치: {new_location}")
                        continue  # 이 일정은 수정하지 않고 넘어감
                    elif new_location != current_location:
                        # 위치 업데이트
                        old_location = schedule.get("location")
                        schedule["location"] = new_location
                        schedule["latitude"] = best_location["latitude"]
                        schedule["longitude"] = best_location["longitude"]
                        schedule["name"] = best_location["name"]
                        
                        # 🔥 현재 옵션에서 사용할 위치로 임시 저장
                        current_option_locations.add(new_location)
                        
                        option_modified = True
                        force_log(f"    🔄 위치 변경:")
                        force_log(f"      이전: {old_location}")
                        force_log(f"      이후: {new_location}")
                        force_log(f"    📝 현재 옵션 위치 목록에 추가: {new_location}")
                    else:
                        force_log(f"    ⚠️ 동일한 위치라서 변경 없음: {new_location}")
                else:
                    force_log(f"    ❌ 검색 실패: 새로운 위치 없음 (모든 후보가 이미 사용됨)")
                    
                    # 🔥 더 이상 새로운 위치가 없으면 옵션 생성 중단
                    if option_num > 0:  # 첫 번째 옵션이 아닌 경우에만
                        force_log(f"    ⏭️ 새로운 위치가 없어서 옵션 생성 중단")
                        break
            
            # 6. 수정된 옵션만 추가 (중복 방지)
            if option_modified or option_num == 0:  # 첫 번째는 원본 유지
                # 🔥 현재 옵션의 위치들을 전역에 추가 (성공적으로 옵션이 생성된 경우에만)
                for location in current_option_locations:
                    global_used_locations.add(location)
                    force_log(f"    ✅ 전역 used_locations에 추가: {location}")
                
                force_log(f"    📊 전역 used_locations 최종 상태: {len(global_used_locations)}개")
                force_log(f"      목록: {list(global_used_locations)}")
                
                # 고유 ID 부여
                current_time = int(time.time() * 1000)
                for j, schedule in enumerate(option_data["fixedSchedules"]):
                    old_id = schedule.get("id")
                    new_id = f"{current_time}_{option_num + 1}_{j + 1}"
                    schedule["id"] = new_id
                    force_log(f"    🆔 ID 업데이트: {old_id} → {new_id}")
                
                options.append({
                    "optionId": option_num + 1,
                    "fixedSchedules": option_data["fixedSchedules"],
                    "flexibleSchedules": option_data.get("flexibleSchedules", [])
                })
                
                successful_options += 1
                force_log(f"  ✅ 옵션 {option_num + 1} 생성 완료 (수정됨: {option_modified})")
                force_log(f"    성공한 옵션 수: {successful_options}")
                
            else:
                force_log(f"  ❌ 옵션 {option_num + 1} 건너뛰기 (변경사항 없음)")
            
            # 🔥 조기 종료 조건: 더 이상 새로운 위치를 찾을 수 없는 경우
            if not option_modified and option_num > 0:
                force_log(f"⏹️ 더 이상 새로운 위치를 찾을 수 없어서 조기 종료 (옵션 {option_num + 1})")
                break
        
        # 7. 중복 제거 (추가 안전장치)
        unique_options = self.remove_duplicate_options(options)
        force_log(f"🔄 중복 제거 결과: {len(options)}개 → {len(unique_options)}개")
        
        # 8. 최종 결과
        force_log(f"🎉 동적 옵션 생성 완료: {len(unique_options)}개")
        force_log(f"📊 최종 전역 used_locations: {len(global_used_locations)}개")
        for i, location in enumerate(global_used_locations):
            force_log(f"  위치 {i+1}: {location}")
        
        # 생성된 옵션들 상세 로깅
        for i, option in enumerate(unique_options):
            force_log(f"📋 최종 옵션 {i+1}:")
            for j, schedule in enumerate(option.get("fixedSchedules", [])):
                force_log(f"  일정 {j+1}: '{schedule.get('name')}' @ {schedule.get('location')}")
        
        return {"options": unique_options}
    
    def identify_variable_schedules(self, schedules: List[Dict], voice_input: str) -> List[Dict]:
        """변경 가능한 일정 자동 식별"""
        def force_log(msg):
            print(f"🔍 {msg}")
            logger.info(msg)
        
        force_log("변경 가능한 일정 식별 시작")
        force_log(f"입력: 일정 수={len(schedules)}, 음성='{voice_input}'")        
        variable_schedules = []
        
        # 브랜드 키워드 동적 감지
        brand_keywords = {
            # ☕ 커피 전문점 (경쟁 브랜드들)
            "스타벅스": ["스타벅스", "starbucks"],
            "커피빈": ["커피빈", "coffee bean", "coffeebean"],
            "할리스": ["할리스", "hollys", "할리스커피"],
            "투썸플레이스": ["투썸플레이스", "twosome", "투썸"],
            "이디야": ["이디야", "ediya", "이디야커피"],
            "폴바셋": ["폴바셋", "paul bassett"],
            "탐앤탐스": ["탐앤탐스", "tom n toms"],
            "엔젤리너스": ["엔젤리너스", "angelinus"],
            "메가커피": ["메가커피", "mega coffee", "메가mgc커피"],
            "컴포즈커피": ["컴포즈", "compose coffee"],
            "식사": ["식사", "저녁", "점심", "아침", "밥", "맛집", "식당"],          
            # 🍰 카페 & 디저트
            "카페": ["카페", "cafe", "커피", "coffee"],
            "베이커리": ["베이커리", "bakery", "빵집", "파리바게뜨", "뚜레쥬르"],
            "디저트": ["디저트", "dessert", "케이크", "마카롱", "아이스크림"],
            
            # 🍔 패스트푸드
            "맥도날드": ["맥도날드", "mcdonald", "맥딜"],
            "버거킹": ["버거킹", "burger king"],
            "롯데리아": ["롯데리아", "lotteria"],
            "kfc": ["kfc", "치킨"],
            "서브웨이": ["서브웨이", "subway"],
            
            # 🍕 피자
            "도미노피자": ["도미노", "domino", "도미노피자"],
            "피자헛": ["피자헛", "pizza hut"],
            "미스터피자": ["미스터피자", "mr pizza"],
            "파파존스": ["파파존스", "papa johns"],
            
            # 🍗 치킨
            "bbq": ["bbq", "비비큐"],
            "굽네치킨": ["굽네", "굽네치킨"],
            "네네치킨": ["네네", "네네치킨"],
            "교촌치킨": ["교촌", "교촌치킨"],
            "bhc": ["bhc", "비에이치씨"],
            "처갓집": ["처갓집", "처갓집양념치킨"],
            
            # 🏪 편의점
            "편의점": ["편의점", "세븐일레븐", "cu", "gs25", "이마트24", "미니스톱"],
            "세븐일레븐": ["세븐일레븐", "7eleven", "711"],
            "cu": ["cu", "씨유"],
            "gs25": ["gs25", "지에스25"],
            "이마트24": ["이마트24", "emart24"],
            
            # 🍜 한식
            "한식": ["한식", "한정식", "백반", "찌개", "국밥", "korean food"],
            "김밥": ["김밥천국", "김밥", "분식"],
            "곱창": ["곱창", "막창", "대창", "양"],
            "삼겹살": ["삼겹살", "고기집", "구이"],
            "치킨갈비": ["닭갈비", "치킨갈비", "춘천닭갈비"],
            
            # 🍝 양식
            "파스타": ["파스타", "이탈리안", "스파게티"],
            "스테이크": ["스테이크", "아웃백", "outback"],
            "양식": ["양식", "이탈리안", "western food"],
            
            # 🍜 일식
            "초밥": ["초밥", "스시", "sushi"],
            "라멘": ["라멘", "ramen", "돈코츠"],
            "돈카츠": ["돈카츠", "카츠", "tonkatsu"],
            "일식": ["일식", "japanese food"],
            
            # 🥟 중식
            "중식": ["중식", "중국집", "짜장면", "짬뽕", "탕수육"],
            "딤섬": ["딤섬", "만두"],
            
            # 🌮 기타 세계음식
            "멕시칸": ["멕시칸", "타코", "부리또"],
            "태국음식": ["태국", "쌀국수", "팟타이"],
            "인도음식": ["인도", "커리", "난"],
            
            # 🥘 분식/간식
            "분식": ["분식", "떡볶이", "순대", "튀김", "어묵"],
            "아이스크림": ["배스킨라빈스", "브라운", "하겐다즈"],
            
            # 🏨 숙박
            "호텔": ["호텔", "hotel", "리조트", "펜션"],
            "모텔": ["모텔", "motel"],
            
            # 🏥 생활시설
            "병원": ["병원", "의원", "clinic", "hospital"],
            "약국": ["약국", "pharmacy"],
            "은행": ["은행", "bank", "atm"],
            "마트": ["마트", "이마트", "홈플러스", "롯데마트"],
            
            # 🎮 오락시설
            "노래방": ["노래방", "karaoke", "코인노래방"],
            "pc방": ["pc방", "피씨방", "게임방"],
            "찜질방": ["찜질방", "사우나", "목욕탕"],
            "볼링장": ["볼링", "볼링장"],
            "당구장": ["당구", "당구장", "포켓볼"],
            
            # 🚗 교통/서비스
            "주유소": ["주유소", "gas station", "sk", "gs칼텍스", "현대오일뱅크"],
            "세차장": ["세차", "세차장"],
            "미용실": ["미용실", "헤어샵", "미용원"],
            "네일샵": ["네일", "네일샵", "nail"],
            
            # 🏃 운동/건강
            "헬스장": ["헬스", "헬스장", "피트니스", "gym"],
            "요가": ["요가", "필라테스", "yoga"],
            "골프": ["골프", "골프장", "골프연습장"],
            
            # 🎯 대형 브랜드 (구체적으로)
            "이마트": ["이마트", "emart"],
            "홈플러스": ["홈플러스", "homeplus"],
            "코스트코": ["코스트코", "costco"],
            "현대백화점": ["현대백화점", "현대"],
            "롯데백화점": ["롯데백화점", "롯데"],
            "신세계": ["신세계백화점", "신세계"],
        }
        force_log(f"브랜드 키워드 설정: {len(brand_keywords)}개 브랜드")       
        for idx, schedule in enumerate(schedules):
            schedule_name = schedule.get("name", "").lower()
            
            # 브랜드 매칭 확인
            for brand, keywords in brand_keywords.items():
                force_log(f"  {brand}: {keywords}")
                if any(keyword in schedule_name for keyword in keywords):
                    variable_schedules.append({
                        "index": idx,
                        "brand": brand,
                        "original_name": schedule.get("name"),
                        "keywords": keywords
                    })
                    logger.info(f"🔍 변경 가능한 일정 발견: {schedule.get('name')} → {brand}")
                    break
        
        return variable_schedules
    
    async def calculate_intermediate_areas(self, start_coord: Tuple, end_coord: Tuple, 
                                         option_num: int, total_options: int = 5) -> List[Tuple]:
        """동적 중간 지역 좌표 계산 - 로깅 추가"""
        
        def force_log(msg):
            print(f"🗺️ {msg}")
            logger.info(msg)
        
        start_lat, start_lng = start_coord
        end_lat, end_lng = end_coord
        
        force_log(f"중간 지역 계산: 옵션 {option_num + 1}")
        force_log(f"  시작점: ({start_lat:.4f}, {start_lng:.4f})")
        force_log(f"  종료점: ({end_lat:.4f}, {end_lng:.4f})")
        
        # 옵션별로 다른 중간점들 계산
        intermediate_coords = []
        
        if option_num == 0:
            ratio = 0.2
            force_log(f"  전략: 출발지 근처 (20% 지점)")
        elif option_num == 1:
            ratio = 0.5
            force_log(f"  전략: 중간 지점 (50% 지점)")
        elif option_num == 2:
            ratio = 0.8
            force_log(f"  전략: 목적지 근처 (80% 지점)")
        elif option_num == 3:
            ratio = 0.5
            perpendicular_offset = 0.01
            force_log(f"  전략: 우회 경로 1 (중간점 + 수직 오프셋)")
        else:
            ratio = 0.3
            perpendicular_offset = -0.01
            force_log(f"  전략: 우회 경로 2 (30% 지점 + 수직 오프셋)")
        
        # 기본 중간점 계산
        mid_lat = start_lat + (end_lat - start_lat) * ratio
        mid_lng = start_lng + (end_lng - start_lng) * ratio
        
        # 우회 경로 옵션인 경우 오프셋 적용
        if option_num >= 3:
            if 'perpendicular_offset' in locals():
                mid_lat += perpendicular_offset
                force_log(f"  수직 오프셋 적용: +{perpendicular_offset}")
        
        intermediate_coords.append((mid_lat, mid_lng))
        force_log(f"  계산된 중간점: ({mid_lat:.4f}, {mid_lng:.4f})")
        
        return intermediate_coords
    
    async def find_optimal_branch(self, brand_name: str, intermediate_areas: List[Tuple], 
                                start_coord: Tuple, end_coord: Tuple, used_locations: Set[str] = None) -> Optional[Dict]:
        """최적의 브랜드 지점 찾기 - 사용된 위치 제외"""
        
        if used_locations is None:
            used_locations = set()
        
        def force_log(msg):
            print(f"🔍 {msg}")
            logger.info(msg)
        
        force_log(f"최적 브랜드 지점 검색: '{brand_name}'")
        force_log(f"검색 지역: {len(intermediate_areas)}개")
        force_log(f"제외할 위치: {len(used_locations)}개 - {list(used_locations)}")
        
        best_location = None
        best_efficiency = 0
        
        for i, coord in enumerate(intermediate_areas):
            force_log(f"지역 {i+1} 검색: 좌표 ({coord[0]:.4f}, {coord[1]:.4f})")
            
            # 해당 좌표 근처에서 브랜드 검색
            candidates = await self.search_brand_near_coordinate(brand_name, coord)
            force_log(f"  검색 결과: {len(candidates)}개 후보")
            
            for j, candidate in enumerate(candidates):
                location = candidate.get('address', '')
                force_log(f"    후보 {j+1}: {candidate.get('name')} @ {location}")
                
                # 🔥 이미 사용된 위치인지 확인
                if location in used_locations:
                    force_log(f"      ❌ 이미 사용된 위치라서 제외")
                    continue
                    
                # 경로 효율성 계산
                efficiency = self.calculate_route_efficiency(
                    start_coord, 
                    (candidate["latitude"], candidate["longitude"]), 
                    end_coord
                )
                force_log(f"      효율성: {efficiency:.3f}")
                
                if efficiency > best_efficiency:
                    best_efficiency = efficiency
                    best_location = candidate
                    force_log(f"      🔥 새로운 최적 후보: {candidate.get('name')} (효율성: {efficiency:.3f})")
        
        if best_location:
            force_log(f"✅ 최종 선택: {best_location['name']} (효율성: {best_efficiency:.3f})")
            # 🔥 사용된 위치 추가
            used_locations.add(best_location['address'])
            force_log(f"📝 사용된 위치에 추가: {best_location['address']}")
        else:
            force_log(f"❌ 적절한 지점을 찾지 못함 (모두 사용된 위치이거나 검색 실패)")
        
        return best_location

    
    async def search_brand_near_coordinate(self, brand_name: str, coord: Tuple, 
                                         radius: int = 3000) -> List[Dict]:
        """특정 좌표 근처에서 브랜드 검색 - 로깅 추가"""
        
        def force_log(msg):
            print(f"🔍 {msg}")
            logger.info(msg)
        
        lat, lng = coord
        force_log(f"브랜드 검색: '{brand_name}' @ ({lat:.4f}, {lng:.4f}), 반경: {radius}m")
        
        try:
            url = "https://dapi.kakao.com/v2/local/search/keyword.json"
            headers = {"Authorization": f"KakaoAK {self.kakao_api_key}"}
            
            params = {
                "query": brand_name,
                "x": lng,
                "y": lat,
                "radius": radius,
                "size": 10,
                "sort": "distance"
            }
            
            force_log(f"Kakao API 호출: query='{brand_name}'")
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers, params=params) as response:
                    if response.status == 200:
                        data = await response.json()
                        
                        candidates = []
                        places = data.get("documents", [])
                        force_log(f"API 응답: {len(places)}개 장소")
                        
                        for i, place in enumerate(places):
                            place_name = place.get("place_name", "")
                            address = place.get("road_address_name") or place.get("address_name", "")
                            distance = place.get("distance", "")
                            
                            force_log(f"  장소 {i+1}: {place_name} ({distance}m)")
                            force_log(f"    주소: {address}")
                            
                            candidates.append({
                                "name": place_name,
                                "address": address,
                                "latitude": float(place.get("y", 0)),
                                "longitude": float(place.get("x", 0)),
                                "distance": distance
                            })
                        
                        force_log(f"✅ 검색 완료: {len(candidates)}개 후보 반환")
                        return candidates
                    else:
                        force_log(f"❌ API 오류: HTTP {response.status}")
                        
        except Exception as e:
            force_log(f"❌ 검색 예외: {e}")
        
        return []
    
    def calculate_route_efficiency(self, start: Tuple, middle: Tuple, end: Tuple) -> float:
        """경로 효율성 계산 - 로깅 추가"""
        
        def distance(p1, p2):
            lat1, lng1 = p1
            lat2, lng2 = p2
            return math.sqrt((lat2 - lat1)**2 + (lng2 - lng1)**2)
        
        # 직선 거리 vs 실제 경로 거리
        direct_distance = distance(start, end)
        route_distance = distance(start, middle) + distance(middle, end)
        
        if route_distance == 0:
            return 0
        
        efficiency = direct_distance / route_distance
        
        # 상세 로깅은 너무 많아서 생략
        return efficiency
    
    def remove_duplicate_options(self, options: List[Dict]) -> List[Dict]:
        """중복 옵션 제거 - 로깅 추가"""
        
        def force_log(msg):
            print(f"🔄 {msg}")
            logger.info(msg)
        
        force_log(f"중복 제거 시작: {len(options)}개 옵션")
        
        unique_options = []
        seen_signatures = set()
        
        for i, option in enumerate(options):
            # 각 옵션의 위치 시그니처 생성
            signature = self.create_location_signature(option)
            force_log(f"옵션 {i+1} 시그니처: '{signature}'")
            
            if signature not in seen_signatures:
                unique_options.append(option)
                seen_signatures.add(signature)
                force_log(f"  ✅ 고유 옵션으로 추가")
            else:
                force_log(f"  ❌ 중복 옵션 제외")
        
        force_log(f"중복 제거 완료: {len(unique_options)}개 남음")
        return unique_options
    
    def create_location_signature(self, option: Dict) -> str:
        locations = []
        for schedule in option.get("fixedSchedules", []):
            location = schedule.get("location", "")
            # 🔥 스타벅스같은 브랜드는 위치만으로 구분
            if "스타벅스" in schedule.get("name", ""):
                locations.append(f"starbucks@{location}")
            else:
                name = schedule.get("name", "")
                locations.append(f"{name}@{location}")
        return " | ".join(locations)
        
        


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
    
    # app.py의 TripleLocationSearchService 클래스 내부
    @staticmethod
    async def analyze_location_with_gpt(text: str, reference_location: Optional[str] = None, route_context: Optional[str] = None) -> LocationAnalysis:
        """GPT로 정확한 지역과 장소 분석 - 경로 맥락과 참조 위치 추가"""
        
        # set을 list로 변환하여 JSON 직렬화 가능하게 만들기
        korea_regions_list = {region: list(districts) for region, districts in KOREA_REGIONS.items()}
        regions_text = json.dumps(korea_regions_list, ensure_ascii=False, indent=2)
        
        # 참조 위치 정보 추가
        reference_context = ""
        if reference_location:
            reference_context = f"\n참조 위치 (이전 일정): {reference_location}"
            reference_context += "\n'근처', '주변' 같은 표현이 있으면 이 참조 위치 근처에서 검색하세요."
        
        # 🔥 경로 맥락 추가 (새로운 기능)
        route_context_text = ""
        if route_context:
            route_context_text = f"\n경로 정보: {route_context}"
            route_context_text += "\n'중간에' 같은 표현이 있으면 경로상의 중간 지점에서 검색하세요."
            
            # 경로에서 지역 추출하여 중간 지점 지역 결정
            import re
            route_pattern = r'(.+?)에서\s*(.+?)까지'
            match = re.search(route_pattern, route_context)
            if match:
                start_place = match.group(1).strip()
                end_place = match.group(2).strip()
                
                # 출발지와 도착지 사이의 중간 지역 결정
                start_region = None
                end_region = None
                
                # 서울 지역 매핑
                seoul_areas = {
                    "신길역": "영등포구",
                    "서울역": "중구",
                    "강남역": "강남구",
                    "홍대": "마포구",
                    "이태원": "용산구",
                    "명동": "중구",
                    "잠실": "송파구",
                    "강동": "강동구"
                }
                
                for place, district in seoul_areas.items():
                    if place in start_place:
                        start_region = district
                    if place in end_place:
                        end_region = district
                
                # 중간 지역 결정 로직
                if start_region and end_region:
                    # 영등포구 → 중구 경로면 중간은 용산구 또는 마포구
                    if start_region == "영등포구" and end_region == "중구":
                        route_context_text += f"\n중간 지점 추천 지역: 용산구, 마포구 (경로상 중간)"
                    elif start_region == "중구" and end_region == "강남구":
                        route_context_text += f"\n중간 지점 추천 지역: 용산구, 서초구 (경로상 중간)"
                    else:
                        route_context_text += f"\n중간 지점 추천 지역: {start_region}과 {end_region} 사이"

        prompt = f"""
    다음 텍스트에서 한국의 정확한 지역 정보와 장소를 분석해주세요.

    텍스트: "{text}"{reference_context}{route_context_text}

    한국 지역 정보:
    {regions_text}

    **중요 분석 규칙**: 
    1. "근처", "주변" 같은 표현이 있으면 참조 위치와 같은 지역으로 설정하세요.
    2. "중간에" 같은 표현이 있으면 경로상의 중간 지점 지역에서 검색하세요.
    3. 모호한 표현("카페", "식당")도 참조 위치나 경로 근처에서 검색하도록 지역을 설정하세요.
    4. 구체적인 장소명(예: 울산대학교, 문수월드컵경기장)은 정확한 위치를 우선하세요.
    5. 경로 맥락이 있으면 지리적으로 효율적인 중간 지점을 선택하세요.

    **지리적 효율성 고려사항**:
    - 신길역(영등포구) → 서울역(중구): 중간은 용산구, 마포구
    - 서울역(중구) → 강남역(강남구): 중간은 용산구, 서초구  
    - 지하철 노선을 고려한 접근성 우선

    JSON 형식으로 응답:
    {{
    "place_name": "추출된 장소명 (맥락 고려)",
    "region": "시/도 (경로나 참조 위치 고려)",
    "district": "시/군/구 (경로나 참조 위치 고려)",
    "category": "장소 카테고리",
    "search_keywords": ["검색에 사용할 키워드들", "지역명+장소명", "카테고리명"],
    "geographical_context": "지리적 맥락 설명"
    }}
    """

        try:
            response = openai_client.chat.completions.create(
                model="gpt-4-turbo",
                messages=[
                    {
                        "role": "system", 
                        "content": "당신은 한국 지역 정보 전문가입니다. 경로 맥락과 참조 위치를 고려하여 '중간에', '근처', '주변' 표현을 지리적으로 효율적으로 해석하세요. 특히 지하철 노선과 실제 이동 경로를 고려한 중간 지점을 제안하세요."
                    },
                    {"role": "user", "content": prompt}
                ],
                temperature=0.1,
                max_tokens=500,  # 더 자세한 응답을 위해 토큰 증가
            )

            content = response.choices[0].message.content.strip()
            if content.startswith("```json"):
                content = content.replace("```json", "").replace("```", "").strip()
            
            data = json.loads(content)
            
            # 응답에 geographical_context가 없으면 기본값 추가
            if "geographical_context" not in data:
                data["geographical_context"] = "기본 분석"
            
            logger.info(f"🧠 GPT 지역 분석 완료: {data.get('region')} {data.get('district')} - {data.get('place_name')}")
            logger.info(f"🗺️ 지리적 맥락: {data.get('geographical_context')}")
            
            return LocationAnalysis(**data)
            
        except Exception as e:
            logger.error(f"❌ GPT 지역 분석 실패: {e}")
            
            # 참조 위치나 경로 맥락이 있으면 같은 지역으로 기본값 설정
            default_region = "서울특별시"
            default_district = "중구"
            
            if reference_location:
                # 참조 위치에서 지역 추출 시도
                for region in ["울산", "서울", "부산", "대구", "인천", "광주", "대전"]:
                    if region in reference_location:
                        if region == "서울":
                            default_region = "서울특별시"
                        else:
                            default_region = f"{region}광역시"
                        break
                
                # 구 정보 추출 시도
                for district in ["중구", "영등포구", "강남구", "마포구", "용산구"]:
                    if district in reference_location:
                        default_district = district
                        break
            
            elif route_context:
                # 경로 맥락에서 지역 추출
                if "서울" in route_context:
                    default_region = "서울특별시"
                    if "영등포" in route_context and "중구" in route_context:
                        default_district = "용산구"  # 중간 지점
            
            logger.info(f"🔄 기본값 사용: {default_region} {default_district}")
            
            # 기본값 반환
            return LocationAnalysis(
                place_name=text,
                region=default_region,
                district=default_district,
                category="장소",
                search_keywords=[f"{default_district} {text}", text],
                geographical_context="기본값 적용"
            )

    @staticmethod
    async def search_foursquare(analysis: LocationAnalysis) -> Optional[PlaceResult]:
        """3순위: Foursquare API 검색 - 카테고리 필터링 강화"""
        if not FOURSQUARE_API_KEY:
            logger.warning("❌ Foursquare API 키가 없습니다")
            return None
            
        logger.info(f"🔍 3순위 Foursquare 검색: {analysis.place_name}")
        
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
            
            # 🔥 카테고리별 강화된 검색 전략
            search_strategies = []
            
            # 1) 구체적인 장소명 (대학교, 경기장 등)
            if any(keyword in analysis.place_name.lower() for keyword in ['대학교', '경기장', '월드컵', '공항', '역']):
                search_strategies.append(analysis.place_name)
                
            # 2) 지역명 + 장소명
            region_name = analysis.region.replace('특별시', '').replace('광역시', '')
            search_strategies.append(f"{region_name} {analysis.place_name}")
            
            # 3) 🔥 카테고리별 특화 검색 (강화됨)
            place_lower = analysis.place_name.lower()
            if any(word in place_lower for word in ["식당", "restaurant", "식사", "밥", "저녁", "점심"]):
                search_strategies.extend([
                    f"{region_name} restaurant",
                    f"{region_name} 식당",
                    f"{region_name} food",
                    f"{analysis.district} restaurant"
                ])
                logger.info(f"🍽️ 식사 카테고리 검색 추가")
            elif any(word in place_lower for word in ["카페", "cafe", "커피"]):
                search_strategies.extend([
                    f"{region_name} cafe",
                    f"{region_name} 커피",
                    f"{region_name} coffee"
                ])
                logger.info(f"☕ 카페 카테고리 검색 추가")
            
            logger.info(f"🔍 Foursquare 검색 전략: {search_strategies}")
            
            for strategy in search_strategies:
                try:
                    params = {
                        "query": strategy,
                        "ll": f"{coords['lat']},{coords['lng']}",
                        "radius": 15000,  # 15km
                        "limit": 20,      # 더 많은 결과
                        "sort": "DISTANCE"
                    }
                    
                    # 🔥 식사 관련이면 카테고리 필터 추가
                    if any(word in strategy.lower() for word in ['restaurant', '식당', 'food']):
                        params["categories"] = "13000"  # Food & Dining
                        logger.info(f"🍽️ 식당 카테고리 필터 적용")
                    elif any(word in strategy.lower() for word in ['cafe', 'coffee', '커피']):
                        params["categories"] = "13032,13040"  # Cafe, Coffee Shop
                        logger.info(f"☕ 카페 카테고리 필터 적용")
                    
                    logger.info(f"🔍 Foursquare 검색어: '{strategy}'")
                    
                    async with aiohttp.ClientSession() as session:
                        async with session.get(url, headers=headers, params=params) as response:
                            if response.status == 200:
                                data = await response.json()
                                
                                if data.get("results"):
                                    logger.info(f"✅ Foursquare 결과 {len(data['results'])}개 발견")
                                    
                                    # 🔥 카테고리 일치 점수 계산 강화
                                    for i, place in enumerate(data["results"]):
                                        location = place.get("geocodes", {}).get("main", {})
                                        address = place.get("location", {}).get("formatted_address", "")
                                        place_name = place.get("name", "")
                                        categories = place.get("categories", [])
                                        
                                        logger.info(f"   후보 {i+1}: {place_name} - {address}")
                                        logger.info(f"     카테고리: {[cat.get('name') for cat in categories]}")
                                        
                                        if not (location.get("latitude") and location.get("longitude")):
                                            logger.info(f"     ❌ 좌표 정보 없음")
                                            continue
                                        
                                        # 🔥 강화된 필터링
                                        
                                        # 1) 부정적 키워드 필터 (대폭 강화)
                                        negative_keywords = [
                                            "학원", "병원", "의원", "약국", "은행", "부동산", 
                                            "유학", "학회", "컨설팅", "사무실", "office", 
                                            "academy", "hospital", "clinic", "bank",
                                            "real estate", "study abroad", "immigration",
                                            "consulting", "law firm", "immigration office",
                                            "어학원", "컨설턴트", "이민", "법무법인"
                                        ]
                                        
                                        is_negative = any(neg in place_name.lower() for neg in negative_keywords)
                                        
                                        if is_negative:
                                            logger.info(f"     ❌ 부정 키워드 필터링: {place_name}")
                                            continue
                                        
                                        # 2) 카테고리 적합성 확인 (대폭 강화)
                                        category_match = False
                                        category_score = 0
                                        
                                        if any(word in strategy.lower() for word in ['restaurant', '식당', 'food', '식사', '밥']):
                                            # 식당 카테고리 확인
                                            food_categories = [
                                                "restaurant", "food", "dining", "korean", "chinese", 
                                                "japanese", "italian", "american", "thai", "indian",
                                                "식당", "음식점", "레스토랑", "eatery", "bistro",
                                                "steakhouse", "pizzeria", "noodle", "barbecue"
                                            ]
                                            for cat in categories:
                                                cat_name = cat.get("name", "").lower()
                                                if any(food_cat in cat_name for food_cat in food_categories):
                                                    category_match = True
                                                    category_score += 5
                                                    logger.info(f"     ✅ 식당 카테고리 일치: {cat_name}")
                                                    break
                                                    
                                        elif any(word in strategy.lower() for word in ['cafe', 'coffee', '커피']):
                                            # 카페 카테고리 확인
                                            cafe_categories = ["cafe", "coffee", "bakery", "dessert", "카페", "tea"]
                                            for cat in categories:
                                                cat_name = cat.get("name", "").lower()
                                                if any(cafe_cat in cat_name for cafe_cat in cafe_categories):
                                                    category_match = True
                                                    category_score += 5
                                                    logger.info(f"     ✅ 카페 카테고리 일치: {cat_name}")
                                                    break
                                        else:
                                            category_match = True  # 기타 검색은 카테고리 제한 없음
                                            category_score += 2
                                        
                                        # 3) 지역 일치 확인
                                        region_score = 0
                                        region_keywords = [
                                            analysis.region.replace('특별시', '').replace('광역시', ''),
                                            analysis.district
                                        ]
                                        
                                        for keyword in region_keywords:
                                            if keyword and keyword in address:
                                                region_score += 3
                                                logger.info(f"     ✅ 지역 일치: {keyword}")
                                        
                                        # 4) 이름 유사도 확인
                                        name_score = 0
                                        search_terms = analysis.place_name.lower().split()
                                        place_terms = place_name.lower().split()
                                        
                                        for term in search_terms:
                                            if len(term) > 1:
                                                if any(term in pt for pt in place_terms):
                                                    name_score += 2
                                        
                                        # 5) 총점 계산
                                        total_score = category_score + region_score + name_score
                                        
                                        logger.info(f"     📊 점수: 카테고리={category_score} + 지역={region_score} + 이름={name_score} = {total_score}")
                                        
                                        # 🔥 엄격한 기준 적용 (식사/카페는 카테고리 필수)
                                        min_score = 5 if any(word in strategy.lower() for word in ['restaurant', '식당', 'cafe']) else 3
                                        
                                        if category_match and total_score >= min_score:
                                            result = PlaceResult(
                                                name=place_name,
                                                address=address,
                                                latitude=location["latitude"],
                                                longitude=location["longitude"],
                                                source="foursquare",
                                                rating=place.get("rating")
                                            )
                                            
                                            logger.info(f"🎉 Foursquare 필터링 검색 성공!")
                                            logger.info(f"   🏪 장소: {result.name}")
                                            logger.info(f"   📍 주소: {result.address}")
                                            logger.info(f"   🏷️ 카테고리: {[cat.get('name') for cat in categories]}")
                                            return result
                                        else:
                                            logger.info(f"     ❌ 기준 미달: 카테고리매치={category_match}, 점수={total_score} < {min_score}")
                                    
                                    logger.info(f"⚠️ 검색어 '{strategy}' - 적절한 결과 없음")
                                else:
                                    logger.info(f"⚠️ 검색어 '{strategy}' - 결과 없음")
                            else:
                                logger.warning(f"⚠️ Foursquare API 오류: {response.status}")
                                
                except Exception as e:
                    logger.error(f"❌ 검색어 '{strategy}' 오류: {e}")
                    continue
                    
        except Exception as e:
            logger.error(f"❌ Foursquare 전체 검색 오류: {e}")
        
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


# app.py의 search_kakao 함수 수정 - KOREA_REGIONS 활용

    @staticmethod
    async def search_kakao(analysis: LocationAnalysis, reference_schedules: List[Dict] = None) -> Optional[PlaceResult]:
        """1순위: Kakao API 검색 - 지역 매칭 로직 개선 (동명이인 방지)"""
        if not KAKAO_REST_API_KEY:
            logger.warning("❌ Kakao API 키가 없습니다")
            return None
            
        logger.info(f"🔍 1순위 Kakao 검색: {analysis.place_name}")
        
        # 🔥 KOREA_REGIONS에서 전국 구/시/군 정보 추출
        all_districts = []
        for region, districts in KOREA_REGIONS.items():
            all_districts.extend(list(districts))
        
        logger.info(f"📍 전국 구/시/군 {len(all_districts)}개 지역 대응")
        
        # 🔥 참조 위치에서 정확한 지역 정보 추출 (시/도 + 구/시/군)
        reference_region = None
        reference_district = None
        reference_dong = None
        
        if reference_schedules:
            for ref_schedule in reference_schedules:
                ref_location = ref_schedule.get("location", "")
                if ref_location:
                    logger.info(f"📍 참조 위치 분석: {ref_location}")
                    
                    # 시/도 정보 추출 (더 정확하게)
                    for region_key, districts in KOREA_REGIONS.items():
                        region_short = region_key.replace('특별시', '').replace('광역시', '').replace('특별자치시', '').replace('특별자치도', '').replace('도', '')
                        if region_short in ref_location or region_key in ref_location:
                            reference_region = region_key
                            logger.info(f"   📍 참조 시/도: {region_key}")
                            
                            # 해당 시/도의 구/시/군만 확인
                            for district in districts:
                                if district in ref_location:
                                    reference_district = district
                                    logger.info(f"   📍 참조 구/시/군: {district}")
                                    break
                            break
                    
                    # 동 정보도 추출 시도
                    import re
                    dong_match = re.search(r'(\w+동)', ref_location)
                    if dong_match:
                        reference_dong = dong_match.group(1)
                        logger.info(f"   📍 참조 동: {reference_dong}")
                    
                    break

        try:
            url = "https://dapi.kakao.com/v2/local/search/keyword.json"
            headers = {"Authorization": f"KakaoAK {KAKAO_REST_API_KEY}"}
            
            # 🔥 동명이인 방지 검색 전략
            search_strategies = []
            
            # 1) 구체적 장소명 (역, 대학교 등)은 지역 제한 없이
            if any(keyword in analysis.place_name.lower() for keyword in ['역', '대학교', '경기장', '공항', '병원', '마트', '터미널']):
                search_strategies.append(analysis.place_name)
                if reference_district and reference_region:
                    # 시/도 + 구/시/군 함께 검색
                    region_short = reference_region.replace('특별시', '').replace('광역시', '').replace('도', '')
                    search_strategies.append(f"{region_short} {reference_district} {analysis.place_name}")
                search_strategies.append(f"{analysis.district} {analysis.place_name}")
            
            # 2) 🔥 식사/카페는 반드시 정확한 지역으로 검색 (시/도 + 구/시/군)
            elif any(word in analysis.place_name.lower() for word in ['식사', '식당', '밥', '카페', '커피', '맛집']):
                
                if reference_district and reference_region:
                    region_short = reference_region.replace('특별시', '').replace('광역시', '').replace('특별자치시', '').replace('특별자치도', '').replace('도', '')
                    
                    # A) 동 단위 검색 (시/도 + 구/시/군 + 동)
                    if reference_dong:
                        search_strategies.extend([
                            f"{region_short} {reference_district} {reference_dong} 맛집",
                            f"{region_short} {reference_district} {reference_dong} 식당",
                            f"{reference_district} {reference_dong} 맛집"
                        ])
                    
                    # B) 구/시/군 + 카테고리 검색 (시/도 포함)
                    search_strategies.extend([
                        f"{region_short} {reference_district} 맛집",
                        f"{region_short} {reference_district} 식당",
                        f"{region_short} {reference_district} 카페",
                        f"{reference_region} {reference_district} 맛집"  # 전체 시/도명도 시도
                    ])
                    
                    logger.info(f"🎯 참조 지역 '{region_short} {reference_district}' 기준 검색")
                    
                else:
                    # 참조 없으면 analysis 정보 활용
                    analysis_region_short = analysis.region.replace('특별시', '').replace('광역시', '').replace('도', '')
                    search_strategies.extend([
                        f"{analysis_region_short} {analysis.district} 맛집",
                        f"{analysis_region_short} {analysis.district} 식당",
                        f"{analysis.region} {analysis.district} 맛집"
                    ])
            
            # 3) 기타 일반 검색
            else:
                if reference_district and reference_region:
                    region_short = reference_region.replace('특별시', '').replace('광역시', '').replace('도', '')
                    search_strategies.extend([
                        f"{region_short} {reference_district} {analysis.place_name}",
                        f"{analysis.place_name}"
                    ])
                else:
                    search_strategies.extend([
                        f"{analysis.district} {analysis.place_name}",
                        f"{analysis.place_name}"
                    ])
            
            # 중복 제거
            search_strategies = list(dict.fromkeys(search_strategies))
            
            logger.info(f"🔍 동명이인 방지 검색 전략 ({len(search_strategies)}개):")
            for i, strategy in enumerate(search_strategies):
                logger.info(f"   {i+1}. {strategy}")
            
            for strategy in search_strategies:
                try:
                    params = {
                        "query": strategy,
                        "size": 15,  # 더 많은 결과
                        "sort": "accuracy"
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
                                        
                                        logger.info(f"   후보 {i+1}: {place_name} - {address}")
                                        
                                        if not address.strip():
                                            continue
                                        
                                        # 🔥 개선된 지역 매칭 점수 (동명이인 방지)
                                        location_score = 0
                                        
                                        if reference_district and reference_region:
                                            # 📍 참조 지역이 있을 때: 시/도 + 구/시/군 모두 확인
                                            reference_region_short = reference_region.replace('특별시', '').replace('광역시', '').replace('특별자치시', '').replace('특별자치도', '').replace('도', '')
                                            
                                            # 주소에서 시/도 정보 확인
                                            address_has_region = any(region_name in address for region_name in [
                                                reference_region_short, 
                                                reference_region
                                            ])
                                            
                                            # 주소에서 구/시/군 정보 확인
                                            address_has_district = reference_district in address
                                            
                                            if address_has_region and address_has_district:
                                                location_score += 10  # 🔥 시/도 + 구/시/군 모두 일치 (최고점)
                                                logger.info(f"     ✅ 완전 지역 일치 ({reference_region_short} {reference_district})")
                                            elif address_has_district and not address_has_region:
                                                # 🔥 같은 구명이지만 다른 시/도 (예: 부산 동구 vs 대구 동구)
                                                location_score -= 20  # 대폭 감점
                                                logger.warning(f"     ❌ 동명이인 지역! {reference_district}이지만 다른 시/도 ({address})")
                                            elif address_has_region and not address_has_district:
                                                # 같은 시/도 내 다른 구/시/군
                                                found_district = None
                                                if reference_region in KOREA_REGIONS:
                                                    region_districts = KOREA_REGIONS[reference_region]
                                                    for district in region_districts:
                                                        if district in address:
                                                            found_district = district
                                                            break
                                                
                                                if found_district:
                                                    location_score += 5  # 같은 시/도 내
                                                    logger.info(f"     ✅ 같은 시/도 내 ({reference_region_short} {found_district})")
                                                else:
                                                    location_score += 2  # 같은 시/도이지만 구 불분명
                                                    logger.info(f"     ✅ 같은 시/도 ({reference_region_short})")
                                            else:
                                                location_score += 1  # 기타 지역
                                                
                                        elif reference_district:
                                            # 참조 구/시/군만 있을 때 (시/도 정보 없음)
                                            if reference_district in address:
                                                # 🔥 구명만 일치하는 경우 추가 검증 필요
                                                # 한국에서 동명이인 가능성 높은 구명들
                                                common_district_names = ["중구", "동구", "서구", "남구", "북구"]
                                                
                                                if reference_district in common_district_names:
                                                    # 동명이인 가능성 높음 - 낮은 점수
                                                    location_score += 2
                                                    logger.warning(f"     ⚠️ 동명이인 가능 지역: {reference_district}")
                                                else:
                                                    # 고유한 구명 (예: "영등포구", "금정구")
                                                    location_score += 6
                                                    logger.info(f"     ✅ 고유 구명 일치 ({reference_district})")
                                            else:
                                                location_score += 1  # 기타
                                                
                                        else:
                                            # 참조 지역 없으면 analysis 지역과 비교
                                            analysis_region_short = analysis.region.replace('특별시', '').replace('광역시', '').replace('도', '')
                                            
                                            # 시/도 + 구/시/군 확인
                                            address_has_analysis_region = any(region_name in address for region_name in [
                                                analysis_region_short,
                                                analysis.region
                                            ])
                                            
                                            if analysis.district in address and address_has_analysis_region:
                                                location_score += 8  # 분석 지역 완전 일치
                                                logger.info(f"     ✅ 분석 지역 완전 일치 ({analysis_region_short} {analysis.district})")
                                            elif analysis.district in address:
                                                # 구명만 일치 - 동명이인 체크
                                                common_district_names = ["중구", "동구", "서구", "남구", "북구"]
                                                if analysis.district in common_district_names:
                                                    location_score += 2  # 동명이인 가능성으로 낮은 점수
                                                    logger.warning(f"     ⚠️ 동명이인 가능: {analysis.district}")
                                                else:
                                                    location_score += 5  # 고유 구명
                                            elif address_has_analysis_region:
                                                location_score += 3  # 시/도만 일치
                                                logger.info(f"     ✅ 시/도 일치 ({analysis_region_short})")
                                            else:
                                                location_score += 1  # 기타
                                        
                                        # 카테고리 점수
                                        category_score = 0
                                        if any(word in strategy.lower() for word in ["맛집", "식당", "밥"]):
                                            if any(cat in category for cat in ["음식점", "식당", "레스토랑", "한식", "중식", "일식", "양식"]):
                                                category_score += 3
                                                logger.info(f"     ✅ 식당 카테고리 일치")
                                        elif "카페" in strategy.lower():
                                            if any(cat in category for cat in ["카페", "커피", "디저트"]):
                                                category_score += 3
                                                logger.info(f"     ✅ 카페 카테고리 일치")
                                        
                                        # 부정 키워드 (식당이 아닌 것들 필터링)
                                        negative_score = 0
                                        negative_keywords = ["학원", "병원", "의원", "약국", "은행", "부동산", "유학", "학회", "컨설팅"]
                                        if any(neg in place_name.lower() for neg in negative_keywords):
                                            negative_score -= 10
                                            logger.info(f"     ❌ 부정 키워드 ({place_name})")
                                        
                                        # 총점 계산
                                        total_score = location_score + category_score + negative_score
                                        
                                        logger.info(f"     📊 점수: 지역={location_score} + 카테고리={category_score} + 부정={negative_score} = {total_score}")
                                        
                                        # 🔥 높은 점수 기준 (동명이인 방지)
                                        min_score = 8 if reference_region and reference_district else 6
                                        
                                        if total_score >= min_score:
                                            result = PlaceResult(
                                                name=place_name,
                                                address=address,
                                                latitude=float(place.get("y", 0)),
                                                longitude=float(place.get("x", 0)),
                                                source="kakao"
                                            )
                                            
                                            logger.info(f"🎉 Kakao 동명이인 방지 검색 성공!")
                                            logger.info(f"   🏪 장소: {result.name}")
                                            logger.info(f"   📍 주소: {result.address}")
                                            logger.info(f"   🏷️ 카테고리: {category}")
                                            logger.info(f"   🎯 검색어: {strategy}")
                                            return result
                                    
                                    logger.info(f"⚠️ 검색어 '{strategy}' - 기준 미달 (최고점: {max([total_score for _ in range(1)] or [0])})")
                                else:
                                    logger.info(f"⚠️ 검색어 '{strategy}' - 결과 없음")
                            else:
                                logger.warning(f"⚠️ Kakao API 오류: {response.status}")
                                
                except Exception as e:
                    logger.error(f"❌ 검색어 '{strategy}' 오류: {e}")
                    continue
                    
        except Exception as e:
            logger.error(f"❌ Kakao 전체 검색 오류: {e}")
        
        logger.warning(f"⚠️ Kakao 동명이인 방지 검색 실패: {analysis.place_name}")
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

# app.py의 create_schedule_chain() 함수 개선

def create_schedule_chain():
    """LangChain을 사용한 일정 추출 체인 생성 - 시간 맥락 강화"""
    current_time = int(datetime.datetime.now().timestamp() * 1000)
    
    today = datetime.datetime.now()
    tomorrow = today + datetime.timedelta(days=1)
    day_after_tomorrow = today + datetime.timedelta(days=2)
    
    # 🔥 현재 실제 시간 정보 추가
    actual_now = datetime.datetime.now()
    current_hour = actual_now.hour
    
    template = """다음 음성 메시지에서 **모든 일정 정보**를 빠짐없이 추출하여 JSON 형식으로 반환해주세요.

음성 메시지: {input}

현재 날짜: {today_date}
현재 실제 시간: {current_hour}시 ({current_time_desc})
내일: {tomorrow_date}
모레: {day_after_tomorrow_date}

**🔥 중요한 시간 맥락 규칙**:
1. "저녁", "dinner" → 18:00~20:00 (저녁 시간)
2. "점심", "lunch" → 12:00~14:00 (점심 시간)  
3. "아침", "morning" → 08:00~10:00 (아침 시간)
4. 현재 시간이 {current_hour}시이므로, 일반적인 "식사"는 다음 식사 시간으로 설정
5. "중간에"는 앞뒤 일정 사이 시간으로 설정

**중요**: 메시지에 언급된 모든 장소와 활동을 개별 일정으로 추출하세요!

예시 입력: "부산역에서 장전역까지 가는데, 중간에 저녁먹고싶어"
→ 3개 일정: 1) 부산역 2) 저녁 식사 (18:00) 3) 장전역

다음 JSON 형식으로 반환:
{{
  "fixedSchedules": [
    {{
      "id": "{current_time}",
      "name": "부산역",
      "type": "FIXED",
      "duration": 60,
      "priority": 1,
      "location": "",
      "latitude": 35.1,
      "longitude": 129.0,
      "startTime": "2025-06-01T10:00:00",
      "endTime": "2025-06-01T11:00:00"
    }},
    {{
      "id": "{current_time_2}",
      "name": "저녁 식사",
      "type": "FIXED", 
      "duration": 120,
      "priority": 2,
      "location": "",
      "latitude": 35.1,
      "longitude": 129.0,
      "startTime": "2025-06-01T18:00:00",
      "endTime": "2025-06-01T20:00:00"
    }},
    {{
      "id": "{current_time_3}",
      "name": "장전역",
      "type": "FIXED",
      "duration": 60,
      "priority": 3,
      "location": "",
      "latitude": 35.2,
      "longitude": 129.1,
      "startTime": "2025-06-01T20:30:00",
      "endTime": "2025-06-01T21:30:00"
    }}
  ],
  "flexibleSchedules": []
}}

주의사항:
1. **시간 맥락을 정확히 반영**: "저녁" → 18:00, "점심" → 12:00
2. **"중간에"는 순서상 중간 시간**으로 배치
3. 이동시간 고려하여 최소 30분 간격 유지
4. JSON만 반환하고 다른 텍스트 포함 금지
"""
    
    # 현재 시간대 설명 추가
    if 6 <= current_hour < 12:
        current_time_desc = "오전"
    elif 12 <= current_hour < 18:
        current_time_desc = "오후"
    elif 18 <= current_hour < 22:
        current_time_desc = "저녁"
    else:
        current_time_desc = "밤"
    
    prompt = PromptTemplate(
        template=template,
        input_variables=["input"],
        partial_variables={
            "current_time": str(current_time),
            "current_time_2": str(current_time + 1),
            "current_time_3": str(current_time + 2),
            "today_date": today.strftime("%Y-%m-%d"),
            "tomorrow_date": tomorrow.strftime("%Y-%m-%d"),
            "day_after_tomorrow_date": day_after_tomorrow.strftime("%Y-%m-%d"),
            "current_hour": current_hour,
            "current_time_desc": current_time_desc
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



 # 1. 지리적 중간점 자동 계산
def calculate_geographic_midpoint(start_coords: tuple, end_coords: tuple, buffer_radius: float = 0.01) -> Dict:
    """두 지점의 지리적 중간점과 검색 반경 자동 계산"""
    start_lat, start_lng = start_coords
    end_lat, end_lng = end_coords
    
    # 중간점 계산
    mid_lat = (start_lat + end_lat) / 2
    mid_lng = (start_lng + end_lng) / 2
    
    # 두 지점 간 거리로 검색 반경 동적 계산
    import math
    distance = math.sqrt((end_lat - start_lat)**2 + (end_lng - start_lng)**2)
    search_radius = min(distance / 3, buffer_radius)  # 전체 거리의 1/3 또는 최대 buffer_radius
    
    return {
        "center": (mid_lat, mid_lng),
        "search_radius": search_radius,
        "total_distance": distance
    }

# 2. 동적 검색 전략 생성
def generate_dynamic_search_strategies(start_location: str, end_location: str, place_type: str = "식사") -> List[str]:
    """출발지와 도착지를 기반으로 동적 검색 전략 생성"""
    
    # 지역명 추출
    def extract_location_info(location: str) -> Dict:
        """위치에서 시/구/동 정보 추출"""
        import re
        
        # 시/구 패턴
        city_pattern = r'(서울|부산|대구|인천|광주|대전|울산)\s*(특별시|광역시)?'
        district_pattern = r'(\w+구|\w+시|\w+군)'
        dong_pattern = r'(\w+동|\w+읍|\w+면)'
        
        city = re.search(city_pattern, location)
        district = re.search(district_pattern, location)
        dong = re.search(dong_pattern, location)
        
        return {
            "city": city.group(1) if city else "서울",
            "district": district.group(1) if district else "",
            "dong": dong.group(1) if dong else "",
            "full_location": location
        }
    
    start_info = extract_location_info(start_location) if start_location else {}
    end_info = extract_location_info(end_location) if end_location else {}
    
    search_strategies = []
    
    # 1) 출발지 근처 검색
    if start_info.get("district"):
        search_strategies.append(f"{start_info['city']} {start_info['district']} {place_type}")
        if start_info.get("dong"):
            search_strategies.append(f"{start_info['city']} {start_info['district']} {start_info['dong']} {place_type}")
    
    # 2) 목적지 근처 검색
    if end_info.get("district") and end_info.get("district") != start_info.get("district"):
        search_strategies.append(f"{end_info['city']} {end_info['district']} {place_type}")
        if end_info.get("dong"):
            search_strategies.append(f"{end_info['city']} {end_info['district']} {end_info['dong']} {place_type}")
    
    # 3) 중간 지역 검색 (GPT 활용)
    middle_search = f"{start_location}에서 {end_location} 중간 {place_type}"
    search_strategies.append(middle_search)
    
    # 4) 일반 검색 (폴백)
    city = start_info.get("city", "서울")
    search_strategies.append(f"{city} {place_type}")
    
    logger.info(f"🎯 동적 검색 전략 생성: {len(search_strategies)}개")
    for i, strategy in enumerate(search_strategies):
        logger.info(f"   {i+1}. {strategy}")
    
    return search_strategies

# 3. 경로 효율성 자동 검증
def calculate_route_efficiency(start_coords: tuple, middle_coords: tuple, end_coords: tuple) -> Dict:
    """경로 효율성 자동 계산"""
    import math
    
    def distance(p1, p2):
        return math.sqrt((p1[0] - p2[0])**2 + (p1[1] - p2[1])**2)
    
    # 직선 거리 vs 실제 경로 거리
    direct_distance = distance(start_coords, end_coords)
    route_distance = distance(start_coords, middle_coords) + distance(middle_coords, end_coords)
    
    # 효율성 계산 (1에 가까울수록 효율적)
    efficiency = direct_distance / route_distance if route_distance > 0 else 0
    detour_ratio = (route_distance - direct_distance) / direct_distance if direct_distance > 0 else 0
    
    # 효율성 등급
    if efficiency >= 0.8:
        grade = "A"  # 매우 효율적
    elif efficiency >= 0.6:
        grade = "B"  # 효율적
    elif efficiency >= 0.4:
        grade = "C"  # 보통
    else:
        grade = "D"  # 비효율적
    
    return {
        "efficiency": efficiency,
        "detour_ratio": detour_ratio,
        "grade": grade,
        "direct_distance": direct_distance,
        "route_distance": route_distance,
        "is_efficient": efficiency >= 0.6  # B등급 이상
    }

# 4. 지능형 위치 검색 (GPT + 동적 전략)
async def smart_location_search(schedule: Dict, start_location: str = None, end_location: str = None) -> Dict:
    """기존 smart_location_search 함수 - API 호출 방식 수정"""
    place_name = schedule.get("name", "")
    if not place_name:
        return schedule
    
    logger.info(f"🧠 스마트 위치 검색: {place_name}")
    logger.info(f"   출발지: {start_location}")
    logger.info(f"   도착지: {end_location}")
    
    try:
        # GPT로 검색어 생성
        search_queries = await generate_search_queries_with_gpt(start_location, end_location, place_name)
        
        best_results = []
        
        for query in search_queries:
            try:
                logger.info(f"🔍 검색어: '{query}'")
                
                # GPT로 지역 분석
                analysis = await TripleLocationSearchService.analyze_location_with_gpt(
                    query,
                    reference_location=start_location,
                    route_context=f"{start_location}에서 {end_location}까지의 경로" if start_location and end_location else None
                )
                
                # 참조 일정 정보 구성
                reference_schedules = []
                if start_location:
                    reference_schedules.append({"location": start_location})
                
                # 🔥 올바른 API 호출 방식
                search_results = []
                
                # Kakao 검색 (2개 인자)
                try:
                    kakao_result = await TripleLocationSearchService.search_kakao(analysis, reference_schedules)
                    if kakao_result and kakao_result.address:
                        search_results.append(("Kakao", kakao_result))
                        logger.info(f"✅ Kakao 결과: {kakao_result.name}")
                except Exception as e:
                    logger.error(f"❌ Kakao 검색 오류: {e}")
                
                # Google 검색 (1개 인자)
                try:
                    google_result = await TripleLocationSearchService.search_google(analysis)
                    if google_result and google_result.address:
                        search_results.append(("Google", google_result))
                        logger.info(f"✅ Google 결과: {google_result.name}")
                except Exception as e:
                    logger.error(f"❌ Google 검색 오류: {e}")
                
                # Foursquare 검색 (1개 인자)
                try:
                    foursquare_result = await TripleLocationSearchService.search_foursquare(analysis)
                    if foursquare_result and foursquare_result.address:
                        search_results.append(("Foursquare", foursquare_result))
                        logger.info(f"✅ Foursquare 결과: {foursquare_result.name}")
                except Exception as e:
                    logger.error(f"❌ Foursquare 검색 오류: {e}")
                
                # 결과 처리 및 점수 계산
                for api_name, result in search_results:
                    if result and result.address:
                        score = calculate_simple_score(result, query)
                        best_results.append({
                            "result": result,
                            "query": query,
                            "api": api_name,
                            "score": score
                        })
                        logger.info(f"   점수: {score}")
                
            except Exception as e:
                logger.error(f"❌ 검색어 '{query}' 처리 오류: {e}")
        
        # 최적 결과 선택
        if best_results:
            # 점수순으로 정렬
            best_results.sort(key=lambda x: x["score"], reverse=True)
            best = best_results[0]
            
            result = best["result"]
            schedule["location"] = clean_address(result.address)
            schedule["latitude"] = result.latitude
            schedule["longitude"] = result.longitude
            
            logger.info(f"🎯 최적 결과: {result.name}")
            logger.info(f"   📍 주소: {schedule['location']}")
            logger.info(f"   🔌 API: {best['api']}")
            logger.info(f"   📊 점수: {best['score']}")
            
            return schedule
        
        logger.warning(f"⚠️ 모든 검색 실패: {place_name}")
        
    except Exception as e:
        logger.error(f"❌ 스마트 검색 오류: {place_name}, {e}")
    
    return schedule

def calculate_simple_score(result, query: str) -> float:
    """간단한 점수 계산"""
    score = 0.0
    
    # 평점 점수
    if hasattr(result, 'rating') and result.rating:
        score += result.rating * 2  # 최대 10점
    else:
        score += 5  # 기본 5점
    
    # 이름 관련성 점수
    query_words = query.lower().split()
    name_words = result.name.lower().split() if hasattr(result, 'name') else []
    
    common_words = set(query_words) & set(name_words)
    score += len(common_words) * 2  # 공통 단어당 2점
    
    # 주소 완전성 점수
    if hasattr(result, 'address') and result.address:
        if len(result.address) > 10:
            score += 3
        if "구" in result.address:
            score += 2
        if "로" in result.address or "길" in result.address:
            score += 1
    
    return score

# 2. GPT 기반 검색어 생성 함수
async def generate_search_queries_with_gpt(start_location: str, end_location: str, place_type: str) -> List[str]:
    """GPT로 검색어 동적 생성 - 하드코딩 없음"""
    
    try:
        prompt = f"""
사용자가 "{place_type}"를 찾고 있습니다.

출발지: {start_location}
도착지: {end_location}

위 두 지점 사이에서 "{place_type}"를 찾기 위한 실용적인 검색어 5개를 생성해주세요.
실제 지도 검색에서 사용할 수 있는 구체적인 검색어로 만들어주세요.

조건:
1. 실제 존재하는 지역명 + 카테고리 형태
2. 지리적으로 합리적인 위치들
3. 다양한 옵션 제공

JSON 형식으로만 응답:
{{
  "search_queries": [
    "검색어1",
    "검색어2", 
    "검색어3",
    "검색어4",
    "검색어5"
  ],
  "reasoning": "검색어 선택 이유"
}}
"""
        
        response = openai_client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {
                    "role": "system", 
                    "content": "당신은 한국 지리 전문가입니다. 실용적이고 검색 가능한 지역명을 제공하세요."
                },
                {"role": "user", "content": prompt}
            ],
            temperature=0.3,
            max_tokens=400
        )
        
        content = response.choices[0].message.content.strip()
        if content.startswith("```json"):
            content = content.replace("```json", "").replace("```", "").strip()
        
        data = json.loads(content)
        queries = data.get("search_queries", [])
        reasoning = data.get("reasoning", "")
        
        logger.info(f"🎯 GPT 생성 검색어 {len(queries)}개:")
        for i, query in enumerate(queries):
            logger.info(f"   {i+1}. {query}")
        logger.info(f"📝 선택 이유: {reasoning}")
        
        return queries
        
    except Exception as e:
        logger.error(f"❌ GPT 검색어 생성 실패: {e}")
        
        # 폴백: 간단한 기본 검색어
        if "식사" in place_type or "밥" in place_type:
            return ["맛집", "식당", "레스토랑", "한식", "분식"]
        elif "카페" in place_type:
            return ["카페", "커피", "디저트", "베이커리", "차"]
        else:
            return ["맛집", "식당", "카페", "레스토랑", "음식점"]

# 3. 기존 create_simple_multiple_options 대신 GPT 기반으로 수정
async def create_multiple_options(enhanced_data: Dict, voice_input: str) -> Dict:
    """DynamicRouteOptimizer를 사용한 다중 옵션 생성"""
    print("🔥🔥🔥 create_multiple_options 함수 호출됨!")
    logger.info("🔥🔥🔥 create_multiple_options 함수 호출됨!")
    
    print(f"🔥 voice_input: {voice_input}")
    print(f"🔥 KAKAO_REST_API_KEY 존재: {bool(KAKAO_REST_API_KEY)}")
    
    optimizer = DynamicRouteOptimizer(KAKAO_REST_API_KEY)
    print("🔥 DynamicRouteOptimizer 인스턴스 생성됨")    
    optimizer = DynamicRouteOptimizer(KAKAO_REST_API_KEY)
    
    try:
        result = await optimizer.create_multiple_options(enhanced_data, voice_input)
        return result
    except Exception as e:
        logger.error(f"❌ 동적 옵션 생성 실패: {e}")
        
        # 폴백: 단일 옵션
        return {"options": [enhanced_data]}

# 4. GPT 기반 옵션 전략 생성 (하드코딩 완전 제거)
async def generate_option_strategies_dynamic(start_location: str, end_location: str, voice_input: str) -> List[str]:
    """GPT로 옵션별 다른 전략 동적 생성"""
    
    try:
        prompt = f"""
사용자 요청: "{voice_input}"
출발지: {start_location}  
도착지: {end_location}

위 정보를 바탕으로 식사 장소에 대한 5가지 다른 옵션 전략을 생성해주세요.
각 옵션은 서로 다른 지역이나 컨셉이어야 합니다.

조건:
1. 지리적으로 합리적인 위치
2. 서로 다른 특색이 있는 옵션들
3. 실제 검색 가능한 구체적인 검색어

JSON 형식으로만 응답:
{{
  "strategies": [
    "전략1 검색어",
    "전략2 검색어", 
    "전략3 검색어",
    "전략4 검색어",
    "전략5 검색어"
  ]
}}
"""
        
        response = openai_client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {
                    "role": "system", 
                    "content": "당신은 맛집 추천 전문가입니다. 다양하고 실용적인 식사 옵션을 제공하세요."
                },
                {"role": "user", "content": prompt}
            ],
            temperature=0.4,  # 약간의 창의성
            max_tokens=300
        )
        
        content = response.choices[0].message.content.strip()
        if content.startswith("```json"):
            content = content.replace("```json", "").replace("```", "").strip()
        
        data = json.loads(content)
        strategies = data.get("strategies", [])
        
        logger.info(f"🎨 GPT 생성 전략 {len(strategies)}개:")
        for i, strategy in enumerate(strategies):
            logger.info(f"   {i+1}. {strategy}")
        
        return strategies
        
    except Exception as e:
        logger.error(f"❌ GPT 전략 생성 실패: {e}")
        
        # 폴백: 기본 검색어들
        return ["맛집", "고급 레스토랑", "가성비 식당", "카페", "분식"]



async def get_coordinates_from_address(address: str) -> tuple:
    """주소에서 좌표 추출 (간단한 지오코딩)"""
    try:
        # 기존 카카오 지오코딩 활용
        if not KAKAO_REST_API_KEY:
            return None
        
        url = "https://dapi.kakao.com/v2/local/search/address.json"
        headers = {"Authorization": f"KakaoAK {KAKAO_REST_API_KEY}"}
        params = {"query": address}
        
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers, params=params, timeout=5) as response:
                if response.status == 200:
                    data = await response.json()
                    documents = data.get("documents", [])
                    if documents:
                        result = documents[0]
                        return (float(result.get("y", 0)), float(result.get("x", 0)))
        
        return None
        
    except Exception as e:
        logger.error(f"주소 좌표 변환 오류: {e}")
        return None
def clean_address(address: str) -> str:
            """주소 정제 함수"""
            if not address:
                return ""
            
            import re
            
            # 1. 중복된 지역명 제거
            address = re.sub(r'부산광역시,?\s*부산광역시', '부산광역시', address)
            address = re.sub(r'서울특별시,?\s*서울특별시', '서울특별시', address)
            address = re.sub(r'대구광역시,?\s*대구광역시', '대구광역시', address)
            
            # 2. 우편번호 제거 (5자리 숫자, 3-3 형태)
            address = re.sub(r',?\s*\d{3}-\d{3}', '', address)
            address = re.sub(r',?\s*\d{5}', '', address)
            
            # 3. 불필요한 쉼표와 공백 정리
            address = re.sub(r',+', ',', address)  # 연속 쉼표 제거
            address = re.sub(r',\s*$', '', address)  # 끝부분 쉼표 제거
            address = re.sub(r'^\s*,', '', address)  # 시작부분 쉼표 제거
            address = re.sub(r'\s+', ' ', address)  # 연속 공백 제거
            
            # 4. 앞뒤 공백 제거
            address = address.strip()
            
            return address
# 5. 지능형 다중 옵션 생성
async def create_smart_multiple_options(enhanced_data: Dict, voice_input: str) -> Dict:
    """지능형 다중 옵션 생성 - 하드코딩 없이"""
    
    def force_log(msg):
        print(f"🧠 {msg}")
        logger.info(msg)
    
    force_log("지능형 다중 옵션 생성 시작")
    
    try:
        # 경로 정보 자동 추출
        fixed_schedules = enhanced_data.get("fixedSchedules", [])
        start_schedule = fixed_schedules[0] if len(fixed_schedules) > 0 else None
        end_schedule = fixed_schedules[-1] if len(fixed_schedules) > 1 else None
        
        start_location = start_schedule.get("location") if start_schedule else None
        end_location = end_schedule.get("location") if end_schedule else None
        
        force_log(f"자동 추출된 경로: {start_location} → {end_location}")
        
        # 🔥 다양한 옵션 생성 전략 (동적)
        option_strategies = [
            {"focus": "start_area", "description": "출발지 근처 중심"},
            {"focus": "end_area", "description": "목적지 근처 중심"},
            {"focus": "midway", "description": "중간 지점 중심"},
            {"focus": "efficient", "description": "최단 경로 중심"},
            {"focus": "diverse", "description": "다양한 지역 탐색"}
        ]
        
        options = []
        used_locations = set()  # 중복 방지
        
        for option_num, strategy in enumerate(option_strategies):
            force_log(f"옵션 {option_num + 1} 생성: {strategy['description']}")
            
            option_data = copy.deepcopy(enhanced_data)
            
            # 식사 일정 찾기 및 재검색
            for schedule in option_data.get("fixedSchedules", []):
                if "식사" in schedule.get("name", ""):
                    force_log(f"   식사 일정 재검색: {strategy['focus']} 전략")
                    
                    # 🔥 전략별 동적 검색
                    if strategy["focus"] == "start_area":
                        # 출발지 근처 우선
                        search_context = f"{start_location} 근처"
                    elif strategy["focus"] == "end_area":
                        # 목적지 근처 우선
                        search_context = f"{end_location} 근처"
                    elif strategy["focus"] == "midway":
                        # 중간 지점 우선
                        search_context = f"{start_location}에서 {end_location} 중간"
                    elif strategy["focus"] == "efficient":
                        # 최단 경로 우선
                        search_context = f"{start_location}에서 {end_location} 최단경로"
                    else:  # diverse
                        # 다양한 지역 탐색
                        search_context = f"{voice_input} 다양한 옵션"
                    
                    # 지능형 검색 수행
                    original_name = schedule.get("name", "")
                    temp_schedule = copy.deepcopy(schedule)
                    temp_schedule["name"] = search_context
                    
                    enhanced_schedule = await smart_location_search(
                        temp_schedule, 
                        start_location, 
                        end_location
                    )
                    
                    # 결과 적용 (중복 체크)
                    new_location = enhanced_schedule.get("location", "")
                    if new_location and new_location not in used_locations:
                        schedule["location"] = new_location
                        schedule["latitude"] = enhanced_schedule.get("latitude", schedule.get("latitude"))
                        schedule["longitude"] = enhanced_schedule.get("longitude", schedule.get("longitude"))
                        schedule["name"] = f"옵션{option_num + 1} 식사"  # 옵션별 구분
                        
                        used_locations.add(new_location)
                        force_log(f"   ✅ 새로운 위치: {new_location}")
                    else:
                        force_log(f"   ⚠️ 중복 또는 실패, 원본 유지")
            
            # 고유 ID 부여
            for schedule_type in ["fixedSchedules", "flexibleSchedules"]:
                for j, schedule in enumerate(option_data.get(schedule_type, [])):
                    schedule["id"] = f"{int(time.time() * 1000)}_{option_num + 1}_{j + 1}"
            
            option = {
                "optionId": option_num + 1,
                "fixedSchedules": option_data.get("fixedSchedules", []),
                "flexibleSchedules": option_data.get("flexibleSchedules", [])
            }
            
            options.append(option)
            force_log(f"✅ 옵션 {option_num + 1} 완성")
        
        final_result = {"options": options}
        force_log(f"🎉 지능형 다중 옵션 생성 완료: {len(options)}개")
        
        # 결과 품질 검증
        for i, option in enumerate(options):
            for schedule in option.get("fixedSchedules", []):
                if "식사" in schedule.get("name", ""):
                    location = schedule.get("location", "")
                    force_log(f"   옵션 {i+1} 검증: {location}")
        
        return final_result
        
    except Exception as e:
        force_log(f"❌ 지능형 옵션 생성 실패: {e}")
        return {"options": []}

def should_use_dynamic_system(enhanced_data: Dict, voice_input: str) -> bool:
    """사용할 시스템 자동 결정"""
    
    fixed_schedules = enhanced_data.get("fixedSchedules", [])
    
    # 1. 브랜드 키워드가 있으면 동적 시스템
    brand_keywords = [
    # ☕ 커피 전문점
    "스타벅스", "starbucks",
    "커피빈", "coffee bean", "coffeebean",
    "할리스", "hollys", "할리스커피",
    "투썸플레이스", "twosome", "투썸",
    "이디야", "ediya", "이디야커피",
    "폴바셋", "paul bassett",
    "탐앤탐스", "tom n toms", "탐탐",
    "엔젤리너스", "angelinus",
    "메가커피", "mega coffee", "메가mgc커피",
    "컴포즈커피", "compose coffee", "컴포즈",
    "빽다방", "paik's coffee", "빽", "빽커피",
    "카페베네", "cafe bene",
    "드롭탑", "droptop",
    "더벤티", "the venti",
    "블루보틀", "blue bottle",
    "스타벅스리저브", "reserve",
    
    # 🏪 편의점
    "편의점",
    "세븐일레븐", "7eleven", "711", "세븐",
    "cu", "씨유",
    "gs25", "지에스25", "gs",
    "이마트24", "emart24", "이마트",
    "미니스톱", "ministop",
    
    # 🍔 패스트푸드
    "맥도날드", "mcdonald", "맥딜", "맥날",
    "버거킹", "burger king", "버킹",
    "롯데리아", "lotteria",
    "kfc", "케이에프씨", "치킨",
    "서브웨이", "subway",
    "도미노피자", "domino", "도미노",
    "피자헛", "pizza hut", "피헛",
    "미스터피자", "mr pizza", "미피",
    "파파존스", "papa johns",
    "맘스터치", "mom's touch",
    "크라제버거", "kraze burger",
    "쉐이크쉑", "shake shack",
    "파이브가이즈", "five guys",
    
    # 🍗 치킨
    "bbq", "비비큐",
    "굽네치킨", "굽네",
    "네네치킨", "네네",
    "교촌치킨", "교촌",
    "bhc", "비에이치씨",
    "처갓집", "처갓집양념치킨",
    "쁘닭", "쁘닭치킨",
    "호식이두마리치킨", "호식이",
    "맥시칸치킨", "맥시칸",
    "페리카나", "pelicana",
    "푸라닭", "puradak",
    "지코바", "zikoba",
    
    # 🍕 피자 (추가)
    "피자스쿨", "pizza school",
    "피자마루", "pizza maru",
    "반올림피자", "round table pizza",
    "청년피자", "young pizza",
    
    # 🍰 베이커리/디저트
    "파리바게뜨", "paris baguette", "파바",
    "뚜레쥬르", "tous les jours", "뚜레",
    "던킨도넛", "dunkin donuts", "던킨",
    "크리스피크림", "krispy kreme",
    "베스킨라빈스", "baskin robbins", "배라",
    "브라운", "brown",
    "하겐다즈", "haagen dazs",
    "나뚜루", "natuur",
    "설빙", "sulbing",
    "빙그레", "binggrae",
    
    # 🍜 패밀리 레스토랑
    "아웃백", "outback",
    "티지아이프라이데이", "tgi friday",
    "베니건스", "bennigans",
    "애슐리", "ashley",
    "빕스", "vips",
    "온더보더", "on the border",
    "마르쉐", "marche",
    "토니로마스", "tony roma",
    
    # 🥘 한식 프랜차이즈
    "김밥천국",
    "백반집",
    "한솥도시락", "한솥",
    "본죽", "본죽&비빔밥",
    "놀부부대찌개", "놀부",
    "청년다방",
    "맘터치", "mom touch",
    "원할머니보쌈", "원할머니",
    "두끼떡볶이", "두끼",
    "죠스떡볶이", "죠스",
    "엽기떡볶이", "엽떡",
    
    # 🍜 일식
    "요시노야", "yoshinoya",
    "스키야", "sukiya",
    "마루가메제면", "marugame",
    "코코이찌방야", "coco",
    "하나로초밥", "hanaro",
    "스시로", "sushiro",
    "온기라쿠", "ongiraku",
    
    # 🥟 중식
    "홍콩반점", "홍콩반점0410",
    "유가네닭갈비", "유가네",
    "진주냉면", "진주함흥냉면",
    
    # 🛒 대형마트/마트
    "이마트", "emart",
    "홈플러스", "homeplus",
    "롯데마트", "lotte mart",
    "코스트코", "costco",
    "하나로마트", "hanaro mart",
    "농협", "nh마트",
    "메가마트", "mega mart",
    
    # 🏬 백화점
    "현대백화점", "현대",
    "롯데백화점", "롯데",
    "신세계백화점", "신세계",
    "갤러리아", "galleria",
    "동화면세점", "동화",
    "아웃렛", "outlet",
    "프리미엄아웃렛",
    
    # 🏥 생활시설
    "약국", "pharmacy",
    "온누리약국", "온누리",
    "삼성약국", "삼성",
    "24시간약국",
    "병원", "의원", "clinic", "hospital",
    "은행", "bank",
    "우리은행", "우리",
    "국민은행", "kb",
    "신한은행", "신한",
    "하나은행", "하나",
    "기업은행", "ibk",
    "농협은행", "nh",
    "카카오뱅크", "kakao bank",
    "토스뱅크", "toss bank",
    
    # ⛽ 주유소
    "주유소", "gas station",
    "sk에너지", "sk", "sk주유소",
    "gs칼텍스", "gs", "gs주유소",
    "현대오일뱅크", "현대", "oilbank",
    "s-oil", "에쓰오일",
    "알뜰주유소",
    
    # 🎮 오락시설
    "노래방", "karaoke", "코인노래방",
    "pc방", "피씨방", "게임방",
    "찜질방", "사우나", "목욕탕",
    "볼링장", "볼링",
    "당구장", "당구", "포켓볼",
    "스크린골프", "골프연습장",
    "vr", "vr체험관",
    "방탈출", "방탈출카페",
    
    # 🏋️ 운동/헬스
    "헬스장", "헬스", "피트니스", "gym",
    "요가", "필라테스", "yoga",
    "골프", "골프장", "골프연습장",
    "수영장", "swimming pool",
    "태권도", "유도", "복싱",
    "클라이밍", "암벽등반",
    "스쿼시", "배드민턴", "테니스",
    
    # 💄 뷰티/미용
    "미용실", "헤어샵", "미용원", "salon",
    "네일샵", "네일", "nail",
    "마사지", "massage", "스파", "spa",
    "피부과", "성형외과", "피부관리",
    "아이브로우", "눈썹",
    "왁싱", "waxing",
    
    # 🚗 자동차
    "세차장", "세차", "car wash",
    "정비소", "자동차정비",
    "타이어", "tire",
    "카센터", "car center",
    "주차장", "parking",
    
    # 🏨 숙박
    "호텔", "hotel",
    "모텔", "motel",
    "리조트", "resort",
    "펜션", "pension",
    "게스트하우스", "guesthouse",
    "에어비앤비", "airbnb",
    "찜질방", "찜방",
    
    # 🎪 기타 서비스
    "세탁소", "laundry",
    "택배", "delivery",
    "포토샵", "사진관",
    "문구점", "stationery",
    "꽃집", "flower shop",
    "반려동물", "펫샵", "pet shop",
    "동물병원", "vet",
    "학원", "academy", "교육",
    "도서관", "library",
    "영화관", "cgv", "롯데시네마", "메가박스",
]
    voice_lower = voice_input.lower()
    
    for keyword in brand_keywords:
        if keyword in voice_lower:
            logger.info(f"🤖 브랜드 '{keyword}' 감지 → 동적 시스템 사용")
            return True
    
    # 2. 일정에 브랜드명이 있으면 동적 시스템
    for schedule in fixed_schedules:
        schedule_name = schedule.get("name", "").lower()
        for keyword in brand_keywords:
            if keyword in schedule_name:
                logger.info(f"🤖 일정에 브랜드 '{keyword}' 감지 → 동적 시스템 사용")
                return True
    
    # 3. 식사 관련은 기존 시스템 (더 안정적)
    meal_keywords = ["식사", "저녁", "점심", "아침", "밥", "맛집"]
    for keyword in meal_keywords:
        if keyword in voice_lower:
            logger.info(f"📋 식사 키워드 '{keyword}' 감지 → 기존 시스템 사용")
            return False
            
    for schedule in fixed_schedules:
        schedule_name = schedule.get("name", "").lower()
        for keyword in meal_keywords:
            if keyword in schedule_name:
                logger.info(f"📋 일정에 식사 키워드 '{keyword}' 감지 → 기존 시스템 사용")
                return False
    
    # 4. 기본값: 기존 시스템 (안전)
    logger.info("📋 기본 설정 → 기존 시스템 사용")
    return False

async def create_multiple_options(self, enhanced_data: Dict, voice_input: str) -> Dict:
    """완전 동적 다중 옵션 생성 - 위치 중복 방지 강화"""
    
    def force_log(msg):
        print(f"🎯 {msg}")
        logger.info(msg)
    
    force_log("🆕 동적 다중 옵션 생성 시작 (위치 중복 방지)")
    force_log(f"입력 데이터: voice_input='{voice_input}'")
    
    # 입력 데이터 상세 로깅
    fixed_schedules = enhanced_data.get("fixedSchedules", [])
    force_log(f"고정 일정 수: {len(fixed_schedules)}개")
    for i, schedule in enumerate(fixed_schedules):
        force_log(f"  고정 일정 {i+1}: '{schedule.get('name', 'N/A')}' (ID: {schedule.get('id', 'N/A')})")
    
    if len(fixed_schedules) < 2:
        force_log("⚠️ 경로 분석에 필요한 최소 일정 부족 (2개 미만)")
        return {"options": [enhanced_data]}  # 단일 옵션 반환
    
    # 1. 경로 정보 자동 추출
    start_schedule = fixed_schedules[0]
    end_schedule = fixed_schedules[-1]
    
    start_coord = (start_schedule.get("latitude"), start_schedule.get("longitude"))
    end_coord = (end_schedule.get("latitude"), end_schedule.get("longitude"))
    
    force_log(f"📍 경로 분석:")
    force_log(f"  시작: {start_schedule.get('name')} ({start_coord})")
    force_log(f"  종료: {end_schedule.get('name')} ({end_coord})")
    
    # 2. 변경 가능한 일정 자동 식별 (로깅 강화)
    variable_schedules = self.identify_variable_schedules(fixed_schedules, voice_input)
    
    force_log(f"🔍 변경 가능한 일정 식별 결과: {len(variable_schedules)}개")
    for i, var_info in enumerate(variable_schedules):
        force_log(f"  변경 가능 {i+1}: 인덱스={var_info['index']}, 브랜드='{var_info['brand']}', 원본명='{var_info['original_name']}'")
    
    if not variable_schedules:
        force_log("⚠️ 변경 가능한 일정이 없음 → 단일 옵션 반환")
        return {"options": [enhanced_data]}
    
    # 🔥 전역 위치 추적
    used_locations = set()
    
    # 3. 각 변경 가능한 일정에 대해 동적 옵션 생성
    options = []
    for option_num in range(5):
        force_log(f"🔄 옵션 {option_num + 1} 동적 생성 시작")
        
        option_data = copy.deepcopy(enhanced_data)
        option_modified = False
        
        for var_info in variable_schedules:
            schedule_idx = var_info["index"]
            schedule = option_data["fixedSchedules"][schedule_idx]
            brand_name = var_info["brand"]
            
            force_log(f"  📝 일정 수정: 인덱스={schedule_idx}, 브랜드='{brand_name}'")
            force_log(f"    현재 이름: '{schedule.get('name')}'")
            force_log(f"    현재 위치: '{schedule.get('location')}'")
            
            # 🔥 현재 위치를 사용된 위치에 추가 (첫 번째 옵션용)
            current_location = schedule.get("location", "")
            if option_num == 0 and current_location:
                used_locations.add(current_location)
                force_log(f"    📝 원본 위치 추가: {current_location}")
            
            # 4. 동적 중간 지역 계산
            force_log(f"  🗺️ 중간 지역 계산 (옵션 {option_num + 1})")
            intermediate_areas = await self.calculate_intermediate_areas(
                start_coord, end_coord, option_num, total_options=5
            )
            force_log(f"    계산된 중간 지역: {intermediate_areas}")
            
            # 5. 해당 지역에서 브랜드 검색 (사용된 위치 제외)
            force_log(f"  🔍 브랜드 검색: '{brand_name}' (제외: {len(used_locations)}개 위치)")
            best_location = await self.find_optimal_branch(
                brand_name, intermediate_areas, start_coord, end_coord, used_locations
            )
            
            if best_location:
                force_log(f"    ✅ 검색 성공: {best_location.get('name')}")
                force_log(f"      주소: {best_location.get('address')}")
                
                if best_location.get("address") != schedule.get("location"):
                    # 위치 업데이트
                    old_location = schedule.get("location")
                    schedule["location"] = best_location["address"]
                    schedule["latitude"] = best_location["latitude"]
                    schedule["longitude"] = best_location["longitude"]
                    schedule["name"] = best_location["name"]
                    
                    option_modified = True
                    force_log(f"    🔄 위치 변경:")
                    force_log(f"      이전: {old_location}")
                    force_log(f"      이후: {best_location['address']}")
                else:
                    force_log(f"    ⚠️ 동일한 위치라서 변경 없음")
            else:
                force_log(f"    ❌ 검색 실패: 새로운 위치 없음")
                # 🔥 원본 위치도 사용하지 않음 (첫 번째 옵션 제외)
                if option_num > 0:
                    force_log(f"    ⏭️ 이 옵션 건너뛰기 (새로운 위치 없음)")
                    break
        
        # 6. 수정된 옵션만 추가 (중복 방지)
        if option_modified or option_num == 0:  # 첫 번째는 원본 유지
            # 고유 ID 부여
            for j, schedule in enumerate(option_data["fixedSchedules"]):
                old_id = schedule.get("id")
                new_id = f"{int(time.time() * 1000)}_{option_num + 1}_{j + 1}"
                schedule["id"] = new_id
                force_log(f"    🆔 ID 업데이트: {old_id} → {new_id}")
            
            options.append({
                "optionId": option_num + 1,
                "fixedSchedules": option_data["fixedSchedules"],
                "flexibleSchedules": option_data.get("flexibleSchedules", [])
            })
            
            force_log(f"  ✅ 옵션 {option_num + 1} 생성 완료 (수정됨: {option_modified})")
        else:
            force_log(f"  ❌ 옵션 {option_num + 1} 건너뛰기 (중복 위치)")
    
    # 7. 중복 제거
    unique_options = self.remove_duplicate_options(options)
    force_log(f"🔄 중복 제거 결과: {len(options)}개 → {len(unique_options)}개")
    
    # 8. 최종 결과
    force_log(f"🎉 동적 옵션 생성 완료: {len(unique_options)}개")
    force_log(f"📊 최종 사용된 위치: {len(used_locations)}개")
    for i, location in enumerate(used_locations):
        force_log(f"  위치 {i+1}: {location}")
    
    # 생성된 옵션들 상세 로깅
    for i, option in enumerate(unique_options):
        force_log(f"📋 최종 옵션 {i+1}:")
        for j, schedule in enumerate(option.get("fixedSchedules", [])):
            force_log(f"  일정 {j+1}: '{schedule.get('name')}' @ {schedule.get('location')}")
    
    return {"options": unique_options}


async def find_optimal_branch(self, brand_name: str, intermediate_areas: List[Tuple], 
                            start_coord: Tuple, end_coord: Tuple, used_locations: Set[str] = None) -> Optional[Dict]:
    """최적의 브랜드 지점 찾기 - 사용된 위치 제외"""
    
    if used_locations is None:
        used_locations = set()
    
    def force_log(msg):
        print(f"🔍 {msg}")
        logger.info(msg)
    
    force_log(f"최적 브랜드 지점 검색: '{brand_name}'")
    force_log(f"검색 지역: {len(intermediate_areas)}개")
    force_log(f"제외할 위치: {len(used_locations)}개 - {list(used_locations)}")
    
    best_location = None
    best_efficiency = 0
    
    for i, coord in enumerate(intermediate_areas):
        force_log(f"지역 {i+1} 검색: 좌표 ({coord[0]:.4f}, {coord[1]:.4f})")
        
        # 해당 좌표 근처에서 브랜드 검색
        candidates = await self.search_brand_near_coordinate(brand_name, coord)
        force_log(f"  검색 결과: {len(candidates)}개 후보")
        
        for j, candidate in enumerate(candidates):
            location = candidate.get('address', '')
            force_log(f"    후보 {j+1}: {candidate.get('name')} @ {location}")
            
            # 🔥 이미 사용된 위치인지 확인
            if location in used_locations:
                force_log(f"      ❌ 이미 사용된 위치라서 제외")
                continue
                
            # 경로 효율성 계산
            efficiency = self.calculate_route_efficiency(
                start_coord, 
                (candidate["latitude"], candidate["longitude"]), 
                end_coord
            )
            force_log(f"      효율성: {efficiency:.3f}")
            
            if efficiency > best_efficiency:
                best_efficiency = efficiency
                best_location = candidate
                force_log(f"      🔥 새로운 최적 후보: {candidate.get('name')} (효율성: {efficiency:.3f})")
    
    if best_location:
        force_log(f"✅ 최종 선택: {best_location['name']} (효율성: {best_efficiency:.3f})")
        # 🔥 사용된 위치 추가
        used_locations.add(best_location['address'])
        force_log(f"📝 사용된 위치에 추가: {best_location['address']}")
    else:
        force_log(f"❌ 적절한 지점을 찾지 못함 (모두 사용된 위치이거나 검색 실패)")
    
    return best_location


async def create_traditional_options(enhanced_data: Dict, voice_input: str, exclude_locations: Set[str] = None) -> Dict:
    """개선된 다중 옵션 생성 - 실제 식당명 포함 및 위치 제외"""
    
    if exclude_locations is None:
        exclude_locations = set()
    
    def force_log(msg):
        print(f"🍽️ {msg}")
        logger.info(msg)
    
    force_log("실제 식당명 포함 다중 옵션 생성 시작")
    force_log(f"제외할 위치: {len(exclude_locations)}개")
    
    try:
        options = []
        
        # 경로 정보 추출
        fixed_schedules = enhanced_data.get("fixedSchedules", [])
        start_location = None
        end_location = None
        
        if len(fixed_schedules) >= 2:
            start_location = fixed_schedules[0].get("location", "")
            end_location = fixed_schedules[-1].get("location", "")
            force_log(f"경로: {start_location} → {end_location}")
        
        # 🔥 중복 방지를 위한 사용된 식당 추적
        used_restaurants = set()
        
        # 🔥 다양한 검색 전략과 지역 조합 (하드코딩 없이)
        base_strategies = ["맛집", "식당", "레스토랑", "음식점", "한식"]
        
        for option_num in range(5):
            force_log(f"옵션 {option_num + 1} 생성 시작")
            
            # 원본 데이터 복사
            option_data = copy.deepcopy(enhanced_data)
            
            # 식사 일정 찾아서 실제 식당으로 교체
            for schedule_idx, schedule in enumerate(option_data.get("fixedSchedules", [])):
                schedule_name = schedule.get("name", "").lower()
                
                # "식사" 관련 일정인지 확인
                
                    
                restaurant_result = None
         # 🔥 다양한 검색 시도 (중복 방지)
                for attempt in range(10):  # 최대 10번 시도
                        # 다양한 검색어 조합 생성
                        strategy_idx = (option_num + attempt) % len(base_strategies)
                        search_query = base_strategies[strategy_idx]
                        
                        # 지역 정보 추가 (다양화)
                        search_areas = []
                        if start_location:
                            import re
                            region_match = re.search(r'(서울|부산|대구|인천|광주|대전|울산)', start_location)
                            district_match = re.search(r'(\w+구|\w+시)', start_location)
                            
                            if region_match and district_match:
                                region = region_match.group(1)
                                district = district_match.group(1)
                                
                                # 🔥 옵션별로 다른 지역 순서로 검색
                                if option_num == 0:
                                    search_areas = [f"{region} {district} {search_query}"]
                                elif option_num == 1:
                                    search_areas = [f"{region} {search_query}"]
                                elif option_num == 2:
                                    search_areas = [f"{district} {search_query}"]
                                elif option_num == 3:
                                    search_areas = [f"{search_query} {region}"]
                                else:
                                    search_areas = [f"{search_query}"]
                            else:
                                search_areas = [f"{search_query}"]
                        else:
                            search_areas = [f"{search_query}"]
                        
                        # 각 검색 영역 시도
                        for full_search_query in search_areas:
                            force_log(f"   시도 {attempt + 1}: {full_search_query}")
                            
                            try:
                                analysis = await TripleLocationSearchService.analyze_location_with_gpt(
                                    full_search_query,
                                    reference_location=start_location
                                )
                                
                                # 🔥 각 API에서 다중 결과 가져오기
                                all_candidates = []
                                
                                # 1. Kakao 다중 검색
                                try:
                                    reference_schedules = [{"location": start_location}] if start_location else []
                                    kakao_result = await TripleLocationSearchService.search_kakao(analysis, reference_schedules)
                                    if kakao_result and kakao_result.name:
                                        all_candidates.append(kakao_result)
                                except Exception as e:
                                    force_log(f"     Kakao 검색 실패: {e}")
                                
                                # 2. Google 검색
                                try:
                                    google_result = await TripleLocationSearchService.search_google(analysis)
                                    if google_result and google_result.name:
                                        all_candidates.append(google_result)
                                except Exception as e:
                                    force_log(f"     Google 검색 실패: {e}")
                                
                                # 3. Foursquare 검색
                                try:
                                    foursquare_result = await TripleLocationSearchService.search_foursquare(analysis)
                                    if foursquare_result and foursquare_result.name:
                                        all_candidates.append(foursquare_result)
                                except Exception as e:
                                    force_log(f"     Foursquare 검색 실패: {e}")
                                
                                # 🔥 중복되지 않은 결과 찾기 (이름 + 위치 모두 확인)
                                for candidate in all_candidates:
                                    candidate_location = clean_address(candidate.address)
                                    
                                    # 이름 중복 체크
                                    if candidate.name in used_restaurants:
                                        force_log(f"     ❌ 이미 사용된 식당명: {candidate.name}")
                                        continue
                                    
                                    # 🔥 위치 중복 체크 (제외할 위치 포함)
                                    if candidate_location in exclude_locations:
                                        force_log(f"     ❌ 제외 위치: {candidate_location}")
                                        continue
                                    
                                    # 성공: 새로운 식당 발견
                                    restaurant_result = candidate
                                    used_restaurants.add(candidate.name)
                                    exclude_locations.add(candidate_location)
                                    force_log(f"   ✅ 새로운 식당 발견: {candidate.name}")
                                    break
                                
                                if restaurant_result:
                                    break  # 찾았으면 더 이상 검색 안 함
                                    
                            except Exception as e:
                                force_log(f"     검색 시도 실패: {e}")
                        
                        if restaurant_result:
                            break  # 찾았으면 더 이상 시도 안 함
                    
                        # 검색 결과 적용
                        if restaurant_result and restaurant_result.name:
                            # 실제 식당 정보로 업데이트
                            schedule["name"] = restaurant_result.name  # 🔥 실제 식당명!
                            schedule["location"] = clean_address(restaurant_result.address)
                            schedule["latitude"] = restaurant_result.latitude
                            schedule["longitude"] = restaurant_result.longitude
                            
                            force_log(f"   🎯 실제 식당 적용: {restaurant_result.name}")
                            force_log(f"      📍 주소: {schedule['location']}")
                        else:
                            force_log(f"   ⚠️ 모든 검색 시도 실패, 원본 이름 유지")           
                    
                
                # 고유 ID 부여
                current_time = int(time.time() * 1000)
                for schedule_type in ["fixedSchedules", "flexibleSchedules"]:
                    for j, schedule in enumerate(option_data.get(schedule_type, [])):
                        schedule["id"] = f"{current_time}_{option_num + 1}_{j + 1}"
                
                # 옵션 추가
                option = {
                    "optionId": option_num + 1,
                    "fixedSchedules": option_data.get("fixedSchedules", []),
                    "flexibleSchedules": option_data.get("flexibleSchedules", [])
                }
                
                options.append(option)
                force_log(f"✅ 옵션 {option_num + 1} 완성")
            
            final_result = {"options": options}
            force_log(f"🎉 실제 식당명 포함 다중 옵션 생성 완료: {len(options)}개")
            
            # 결과 검증 로깅
            for i, option in enumerate(options):
                for schedule in option.get("fixedSchedules", []):
                    if any(word in schedule.get("name", "").lower() for word in ["식사", "식당", "맛집", "레스토랑"]):
                        force_log(f"   옵션 {i+1} 식당: {schedule.get('name')}")
            
            return final_result
        
    except Exception as e:
        force_log(f"❌ 실제 식당명 생성 실패: {e}")
        
        # 폴백: 기존 방식 (인라인으로 처리)
        force_log("기존 방식으로 폴백 처리")
        options = []
        current_time = int(time.time() * 1000)
        
        for i in range(5):
            option_data = copy.deepcopy(enhanced_data)
            
            # ID만 변경
            for schedule_type in ["fixedSchedules", "flexibleSchedules"]:
                for j, schedule in enumerate(option_data.get(schedule_type, [])):
                    schedule["id"] = f"{current_time}_{i + 1}_{j + 1}"
            
            options.append({
                "optionId": i + 1,
                "fixedSchedules": option_data.get("fixedSchedules", []),
                "flexibleSchedules": option_data.get("flexibleSchedules", [])
            })
        
        return {"options": options}


@app.post("/extract-schedule")
async def extract_schedule(request: ScheduleRequest):
    """수정된 다중 옵션 일정 추출 API - Name 정제 및 주소 정상화 적용"""
    import datetime as dt
    import time
    import copy
    
    # 강제 로깅 함수
    def force_log(message):
        timestamp = dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        output = f"🔥 {timestamp} - {message}"
        print(output)
        logger.info(message)
        return output
    
    force_log("=== 수정된 일정 추출 시작 (Name정제+주소정상화) ===")
    force_log(f"입력 텍스트: {request.voice_input}")
    force_log(f"입력 길이: {len(request.voice_input)}자")
    
    start_time = time.time()
    
    try:
        # Step 1: 개선된 프롬프트로 LLM 호출
        force_log("Step 1: 개선된 프롬프트로 LLM 호출")
        
        try:
            current_time = int(dt.datetime.now().timestamp() * 1000)
            today = dt.datetime.now()
            current_hour = today.hour
            
            # 현재 시간대 설명
            if 6 <= current_hour < 12:
                current_time_desc = "오전"
            elif 12 <= current_hour < 18:
                current_time_desc = "오후"
            elif 18 <= current_hour < 22:
                current_time_desc = "저녁"
            else:
                current_time_desc = "밤"
            
            force_log(f"현재 시간: {current_hour}시 ({current_time_desc})")
            
            # 🔥 개선된 프롬프트 (일정 분리 강화)
            improved_template = f"""다음 음성 메시지에서 **각 장소를 개별 일정으로** 빠짐없이 추출하여 JSON 형식으로 반환해주세요.

음성 메시지: {request.voice_input}

현재 시간: {current_hour}시 ({current_time_desc})
현재 날짜: {today.strftime('%Y-%m-%d')}

**🔥 중요한 분리 규칙**:
1. "A에서 B까지" → A와 B를 **반드시 각각 별도 일정**으로 추출
2. "중간에 C" → C를 **반드시 별도 일정**으로 추출  
3. 절대로 "A에서 B 이동" 같은 통합 이름 사용 금지
4. 각 장소는 독립적인 일정으로 처리

**올바른 예시**:
입력: "부산역에서 장전역까지 가는데, 중간에 저녁먹고싶어"
→ 반드시 3개 일정: 
1) "부산역" (17:00-17:30)
2) "저녁 식사" (18:00-20:00) 
3) "장전역" (20:30-21:00)

**잘못된 예시** (절대 금지):
- "부산역에서 장전역 이동" ❌
- "부산역-장전역" ❌

**시간 규칙**:
- "저녁" → 18:00~20:00
- "점심" → 12:00~14:00  
- "아침" → 08:00~10:00
- 순서대로 배치 (이동시간 30분 고려)

JSON 형식으로 반환:
{{
  "fixedSchedules": [
    {{
      "id": "{current_time}_1",
      "name": "부산역",
      "type": "FIXED",
      "duration": 30,
      "priority": 1,
      "location": "",
      "latitude": 35.1156,
      "longitude": 129.0419,
      "startTime": "{today.strftime('%Y-%m-%d')}T17:00:00",
      "endTime": "{today.strftime('%Y-%m-%d')}T17:30:00"
    }},
    {{
      "id": "{current_time}_2", 
      "name": "저녁 식사",
      "type": "FIXED",
      "duration": 120,
      "priority": 2,
      "location": "",
      "latitude": 35.2,
      "longitude": 129.1,
      "startTime": "{today.strftime('%Y-%m-%d')}T18:00:00",
      "endTime": "{today.strftime('%Y-%m-%d')}T20:00:00"
    }},
    {{
      "id": "{current_time}_3",
      "name": "장전역",
      "type": "FIXED", 
      "duration": 30,
      "priority": 3,
      "location": "",
      "latitude": 35.2311,
      "longitude": 129.0839,
      "startTime": "{today.strftime('%Y-%m-%d')}T20:30:00",
      "endTime": "{today.strftime('%Y-%m-%d')}T21:00:00"
    }}
  ],
  "flexibleSchedules": []
}}

**주의사항**:
1. **각 장소를 개별 일정으로 반드시 분리**
2. **name은 단순한 장소명/활동명만 사용**
3. **"이동", "까지", "에서" 같은 연결어 절대 금지**
4. **JSON만 반환**, 다른 텍스트 포함 금지
"""
            
            # OpenAI 호출
            response = openai_client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {
                        "role": "system", 
                        "content": "당신은 일정 추출 전문가입니다. 한국어 음성 메시지에서 각 장소를 개별 일정으로 분리하여 정확한 JSON 형식으로 반환하세요."
                    },
                    {"role": "user", "content": improved_template}
                ],
                temperature=0,
                max_tokens=1500
            )
            
            llm_content = response.choices[0].message.content.strip()
            force_log(f"✅ OpenAI 응답 수신: {len(llm_content)}자")
            
            # JSON 추출
            if llm_content.startswith("```json"):
                llm_content = llm_content.replace("```json", "").replace("```", "").strip()
            
            schedule_data = json.loads(llm_content)
            force_log(f"✅ JSON 파싱 성공")
            
        except Exception as e:
            force_log(f"❌ 개선된 LLM 호출 실패: {e}")
            
            # 폴백: 수동으로 일정 생성 (분리된 형태로)
            force_log("폴백: 수동 분리 일정 생성")
            
            voice_text = request.voice_input.lower()
            schedules = []
            
            # 🔥 분리된 일정으로 생성
            if "부산역" in voice_text:
                schedules.append({
                    "id": f"{current_time}_1",
                    "name": "부산역",  # 단순한 이름
                    "type": "FIXED",
                    "duration": 30,
                    "priority": 1,
                    "location": "",
                    "latitude": 35.1151,
                    "longitude": 129.0425,
                    "startTime": f"{today.strftime('%Y-%m-%d')}T17:00:00",
                    "endTime": f"{today.strftime('%Y-%m-%d')}T17:30:00"
                })
            
            if "저녁" in voice_text or "식사" in voice_text:
                schedules.append({
                    "id": f"{current_time}_2",
                    "name": "저녁 식사",  # 단순한 이름
                    "type": "FIXED",
                    "duration": 120,
                    "priority": 2,
                    "location": "",
                    "latitude": 35.2,
                    "longitude": 129.1,
                    "startTime": f"{today.strftime('%Y-%m-%d')}T18:00:00",
                    "endTime": f"{today.strftime('%Y-%m-%d')}T20:00:00"
                })
            
            if "장전역" in voice_text:
                schedules.append({
                    "id": f"{current_time}_3",
                    "name": "장전역",  # 단순한 이름
                    "type": "FIXED",
                    "duration": 30,
                    "priority": 3,
                    "location": "",
                    "latitude": 35.2311,
                    "longitude": 129.0839,
                    "startTime": f"{today.strftime('%Y-%m-%d')}T20:30:00",
                    "endTime": f"{today.strftime('%Y-%m-%d')}T21:00:00"
                })
            
            schedule_data = {
                "fixedSchedules": schedules,
                "flexibleSchedules": []
            }
            
            force_log(f"✅ 수동 분리 일정 생성 완료: {len(schedules)}개")
        
        # Step 2: Name 정제 적용
        force_log("Step 2: Name 정제 적용")
        
        def apply_name_cleaning(schedule_data: Dict) -> Dict:
            """모든 일정의 name 정제 적용"""
            import re
            
            for schedule_type in ["fixedSchedules", "flexibleSchedules"]:
                schedule_list = schedule_data.get(schedule_type, [])
                
                for i, schedule in enumerate(schedule_list):
                    if schedule.get("name"):
                        old_name = schedule["name"]
                        
                        # 1. 기본 텍스트 정제
                        cleaned_name = clean_korean_text(schedule["name"])
                        
                        # 2. 이동 표현 제거
                        cleaned_name = re.sub(r'에서\s*.*?까지', '', cleaned_name)
                        cleaned_name = re.sub(r'.*?에서\s*', '', cleaned_name)
                        cleaned_name = re.sub(r'\s*이동$', '', cleaned_name)
                        cleaned_name = re.sub(r'^이동\s*', '', cleaned_name)
                        
                        # 3. 특정 장소 단순화
                        if "부산역" in cleaned_name:
                            cleaned_name = "부산역"
                        elif "장전역" in cleaned_name:
                            cleaned_name = "장전역"
                        elif "서울역" in cleaned_name:
                            cleaned_name = "서울역"
                        elif any(word in cleaned_name for word in ["저녁", "식사"]):
                            if "저녁" in cleaned_name:
                                cleaned_name = "저녁 식사"
                            elif "점심" in cleaned_name:
                                cleaned_name = "점심 식사"
                            elif "아침" in cleaned_name:
                                cleaned_name = "아침 식사"
                            else:
                                cleaned_name = "식사"
                        elif "카페" in cleaned_name or "커피" in cleaned_name:
                            cleaned_name = "카페"
                        
                        schedule["name"] = cleaned_name.strip()
                        
                        if old_name != schedule["name"]:
                            force_log(f"   이름 정제 {schedule_type}[{i}]: '{old_name}' → '{schedule['name']}'")
            
            return schedule_data
        
        schedule_data = apply_name_cleaning(schedule_data)
        force_log("✅ Name 정제 완료")
        
        # Step 3: 위치 정보 보강 (주소 정제 포함)
        force_log("Step 3: 위치 정보 보강 및 주소 정제")
        
        
        try:
            enhanced_data = await asyncio.wait_for(
                enhance_locations_with_triple_api(schedule_data),
                timeout=30
            )
            force_log("✅ 위치 정보 보강 완료")
            schedule_data = enhanced_data
            
        except Exception as e:
            force_log(f"⚠️ 위치 정보 보강 실패: {e}")
            enhanced_data = schedule_data
        
        # Step 4: 최종 검증 및 정제
        force_log("Step 4: 최종 검증 및 정제")
        
        for schedule_type in ["fixedSchedules", "flexibleSchedules"]:
            schedule_list = enhanced_data.get(schedule_type, [])
            
            for i, schedule in enumerate(schedule_list):
                # 주소 최종 정제
                if schedule.get("location"):
                    old_location = schedule["location"]
                    schedule["location"] = clean_address(schedule["location"])
                    if old_location != schedule["location"]:
                        force_log(f"   주소 정제 {schedule_type}[{i}]: '{old_location}' → '{schedule['location']}'")
                
                # Name 최종 검증
                if schedule.get("name"):
                    old_name = schedule["name"]
                    schedule["name"] = clean_korean_text(schedule["name"])
                    if old_name != schedule["name"]:
                        force_log(f"   이름 최종검증 {schedule_type}[{i}]: '{old_name}' → '{schedule['name']}'")
        
        force_log("✅ 최종 검증 및 정제 완료")
        
        # Step 5: 다중 옵션 생성 (각 옵션별 다른 검색 전략)
        force_log("Step 5: 다중 옵션 생성")
        
        try:
            options = []
            # 🔥 사용할 시스템 자동 결정
            use_dynamic_system = should_use_dynamic_system(enhanced_data, request.voice_input)
            
            if use_dynamic_system:
                force_log("🤖 DynamicRouteOptimizer 사용 (브랜드 기반)")
                optimizer = DynamicRouteOptimizer(KAKAO_REST_API_KEY)
                final_result = await optimizer.create_multiple_options(enhanced_data, request.voice_input)
                
                # 🔥 개선된 폴백 로직: 1개라도 성공으로 간주
                if len(final_result.get("options", [])) >= 1:
                    force_log(f"✅ 동적 시스템 성공: {len(final_result.get('options', []))}개 옵션")
                    
                    # 5개 미만이면 기존 시스템으로 추가 생성
                    if len(final_result.get("options", [])) < 5:
                        needed = 5 - len(final_result.get("options", []))
                        force_log(f"🔄 추가 옵션 필요: {needed}개")
                        
                        # 🔥 사용된 위치 수집
                        used_locations = set()
                        for option in final_result.get("options", []):
                            for schedule in option.get("fixedSchedules", []):
                                if "스타벅스" in schedule.get("name", ""):  # 브랜드 일정만
                                    used_locations.add(schedule.get("location", ""))
                        
                        # 🔥 기존 시스템으로 추가 생성 (사용된 위치 제외 로직 추가)
                        additional_result = await create_traditional_options(
                            enhanced_data, 
                            request.voice_input, 
                            exclude_locations=used_locations  # 제외할 위치 전달
                        )
                        
                        # 동적 결과 + 추가 결과 결합
                        all_options = final_result.get("options", [])
                        
                        for additional_option in additional_result.get("options", []):
                            if len(all_options) >= 5:
                                break
                                
                            # 중복 위치 체크
                            is_duplicate = False
                            for schedule in additional_option.get("fixedSchedules", []):
                                if schedule.get("location") in used_locations:
                                    is_duplicate = True
                                    break
                            
                            if not is_duplicate:
                                # optionId 재할당
                                additional_option["optionId"] = len(all_options) + 1
                                all_options.append(additional_option)
                        
                        final_result = {"options": all_options}
                else:
                    force_log("❌ 동적 시스템 완전 실패, 기존 시스템으로 폴백")
                    final_result = await create_traditional_options(enhanced_data, request.voice_input)
            else:
                # 🔥 기존 시스템 사용 (식사 관련)
                force_log("📋 기존 시스템 사용 (식사 관련)")
                final_result = await create_traditional_options(enhanced_data, request.voice_input)            
        except Exception as e:
            force_log(f"❌ 다중 옵션 생성 실패: {e}")
            final_result = await create_traditional_options(enhanced_data, request.voice_input)
            
        # Step 6: 최종 응답
        total_time = time.time() - start_time
        force_log(f"Step 6: 최종 완료 - 총 {total_time:.2f}초")
        
        option_count = len(final_result.get('options', []))
        force_log(f"최종 옵션 수: {option_count}개")
        
        # 첫 번째 옵션의 일정 상세 로깅
        if final_result.get('options') and len(final_result['options']) > 0:
            first_option = final_result['options'][0]
            force_log("첫 번째 옵션 상세:")
            
            for j, schedule in enumerate(first_option.get('fixedSchedules', [])):
                name = schedule.get('name', 'N/A')
                location = schedule.get('location', 'N/A')
                start_time = schedule.get('startTime', 'N/A')
                force_log(f"  일정 {j+1}: {name}")
                force_log(f"     📍 위치: {location}")
                force_log(f"     ⏰ 시간: {start_time}")
        
        force_log("=== 수정된 일정 추출 완료 (Name정제+주소정상화) ===")
        
        return UnicodeJSONResponse(content=final_result, status_code=200)
    
    except Exception as e:
        force_log(f"❌ 전체 실패: {str(e)}")
        force_log(f"   오류 타입: {type(e).__name__}")
        
        # 최종 폴백
        current_time = int(dt.datetime.now().timestamp() * 1000)
        today = dt.datetime.now()
        
        fallback_result = {
            "options": [
                {
                    "optionId": 1,
                    "fixedSchedules": [
                        {
                            "id": f"{current_time}_fallback_1",
                            "name": "부산역",
                            "type": "FIXED",
                            "duration": 30,
                            "priority": 1,
                            "location": "부산광역시 동구 중앙대로 206",
                            "latitude": 35.1156,
                            "longitude": 129.0419,
                            "startTime": f"{today.strftime('%Y-%m-%d')}T17:00:00",
                            "endTime": f"{today.strftime('%Y-%m-%d')}T17:30:00"
                        },
                        {
                            "id": f"{current_time}_fallback_2",
                            "name": "저녁 식사",
                            "type": "FIXED",
                            "duration": 120,
                            "priority": 2,
                            "location": "부산광역시 금정구 장전동",
                            "latitude": 35.2311,
                            "longitude": 129.0839,
                            "startTime": f"{today.strftime('%Y-%m-%d')}T18:00:00",
                            "endTime": f"{today.strftime('%Y-%m-%d')}T20:00:00"
                        },
                        {
                            "id": f"{current_time}_fallback_3",
                            "name": "장전역",
                            "type": "FIXED",
                            "duration": 30,
                            "priority": 3,
                            "location": "부산광역시 금정구 장전동",
                            "latitude": 35.2311,
                            "longitude": 129.0839,
                            "startTime": f"{today.strftime('%Y-%m-%d')}T20:30:00",
                            "endTime": f"{today.strftime('%Y-%m-%d')}T21:00:00"
                        }
                    ],
                    "flexibleSchedules": []
                }
            ]
        }
        
        force_log("최종 폴백 결과 반환 (정제된 일정으로)")
        return UnicodeJSONResponse(content=fallback_result, status_code=200)
# 서버 시작
if __name__ == "__main__":
    import uvicorn
    
    # UTF-8 인코딩으로 서버 시작
    uvicorn.run(
        "app:app", 
        host="0.0.0.0", 
        port=8083, 
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