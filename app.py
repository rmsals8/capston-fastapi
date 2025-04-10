from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from langchain_openai import OpenAI
from langchain.prompts import PromptTemplate
import os
import json
import re
import time
import requests
import datetime
from dotenv import load_dotenv

# 환경 변수 로드
load_dotenv()

app = FastAPI()

# 입력 모델 정의
class ScheduleRequest(BaseModel):
    voice_input: str

# 프롬프트 템플릿 개선 - 더 명확한 지시사항과 날짜 처리 안내 추가
prompt_template = """다음 음성 메시지에서 일정 정보를 추출하여 JSON 형식으로 반환해주세요.

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

예시:
입력: "내일 오전 10시에 강남역에서 회의 있고, 점심에는 식당에서 식사하고 싶어."
출력:
{{
  "fixedSchedules": [
    {{
      "id": "1680123456789",
      "name": "강남역",
      "type": "FIXED",
      "duration": 60,
      "priority": 1,
      "location": "서울특별시 강남구 강남대로 지하 396",
      "latitude": 37.4980,
      "longitude": 127.0276,
      "startTime": "{tomorrow_date}T10:00:00",
      "endTime": "{tomorrow_date}T11:00:00"
    }}
  ],
  "flexibleSchedules": [
    {{
      "id": "1680123456790",
      "name": "식당",
      "type": "FLEXIBLE",
      "duration": 60,
      "priority": 3,
      "location": "강남역 인근",
      "latitude": 37.5665,
      "longitude": 126.9780
    }}
  ]
}}

음성 메시지: {input}
"""


# 새로운 향상된 위치 정보 보강 함수 (요청한 대로 추가)
def enhanced_location_data(schedule_data):
    """
    향상된 위치 정보 보강 함수 - 장소명 보존 및 카테고리 기반 검색
    """
    print("향상된 위치 정보 보강 시작...")
    
    # Google Maps API 키 확인
    api_key = os.getenv("GOOGLE_MAPS_API_KEY")
    if not api_key:
        print("경고: GOOGLE_MAPS_API_KEY가 환경 변수에 설정되지 않았습니다.")
        return schedule_data
    
    # 복사본 생성하여 원본 데이터 보존
    enhanced_data = json.loads(json.dumps(schedule_data))
    
    # 고정 일정 처리 - 정확한 장소명과 주소 유지
    if "fixedSchedules" in enhanced_data and isinstance(enhanced_data["fixedSchedules"], list):
        for i, schedule in enumerate(enhanced_data["fixedSchedules"]):
            print(f"고정 일정 {i+1} 처리 중: {schedule.get('name', '이름 없음')}")
            
            # 원래 장소명 저장
            original_name = schedule.get("name", "")
            
            # 더 정확한 검색어 구성 (예: "강남역" 대신 "서울 강남역")
            search_term = f"서울 {original_name}"
            
            if original_name:
                print(f"'{search_term}' 장소 정보 검색 중...")
                place_info = get_place_details(search_term, api_key)
                
                if place_info:
                    print(f"장소 정보 검색 성공: {place_info.get('name')}")
                    
                    # 원래 장소명 보존
                    # 정확한 주소 업데이트
                    if place_info.get("formatted_address"):
                        print(f"주소 업데이트: '{schedule.get('location', '')}' -> '{place_info['formatted_address']}'")
                        schedule["location"] = place_info["formatted_address"]
                    
                    # 좌표 업데이트
                    if place_info.get("latitude") and place_info.get("longitude"):
                        schedule["latitude"] = place_info["latitude"]
                        schedule["longitude"] = place_info["longitude"]
                        print(f"좌표 업데이트: [{place_info['latitude']}, {place_info['longitude']}]")
    
    # 유연 일정 처리 - 카테고리 기반 또는 지역 근처 검색
    if "flexibleSchedules" in enhanced_data and isinstance(enhanced_data["flexibleSchedules"], list):
        for i, schedule in enumerate(enhanced_data["flexibleSchedules"]):
            print(f"유연 일정 {i+1} 처리 중: {schedule.get('name', '이름 없음')}")
            
            # 카테고리에 따른 검색어 구성
            category = schedule.get("name", "")
            
            if "식사" in category or "식당" in category:
                search_term = "서울 강남 맛집"  # 고정 일정 근처 검색
            elif "카페" in category:
                search_term = "서울 강남 카페"
            else:
                # 기본 검색어
                search_term = f"서울 강남 {category}"
            
            print(f"'{search_term}' 장소 정보 검색 중...")
            place_info = get_nearby_places(search_term, api_key)
            
            if place_info:
                print(f"장소 정보 검색 성공: {place_info.get('name')}")
                
                # 카테고리는 유지하면서 구체적인 장소 제안
                original_name = schedule.get("name", "")
                schedule["name"] = f"{original_name} - {place_info.get('name', '')}"
                
                # 정확한 주소 업데이트
                if place_info.get("formatted_address"):
                    print(f"주소 업데이트: '{schedule.get('location', '')}' -> '{place_info['formatted_address']}'")
                    schedule["location"] = place_info["formatted_address"]
                
                # 좌표 업데이트
                if place_info.get("latitude") and place_info.get("longitude"):
                    schedule["latitude"] = place_info["latitude"]
                    schedule["longitude"] = place_info["longitude"]
                    print(f"좌표 업데이트: [{place_info['latitude']}, {place_info['longitude']}]")
    
    print("향상된 위치 정보 보강 완료")
    return enhanced_data

