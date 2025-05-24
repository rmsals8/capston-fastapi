# scheduler/chains.py (최적화됨)
import datetime
import json
from typing import Dict, Any
from langchain.chains import LLMChain
from langchain_openai import ChatOpenAI
from .config.prompts import (
    time_inference_prompt, 
    priority_prompt,
    time_parser,
    priority_parser
)
from .cache_manager import cached_result
import os

@cached_result("schedule_chain_creation", expire_seconds=3600)
def create_schedule_chain():
    """기존 일정 추출 체인 생성 (캐시됨)"""
    # 기존 app.py의 create_schedule_chain 함수와 동일
    pass

@cached_result("enhancement_chain_creation", expire_seconds=3600)
def create_enhancement_chain():
    """시간 추론 및 우선순위 분석 체인 생성 (캐시됨)"""
    llm = ChatOpenAI(
        model_name="gpt-3.5-turbo",  # gpt-4 대신 3.5-turbo 사용 (속도 향상)
        temperature=0,
        max_tokens=1500,  # 토큰 제한으로 응답 시간 단축
        request_timeout=30  # 타임아웃 설정
    )
    
    time_chain = LLMChain(
        llm=llm, 
        prompt=time_inference_prompt, 
        output_parser=time_parser,
        verbose=False  # 로깅 최소화
    )
    
    priority_chain = LLMChain(
        llm=llm, 
        prompt=priority_prompt, 
        output_parser=priority_parser,
        verbose=False  # 로깅 최소화
    )
    
    return {
        "time_chain": time_chain,
        "priority_chain": priority_chain
    }