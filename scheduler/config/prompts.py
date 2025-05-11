# scheduler/config/prompts.py
from langchain.prompts import PromptTemplate
from langchain.output_parsers import ResponseSchema, StructuredOutputParser

# 시간 추론을 위한 출력 스키마
time_schemas = [
    ResponseSchema(name="time_expressions", description="메시지에서 발견된 모든 시간 관련 표현"),
    ResponseSchema(name="inferred_times", description="각 표현에 대한 추론된 시작 및 종료 시간 (ISO 형식)"),
    ResponseSchema(name="reasoning", description="시간 추론 과정에 대한 설명")
]
time_parser = StructuredOutputParser.from_response_schemas(time_schemas)

# 우선순위를 위한 출력 스키마
priority_schemas = [
    ResponseSchema(name="schedule_priorities", description="각 일정별 우선순위 (id와 priority 값 포함)"),
    ResponseSchema(name="sequence_expressions", description="발견된 순서 표현과 연관된 일정"),
    ResponseSchema(name="reasoning", description="우선순위 결정 과정에 대한 설명")
]
priority_parser = StructuredOutputParser.from_response_schemas(priority_schemas)

# 시간 추론 프롬프트
TIME_INFERENCE_TEMPLATE = """
당신은 일정 계획에서 시간 표현을 정확하게 인식하고 해석하는 전문가입니다.
다음 메시지에서 시간 관련 표현을 분석하고 구체적인 시간 정보로 변환해주세요.

사용자 메시지: {input}

현재 날짜: {current_date}
현재 시간: {current_time}
이전 일정: {previous_schedules}

단계적으로 생각해보세요:
1. 메시지에서 모든 시간 관련 표현을 식별합니다.
2. 각 표현이 절대적 시간인지(예: "오전 10시"), 상대적 시간인지(예: "점심", "회의 후") 판단합니다.
3. 절대적 시간은 그대로 변환하고, 상대적 시간은 맥락을 고려하여 추론합니다.
4. 모호한 표현("점심시간")은 한국 문화권의 일반적인 시간대를 적용합니다:
   - 아침: 7시~9시
   - 오전: 9시~12시
   - 점심: 12시~14시
   - 오후: 14시~18시
   - 저녁: 18시~20시
   - 밤: 20시~23시
5. 상대적 시간 표현("~후")은 이전 일정의 종료 시간을 참고합니다.
6. 날짜 정보가 없으면 현재 날짜를 기준으로 합니다.

응답은 다음 JSON 형식으로 제공해주세요:
{format_instructions}
"""

# 우선순위 분석 프롬프트
PRIORITY_TEMPLATE = """
당신은 사용자의 일정 메시지를 분석하여 일정 간의 우선순위와 선후 관계를 파악하는 전문가입니다.
다음 메시지와 추출된 일정을 분석하여 각 일정의 우선순위를 결정해주세요.

사용자 메시지: {input}

추출된 일정:
{extracted_schedules}

단계적으로 생각해보세요:
1. 메시지에서 순서 표현("먼저", "그 다음", "마지막으로" 등)을 식별합니다.
2. 각 표현이 어떤 일정과 연관되어 있는지 파악합니다.
3. 표현된 순서, 언급된 순서, 시간 순서를 모두 고려하여 우선순위를 결정합니다.
4. 시간이 정해진 고정 일정은 시간순으로 정렬합니다.
5. 유연한 일정은 언급된 맥락과 표현을 고려하여 우선순위를 매깁니다.
6. 각 일정에 1-5 사이의 우선순위 점수를 할당합니다(1이 가장 높은 우선순위).

응답은 다음 JSON 형식으로 제공해주세요:
{format_instructions}
"""

# 프롬프트 템플릿 생성
time_inference_prompt = PromptTemplate(
    template=TIME_INFERENCE_TEMPLATE,
    input_variables=["input", "current_date", "current_time", "previous_schedules"],
    partial_variables={"format_instructions": time_parser.get_format_instructions()}
)

priority_prompt = PromptTemplate(
    template=PRIORITY_TEMPLATE,
    input_variables=["input", "extracted_schedules"],
    partial_variables={"format_instructions": priority_parser.get_format_instructions()}
)