# 근처 장소를 찾는 새로운 함수 추가
def get_nearby_places(query, api_key, location=None):
    """
    카테고리와 지역 기반으로 주변 장소 검색
    """
    try:
        # 기본 위치 (고정 일정 위치 또는 강남 기준)
        if not location:
            location = "37.4980,127.0276"  # 강남역 좌표
        
        # 장소 검색 API 사용
        nearby_url = f"https://maps.googleapis.com/maps/api/place/nearbysearch/json?location={location}&radius=1000&keyword={requests.utils.quote(query)}&language=ko&key={api_key}"
        
        print(f"주변 장소 검색 API 요청: {nearby_url.replace(api_key, 'API_KEY')}")
        response = requests.get(nearby_url)
        
        print(f"주변 장소 검색 API 응답 상태: {response.status_code}")
        
        if response.status_code == 200:
            data = json.loads(response.text)
            
            if data['status'] == 'OK' and data.get('results') and len(data['results']) > 0:
                # 상위 인기 장소 선택
                top_place = data['results'][0]
                
                place_info = {
                    'name': top_place.get('name', ''),
                    'formatted_address': top_place.get('vicinity', ''),
                    'latitude': top_place['geometry']['location']['lat'],
                    'longitude': top_place['geometry']['location']['lng'],
                    'place_id': top_place.get('place_id', '')
                }
                
                return place_info
            else:
                print(f"주변 장소를 찾을 수 없음: {data['status']}")
        else:
            print(f"주변 장소 API 요청 실패: {response.status_code}")
    
    except Exception as e:
        print(f"주변 장소 검색 중 오류 발생: {str(e)}")
    
    return None

# Google Places API로 장소 상세 정보 조회 (원본 함수 유지)
def get_place_details(place_name, api_key):
    """
    Google Places API를 사용하여 장소 상세 정보를 조회합니다.
    """
    try:
        # URL 인코딩
        encoded_place = requests.utils.quote(place_name)
        
        # Google Places API - 텍스트 검색
        # search_url = f"https://maps.googleapis.com/maps/api/place/findplacefromtext/json?input={encoded_place}&inputtype=textquery&fields=name,formatted_address,geometry,place_id&key={api_key}"
        search_url = f"https://maps.googleapis.com/maps/api/place/findplacefromtext/json?input={encoded_place}&inputtype=textquery&fields=name,formatted_address,geometry,place_id,address_components&key={api_key}"
        
        print(f"Google Places API 요청: {search_url.replace(api_key, 'API_KEY')}")
        response = requests.get(search_url)
        
        print(f"Google Places API 응답 상태: {response.status_code}")
        
        if response.status_code == 200:
            data = json.loads(response.text)
            print(f"Google Places API 응답: {json.dumps(data, ensure_ascii=False)}")
            
            if data['status'] == 'OK' and data.get('candidates') and len(data['candidates']) > 0:
                candidate = data['candidates'][0]
                
                place_info = {
                    'name': candidate.get('name', place_name),
                    'formatted_address': candidate.get('formatted_address', ''),
                    'latitude': candidate['geometry']['location']['lat'],
                    'longitude': candidate['geometry']['location']['lng'],
                    'place_id': candidate.get('place_id', '')
                }
                
                # 더 상세한 정보가 필요한 경우 place_id로 추가 요청할 수 있음
                if place_info['place_id']:
                    print(f"더 상세한 정보 조회를 위한 place_id: {place_info['place_id']}")
                
                return place_info
            else:
                print(f"장소를 찾을 수 없음: {data['status']}")
        else:
            print(f"API 요청 실패: {response.status_code}")
    
    except Exception as e:
        print(f"장소 정보 조회 중 오류 발생: {str(e)}")
    
    return None

