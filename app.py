from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from langchain_openai import OpenAI
from langchain.prompts import PromptTemplate
import os
import json
import re
import time
from dotenv import load_dotenv

# 환경 변수 로드
load_dotenv()

app = FastAPI()

# 입력 모델 정의
class ScheduleRequest(BaseModel):
    voice_input: str

# 기존 프롬프트 템플릿 사용
prompt_template = """다음 음성 메시지에서 일정 정보를 추출하여 JSON 형식으로 반환해주세요.

필요한 정보:
- 장소명(name): 방문할 장소 이름
- 일정 유형(type): "FIXED"(고정 일정) 또는 "FLEXIBLE"(유연한 일정)
- 소요 시간(duration): 분 단위 (언급이 없으면 60분으로 설정)
- 우선순위(priority): 1-5 사이 숫자 (언급이 없으면 1로 설정)
- 위치(location): 장소의 주소나 위치 설명
- 시작 시간(startTime): ISO 8601 형식 (YYYY-MM-DDTHH:MM:SS)
- 종료 시간(endTime): ISO 8601 형식 (시작 시간 + 소요 시간)

다음 JSON 형식으로 반환해주세요:
{
  "fixedSchedules": [
    {
      "id": "${current_milliseconds}",
      "name": "장소명",
      "type": "FIXED",
      "duration": 60,
      "priority": 1,
      "location": "위치 상세",
      "latitude": 37.5665,
      "longitude": 126.9780,
      "startTime": "2023-12-01T10:00:00",
      "endTime": "2023-12-01T11:00:00"
    }
  ],
  "flexibleSchedules": [
    {
      "id": "${current_milliseconds + 1}",
      "name": "방문할 곳",
      "type": "FLEXIBLE",
      "duration": 60,
      "priority": 3,
      "location": "위치 상세",
      "latitude": 37.5665,
      "longitude": 126.9780
    }
  ]
}

시간이 명확한 일정은 fixedSchedules에, 시간이 불명확한 일정은 flexibleSchedules에 포함시켜주세요.
각 일정의 id는 현재 시간 기준 밀리초로 설정해주세요.
latitude와 longitude 값은 장소에 맞게 적절히 설정해주세요.
한글이 포함된 JSON 응답을 보낼 때 UTF-8 인코딩이 유지되도록 해주세요.

음성 메시지: {input}
"""

# 최신 LangChain 방식으로 체인 생성
def create_schedule_chain():
    # 환경 변수에서 API 키 직접 확인
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("OPENAI_API_KEY가 환경 변수에 설정되지 않았습니다.")
    
    print(f"API 키 확인: {api_key[:5]}...")  # 디버깅용
    
    # 현재 밀리초 값 가져오기
    current_time = int(time.time() * 1000)
    
    # 프롬프트 템플릿에 현재 시간 삽입
    current_prompt = prompt_template.replace("${current_milliseconds}", str(current_time))
    
    prompt = PromptTemplate(
        template=current_prompt,
        input_variables=["input"]
    )
    
    llm = OpenAI(temperature=0, openai_api_key=api_key)
    
    # 새로운 방식: RunnableSequence 사용
    chain = prompt | llm
    
    return chain

@app.get("/")
async def root():
    return {"message": "일정 추출 API가 실행 중입니다."}

@app.post("/extract-schedule")
async def extract_schedule(request: ScheduleRequest):
    try:
        chain = create_schedule_chain()
        
        # 최신 방식: invoke 사용
        result = chain.invoke({"input": request.voice_input})
        
        # 결과에서 JSON 부분만 추출
        json_match = re.search(r'({[\s\S]*})', result)
        if json_match:
            json_str = json_match.group(1)
            schedule_data = json.loads(json_str)
            return schedule_data
        else:
            raise HTTPException(status_code=422, detail="JSON 결과를 추출할 수 없습니다")
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"일정 추출 중 오류 발생: {str(e)}")