# 최신 LangChain 방식으로 체인 생성
def create_schedule_chain():
    # 환경 변수에서 API 키 직접 확인
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("OPENAI_API_KEY가 환경 변수에 설정되지 않았습니다.")
    
    print(f"API 키 확인: {api_key[:5]}...")  # 디버깅용
    
    # 현재 밀리초 값 가져오기
    current_time = int(time.time() * 1000)
    current_time_plus = current_time + 1
    
    # 현재 날짜 계산
    today = datetime.datetime.now()
    tomorrow = today + datetime.timedelta(days=1)
    day_after_tomorrow = today + datetime.timedelta(days=2)
    next_week = today + datetime.timedelta(days=7)
    
    # 프롬프트 템플릿 객체 생성
    prompt = PromptTemplate(
        template=prompt_template,
        input_variables=["input"],
        partial_variables={
            "current_milliseconds": str(current_time),
            "current_milliseconds_plus": str(current_time_plus),
            "today_date": today.strftime("%Y-%m-%d"),
            "tomorrow_date": tomorrow.strftime("%Y-%m-%d"),
            "day_after_tomorrow_date": day_after_tomorrow.strftime("%Y-%m-%d"),
            "next_week_date": next_week.strftime("%Y-%m-%d")
        }
    )
    
    llm = OpenAI(temperature=0, openai_api_key=api_key)
    
    # 새로운 방식: RunnableSequence 사용
    chain = prompt | llm
    
    return chain

# JSON 파싱 함수 - 문자열 수정 및 오류 방지
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

@app.get("/")
async def root():
    return {"message": "일정 추출 API가 실행 중입니다."}

@app.post("/enhanced-schedule")
async def enhanced_schedule(request: ScheduleRequest):
    """
    음성 입력에서 일정을 추출하고 향상된 방식으로 위치 정보를 보강합니다.
    """
    try:
        print(f"음성 입력 받음 (향상된 위치 정보 보강): '{request.voice_input}'")
        
        # 1. 일정 추출
        chain = create_schedule_chain()
        print("LangChain 처리 중...")
        result = chain.invoke({"input": request.voice_input})
        print(f"LangChain 응답 길이: {len(result)}자")
        
        # 2. 결과에서 JSON 부분만 추출
        json_match = re.search(r'({[\s\S]*})', result)
        if not json_match:
            print("JSON 결과를 추출할 수 없습니다.")
            raise HTTPException(status_code=422, detail="JSON 결과를 추출할 수 없습니다")
        
        json_str = json_match.group(1)
        print(f"추출된 JSON 문자열: {json_str}")
        
        # 3. 안전하게 JSON 파싱
        schedule_data = safe_parse_json(json_str)
        print(f"파싱된 일정 데이터: {json.dumps(schedule_data, ensure_ascii=False)}")
        
        # 4. 향상된 위치 정보 보강 - 수정된 함수 사용
        enhanced_data = enhanced_location_data(schedule_data)
        print(f"향상된 위치 정보 보강된 일정 데이터: {json.dumps(enhanced_data, ensure_ascii=False)}")
        
        return enhanced_data
        
    except Exception as e:
        print(f"일정 처리 오류: {str(e)}")
        raise HTTPException(status_code=500, detail=f"일정 처리 중 오류 발생: {str(e)}")
  # FastAPI 서버 실행 코드 (직접 python app.py로 실행할 때 사용)
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="0.0.0.0", port=8081, reload=True)
